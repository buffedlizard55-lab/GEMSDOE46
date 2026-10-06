"""GEMSDOE47 - catalogue-supervised multi-scale lineament detector + metric-algebraic emission.

Why this package exists (session 2026-10-06, hypothesis H47-1):

* Every arm in the GEMSDOE family that we could inspect emits from a *hand-built* transform of the
  official bands, with the published catalogue used only as a mask/exclusion.  GEMSDOE32 and
  GEMSDOE36 additionally contain supervised detectors (HistGradientBoosting grown on the catalogue
  and a small stress-regularised U-Net) whose best artefact scored 0.2750 - i.e. no better than the
  hand-built 0.2708/0.2778 line.  H47-1 is therefore *not* "train a model": it is a specific,
  checkable claim that a wider multi-scale oriented-lineament feature stack, trained with spatial
  blocking + hard-negative mining and coupled to an emission rule derived from the metric algebra,
  raises the *placement precision* of the emitted dots - the only quantity the live metric rewards
  once the mass is sparse.

* The emission rule is not tuned: it is the exact marginal condition of the published metric
  (``src/gems46/metric.py``) transcribed in ``emission.py``.

Evidence classes used in this package, following ``registry/irregularities.json``:
[OFFICIAL] organizer text, [MEASURED] computed here from hash-pinned bytes, [OWNER-REPORT] the
group's own unverified ledger, [INFERENCE] model output.  Nothing here is a leaderboard score.
"""

__version__ = "47.0.0"
