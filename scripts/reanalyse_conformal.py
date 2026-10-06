#!/usr/bin/env python
"""Re-run the authoritative split-conformal selection from the saved sweep.

Thin CLI over :mod:`gems46.conformal`; see that module for rules R1-R4.  Use it
instead of recomputing the 24-block sweep when only the selection changes.

    PYTHONPATH=src python scripts/reanalyse_conformal.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems46 import conformal as C  # noqa: E402
from gems46 import pipeline as P   # noqa: E402


def main() -> None:
    raw = json.loads((ROOT / "evidence/spacing_sweep_raw.json").read_text())
    out = C.select_from_raw(raw)

    print(f"blocks: total {out['n_blocks_total']}  eligible {out['n_blocks_eligible']}")
    print(f"        selection {out['n_selection']}  calibration {out['n_calibration']} "
          f"-> smallest usable alpha = {out['alpha']:.6f} "
          f"(confidence {100 * out['confidence']:.1f}%)")
    print(f"        excluded (no held-out truth): {out['excluded_tiles']}")
    print(f"[R3] declared |G| = {out['rule_R3']['declared_G_px']:.0f} px; largest dot count that can "
          f"still reach {out['rule_R3']['target_score']:.4f} = "
          f"{out['rule_R3']['max_dots_for_target']:,.0f}")
    print(f"     admissible arms: {out['rule_R3']['admissible_spacings']}")

    for pop in ("pop_thin", "pop_full"):
        print(f"\n[{pop}] chosen spacing = {out[pop]['chosen_spacing']:g} px "
              f"(certified floor {out[pop]['certified_floor_at_chosen']:.4f} at "
              f"{100 * out['confidence']:.1f}% confidence)")
        for s in P.SPACINGS:
            r = out[pop]["table"][str(s)]
            print(f"   r={s:<5g} sel={r['selection_mean']:.4f} cal={r['calibration_mean']:.4f} "
                  f"q={r['conformal_quantile']:.4f} floor={r['certified_floor']:.4f} "
                  f"dots~{r['median_dots_full_footprint']:,.0f}")

    for k, v in out["population_sensitivity"].items():
        print(f"[sensitivity] population {k:<12} ratio={v['ratio']:<8g} -> R3+R4 "
              f"r={v['rule_R3R4_choice']:g} px (floor {v['rule_R3R4_certified_floor']:.4f}); "
              f"score-only r={v['score_only_choice']:g} px")

    ship = out["ship"]
    print(f"\nSHIP r={ship['spacing_px']:g} px ({ship['why']}); "
          f"certified floor {ship['certified_floor']:.4f} at "
          f"{100 * ship['certified_confidence']:.1f}% confidence "
          f"({ship['n_calibration']} calibration blocks)")

    (ROOT / "evidence/conformal_selection.json").write_text(json.dumps(out, indent=2))
    (ROOT / "evidence/population_sensitivity.json").write_text(
        json.dumps(out["population_sensitivity"], indent=2))
    print("\nwrote evidence/conformal_selection.json and evidence/population_sensitivity.json")


if __name__ == "__main__":
    main()
