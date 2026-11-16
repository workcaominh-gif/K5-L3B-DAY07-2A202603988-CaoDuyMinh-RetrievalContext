"""Tools the agent may call (allowlist). Every tool validates and clamps its arguments, returns compact JSON, and tags
each retrievable item with a citation id the output guardrail can check later.

Stores (built by parser/): kb_cook (bge vectors + full-text), kb_image (CLIP), kg_edges (graph), recipes.json,
html/pNNN.html (layout-preserving pages), video/<id>/video.json, audio fingerprint index.
"""
from __future__ import annotations

import contextvars
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parser"))
import mm_search as M  # noqa: E402

METHOD = contextvars.ContextVar("retrieval_method", default="dense_gemma")
IMAGE_BACKEND = contextvars.ContextVar("image_backend", default="fusion")

WORK = Path("/Volumes/T7 Dev/AI20K/day7/work")
UPLOADS = WORK / "uploads"
KINDS = {"page", "fact", "video_segment", "package"}
RELS = {"has_ingredient", "in_category", "contains_allergen", "ccp_temp_F", "demonstrates", "is_video"}

TOOLS = [
    {"name": "search_kb",
     "description": "Hybrid search (bge dense + full-text, fused with RRF) over the Kitchen KB: cookbook pages, atomic facts, "
                    "video segments and compiled packages (recipe wiki, food-safety SOP, FAQ, glossary). Use for almost every "
                    "question. Rewrite the user's question into a focused search query; call again with a different query if "
                    "the first results do not contain the evidence.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "focused search query in English (the KB is English)"},
         "kind": {"type": "string", "enum": ["any", "page", "fact", "video_segment", "package"], "description": "restrict unit type"},
         "recipe": {"type": "string", "description": "exact recipe name to filter on, only when the user named one"},
         "top_k": {"type": "integer", "minimum": 1, "maximum": 10}},
         "required": ["query"], "additionalProperties": False}},
    {"name": "get_recipe",
     "description": "Complete structured record of ONE recipe: every ingredient row (25 and 50 servings, weight and measure, "
                    "with the PDF page), category, award, pages, allergens, linked video. Cheap - use it to VERIFY a recipe "
                    "before claiming it does or does not contain something; call it for several recipes in parallel.",
     "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "recipe name (partial is ok)"}},
                      "required": ["name"], "additionalProperties": False}},
    {"name": "get_page",
     "description": "Read one cookbook page in full (layout-preserving text incl. complete tables). Use after search_kb when "
                    "a table row, step or nutrient needs the whole page to answer exactly.",
     "input_schema": {"type": "object", "properties": {"pdf_page": {"type": "integer", "minimum": 1, "maximum": 148}},
                      "required": ["pdf_page"], "additionalProperties": False}},
    {"name": "graph_query",
     "description": "Query the recipe knowledge graph for list/aggregate questions that search can't answer completely "
                    "(e.g. all recipes containing an allergen, all recipes in a category, recipes using an ingredient, "
                    "CCP temperatures). Relations: has_ingredient (object = ingredient key, lowercase), in_category, "
                    "contains_allergen (milk, egg, wheat/gluten, soy, fish, peanut, tree nuts, sesame), ccp_temp_F, demonstrates.",
     "input_schema": {"type": "object", "properties": {
         "relation": {"type": "string", "enum": sorted(RELS)},
         "subject": {"type": "string", "description": "recipe name (optional)"},
         "object_contains": {"type": "string", "description": "substring of the object; several alternatives separated by '|', e.g. 'fish|egg' (optional)"}},
         "required": ["relation"], "additionalProperties": False}},
    {"name": "search_images",
     "description": "Visual search over ALL cookbook page images and ALL video keyframes (CLIP text-to-image), e.g. "
                    "'dish with orange squash cubes and crumble topping', 'hand setting an oven dial', 'kids flipping pancakes'. "
                    "Video hits come back with the exact second (t) and a youtu.be link at that moment; page hits with pdf_page. "
                    "Use for any 'show me / where in the video / which page shows / looks like' request.",
     "input_schema": {"type": "object", "properties": {"description": {"type": "string"},
                                                        "top_k": {"type": "integer", "minimum": 1, "maximum": 6}},
                      "required": ["description"], "additionalProperties": False}},
    {"name": "analyze_attachment",
     "description": "Analyse a file the user attached (image, recording or audio clip). Image -> nearest cookbook pages and "
                    "video frames (with timestamps). Audio -> ONE recording runs three analyses: (1) Shazam-style fingerprint "
                    "(sound played from one of the videos -> video + exact second), (2) speech-to-text (the user describing "
                    "what they want; any language -> then search_kb with an English query built from the transcript), "
                    "(3) humming / melody matching. The result's 'verdict' says which one had real evidence "
                    "(video_sound | voice | hum | nothing); report the others only as low-confidence alternatives.",
     "input_schema": {"type": "object", "properties": {"attachment_id": {"type": "string"},
                                                        "mode": {"type": "string", "enum": ["auto", "hum"]}},
                      "required": ["attachment_id"], "additionalProperties": False}},
    {"name": "view_candidates",
     "description": "LOOK at the user's attached image next to up to 3 candidate matches (video frames at their exact second, "
                    "cookbook pages, or PDF figures) so you can compare them visually. Use it after analyze_attachment / "
                    "search_images whenever the top candidates are close or the attachment is a crop, before naming a match. "
                    "Candidate ids are the ids returned by those tools (e.g. 'img:yt:QhkDOr6kmi4@4', 'img:cookbook:p012', "
                    "'img:cookbook:fig:x642').",
     "input_schema": {"type": "object", "properties": {
         "attachment_id": {"type": "string"},
         "candidates": {"type": "array", "items": {"type": "string"}, "maxItems": 3}},
         "required": ["attachment_id", "candidates"], "additionalProperties": False}},
    {"name": "get_video_segment",
     "description": "Read the transcript, on-screen text and visual description of a video around a timestamp.",
     "input_schema": {"type": "object", "properties": {"video_id": {"type": "string", "enum": ["QhkDOr6kmi4", "eSKtPtW0X2o"]},
                                                        "t": {"type": "number", "minimum": 0}},
                      "required": ["video_id", "t"], "additionalProperties": False}},
]


