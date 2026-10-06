import numpy as np
import pytest
from gems46.crossover import slopes, coarse_maps, score_maps, expand
from gems46.dfa import alpha_reference, alpha_map, transect_alpha


def test_slopes_reference_and_affine_invariance():
    a = np.random.default_rng(42).normal(size=(40,512))
    full,short,long = slopes(a)
    np.testing.assert_allclose(full, [alpha_reference(x,(8,16,32,64,96,128)) for x in a],atol=1e-9)
    np.testing.assert_allclose(slopes(a*13+700)[0],full,atol=1e-11)
    assert 0.4 < np.median(full) < 0.65
    assert 1.3 < np.median(slopes(a.cumsum(axis=1))[0]) < 1.7
    assert np.isnan(slopes(np.ones((1,512)))[0]).all()
    with pytest.raises(ValueError): slopes(a[:,:100])


def test_old_map_center_alignment():
    a = np.random.default_rng(12).normal(size=(256,256))
    row,col,rc,cc = alpha_map(a,np.ones_like(a,bool))
    centers, expected = transect_alpha(a[0])
    np.testing.assert_array_equal(centers,rc)
    np.testing.assert_allclose(row[0],expected,rtol=1e-6,equal_nan=True)


def test_maps_gap_support_and_transpose():
    a = np.random.default_rng(2).normal(size=(544,544)).astype('float32')
    valid = np.ones_like(a,bool)
    m,r,c = coarse_maps(a,valid)
    mt,_,_ = coarse_maps(a.T,valid.T)
    np.testing.assert_allclose(m[0],mt[1].transpose(0,2,1))
    s,v = score_maps(m)
    out,support = expand(s,v,r,c,a.shape)
    assert not support[0].any()
    assert np.isfinite(out).all() and out.max() <= 1
    valid[256,100] = False
    m,_,_ = coarse_maps(a,valid)
    assert np.isnan(m[0,:,0,0]).all()


def test_binary_metric_empty_prediction_has_zero_credit():
    from gems46.metric import components_binary
    truth = np.zeros((8,8),bool); truth[0,0] = True
    c = components_binary(np.zeros_like(truth),truth)
    assert c.tp == 0 and c.fn == 1 and c.dti == 0


def test_shipped_r10_receipt_and_gate():
    import json, hashlib
    import rasterio
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root/'registry/r10.json').read_text())
    p = root/'docs/r10'/receipt['file']
    assert hashlib.sha256(p.read_bytes()).hexdigest() == receipt['audit']['sha256']
    with rasterio.open(p) as src:
        a = src.read(1)
        assert src.count == 1 and src.dtypes == ('float32',)
        assert str(src.crs) == 'EPSG:32611' and src.shape == (3730,3292)
        assert np.isfinite(a).all() and a.min() >= 0 and a.max() <= 1
        assert src.nodata is None and (a>0).sum() == 37654
        assert hashlib.sha256(a.tobytes()).hexdigest() == receipt['audit']['pixel_sha256']
    assert not receipt['gate_passed'] and receipt['status'] == 'HOLD_DO_NOT_SUBMIT'
    assert receipt['low_correlation_gate_passed']
    assert all(not r['equal'] for r in receipt['local_pixel_uniqueness'])


def test_active_site_local_links():
    """The active three pages must be link-clean and must state the *current* receipt's status.

    This test used to hard-code the R10 HOLD banner.  It now reads `registry/r11.json`, so the
    contract it enforces is "the page agrees with the receipt", not "the page says HOLD".
    """
    import json
    from html.parser import HTMLParser
    from pathlib import Path
    from urllib.parse import urlparse, unquote
    root = Path(__file__).resolve().parents[1]
    receipt = json.loads((root / 'registry/r11.json').read_text())

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for name, value in attrs:
                if name in ('href', 'src'):
                    url = urlparse(value)
                    if not url.scheme and url.path:
                        assert (self.base / unquote(url.path)).is_file(), value

    for page in ('index.html', 'docs/index.html', 'docs/executive-summary.html'):
        parser = Links()
        parser.base = (root / page).parent
        text = (root / page).read_text()
        parser.feed(text)
        assert receipt['candidate']['file'] in text, page
        assert receipt['candidate']['sha256'][:16] in text, page
        if receipt['status'] == 'HOLD_DO_NOT_SUBMIT':
            assert 'do not submit' in text, page
        else:
            assert receipt['status'] in text or 'Proxy gate passed' in text, page
