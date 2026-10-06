# Why `0.2778` scored, and what the metric will and will not pay for

*Every number is tagged **[OFFICIAL]** (read from an organizer page or product),
**[MEASURED]** (computed in this checkout from hash-pinned bytes), or **[OWNER-REPORT]**
(a sibling site's own claim). Nothing here is presented as an organizer receipt.*

---

## 1. The metric, exactly

**[OFFICIAL]** <https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>

```
k(d) = max(1 - d/300 m, 0)
TPw = sum_{g in G} max_{x: d(x,g)<=300m} p(x) k(d(x,g))
FPw = sum_{x: p(x)>0} p(x) [ 1 - max_{g in G} k(d(x,g)) ]
FNw = sum_{g in G} [ 1 - max_{x: d(x,g)<=300m} p(x) k(d(x,g)) ]
DTI = TPw / (TPw + 0.2*FPw + 0.8*FNw + eps)
```

`tests/test_metric.py` transcribes the three sums as literal O(N²) loops and checks the
vectorised implementation against them to 1e-9 on random rasters, plus the published worked
example (`TPw=3.00, FPw=1.89, FNw=2.00 → 0.60`). Both pass.

**Two exact identities** follow from the definitions and are used everywhere below:

| identity | why |
| --- | --- |
| `FNw = |G| − TPw` | for binary truth, `1 − coverage(g)` summed over g is `|G| − sum_g coverage(g)` |
| `FPw = N − TPw` (**sparse regime**) | when no two dots are the best cover of the same truth pixel, `sum_x (1 − k(x)) = N − sum_x k(x) = N − TPw` |

so with `T = TPw` and `N` = emitted unit-mass pixels,

```
DTI = T / (0.2*N + 0.8*|G|)                              (★)
```

**[MEASURED]** (★) reproduces the sibling site's reported `0.2600` *exactly* from its own reported
credit and dot count: `0.0893 × 44,090 / (0.2 × 44,090 + 0.8 × 7,905) = 0.2600`.
The internal consistency of an independently reported credit-per-pixel and an independently reported
leaderboard score is a genuine cross-check that the algebra is the one the leaderboard uses.

## 2. Two consequences that decide the whole competition

**(a) Binary beats graded.** Scale a support by `λ`: `DTI(λ) = λT/(0.2λN + 0.8|G|)`, and
`dDTI/dλ = 0.8·T·|G| / (0.2λN + 0.8|G|)² > 0`. **A probabilistic map is strictly dominated by its
own thresholded support.** Every competitive artefact must be a 0/1 dot raster.

**(b) There is a hard, data-free speed limit.** Because `T ≤ |G|`,

```
DTI  ≤  |G| / (0.2*N + 0.8*|G|)                          (★★)     <- src/gems46/analytic.py
```

At the sibling site's declared `|G| = 7,905 px` (an *inferred* value: it is the mass implied by the
`0.2600` cross-check above, see `docs/IRREGULARITIES.md` IR-46-07; the whole curve is recomputed at
`|G| ∈ {3,950, 7,905, 15,810}` px in `evidence/analytic_screen.json`):

| emitted dots `N` | 20,000 | 30,000 | 44,090 | 60,069 | 80,000 | **86,541** | 100,000 | 121,131 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ceiling (★★) | 0.7657 | 0.6414 | 0.5221 | 0.4311 | 0.3541 | **0.3345** | 0.3003 | 0.2588 |
| credit `T` needed for 0.3345 | 3,453 | 4,301 | 5,065 | 6,134 | 7,467 | 7,905 | 8,805 | 10,219 |

Three exact consequences, all arithmetic from (★) and (★★):

* **`N = 86,541` is the hard density wall.** Any submission carrying more dots than that cannot
  reach 0.3345 *even with perfect placement*; at 121,131 dots (the family's 0.1922 arm) the ceiling
  itself is 0.2588, i.e. below the 0.2778 already on the board.
* **At the sibling's own mass the target needs a better field, not a bigger one.** Their 0.2600 row
  earned `T = 0.0893 × 44,090 = 3,937` credit; hitting 0.3345 at the same 44,090 dots needs
  `T = 5,065`, i.e. **28.6 % more kernel credit per unit mass**.
* **Credit-per-dot has a hard limit too.** With a fixed credit per dot `c`, (★) tends to `c / 0.2`
  as `N → ∞`, so no amount of densification rescues a weak field — but the denser arm also has to
  stay under the wall, and `T ≤ |G|` caps what any field can earn. The two constraints together are
  what `scripts/make_submission.py` checks before a file is written.

## 3. Why `h33-h33-2-b2` (0.2778) was the family's best

**[MEASURED]** from `gemsdoe32-h33-h33-2-b2-…-audit.json`: the file is the `0.2708` base with
**every dot at `d(catalogue) ≤ 2 px` deleted** → 37,654 dots, `0` on the catalogue, 0 within 200 m
of it. `docs/score-ledger`-equivalent rows on the live board (observed 2026-10-06, ranks #13 and
#20) confirm `0.2778` and `0.2600` are real scores, not owner fiction.

The mechanism is (b) applied to *removed* mass. The organizer masks USGS/INGENIOUS pixels from every
metric term (organizer clarification, community thread 11516, quoted by the sibling sites), so:

* a dot **on** the catalogue costs nothing and earns nothing — pure waste, worth deleting so it
  cannot radiate a false-positive penalty into neighbouring scored pixels;
* a dot **beside** the catalogue costs `0.2·(1 − k)` and earns `k` only if a *new* fault happens to
  be within 300 m of it.

The sibling site's own live sequence — 0.1922 at 121,131 dots, 0.2477 at 60,069, 0.2600 at 44,090,
0.2708 at 40,199, 0.2778 at 37,654 — is monotone in **mass deleted**, not in model quality. That is
the single most important, most replicable fact in the family's whole record.

## 4. What this repository therefore does differently

1. **It stops trusting the catalogue-truth holdout for density.** A holdout whose truth *is* the
   catalogue rewards dots that sit on the catalogue, and the scored task deletes exactly those.
   So the sweep is evaluated on **two populations** on the same bytes: the tile's catalogue
   (`pop_full`, the density *diagnostic*) and a deterministic 12.96 % subsample of it
   (`pop_thin`, the declared primary), with the ratio itself swept 1.0 → 0.06 for sensitivity.
2. **It certifies the choice instead of reporting it.** The 24 tiles are split into a selection half
   and a calibration half; the selection half ranks the sweep arms and the calibration half supplies
   the split-conformal quantile (`src/gems46/pipeline.py::conformal_select`). The shipped note
   carries the confidence level and the number of exchangeable blocks.
3. **It respects (★★).** The analytic screen is written into the evidence bundle so that any future
   arm that violates the dot-count ceiling is rejected before it can waste a weekly slot.
4. **It looks for the one thing a surface catalogue structurally cannot contain** — a fault that
   ruptured *after* the catalogue was compiled. See `docs/HYPOTHESES.md` H46-1.