def _cite_for(meta: dict, uid: str) -> dict:
    c = {"cite": uid}
    if meta.get("pdf_page"):
        c["source"] = f"cookbook p.{meta['pdf_page']}"
    if meta.get("link"):
        c["source"] = meta["link"]
    return c


def search_kb(query: str, kind: str = "any", recipe: str | None = None, top_k: int = 5) -> dict:
    import retrieval as R
    top_k = max(1, min(int(top_k), 10))
    method = METHOD.get()
    hits = R.retrieve(query, method, k=40 if (kind != "any" or recipe) and method != "hybrid_rerank" else 20)
    out = []
    for h in hits:
        meta = h["meta"] or {}
        hk = h["kind"].split(":")[-1]
        if kind != "any" and hk != kind:
            continue
        if recipe and (meta.get("recipe") or "").lower() != recipe.lower():
            continue
        cid = meta.get("unit_id") or h["id"]
        out.append({**_cite_for({**meta, "link": meta.get("link")}, cid), "kind": h["kind"], "recipe": meta.get("recipe"),
                    "text": " ".join((h["text"] or "").split())[:240], **({"rerank": h["rerank"]} if "rerank" in h else {}),
                    **({"pdf_page": meta["pdf_page"]} if meta.get("pdf_page") else {}), **({"t": meta["t"]} if meta.get("t") is not None else {})})
        if len(out) >= top_k:
            break
    return {"query": query, "method": method, "filters": {"kind": kind, "recipe": recipe}, "results": out}


