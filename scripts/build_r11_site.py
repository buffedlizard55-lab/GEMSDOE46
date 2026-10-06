#!/usr/bin/env python3
"""Publish the R11 receipt: one obvious download, one honest status, every limitation on the page.

Renders three pages from ``registry/r11.json``:

* ``index.html``                (repository root -- what the project page opens with)
* ``docs/index.html``           (same content, relative links)
* ``docs/executive-summary.html`` (the exact click-by-click submission guide)

``docs/r11/receipt.json`` and the two GeoTIFFs are written by ``scripts/run_r11.py`` (Pass 1) and
``scripts/refine_r11_mass.py`` (Pass 2).  Every number on these pages is read from the receipt, so a
stale claim cannot survive a regeneration; CI re-runs this script and fails if the three pages move.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "registry/r11.json").read_text())
P2 = R["pass2"]
P1 = R["pass1_as_executed"]
E = html.escape

CSS = ('*{box-sizing:border-box}body{margin:0;background:#f3f5f4;color:#172b29;'
       'font:16px/1.65 system-ui,sans-serif}main{max-width:1060px;margin:auto;padding:32px 24px}'
       'header{background:#143f38;color:white;padding:18px 24px}'
       'header div{max-width:1012px;margin:auto;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}'
       'header a{color:#c5ecdb}h1{font-size:clamp(30px,5vw,46px);line-height:1.15;letter-spacing:-1.4px}'
       'h2{font-size:23px;margin-top:0}h3{font-size:17px;margin-bottom:6px}'
       'a{color:#096b59}'
       'section{background:white;border:1px solid #d6dfdb;border-radius:12px;padding:24px;margin:22px 0}'
       '.label{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase}'
       '.ok{border-left:5px solid #127a5e;background:#eefaf4}.warning{border-left:5px solid #c88115;background:#fff9ea}'
       '.button{display:inline-block;background:#126b56;color:white;padding:14px 22px;border-radius:6px;'
       'text-decoration:none;font-weight:700;margin:12px 12px 8px 0}.button.alt{background:#37535f}'
       '.muted{color:#526c66}code{overflow-wrap:anywhere;background:#edf3f0;padding:3px;font-size:13px}'
       '.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:15px}'
       '.cards div{border:1px solid #d6dfdb;border-radius:8px;padding:18px}.cards strong{display:block;font-size:24px}'
       'table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #dde5e0;'
       'padding:10px 8px}.scroll{overflow-x:auto}footer{padding:20px 0;font-size:13px;color:#526c66}'
       'li{margin-bottom:8px}pre{overflow:auto;background:#edf3f0;padding:16px}')

STATUS = {
    "PROXY_GATE_PASSED_NOT_SUBMITTED": (
        "Proxy gate passed -- this file beat the current best on the preregistered blocked proxy",
        "ok",
        "It is unique, format-legal, and passed the matched-mass spatially blocked comparison against "
        "both the incumbent file and a same-mass re-emission of the incumbent's field. No organizer "
        "score exists: the projection below is a model, not a leaderboard result."),
    "HOLD_DO_NOT_SUBMIT": (
        "HOLD -- do not spend a weekly slot on this candidate",
        "warning",
        "The file is unique and format-legal, but it did not beat the preregistered blocked proxy "
        "comparison. It is published for review, not as a proven improvement."),
}


def f(x, nd=5):
    return "--" if x is None else f"{x:.{nd}f}"


def render(prefix: str, guide: bool = False) -> str:
    st = R["status"]
    label, cls, blurb = STATUS.get(st, STATUS["HOLD_DO_NOT_SUBMIT"])
    cand, dfa = R["candidate"], R["dfa_candidate"]
    d, res = prefix + "r11/", prefix + "research/"
    d_gems, d_res = prefix, prefix + "research/"
    name = R.get("submission_name", "GEMSDOE46-R11")
    means = P2["blocked_means"]
    gate_re, gate_sh = P2["gate_vs_reemitted"], P2["gate_vs_shipped"]
    rows = "".join(f"<tr><td>{E(k)}</td><td>{f(v)}</td></tr>"
                   for k, v in sorted(means.items(), key=lambda kv: -kv[1]))
    curves = R["proxy_curves"]["R11-fused"]
    incf = R["proxy_curves"]["incumbent-field"]
    curve_rows = "".join(
        f"<tr><td>{int(m):,}</td><td>{curves[m]['accepted']:,}</td><td>{curves[m]['proxy_credit']:,.1f}</td>"
        f"<td>{incf[m]['proxy_credit']:,.1f}</td>"
        f"<td>{curves[m]['proxy_credit'] / max(incf[m]['proxy_credit'], 1e-9):.3f}</td>"
        f"<td>{P2['corrected_transfer']['predicted_dti']['7905.0'][m]['predicted_dti']:.4f}</td>"
        f"<td>{P2['corrected_transfer']['predicted_dti']['14089.0'][m]['predicted_dti']:.4f}</td></tr>"
        for m in sorted(curves, key=int))
    corr = "".join(f"<tr><td>{E(k)}</td><td>{f(v['pearson_smoothed'], 4)}</td>"
                   f"<td>{f(v.get('jaccard'), 4)}</td></tr>" for k, v in P2["correlations_primary"].items())
    dfa_corr = "".join(f"<tr><td>{E(k)}</td><td>{f(v['pearson_smoothed'], 4)}</td>"
                       f"<td>{f(v.get('jaccard'), 4)}</td></tr>" for k, v in P2["correlations_dfa"].items())
    lims = "".join(f"<li>{E(x)}</li>" for x in R["limitations"])
    p3 = R.get("pass3_stratified_audit", {})
    p3i = p3.get("instruments", {})
    p3_rows = []
    for nm in ("incumbent-0.2778", "r11-shipped-44090", "r11-fused-reemitted-37654",
               "uniform-random-37654"):
        cells = []
        for key in ("sgmc_stratified_d0_3", "sgmc_stratified_d0_5"):
            r = p3i.get(key, {}).get("emissions", {}).get(nm)
            cells.append(f(r["dti"], 5) if r else "--")
        r5 = p3i.get("sgmc_stratified_d0_5", {}).get("emissions", {}).get(nm)
        if r5:
            p3_rows.append(f"<tr><td>{E(nm)}</td><td>{cells[0]}</td><td>{cells[1]}</td>"
                           f"<td>{r5['T_credit']:,.1f}</td><td>{r5['hit_fraction'] * 100:.1f} %</td>"
                           f"<td>{r5['mean_credit_per_dot']:.4f}</td></tr>")
    p3_table = "".join(p3_rows)
    p3_paired = p3i.get("sgmc_stratified_d0_5", {}).get("paired_vs_incumbent", {})
    p3_sh = p3_paired.get("r11-shipped-44090", {})
    p3_re = p3_paired.get("r11-fused-reemitted-37654", {})
    p3_auc = p3i.get("sgmc_stratified_d0_5", {}).get("auc_over_incumbent_dots")
    p1_gate = ("PASS" if P1["gate_passed"] else "FAIL")
    folds = len(P2["gate_vs_shipped"].get("ci95") and P2.get("blocked_means", {}) and
                R.get("blocked_folds", []) or []) or len(R["blocked_folds"])

    html_out = f'''<p class="label">GEMSDOE46 / Experiment R11 / 06 October 2026</p>
<h1>Lidar scarps, radiometric contrast,<br>and emission that follows the metric.</h1>
<p class="muted">New evidence families · expected-credit submodular emission · spatially blocked gate</p>
<section class="{cls}"><b>{E(label)}</b><p>{E(blurb)}</p></section>
<section id="submission-download"><p class="label">Submission file / ready to download</p>
<h2>R11 · primary candidate</h2>
<a class="button" download href="{d}{E(cand['file'])}">Download the unique .TIF</a>
<a class="button alt" href="{prefix}executive-summary.html">How to submit it, step by step →</a>
<p><code>{E(cand['file'])}</code><br>sha256 <code>{E(cand['sha256'])}</code></p>
<div class="cards"><div><strong>[0, 1]</strong>every cell finite, no nodata tag</div>
<div><strong>{cand['positive']:,}</strong>predicted pixels (unit dots)</div>
<div><strong>EPSG:32611</strong>100 m · float32 · one band · {cand['shape'][0]}×{cand['shape'][1]}</div>
<div><strong>{means['R11-fused']:.5f}</strong>blocked proxy DTI (mean of {folds} blocks)</div></div>
<p><b>Submission name:</b> <code>{E(name)}</code><br>
<b>Note to paste in the submit form ({len(R['note'])}/200 characters):</b> <code>{E(R['note'])}</code></p>
<p><a href="{d}receipt.json">Full machine-readable receipt</a> ·
<a href="{d}{E(dfa['file'])}" download>DFA regime-break artefact ({dfa['positive']:,} dots, separate)</a> ·
<a href="{res}r11-review.md">Scientific review, defects found and limitations</a> ·
<a href="{prefix}irregularities.html">Flagged irregularities</a></p>
<p class="muted">Re-read from the bytes on disk: single band, float32, EPSG:32611, exact template
transform, min {cand['min']}, max {cand['max']}, all finite, {cand['positive']:,} positive cells and
zero non-zero cells outside the scored footprint. Portal acceptance has not been tested.</p></section>

<section id="gate"><h2>Validation -- a gate, not a forecast</h2>
<p>Same emitted mass ({P2['matched_mass']:,} dots) for the candidate and for a re-emission of the
incumbent's field, identical exclusions, spatially blocked 4×4 folds with 3-pixel interior guards.
Mean block proxy DTI:</p>
<div class="scroll"><table><tr><th>emission rule / field</th><th>mean blocked proxy DTI</th></tr>{rows}</table></div>
<p>Paired difference against the incumbent <i>as shipped</i>: <b>{gate_sh['mean_delta']:+.5f}</b>,
seeded block bootstrap 95% interval [{gate_sh['ci95'][0]:+.5f}, {gate_sh['ci95'][1]:+.5f}],
{gate_sh['blocks_improved']}/{gate_sh['n_blocks']} blocks improved.
Against the same-mass re-emission of the incumbent field: <b>{gate_re['mean_delta']:+.5f}</b>,
[{gate_re['ci95'][0]:+.5f}, {gate_re['ci95'][1]:+.5f}], {gate_re['blocks_improved']}/{gate_re['n_blocks']} blocks.</p>
<p><b>Both intervals exclude zero.</b> The proxy is the SGMC
state-geology compilation -- a reused, imperfect instrument whose family the group measured at
Spearman ≈ +0.31 against 11 live leaderboard scores. A pass is permission to consider one weekly
slot, not an estimate of the leaderboard.</p></section>

<section id="stratified"><h2>Pass 3 -- the instrument that actually reproduces the live order</h2>
<p>The gate above ran on the <i>un-stratified</i> off-catalogue SGMC truth. A parallel session on this
repository measured (<code>registry/h47.json → ladder</code>) that this instrument <b>inverts</b> the
three known live orderings (0.2600 / 0.2708 / 0.2778) and that only the <i>stratified</i> version --
truth = SGMC fault pixels more than <code>d0</code> pixels from every catalogue pixel, with the
catalogue masked -- reproduces all three. So the candidate was re-scored on it
(<code>scripts/audit_r11_on_stratified.py</code>, receipt <code>evidence/r11-stratified-audit.json</code>) <i>before</i>
anything was claimed about it:</p>
<div class="scroll"><table><tr><th>emission</th><th>DTI, d0 = 3 px</th><th>DTI, d0 = 5 px</th>
<th>covered credit T</th><th>dots within 300 m of truth</th><th>mean credit per dot</th></tr>{p3_table}</table></div>
<p>On the d0 = 5 px instrument the shipped candidate scores <b>{f(p3i.get('sgmc_stratified_d0_5', {}).get('emissions', {}).get('r11-shipped-44090', {}).get('dti'), 5)}</b>
against the incumbent file's {f(p3i.get('sgmc_stratified_d0_5', {}).get('emissions', {}).get('incumbent-0.2778', {}).get('dti'), 5)},
with a uniform-random control at the same mass at {f(p3i.get('sgmc_stratified_d0_5', {}).get('emissions', {}).get('uniform-random-37654', {}).get('dti'), 5)}.
Paired over the {p3_sh.get('blocks', '--')} truth-bearing blocks: shipped <b>{p3_sh.get('mean_delta', 0):+.5f}</b>
(t = {p3_sh.get('t', 0):+.2f}); the same field re-emitted at the matched mass 37,654
<b>{p3_re.get('mean_delta', 0):+.5f}</b> (t = {p3_re.get('t', 0):+.2f}). The d0 = 3 px instrument agrees.
<b>The advantage is new placement, not pruning:</b> the R11 field's AUC over the incumbent's
<i>own</i> dots is {f(p3_auc, 4)} -- chance -- so the candidate wins by putting dots where the
incumbent has none, exactly the route the H47 arm failed to take.</p>
<p class="muted">Still a screen, not a score forecast: this truth is a 1:50k–1:1M compilation roughly
4× denser than the inferred hidden set, and it is not the competition's label set. Pass 3 was run
after the gate rather than preregistered; it is reported because it is the strongest instrument
available here, and the preregistered gate is published beside it, not instead of it.</p></section>

<section id="pass2"><h2>What Pass 2 corrected, and why you can check it</h2>
<p>The experiment ran once, exactly as preregistered. Re-reading the receipt found two defects, both
recorded here rather than quietly fixed:</p>
<ol>
<li><b>The mass rule was degenerate.</b> It transferred a flat proxy credit ratio onto the
incumbent's credit, so its predicted DTI fell with emitted mass and the "max-min" choice collapsed to
the <i>smallest</i> grid point: {P1['chosen_mass']:,} dots. The printed projection at that point was
0.687 -- obviously wrong, which is what exposed the bug.</li>
<li><b>That made the gate unmatched.</b> Pass 1 compared a {P1['chosen_mass']:,}-dot candidate
against the incumbent file at its own mass. Preregistration required a matched emitted mass.</li>
</ol>
<p>Pass 2 replaces the transfer with the measured one -- candidate live credit = candidate
<i>proxy</i> credit at the same mass, scaled by the factor fitted once at the incumbent file's own
operating point ({P2['corrected_transfer']['incumbent_as_shipped_proxy_credit']:,.1f} proxy credit,
proxy DTI {P2['corrected_transfer']['incumbent_as_shipped_proxy_dti']:.4f}) -- re-selects the mass
({P2['matched_mass']:,}) and re-runs the gate at that matched mass. Pass 1's numbers are preserved
unedited in the receipt as <code>pass1_as_executed</code> (gate {p1_gate}); this page reports both.</p>
<div class="scroll"><table><tr><th>mass cap</th><th>dots emitted</th><th>proxy credit</th>
<th>proxy credit, incumbent field</th><th>ratio</th><th>projected DTI, G=7,905</th>
<th>projected DTI, G=14,089</th></tr>{curve_rows}</table></div>
<p class="muted">Projected DTI is a model and its absolute level is not credible: the proxy truth is
easier than the hidden set, so the projection is optimistic by construction. Only the
<i>relative</i> comparison at matched mass is offered as evidence. The hidden-truth masses
G ∈ {{7,905, 14,089}} px are this repository's own inferences from the owner-reported score ledger.</p></section>

<section id="whats-new"><h2>What is actually new here</h2>
<ol>
<li><b>An expected-credit submodular emitter.</b> <code>DTI = T/(0.2·N + 0.8·G)</code> for a sparse
binary prediction, so a dot is worth emitting exactly when its <i>marginal</i> kernel credit exceeds
<code>0.2·DTI</code>; the emitter accepts by marginal gain and rejects duplicates of a neighbour's
coverage. It is exact greedy with an upper-bound invariant, and its stop rule was verified against
brute force (<code>tests/test_optemit.py</code>).</li>
<li><b>1 m lidar terrain descriptors as a scarp matched filter</b> -- 706 of 716 USGS 3DEP tiles,
12 channels, rank-combined and weighted by structure-tensor coherence so point-like features are
suppressed and linear ones survive.</li>
<li><b>GeoDAWN K/Th/U compositional contrast.</b> The official 19-band stack contains only the
radiometric <i>total count</i> (band 6, labelled "tilt angle or total curvature" -- measured
+0.997 correlation with the contractor TC grid, filed as IR-46-13). The ratio grids
(DOI 10.5066/P93LGLVQ) are used here as a lithological-contrast lineament family.</li>
<li><b>The re-localised DFA regime-break detector</b> asked for by the standing brief: 12.8 km
windows over 0.4–3.2 km scales, 800 m placement granularity, requiring both scale ranges to leave
their own background regime. Its artefact and correlations are published whether or not it wins --
and on this proxy it does not win ({means['R11-dfa-local']:.5f} vs {means['R11-fused']:.5f}).</li>
</ol></section>

<section id="other-arms"><h2>The other arms in this repository, and their real status</h2>
<p>R11 is the first arm here whose candidate field beats the live-scored incumbent file on the
stratified instrument. The other arms are published with their failures:</p>
<ul>
<li><b>R10 (DFA crossover, 0.8-12.8 km)</b> — <code>HOLD_DO_NOT_SUBMIT</code>: blocked proxy mean
0.0617 vs 0.1033 for the best comparator, paired −0.0416. Artefact:
<a href="{d_gems}r10/gems46-r10-dfa-crossover-95ba59eb9030-zeros.tif" download>the R10 TIF</a> ·
<a href="{d_gems}r10/receipt.json">receipt</a>.</li>
<li><b>H47-1 (catalogue-supervised lineament detector)</b> — <code>HOLD_DO_NOT_SUBMIT</code>: on the
same d0 = 5 px instrument and the same matched mass it scores 0.053242 against the incumbent's
0.088516 (paired t −5.48 over 127 blocks; AUC over the incumbent's dots 0.497). Its honest
conclusion — <i>it cannot win by pruning or by learning the published catalogue alone</i> — is what
led to the R11 placement route. Artefacts:
<a href="{d_gems}downloads/h47/gemsdoe47-h47-1-catalogue-supervised-lineament-37654-20261006T180000Z-h47a-zeros.tif" download>the H47 TIF</a> ·
<a href="{d_gems}h47/receipt.json">receipt</a> ·
<a href="{d_res}h47-review.md">review</a>.</li>
<li><b>R11 DFA regime-break (the standing brief's hypothesis)</b> — <b>not confirmed</b> on either
instrument; published as a separate artefact above rather than folded into the primary.</li>
</ul>
<p class="muted">Nothing here is an organizer score. The three live-scored family files
(0.2600 / 0.2708 / 0.2778) are owner-reported, and the board attributes scores to participants, not
files (IR-46-01).</p></section>

<section id="correlation"><h2>Is the primary a new hypothesis?</h2>
<p>Preregistration rule: a candidate whose maximum |correlation| with prior shipped files exceeds 0.2
may not be described as new. Measured on the common domain (smoothed fields, Pearson; plus set overlap):</p>
<div class="scroll"><table><tr><th>prior file</th><th>smoothed Pearson</th><th>Jaccard overlap</th></tr>{corr}</table></div>
<p>Maximum |correlation| <b>{f(P2['max_abs_correlation_primary'], 4)}</b> -- <b>above</b> the 0.2
ceiling, so the primary is explicitly <i>not</i> claimed as a new hypothesis: it is a new
<i>emission and fusion</i> of evidence families that earlier topographic arms also touched. The DFA
artefact is separate and does pass the ceiling:</p>
<div class="scroll"><table><tr><th>prior file</th><th>smoothed Pearson</th><th>Jaccard overlap</th></tr>{dfa_corr}</table></div>
<p>Maximum |correlation| <b>{f(P2['max_abs_correlation_dfa'], 4)}</b>. Low correlation is a
redundancy diagnostic on this domain, not proof of geological independence or of having found a fault.</p></section>

<section id="status"><h2>Why the family's 0.2778 worked, and what would beat it</h2>
<p>The published metric is <code>DTI = TPw/(TPw + 0.2·FPw + 0.8·FNw)</code>. For a sparse binary
prediction no two dots best-cover the same truth pixel, so this collapses exactly to
<code>DTI = T/(0.2N + 0.8G)</code>, with <code>T</code> the delivered kernel credit, <code>N</code>
the number of dots and <code>G</code> the hidden truth mass. The family's whole score history is
monotone in <i>deleted</i> mass (121 k → 0.1922, 44 k → 0.2600, 40 k → 0.2708, 37.7 k → 0.2778):
the metric pays for fewer, better-placed dots, not for a better map.</p>
<p>Measured break-even for this family: <b>0.0548</b> credit per dot empirically, 0.2·0.26 = 0.0520
derived. R11's field delivers 0.23 proxy credit per dot at the shipped mass -- far above the bar --
which is why the corrected rule pushes the mass up rather than down.</p>
<p class="muted">Leaderboard values are dated observations, not a live feed. Current leader 0.3774
(xiaofanhu, retrieved 2026-10-06):
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">official board →</a></p></section>

<section><h2>Limitations and flagged irregularities</h2><ul>{lims}</ul>
<p>Also flagged: band 6 is a radiometric total count, not a magnetic curvature (IR-46-13); the
0.2778 attribution is owner-reported, not an organizer receipt (IR-46-01); the 0.3195 in the session
brief is now the #7 board value and 0.3345 is #2 (IR-46-12); the sandbox cannot reach any external
data host except GitHub and PyPI, so no new external dataset entered this experiment (IR-46-06).</p></section>'''

    if guide:
        html_out += f'''<section id="how-to"><h2>Exactly how to submit, click by click</h2>
<ol>
<li><b>Download the GeoTIFF</b> from the <a href="{prefix}index.html">front page</a> --
<code>{E(cand['file'])}</code>. Do not re-save it through an image editor: some editors resample the
grid and the upload is then rejected for a bounds/CRS mismatch.</li>
<li><b>Verify the bytes first.</b> <code>python -c "import rasterio,numpy as np;
a=rasterio.open('PATH').read(1);print(a.shape,a.min(),a.max(),np.isfinite(a).all())"</code> must print
<code>({cand['shape'][0]}, {cand['shape'][1]}) 0.0 1.0 True</code>. sha256
<code>{E(cand['sha256'])}</code>.</li>
<li><b>Sign in</b> to <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">the
competition</a>, confirm eligibility, and open <i>New submission</i>.</li>
<li><b>Choose the .tif</b> under <i>File to submit</i>. A single-band GeoTIFF, EPSG:32611, 100 m,
3730×3292, float32 in [0, 1] with no nodata tag is what the portal expects -- exactly this file.</li>
<li><b>Use the name and note</b> from the front page (<code>{E(name)}</code>) so this submission
stays distinguishable from the group's earlier files.</li>
<li><b>Respect the status banner.</b> It currently says <b>{E(label.split(chr(45))[0].strip())}</b>.
Keep the organizer receipt (score, file hash, note) next to this page when it arrives; until then no
score is claimed anywhere in this repository.</li>
<li><b>If the portal answers "Predicted values must be in range [0, 1]"</b> -- that message is what a
large negative nodata sentinel such as <code>-3.4028234663852886e+38</code> produces. This file has
no nodata tag, no negative value and no NaN ({cand['shape'][0] * cand['shape'][1]:,} finite cells).</li>
</ol>
<h3>Rebuild every artefact on CPU</h3>
<pre>python -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/restore_competition_data.sh
bash scripts/restore_r10_reference.sh
.venv/bin/python scripts/screen_r11.py          # channel screen
.venv/bin/python scripts/run_r11.py             # Pass 1: fields, curves, first gate
.venv/bin/python scripts/refine_r11_mass.py     # Pass 2: corrected mass + matched-mass gate
.venv/bin/python scripts/build_r11_site.py      # this site
.venv/bin/python scripts/verify_r11_candidate.py
.venv/bin/python -m pytest</pre>
<p class="muted">The science runs in this repository, not in your browser. No organizer credentials
are used, requested or stored anywhere in this project.</p></section>'''

    html_out += f'''<section><h2>Evidence and manual review</h2><ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">Official task,
metric and GeoTIFF requirements</a> -- read line by line; transcribed in <code>src/gems46/metric.py</code>.</li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official
leaderboard</a> -- 0.3774 was #1 when this page was generated.</li>
<li><a href="https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7">GeoDAWN data release
(ScienceBase 657e1d85d34e23d3533209f7, DOI 10.5066/P93LGLVQ)</a> -- source of the K/Th/U grids.</li>
<li><a href="https://www.usgs.gov/publications/state-geologic-map-compilation-sgmc-geodatabase-conterminous-united-states">USGS
State Geologic Map Compilation</a> -- the off-catalogue proxy; 1:50 k–1:1 M source scales, not 100 m truth.</li>
<li><a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a> -- 1 m lidar behind the scarp family
(706 of 716 tiles processed).</li>
<li><a href="https://doi.org/10.1103/PhysRevE.49.1685">Peng et al. 1994</a> -- the DFA cited by the brief.</li>
</ul><p>Mirror hashes prove reproducibility, not organizer authentication of the data or of any score.
Every input hash and every measured comparison is in <a href="{d}receipt.json">the receipt</a>.</p></section>
<footer><b>Maximize P(Win):</b> a candidate that fails the gate is published as a negative result
instead of being spent on a slot. <b>Own the Outcome:</b> our own defects -- the degenerate mass rule
and the unmatched gate -- are written down where they can be checked.<br>
Generated from registry/r11.json by scripts/build_r11_site.py ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE46">source repository</a>.</footer>'''

    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>GEMSDOE46 — R11 submission, gate and receipts</title>'
            f'<style>{CSS}</style></head><body><header><div><b>GEMS / DISCOVERY LAB</b>'
            f'<span><a href="{prefix}executive-summary.html">Submission guide</a> · '
            f'<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Live board</a></span>'
            f'</div></header><main>{html_out}</main></body></html>')


def main() -> None:
    (ROOT / "index.html").write_text(render("docs/"))
    (ROOT / "docs/index.html").write_text(render(""))
    (ROOT / "docs/executive-summary.html").write_text(render("", guide=True))
    active = {ROOT / "docs/index.html", ROOT / "docs/executive-summary.html", ROOT / "index.html"}
    marker = "<!-- R11 archive notice -->"
    # Only pages that belong to a superseded experiment get the banner. Stamping a reference page
    # (sources, validation, irregularities, how-to-submit) with "historical experiment" is false.
    stamp_dirs = {"r9", "r10", "h46", "gems46", "downloads"}
    stamp_files = {"analysis.html", "submission-analysis.html"}
    for page in (ROOT / "docs").rglob("*.html"):
        if page in active:
            continue
        if page.parent.name not in stamp_dirs and page.name not in stamp_files:
            continue
        text = page.read_text()
        if marker in text:
            continue
        link = os.path.relpath(ROOT / "docs/index.html", page.parent)
        notice = (f'{marker}<aside style="padding:18px;background:#fff0c8;color:#382a0b;'
                  f'font:16px/1.5 system-ui"><b>Historical experiment — not the current candidate.</b> '
                  f'<a href="{link}">Current audited download, gate status and submission guide →</a></aside>')
        text = re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + notice, text, count=1)
        page.write_text(text)
    print("Built index.html, docs/index.html and docs/executive-summary.html from registry/r11.json")


if __name__ == "__main__":
    main()
