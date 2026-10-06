# H33 score attribution and public-board comparison

**Evidence date:** 2026-10-06 UTC. This is a point-in-time analysis; the public board is not mirrored or automatically refreshed here.
**Short answer:** the statement “H33/H33-2-B2 scored 0.2778” is **not verified**. The official board did show a 0.2778 entry, but that row belongs to `extradr19`; the inspected row does not identify H33 or link an artifact. The inspected GEMSDOE32 owner-maintained H33 page calls the H33 artifact **UNSCORED** and describes 0.2747 as a model projection, not an organizer score. There is no evidence that connects the two records.

## What the public leaderboard showed on 2026-10-06

- The live official top entry was **0.3345** (`alexoktaba`).
- The cited **0.3195** entry (`DARD`) was fifth in that review, not first.
- The public **0.2778** entry was `extradr19` (rank 13 in that point-in-time view).
- The competition leaderboard is the authoritative place to check current rank and scores: [official live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/).

This repository records only those facts needed to answer the user's attribution question. It does **not** mirror the whole board, poll it, or promise a current feed. DrivenData's [Terms of Use](https://www.drivendata.org/termsofuse/) prohibit automated access for monitoring/copying and manual monitoring/copying absent prior written consent. A dated note plus a direct link is not an auto-refresh mechanism.

## What is and is not established about H33/H33-2-B2

| Statement | Evidence status | Proper interpretation |
|---|---|---|
| “H33/H33-2-B2 received organizer score 0.2778.” | **Unverified / not attributable.** | A matching numerical row exists for a different displayed participant (`extradr19`). No public artifact link or evidence establishes identity with H33. Do not report 0.2778 as an H33 result without a DrivenData submission receipt or other primary evidence. |
| H33-2-B2 is “UNSCORED.” | **Reported by the inspected owner-maintained GEMSDOE32 page.** | This is a nonofficial owner statement, but it directly conflicts with the score attribution. Treat it as a report, not organizer evidence. |
| H33 has a `0.2747` value. | **Owner-reported model projection, not a public/organizer score.** | A projected/local result cannot be compared as if it were a leaderboard result. Its split, input, and code have not been rerun in this checkout. |
| 0.2778 was the competition high score. | **False as of 2026-10-06.** | The live public leader observed was 0.3345; 0.3195 was fifth. |

If 0.2778 were eventually confirmed as an H33 submission, it would be **0.0417 below 0.3195** and **0.0567 below the observed 0.3345 leader**. Those differences are arithmetic comparisons only; because H33's attribution is unverified, they are not a verified H33 performance gap.

## Why a sparse-map edit could help in principle — not a causal explanation of H33

The official competition description defines a distance-weighted Tversky score. In simplified notation consistent with the published description, for each labeled fault pixel `g` let

`credit(g) = max over predicted pixels x of [p(x) * max(0, 1 - distance(x,g)/300 m)]`.

Then the true-positive credit sums `credit(g)`, the false-negative term sums `1 - credit(g)`, and predicted mass receives a distance-weighted false-positive penalty. The score uses `alpha = 0.2` and `beta = 0.8`:

`DTI = TP / (TP + 0.2*FP + 0.8*FN)`.

Read the [official metric/formats page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) for the authoritative definitions. The kernel gives partial credit only inside 300 m; predictions farther away get no local true-positive credit and incur false-positive cost. The larger beta coefficient makes missed labeled-fault credit more costly than false-positive mass at the coefficient level. For each ground-truth pixel, prediction credit uses a **maximum**, so redundant probability mass near already-covered labels need not add much true-positive credit while it can still add false-positive mass elsewhere.

Therefore, **if** a candidate was overly dense, a pruning operation could improve DTI if it removed low-value probability mass that was far from the held-out labeled faults. But a two-pixel (200 m on a 100 m grid) exclusion around an existing fault catalogue is not automatically good: it can also erase predictions that fall within 300 m of an unlabeled evaluation fault. The catalogue is not the hidden answer, and “exclude known faults” is not a scoring reward by itself.

This offers a plausible metric-level mechanism for sparse/recall-oriented tradeoffs. It does **not** show that H33 used that mechanism, that H33 scored 0.2778, or why `extradr19` scored 0.2778. The leaderboard row does not provide enough evidence for causal attribution.

## Correct benchmark interpretation

- **Public board score:** organizer feedback for the submitted artifact; identities and current rank must be read from the official board.
- **Local spatial holdout score:** a reproducible development comparison on a fixed spatial split of the available labels. It is not the private leaderboard and not evidence of undiscovered-fault detection by itself.
- **Owner projection:** a stated model projection, only as credible as its inputs/split/method; it is not an organizer score.

The current checkout has no training data, candidate rasters, split, scorecard, or current holdout-best artifact. Consequently there is no locally measured baseline against which to validate H46-1. **No model and no submission TIF have been produced.**

## Source trail

- [Official competition metric and submission-format page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [Official live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)
- [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/)
- [GEMSDOE32 owner-maintained hypotheses page](https://buffedlizard55-lab.github.io/GEMSDOE32/docs/hypotheses.html) — nonofficial source, used only to identify its stated H33 status/projection.
