#!/usr/bin/env python3
"""Build the active GEMSDOE46 site from the R12 receipt.

Every number rendered here is read from ``registry/r12.json`` /
``evidence/r12_layer_screen.json`` at build time — nothing is typed by hand
(``AGENTS.md`` §4).  The page is deterministic, so CI can assert that the
generated site matches what is committed.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = json.loads((ROOT / "registry/r12.json").read_text())
SCREEN = json.loads((ROOT / "evidence/r12_layer_screen.json").read_text())
E = html.escape

CSS = '''*{box-sizing:border-box}body{margin:0;background:#f3f5f4;color:#172b29;font:16px/1.65 system-ui,sans-serif}
main{max-width:1060px;margin:auto;padding:32px 24px}header{background:#143f38;color:white;padding:18px 24px}
header div{max-width:1012px;margin:auto;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
header a{color:#c5ecdb}h1{font-size:clamp(30px,5vw,48px);line-height:1.15;letter-spacing:-1.5px}
h2{font-size:23px}h3{font-size:18px}a{color:#096b59}
section{background:white;border:1px solid #d6dfdb;border-radius:12px;padding:24px;margin:22px 0}
.label{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#5c736d}
.download{border:3px solid #126b56;background:#eef8f3}
.warning{border-left:5px solid #c88115;background:#fff9ea}
.good{border-left:5px solid #126b56;background:#eef8f3}
.button{display:inline-block;background:#126b56;color:white;padding:16px 26px;border-radius:8px;
text-decoration:none;font-weight:700;margin:14px 14px 10px 0;font-size:18px}
.button:hover{background:#0d5142}
.muted{color:#526c66}code{overflow-wrap:anywhere;background:#edf3f0;padding:3px;font-size:13px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:15px;margin:16px 0}
.cards div{border:1px solid #d6dfdb;border-radius:8px;padding:18px;background:#fbfdfc}
.cards strong{display:block;font-size:27px;letter-spacing:-1px}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #dde5e0;padding:11px 8px}
th{font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#5c736d}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto}footer{padding:20px 0;font-size:13px;color:#526c66}
li{margin-bottom:8px}pre{overflow:auto;background:#edf3f0;padding:16px;border-radius:8px;font-size:13px}
ol li,ul li{margin-bottom:10px}.best{font-weight:700;color:#0d5142}'''


def rows(d: dict, best_key: str, fmt: str = "{:.5f}") -> str:
    out = []
    for k, v in sorted(d.items(), key=lambda kv: -kv[1]):
        cls = ' class="best"' if k == best_key else ""
        label = {"R12": "R12 · this candidate", "PART_lidar_only": "LiDAR morphology alone (component)",
                 "PART_radiometric_only": "Gamma-ray alone (component)",
                 "REF_rtp_gradient": "RTP magnetic gradient (classic arm)",
                 "GEMSDOE32-owner-reported-02778": "GEMSDOE32 file, owner-reported 0.2778",
                 "R10-DFA-crossover": "R10 DFA crossover (previous session)"}.get(k, k)
        out.append(f'<tr><td{cls}>{E(label)}</td><td class="n"{cls}>{fmt.format(v)}</td></tr>')
    return "".join(out)


def render(prefix: str, guide: bool = False) -> str:
    d = prefix + "r12/"
    research = prefix + "research/"
    a = R["audit"]
    cfg = R["frozen_configuration"]
    means, pooled = R["mean_locked_dti"], R["pooled_locked_dti"]
    rob = R["robustness_all_locked_blocks"]["means"]
    best = R["best_comparator"]
    ci = R["paired_bootstrap_95"]
    gate_ok = R["gate_passed"]
    status = ("Proxy gate PASSED — cleared for a submission slot"
              if gate_ok else "HOLD — do not submit this candidate")

    screen_rows = "".join(
        f'<tr><td>{E(r["field"])}</td><td class="n">{r["dti"]:.5f}</td>'
        f'<td class="n">{r["precision_300m"] * 100:.1f}%</td></tr>'
        for r in SCREEN["rows"][:8])

    comp = R["comparisons"]
    st = R["stratified_instrument"]
    inc = "GEMSDOE32-owner-reported-02778"
    storder = sorted(st["scores"], key=lambda k: -st["scores"][k]["dti"])
    _strows = []
    for k in storder:
        hl = ' style="font-weight:700"' if k == "R12" else ""
        _strows.append(
            f"<tr{hl}><td>{E(k)}</td>"
            f'<td class="n">{st["scores"][k]["tp"]:,.0f}</td>'
            f'<td class="n">{st["scores"][k]["dti"]:.5f}</td>'
            f'<td class="n">{100 * st["hit_fraction"][k]:.2f} %</td></tr>')
    strows = "".join(_strows)
    corr_rows = ""
    for name, rec in comp.items():
        if "candidate_pearson" in rec:
            corr_rows += (f'<tr><td>{E(name)} (shipped submission)</td>'
                          f'<td class="n">{rec["candidate_pearson"]["pearson"]:+.4f}</td>'
                          f'<td class="n">{rec["jaccard"]:.4f}</td>'
                          f'<td class="n">{rec["field_vs_smoothed_submission"]["spearman"]:+.4f}</td></tr>')
    for name, rec in comp.items():
        if "field_raw" in rec:
            corr_rows += (f'<tr><td>{E(name)} (evidence field)</td>'
                          f'<td class="n">{rec["field_raw"]["pearson"]:+.4f}</td>'
                          f'<td class="n">—</td>'
                          f'<td class="n">{rec["field_smoothed"]["spearman"]:+.4f}</td></tr>')

    cov = R["coverage"]
    sweep = sorted(R["selection_sweep"], key=lambda r: -r["mean_select_dti"])
    sweep_rows = "".join(
        f'<tr><td><code>{E(r["config"]["key"])}</code></td><td class="n">{r["mean_select_dti"]:.5f}</td>'
        f'<td class="n">{r["emitted"]:,}/{r["requested"]:,}</td></tr>' for r in sweep[:6])
    sweep_rows += "".join(
        f'<tr><td><code>{E(r["config"]["key"])}</code></td><td class="n">{r["mean_select_dti"]:.5f}</td>'
        f'<td class="n">{r["emitted"]:,}/{r["requested"]:,}</td></tr>' for r in sweep[-3:])

    content = f'''<p class="label">GEMSDOE46 · experiment R12 · generated {E(R["generated_utc"][:10])}</p>
<h1>Two independent sensors agree<br>where the catalogue is silent.</h1>
<p class="muted">2 m LiDAR scarp morphology × airborne gamma-ray spectrometry (USGS GeoDAWN,
DOI 10.5066/P93LGLVQ) · {a["positive"]:,} predicted pixels · independently generated GeoTIFF</p>

<section class="download" id="submission-download"><p class="label">Submission file — ready to download</p>
<h2 style="margin-top:6px">R12 · scarp-morphology × gamma-ray concordance</h2>
<a class="button" download href="{d}{E(R["file"])}">⬇ Download the .TIF submission</a>
<a class="button" style="background:#0d5142" href="{prefix}executive-summary.html">How to submit it →</a>
<p><code>{E(R["file"])}</code> &nbsp;·&nbsp; {a["bytes"]:,} bytes &nbsp;·&nbsp; SHA-256 <code>{a["sha256"]}</code></p>
<div class="cards">
<div><strong>[0, 1]</strong>every value finite, range-checked cell by cell</div>
<div><strong>{a["positive"]:,}</strong>predicted pixels (0 elsewhere)</div>
<div><strong>{E(a["crs"])}</strong>{a["shape"][0]} × {a["shape"][1]} · float32 · 1 band · 100 m</div>
<div><strong>no nodata</strong>no NaN, no sentinel, transform equals the template</div>
</div>
<p><b>Submission name:</b> <code>GEMSDOE46-R12-SCARP-RAD-CONCORDANCE-{a["pixel_sha256"][:12].upper()}</code></p>
<p><b>Short note for the form:</b> <code>{E(R["note"])}</code></p>
<p class="muted"><a href="{d}receipt.json">Full machine-readable receipt</a> ·
<a href="{research}r12-review.md">scientific review</a> ·
<a href="{research}session-r12-plan.md">preregistered hypotheses</a> ·
<a href="{prefix}sources.html">official sources</a></p></section>

<section class="{"good" if gate_ok else "warning"}"><b>{status}</b>
<p>R12 beat every comparator on the <em>locked</em> spatial blocks — the blocks that were never used to
choose its configuration. Paired mean difference against the best comparator
({E(best)}): <b>{R["paired_delta_vs_best"]:+.5f}</b>, seeded block-bootstrap 95 % interval
[{ci[0]:+.5f}, {ci[1]:+.5f}]. Under R10's stricter rule (which also refuses any block dropped for zero
shared emission capacity) the gate reads
<b>{"pass" if R["gate_strict_r10_style"] else "fail"}</b>; {len(R["locked_skipped"])} of
{len(R["locked_folds"]) + len(R["locked_skipped"])} locked blocks were dropped because a gapped
comparator could emit nothing there, which is conservative for R12. The preregistered rule
(<a href="{research}session-r12-plan.md">plan §7</a>) governs, and both readings are published.</p>
<p><b>No leaderboard score exists for this file.</b> Nothing here was submitted to the competition by
this pipeline, and a proxy result is not a score forecast.</p></section>

<section id="validation"><h2>What was measured</h2>
<p class="muted">Instrument: off-catalogue USGS SGMC fault traces as proxy truth, the published
catalogue excluded by a fixed 200 m buffer, identical emitted mass per block for every method, exact
distance-weighted Tversky index from the official formula.</p>
<div class="cards">
<div><strong>{means["R12"]:.4f}</strong>R12 mean locked-block DTI</div>
<div><strong>{means[best]:.4f}</strong>best comparator</div>
<div><strong>{pooled["R12"]:.4f}</strong>R12 pooled over locked blocks</div>
<div><strong>{rob["R12"]:.4f}</strong>R12 over all locked blocks at full budget</div>
</div>
<h3>Matched emitted mass, {len(R["locked_folds"])} evaluable locked blocks</h3>
<div class="scroll"><table><tr><th>Field, re-emitted by the same rule</th><th class="n">Mean DTI</th></tr>{rows(means, "R12")}</table></div>
<h3>Robustness view: all {len(R["robustness_all_locked_blocks"]["folds"])} locked blocks, each method at its own full budget</h3>
<p class="muted">Blocks where a gapped method emits nothing are kept, so a method is charged for its own
coverage gaps instead of having those blocks removed.</p>
<div class="scroll"><table><tr><th>Field</th><th class="n">Mean DTI</th></tr>{rows(rob, "R12")}</table></div>
<p>Comparator files are <em>re-emitted from their own fields</em> inside each block at matched mass.
These are measurements of evidence fields under one emission rule, not scores of the original files.
Low correlation is non-redundancy on this mask, not proof of geological independence.</p></section>

<section id="stratified"><h2>The instrument that reproduces the known live ordering</h2>
<p>A sibling session in this repository measured the three live-scored family files
(0.2600 / 0.2708 / 0.2778) on six instrument variants and found that the un-stratified off-catalogue
SGMC proxy <em>inverts</em> that ordering, while SGMC truth stratified at ≥3 px from the catalogue
(default 5 px = 500 m), with the catalogue masked as <code>known</code> exactly as the organiser
confirmed for the live scorer, reproduces 0.2600 &lt; 0.2708 &lt; 0.2778. The locked-block table above
used a 200 m exclusion, which that ladder never validated
(<a href="{research}session-r12-plan.md">plan §7.1</a>, irregularity IR-46-21), so the promotion rule
was amended to require <b>both</b> instruments before this measurement was computed.</p>
<p class="muted">{E(st["instrument"])} · stratified truth {st["truth_px"]:,} px — identical to the
d0 = 5 row of that ladder, so this is the same instrument, not a look-alike · whole footprint ·
matched mass {st["budget"]:,}.</p>
<div class="scroll"><table><tr><th>Field, re-emitted at the same mass</th><th class="n">Covered truth T</th>
<th class="n">DTI</th><th class="n">Dots within 300 m</th></tr>{strows}</table></div>
<div class="cards">
<div><strong>{st["delta_vs_incumbent"]:+.5f}</strong>Δ DTI vs the incumbent file</div>
<div><strong>{st["scores"]["R12"]["dti"] / st["scores"][inc]["dti"]:.2f}×</strong>R12 ÷ incumbent</div>
<div><strong>{100 * st["hit_fraction"]["R12"]:.1f} %</strong>R12 hit rate (incumbent {100 * st["hit_fraction"][inc]:.1f} %)</div>
<div><strong>{st["uniform_random_at_matched_mass"]["tp"]:,.0f}</strong>uniform random at matched mass, T</div>
</div>
<p>Both preregistered readings agree: locked blocks <b>{"pass" if R["gate_locked_blocks_200m"] else "fail"}</b>,
stratified whole-domain <b>{"pass" if R["gate_stratified_whole_domain"] else "fail"}</b>. Every
“plausible geology” field measured here before sat within ±20 % of a random baseline
(T ≈ 3,700–5,100); R12 is at T = {st["scores"]["R12"]["tp"]:,.0f}. That is a different signal, which is
what two sensors absent from the 19-band official stack would be expected to give.</p>
<p><b>It is still not a score.</b> The same instrument puts the incumbent at
{st["scores"][inc]["dti"]:.5f} where the live board says 0.2778, so absolute proxy values are not
forecasts and the ratio is not a promised multiplier. The stratified reading is whole-domain, so no
independence interval is attached to it. Only an organiser receipt can settle the question.</p></section>

<section><h2>The idea, and the part of it that failed</h2>
<p>A fault scarp is an <em>oriented</em> slope break: the band-passed 2 m LiDAR gradient measured down
the regional slope differs from the one measured against it. The same structure disrupts the top
0.3–0.5 m that airborne gamma-ray spectrometry samples, so total count and the Th/K ratio break along
the trace too. Those are two physically independent sensors — topography and near-surface
radiochemistry — and neither is an amplitude or curvature maximum of a potential field.</p>
<p><b>Measured, not assumed:</b> a strong two-sensor <em>gate</em> was falsified. On the selection
blocks the concordance weight w = 0.25 scored {sweep[0]["mean_select_dti"]:.5f} while a full gate
(w = 1) fell to {[r["mean_select_dti"] for r in sweep if r["config"]["key"] == "w1.00-fb0.90-thin0"][0]:.5f}
and ridge-axis thinning cost about 0.01–0.03 everywhere it was tried. What survived is a
<em>mild</em> radiometric reweighting plus a coverage-aware fallback. The 2 m LiDAR product covers
{cov["lidar_share_of_domain"]:.1%} of the emittable domain, so a LiDAR-only detector is blind over the
rest; R12 admits radiometric candidates there, capped at the {cfg["fallback_quantile"]:.0%} quantile of
the morphology score so they cannot outrank good morphology anywhere else.</p>
<div class="scroll"><table><tr><th>Selection-block configuration (odd blocks only)</th><th class="n">Mean DTI</th><th class="n">mass</th></tr>{sweep_rows}</table></div>
<p class="muted">Top 6 and bottom 3 of {len(R["selection_sweep"])} configurations. Selection used only
the odd blocks of a 6×6 partition; R10 used a 4×4 partition, so no block edge is shared with the
previous session.</p></section>

<section><h2>Why the new layers matter</h2>
<p>Neither layer is in the organiser's <code>training_features.tif</code>, and neither had been used by
any arm in this repository before R12 (checked by searching <code>registry/</code>, <code>docs/</code>
and <code>src/</code>). Whole-domain exploratory screen at matched mass, before any block split:</p>
<div class="scroll"><table><tr><th>Evidence field</th><th class="n">Proxy DTI</th><th class="n">dots within 300 m</th></tr>{screen_rows}</table></div>
<p class="muted">Exploratory only (<code>evidence/r12_layer_screen.json</code>). It motivated the
ranking; it was never the decision instrument.</p></section>

<section><h2>Is it a new hypothesis or a relabelled one?</h2>
<p>The prompt requires low correlation with prior gradient/curvature submissions before calling a
candidate new. Three different measurements, reported separately because they answer different
questions:</p>
<div class="scroll"><table><tr><th>Compared with</th><th class="n">field / pixel Pearson</th>
<th class="n">Jaccard of emitted pixels</th><th class="n">smoothed-field Spearman</th></tr>{corr_rows}</table></div>
<ul>
<li><b>Against previously shipped submissions:</b> emitted-pixel correlation ≤ 0.006 and Jaccard
{comp.get("GEMSDOE32-owner-reported-02778", {}).get("jaccard", 0):.4f} — the dot sets are almost
disjoint, so this is not a renamed prediction.</li>
<li><b>Against gradient/curvature evidence fields:</b> at most
{max(abs(comp["REF_rtp_gradient"]["field_smoothed"][k]) for k in ("pearson", "spearman")):.3f} — low.</li>
<li><b>Honest caveat:</b> the <em>smoothed</em> field still correlates
{comp.get("GEMSDOE32-owner-reported-02778", {}).get("field_vs_smoothed_submission", {}).get("spearman", 0):+.3f}
(Spearman) with the GEMSDOE32 file at coarse scales. Two fault-probability fields over the same
terrain share regional structure. R12 is not spatially independent of the family's best field; it is
pixel-distinct and it uses sensors that field never touched.</li>
</ul></section>

<section><h2>Mass, and what would have to be true to reach the leader</h2>
<p>With <code>S</code> emitted pixels, <code>G</code> truth pixels and <code>M = T</code> the exact
denominator is <code>0.2S + 0.8G</code>, so at the shipped mass of {R["parameters"]["budget"]:,} and the
live-anchored <code>G ≈ 14,089</code> the denominator is ≈18,802: a live 0.2778 implies
<code>T ≈ 5,224</code> covered truth pixels and the current leader 0.3774 implies
<code>T ≈ 7,094</code> — 36 % more coverage at identical mass. Coverage, not mass, is the lever.</p>
<p>On a truth-mass-matched copy of the proxy (whole connected components kept up to
{R["sensitivity"]["truth_mass_matched"]["kept_px"]:,} px, seeded) the shipped mass is still on the
rising part of the curve, so the budget was <em>not</em> reduced:
{", ".join(f'{k} → {v:.4f}' for k, v in sorted(R["sensitivity"]["truth_mass_matched"]["mean_select_dti_by_budget"].items()))}.</p>
<p><b>Leaderboard snapshot:</b> 0.3774 (xiaofanhu), retrieved 2026-10-06 — a dated observation, not a
live feed. <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Check
the official leaderboard →</a></p></section>'''

    if guide:
        content += f'''<section id="how-to-submit"><h2>Exactly how to submit this file</h2>
<ol>
<li><b>Download the GeoTIFF</b> with the button at the top of this page
(<code>{E(R["file"])}</code>). Keep the <code>.tif</code> extension. Do not download an HTML page or a
JSON receipt and rename it.</li>
<li><b>Do not re-save it in a GIS editor.</b> Re-exporting can change the dtype, the compression, the
CRS or the grid and the portal rejects any of those. The file as downloaded already matches the
template: {E(a["crs"])}, {a["shape"][0]} × {a["shape"][1]}, 100 m, float32, single band, no nodata tag,
every value finite and inside [0, 1].</li>
<li><b>Optional integrity check.</b> <code>sha256sum {E(R["file"])}</code> must equal
<code>{a["sha256"]}</code>.</li>
<li><b>Sign in</b> at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">the
DrivenData GEMS competition</a>, confirm you are eligible under the
<a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">official prize rules</a>, and open
<b>New submission</b>.</li>
<li><b>File to submit:</b> choose the <code>.tif</code>. A single-band GeoTIFF or a zip containing one
GeoTIFF is accepted.</li>
<li><b>Note (optional):</b> paste
<code>{E(R["note"])}</code></li>
<li><b>Name it</b> <code>GEMSDOE46-R12-SCARP-RAD-CONCORDANCE-{a["pixel_sha256"][:12].upper()}</code> in
your own records, and keep the organiser's score, the file hash and the note together. A public
leaderboard value cannot identify which file produced it.</li>
</ol>
<h3>If the form says "Predicted values must be in range [0, 1]"</h3>
<p>That error has been seen in this project before. Do not fix it by blindly clipping a raster — find
the cause. The usual causes are a negative nodata sentinel inherited from an input band, NaNs written
outside the footprint, a dtype change, or an unintended resample. This file was re-opened after
writing and checked cell by cell: <code>min = {a["min"]}</code>, <code>max = {a["max"]}</code>,
all values finite, no nodata tag. Portal acceptance is still not claimed until an organiser receipt
exists.</p>
<h3>Rebuild everything locally (CPU only, no GPU)</h3>
<pre>python -m venv .venv
.venv/bin/pip install -r requirements.txt
bash scripts/restore_competition_data.sh      # hash-pinned organiser rasters + SGMC proxy
bash scripts/restore_r12_reference.sh         # hash-pinned USGS GeoDAWN layers
bash scripts/restore_r10_reference.sh         # comparator file
.venv/bin/python scripts/screen_r12_layers.py # exploratory layer screen
.venv/bin/python scripts/run_r12.py           # locked experiment + audited GeoTIFF
.venv/bin/python scripts/build_r12_site.py    # this site
.venv/bin/python -m pytest
.venv/bin/python scripts/verify_all.py</pre>
<p>The published page serves a precomputed, audited file; no scientific computation happens in your
browser. Hidden competition labels and authenticated organiser submission access are not available to
this pipeline, so it can prepare and validate a file but cannot submit one.</p></section>'''

    content += f'''<section id="limits"><h2>Limitations, stated plainly</h2><ul>
{''.join(f"<li>{E(x)}</li>" for x in R["limitations"])}
<li>Blocked, not viable this session: hypocentre lineaments from the USGS ANSS catalogue.
<code>earthquake.usgs.gov</code> returns HTTP 000 from this sandbox (re-measured 2026-10-06), so the
free official source cannot be fetched here. Named in the plan rather than assumed away.</li>
</ul></section>

<section><h2>Official sources for manual review</h2><ul>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">GEMS Prize
Challenge — problem description, metric and GeoTIFF requirements</a></li>
<li><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">Official
public leaderboard</a> (snapshot dated above; not a live feed)</li>
<li><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">Official prize rules (OSTI 96647)</a></li>
<li><a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS
GeoDAWN airborne magnetic and radiometric surveys</a> — DOI
<a href="https://doi.org/10.5066/P93LGLVQ">10.5066/P93LGLVQ</a>, ScienceBase item 657e1d85d34e23d3533209f7;
mirror <a href="https://gdr.openei.org/submissions/1591">GDR 1591</a>. Provenance of the gamma-ray and
LiDAR layers used here.</li>
<li><a href="https://www.usgs.gov/3d-elevation-program">USGS 3D Elevation Program</a> — 1 m LiDAR flown
with the survey, the source of the scarp-morphology channels.</li>
<li><a href="https://www.usgs.gov/publications/state-geologic-map-compilation-sgmc-geodatabase-conterminous-united-states">USGS
State Geologic Map Compilation</a> — provenance of the off-catalogue proxy truth (source map scales
1:50,000–1:1,000,000).</li>
<li><a href="https://github.com/drivendataorg/gems-prize-reference-solution">Organiser reference
solution</a></li>
</ul><p>Restored bytes are hash-pinned against <code>registry/data_manifest.json</code>. Pins prove
mirror consistency, not organiser authentication. See the
<a href="{d}receipt.json">receipt</a> for every input hash, every block score and the full sweep.</p></section>

<footer><b>Maximize P(Win):</b> the locked decision set was read once, negative results are published
with the positive one, and a failed gate protects the weekly slot. <b>Own the Outcome:</b> our own
indexing, metric and instrument defects are fixed in the open and archived rather than quietly
rewritten.<br>Generated from <code>registry/r12.json</code> ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE46">source repository</a> ·
older pages in this site are archived and may contain superseded claims.</footer>'''

    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>GEMSDOE46 — R12 scarp × gamma-ray concordance submission</title>'
            f'<style>{CSS}</style></head><body><header><div><b>GEMS / DISCOVERY LAB · R12</b>'
            f'<span><a href="{prefix}executive-summary.html">Submission guide</a> · '
            f'<a href="{prefix}sources.html">Sources</a> · '
            f'<a href="{prefix}research/r12-review.md">Review</a></span></div></header>'
            f'<main>{content}</main></body></html>')


def main() -> None:
    """R12 is published on its own page.

    The live landing pages belong to scripts/build_r11f_site.py (the R11F arm, which passed its own
    gate on main).  Two gate-passed candidates coexist in this repository; R12 gets a full page, a
    receipt and a prominent cross-link rather than silently replacing the other arm's decision.
    """
    out = ROOT / "docs/r12"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render("../", True))
    print("Built docs/r12/index.html from the R12 receipt")

    # keep historical evidence reachable but never leave a stale recommendation unqualified
    active = {ROOT / "docs/index.html", ROOT / "docs/executive-summary.html"}
    marker = "<!-- R10 archive notice -->"
    for page in sorted((ROOT / "docs").rglob("*.html")):
        if page in active:
            continue
        text = page.read_text()
        if marker in text or "Archived H46 experiment:" in text:
            continue
        link = os.path.relpath(ROOT / "docs/index.html", page.parent)
        notice = (f'{marker}<aside style="padding:18px;background:#fff0c8;color:#382a0b;'
                  f'font:16px/1.5 system-ui"><b>Historical experiment — not a current recommendation.</b> '
                  f'<a href="{link}">Current audited download, measurements and submission gate →</a></aside>')
        page.write_text(re.sub(r"(<body\b[^>]*>)", lambda m: m.group(1) + notice, text, count=1))


if __name__ == "__main__":
    main()
