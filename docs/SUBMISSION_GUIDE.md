# How to submit — step by step

This page exists because the brief asks for it explicitly ("create an executive summary
subpage that explains exactly how to make a submission into the contest"), and because
the portfolio has already lost time to a format rejection (`docs/IRREGULARITIES.md`
IR-46-02).

---

## 0. What you are uploading

| | |
| --- | --- |
| **File to upload** | `SUBMISSION-GEMSDOE46-r8-conformal.tif` (repository root, and mirrored at `docs/SUBMISSION-GEMSDOE46-r8-conformal.tif`) |
| Same file on the published site | `…/GEMSDOE46/SUBMISSION-GEMSDOE46-r8-conformal.tif` (link at the very top of the executive summary) |
| **Suggested name** | `gemsdoe46-h46a-r8-conformal` |
| **Note to paste** | copy the single line in `docs/downloads/NOTE-gemsdoe46-h46a-r8-conformal.txt` — it contains the spacing, the conformal confidence level and the certified floor |
| Audits of that exact file | `docs/downloads/checks-gemsdoe46-h46a-r8-conformal-allfinite.json` |
| Fallback file (same dots, `NaN` outside the survey bounds, exactly like `sample_submission.tif`) | `docs/gemsdoe46-h46a-r8-conformal-nan.tif` |

The two files contain **the same 39,108 positive cells**; they differ only in how the
out-of-survey region is encoded (0.0 vs `NaN`). They are provably identical under the
official metric (see IR-46-02). Upload the primary; if the form complains about values,
upload the `-nan` one instead.

---

## 1. The format rules, quoted from the official problem page

From <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>
(section *Submission format*), the file must be:

* "in the same projected coordinate reference system as the training data (projected
  coordinate system for UTM zone 11N, EPSG 32611)" — the shipped file is `EPSG:32611`;
* "at the same resolution as the training data (100m)" — the shipped file is 100 m;
* "the same bounds as the training data, and data outside the bounds is null or nan" —
  the shipped file has exactly the template's shape `(3730, 3292)` and geotransform
  `(100, 0, 243350, 0, -100, 4508550)`;
* "a single layer with datatype of 32-bit float (float32) with values between 0 and 1
  indicating the confidence or probability of fault presence" — the shipped file is
  single-band `float32` whose minimum is `0.0` and maximum is `1.0`.

The organizer's own summary of the same rule, as quoted in the brief: *"You can submit a
single-band GeoTIFF (.tif) file, or a .zip file containing a single GeoTIFF, with your
predictions. It must match the submission format's CRS, shape, and geotransform."*

The form also has an optional **Note** field: *"A short comment to help you or your team
tell submissions apart later e.g. clustering with k=25"*. Paste the generated note line —
it is the audit trail for this submission (spacing, conformal confidence, certified
floor, dot count, declared `|G|` and the analytic ceiling).

---

## 2. The click path

1. Sign in at <https://www.drivendata.org/> and open the competition:
   <https://www.drivendata.org/competitions/306/competition-doe-gems/>.
2. Open the **Submit** tab (the same tab that carries the data download links).
3. Download `SUBMISSION-GEMSDOE46-r8-conformal.tif` from this repository (the link is the
   first thing on the executive summary page, and also the first thing in the README).
4. Choose that file in the form's file picker. Do **not** re-save, re-scale or re-encode
   it: the file is already `float32` in `[0, 1]` with the exact template geometry.
5. Paste the note line from `docs/downloads/NOTE-gemsdoe46-h46a-r8-conformal.txt` into
   the optional **Note** field, and use `gemsdoe46-h46a-r8-conformal` as the name if the
   form asks for one.
6. Submit, then confirm the row appears on your submissions list with a DW-Tversky
   score.

If the form returns `"Predicted values must be in range [0, 1]"`, upload
`docs/gemsdoe46-h46a-r8-conformal-nan.tif` instead — the encoding question is the only
difference between the two files — and record the event here
(`docs/IRREGULARITIES.md` IR-46-02).

---

## 3. Verify the file yourself before uploading (optional, 30 seconds)

With GDAL:

```bash
gdalinfo -stats SUBMISSION-GEMSDOE46-r8-conformal.tif | head -20
# expect: 1 band, Type=Float32, EPSG:32611, 3292 x 3730, 100 m pixels,
#         STATISTICS_MINIMUM=0, STATISTICS_MAXIMUM=1
```

With Python:

```bash
python - <<'PY'
import rasterio, numpy as np, json
p = "SUBMISSION-GEMSDOE46-r8-conformal.tif"
with rasterio.open(p) as s:
    a = s.read(1)
    print(s.dtypes[0], (s.height, s.width), s.crs, tuple(s.transform)[:6])
    print("min", a.min(), "max", a.max(), "positives", int((a > 0).sum()))
print(json.load(open("docs/downloads/checks-gemsdoe46-h46a-r8-conformal-allfinite.json")))
PY
```

Every one of those fields is also asserted programmatically at write time:
`src/gems46/submit.py::audit` re-opens the file from disk and refuses to let
`make_submission.py` finish unless each check passes and the byte-level positive count
equals the number of emitted dots.

---

## 4. How this submission is unique

* It is generated from the **official rasters only** (hashes in IR-46-01), by this
  repository's own model, emitter and selection rules. No raster, weight, dot list or
  archive from any other submission was copied, downloaded or re-used.
* The **operating point is certified, not chosen by eye**: r = 8 px (800 m minimum
  separation) is the arm with the largest split-conformal floor (0.0283 at 90 %
  confidence, α = 0.1000, 9 exchangeable calibration blocks) among the arms that also
  pass the density-admissibility rule R3 at the declared scored-truth mass. The exact
  rule text is in `src/gems46/conformal.py`.
* Its **density is checked against the metric's own algebra**: 39,108 dots against the
  86,541-dot upper limit that still allows a perfect-placement score of 0.3345 at the
  declared `|G| = 7,905 px`; the analytic ceiling for this arm is 0.5588.
* Its **geology is different from the catalogue-driven submissions**: the feature stack
  is multi-scale L2 curvature (elevation, tilt-angle, TMI, RTP, isostatic gravity) plus
  official gradient/edge and cover proxies, and it contains **no distance-to-known-fault
  feature at all** (`src/gems46/features.py`, "Deliberate exclusion").

---

## 5. Reproduce it from scratch

```bash
bash   scripts/download_competition_data.sh     # needs a signed-in DrivenData session
python scripts/prepare_data.py                  # place/verify the 3 rasters in data/
python scripts/run_pipeline.py                  # hash verify -> 24-block sweep -> conformal
python scripts/make_submission.py               # rules pick the arm, writes + audits the TIFF
```

`run_pipeline.py --stage post` re-runs only the selection from saved blocks (seconds),
which is the cheap path when only a rule changes.
