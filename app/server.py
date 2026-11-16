"""Local chat server for the Kitchen KB agent (stdlib only).

    python app/server.py            # http://127.0.0.1:8780   (binds to localhost only)

GET  /                     chat UI (app/static/index.html)
POST /api/upload           {"name": "...", "data": "<base64>"} -> {"id": "<hex12>.<ext>"}  (image/audio, <= 15 MB)
POST /api/chat             {"session": "...", "text": "...", "attachments": [...]} -> Server-Sent Events, one per trace event
GET  /media/page/<n>       page image for citation previews        GET /media/frame/<vid>/<f_###>  video keyframe
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")                 # models are cached on T7; no hub calls at runtime
os.environ.setdefault("HF_HOME", "/Volumes/T7 Dev/AI20K/day6/hf_cache")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import agent as A  # noqa: E402
import tools as T  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
EXT = {"png", "jpg", "jpeg", "webp", "wav", "webm", "m4a", "mp3", "ogg"}
SESSIONS: dict[str, A.Session] = {}
MAX_UPLOAD = 15 * 1024 * 1024


def _thumb(cid: str | None, meta: dict | None = None) -> dict | None:
    """Map an evidence id (or a hit's metadata) to a small viewable image URL for the trace panel."""
    meta = meta or {}
    cid = cid or ""
    m = re.match(r"(?:img:)?yt:([A-Za-z0-9_-]{11})[@:]?(\d+)?", cid)
    if m and (m.group(2) or meta.get("t") is not None or meta.get("t0") is not None):
        t = int(m.group(2) if m.group(2) else (meta.get("t") if meta.get("t") is not None else meta.get("t0")))
        return {"url": f"/media/still/{m.group(1)}/{t}", "label": f"{t // 60}:{t % 60:02d}", "href": f"https://youtu.be/{m.group(1)}?t={t}"}
    m = re.match(r"img:cookbook:fig:x(\d+)", cid)
    if m:
        pg = meta.get("pdf_page")
        return {"url": f"/media/figure/x{m.group(1)}", "label": f"hình · tr.{pg}" if pg else "hình", "href": f"/media/figure/x{m.group(1)}"}
    m = re.match(r"(?:img:)?cookbook:p(\d{3})", cid)
    pg = int(m.group(1)) if m else meta.get("pdf_page")
    if pg:
        return {"url": f"/media/page/{pg}", "label": f"tr.{pg}", "href": f"/media/page/{pg}"}
    return None


def thumbs_for(tool: str, result, inp: dict | None = None) -> list[dict]:
    out, seen = [], set()
    def add(t):
        if t and t["url"] not in seen and len(out) < 6:
            seen.add(t["url"]); out.append(t)
    if not isinstance(result, dict):
        return out
    if tool == "view_candidates" and inp:
        add({"url": f"/media/upload/{inp.get('attachment_id')}", "label": "ảnh của bạn", "href": f"/media/upload/{inp.get('attachment_id')}"})
        for c in result.get("candidates", []):
            add(_thumb(c.get("candidate")))
    elif tool in ("analyze_attachment", "search_images", "search_kb"):
        mt = result.get("match") or {}
        if mt.get("cite"):
            add(_thumb(mt["cite"], mt))
        for h in (result.get("hits") or result.get("results") or [])[:5]:
            if tool == "search_kb" and not (h.get("pdf_page") or h.get("t") is not None):
                continue
            add(_thumb(h.get("id") if str(h.get("id", "")).startswith("img:") else h.get("cite"), h))
    elif tool == "get_page":
        add(_thumb(result.get("cite")))
    elif tool == "get_video_segment":
        seg = result.get("segment") or {}
        add(_thumb(result.get("cite"), {"t0": seg.get("t0")}))
    elif tool == "get_recipe":
        add(_thumb(result.get("cite")))
    return [t for t in out if t]


def ui_event(ev: dict) -> dict:
    """Trim observations for the browser (full results stay in the trace file); attach thumbnails of what was seen."""
    ev = {k: v for k, v in ev.items() if k not in ("session",)}
    if ev.get("type") == "observation":
        try:
            ev["thumbs"] = thumbs_for(ev.get("tool"), ev.get("result"), ev.get("input"))
        except Exception:
            ev["thumbs"] = []
        s = json.dumps(ev["result"], ensure_ascii=False, default=str)
        ev["preview"] = s[:1500]
        ev.pop("result")
    return ev


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        if self.path == "/api/pages":
            return self._json(200, pages_index())
        m = re.fullmatch(r"/api/page/(\d{1,3})", self.path)
        if m and 1 <= int(m.group(1)) <= 148:
            n = int(m.group(1))
            j = json.loads((T.WORK / "json" / f"p{n:03d}.json").read_text(encoding="utf-8"))
            return self._json(200, {"html": clean((T.WORK / "html" / f"p{n:03d}.html").read_text(encoding="utf-8")),
                                    "facts": j.get("facts", []), "disagreements": j.get("disagreements", []),
                                    "illegible": j.get("illegible", []), "confidence": j.get("confidence")})
        m = re.fullmatch(r"/api/video/(QhkDOr6kmi4|eSKtPtW0X2o)", self.path)
        if m:
            d = T.WORK / "video" / m.group(1)
            v = json.loads((d / "video.json").read_text(encoding="utf-8"))
            return self._json(200, {"html": clean((d / "video.html").read_text(encoding="utf-8")), "meta": {k: v.get(k) for k in ("video_id", "title", "url", "duration_s", "speech")},
                                    "segments": [{**{k: s.get(k) for k in ("t0", "t1", "link", "topic", "on_screen_text", "visual")}, "frame": (s.get("frames") or [None])[0]} for s in v.get("segments", [])],
                                    "corrections": v.get("corrections", []), "stt_vs_captions": v.get("stt_vs_captions", [])[:25], "facts": v.get("facts", [])})
        if self.path == "/api/inventory":
            return self._json(200, inventory())
        if self.path == "/api/methods":
            import retrieval as R
            return self._json(200, {"methods": R.METHODS, "image_backends": {"fusion": "Ảnh: CLIP + EmbeddingGemma 2 + OCR + hash (mặc định)",
                                                                          "gemma": "Ảnh: EmbeddingGemma 2 + OCR + hash",
                                                                          "clip": "Ảnh: CLIP + tiles + OCR + hash"}})
        if self.path == "/api/graph":
            return self._json(200, graph())
        if self.path == "/api/pipeline":
            return self._json(200, pipeline_stats())
        m = re.fullmatch(r"/media/page/(\d{1,3})", self.path)
        if m and 1 <= int(m.group(1)) <= 148:
            return self._send(200, (T.WORK / "pages" / f"p{int(m.group(1)):03d}.png").read_bytes(), "image/png")
        if self.path.split("#")[0] == "/media/pdf":           # the original source PDF (for side-by-side checking)
            return self._send(200, (T.WORK.parent / "raw" / "pdf" / "cookbook_child_care.pdf").read_bytes(), "application/pdf")
        m = re.fullmatch(r"/api/verify/(\d{1,3})", self.path)
        if m:                                                  # per-page number cross-check (parser/verify_numbers.py)
            pg = next((p for p in json.loads((T.WORK / "verify" / "numbers.json").read_text())["pages"] if p["pdf_page"] == int(m.group(1))), {})
            return self._json(200, pg)
        m = re.fullmatch(r"/media/still/(QhkDOr6kmi4|eSKtPtW0X2o)/(\d{1,4})", self.path)
        if m:                                   # the real frame at second t (poster for an embedded video moment)
            vid, t = m.group(1), int(m.group(2))
            out = T.WORK / "stills" / f"{vid}_{t}.jpg"
            if not out.exists():
                import subprocess
                out.parent.mkdir(exist_ok=True)
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i",
                                str(T.WORK.parent / "raw" / "video" / f"{vid}.mp4"), "-frames:v", "1", "-vf", "scale=640:-2",
                                "-q:v", "4", str(out)], timeout=20)
            if out.exists():
                return self._send(200, out.read_bytes(), "image/jpeg")
        m = re.fullmatch(r"/media/figure/x(\d{1,6})", self.path)
        if m and (T.WORK / "pdf_figures" / f"x{m.group(1)}.png").exists():
            return self._send(200, (T.WORK / "pdf_figures" / f"x{m.group(1)}.png").read_bytes(), "image/png")
        m = re.fullmatch(r"/media/upload/([a-f0-9]{12}\.(?:png|jpg|jpeg|webp))", self.path)
        if m and (T.UPLOADS / m.group(1)).exists():
            ext = m.group(1).rsplit(".", 1)[1].replace("jpg", "jpeg")
            return self._send(200, (T.UPLOADS / m.group(1)).read_bytes(), f"image/{ext}")
        m = re.fullmatch(r"/media/frame/(QhkDOr6kmi4|eSKtPtW0X2o)/(f_\d{3})", self.path)
        if m:
            f = T.WORK / "video" / m.group(1) / "frames" / f"{m.group(2)}.jpg"
            if f.exists():
                return self._send(200, f.read_bytes(), "image/jpeg")
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD * 1.4:
            return self._json(413, {"error": "too large"})
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})
        if self.path == "/api/upload":
            ext = (body.get("name") or "").rsplit(".", 1)[-1].lower()
            if ext not in EXT:
                return self._json(400, {"error": f"file type .{ext} not allowed"})
            data = base64.b64decode(body.get("data") or "", validate=False)
            if not data or len(data) > MAX_UPLOAD:
                return self._json(400, {"error": "empty or too large"})
            T.UPLOADS.mkdir(parents=True, exist_ok=True)
            fid = f"{secrets.token_hex(6)}.{ext}"
            (T.UPLOADS / fid).write_bytes(data)
            return self._json(200, {"id": fid})
        if self.path == "/api/chat":
            sid = re.sub(r"[^a-f0-9]", "", body.get("session") or "")[:10] or None
            sess = SESSIONS.get(sid) if sid else None
            if sess is None:
                sess = A.Session(sid)
                SESSIONS[sess.id] = sess
            atts = [a for a in body.get("attachments") or [] if re.fullmatch(r"[a-f0-9]{12}\.[a-z0-9]{2,4}", a)]
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(f"data: {json.dumps({'type': 'session', 'id': sess.id})}\n\n".encode())
            for ev in sess.turn(str(body.get("text") or ""), atts, method=str(body.get("method") or "dense_gemma"),
                                image_backend=str(body.get("image_backend") or "fusion")):
                self.wfile.write(f"data: {json.dumps(ui_event(ev), ensure_ascii=False, default=str)}\n\n".encode())
                self.wfile.flush()
            return
        self._json(404, {"error": "not found"})


