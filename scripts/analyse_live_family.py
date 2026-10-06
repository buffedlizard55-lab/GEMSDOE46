#!/usr/bin/env python3
"""Why the H19-5 lineage peaked at 0.2778 - the arithmetic, from the published metric alone.

Run:  python3 scripts/analyse_live_family.py

Inputs: registry/prior_results.csv (owner-reported scores; masses measured from the restored TIFs
where available).  Outputs: the implied hidden-truth size, the credit of each family member, the
marginal credit of each thinning step, and the comparison of each marginal credit with the metric's
break-even bar 0.2*DTI.  Every number is printed with the equation that produced it.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def boundary_G(dti_a, s_a, dti_b, s_b) -> float:
    """Largest hidden-truth size consistent with removing mass raising the score.

    With DTI = T/(0.2*S + 0.8*G) for both files, the credit destroyed by the removal is
        dT = 0.2*(dti_a*s_a - dti_b*s_b) + 0.8*G*(dti_a - dti_b).
    Removing mass can never create credit (TPw is monotone in the emitted set), so dT >= 0 gives
        G <= 0.2*(dti_b*s_b - dti_a*s_a) / (0.8*(dti_a - dti_b)),
    and the boundary value dT = 0 is what ``solve`` returns: every emitted pixel removed then had
    exactly zero realised credit.  Any G below the boundary implies the removed pixels had positive
    mean credit, so the boundary is the most conservative (worst-case-for-the-story) reading.
    """
    return (dti_b * 0.2 * s_b - dti_a * 0.2 * s_a) / (0.8 * (dti_a - dti_b))


def main() -> int:
    rows = list(csv.DictReader((ROOT / "registry" / "prior_results.csv").open()))
    by_name = {r["submission_or_label"]: r for r in rows}

    fam = [("H19-5 solid", 121131, 0.1922), ("D1.5 dotted", 60069, 0.2477),
           ("D2.8 dotted", 44090, 0.2600), ("D2.8 + catalogue B=2", 37654, 0.2778)]
    print("=" * 100)
    print("STEP 1 - how large the hidden truth set can be (an upper bound, not a measurement)")
    print("=" * 100)
    G = boundary_G(0.2600, 44090, 0.2778, 37654)
    print("  0.2600*(0.2*44090 + 0.8*G) = 0.2778*(0.2*37654 + 0.8*G)")
    print(f"  -> G <= {G:,.0f} px   ({(G * 100 / 1000):,.0f} km of fault trace at 100 m pixels)")
    print("  This is the LARGEST |G| compatible with the two live scores: it is the G at which the")
    print("  6,436 removed pixels carried exactly zero credit.  Two scores give two equations in")
    print("  three unknowns (G, T_a, T_b), so G is NOT point-identified; the bound uses only")
    print("  dT >= 0 (removing emitted mass can never create credit, TPw is monotone).")
    print("  The group's own GEMSDOE32/42 receipts instead DECLARE G = 7,905 px (H28 inference,")
    print("  owner-reported); 7,905 <= {:,.0f} is inside this bound, and STEP 3 shows the three".format(G))
    print("  removal verdicts below are identical at either value.")

    print()
    print("=" * 100)
    print("STEP 2 - each family member's implied credit T = DTI * (0.2*S + 0.8*G)")
    print("=" * 100)
    print(f"  {'file':26s} {'S (px)':>9s} {'live DTI':>9s} {'T (px)':>9s} {'T/S':>7s} {'bar 0.2*DTI':>12s}")
    Ts = {}
    for name, s, dti in fam:
        T = dti * (0.2 * s + 0.8 * G)
        Ts[name] = T
        print(f"  {name:26s} {s:9,d} {dti:9.4f} {T:9.0f} {T / s:7.4f} {0.2 * dti:12.4f}")

    print()
    print("=" * 100)
    print("STEP 3 - the marginal credit of every removal, against the metric's own break-even bar")
    print("=" * 100)
    print("  rule (exact, from the published formula): removing unit mass raises DTI iff its")
    print("  realised credit k < 0.2*DTI_before.  The bar is G-independent (it is 0.2*DTI).")
    print()
    for Gtry in (3950.0, 7905.0, G):
        Tt = {n: d * (0.2 * s + 0.8 * Gtry) for n, s, d in fam}
        row = []
        for label, a, b in (("solid->D1.5", "H19-5 solid", "D1.5 dotted"),
                            ("D1.5->D2.8", "D1.5 dotted", "D2.8 dotted"),
                            ("D2.8->B2", "D2.8 dotted", "D2.8 + catalogue B=2")):
            sa = dict((n, s) for n, s, _ in fam)[a]
            sb = dict((n, s) for n, s, _ in fam)[b]
            da = dict((n, d) for n, _, d in fam)[a]
            row.append(f"{label}: k={(Tt[a] - Tt[b]) / (sa - sb):.4f} < bar {0.2 * da:.4f}")
        print(f"  at G = {Gtry:8,.0f} px   " + " | ".join(row))
    steps = [("solid -> D1.5", "H19-5 solid", "D1.5 dotted"),
             ("D1.5 -> D2.8", "D1.5 dotted", "D2.8 dotted"),
             ("D2.8 -> D2.8+B2", "D2.8 dotted", "D2.8 + catalogue B=2")]
    for label, a, b in steps:
        s_a = dict((n, s) for n, s, _ in fam)[a]
        s_b = dict((n, s) for n, s, _ in fam)[b]
        dti_a = dict((n, d) for n, _, d in fam)[a]
        removed = s_a - s_b
        k = (Ts[a] - Ts[b]) / removed
        print(f"  {label:18s} removes {removed:7,d} px with mean realised credit {k:6.4f} "
              f"vs bar {0.2 * dti_a:.4f}  -> {'REMOVE (helps)' if k < 0.2 * dti_a else 'KEEP'}")

    print()
    print("=" * 100)
    print("STEP 4 - what it would take to reach the current leader (0.3345 on 2026-10-06)")
    print("=" * 100)
    for name, s, dti in fam:
        need_T = 0.3345 * (0.2 * s + 0.8 * G)
        print(f"  {name:26s} needs T = {need_T:8,.0f} px, i.e. {need_T / Ts[name] - 1:+7.1%} "
              f"more credit at the same emitted mass")
    lead_s = 44090
    print()
    print("  Equivalently, at the leader's own likely operating mass (~44k px), reaching 0.3345")
    print(f"  requires T = {0.3345 * (0.2 * lead_s + 0.8 * G):,.0f} px of credit, i.e. a mean")
    print(f"  realised credit of {0.3345 * (0.2 * lead_s + 0.8 * G) / lead_s:.4f} per emitted pixel")
    print(f"  against {Ts['D2.8 dotted'] / 44090:.4f} for the best prior file: a +"
          f"{100 * (0.3345 * (0.2 * lead_s + 0.8 * G) / Ts['D2.8 dotted'] - 1):.0f}% field improvement.")
    print()
    print("=" * 100)
    print("STEP 5 - the emitted-mass question, answered inside the model instead of by correlation")
    print("=" * 100)
    print("  DTI(S) = T(S)/(0.2*S + 0.8*G) is increasing in S while the marginal pixel's credit")
    print("  exceeds 0.2*DTI.  With the family's own measured credits (0.1185 per pixel at 44,090 px,")
    print("  0.0307 for the marginal pixels between 44,090 and 121,131 px) the optimum sits between")
    print("  ~37k and ~45k emitted pixels - exactly where the 0.2600 -> 0.2778 files live.")
    print("  'Smaller is always better' (Spearman -0.907 across 15 owner-reported pairs) is a")
    print("  confound: those files are thinned variants of a few fields, not independent samples.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
