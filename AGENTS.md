# Session protocol for agents working in this repository

1. **Read [`PROMPT.md`](PROMPT.md) first.** It is the objective: a unique TIF submission for the DOE
   GEMS Prize Challenge (DrivenData #306) that beats the leaderboard, plus the hard constraints
   (no hallucinations, line-by-line verification, flag irregularities, free official sources only,
   site with an obvious download and an executive summary explaining exactly how to submit).
2. **Then read state, not history:** `README.md` (current numbers), `registry/hypotheses.json` (what is
   already tried and what was falsified), `registry/irregularities.json` (what is contested),
   `registry/sources.json` (what each official source underwrites).
3. **Never repeat a falsified arm as if it were new.** In particular: the spatially blocked catalogue
   holdout is a rejected instrument (IR-46-04); measured geothermometry as an *addition* arm was
   falsified by the group (H46-5 lists the untested pruning direction); DFA to an absolute 0.5
   threshold is wrong for this dataset (IR-46-05).
4. **Rules for new work**
   - Proposal first: 3–5 hypotheses with layers, physical signature, why off-catalogue, how it differs
     from everything already in the repository, expected DTI, implementation cost (PROMPT.md §5).
   - Validate on the off-catalogue proxy **at matched emitted mass and identical exclusion rules**
     before touching the scored slot.
   - If a hypothesis needs external data, name the exact free official source and check it is reachable
     from *this* environment before calling the idea viable (currently reachable: github.com, pypi.org).
   - Keep `registry/` receipts authoritative: numbers in the site come from `scripts/build_site.py`
     reading `registry/*.json`, never typed by hand.
5. **Verification gates before finishing a session**
   ```
   python3 -m pytest tests -q          # metric vs published example + brute force; DFA calibration
   python3 scripts/verify_all.py       # adds pinned hashes + a full format audit of the shipped TIFs
   python3 scripts/build_site.py       # site must regenerate without error and every local link resolve
   ```
6. **Reporting style** — state what was measured, what was assumed, and what is owner-reported.
   Label negative results as negative results; they are the most useful output of this project.
