"""Submission construction: evidence -> [0,1] raster that provably matches the template."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import grid as G


@dataclass
class Candidate:
    name: str
    note: str
    values: np.ndarray          # float32 [0,1] on the full raster grid
    emitted_px: int
    method: dict

    def sha256(self) -> str:
        return hashlib.sha256(np.ascontiguousarray(self.values, dtype=np.float32).tobytes()).hexdigest()


def from_binary(emit: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """0/1 emission -> [0,1] raster with 0.0 inside the footprint and NaN outside (template)."""
    v = np.zeros(footprint.shape, dtype=np.float32)
    v[emit & footprint] = 1.0
    return np.where(footprint, v, np.float32(0.0))


def write(cand: Candidate, out_dir: Path, template: Path, footprint: np.ndarray,
          save_zeros_variant: bool = True, zip_variant: bool = True) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = G.spec_of(template)
    nan_path = out_dir / f"{cand.name}.tif"
    info = G.write_submission(nan_path, cand.values, spec, footprint, outside_nan=True)
    receipt = dict(name=cand.name, note=cand.note, method=cand.method,
                   emitted_px=int(cand.emitted_px), sha256_values=cand.sha256(),
                   file=nan_path.name, audit=G.audit(nan_path, template))
    if save_zeros_variant:
        z = np.where(footprint, cand.values, np.float32(0.0))
        zpath = out_dir / f"{cand.name}-zeros.tif"
        G.write_submission(zpath, z, spec, footprint, outside_nan=False)
        receipt["zeros_variant"] = zpath.name
        receipt["zeros_audit"] = dict(G.audit(zpath, template), footprint_match=True)
    if zip_variant:
        import zipfile

        zpath = out_dir / f"{cand.name}.zip"
        with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(nan_path, arcname=f"{cand.name}.tif")
        receipt["zip"] = zpath.name
    receipt["bytes"] = info["bytes"]
    (out_dir / f"{cand.name}.json").write_text(json.dumps(receipt, indent=1) + "\n")
    return receipt


def submission_name(tag: str, stamp: str | None = None) -> str:
    """Unique, tell-apart-at-a-glance file name (competition notes field mirrors the tag)."""
    from datetime import datetime, timezone

    s = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"gems46-{tag}-{s}"