def clean(fragment: str) -> str:
    fragment = re.sub(r"(?is)<(script|style|iframe|object|embed)[^>]*>.*?</\1>", "", fragment)
    fragment = re.sub(r"(?i)\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", fragment)
    return re.sub(r"(?i)(href|src)\s*=\s*([\"'])\s*javascript:[^\"']*\2", r'\1="#"', fragment)


HARD = {3: "Mục lục: ảnh không chú thích, số trang in lệch 2", 12: "Bảng nguyên liệu 25/50 suất, ô gộp", 13: "'V cup' trong text layer = ⅛ cup",
        14: "Ảnh full-bleed có chữ đè", 47: "Nhãn Nutrition Facts là ảnh", 145: "Trang an toàn thực phẩm: mọi nhiệt độ/thời gian",
        64: "Kích thước khay 20 ⅞” x 17 ⅜” bị mã hoá Y/W", 4: "Text layer trộn danh sách giám khảo"}


def pages_index() -> list[dict]:
    man = json.loads((T.WORK / "manifest.json").read_text(encoding="utf-8"))
    ver = {p["pdf_page"]: len(p["mismatches"]) for p in json.loads((T.WORK / "verify" / "numbers.json").read_text())["pages"]}
    out = []
    for r in man:
        n = r["pdf_page"]
        j = json.loads((T.WORK / "json" / f"p{n:03d}.json").read_text(encoding="utf-8"))
        out.append({"n": n, "printed": r["printed_page"], "type": j.get("type") or r["type"], "recipe": r["recipe"],
                    "category": j.get("category") or r["category"], "tier": r["tier"], "facts": len(j.get("facts", [])),
                    "disagreements": len(j.get("disagreements", [])), "mismatch": ver.get(n, 0),
                    "confidence": j.get("confidence"), "hard": HARD.get(n)})
    return out


