# R11 review — what was run, what was wrong with it, and what is actually claimed

**Scope.** Experiment R11 asked for a *unique, format-legal* GeoTIFF that is at least as good as the
best file this family knows (the 0.2778 scoring 37,654-dot file whose provenance is owner-reported),
using two evidence families that the official 19-band stack does not contain, and emission that
follows the published metric rather than a spacing heuristic. No competition slot was spent and no
portal credentials were used.

**Verdict.** `PROXY_GATE_PASSED_NOT_SUBMITTED`. At a matched emitted mass of 44,090 pixels the
candidate beats both the incumbent file as shipped and a same-mass re-emission of the incumbent's
field on the preregistered off-catalogue proxy, with a seed-fixed block bootstrap interval that
excludes zero in both comparisons. This is permission to consider one weekly slot, not a score.

---

## 1. What was built

| piece | file | what it does |
|---|---|---|
| evidence families | `src/gems46/evidence.py` | rank-normalised, coherence-weighted lidar-scarp, topographic, radiometric-contrast and potential-field lineament scores |
| metric-optimal emitter | `src/gems46/optemit.py` | exact lazy-greedy expected-credit coverage with a break-even stop |
| Pass 1 | `scripts/run_r11.py` | builds the fields, the DFA artefact, proxy credit curves, first gate, receipt |
| Pass 2 | `scripts/refine_r11_mass.py` | corrects the two defects below and re-gates at a matched mass |
| screen | `scripts/screen_r11.py` | one-channel-at-a-time AUC screen on the off-catalogue proxy |
| format audit | `scripts/verify_r11_candidate.py` | every clause of the submission contract, re-read from the bytes |

The only information that enters the emitter is the published metric: `DTI = T/(0.2N + 0.8G)` for a
sparse binary prediction, so a dot is worth emitting while its marginal kernel credit exceeds
`0.2·DTI`. Nothing about the hidden set is used.

## 2. Measurements that matter

Emitted mass 44,090 px, 4×4 blocks with 3-pixel interior guards, 11 evaluable blocks (5 have no
proxy truth or no emittable domain), SGMC off-catalogue proxy:

| emission rule / field | mean block proxy DTI |
|---|---|
| **R11-fused (shipped)** | **0.17061** |
| incumbent field, re-emitted at the same mass | 0.10224 |
| incumbent file as shipped (37,654 px) | 0.09130 |
| R11 DFA regime-break field | 0.08973 |

Paired, seeded block bootstrap (10,000 draws, seed 4611): **+0.07931** vs the incumbent as shipped,
95 % interval [+0.02719, +0.12694], 8/11 blocks improved; **+0.06837** vs the same-mass re-emission,
[+0.01618, +0.11658], 8/11 blocks. Both intervals exclude zero.

The DFA arm does **not** win: 0.08973, i.e. indistinguishable from the incumbent file on this proxy.
That is the honest result of the hypothesis the standing brief asked to be tested, and it is
published next to the winning arm rather than hidden behind it.

## 3. The two defects Pass 2 found in its own Pass 1, and the fix

1. **A degenerate mass rule.** The preregistered transfer multiplied a flat proxy credit *ratio* by
   the incumbent's live-anchored credit, so its predicted DTI decreased with emitted mass and the
   "max-min" choice collapsed to the smallest grid point — 10,000 dots. The projection printed at
   that point (0.687) was obviously impossible; that absurdity is what exposed the bug.
2. **An unmatched gate.** Pass 1's gate took the best comparator, which included the incumbent file
   at *its own* mass, while the preregistered clause demanded a matched emitted mass.

The fix is a measured transfer: candidate live credit = candidate **proxy** credit at the same mass,
scaled by a factor fitted once at the incumbent file's own operating point (5,518.4 proxy credit,
proxy DTI 0.0946). The mass is then re-selected with the preregistered max-min rule
(G = 7,905 → 0.4742; G = 14,089 → 0.4851 at 44,090 px) and the gate re-run at that matched mass.
Pass 1's numbers are preserved unedited in `registry/r11.json` under `pass1_as_executed`, including
its `HOLD_DO_NOT_SUBMIT` status, so the correction is auditable rather than invisible.

**What this correction does and does not buy.** It does buy a legitimate comparison at matched mass.
It does not make the projection credible: the proxy truth (state-geology fault traces) is easier than
the hidden set, so the absolute projected DTI is optimistic by construction. Only the *relative*
comparison is offered as evidence.

## 4. Novelty, checked against the preregistered ceiling

Preregistration: a candidate whose maximum |correlation| with prior shipped files exceeds 0.2 may not
be called a new hypothesis. Measured on the common domain, smoothed:

* primary: 0.3161 vs the incumbent file, **0.3779** vs H46-2 — **above the ceiling**, therefore the
  primary is explicitly *not* claimed as new; it is a new fusion and a new emitter over evidence
  families that earlier topographic arms also touched;
* DFA artefact: maximum 0.1406 — below the ceiling, so the localised regime-break statistic is the
  part of this experiment that is claimed as new.

## 5. Limitations, stated plainly

* The proxy is weak: the group measured Spearman ≈ +0.31 between this instrument family and 11 live
  leaderboard scores. A pass here is permission to consider a slot.
* The mass transfer is a model fitted to one owner-reported score (0.2778) and one inference
  (G ∈ {7,905, 14,089} px). No organizer receipt exists for any file in this repository.
* Lidar covers 75 % of the footprint; the rest rests on coarser evidence.
* The channel screen ran on the same proxy population used for the gate, so both share whatever bias
  that population has. The families were fixed by physical reasoning *before* the gate, and the
  weights were preregistered rather than fitted, but this is not a guarantee.
* Band 6 of the official stack is a radiometric total count, not the magnetic curvature the data
  dictionary claims (IR-46-13); any prior reading of that band as a tilt/curvature transform in this
  repository is wrong.
* Correlation is a redundancy diagnostic on this domain, not proof of independence.

## 6. Reproduce

```bash
bash scripts/restore_competition_data.sh
bash scripts/restore_r10_reference.sh
.venv/bin/python scripts/screen_r11.py
.venv/bin/python scripts/run_r11.py          # ~45 min on 2 cores
.venv/bin/python scripts/refine_r11_mass.py  # ~5 min
.venv/bin/python scripts/build_r11_site.py
.venv/bin/python scripts/verify_r11_candidate.py
.venv/bin/python -m pytest
```

Hashes of every input, the exact emitted masks (as GeoTIFFs and as pixel-array sha256), the fold
table, the bootstrap seed and the Pass 1 / Pass 2 comparison are in `registry/r11.json` and
`docs/r11/receipt.json`.