def get_recipe(name: str) -> dict:
    recipes = json.loads((WORK / "kb" / "recipes.json").read_text(encoding="utf-8"))
    key = name.lower().replace("’", "'").strip()
    match = [r for r in recipes if r.lower().replace("’", "'") == key] or [r for r in recipes if key in r.lower().replace("’", "'")]
    if not match:
        return {"error": f"no recipe matching '{name}'", "known": sorted(recipes)[:40]}
    r = recipes[match[0]]
    ings = r["ingredients"]
    vid = (r.get("videos") or [None])[0]
    cite = (f"cookbook:p{ings[0]['pdf_page']:03d}" if ings and ings[0].get("pdf_page") else
            f"yt:{vid}@{ings[0]['t']}" if ings and vid and ings[0].get("t") is not None else
            f"cookbook:p{r['pages'][0]['pdf_page']:03d}" if r["pages"] else f"yt:{vid}@0" if vid else None)
    return {"cite": cite, "recipe": match[0], "other_matches": match[1:4], "category": r["category"], "award": r.get("award"),
            "pages": [p["pdf_page"] for p in r["pages"]], "videos": r.get("videos", []),
            "ingredient_count": len(ings),
            "ingredients": [{"name": i["name"], "25": " / ".join(x for x in (i.get("w25"), i.get("m25")) if x),
                             "50": " / ".join(x for x in (i.get("w50"), i.get("m50")) if x),
                             "cite": f"cookbook:p{i['pdf_page']:03d}" if i.get("pdf_page") else f"yt:{vid}@{i.get('t')}"} for i in ings],
            # each nutrient cites the page that prints it (the nutrition box is usually on the page AFTER the ingredients)
            "nutrients_per_serving": {k: {"value": v["value"], "cite": f"cookbook:p{v['pdf_page']:03d}"}
                                      for k, v in (r.get("nutrients_per_serving") or {}).items()},
            "allergens_rule_based": r.get("allergens", {}),
            # salt vs sodium: a recipe can list no salt yet contain sodium (soy sauce, broth/base, canned goods, cheese)
            "sodium_per_serving": ({"value": r["nutrients_per_serving"]["Sodium"]["value"],
                                    "cite": f"cookbook:p{r['nutrients_per_serving']['Sodium']['pdf_page']:03d}"}
                                   if (r.get("nutrients_per_serving") or {}).get("Sodium") else None),
            "salt_rows": [i["name"] for i in ings if re.search(r"\bsalt\b", i["name"], re.I) and not re.search(r"salt-free", i["name"], re.I)],
            "sodium_sources": [i["name"] for i in ings if re.search(r"sodium|soy sauce|\bbase\b|broth|stock|seasoning|cheese|canned|tortilla|bread|roll", i["name"], re.I)],
            "note": "cite each value with ITS cite id: ingredient rows -> their table page, nutrients/sodium -> the nutrition page. "
                    "The top-level cite is the first ingredient page."}


def get_page(pdf_page: int) -> dict:
    n = int(pdf_page)
    if not 1 <= n <= 148:
        raise ValueError("pdf_page must be 1..148")
    f = WORK / "html" / f"p{n:03d}.html"
    text = M_text(f.read_text(encoding="utf-8"))
    man = {r["pdf_page"]: r for r in json.loads((WORK / "manifest.json").read_text())}[n]
    return {"cite": f"cookbook:p{n:03d}", "source": f"cookbook p.{n} (printed p.{man['printed_page']})",
            "recipe": man["recipe"], "type": man["type"], "text": text[:6000]}


def M_text(html: str) -> str:
    sys.path.insert(0, str(ROOT / "parser"))
    from enrich import text_of
    return text_of(html)


def graph_query(relation: str, subject: str | None = None, object_contains: str | None = None) -> dict:
    if relation not in RELS:
        raise ValueError(f"unknown relation {relation}")
    sql, args = "SELECT s, rel, o, attrs, source FROM kg_edges WHERE rel = %s", [relation]
    if subject:
        sql += " AND lower(s) = lower(%s)"
        args.append(subject)
    if object_contains:
        alts = [a.strip().lower() for a in re.split(r"[|,]", object_contains) if a.strip()][:8]
        sql += " AND (" + " OR ".join(["lower(o) LIKE %s"] * len(alts)) + ")"
        args += [f"%{a}%" for a in alts]
    with M._conn() as c:
        rows = c.execute(sql + " ORDER BY s LIMIT 60", args).fetchall()
        # derived edges (allergens, categories) cite the page that holds the evidence: the ingredient-table row
        ing_page = {(s, a.get("name")): src for s, a, src in
                    c.execute("SELECT s, attrs, source FROM kg_edges WHERE rel = 'has_ingredient'").fetchall()}
        first_page = {}
        for (s, _), src in sorted(ing_page.items(), key=lambda x: x[1]):
            first_page.setdefault(s, src)
    edges = []
    for s, rel, o, attrs, src in rows:
        if src.startswith(("cookbook:", "yt:")):
            cite = src
        elif rel == "contains_allergen":
            cite = next((ing_page[(s, n)] for n in attrs.get("via", []) if (s, n) in ing_page), first_page.get(s))
        else:
            cite = first_page.get(s)
        edges.append({"cite": cite or "graph:" + re.sub(r"[^a-z0-9]+", "-", f"{s}-{rel}".lower()).strip("-"),
                      "subject": s, "object": o, "attrs": attrs, "derived_from": src})
    return {"relation": relation, "n": len(edges), "edges": edges,
            "coverage": "30 cookbook recipes (from ingredient tables) + 2 video recipes (Corn and Zucchini Pancakes: on-screen "
                        "ingredient card; Golden Squash Hotcakes: no ingredient list shown, edges marked 'seen in the video only'). "
                        "Allergen edges are rule-based on ingredient names. Anything else in the sources is NOT in the graph: "
                        "confirm list answers with search_kb before calling them complete."}