def inventory() -> dict:
    W = T.WORK
    with T.M._conn() as c:
        units = dict(c.execute("SELECT kind, count(*) FROM kb_cook GROUP BY 1").fetchall())
        images = dict(c.execute("SELECT kind, count(*) FROM kb_image GROUP BY 1").fetchall())
        edges = dict(c.execute("SELECT rel, count(*) FROM kg_edges GROUP BY 1").fetchall())
    recipes = json.loads((W / "kb" / "recipes.json").read_text(encoding="utf-8"))
    ing: dict = {}
    for name, r in recipes.items():
        for i in r["ingredients"]:
            e = ing.setdefault(i["key"], {"ingredient": i["key"], "recipes": {}, "names": set()})
            e["names"].add(i["name"])
            e["recipes"].setdefault(name, {"pdf_page": i.get("pdf_page"), "m25": i.get("m25", ""), "w25": i.get("w25", ""),
                                           "m50": i.get("m50", ""), "w50": i.get("w50", ""),
                                           # video recipes: quantity as printed on the on-screen card + the second it appears
                                           "card": i["name"] if "t" in i else None, "t": i.get("t"),
                                           "video": (r.get("videos") or [None])[0] if "t" in i else None})
    ingredients = sorted(({"ingredient": k, "names": sorted(v["names"]), "n_recipes": len(v["recipes"]),
                           "recipes": [{"recipe": rn, **d} for rn, d in sorted(v["recipes"].items())]} for k, v in ing.items()),
                         key=lambda x: (-x["n_recipes"], x["ingredient"]))
    vids = []
    for vj in sorted((W / "video").glob("*/video.json")):
        v = json.loads(vj.read_text(encoding="utf-8"))
        meta = json.loads((vj.parent / "meta.json").read_text(encoding="utf-8"))
        vids.append({"id": v["video_id"], "title": v.get("title"), "url": v.get("url"), "seconds": meta.get("duration"),
                     "stt_segments": len(json.loads((vj.parent / "stt.json").read_text())), "captions": len(json.loads((vj.parent / "captions.json").read_text())),
                     "frames": len(list((vj.parent / "frames").glob("f_*.jpg"))), "text_frames": len(json.loads((vj.parent / "ocr.json").read_text())),
                     "segments": len(v.get("segments", [])), "facts": len(v.get("facts", [])), "corrections": len(v.get("corrections", []))})
    pk = W / "kb" / "packages"
    ver = json.loads((W / "verify" / "numbers.json").read_text())["totals"]
    fp = json.loads((W / "audio" / "fp_eval.json").read_text())["summary"] if (W / "audio" / "fp_eval.json").exists() else {}
    return {"sources": [{"id": "cookbook", "title": "Recipes for Healthy Kids: Cookbook for Child Care Centers (USDA FNS, 2013)",
                         "url": "https://www.govinfo.gov/app/details/GOVPUB-A98-PURL-gpo47594", "license": "US government work, public domain (17 U.S.C. §105)",
                         "pages": 148, "sha256": "35139387…fe5d"}] + [{"id": f"yt:{v['id']}", "title": v["title"], "url": v["url"],
                         "license": "USDA FNS video (US government work)", "seconds": v["seconds"]} for v in vids],
            "videos": vids, "stores": {"kb_cook (bge-small 384d + full-text)": units, "kb_image (CLIP ViT-B/32 512d)": images,
                                       "kg_edges (graph)": edges, "audio fingerprint": {"hashes": 29427 + 84829}},
            "verification": ver, "fingerprint_eval": fp,
            "packages": {"wiki": len(list((pk / "wiki").glob("*.md"))), "sop": (pk / "sop_food_safety.md").exists(),
                         "faq": len(json.loads((pk / "faq.json").read_text())), "glossary": (pk / "glossary.md").exists()},
            "recipes": [{"recipe": k, "category": r["category"], "award": r["award"], "ingredients": len(r["ingredients"]),
                         "allergens": sorted(r["allergens"]), "pages": [p["pdf_page"] for p in r["pages"]],
                         "videos": r.get("videos", [])} for k, r in sorted(recipes.items())],
            "ingredients": ingredients}


