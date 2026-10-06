# Competition data staging

No official competition data is present in this checkout. The official DrivenData data page is enrollment/login-gated; do not bypass it.

1. Enroll/sign in and download the official archive through the participant portal.
2. Put exactly one downloaded `.zip` in `data/inbox/` (or set `GEMS_DATA_ARCHIVE=/path/to/archive.zip`).
3. Run `bash scripts/download_competition_data.sh`. Despite the historical script name, it is intentionally **offline**: it only safely imports a local archive and never contacts DrivenData.
4. Identify the actual feature, label, and sample filenames in the extracted archive. Create the project environment with `python -m venv .venv && .venv/bin/python -m pip install -e '.[test]'`, then run `.venv/bin/python scripts/validate_inputs.py --features … --labels … --sample …`. Do not guess layer order, nodata semantics, or sample bounds.

Raw and processed data are ignored by Git to avoid redistributing restricted or large inputs. Keep the official archive, its hash, and any external-data license/attribution record with your private research files. Share external sources with competition organizers only as permitted by the source license and the competition rules.