def search_images(description: str, top_k: int = 4) -> dict:
    v = M._clip().encode([description], normalize_embeddings=True)[0]
    hits = M.image_search(v, k=max(1, min(int(top_k), 6)))
    for h in hits:
        h["cite"] = f"cookbook:p{h['pdf_page']:03d}" if h.get("pdf_page") else h["id"]
        h["note"] = "visual similarity only (CLIP); confirm with get_page / get_video_segment before stating facts"
    return {"description": description, "results": hits}


def analyze_attachment(attachment_id: str, mode: str = "auto") -> dict:
    if not re.fullmatch(r"[a-f0-9]{12}\.(png|jpg|jpeg|webp|wav|webm|m4a|mp3|ogg)", attachment_id):
        raise ValueError("unknown attachment id")
    p = UPLOADS / attachment_id
    if not p.exists():
        raise ValueError("attachment not found")
    r = M.ask(WORK, str(p if p.suffix != ".webm" else _to_wav(p)), hum=(mode == "hum"), backend=IMAGE_BACKEND.get())
    for h in r.get("hits", []) or []:
        if h.get("kind") == "pdf_figure":       # a reused figure: cite its first page, list every page it appears on
            h["cite"] = f"cookbook:p{h['pdf_page']:03d}"
            h["note"] = f"embedded image used on {len(h.get('pages', []))} page(s): {h.get('pages')}"
        h.setdefault("cite", h.get("id"))
    if r.get("mode") == "fingerprint":
        r["cite"] = f"yt:{r['match']['match']}@{r['match']['t']}"
    return r


def _to_wav(p: Path) -> Path:
    import subprocess
    out = p.with_suffix(".wav")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(p), "-ar", "16000", "-ac", "1", str(out)], check=True)
    return out


def _jpeg_b64(path: Path, max_side: int = 768) -> str:
    import base64
    import io
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def _candidate_path(cid: str) -> Path | None:
    m = re.fullmatch(r"img:yt:(QhkDOr6kmi4|eSKtPtW0X2o)@(\d{1,4})", cid)
    if m:
        f = WORK / "video" / m.group(1) / "dense" / f"t_{int(m.group(2)):04d}.jpg"
        return f if f.exists() else None
    m = re.fullmatch(r"(?:img:)?cookbook:p(\d{3})", cid)
    if m:
        return WORK / "pages" / f"p{m.group(1)}.png"
    m = re.fullmatch(r"img:cookbook:fig:x(\d+)", cid)
    if m:
        f = WORK / "pdf_figures" / f"x{m.group(1)}.png"
        return f if f.exists() else None
    return None


def view_candidates(attachment_id: str, candidates: list) -> dict:
    """Returns images for Claude to look at (the agent loop turns '_images' into image content blocks)."""
    if not re.fullmatch(r"[a-f0-9]{12}\.(png|jpg|jpeg|webp)", attachment_id) or not (UPLOADS / attachment_id).exists():
        raise ValueError("unknown image attachment id")
    imgs, labels = [("attachment (the user's image)", UPLOADS / attachment_id)], []
    for cid in [c for c in candidates if isinstance(c, str)][:3]:
        p = _candidate_path(cid)
        if p is None:
            labels.append({"candidate": cid, "error": "no image for this id"})
            continue
        imgs.append((f"candidate {cid}", p))
        labels.append({"candidate": cid, "cite": cid})
    return {"shown": [l for l, _ in imgs], "candidates": labels,
            "instruction": "Compare the attachment with each candidate visually (layout, text, colours, objects). "
                           "Say which candidate matches, or that none does.",
            "_images": [(l, _jpeg_b64(p)) for l, p in imgs]}


def get_video_segment(video_id: str, t: float) -> dict:
    seg = M.segment_at(WORK, video_id, float(t))
    if not seg:
        return {"video_id": video_id, "t": t, "segment": None}
    return {"cite": f"yt:{video_id}@{int(seg.get('t0') or t)}", "source": seg.get("link"),
            "segment": {k: seg.get(k) for k in ("t0", "t1", "topic", "transcript", "on_screen_text", "visual")}}


IMPL = {"view_candidates": view_candidates, "get_recipe": get_recipe, "search_kb": search_kb, "get_page": get_page, "graph_query": graph_query, "search_images": search_images,
        "analyze_attachment": analyze_attachment, "get_video_segment": get_video_segment}



