#!/usr/bin/env python3
"""Render ``registry/irregularities.json`` into ``docs/irregularities.html``.

The page used to be hand-maintained and had drifted (it stopped at IR-46-08 while the registry
carried thirteen entries).  Rendering it makes drift impossible: every panel on the page is an
entry in the JSON, and CI re-runs this script and fails if the page moves.
"""
from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / "registry/irregularities.json").read_text())

SEV = {"high": ("bad", "#b3261e"), "medium": ("warn", "#c88115"), "low": ("dim", "#526c66")}
CSS = ('body{margin:0;background:#f3f5f4;color:#172b29;font:16px/1.6 system-ui,sans-serif}'
       '.wrap{max-width:1000px;margin:auto;padding:32px 24px}h1{font-size:30px}'
       'header{background:#143f38;color:#fff;padding:14px 24px}header a{color:#c5ecdb;margin-right:14px}'
       '.panel{background:#fff;border:1px solid #d6dfdb;border-radius:10px;padding:18px;margin:16px 0}'
       '.panel h3{margin:0 0 6px;font-size:17px}.tag{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;'
       'color:#526c66;margin-right:10px}.bad{color:#b3261e;font-weight:700}.warn{color:#c88115;font-weight:700}'
       '.dim{color:#526c66}.panel p{margin:8px 0}.note{background:#fff9ea;border-left:5px solid #c88115;'
       'padding:16px;border-radius:8px}code{background:#edf3f0;padding:2px 4px;font-size:13px}'
       'footer{color:#526c66;font-size:13px;padding:20px 0}')


def main() -> None:
    c = Counter(i["severity"] for i in D["irregularities"])
    panels = []
    for i in D["irregularities"]:
        cls, colour = SEV.get(i["severity"], SEV["low"])
        panels.append(
            f'<div class="panel"><h3><span class="tag">{html.escape(i["id"])}</span>'
            f'<span class="{cls}">[{html.escape(i["severity"])}]</span> {html.escape(i["title"])}</h3>'
            f'<p>{html.escape(i["detail"])}</p>'
            f'<p><span class="tag">effect here</span> {html.escape(i.get("effect_on_this_repository", ""))}</p>'
            f'<p class="dim">{html.escape(i.get("status", ""))}</p></div>')
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Irregularities - GEMSDOE46</title><style>{CSS}</style></head>
<body><header><div class="wrap"><b>GEMSDOE46 · DOE GEMS Prize</b> ·
<a href="index.html">Overview and download</a><a href="executive-summary.html">Submission guide</a>
<a href="hypotheses.html">Hypotheses</a><a href="sources.html">Sources</a></div></header>
<div class="wrap"><h1>Irregularities and unresolved issues</h1>
<p>Everything on this page is an entry in <code>registry/irregularities.json</code>; the page is
generated from it by <code>scripts/build_irregularities_page.py</code>, so it cannot drift.
Counts: {c['high']} high · {c['medium']} medium · {c['low']} low, last updated {html.escape(D.get('updated_utc', ''))}.</p>
<div class="note"><b>How to read two tracks.</b> This registry (<code>registry/irregularities.json</code>,
rendered here) is the machine track, keyed by <code>IR-46-NN</code>. The older prose track in
<code>docs/IRREGULARITIES.md</code> uses the same prefix for a <i>different, historically numbered</i> list,
and <code>docs/HYPOTHESES.md</code> (H1–H5), <code>docs/research/hypotheses.md</code> (H46-1–H46-4) and
<code>registry/hypotheses.json</code> (H46-1–H46-5) are three further registers whose identifiers overlap
numerically. When an identifier matters, quote the file name as well as the id.</div>
{"".join(panels)}
<footer>Generated from registry/irregularities.json ·
<a href="https://github.com/buffedlizard55-lab/GEMSDOE46">source repository</a></footer></div>
</body></html>
'''
    (ROOT / "docs/irregularities.html").write_text(page)
    print(f"Wrote docs/irregularities.html ({len(D['irregularities'])} entries)")


if __name__ == "__main__":
    main()
