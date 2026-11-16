"""Side-by-side viewer: original page image | HTML produced by the VLM tier (+ facts, disagreements).

    python parser/showcase/build_viewer.py <work_dir> <out.html> 3 12 13 14 47 145 [--video QhkDOr6kmi4 ...]
Images are embedded as JPEG data URIs so the file is self-contained. Fragments are stripped of <script>/<style>/on*= .
"""
from __future__ import annotations

import base64
import html
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#d9d6cf;--accent:#a3122a;--ok:#1f7a4d}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--card:#202024;--ink:#ececef;--muted:#a0a0a8;--line:#3a3a40;--accent:#ff6b7f;--ok:#5fd39a}}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,system-ui,sans-serif}
header.top{padding:16px;border-bottom:1px solid var(--line)} h1{margin:0;font-size:20px} .sub{color:var(--muted)}
nav{display:flex;gap:6px;flex-wrap:wrap;padding:10px 16px} nav a{border:1px solid var(--line);border-radius:14px;padding:3px 10px;color:var(--ink);text-decoration:none}
.pg{margin:16px;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.pg>h2{margin:0;padding:10px 14px;font-size:15px;border-bottom:1px solid var(--line)} .why{color:var(--accent);font-weight:600}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)} @media(max-width:900px){.grid{grid-template-columns:1fr}}
.grid>div{padding:12px;min-width:0;overflow:auto} .grid img{width:100%;border:1px solid var(--line)}
.lbl{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:6px}
.out table{border-collapse:collapse;width:100%;font-size:12px;margin:6px 0} .out th,.out td{border:1px solid var(--line);padding:3px 5px;vertical-align:top;text-align:left}
.out th{background:color-mix(in srgb,var(--accent) 14%,transparent)} .out figure{margin:8px 0;padding:8px;border:1px dashed var(--line);border-radius:6px}
.out figcaption{font-style:italic;color:var(--muted)} .out .cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.out header,.out footer{color:var(--muted);font-size:12px} .out h1{font-size:18px}
details{padding:0 14px 12px} summary{cursor:pointer;color:var(--muted)} .dis{color:var(--accent)} .ok{color:var(--ok)}
ul.f{margin:6px 0;padding-left:18px;font-size:12px}
"""


def clean(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", fragment)
    return re.sub(r"(?i)\son\w+\s*=\s*(\"[^\"]*\"|'[^']*')", "", fragment)


def img_uri(path: Path, width: int = 1000) -> str:
    im = Image.open(path).convert("RGB")
    im.thumbnail((width, width * 2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


WHY = {3: "TOC: photos without captions, printed page = PDF page − 2", 12: "Ingredient table: 25/50 servings × weight/measure, merged headers",
       13: "Table continuation: '⅛ cup' is 'V cup' in the text layer; nutrients block", 14: "Full-bleed photo with overlaid text",
       47: "Nutrition Facts label is a photo inside the page", 145: "Food-safety page: every temperature/time"}


def main(work: Path, out: Path, pages: list[int], videos: list[str]) -> None:
    secs, nav = [], []
    for n in pages:
        j = json.loads((work / "json" / f"p{n:03d}.json").read_text(encoding="utf-8"))
        frag = clean((work / "html" / f"p{n:03d}.html").read_text(encoding="utf-8"))
        dis = j.get("disagreements") or []
        nav.append(f'<a href="#p{n}">p.{n}</a>')
        secs.append(f"""<section class="pg" id="p{n}"><h2>PDF p.{n} · {html.escape(j.get('type') or '')} · {html.escape(j.get('recipe') or '')}
 — <span class="why">{html.escape(WHY.get(n, ''))}</span></h2>
<div class="grid"><div><div class="lbl">Original page</div><img alt="PDF page {n}" src="{img_uri(work / 'pages' / f'p{n:03d}.png')}"></div>
<div class="out"><div class="lbl">Generated HTML (VLM tier)</div>{frag}</div></div>
<details><summary>{len(j.get('facts', []))} atomic facts · <span class="{'dis' if dis else 'ok'}">{len(dis)} text-layer disagreements</span> · confidence {html.escape(str(j.get('confidence')))}</summary>
<ul class="f">{''.join(f'<li class=dis>{html.escape(d.get("where",""))}: image <b>{html.escape(str(d.get("image")))}</b> vs text layer <b>{html.escape(str(d.get("text_layer")))}</b></li>' for d in dis)}
{''.join(f'<li>{html.escape(f)}</li>' for f in j.get('facts', [])[:40])}</ul></details></section>""")
    for vid in videos:
        vdir = work / "video" / vid
        v = json.loads((vdir / "video.json").read_text(encoding="utf-8"))
        shots = [s for s in v.get("segments", []) if s.get("frames")][:6]
        thumbs = "".join(f'<figure><img alt="frame" src="{img_uri(vdir / "frames" / s["frames"][0], 480)}"><figcaption>{s.get("t0")}s · '
                         f'{html.escape(" / ".join(s.get("on_screen_text") or []) or (s.get("visual") or "")[:80])}</figcaption></figure>' for s in shots)
        nav.append(f'<a href="#v{vid}">video {vid}</a>')
        secs.append(f"""<section class="pg" id="v{vid}"><h2>Video · {html.escape(v.get('title') or vid)} — <span class="why">timestamps, on-screen text, speech</span></h2>
<div class="grid"><div class="out"><div class="lbl">Keyframes (scene change) + corrected on-screen text</div>{thumbs}</div>
<div class="out"><div class="lbl">Generated HTML (video agent)</div>{clean((vdir / 'video.html').read_text(encoding='utf-8'))}</div></div></section>""")
    out.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hard Pages Viewer</title><style>{CSS}</style></head><body>
<header class="top"><h1>Hard pages → HTML</h1><div class="sub">USDA <i>Recipes for Healthy Kids: Cookbook for Child Care Centers</i> (2013, public domain) and USDA Team Nutrition videos.
Left: original. Right: layout-preserving HTML written by Sonnet 5.5 / Haiku 5.5 agents, numbers cross-checked against the decoded PDF text layer.</div></header>
<nav>{''.join(nav)}</nav>{''.join(secs)}</body></html>""", encoding="utf-8")
    print(out, round(out.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    args = sys.argv[1:]
    vids = args[args.index("--video") + 1:] if "--video" in args else []
    nums = [int(a) for a in (args[2:args.index("--video")] if "--video" in args else args[2:])]
    main(Path(args[0]), Path(args[1]), nums, vids)
