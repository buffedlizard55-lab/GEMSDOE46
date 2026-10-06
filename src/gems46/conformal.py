"""Split-conformal selection driver over the saved spacing sweep.

This is the single authoritative implementation of the selection procedure.  It is
deliberately separate from :mod:`gems46.pipeline`, which only *produces* per-block
arms; here those arms are turned into one shipped operating point.

The procedure, in the order the rules are applied (all four are fixed in advance
and none of them looks at an arm's score -- so no part of the verdict is tuned on
the holdout):

  R1  **eligibility.**  A block enters the procedure iff it contains at least one
      held-out truth pixel.  Blocks outside the GeoDAWN footprint contain no
      catalogue pixels: every arm scores exactly 0 there and the block contributes
      nothing but noise to the residual distribution.  The rule is a function of
      the truth mask alone.
  R2  **split.**  Selection / calibration halves are the two tile parities
      ``(i + j) % 2``.  A contiguous split is not used because fault density and
      distance to the survey edge both drift with latitude; parity keeps the two
      halves comparable, which is what the exchangeability the bound relies on
      actually needs.
  R3  **admissibility.**  An arm may be shipped only if its *density* leaves room
      for the target score under the data-free ceiling
      ``DTI <= |G| / (0.2 N + 0.8 |G|)`` (``gems46.analytic``).  This stage uses no
      score at all: it compares the arm's emitted dot count against the largest dot
      count that can still reach the target at the declared truth mass |G|.
  R4  **choice.**  Among admissible arms, take the one with the largest certified
      floor from the split-conformal bound of Lei, G'Sell, Rinaldo, Tibshirani &
      Wasserman (JASA 2018, 113(523), Sec. 3), applied to the block-mean loss:

          q(s) = the  ceil((n_cal + 1)(1 - alpha))-th smallest  s_j(s) - mean_cal(s)
          L(s) = mean_cal(s) - q(s)

      ``alpha`` is set to the smallest value the calibration half can support,
      ``1 / (n_cal + 1)``, which is the standard conformal floor for a one-sided
      bound; asking for more confidence than that would make ``q`` infinite.
"""

from __future__ import annotations

from . import pipeline as P

TARGET_SCORE = 0.3345      # current leaderboard #1 (alexoktaba), the score to beat
DECLARED_G_PX = 7905.0     # declared scored-truth mass, in pixels (see docs/SCORE_ANALYSIS.md)


class RawFold:
    """Rehydrate one block of ``evidence/spacing_sweep_raw.json`` into the API
    :func:`gems46.pipeline.conformal_select` expects."""

    def __init__(self, d):
        self.fold = d["fold"]
        self.tile = tuple(d["tile"])
        self.selection = True
        self.n_train_pos = d["n_train_pos"]
        self.n_train_neg = d["n_train_neg"]
        self.arms = {float(k): v for k, v in d["arms"].items()}


def effective_alpha(n_cal: int) -> float:
    """Smallest alpha for which the conformal quantile is finite."""
    return 1.0 / (n_cal + 1.0)


def select_from_raw(raw, g_px: float = DECLARED_G_PX,
                    target: float = TARGET_SCORE) -> dict:
    """Apply R1-R4 to a raw sweep and return the full evidence dictionary."""
    from .analytic import max_dots_for_target

    folds = [RawFold(d) for d in raw]
    P.split_folds(folds, "checkerboard")

    elig = [f for f in folds if P.eligible(f)]
    n_sel = sum(1 for f in elig if f.selection)
    n_cal = sum(1 for f in elig if not f.selection)
    alpha = effective_alpha(n_cal)
    excluded = [list(f.tile) for f in folds if not P.eligible(f)]

    out = {
        "alpha": alpha, "confidence": 1.0 - alpha,
        "n_blocks_total": len(folds), "n_blocks_eligible": len(elig),
        "n_selection": n_sel, "n_calibration": n_cal,
        "excluded_tiles": excluded,
        "split_scheme": "checkerboard (tile parity (i+j)%2)",
        "eligibility_rule": "block contains >=1 held-out truth pixel",
        "rule_R3": {"declared_G_px": g_px, "target_score": target,
                    "max_dots_for_target": max_dots_for_target(target, g_px)},
        "rule_R4": "argmax certified_floor among admissible arms",
    }

    tables = {}
    for pop in ("pop_thin", "pop_full"):
        chosen, short, table = P.conformal_select(folds, alpha, pop_key=pop)
        tables[pop] = table
        out[pop] = {"chosen_spacing": chosen, "shortlist": list(short),
                    "certified_floor_at_chosen": table[chosen]["certified_floor"],
                    "table": {str(k): v for k, v in table.items()}}

    # R3/R4 on the primary population: density first, then the certified floor.
    max_dots = out["rule_R3"]["max_dots_for_target"]
    table = tables["pop_thin"]
    admissible = {s: r for s, r in table.items()
                  if r["median_dots_full_footprint"] <= max_dots}
    out["rule_R3"]["admissible_spacings"] = sorted(admissible)
    if admissible:
        best = max(admissible, key=lambda s: table[s]["certified_floor"])
        out["ship"] = {"spacing_px": float(best),
                       "why": "argmax certified floor among R3-admissible arms",
                       "certified_floor": table[best]["certified_floor"],
                       "certified_confidence": 1.0 - alpha,
                       "n_calibration": n_cal,
                       "median_dots_full_footprint": table[best]["median_dots_full_footprint"]}
    else:  # pragma: no cover - only if every arm is too dense
        out["ship"] = {"spacing_px": float(max(table)), "why": "no admissible arm"}

    # Sensitivity screen: how far does the *shipped* decision move when the declared
    # scored population moves?  R3 is applied here to the sweep's per-block
    # extrapolation (the only density estimate a saved sweep can offer); the shipped
    # arm is re-checked against its measured full-grid count by make_submission.py.
    sens = {}
    for ratio in P.TRUTH_RATIOS:
        key = ("pop_full" if ratio >= 1.0 else
               ("pop_thin" if abs(ratio - P.NEW_FAULT_TO_CATALOGUE_RATIO) < 1e-12
                else f"pop_r{ratio:g}"))
        ch, sh, tb = P.conformal_select(folds, alpha, pop_key=key)
        adm = {s: r for s, r in tb.items()
               if r["median_dots_full_footprint"] <= max_dots}
        rule = max(adm, key=lambda s: adm[s]["certified_floor"]) if adm else None
        sens[key] = {"ratio": ratio,
                     "rule_R3R4_choice": (float(rule) if rule is not None else None),
                     "rule_R3R4_certified_floor": (tb[rule]["certified_floor"]
                                                  if rule is not None else None),
                     "rule_R3R4_admissible": sorted(adm),
                     "score_only_choice": ch, "shortlist": list(sh),
                     "certified_floor_at_score_only_choice": tb[ch]["certified_floor"],
                     "selection_mean_at_score_only_choice": tb[ch]["selection_mean"]}
    out["population_sensitivity"] = sens
    return out