SEARCH_MODELS = {
    "dense_gemma": ("Tìm đoạn văn bản gần nghĩa nhất với câu truy vấn.", ["EmbeddingGemma 2 (768-d) · pgvector cosine"]),
    "gemma_all": ("Tìm trên mọi phương thức (chữ, ảnh trang, khung video, âm thanh) bằng một không gian vector.", ["EmbeddingGemma 2 (768-d) · pgvector cosine"]),
    "hybrid_gemma": ("Gộp tìm theo nghĩa và tìm theo từ khoá (RRF).", ["EmbeddingGemma 2", "Postgres full-text (không model)"]),
    "hybrid_bge": ("Gộp tìm theo nghĩa và tìm theo từ khoá (RRF).", ["bge-small-en-v1.5 (384-d)", "Postgres full-text (không model)"]),
    "dense_bge": ("Tìm đoạn văn bản gần nghĩa nhất.", ["bge-small-en-v1.5 (384-d) · pgvector cosine"]),
    "lexical": ("Tìm theo từ khoá (stemming tiếng Anh).", ["Postgres full-text (không model)"]),
    "hybrid_rerank": ("Lấy 20 ứng viên lai rồi cho model chấm lại thứ tự.", ["bge-small-en-v1.5", "Postgres full-text", "Claude Haiku 5.5 (rerank)"]),
}
IMAGE_MODELS = {"clip": ["CLIP ViT-B/32 (ảnh + 5 tile)"], "gemma": ["EmbeddingGemma 2 (ảnh)"],
                "fusion": ["CLIP ViT-B/32 (ảnh + 5 tile)", "EmbeddingGemma 2 (ảnh)"]}


def tool_info(name: str, args: dict) -> dict:
    """Plain-language description of a tool call and the models it runs, for the trace panel."""
    if name == "search_kb":
        does, models = SEARCH_MODELS.get(METHOD.get(), ("Tìm trong kho.", []))
        return {"does": does, "models": models}
    if name == "analyze_attachment":
        aid = str(args.get("attachment_id", ""))
        if re.search(r"\.(png|jpe?g|webp)$", aid):
            return {"does": "So khớp ảnh bạn gửi với 148 trang, 151 hình trong PDF và 616 khung video (mỗi giây), "
                            "rồi xếp lại bằng so khớp điểm ảnh để bắt ảnh cắt nhỏ.",
                    "models": IMAGE_MODELS.get(IMAGE_BACKEND.get(), []) + ["Apple Vision OCR (chữ trong ảnh)", "dHash (ảnh gần trùng)",
                                                                           "Template matching NCC (numpy/scipy)"]}
        return {"does": "Nhận diện bản ghi âm: âm thanh phát từ video (vân âm thanh), lời nói (chuyển thành chữ) hoặc ngân nga (giai điệu).",
                "models": ["Fingerprint kiểu Shazam (numpy/scipy, không model)", "faster-whisper small (STT)", "librosa pYIN (cao độ)"]}
    if name == "view_candidates":
        return {"does": "Đưa ảnh của bạn và các ứng viên cho model nhìn trực tiếp để so sánh.", "models": ["Claude Sonnet 5.5 (vision)"]}
    if name == "search_images":
        return {"does": "Tìm trang/khung video có HÌNH giống mô tả bằng chữ.", "models": ["CLIP ViT-B/32 (text → image)"]}
    if name == "get_recipe":
        return {"does": "Đọc bản ghi công thức đã trích xuất: toàn bộ nguyên liệu, dinh dưỡng, trang.",
                "models": ["Không gọi model (dữ liệu do Sonnet/Haiku 5.5 trích xuất lúc nạp)"]}
    if name == "get_page":
        return {"does": "Đọc toàn văn một trang (HTML giữ bố cục, gồm bảng).",
                "models": ["Không gọi model (HTML do Sonnet/Haiku 5.5 tạo lúc nạp)"]}
    if name == "graph_query":
        return {"does": "Truy vấn đồ thị công thức – nguyên liệu – dị ứng – nhóm – CCP.", "models": ["SQL trên kg_edges (không model)"]}
    if name == "get_video_segment":
        return {"does": "Đọc đoạn video quanh mốc thời gian: lời, chữ trên màn hình, mô tả hình.",
                "models": ["Không gọi model (đoạn do Whisper + phụ đề + OCR + Sonnet 5.5 tạo lúc nạp)"]}
    return {"does": "", "models": []}
