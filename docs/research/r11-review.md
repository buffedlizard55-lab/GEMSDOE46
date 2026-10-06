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

* The preregistered proxy is weak and mis-calibrated (it inverts the known live order). The
  stratified instrument used in Pass 3 is the only one in this repository that reproduces that order
  — and its own ordering evidence is three files inside a 0.002-wide band, so "calibrated" is a low
  bar. R11's margin on it is ten times that band, which is why the claim is made at all; it is still
  a proxy.
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

## 5b. Pass 3 — re-scored on the instrument that reproduces the live order (added after the gate)

The gate in §4 ran on the **un-stratified** off-catalogue SGMC truth. While this experiment was being
written up, the parallel H47 session measured (`registry/h47.json -> ladder`) that this instrument
**inverts** the three known live orderings (0.2600 / 0.2708 / 0.2778), and that only the *stratified*
version — truth = SGMC fault pixels more than `d0` px from every catalogue pixel, catalogue masked —
reproduces all three (d0 = 3 px and d0 = 5 px both do; d0 = 0 does not). A gate pass on an instrument
that inverts the live board is not evidence, so the candidate was re-scored on the stratified
instrument before any claim was made about it (`scripts/audit_r11_on_stratified.py`,
`evidence/r11-stratified-audit.json`).

Truth 56,822 px at d0 = 5 px (62,122 px at d0 = 3 px), domain 5,106,385 px, 127 truth-bearing 16×16
blocks; the incumbent row reproduces the H47 session's published 0.088516 exactly, which is the
cross-check that this script and theirs are measuring the same thing.

| emission | DTI d0=3 | DTI d0=5 | T (d0=5) | dots within 300 m | credit/dot |
|---|---:|---:|---:|---:|---:|
| incumbent file as shipped (37,654 dots, live 0.2778) | 0.09539 | 0.08852 | 4,737.5 | 10.5 % | 0.0551 |
| **R11 shipped candidate (44,090 dots)** | **0.16616** | **0.16619** | **9,213.7** | **14.3 %** | **0.0769** |
| R11 same field, re-emitted at the matched mass 37,654 | 0.14329 | 0.13877 | 7,487.5 | 13.3 % | 0.0704 |
| uniform-random control, 37,654 dots | 0.06921 | 0.06835 | 3,653.1 | 6.9 % | 0.0363 |

Paired over the 127 truth-bearing blocks: shipped **+0.06476** (t = +6.77, p = 4.5e-10); the
matched-mass re-emission **+0.03837** (t = +4.31, p = 3.3e-5). The random control sits *below* the
incumbent, so the instrument is not merely rewarding mass.

Two honest qualifications. First, the R11 field's AUC over the incumbent's **own** dots is 0.507 —
chance. The advantage is not pruning the incumbent's dead mass (the H47 route, which failed); it is
the placement of new dots, and that is exactly what the H47 review concluded was required. Second,
this instrument's truth is a 1:50k–1:1M compilation roughly 4× denser than the inferred hidden set
and it is not the competition's label set. R11 is the first arm in this repository that beats the
live-scored incumbent file on an instrument with *any* demonstrated link to the live board, by a
margin far outside that instrument's measured noise; that is a reason to spend a slot, not a forecast
of a number.


## 6. Reproduce

```bash
bash scripts/restore_competition_data.sh
bash scripts/restore_r10_reference.sh
.venv/bin/python scripts/screen_r11.py
.venv/bin/python scripts/run_r11.py          # ~45 min on 2 cores
.venv/bin/python scripts/refine_r11_mass.py  # ~5 min
.venv/bin/python scripts/audit_r11_on_stratified.py  # Pass 3, ~2 min
.venv/bin/python scripts/build_r11_site.py
.venv/bin/python scripts/verify_r11_candidate.py
.venv/bin/python -m pytest
```

Hashes of every input, the exact emitted masks (as GeoTIFFs and as pixel-array sha256), the fold
table, the bootstrap seed and the Pass 1 / Pass 2 comparison are in `registry/r11.json` and
`docs/r11/receipt.json`.
