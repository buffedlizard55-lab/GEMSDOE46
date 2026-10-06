#!/usr/bin/env python3
"""Locked R11-D experiment (matched-filter contacts). Saves auditable, unsubmitted artifact."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from gems46.matchedfilter import score_pair, HALF, R_FLOOR, MIN_VALID_FRAC, ANGLES
from gems46 import grid, emission, metric


def read(path):
    with rasterio.open(path) as s:
        return s.read(1)


def correlation(a, b, mask):
    x, y = a[mask][::8], b[mask][::8]
    return dict(n=len(x), pearson=float(np.corrcoef(x, y)[0, 1]),
                spearman=float(spearmanr(x, y).statistic))


def audit(path, template):
    with rasterio.open(path) as s, rasterio.open(template) as t:
        a = s.read(1)
        checks = dict(single_band=s.count == 1, float32=s.dtypes == ('float32',),
            crs=s.crs == t.crs, shape=s.shape == t.shape, transform=s.transform == t.transform,
            finite=bool(np.isfinite(a).all()), range=bool(((a >= 0) & (a <= 1)).all()),
            no_nodata=s.nodata is None)
        assert all(checks.values()), checks
        return dict(checks=checks, min=float(a.min()), max=float(a.max()),
            positive=int((a > 0).sum()), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            pixel_sha256=hashlib.sha256(a.tobytes()).hexdigest(), bytes=path.stat().st_size,
            shape=list(s.shape), crs=str(s.crs), transform=list(s.transform))


def main():
    out = ROOT / 'docs/r11'; out.mkdir(exist_ok=True)
    derived = ROOT / 'data/derived'; derived.mkdir(exist_ok=True)
    raw = ROOT / 'data/raw'; template = raw / 'sample_submission.tif'
    # All inputs pinned before scientific use.
    manifest = json.loads((ROOT / 'registry/data_manifest.json').read_text())
    hashes = {}
    for item in manifest['files']:
        p = ROOT / item['dest']; sha = hashlib.sha256(p.read_bytes()).hexdigest()
        assert sha == item['sha256'], p
        hashes[item['dest']] = sha
    fp = grid.footprint(template, raw / 'training_features.tif')
    cat = (read(raw / 'labels.tif') > 0) & fp
    exclusion = ndimage.binary_dilation(cat, iterations=2)
    domain = fp & ~exclusion
    truth = (read(ROOT / 'data/external/sgmc_faults_100m_u8.tif') > 0) & domain
    blocks_id = read(ROOT / '.mirror/GEMSDOE24/data/external/audit_sources/acquisition_block_id_100m.tif')
    assert blocks_id.shape == fp.shape
    bands = {}
    with rasterio.open(raw / 'training_features.tif') as src:
        for band, name in [(2, 'rtp'), (13, 'gravity')]:
            a = src.read(band, masked=True).filled(np.nan)
            print('R11-D', name, src.descriptions[band - 1], flush=True)
            bands[name] = (a, fp & np.isfinite(a))
    valid = bands['rtp'][1] & bands['gravity'][1]
    rtp = np.where(bands['rtp'][1], bands['rtp'][0], 0)
    grav = np.where(bands['gravity'][1], bands['gravity'][0], 0)
    field, support, diag = score_pair(rtp, grav, valid)
    print('scorer diagnostics', json.dumps(diag), flush=True)
    support = support & domain
    np.save(derived / 'r11d_field.npy', field)
    np.save(derived / 'r11d_support.npy', support)
    controls = {}
    for name, (a, v) in bands.items():
        filled = np.where(v, a, 0)
        blurred = ndimage.gaussian_filter(filled, 3)
        gy, gx = np.gradient(blurred)
        controls[name + '_gradient'] = np.hypot(gy, gx)
        controls[name + '_curvature'] = np.abs(ndimage.laplace(blurred))
    candidate, _ = emission.greedy_emit(field, domain & support, 37654, min_dist=3, smooth_px=1.85)
    assert candidate.sum() == 37654
    values = candidate.astype('float32')
    pixelhash = hashlib.sha256(values.tobytes()).hexdigest()
    filename = f'gems46-r11d-matchedfilter-{pixelhash[:12]}-zeros.tif'
    with rasterio.open(template) as t:
        profile = t.profile.copy()
    profile.update(count=1, dtype='float32', nodata=None, compress='deflate', predictor=3)
    path = out / filename
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(values, 1)
    receipt = audit(path, template)
    refs = {
        'GEMSDOE32-owner-reported-02778': ROOT / 'data/derived/incumbent_02778.tif',
        'H46-structural-DFA': ROOT / 'docs/downloads/gems46-h46-2-dfa-corroborated-zeros.tif',
        'R8-conformal': ROOT / 'SUBMISSION-GEMSDOE46-r8-conformal.tif',
        'R9-conformal': ROOT / 'docs/r9/downloads/gems46-r9-conformal-s5-20261006T110804Z.tif',
        'H46-pure-DFA': ROOT / 'docs/downloads/gems46-h46-1-dfa-regime-break-zeros.tif',
        'R10-DFA-crossover': ROOT / 'docs/r10/gems46-r10-dfa-crossover-95ba59eb9030-zeros.tif'}
    comparisons = {}; fields = {'R11-D': field}
    mask = domain & support
    smooth = ndimage.gaussian_filter(field, 8)
    for name, p in refs.items():
        if not p.exists():
            comparisons[name] = {'missing': True}; continue
        with rasterio.open(p) as s:
            assert s.shape == fp.shape and s.transform == profile['transform'] and s.crs == profile['crs']
        a = np.nan_to_num(read(p), nan=0, posinf=0, neginf=0)
        assert np.all((a >= 0) & (a <= 1))
        fields[name] = a
        assert not np.array_equal(values, a), 'candidate duplicates comparator'
        old = a > 0
        comparisons[name] = dict(file=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            pixel_identical=bool(np.array_equal(values, a)),
            candidate_pearson=correlation(values, a, domain),
            field_vs_smoothed_submission=correlation(smooth, ndimage.gaussian_filter(a, 8), mask),
            jaccard=float((candidate & old).sum() / max((candidate | old).sum(), 1)))
    for name, a in controls.items():
        comparisons[name] = dict(raw=correlation(field, a, mask),
            smoothed=correlation(smooth, ndimage.gaussian_filter(a, 8), mask))
    # Scan every shipped local raster for pixel equality, not just byte inequality.
    equality = []
    for p in sorted(set(ROOT.glob('*.tif')) | set((ROOT / 'docs').rglob('*.tif'))):
        if p == path:
            continue
        a = read(p)
        equality.append(dict(file=str(p.relative_to(ROOT)), equal=bool(a.shape == values.shape and np.array_equal(np.nan_to_num(a), values))))
    assert not any(x['equal'] for x in equality)
    survey = {}
    for bid in (1, 2, 3, 4):
        cells = mask & (blocks_id == bid)
        survey[f'block_{bid}'] = dict(cells=int(cells.sum()),
            emitted=int((candidate & cells).sum()), truth=int((truth & cells).sum()),
            field_mean=float(field[cells].mean()) if cells.any() else 0.0)
    print('Validating spatial blocks', flush=True)
    # Fixed detector, no fitting to proxy labels. Per-block common counts, exclusions and guard.
    re = np.linspace(0, fp.shape[0], 5, dtype=int); ce = np.linspace(0, fp.shape[1], 5, dtype=int)
    folds = []; skipped = []
    for i in range(4):
        for j in range(4):
            sl = np.s_[re[i] + 3:re[i + 1] - 3, ce[j] + 3:ce[j + 1] - 3]
            d = domain[sl]; target = truth[sl]
            if target.sum() == 0 or d.sum() == 0:
                skipped.append(dict(block=4 * i + j, reason='no proxy truth or empty domain')); continue
            budget = int(round(37654 * d.sum() / domain.sum()))
            masks = {}; scores = {}
            for name, f in fields.items():
                masks[name], _ = emission.greedy_emit(f[sl], d, budget, min_dist=3, smooth_px=1.85)
            # Where a sparse reference cannot supply the budget, compare all at minimum count.
            n = min(int(a.sum()) for a in masks.values())
            if n == 0:
                skipped.append(dict(block=4 * i + j, reason='zero shared emission capacity',
                    counts={k: int(v.sum()) for k, v in masks.items()})); continue
            for name, f in fields.items():
                pred, _ = emission.greedy_emit(f[sl], d, n, min_dist=3, smooth_px=1.85)
                assert pred.sum() == n
                scores[name] = metric.components_binary(pred, target, valid=d).as_dict()
            folds.append(dict(block=4 * i + j, emitted_each=n, truth=int(target.sum()), scores=scores))
            print('block', 4 * i + j, 'mass', n, 'R11-D', scores['R11-D']['dti'], flush=True)
    means = {n: float(np.mean([b['scores'][n]['dti'] for b in folds])) for n in fields}
    best = max((n for n in fields if n != 'R11-D'), key=means.get)
    delta = np.array([b['scores']['R11-D']['dti'] - b['scores'][best]['dti'] for b in folds])
    rng = np.random.default_rng(4613)
    ci = np.percentile(rng.choice(delta, (10000, len(delta)), replace=True).mean(axis=1), [2.5, 97.5])
    gate = bool(not any(b['reason'] == 'zero shared emission capacity' for b in skipped) and len(folds) >= 8 and ci[0] > 0 and means['R11-D'] > means[best] and not any(x.get('missing') for x in comparisons.values()))
    coeff = []
    for rec in comparisons.values():
        for key in ('raw', 'smoothed', 'field_vs_smoothed_submission'):
            if key in rec:
                coeff += [abs(rec[key][k]) for k in ('pearson', 'spearman')]
    distinct = bool(coeff and np.isfinite(coeff).all() and max(coeff) < 0.2)
    result = dict(experiment='H46-R11D', generated_utc=datetime.now(timezone.utc).isoformat(),
        file=filename, note='R11-D step-template matched filter (Pearson r, 4 angles, dual-physics coincidence), RTP + isostatic gravity; 37,654 dots; research candidate, proxy-gated, no leaderboard score.',
        parameters=dict(template_half_width_px=HALF, template_taps=2 * HALF + 1, angles=list(ANGLES),
            r_floor=R_FLOOR, min_valid_frac=MIN_VALID_FRAC, bands=[2, 13],
            budget=37654, min_dist_argument=3, smooth_px=1.85,
            catalogue_cross_dilation_iterations=2, block_grid=[4, 4], guard_pixels=3,
            bootstrap_seed=4613, correlation_sampling='every eighth pixel of fixed common-valid mask'),
        session_arms=dict(
            R11A='STOPPED FOR FUTILITY at synthetic stage (Amendment 2): windowed-DFA boundary mislocalized 4.4 km on locked step; no TIF.',
            R11C='SUSPENDED at synthetic stage (Addendum 4): tilt zero-crossing not robust to grid noise after 6 iterations; no TIF.',
            R11D='This experiment: matched-filter contacts; D-S1/D-S2/D-S3 all passed (1.0/0.0/0.0).'),
        source_hashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
            ['scripts/run_r11d.py', 'src/gems46/matchedfilter.py', 'src/gems46/emission.py', 'src/gems46/metric.py']},
        input_hashes=hashes, audit=receipt, support_pixels=int(support.sum()),
        scorer_diagnostics=diag, survey_block_audit=survey,
        comparisons=comparisons, local_pixel_uniqueness=equality,
        folds=folds, skipped_blocks=skipped, mean_block_dti=means, best_comparator=best,
        paired_delta=float(delta.mean()), paired_bootstrap_95=ci.tolist(), gate_passed=gate,
        low_correlation_gate_passed=distinct, max_absolute_correlation=max(coeff),
        status='PROXY_GATE_PASSED_NOT_SUBMITTED' if gate else 'HOLD_DO_NOT_SUBMIT',
        limitations=['SGMC is an imperfect reused proxy, not hidden competition truth.',
          'Matched-mass comparator rules re-emit fields within each block; these are not scores of original files.',
          '25-tap template merges contacts closer than ~1.2 km; |r|>=0.8 floor drops weak/gradual contacts.',
          'Correlation cannot establish geological independence or fault discovery.',
          'Unique against inspected local rasters and restored GEMSDOE32 only; universal uniqueness not verified.'])
    (out / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    (ROOT / 'registry/r11.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('file', 'mean_block_dti', 'paired_delta', 'paired_bootstrap_95', 'status', 'low_correlation_gate_passed', 'max_absolute_correlation')}, indent=2))


if __name__ == '__main__':
    main()
