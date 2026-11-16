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
        if self.path == "/api/vectors/summary":
            return self._json(200, vectors_summary())
        if self.path.startswith("/api/vectors"):
            from urllib.parse import parse_qs, urlparse
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/api/vectors/nn":
                    return self._json(200, vectors_nn(qs.get("table", ""), qs.get("id", "")))
                if u.path == "/api/vectors" and qs.get("table") == "audio_fingerprint":
                    return self._json(200, fingerprint_rows(qs.get("kind", ""), qs.get("q", ""), int(qs.get("offset", 0) or 0)))
                if u.path == "/api/vectors":
                    return self._json(200, vectors_rows(qs.get("table", ""), qs.get("kind", ""), qs.get("q", ""),
                                                        int(qs.get("offset", 0) or 0)))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
        m = re.fullmatch(r"/media/audio/(QhkDOr6kmi4|eSKtPtW0X2o)/(\d{1,4})", self.path)
        if m:                                   # the 5-second window an audio embedding was computed from
            vid, t = m.group(1), int(m.group(2))
            out = T.WORK / "stills" / f"{vid}_{t}.m4a"
            if not out.exists():
                import subprocess
                out.parent.mkdir(exist_ok=True)
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-t", "5", "-i",
                                str(T.WORK.parent / "raw" / "video" / f"{vid}.mp4"), "-vn", "-c:a", "aac", "-b:a", "96k", str(out)], timeout=20)
            if out.exists():
                return self._send(200, out.read_bytes(), "audio/mp4")
        if self.path == "/api/compare/meta":
            import compare as CMP
            return self._json(200, CMP.meta())
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
        if self.path == "/api/compare":
            import compare as CMP
            try:
                return self._json(200, CMP.run(str(body.get("corpus") or ""), body.get("qid") or None, body.get("text"),
                                               [str(m) for m in body.get("methods") or []][:8], int(body.get("k") or 5),
                                               bool(body.get("no_pkg", True))))
            except ValueError as e:
                return self._json(400, {"error": str(e)})
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


# ---------------- embedding databases explorer ----------------
VEC_TABLES = {
    "kb_cook": {"model": "BAAI/bge-small-en-v1.5", "dims": 384, "kind_col": "kind", "text_col": "text", "corpus": "Kitchen KB",
                "purpose": "Đơn vị văn bản của sách + video: fact nguyên tử, trang, đoạn video, gói wiki/SOP/FAQ (+ full-text tsvector)"},
    "kb_image": {"model": "CLIP ViT-B/32 (sentence-transformers/clip-ViT-B-32)", "dims": 512, "kind_col": "kind", "text_col": None, "corpus": "Kitchen KB",
                 "purpose": "Ảnh: trang PDF, hình nhúng trong PDF, khung video mỗi giây, khung đổi cảnh, 5 tile mỗi ảnh (bắt ảnh cắt)"},
    "kb_mm": {"model": "google/embeddinggemma-2", "dims": 768, "kind_col": "kind", "text_col": None, "corpus": "Kitchen KB",
              "purpose": "MỘT không gian cho mọi phương thức: chữ, ảnh trang, hình, khung video, cửa sổ âm thanh 5 giây"},
    "chunks_bge": {"model": "BAAI/bge-small-en-v1.5", "dims": 384, "kind_col": "strategy", "text_col": "text", "corpus": "Day 6 · EU AI Act + GDPR",
                   "purpose": "Chunk luật theo 6 chiến lược chunking của Day 6 (F/A/D/B/S/L); baseline của Day 7"},
    "chunks_minilm": {"model": "sentence-transformers/all-MiniLM-L6-v2", "dims": 384, "kind_col": "strategy", "text_col": "text", "corpus": "Day 6 · EU AI Act + GDPR",
                      "purpose": "Cùng các chunk, model MiniLM (so sánh model ở Day 6)"},
    "chunks_gemma": {"model": "google/embeddinggemma-300m", "dims": 768, "kind_col": "strategy", "text_col": "text", "corpus": "Day 6 · EU AI Act + GDPR",
                     "purpose": "Cùng các chunk, EmbeddingGemma-300m — cấu hình chốt của Day 7"},
}
KIND_LABEL = {"F": "F · cố định 500", "A": "A · 500 + overlap 50", "D": "D · đệ quy 800/80", "B": "B · theo cấu trúc (chọn)",
              "S": "S · ngữ nghĩa", "L": "L · Haiku chia (mẫu)"}


