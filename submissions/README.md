# Submission artifact policy

There is currently **no submission TIF** in this repository. Do not create a placeholder or use a weekly slot to test an unvalidated idea.

When official data and a current holdout-best artifact are available:

1. Produce candidate and baseline out-of-fold probability rasters with the same four contiguous spatial folds and 300 m label embargo.
2. Create a validation manifest and run `.venv/bin/python scripts/evaluate_holdout.py …`.
3. Proceed only when the report passes the registered global-DTI, foldwise, prediction-mass, and provenance gates.
4. Before packaging, provide every known prior submission TIF via `--prior-submission` (repeat as needed). If and only if no prior artifact exists, explicitly pass `--no-prior-submissions`.
5. Run `.venv/bin/python scripts/build_submission.py …`; it creates a dated, content-fingerprinted filename and a JSON receipt. Then independently rerun `.venv/bin/python scripts/validate_submission.py --submission … --sample …` against the official sample grid.

Output rasters/receipts are ignored by Git. If a final artifact must be included for competition reproducibility, first review its licensing, provenance, size, and disclosure requirements; do not commit raw competition data.
