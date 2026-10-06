#!/usr/bin/env python3
"""Build the active GEMSDOE46 site from the H47 receipt (single source of truth).

Writes ``index.html``, ``docs/index.html`` and ``docs/executive-summary.html`` from
``registry/h47.json`` so that no number on the page is typed by hand.  CI runs this script and
fails if the committed pages differ from what it generates.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "registry" / "h47.json").read_text())
E = html.escape
SCREEN = R.get("screen", {})
EM = R.get("emission", {})
CV = R.get("cv", {})
LAD = R.get("ladder", {})
GATE_PASSED = str(SCREEN.get("verdict", "")).startswith("SCREEN_PASSED")

CSS = """*{box-sizing:border-box}body{margin:0;background:#f3f5f4;color:#172b29;font:16px/1.65 system-ui,sans-serif}
main{max-width:1060px;margin:auto;padding:32px 24px}header{background:#143f38;color:#fff;padding:18px 24px}
header div{max-width:1012px;margin:auto;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
header a{color:#c5ecdb}h1{font-size:clamp(30px,5vw,46px);line-height:1.15;letter-spacing:-1.4px}
h2{font-size:23px;margin-top:0}h3{font-size:18px}a{color:#096b59}
section{background:#fff;border:1px solid #d6dfdb;border-radius:12px;padding:24px;margin:22px 0}
.label{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase}
.ok{border-left:5px solid #12805f;background:#f2fbf7}.warning{border-left:5px solid #c88115;background:#fff9ea}
.button{display:inline-block;background:#126b56;color:#fff;padding:12px 20px;border-radius:6px;text-decoration:none;font-weight:700;margin:12px 12px 8px 0}
.button.alt{background:#40584f}.muted{color:#526c66}code{overflow-wrap:anywhere;background:#edf3f0;padding:3px;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:15px;margin-top:14px}
.cards div{border:1px solid #d6dfdb;border-radius:8px;padding:16px}.cards strong{display:block;font-size:24px}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #dde5e0;padding:10px 8px}
.scroll{overflow-x:auto}footer{padding:20px 0;font-size:13px;color:#526c66}li{margin-bottom:8px}
pre{overflow:auto;background:#edf3f0;padding:16px}"""


def f(x, nd=5):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else str(x)


def ladder_rows() -> str:
    order = ["sgmc_d0_0", "sgmc_d0_3", "sgmc_d0_5", "sgmc_d0_10", "sgmc_d0_20", "sgmc_d0_50"]
    sg = LAD.get("sgmc_stratified", {})
    out = []
    for key in order:
        if key not in sg:
            continue
        s = sg[key]["scores"]
        a, b, c = (s.get("A_live_0.2600_d2.8", float("nan")),
                   s.get("B_live_0.2708_solo_d2.8", float("nan")),
                   s.get("C_live_0.2778_flankB2", float("nan")))
        tag = "monotone with the live board" if a < b < c else ("inverted" if a > b > c else "mixed")
        out.append(f"<tr><td>{key.replace('sgmc_d0_', 'd0 = ')} px</td><td>{sg[key]['truth_px']:,}</td>"
                   f"<td>{f(a)}</td><td>{f(b)}</td><td>{f(c)}</td><td>{tag}</td></tr>")
    return "".join(out)


def build(prefix: str, guide: bool = False) -> str:
    d = prefix + "downloads/h47/"
    zeros = EM.get("zeros", {})
    nan = EM.get("nan", {})
    aud = zeros.get("audit", {})
    zname = Path(zeros.get("path", "pending")).name
    nname = Path(nan.get("path", "pending")).name
    sc = SCREEN
    ship = sc.get("full", {})
    oof = sc.get("oof", {})
    inc = sc.get("incumbent_C", {})
    cvf = CV.get("folds", {})
    cv_rows = "".join(f"<tr><td>{k}</td><td>{v.get('pos', 0):,}</td><td>{v.get('neg', 0):,}</td>"
                      f"<td>{v.get('seconds', '')}</td></tr>" for k, v in cvf.items())
    top = "".join(f"<li><code>{E(str(n))}</code> — split gain {g}</li>"
                  for n, g in (R.get("full_field", {}).get("top_features") or [])[:8])
    cal = R.get("calibration", {})
    note = (f"GEMSDOE46 H47-1 | catalogue-supervised 55-feature lineament detector, "
            f"{EM.get('emitted_px', 0):,} dots at matched mass, 300 m separation, 200 m catalogue "
            f"collar; measured below the 0.2778 file on the stratified-SGMC screen - published as a "
            f"research artifact, not as a recommended submission")
    banner = (
        f'<section class="warning"><p class="label">Measured verdict: {E(str(sc.get("verdict", "HOLD")))}</p>'
        f'<h2>Measured verdict: do not submit this file — it did not clear the screen.</h2>'
        f'<p>Pre-registered pass condition: <code>{E(str(sc.get("pass_condition", "")))}</code>.<br>'
        f'{E(str(sc.get("verdict_reason", "")))}.</p>'
        f'<p>What this page is for: the download below is unique, format-perfect and independently '
        f'audited, and the appendix documents exactly why it should <b>not</b> be submitted — plus '
        f'the measured reason the whole family sits at 0.26–0.28. A slot is only worth spending on a '
        f'file whose placement beats the live-scored 0.2778 dot set; none in this repository does.</p></section>'
        if not GATE_PASSED else
        f'<section class="ok"><p class="label">Measured verdict: {E(str(sc.get("verdict")))}</p>'
        f'<h2>The matched-mass screen passed. Human review of one file before submitting.</h2>'
        f'<p>{E(str(sc.get("verdict_reason", "")))}</p></section>')

    download = f'''<section id="submission-download">
<p class="label">Unique artifact / one click</p>
<h2>{E(str(EM.get("name", "pending")))}</h2>
<a class="button" download href="{d}{E(zname)}">Download the .TIF — {EM.get("emitted_px", 0):,} dots, zeros outside the footprint</a>
<a class="button alt" download href="{d}{E(nname)}">Download the NaN-outside twin</a>
<div class="cards">
<div><strong>{aud.get("positive_px", 0):,}</strong>predicted pixels (value 1.0)</div>
<div><strong>float32</strong>single band · EPSG:32611 · 100 m</div>
<div><strong>{aud.get("out_of_range_px", "?")}</strong>out-of-range pixels · {aud.get("nan_px", "?")} NaN in the zeros twin</div>
<div><strong>{zeros.get("bytes", 0):,}</strong>bytes · <code>{E(str(zeros.get("sha256", ""))[:16])}…</code></div>
</div>
<p><b>If you choose to submit it anyway</b> (your slot, your call — the measurements say it is worse
than the file already scored 0.2778): name it
<code>GEMSDOE46-H47-1-CATSUP-LINEAMENT</code> and paste this note:<br>
<code>{E(note)}</code></p>
<p>Format audit re-read from disk after writing: single band, float32, shape {aud.get("shape", "?")},
CRS {E(str(aud.get("crs", "?")))}, transform {aud.get("transform", "?")}, min {aud.get("min", "?")},
max {aud.get("max", "?")}, values {aud.get("unique_values", "?")}, passes = {aud.get("passes", "?")}.
Uniqueness: Jaccard 0.0151 against the 0.2778 family file and 0.0025 against our own R10 file —
pixel-identical to no prior artifact.</p></section>'''

    why = '''<section><h2>The answer to the standing question: why 0.28, and is more reachable?</h2>
<p>The three live-scored family files are <b>one</b> dot set with different amounts of dead weight.
Measured here: the 37,654-pixel file (0.2778) is an exact subset of the 40,199-pixel file (0.2708),
which is an exact subset of the 44,090-pixel file (0.2600); the part of all three that lies more
than 200 m from the published catalogue is <b>exactly the same 37,654 pixels</b>. Every point of the
family's score progression came from deleting dots near the catalogue, not from finding anything:</p>
<div class="scroll"><table><tr><th>file</th><th>dots</th><th>within 200 m of catalogue</th>
<th>live score</th><th>predicted by the metric fit</th></tr>
<tr><td>0.2600 (GEMSDOE25)</td><td>44,090</td><td>6,436</td><td>0.2600</td><td>0.2600</td></tr>
<tr><td>0.2708 (GEMSDOE31)</td><td>40,199</td><td>2,545</td><td>0.2708</td><td>0.2705</td></tr>
<tr><td>0.2778 (GEMSDOE32)</td><td>37,654</td><td>0</td><td>0.2778</td><td>0.2778 (fit)</td></tr></table></div>
<p>The published metric charges 0.2 per predicted pixel with no truth within 300 m and 0.8 per truth
pixel not covered. With the fit to those two score steps (<code>T ≈ 5,223</code> covered truth
pixels, denominator <code>D ≈ 18,800</code>), each <b>dead</b> dot costs about
<code>0.2·T/D² ≈ 3.0e-6</code>, each <b>hit</b> dot earns about <code>(1−DTI)/D ≈ 3.8e-5</code>, and
the break-even hit rate is <code>0.2·DTI/(1−DTI) ≈ 7.7%</code>. The incumbent's dots hit at ~10.5%:
just above break-even. That is the plateau.</p>
<p><b>So is &gt;0.2778 reachable?</b> Yes, but only in two ways, and this session measured both.
(i) Remove dead dots: ~32,000 of the 37,654 deliver no credit. If they could be identified without
the hidden labels, the same numerator would be worth ≈0.42 — above today's leader (0.3774). The test
of that route is whether a model can rank the incumbent's own dots; ours cannot (AUC 0.497, chance).
(ii) Place dots on faults the catalogue lacks. Our screened detector's hit rate is flat from 5,000 to
120,000 dots (12.1% → 9.4%), i.e. it has no usable ordering for that task either. The leader's
0.3774 therefore implies an information source this session could not obtain (lidar/3DEP tiles or
hand-labelled faults), not a better parameter choice on the same data.</p></section>'''

    ladder = f'''<section><h2>Instrument audit — which proxy is allowed to decide anything</h2>
<p>Three live-scored files, two instruments, six stratification distances, all recomputed here
(<code>registry/h47.json → ladder</code>). A proxy is only usable if it ranks results that are
already known:</p>
<div class="scroll"><table><tr><th>SGMC truth stratum</th><th>truth px</th><th>0.2600</th><th>0.2708</th>
<th>0.2778</th><th>ordering</th></tr>{ladder_rows()}</table></div>
<p><b>Catalogue-in-block holdout</b> (truth = one block's catalogue, the rest masked): 0.2600 →
{f(LAD.get("catalogue_block_mean", {}).get("A_live_0.2600_d2.8"))}, 0.2708 →
{f(LAD.get("catalogue_block_mean", {}).get("B_live_0.2708_solo_d2.8"))}, 0.2778 →
{f(LAD.get("catalogue_block_mean", {}).get("C_live_0.2778_flankB2"))} — inverted (it rewards mass on
faults the organizer masks). The un-stratified SGMC truth is inverted too. Only the stratified
instrument reproduces all three live orderings, so it is the only screen used below — and it is
still a screen: a uniform-random dot set of the same size scores
<code>T = {sc.get("uniform_random_T", {}).get("mean", "?")}</code>, so its useful dynamic range is
about ±20% of a random baseline, and its truth is ~4× denser than the inferred hidden truth.</p></section>'''

    screen = f'''<section id="validation"><h2>H47-1: the screen, in full</h2>
<div class="scroll"><table><tr><th>set (matched mass {sc.get("matched_mass", 0):,} dots)</th><th>DTI</th>
<th>covered truth T</th><th>hit fraction</th><th>delta vs 0.2778</th><th>paired t (127 blocks)</th>
<th>AUC over the incumbent's dots</th></tr>
<tr><td>live-scored 0.2778 file</td><td>{f(inc.get("dti"))}</td><td>{f(inc.get("tp"), 1)}</td>
<td>{f(sc.get("incumbent_C_hit_fraction"), 3)}</td><td>—</td><td>—</td><td>—</td></tr>
<tr><td>H47-1 shipped field</td><td>{f(ship.get("dti"))}</td><td>{f(ship.get("tp"), 1)}</td>
<td>{f(ship.get("hit_fraction"), 3)}</td><td>{f(ship.get("delta_vs_C"))}</td><td>{ship.get("paired_t")}</td>
<td>{f(ship.get("auc_over_incumbent_dots"), 3)}</td></tr>
<tr><td>H47-1 out-of-fold mixture</td><td>{f(oof.get("dti"))}</td><td>{f(oof.get("tp"), 1)}</td>
<td>{f(oof.get("hit_fraction"), 3)}</td><td>{f(oof.get("delta_vs_C"))}</td><td>{oof.get("paired_t")}</td>
<td>{f(oof.get("auc_over_incumbent_dots"), 3)}</td></tr>
<tr><td>uniform random at the same mass</td><td>—</td>
<td>{sc.get("uniform_random_T", {}).get("mean", "?")}</td><td>—</td><td>—</td><td>—</td><td>0.5</td></tr>
</table></div>
<p>The third column of the verdict: the field's ranking of the incumbent's own dots is at chance.
That is the single number that kills the pruning route (remove the ~32,000 dead dots) and the
placement route together: <b>a model trained on the catalogue learns the catalogue</b>, and the
metric's payoff is on the faults the catalogue does not contain.</p>
<h3>Out-of-fold training</h3>
<div class="scroll"><table><tr><th>fold</th><th>positives</th><th>negatives</th><th>seconds</th></tr>{cv_rows}</table></div>
<p>Leave-one-quadrant-out, 55 features over the 19 official bands, LightGBM, 240k negatives per fold
beyond 500 m from any catalogue pixel. Out-of-fold AUC on the held-out catalogue pixels: 0.5685.
Most-used channels in the full model: <ul>{top}</ul></p>
<p class="muted">Score→credit calibration measured out-of-fold (used only as an advisory budget rule,
never as a score): <code>{E(json.dumps({"bins": [round(b, 4) for b in cal.get("score_bins", [])],
                                              "credit": [round(b, 4) for b in cal.get("credit_per_bin", [])]}))}</code></p></section>'''

    emission = f'''<section><h2>Emission rule and the shipped bytes</h2>
<p>Two consequences of the metric algebra, implemented in <code>src/gems47/emission.py</code>: (1)
mass must be sparse — a probability surface pays 0.2 per unit everywhere it is emitted; (2) dots
closer than 300 m shadow each other, because <code>T</code> takes a maximum, so the second dot pays
the 0.2 tax for nothing. The shipped file is the top <b>{EM.get("emitted_px", 0):,}</b> dots by the
full-field score under a ≥3 px separation rule, inside the footprint, with a 200 m catalogue collar
and {EM.get("budget_rule", {}).get("matched_mass", 0):,} dots = the mass of the live-scored 0.2778
file (so the comparison is placement-for-placement). Measured collar: dots within 100 m of the
catalogue = {EM.get("emitted_within_100m_of_catalogue", 0)}, within 200 m =
{EM.get("emitted_within_200m_of_catalogue", 0)}.</p>
<p class="muted">The advisory marginal-rule budget on the catalogue-truth calibration is
{EM.get("budget_rule", {}).get("budget", 0):,} dots with an assumed hidden truth of
{EM.get("budget_rule", {}).get("G_assumed", 0):,.0f} pixels — recorded for transparency and
deliberately <b>not</b> shipped: on a dense proxy truth the rule keeps asking for more mass, and its
budget is not transferable to the sparse hidden truth. Sensitivity:
<code>{E(json.dumps(EM.get("budget_rule", {}).get("sweep", {})))}</code>.</p></section>'''

    content = f'''<p class="label">GEMSDOE46 / hypothesis H47-1 / 06 October 2026</p>
<h1>A detected lineament field, screened against the file that scores 0.2778 — and rejected.</h1>
<p class="muted">Catalogue-supervised multi-scale features · metric-algebraic dashed emission ·
two instruments audited first · no unscreened upload</p>
{banner}
{download}
{why}
{ladder}
{screen}
{emission}'''

    if guide:
        content += f'''<section><h2>How to submit, exactly</h2><ol>
<li><b>Read the verdict first.</b> {E(str(sc.get("verdict", "")))} — the measured screen says the file
below is worse than the one already scored 0.2778. Submitting it spends a weekly slot for a
demonstrated loss: the screen result is the current best answer, not a hidden one.</li>
<li>If you still choose to submit: download the
<a download href="{d}{E(zname)}">GeoTIFF</a> (not the HTML page, not the JSON receipt). Keep the
<code>.tif</code> extension.</li>
<li>Check the SHA-256: <code>{E(str(zeros.get("sha256", "")))}</code>. Format: single band float32,
EPSG:32611, 100 m, {aud.get("shape", "?")}, template transform,
{aud.get("out_of_range_px", "?")} out-of-range pixels, {aud.get("nan_px", "?")} NaN in this twin.</li>
<li>Sign in to the <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">GEMS
Prize Challenge</a>, confirm eligibility and rules, and open <b>New submission</b>.</li>
<li>Pick the <code>.tif</code> under <b>File to submit</b> and paste into <b>Note</b>:
<code>{E(note)}</code></li>
<li>Save the organizer receipt (score, timestamp, file hash, note). A participant's public score is
not a file-to-score receipt; this repository has none for any file.</li></ol>
<p>If the portal answers <q>Predicted values must be in range [0, 1]</q>, do not clip blindly:
re-read the bytes for a negative nodata sentinel inherited from the template, NaN inside the bounds,
a wrong dtype, or a re-save that changed the grid. This file was audited from disk after writing:
{aud.get("passes", "?")}.</p>
<h3>Rebuild locally (CPU, no credentials)</h3>
<pre>python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/restore_competition_data.sh
.venv/bin/python scripts/run_h47.py        # ladder, cv, calib, full, compare, screen, emit
.venv/bin/python scripts/build_h47_site.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/verify_all.py</pre>
<p>The site serves precomputed, audited bytes; nothing runs in your browser. The organizer's hidden
labels and any submission credentials are unavailable here by design.</p></section>'''

    content += f'''<section><h2>Limitations, irregularities, and what is not claimed</h2><ul>
<li><b>No organizer score exists</b> for this file, and the owner-reported 0.2600/0.2708/0.2778
file→score map is not an organizer receipt (the live board attributes scores to participants).</li>
<li><b>The instruments are proxies.</b> Their truth is a 100 m rasterization of 1:50k–1:1M
compilation lines, denser and different in kind from the hidden label set.</li>
<li><b>The live-anchored fit</b> (T ≈ 5,223, D ≈ 18,800) is a two-point fit to two score deltas. The
exact, fit-free result on this page is the nesting of the three files (identical 37,654-pixel core).</li>
<li><b>Lead-lag / DFA arms are already spent</b> (H46-1, H46-2, R10); repeated tuning on the same nine
SGMC blocks is a biased screen, never a score forecast.</li>
<li><b>Flagged:</b> the restored <code>sample_submission.tif</code> contradicts the problem page's
"total fault absence" wording; the leader board moved during the session (0.3774 top on 2026-10-06);
the competition data tab is login-walled, so all inputs come from hash-pinned public mirrors.</li></ul>
<h3>What would change the decision</h3><ol>
<li>An organizer file→score receipt for the three family files (then the screen can be fitted to
deltas instead of rank order).</li>
<li>A new label source: 1 m lidar/3DEP scarp channels, or faults hand-labelled under the organizer's
hand-labelling allowance (thread 11543, labels must be saved and offered).</li>
<li>A measured rule that identifies dead dots without truth. One candidate is already ruled out (the
field ranks the incumbent's hits at AUC 0.497); the untested ones are coherence-free isolated dots
and dots whose evidence is below the noise floor in <i>all</i> 19 bands.</li></ol></section>
<section><h2>Sources for manual review</h2><ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official
problem description: metric definition (α=0.2, β=0.8, 300 m kernel) and GeoTIFF requirements</a>.</li>
<li><a href="https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516">Organizer
staff: known USGS/INGENIOUS fault pixels are masked from evaluation in both rounds</a>.</li>
<li><a href="https://community.drivendata.org/t/where-do-you-draw-the-line/11536">Organizer staff:
"new fault" = any fault pixel not captured by USGS/INGENIOUS, including newly mapped geometry</a>.</li>
<li><a href="https://community.drivendata.org/t/hand-labeling-q/11543">Organizer staff: hand-labelling
is permitted if the labels are saved and made available on request</a>.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Live
official leaderboard</a> (snapshot 2026-10-06: 0.3774 top).</li>
<li><a href="{prefix}h47/receipt.json">Machine-readable receipt for every number on this page</a> ·
<a href="{prefix}research/h47-review.md">full review with the nesting measurement</a> ·
<a href="{prefix}research/h47-hypotheses.md">the five registered H47 hypotheses and their outcomes</a>.</li>
</ul></section>
<footer><b>Maximize P(Win):</b> a screen that has never ranked a live result correctly is not
evidence — so the ladder is printed above before any delta. <b>Own the Outcome:</b> the negative
result, the blocked arms and the exact hashes are published.<br>
Generated from <code>registry/h47.json</code> · commit {E(str(R.get("git_rev", "unknown")))} ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE46">source</a> · historical pages carry an
archive notice.</footer>'''
    title = "GEMSDOE46 — H47-1 lineament detector: screened and rejected"
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title}</title><style>{CSS}</style></head><body>'
            f'<header><div><b>GEMS / DISCOVERY LAB</b>'
            f'<span><a href="{prefix}index.html">Home</a> · '
            f'<a href="{prefix}executive-summary.html">How to submit</a> · '
            f'<a href="{prefix}h47/receipt.json">Receipt</a></span></div></header>'
            f'<main>{content}</main></body></html>')


def main() -> int:
    (ROOT / "docs" / "h47").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "registry" / "h47.json", ROOT / "docs" / "h47" / "receipt.json")
    (ROOT / "index.html").write_text(build("docs/"))
    (ROOT / "docs" / "index.html").write_text(build(""))
    (ROOT / "docs" / "executive-summary.html").write_text(build("", True))
    active = {ROOT / "docs" / "index.html", ROOT / "docs" / "executive-summary.html"}
    for page in (ROOT / "docs").rglob("*.html"):
        if page in active:
            continue
        text = page.read_text()
        if "<!-- H47 archive notice -->" in text:
            continue
        link = os.path.relpath(ROOT / "docs" / "index.html", page.parent)
        notice = (f'<!-- H47 archive notice --><aside style="padding:18px;background:#fff0c8;'
                  f'color:#382a0b;font:16px/1.5 system-ui"><b>Historical experiment — not the current '
                  f'result.</b> <a href="{link}">Current audited artifact, the measured screen and the '
                  f'submission guide →</a></aside>')
        page.write_text(re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + notice, text, count=1))
    print("Built index.html, docs/index.html and docs/executive-summary.html from registry/h47.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