def _vt(table: str) -> dict:
    if table not in VEC_TABLES:
        raise ValueError("unknown table")
    return VEC_TABLES[table]


_FP: dict = {}


def _fp() -> dict:
    """Shazam-style fingerprint index (parser/audio_search.py), regrouped per (video, second) for browsing."""
    if not _FP:
        import audio_search as A
        db = A._db(T.WORK)
        per: dict = {}
        for h, posts in db["index"].items():
            f1, f2, dt = h >> 20, (h >> 8) & 0xFFF, h & 0xFF
            for vid, frame in posts:
                per.setdefault((vid, int(frame * A.FRAME_S)), []).append((f1, f2, dt, int(frame)))
        _FP.update(A=A, keys=sorted(per), per=per, meta=db["meta"], melody=db["melody"],
                   hz=A.SR / A.NFFT, frame_s=A.FRAME_S)
    return _FP


def fingerprint_summary() -> dict:
    F = _fp()
    kinds = [{"kind": f"hash:{v}", "label": f"vân âm thanh · {v}", "n": sum(1 for k in F["keys"] if k[0] == v)} for v in F["meta"]]
    kinds += [{"kind": f"melody:{v}", "label": f"giai điệu (ngân nga) · {v}", "n": -(-F["melody"][v].shape[1] // 100)} for v in F["melody"]]
    return {"table": "audio_fingerprint", "model": "Không phải embedding: hash cặp đỉnh phổ (Wang 2003) + đường cao độ pYIN",
            "dims": None, "corpus": "Kitchen KB · 2 video", "total": sum(m["hashes"] for m in F["meta"].values()),
            "purpose": "Shazam: mỗi hash = (tần số đỉnh 1, tần số đỉnh 2, khoảng cách thời gian) → (video, thời điểm). "
                       "Ngân nga: bước cao độ (nửa cung) theo thời gian. Lưu trong fp_index.pkl, không trong pgvector.",
            "kinds": kinds}


def fingerprint_rows(kind: str, q: str, offset: int, limit: int = 20) -> dict:
    F = _fp()
    if kind.startswith("melody:"):
        vid = kind.split(":", 1)[1]
        c = F["melody"].get(vid)
        if c is None:
            raise ValueError("unknown video")
        blocks = list(range(0, c.shape[1], 100))                          # ~100 contour points per row
        rows = []
        for b in blocks[offset:offset + limit]:
            seg = c[:, b:b + 100]
            t0, t1 = int(seg[1][0]), int(seg[1][-1])
            iv = [round(float(x), 2) for x in seg[0]]
            rows.append({"id": f"melody:{vid}@{t0}", "kind": kind, "kind_label": "giai điệu", "text": f"{len(iv)} bước cao độ, {t0}s–{t1}s",
                         "media": {"audio": f"/media/audio/{vid}/{t0}", "label": f"âm thanh {t0 // 60}:{t0 % 60:02d}", "href": f"https://youtu.be/{vid}?t={t0}"},
                         "meta": {"video": vid, "t": t0}, "melody": iv})
        return {"table": "audio_fingerprint", "total": len(blocks), "offset": offset, "limit": limit, "rows": rows}
    keys = [k for k in F["keys"] if not kind or kind == f"hash:{k[0]}"]
    if q and q.replace(":", "").isdigit():                                # jump to a time like 5:40 or 340
        sec = int(q.split(":")[0]) * 60 + int(q.split(":")[1]) if ":" in q else int(q)
        keys = [k for k in keys if k[1] >= sec]
    rows = []
    for vid, sec in keys[offset:offset + limit]:
        hs = F["per"][(vid, sec)]
        rows.append({"id": f"fp:{vid}@{sec}", "kind": f"hash:{vid}", "kind_label": "vân âm thanh",
                     "text": f"{len(hs)} hash trong giây {sec // 60}:{sec % 60:02d} · ví dụ " + ", ".join(
                         f"({h[0] * F['hz']:.0f} Hz → {h[1] * F['hz']:.0f} Hz, +{h[2] * F['frame_s'] * 1000:.0f} ms)" for h in hs[:3]),
                     "media": {"audio": f"/media/audio/{vid}/{sec}", "label": f"âm thanh {sec // 60}:{sec % 60:02d}", "href": f"https://youtu.be/{vid}?t={sec}"},
                     "meta": {"video": vid, "t": sec, "hashes": len(hs)},
                     "constellation": [[round((h[3] * F["frame_s"]) - sec, 3), h[0], round(h[2] * F["frame_s"], 3), h[1]] for h in hs[:60]]})
    return {"table": "audio_fingerprint", "total": len(keys), "offset": offset, "limit": limit, "rows": rows}


def vectors_summary() -> list[dict]:
    out = []
    with T.M._conn() as c:
        for t, info in VEC_TABLES.items():
            kinds = c.execute(f"SELECT {info['kind_col']}, count(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC").fetchall()
            out.append({"table": t, **{k: v for k, v in info.items() if k not in ("kind_col", "text_col")},
                        "total": sum(n for _, n in kinds), "kinds": [{"kind": k, "label": KIND_LABEL.get(k, k), "n": n} for k, n in kinds]})
    try:
        out.append(fingerprint_summary())
    except Exception as e:                       # index file missing -> show the other stores, report why
        out.append({"table": "audio_fingerprint", "model": "unavailable", "dims": None, "corpus": "", "total": 0,
                    "purpose": f"fp_index.pkl không đọc được: {type(e).__name__}", "kinds": []})
    return out


def _media_for(table: str, rid: str, kind: str, meta: dict) -> dict:
    """What a human sees for this embedding: text, an image or an audio clip."""
    m = re.match(r"(?:mm:)?(?:img|aud):yt:([\w-]{11})@([\d.]+)", rid)
    if m and kind.startswith("audio"):
        t = int(float(m.group(2)))
        return {"audio": f"/media/audio/{m.group(1)}/{t}", "label": f"âm thanh {t // 60}:{t % 60:02d}–{(t + 5) // 60}:{(t + 5) % 60:02d}",
                "href": f"https://youtu.be/{m.group(1)}?t={t}"}
    if m:
        t = int(float(m.group(2)))
        return {"img": f"/media/still/{m.group(1)}/{t}", "label": f"khung {t // 60}:{t % 60:02d}", "href": f"https://youtu.be/{m.group(1)}?t={t}"}
    m = re.match(r"img:yt:([\w-]{11}):(f_\d{3})", rid)
    if m:
        return {"img": f"/media/frame/{m.group(1)}/{m.group(2)}", "label": f"khung đổi cảnh {m.group(2)}"}
    m = re.match(r"(?:mm:)?img:cookbook:fig:x(\d+)", rid)
    if m:
        return {"img": f"/media/figure/x{m.group(1)}", "label": f"hình x{m.group(1)} · {len(meta.get('pages') or [])} trang"}
    m = re.match(r"(?:mm:)?img:cookbook:p(\d{3})", rid)
    if m:
        return {"img": f"/media/page/{int(m.group(1))}", "label": f"trang PDF {int(m.group(1))}"}
    return {}


def _vec_preview(vec_text: str) -> dict:
    import numpy as np
    v = np.array(json.loads(vec_text), dtype=np.float32)
    return {"dims": int(v.size), "norm": round(float(np.linalg.norm(v)), 4), "head": [round(float(x), 4) for x in v[:8]],
            "bars": [round(float(x), 3) for x in v[:: max(1, v.size // 96)][:96]],      # ~96 evenly spaced dims for the strip
            "min": round(float(v.min()), 4), "max": round(float(v.max()), 4)}


def _row_out(table: str, r: dict) -> dict:
    info = VEC_TABLES[table]
    meta = r.get("meta") or {}
    rid, kind = r["id"], r["kind"]
    if table.startswith("chunks_"):
        text = r.get("text") or ""
        meta = {"document": r.get("document_id"), "page": r.get("page"), "page_end": r.get("page_end"), "part": r.get("part"),
                "article": r.get("article"), "annex": r.get("annex"), "strategy": kind}
    else:
        text = r.get("text") or meta.get("text") or meta.get("ocr") or meta.get("segment") or ""
        if table == "kb_image" and kind == "tile":
            text = f"tile {rid.split('#')[-1]} của {meta.get('parent')}"
    media = _media_for(table, rid if kind != "tile" else (meta.get("parent") or rid), kind, meta)
    keep = {k: meta.get(k) for k in ("recipe", "pdf_page", "pages", "printed_page", "page_type", "category", "t", "t0", "link", "video_title",
                                     "document", "page", "page_end", "part", "article", "annex", "unit_id", "parent", "box", "extractor")
            if meta.get(k) not in (None, "", [])}
    return {"id": rid, "kind": kind, "kind_label": KIND_LABEL.get(kind, kind), "text": " ".join(text.split())[:420], "media": media,
            "meta": keep, "vector": _vec_preview(r["e"])}


def vectors_rows(table: str, kind: str, q: str, offset: int, limit: int = 20) -> dict:
    info = _vt(table)
    kc = info["kind_col"]
    cols = ("chunk_id AS id, strategy AS kind, text, document_id, page, page_end, part, article, annex" if table.startswith("chunks_")
            else "id, kind, meta" + (", text" if info["text_col"] else ""))
    where, args = [], []
    if kind:
        where.append(f"{kc} = %s")
        args.append(kind)
    if q:
        where.append(("text" if info["text_col"] else "meta::text") + " ILIKE %s" + (" OR id ILIKE %s" if not table.startswith("chunks_") else " OR chunk_id ILIKE %s"))
        args += [f"%{q[:80]}%", f"%{q[:80]}%"]
    w = (" WHERE " + " AND ".join(f"({x})" for x in where)) if where else ""
    idcol = "chunk_id" if table.startswith("chunks_") else "id"
    from psycopg.rows import dict_row
    with T.M._conn() as c:
        total = c.execute(f"SELECT count(*) FROM {table}{w}", args).fetchone()[0]
        with c.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(f"SELECT {cols}, embedding::text AS e FROM {table}{w} ORDER BY {idcol} LIMIT %s OFFSET %s",
                               args + [limit, max(0, offset)]).fetchall()
    return {"table": table, "model": info["model"], "dims": info["dims"], "total": total, "offset": offset, "limit": limit,
            "rows": [_row_out(table, r) for r in rows]}


def vectors_nn(table: str, rid: str, k: int = 6) -> dict:
    """Nearest neighbours of one stored vector inside the same table (cosine), excluding itself and its own tiles."""
    info = _vt(table)
    idcol = "chunk_id" if table.startswith("chunks_") else "id"
    cols = ("chunk_id AS id, strategy AS kind, text, document_id, page, page_end, part, article, annex" if table.startswith("chunks_")
            else "id, kind, meta" + (", text" if info["text_col"] else ""))
    from psycopg.rows import dict_row
    with T.M._conn() as c, c.cursor(row_factory=dict_row) as cur:
        src = cur.execute(f"SELECT embedding::text AS e, {info['kind_col']} AS kind FROM {table} WHERE {idcol} = %s", (rid,)).fetchone()
        if not src:
            raise ValueError("unknown id")
        same = f" AND strategy = %s" if table.startswith("chunks_") else (" AND kind <> 'tile'" if table == "kb_image" else "")
        args = [src["e"], rid] + ([src["kind"]] if table.startswith("chunks_") else []) + [src["e"], k]
        rows = cur.execute(f"SELECT {cols}, embedding::text AS e, 1 - (embedding <=> %s::vector) AS cos FROM {table} "
                           f"WHERE {idcol} <> %s{same} ORDER BY embedding <=> %s::vector LIMIT %s", args).fetchall()
    return {"table": table, "id": rid, "neighbours": [{**_row_out(table, r), "cos": round(float(r["cos"]), 4)} for r in rows]}


def warm() -> None:
    T.search_kb("warm up")          # loads EmbeddingGemma 2 (default text method) + DB
    T.search_images("warm up")      # loads CLIP


if __name__ == "__main__":
    warm()
    port = int(os.environ.get("PORT", 8780))
    print(f"Kitchen KB agent on http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
