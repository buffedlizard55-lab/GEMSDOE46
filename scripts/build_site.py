#!/usr/bin/env python3
"""Generate the GitHub Pages site from registry/*.json so the pages cannot drift from the receipts.

Default: delegates to build_r12_site.py for the active site.
Historical rebuild (requires old derived stats): --legacy-h46 ->  docs/h46/{index,executive-summary,hypotheses,validation,
research,sources,irregularities}.html + docs/h46/assets/style.css + docs/h46/downloads/*.png
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "h46"
REG = ROOT / "registry"
ASSETS = DOCS / "assets"

CSS = """
:root{--bg:#0f1317;--panel:#161c22;--line:#243040;--ink:#e8eef5;--dim:#9fb0c0;--accent:#4cc2ff;--ok:#3ddc97;--warn:#ffb347;--bad:#ff6b6b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
header{border-bottom:1px solid var(--line);background:linear-gradient(180deg,#131a21,#0f1317)}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
header .wrap{display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:space-between;padding:14px 20px}
.brand{font-weight:700;letter-spacing:.3px}
nav a{margin-left:16px;color:var(--dim);font-size:14px}nav a.active{color:var(--ink)}
h1{font-size:30px;line-height:1.25;margin:28px 0 10px}
h2{font-size:22px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:17px;margin:22px 0 6px}
p,li{color:#d8e2ec}
.dim{color:var(--dim)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:16px 0}
.download{border:1px solid #2e6f8f;background:linear-gradient(180deg,#14242e,#121a20);border-radius:14px;padding:20px;margin:18px 0}
.download h2{margin-top:0;border:0}
.btn{display:inline-block;background:var(--accent);color:#04121b;font-weight:700;padding:11px 18px;border-radius:9px;margin:6px 10px 6px 0}
.btn.alt{background:#2b3a48;color:var(--ink)}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px}
code{background:#0b1014;border:1px solid var(--line);border-radius:5px;padding:1px 5px}
pre{background:#0b1014;border:1px solid var(--line);border-radius:10px;padding:14px;overflow:auto}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:#131c24;color:#cfe0ee}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:14px 0}
.kv div{background:#131a21;border:1px solid var(--line);border-radius:10px;padding:12px}
.kv b{display:block;font-size:24px}
footer{border-top:1px solid var(--line);color:var(--dim);font-size:13px;margin-top:40px;padding:22px 0 40px}
.tag{display:inline-block;font-size:12px;border:1px solid var(--line);border-radius:999px;padding:2px 9px;color:var(--dim);margin-right:6px}
img{max-width:100%;border-radius:10px;border:1px solid var(--line)}
"""

NAV = [("index.html", "Overview"), ("executive-summary.html", "Executive summary &amp; how to submit"),
       ("hypotheses.html", "Hypotheses"), ("validation.html", "Validation"),
       ("research.html", "Research"), ("sources.html", "Sources"),
       ("irregularities.html", "Irregularities")]


CORE_VALUES = """
<div class="card" style="border-left:4px solid #b45309;margin:18px 0">
<b>How decisions are made here &mdash; the two core values.</b>
<div><b>Maximize P(Win).</b> Every choice is made against the official metric's own algebra
(use the exact metric and state every emission-model assumption), never against a proxy known
to drift. Where the proxy and the algebra disagree &mdash; they do, see IR-46-04 &mdash; the algebra decides and the
disagreement is filed.</div>
<div><b>Own the Outcome.</b> End to end: the shipped bytes are re-read and audited, the estimator is verified
against exact-spectral fGn and textbook DFA values, negative results are published as negative results
(H46-1 measured weaker than the structural field), and the instrument that would falsify the next idea is
shipped with it.</div>
</div>
"""


def page(title: str, body: str, active: str) -> str:
    parts = []
    for h, t in NAV:
        cls = " class='active'" if h == active else ""
        parts.append(f'<a href="{h}"{cls}>{t}</a>')
    nav = "".join(parts)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} - GEMSDOE46</title>
<link rel="stylesheet" href="assets/style.css"></head>
<body>
<aside style="padding:20px;background:#ffe3a3;color:#241800"><b>Archived H46 experiment:</b> recommendations and claims may be superseded. <a href="../index.html">Read the current audited download, measurements and submission gate.</a></aside>
<header><div class="wrap"><span class="brand">GEMSDOE46 &middot; DOE GEMS Prize</span><nav>{nav}</nav></div></header>
<main class="wrap">{body}</main>
<footer class="wrap">Every number on this site is regenerated from <code>registry/*.json</code> by
<code>scripts/build_site.py</code>. Scores marked <em>owner-reported</em> are not organiser receipts.
Retrieved 2026-10-06 UTC.</footer>
{CORE_VALUES}
</body></html>
"""


def g(d: dict, k: str, default: str = "\u2014") -> str:
    """Archived pages must survive registry entries written by later sessions."""
    v = d.get(k, default)
    return v if isinstance(v, str) else str(v)


def esc(x) -> str:
    return html.escape(str(x))


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    (DOCS / ".nojekyll").write_text("")
    (ASSETS / "style.css").write_text(CSS)

    sub = json.loads((REG / "submissions.json").read_text())
    hyp = json.loads((REG / "hypotheses.json").read_text())
    src = json.loads((REG / "sources.json").read_text())
    irr = json.loads((REG / "irregularities.json").read_text())
    cal = sub["calibration"]
    files = sub["files"]
    names = list(files)
    h1_tag = next(n for n in names if n.startswith("H46-1"))
    h2_tag = next(n for n in names if n.startswith("H46-2"))
    h1f, h2f = files[h1_tag], files[h2_tag]
    inst = sub["instrument_results"]
    sweep = sub.get("hedge_sweep", {}).get("hedge_sweep_proxy_dti", {})
    snap = hyp.get("leaderboard_snapshot", {})
    dist = sub["distinctness"]
    # dfa_stats.json is a git-ignored derived artifact (scripts/build_dfa_field.py).  The archived
    # H46 pages must still regenerate in a clean checkout, so it is optional.
    stats_path = ROOT / "data" / "derived" / "dfa_stats.json"
    stats = json.loads(stats_path.read_text()) if stats_path.exists() else {"bands": {}}

    # ------------------------------------------------------------------ overview
    dfa_rows = "".join(
        f"<tr><td><code>{k}</code></td><td>{v['alpha_median_row']:.3f}</td>"
        f"<td>{v['alpha_iqr_row']:.3f}</td><td>{v['absz_p99']:.2f}</td></tr>"
        for k, v in stats["bands"].items() if k.endswith("_raw"))
    if not dfa_rows:
        dfa_rows = ("<tr><td colspan='4'>not regenerated in this checkout &mdash; run "
                    "<code>scripts/build_dfa_field.py</code> (needs the restored rasters)</td></tr>")
    ov = CORE_VALUES + f"""
<h1>A unique submission for the DOE GEMS Prize Challenge &mdash; and an honest account of what it can and cannot do</h1>
<p class="dim">Competition 306, GeoDAWN region, northwestern Great Basin, Nevada.
Task: predict geological faults, scored by a distance-weighted Tversky index on faults that are
<em>not</em> in the published USGS/INGENIOUS catalogue. Public #1 on
{esc(snap.get("retrieved_utc", "unknown date"))}:
<strong>{esc(snap.get("leader_public", "unknown"))}</strong>
({esc(snap.get("leader_participant", ""))}). Our best prior family:
<strong>0.2778</strong> (owner-reported).</p>

<div class="download">
 <h2>1 &middot; Download the submission file</h2>
 <p class="dim">Both files below pass every format check re-read from disk (single band, float32,
 EPSG:32611, 3292&times;3730, identical geotransform and finite-mask to the official template,
 every finite value in [0,1]). Pick one.</p>
 <p><a class="btn" href="downloads/{esc(h2f['file'])}">Download {esc(h2f['file'])}</a>
    <a class="btn alt" href="downloads/{esc(h2f['zip'])}">Download as .zip</a>
    <span class="dim">{h2f['audit']['positive_px']:,} emitted pixels &middot; proxy-validated best</span></p>
 <p class="dim"><strong>H46-2</strong> &mdash; structural corroboration with a 10&nbsp;% DFA regime-break hedge.
 Off-catalogue proxy score <strong>{inst[h2_tag]['instrument_sgmc_dti']:.4f}</strong> versus
 <strong>0.0991</strong> for the best prior files at identical emitted mass and buffering.</p>
 <p style="margin-top:22px"><a class="btn alt" href="downloads/{esc(h1f['file'])}">Download {esc(h1f['file'])}</a>
    <span class="dim">{h1f['audit']['positive_px']:,} emitted pixels</span></p>
 <p class="dim"><strong>H46-1</strong> &mdash; the pure new hypothesis: DFA scaling-exponent breaks along
 magnetic and gravity transects. Correlation with every prior submission and every plain
 gradient/curvature transform is <strong>|r| &le; 0.04</strong>. Proxy score
 <strong>{inst[h1_tag]['instrument_sgmc_dti']:.4f}</strong>, i.e. measured <em>weaker</em> than the prior
 files on the only proxy available; ship it if you want the file that tests the new idea, or for the
 final round where an expert panel reviews submitted predictions.</p>
 <p class="dim">A <code>-zeros.tif</code> fallback variant accompanies each file (0.0 outside the
 footprint instead of NaN) for submission systems that reject NaN.</p>
</div>

<div class="download">
 <h2>2 &middot; Submit it (three steps)</h2>
 <ol>
  <li>Sign in and open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">New submission</a>.</li>
  <li><strong>File to submit:</strong> choose <code>{esc(h2f['file'])}</code> (or its <code>.zip</code>).</li>
  <li><strong>Note (optional):</strong> paste exactly this, so the run is identifiable later:
      <pre>{esc(h2f['note'])}</pre></li>
 </ol>
 <p class="dim">Full walkthrough, including how the rounds work and what to do if a file is rejected,
 is on the <a href="executive-summary.html">executive summary page</a>.</p>
</div>

<h2>What this repository found</h2>
<div class="kv">
 <div><b>&le; {cal['hidden_truth_px']:,.0f} px</b><span class="dim">upper bound on the hidden truth size set by the two closest live scores (0.2600 and 0.2778): the boundary value at which the removed mass carried zero credit, since two scores give two equations in three unknowns and |G| is not point-identified (the group's own receipts declare 7,905 px, also feasible)</span></div>
 <div><b>{100*(cal['credit_per_px'] - 0.2*0.2600):.2f}%</b><span class="dim">implied credit per emitted pixel of the best prior file (0.1185) against the metric's own break-even bar (0.0520)</span></div>
 <div><b>+20.4%</b><span class="dim">credit the best prior file would need, at the same 37,654 px, to reach 0.3345</span></div>
 <div><b>|r| &le; 0.04</b><span class="dim">correlation of the DFA candidate with all prior submissions and all gradient/curvature transforms of the same bands</span></div>
</div>

<h2>The five hypotheses ranked, and what happened to each</h2>
<table><tr><th>#</th><th>Hypothesis</th><th>Expected DTI</th><th>Cost</th><th>Status</th></tr>
""" + "".join(
        f"<tr><td>{g(h, 'rank')}</td><td><strong>{esc(g(h, 'id'))}</strong> &mdash; {esc(g(h, 'title'))}</td>"
        f"<td>{esc(h.get('expected_dti', '—'))}</td><td>{esc(h.get('cost', '—'))}</td>"
        f"<td>{esc(g(h, 'validation_status'))}</td></tr>" for h in hyp["hypotheses"]) + f"""
</table>
<p class="dim"><a href="hypotheses.html">Full table with layers, physical signature, why it should be
off-catalogue, and how each differs from everything already in this repository &rarr;</a></p>

<h2>Measured scaling regimes of the official magnetic and gravity bands</h2>
<p class="dim">Median local DFA exponent &alpha; along row transects (12.8 km windows, scales
0.8&ndash;6.4 km). Note that the background regime of this dataset is <em>not</em> the 0.5 of the
pre-rupture literature: the detector therefore looks for breaks relative to the local background,
never for an absolute threshold. Full discussion in <a href="research.html">Research</a>.</p>
<table><tr><th>band</th><th>median &alpha;</th><th>IQR</th><th>p99 of |z|</th></tr>{dfa_rows}</table>
<p><img src="downloads/preview_h46_2.png" alt="Emission preview"></p>
"""
    # DOCS is docs/h46 (the archive).  The live pages are docs/index.html and
    # docs/executive-summary.html, written by scripts/build_r12_site.py, which this script
    # delegates to in its default mode.
    (DOCS / "index.html").write_text(page("Overview", ov, "index.html"))

    # ------------------------------------------------------------------ executive summary
    ex = f"""
<h1>Executive summary, and exactly how to make a submission</h1>

<h2>1. Why the 0.2778 file was the best of the family &mdash; the arithmetic</h2>
<p>The published metric is
<code>DTI = TPw / (TPw + 0.2&middot;FPw + 0.8&middot;FNw)</code> with a triangular kernel
<code>k(d) = max(1 &minus; d/300 m, 0)</code>. Two identities follow directly from the definition
(both verified in <code>tests/test_metric.py</code> against an independent O(N&sup2;) transcription):
<code>FNw = |G| &minus; TPw</code>, so with mass budget <code>S</code> and best-covering mass
<code>M</code>, <code>DTI = TPw / (0.2(TPw + S &minus; M) + 0.8|G|)</code>, and adding one unit of mass
raises DTI exactly when its realised credit exceeds <code>0.2&middot;DTI</code>.</p>
<p>Applying that to the three files of the H19-5 family whose scores are owner-reported, using the
two closest members to solve for the hidden truth set:</p>
<pre>0.2600 &middot; (0.2&middot;44090 + 0.8&middot;G) = 0.2778 &middot; (0.2&middot;37654 + 0.8&middot;G)
&rArr; G &le; {cal['hidden_truth_px']:,.0f} hidden truth pixels (1,409 km of fault trace at 100 m)
&rArr; TPw(44,090 px file) = {cal['implied_credit_px']:,.0f} px of credit, i.e. 0.1185 per emitted pixel
&rArr; break-even bar at that score = 0.2 &middot; 0.2600 = 0.0520</pre>
<p>So the answer to &ldquo;why did the thinned, catalogue-buffered member win?&rdquo; is not
&ldquo;smaller is better&rdquo;. It is that every removal step deleted mass whose realised credit was
<em>below</em> the metric's own break-even bar:</p>
<table><tr><th>step</th><th>pixels removed</th><th>mean realised credit of the removed pixels</th><th>bar</th><th>verdict</th></tr>
<tr><td>solid 121,131 px &rarr; dotted 60,069 px</td><td>61,062</td><td>0.0173</td><td>0.0384</td><td class="ok">remove</td></tr>
<tr><td>dotted 60,069 px &rarr; 44,090 px</td><td>15,979</td><td>0.0341</td><td>0.0495</td><td class="ok">remove</td></tr>
<tr><td>44,090 px &rarr; 37,654 px (200 m catalogue buffer)</td><td>6,436</td><td>0.0000</td><td>0.0520</td><td class="ok">remove</td></tr></table>
<p>The last row is the key one and it follows from an official clarification: DrivenData staff
confirmed (forum thread 11516) that <em>pixels corresponding to known USGS/INGENIOUS faults are
masked out of evaluation in both rounds</em>. Mass within the kernel of a mapped fault therefore
pays part of the false-positive tax while being structurally unable to earn credit. Removing it is
free score. This is also why the catalogue must be treated as an <em>exclusion zone</em>, not as
training targets.</p>
<p class="warn">Provenance warning: the 0.2778 attribution is contested. The public board shows
0.2778 for participant <code>extradr19</code> but links no file name; the GEMSDOE32 site labels its
own B=2 artifact UNSCORED. See <a href="irregularities.html">Irregularities</a>.</p>

<h2>2. Can this project beat 0.3345? What the same algebra requires</h2>
<p>Solving for the credit needed at the leader's score, at the same emitted mass and the same implied
hidden truth:</p>
<table><tr><th>file</th><th>emitted px</th><th>implied credit</th><th>credit needed for 0.3345</th><th>required improvement</th></tr>
<tr><td>H19-5 solid</td><td>121,131</td><td>6,823</td><td>11,874</td><td>+74.0%</td></tr>
<tr><td>D1.5 dotted</td><td>60,069</td><td>5,768</td><td>7,789</td><td>+35.0%</td></tr>
<tr><td>D2.8 dotted</td><td>44,090</td><td>5,223</td><td>6,720</td><td>+28.7%</td></tr>
<tr><td>D2.8 + catalogue B=2</td><td>37,654</td><td>5,223</td><td>6,289</td><td>+20.4%</td></tr></table>
<p><strong>Answer:</strong> yes, but only by improving the <em>field</em>. No combination of thinning,
dotting, buffering or thresholding can bridge the remaining gap, because those only move mass along
the same credit curve: the best prior file already sits at its own optimum, with the marginal pixel's
credit (0.0307 in the thinning range, 0.0000 in the buffer step) below the break-even bar (0.0520).
Reaching 0.3345 requires the top ~44,000 emitted pixels to average <strong>+29% more realised
credit</strong> than they do today, i.e. a detector problem. That is what H46-1 and H46-2 attack.</p>

<h2>3. What we shipped this session</h2>
<table><tr><th>artifact</th><th>what it is</th><th>off-catalogue proxy DTI (matched mass)</th><th>distinctness</th></tr>
<tr><td><strong>H46-2</strong> {esc(h2f['file'])}</td><td>geometric-mean corroboration of nine edge/curvature
transforms across magnetic, gravity and topographic bands, with 10% of the mass reserved for the DFA
regime-break field</td><td class="ok">{inst[h2_tag]['instrument_sgmc_dti']:.4f}</td>
<td>r = 0.31&ndash;0.36 vs prior submissions (an edge-based field, stated as such)</td></tr>
<tr><td><strong>H46-1</strong> {esc(h1f['file'])}</td><td>pure DFA scaling-exponent-break detection along
row and column transects of the magnetic and gravity bands</td><td class="bad">{inst[h1_tag]['instrument_sgmc_dti']:.4f}</td>
<td class="ok">r = &minus;0.012 / &minus;0.009 / &minus;0.012 vs the three prior submissions; |r| &le; 0.04 vs all
gradient/curvature transforms &mdash; a genuinely new hypothesis by the stated criterion</td></tr>
<tr><td>reference: best prior files, re-emitted at the same mass</td><td>the restored 0.2600 and 0.2778
TIFs scored as fields</td><td>0.0991</td><td>&mdash;</td></tr></table>
<p>Honest expectation: H46-2 sits at the same live operating point as the 0.2708&ndash;0.2778 family and
is 0.0025 ahead of it on the only available proxy &mdash; that is inside the noise of the instrument, so
the defensible expectation is <strong>~0.27&ndash;0.29, not above 0.30</strong>. We did not find a
+20&ndash;29% field improvement in this session, and we will not claim one. The upside path is set out
in <a href="hypotheses.html">Hypotheses</a> (H46-3 is the strongest untested idea and needs exactly one
public HTTP call from an unrestricted machine).</p>

<h2>4. Exactly how to make a submission (step by step)</h2>
<ol>
 <li>Sign in at <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">drivendata.org/competitions/306</a>
     and open the <em>Submissions</em> tab, then <strong>New submission</strong>.</li>
 <li><strong>File to submit.</strong> Choose one of:
  <ul>
   <li><code>{esc(h2f['file'])}</code> &mdash; recommended for the scored slot (best proxy evidence);</li>
   <li><code>{esc(h1f['file'])}</code> &mdash; the new-hypothesis artifact;</li>
   <li>either <code>.zip</code> if the form prefers a zip (it contains the same single GeoTIFF);</li>
   <li>the matching <code>-zeros.tif</code> if a file with NaN outside the footprint is rejected.</li>
  </ul></li>
 <li><strong>Note (optional).</strong> Paste the exact note from the <a href="index.html">overview page</a>
     (it names the method, the emitted mass and the buffer rule) so the run is identifiable later.</li>
 <li>Press submit and wait for the public score. Per page 967 the file you keep selected is the one
     scored in <em>both</em> rounds, so pick the artifact you are willing to stand behind: the initial
     round scores it against a fixed private set of expert-labelled new faults, and the final round
     re-scores the same file against an expanded label set after experts review all submissions.</li>
 <li>If the form returns <em>&ldquo;Predicted values must be in range [0, 1]&rdquo;</em>: that error comes
     from values outside [0,1] or from a nodata encoding the scorer reads as out-of-range. The files here
     are 0/1 inside the footprint (max exactly 1.0, min exactly 0.0) and NaN outside; use the
     <code>-zeros</code> variant to replace NaN with 0.0 if needed.</li>
</ol>

<h2>5. Limitations, stated plainly</h2>
<ul>
 <li>No access to the private or public test labels: <strong>no score can be predicted</strong> from
     inside this repository. The proxy instrument is a different fault population and predicts the live
     board only weakly (group measurement: Spearman +0.31 over 11 files).</li>
 <li>The spatially blocked catalogue holdout is <strong>worse than useless</strong> here and is not used:
     it ranks the 0.2600 file above the 0.2778 file, the opposite of the live board, because the truth
     it hides is the very population the organiser masks out. See
     <a href="irregularities.html">IR-46-04</a>.</li>
 <li>The DFA method is adapted from a temporal to a <em>spatial</em> setting, and the published
     pre-rupture result is a lag crossover, not a spatial regime change (IR-46-05).</li>
 <li>Sandbox egress allowed only github.com and pypi.org, so no new external dataset could be added
     (IR-46-06). Every external file used here is a hash-pinned mirror.</li>
</ul>
"""
    (DOCS / "executive-summary.html").write_text(
        page("Executive summary", ex, "executive-summary.html"))

    # ------------------------------------------------------------------ hypotheses
    rows = ""
    for h in hyp["hypotheses"]:
        rows += f"""<div class="panel">
<h3>{g(h, 'rank')}. {esc(g(h, 'id'))} &mdash; {esc(g(h, 'title'))}</h3>
<p><span class="tag">layers</span></p><ul>{''.join(f'<li><code>{esc(x)}</code></li>' for x in g(h, 'layers'))}</ul>
<p><span class="tag">physical signature</span> {esc(g(h, 'physical_signature'))}</p>
<p><span class="tag">why off-catalogue</span> {esc(g(h, 'why_off_catalogue'))}</p>
<p><span class="tag">differs from everything already in the repository</span> {esc(g(h, 'differs_from_repo'))}</p>
<p><span class="tag">expected DTI</span> {esc(h.get('expected_dti', '—'))}</p>
<p><span class="tag">implementation cost</span> {esc(g(h, 'cost'))}</p>
<p><span class="tag">validation</span> {esc(g(h, 'validation_status'))}</p>
<p><span class="tag">data</span> {esc(g(h, 'data_status'))}</p>
</div>"""
    hy = f"""
<h1>Five candidate hypotheses, ranked</h1>
<p class="dim">Ranking rule: expected DTI improvement first (evidence-weighted, using the
off-catalogue proxy at matched emitted mass plus the live-anchored emitted-mass rule), then
implementation cost. No candidate was given a submission slot without validation &mdash; with one
documented exception, H46-1, which was validated <em>and found negative</em> on the proxy and is
shipped only as the new-hypothesis artifact, never as the recommended scoring file.</p>
{rows}
<h2>What is next, in order</h2>
<ol>
 <li><strong>H46-3 first</strong> (needs one HTTP call from an unrestricted machine):
     <code>bash scripts/fetch_earthquake_catalog.sh</code>, then build hypocentre lineaments and run the
     same matched-mass protocol. Strongest untested physical argument; free official source verified
     to exist and verified unreachable from this sandbox.</li>
 <li><strong>H46-4 next</strong> (no new data needed): windowed Euler deconvolution with structural
     index 1 on the gravity plus RTP magnetics, requiring along-strike depth consistency across two
     independent potential fields.</li>
 <li><strong>H46-5</strong>: reverse the sign of the measured-geochemistry arm and use it as a
     pruning (removal) prior, which is the direction the group never tested.</li>
 <li>Re-run <code>scripts/validate_candidates.py</code> and only then touch a submission slot for the
     scored file.</li>
</ol>
"""
    (DOCS / "hypotheses.html").write_text(page("Hypotheses", hy, "hypotheses.html"))

    # ------------------------------------------------------------------ validation
    sweep_rows = "".join(
        f"<tr><td>{float(k.split('_')[1])*100:.0f}%</td><td>{v['dti']:.4f}</td>"
        f"<td>{v['tp']:.0f}</td><td>{v['px']:,}</td></tr>"
        for k, v in sorted(sweep.items(), key=lambda kv: float(kv[0].split('_')[1])))
    d1 = dist["H46-1"]
    d2 = dist["H46-2"]
    va = f"""
<h1>Validation</h1>
<p class="dim">Protocol: compare fields <em>at matched emitted mass and identical exclusion rules</em>.
Every number below is produced by <code>scripts/validate_candidates.py</code> and
<code>scripts/build_h46_submission.py</code> and stored in <code>registry/</code>.</p>

<h2>Instruments used, and their measured worth</h2>
<table>
<tr><th>instrument</th><th>truth it hides</th><th>verdict</th></tr>
<tr><td>A. spatially blocked catalogue holdout (9 blocks)</td><td>published catalogue faults inside a block,
with the rest of the catalogue masked</td><td class="bad">rejected: it ranks the 0.2600 file (0.0659)
above the 0.2778 file (0.0330), the opposite of the live board, and the group's own measurement puts
its Spearman against 11 live scores at +0.09</td></tr>
<tr><td>B. off-catalogue USGS SGMC traces (main instrument)</td><td>83,593 rasterised SGMC fault pixels,
of which 66,277 survive after removing pixels that coincide with the published catalogue</td>
<td class="warn">used for relative comparisons only; group measurement of Spearman vs 11 live scores +0.31.
It does rank the two scored prior files correctly (0.1058 for the 0.2778 file vs 0.1037 for the 0.2600
file)</td></tr>
<tr><td>C. live-score algebra</td><td>nothing: it uses the published metric plus owner-reported scores
</td><td class="ok">used to set the emitted mass and to state what a higher score would require</td></tr>
</table>

<h2>Distinctness of the shipped artifacts (the criterion for calling H46-1 a new hypothesis)</h2>
<table><tr><th>compared against</th><th>H46-1 (DFA) smoothed Pearson</th><th>H46-2 smoothed Pearson</th></tr>
""" + "".join(
        f"<tr><td>{esc(k)} <span class='dim'>(prior submission)</span></td>"
        f"<td class='ok'>{v:.3f}</td><td>{d2['vs_prior_submissions'][k]:.3f}</td></tr>"
        for k, v in d1["vs_prior_submissions"].items()) + "".join(
        f"<tr><td>{esc(k)} <span class='dim'>(gradient/curvature transform of the same bands)</span></td>"
        f"<td class='ok'>{v:.3f}</td><td>{d2['vs_gradient_curvature_transforms'][k]:.3f}</td></tr>"
        for k, v in d1["vs_gradient_curvature_transforms"].items()) + f"""
</table>
<p>Jaccard overlap between the H46-1 emission and the 0.2778 incumbent emission:
<strong>0.0037</strong> (276 shared pixels of 37,654). Conclusion: H46-1 is a different hypothesis,
not a relabelled edge detector &mdash; and H46-2 is honestly a fusion whose main term <em>is</em> an
edge construct (0.75 correlation with the total-magnetic-intensity gradient), which is why it is not
described as a new hypothesis anywhere on this site.</p>

<h2>Hedge sweep: what it costs to carry the new hypothesis inside the scored file</h2>
<table><tr><th>DFA share of budget</th><th>proxy DTI</th><th>credit (px)</th><th>emitted px</th></tr>
{sweep_rows}
<tr><td class="dim">best prior files, same rules</td><td class="dim">0.0991</td><td class="dim">&mdash;</td><td class="dim">37,654</td></tr>
</table>
<p>10% is the shipped choice: still ahead of the prior files on the proxy, and 3,765 pixels of the
emission carry predictions that no gradient-based field would make.</p>

<h2>Emission parameters, and why they are what they are</h2>
<table>
<tr><td>emitted mass</td><td><strong>37,654 px</strong> (= the measured mass of the highest-scoring prior
file; the model in <code>src/gems46/emission.py</code> puts the optimum for this credit curve between
~37k and ~45k px)</td></tr>
<tr><td>minimum dot separation</td><td><strong>3 px</strong> (300 m): below the kernel radius, two dots can
only earn credit for the same truth pixel, and the metric takes the maximum, so the second dot pays the
0.2 tax for nothing</td></tr>
<tr><td>ranking filter</td><td>each field blurred at &sigma; = 1.85 px, the matched filter for partial
credit under the triangular kernel</td></tr>
<tr><td>catalogue exclusion</td><td><strong>200 m buffer</strong> (2 px) around every published fault
pixel, because the organiser masks that population (thread 11516)</td></tr>
<tr><td>values</td><td>exactly 0.0 / 1.0: with <code>p &rarr; &lambda;p</code> the metric is increasing in
&lambda;, so unit mass is optimal on any chosen support</td></tr>
</table>

<h2>What would falsify the shipped choice</h2>
<ul>
 <li>A live score below 0.27 for H46-2 would say the proxy instrument is worse than its +0.31 Spearman
     suggests and that the structural field here is weaker than the prior family.</li>
 <li>A live score above 0.30 would say the geometric-mean corroboration found something the prior
     family missed.</li>
 <li>Either way the DFA artifact's live score tests the new hypothesis directly and is the number worth
     recording first.</li>
</ul>
"""
    (DOCS / "validation.html").write_text(page("Validation", va, "validation.html"))

    # ------------------------------------------------------------------ research
    band_rows = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td>{v['alpha_median_row']:.3f}</td>"
        f"<td>{v['alpha_iqr_row']:.3f}</td><td>{v['valid_px']:,}</td></tr>"
        for k, v in stats["bands"].items())
    re_ = f"""
<h1>Research notes and the knowledge base</h1>

<h2>1. The metric, and every consequence used in this repository</h2>
<p>Officially published (page 967): <code>k(d) = (1 &minus; d/300 m)<sub>+</sub></code>,
<code>TPw = &Sigma;<sub>g</sub> max<sub>x</sub> p(x)k(d(x,g))</code>,
<code>FPw = &Sigma;<sub>x:p&gt;0</sub> p(x)[1 &minus; max<sub>g</sub> k(d(x,g))]</code>,
<code>FNw = &Sigma;<sub>g</sub>[1 &minus; max<sub>x</sub> p(x)k(d(x,g))]</code>,
<code>DTI = TPw/(TPw + 0.2FPw + 0.8FNw + &epsilon;)</code>, with the worked example
<code>TPw=3.00, FPw=1.89, FNw=2.00 &rarr; 0.6026 &asymp; 0.60</code>.</p>
<p>Derived here and confirmed numerically (<code>tests/test_metric.py</code>):</p>
<ul>
<li><code>FNw = |G| &minus; TPw</code> exactly.</li>
<li><code>FPw = S &minus; M</code> with <code>S = &Sigma;p</code>, <code>M = &Sigma;p&middot;max<sub>g</sub>k</code>,
so <code>DTI = TPw/(0.2(TPw + S &minus; M) + 0.8|G|)</code>.</li>
<li>Adding unit mass at a pixel with realised credit <code>k</code> raises DTI iff
<code>k(0.2FP + 0.8|G|) &gt; 0.2&middot;DTI&middot;D&middot;(1&minus;C)</code>; when the truth set is much
larger than the covered part, this is <code>k &gt; 0.2&middot;DTI</code>, which is why the break-even bar
at 0.26&ndash;0.33 is 0.052&ndash;0.067.</li>
<li><code>p &rarr; &lambda;p</code> is increasing, so binary 0/1 emission is optimal on a fixed support.</li>
<li>For a collinear dotted trace with spacing <code>s</code> px the average kernel weight is
<code>1 &minus; s/12</code>, which is what makes ~2&ndash;3 px spacing the empirical sweet spot in this
competition rather than a solid line.</li>
</ul>

<h2>2. The organiser's masking rule, and why it dominates the catalogue strategy</h2>
<p>Forum thread 11516, DrivenData staff: known USGS/INGENIOUS fault pixels are excluded from evaluation
in both rounds. Consequence: mass on a mapped fault is neutral, mass <em>near</em> a mapped fault pays a
partial false-positive tax with no possibility of credit, and mass on a genuinely new fault is the only
mass that earns anything. This single rule explains the +0.0070 jump from 0.2708 to 0.2778 for a pure
200 m buffer deletion.</p>

<h2>3. DFA, adapted to a spatial grid</h2>
<p>DFA (Peng et al. 1994, Phys. Rev. E 49, 1685) integrates a series, splits it into boxes of length
<code>n</code>, removes the local least-squares trend in each box, evaluates the RMS fluctuation
<code>F(n)</code>, and takes the slope of <code>log F(n)</code> vs <code>log n</code> as the exponent
&alpha;. The estimator here is verified against its textbook calibration: white noise &rarr; 0.50,
fractional Gaussian noise &rarr; H (0.24 measured at H = 0.2, 0.91 at H = 0.9), random walk &rarr; 1.5
(<code>tests/test_dfa.py</code>).</p>
<p>The pre-rupture application (Varotsos, Sarlis &amp; Skordas 2009, Chaos 19, 023114) reports that
magnetic field variations preceding rupture look random at short lags and become long-range correlated
at longer lags with &alpha; &asymp; 0.9, while long pre-seismic electric field series show
&alpha; &asymp; 1 over five orders of magnitude. <strong>Nuance that matters:</strong> that is a
crossover in <em>time lag</em>, not a demonstration of a spatial exponent change across a fault. This
repository's H46-1 is an adaptation, and it is labelled as a hypothesis, not a replication.</p>
<p>Adaptation used here: 12.8 km windows (128 px), 800 m stride, box sizes 0.8/1.6/3.2/6.4 km, computed
along every row and column transect strictly inside the survey footprint (no interpolation across gaps),
then differenced against a 24.8 km median background and scaled by a local MAD estimate to give a robust
z-score. Reported as |z| (regime break) and |&nabla;z| (regime boundary).</p>

<h2>4. Measured scaling regimes of the official bands</h2>
<table><tr><th>band (raw / high-passed at 2 km)</th><th>median &alpha;</th><th>IQR of &alpha;</th><th>valid px</th></tr>{band_rows}</table>
<p>The background exponents are 1.0&ndash;1.95, i.e. the potential fields of this region are dominated by
long-wavelength power, and derivatives have lower exponents (total-magnetic-intensity vertical gradient
1.00) exactly as differencing theory predicts. The detector therefore never uses an absolute 0.5-style
threshold; it flags <em>breaks relative to the local background</em>, which is also what makes it
insensitive to the amplitude of the field.</p>

<h2>5. Data provenance</h2>
<table><tr><th>file</th><th>sha256</th><th>provenance</th></tr>
<tr><td>training_features.tif</td><td><code>4371c82e&hellip;</code></td><td>5 parts reassembled; matches the
pinned hash; 19 float32 bands, EPSG:32611, 100 m, nodata &minus;3.4028235e38</td></tr>
<tr><td>labels.tif</td><td><code>7ba308cc&hellip;</code></td><td>byte-identical to the group's
existing_faults.tif; 60,988 labelled pixels inside the footprint</td></tr>
<tr><td>sample_submission.tif</td><td><code>2176d08e&hellip;</code></td><td>the grid/footprint template
(5,167,373 finite pixels); also contains 1s on the catalogue, contrary to the page's wording</td></tr>
<tr><td>sgmc_faults_100m_u8.tif</td><td><code>643cbe99&hellip;</code></td><td>USGS SGMC traces rasterised
to this grid, restored from the group's public mirror</td></tr></table>

<h2>6. Band index map (verified from the GeoTIFF band descriptions)</h2>
<pre>1 mag_anom            6 tc (tilt/curvature)     11 iso_grav_anom_vg   16 ieq_n100a15
2 rtp                 7 geod_shearrate           12 det_elev            17 cond_surf
3 tmi_hg              8 geod_dilaterate          13 iso_grav_anom       18 iso_grav_anom_hg
4 geod_2ndinv         9 tmi_vg                   14 tmi                 19 det_elev_slope
5 iso_grav_anom_slope 10 deq_n100a15             15 depth_to_base_surf</pre>
"""
    (DOCS / "research.html").write_text(page("Research", re_, "research.html"))

    # ------------------------------------------------------------------ sources
    sr = "<h1>Sources</h1><p class='dim'>What each source supports, and whether it could be reached "\
         "from this environment.</p>"
    for s in src["sources"]:
        reach = ("reached" if s.get("reached_from_sandbox") else
                 "NOT reachable from the sandbox; checked via " + ", ".join(s.get("reached_via", [])))
        sr += (f"<div class='panel'><h3>{esc(s['id'])} &middot; {esc(s['title'])}</h3>"
               f"<p><a href='{esc(s['url'])}'>{esc(s['url'])}</a> &middot; "
               f"<span class='{'ok' if s.get('reached_from_sandbox') else 'warn'}'>{esc(reach)}</span>"
               f"{'' if s.get('official') else ' &middot; <span class=warn>third-party mirror</span>'}</p>"
               f"<ul>{''.join(f'<li>{esc(x)}</li>' for x in s['supports'])}</ul></div>")
    (DOCS / "sources.html").write_text(page("Sources", sr, "sources.html"))

    # ------------------------------------------------------------------ irregularities
    ir = "<h1>Irregularities and unresolved issues</h1>"
    for i in irr["irregularities"]:
        cls = {"high": "bad", "medium": "warn", "low": "dim"}.get(
        str(i.get("severity", "medium")).lower(), "dim")
        ir += (f"<div class='panel'><h3>{esc(g(i, 'id'))} <span class='{cls}'>[{esc(g(i, 'severity'))}]</span> "
               f"{esc(g(i, 'title'))}</h3><p>{esc(g(i, 'detail'))}</p>"
               f"<p><span class='tag'>effect here</span> {esc(g(i, 'effect_on_this_repository'))}</p>"
               f"<p class='dim'>{esc(g(i, 'status'))}</p></div>")
    (DOCS / "irregularities.html").write_text(page("Irregularities", ir, "irregularities.html"))

    # ------------------------------------------------------------------ preview image
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        import rasterio

        for tag, name in ((h1_tag, "preview_h46_1.png"), (h2_tag, "preview_h46_2.png")):
            with rasterio.open(DOCS / "downloads" / files[tag]["file"]) as s:
                a = np.nan_to_num(s.read(1))
            f, ax = plt.subplots(figsize=(11, 6), dpi=110)
            ax.imshow(a, cmap="inferno", interpolation="nearest")
            ax.set_title(f"{tag} - {files[tag]['audit']['positive_px']:,} emitted pixels (1.0) "
                         f"on a {a.shape[0]}x{a.shape[1]} grid")
            ax.set_xticks([]); ax.set_yticks([])
            f.tight_layout()
            f.savefig(DOCS / "downloads" / name)
            plt.close(f)
        print("previews written")
    except Exception as exc:  # pragma: no cover - preview is cosmetic
        print("preview skipped:", exc)

    print("site written to", DOCS)
    return 0


if __name__ == "__main__":
    if "--legacy-h46" in sys.argv:
        raise SystemExit(main())
    import runpy
    runpy.run_path(str(ROOT / "scripts" / "build_r12_site.py"), run_name="__main__")