def graph() -> dict:
    """Whole knowledge graph for the Graph tab: typed nodes + edges, each edge with its evidence source."""
    with T.M._conn() as c:
        rows = c.execute("SELECT s, rel, o, attrs, source FROM kg_edges").fetchall()
    recipes = json.loads((T.WORK / "kb" / "recipes.json").read_text(encoding="utf-8"))
    titles = {r[0]: r[2] for r in rows if r[1] == "is_video"}
    nodes: dict = {}

    def node(key: str, typ: str, label: str) -> str:
        nid = f"{typ}:{key}"
        nodes.setdefault(nid, {"id": nid, "type": typ, "label": label})
        return nid
    for name, r in recipes.items():
        nodes[node(name, "recipe", name)].update(category=r["category"], award=r.get("award"),
                                       pages=[p["pdf_page"] for p in r["pages"]], videos=r.get("videos", []))
    edges = []
    ing_page = {(s, (a or {}).get("name")): src for s, rel, o, a, src in rows if rel == "has_ingredient"}
    first_page = {}
    for (s, _), src in sorted(ing_page.items(), key=lambda x: x[1]):
        first_page.setdefault(s, src)
    for s, rel, o, attrs, src in rows:
        if not src.startswith(("cookbook:", "yt:")):      # derived edge -> cite the ingredient-table row it came from
            src = next((ing_page[(s, n)] for n in (attrs or {}).get("via", []) if (s, n) in ing_page), first_page.get(s, src))
        if rel == "is_video":
            node(s, "video", titles.get(s, s))
            continue
        if rel == "demonstrates":
            a, b = node(s, "video", titles.get(s, s)), node(o, "recipe", o)
        else:
            typ = {"has_ingredient": "ingredient", "in_category": "category", "contains_allergen": "allergen", "ccp_temp_F": "temp"}[rel]
            a, b = node(s, "recipe", s), node(o, typ, f"{o} °F" if typ == "temp" else o)
        edges.append({"source": a, "target": b, "rel": rel, "cite": src,
                      "detail": {k: v for k, v in (attrs or {}).items() if k in ("name", "w25", "m25", "w50", "m50", "via", "evidence", "text")}})
    deg: dict = {}
    for e in edges:
        for k in (e["source"], e["target"]):
            deg[k] = deg.get(k, 0) + 1
    for n in nodes.values():
        n["degree"] = deg.get(n["id"], 0)
    return {"nodes": list(nodes.values()), "edges": edges}


