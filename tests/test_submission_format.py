"""Format contract of a GEMS submission, verified against the shipped file."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems46 import grid as G  # noqa: E402

REG = ROOT / "registry" / "submissions.json"
TEMPLATE = ROOT / "data" / "raw" / "sample_submission.tif"


def _shipped():
    if not REG.exists():
        pytest.skip("no built submission (run scripts/build_submission.py)")
    sub = json.loads(REG.read_text())
    return [(tag, ROOT / "docs" / "downloads" / rec["file"]) for tag, rec in sub["files"].items()]


def test_shipped_files_match_the_official_format():
    for tag, path in _shipped():
        assert path.exists(), f"{tag} missing"
        rep = G.audit(path, TEMPLATE)
        assert rep["count"] == 1, f"{tag}: must be single band"
        assert rep["dtype"] == "float32", f"{tag}: must be float32"
        assert rep["crs_match"] and rep["crs"] == "EPSG:32611"
        assert rep["shape_match"] and rep["transform_match"]
        assert rep["footprint_match"], f"{tag}: finite mask must equal the template's"
        assert rep["range_ok"] and rep["min"] >= 0.0 and rep["max"] <= 1.0
        assert rep["positive_px"] > 0


def test_values_are_binary_and_outside_is_nan():
    for tag, path in _shipped():
        with rasterio.open(path) as s:
            a = s.read(1)
        fin = np.isfinite(a)
        assert np.isnan(a[~fin]).all()
        v = np.unique(a[fin])
        assert set(np.round(v, 6)).issubset({0.0, 1.0}), f"{tag}: expected 0/1 emission, got {v[:8]}"


def test_emission_mass_is_the_validated_operating_point():
    """Mass must equal the live-matched operating point used in the validation receipts."""
    sub = json.loads(REG.read_text())
    for tag, rec in sub["files"].items():
        assert rec["audit"]["positive_px"] == sub["fields"]["budget"], tag


def test_no_emission_on_the_masked_catalogue():
    """The catalogue-buffer removal rule must actually hold in the shipped bytes."""
    with rasterio.open(ROOT / "data" / "raw" / "labels.tif") as s:
        cat = s.read(1) > 0
    from scipy import ndimage

    near = ndimage.binary_dilation(cat, iterations=2)
    for tag, path in _shipped():
        with rasterio.open(path) as s:
            emit = np.nan_to_num(s.read(1)) > 0
        assert not (emit & near).any(), f"{tag}: {int((emit & near).sum())} pixels inside the buffer"