def pipeline_stats() -> dict:
    """Every number the Pipeline tab charts, read from the artifacts each stage wrote (nothing hard-coded)."""
    from collections import Counter
    W = T.WORK
    man = json.loads((W / "manifest.json").read_text())
    pages = {int(f.stem[1:]): json.loads(f.read_text()) for f in (W / "json").glob("p*.json")}
    ptype = Counter((pages[r["pdf_page"]].get("type") or r["type"]) for r in man)
    tier = Counter(r["tier"] for r in man)
    facts_by_tier = Counter()
    dis_by_type = Counter()
    for r in man:
        p = pages[r["pdf_page"]]
        facts_by_tier[r["tier"]] += len(p.get("facts", []))
        dis_by_type[p.get("type") or r["type"]] += len(p.get("disagreements", []))
    glyph = Counter()
    for p in pages.values():
        for d in p.get("disagreements", []):
            m = re.search(r"\b([KLMNOVWXY])\b", str(d.get("text_layer", "")))
            if m:
                glyph[m.group(1)] += 1
    ver = json.loads((W / "verify" / "numbers.json").read_text())["totals"]
    vids = []
    for vj in sorted((W / "video").glob("*/video.json")):
        d = vj.parent
        v = json.loads(vj.read_text())
        dense = json.loads((d / "dense.json").read_text()) if (d / "dense.json").exists() else []
        vids.append({"id": v["video_id"], "title": v.get("title"), "seconds": json.loads((d / "meta.json").read_text()).get("duration"),
                     "stt": len(json.loads((d / "stt.json").read_text())), "captions": len(json.loads((d / "captions.json").read_text())),
                     "keyframes": len(list((d / "frames").glob("f_*.jpg"))), "keyframes_text": len(json.loads((d / "ocr.json").read_text())),
                     "dense": len(dense), "dense_text": sum(bool(x["ocr"]) for x in dense), "segments": len(v.get("segments", [])),
                     "facts": len(v.get("facts", [])), "corrections": len(v.get("corrections", [])), "stt_vs_captions": len(v.get("stt_vs_captions", []))})
    with T.M._conn() as c:
        units = dict(c.execute("SELECT kind, count(*) FROM kb_cook GROUP BY 1").fetchall())
        images = dict(c.execute("SELECT kind, count(*) FROM kb_image GROUP BY 1").fetchall())
        edges = dict(c.execute("SELECT rel, count(*) FROM kg_edges GROUP BY 1").fetchall())
    pk = W / "kb" / "packages"
    faq = Counter(x.get("type") for x in json.loads((pk / "faq.json").read_text()))
    fp = json.loads((W / "audio" / "fp_eval.json").read_text())["summary"]
    img = json.loads((W / "queries" / "image_eval.json").read_text()) if (W / "queries" / "image_eval.json").exists() else {}
    turns = []                                     # agent traces: cost, latency, cache share, tool calls
    for f in (W / "traces").glob("*.jsonl"):
        for l in f.read_text(encoding="utf-8").splitlines():
            e = json.loads(l)
            if e.get("type") == "final" and e.get("tokens") is not None:
                turns.append(e)
    live = [t for t in turns if not t.get("cached")]
    tool_use = Counter()
    for f in (W / "traces").glob("*.jsonl"):
        for l in f.read_text(encoding="utf-8").splitlines():
            e = json.loads(l)
            if e.get("type") == "action":
                tool_use[e["tool"]] += 1
    def med(xs):
        xs = sorted(x for x in xs if x is not None)
        return xs[len(xs) // 2] if xs else None
    return {"pages": {"total": len(man), "by_type": dict(ptype), "by_tier": dict(tier), "facts_by_tier": dict(facts_by_tier),
                      "disagreements_by_type": dict(dis_by_type), "glyphs": dict(glyph)},
            "verify": ver, "videos": vids, "units": units, "images": images, "edges": edges,
            "packages": {"wiki": len(list((pk / "wiki").glob("*.md"))), "faq_by_type": dict(faq), "faq": sum(faq.values()),
                         "glossary": len(re.findall(r"^##+ ", (pk / "glossary.md").read_text(), re.M)) if (pk / "glossary.md").exists() else 0},
            "fingerprint": fp, "image_eval": {k: img.get(k) for k in ("baseline_2s", "new_2s", "new_5s", "right_video", "n")},
            "agent": {"turns": len(turns), "cached_turns": len(turns) - len(live), "median_cost": med([t.get("cost_usd") for t in live]),
                      "median_seconds": med([t.get("seconds") for t in live]), "median_steps": med([t.get("steps") for t in live]),
                      "cache_read_share": round(sum(t.get("cache_read_tokens") or 0 for t in live) / max(1, sum(t.get("tokens") or 0 for t in live)), 2),
                      "abstained": sum(bool(t.get("abstained")) for t in turns), "tool_use": dict(tool_use)}}


def warm() -> None:
    T.search_kb("warm up")          # loads EmbeddingGemma 2 (default text method) + DB
    T.search_images("warm up")      # loads CLIP


if __name__ == "__main__":
    warm()
    port = int(os.environ.get("PORT", 8780))
    print(f"Kitchen KB agent on http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
