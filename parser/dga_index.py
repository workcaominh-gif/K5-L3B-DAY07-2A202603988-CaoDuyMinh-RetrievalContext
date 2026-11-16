"""Crops + index for the Dietary Guidelines 2020-2025 (Postgres table dga_units, EmbeddingGemma 2, 768-d).

    python parser/dga_index.py crops          # work/crops/pNNN_rK.jpg + work/regions.json (pixel + PDF-point bboxes)
    python parser/dga_index.py units          # work/units.jsonl (no model, no DB)
    python parser/dga_index.py build          # crops + units + embeddings -> dga_units (idempotent: delete+insert by id)
    python parser/dga_index.py stats          # -> work/stats.json

Units (all rows carry pdf_page, printed_page, region and, for visuals, the crop path + PDF-point bbox):
  page        one per page: context header + region summaries + full page text (from the layout HTML)
  chunk       paragraph-sized chunks of the page text, <= 350 words, header "Dietary Guidelines 2020-2025 · <section> · p.<printed> (PDF p.<n>)"
  facts       groups of <= 8 atomic facts of the page
  table       title + linearised rows "row | column: value"
  chart       title + axes + every data point (model value; exact geometry value when dga_verify recovered it)
  image       image / diagram regions: summary + alt + labelled elements
  box         boxed callouts (region kind text)
  image:crop  Gemma image embedding of every region crop        (same 768-d space as the text rows)
  image:page  Gemma image embedding of every page render
Text rows use the EmbeddingGemma "Document" prompt (title: none); images use no prompt (model card).
"""
from __future__ import annotations

import html as H
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mm_search as M  # noqa: E402  (_conn, _vec)

PDF = Path("/Volumes/T7 Dev/AI20K/day7/dga/raw/dga_2020_2025.pdf")
WORK = Path("/Volumes/T7 Dev/AI20K/day7/dga/work")
DOC = "Dietary Guidelines 2020-2025"
DPI = 150
MAXW = 350
REEMBED = "--reembed-images" in sys.argv          # default: reuse image vectors of unchanged crops/pages


def refine_bbox(pg, bb_pt, kind):
    """Tighten/extend the model's box to the PDF objects (text blocks, vector drawings, images) whose centre lies in it."""
    import fitz
    W, H_ = pg.rect.width, pg.rect.height
    pad = 0.03 * W
    outer = fitz.Rect(bb_pt[0] - pad, bb_pt[1] - pad, bb_pt[2] + pad, bb_pt[3] + pad) & pg.rect
    rects = [fitz.Rect(b[:4]) for b in pg.get_text("blocks")]
    rects += [d["rect"] for d in pg.get_drawings() if d["rect"].get_area() < 0.5 * W * H_]
    rects += [fitz.Rect(r) for x in pg.get_images() for r in pg.get_image_rects(x[0])]
    inner = fitz.Rect(bb_pt)
    u = fitz.Rect()
    for r in rects:
        c = fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        if r.is_empty and r.width == 0 and r.height == 0:
            continue
        if inner.contains(c) and outer.contains(r):
            u |= r
    if u.is_empty or u.get_area() < 0.25 * inner.get_area():
        u, refined = fitz.Rect(bb_pt), False
    else:
        u, refined = u & outer, True
    if kind in ("table", "chart", "diagram"):          # pull in the "Table A3-2 ..." / "Figure 3-2 ..." caption just above
        for _ in range(1):
            cap = [fitz.Rect(b[:4]) for b in pg.get_text("blocks")
                   if re.match(r"\s*(Table|Figure)\s+[A-Z]?\d", b[4]) and u.y0 - 70 <= b[3] <= u.y0 + 2
                   and min(b[2], u.x1) - max(b[0], u.x0) > 0]
            if not cap:
                break
            for c in cap:
                u |= c
            refined = True
    return [round(v, 1) for v in u], refined


def crops() -> list[dict]:
    import fitz
    from PIL import Image
    doc = fitz.open(PDF)
    (WORK / "crops").mkdir(exist_ok=True)
    out = []
    for jf in sorted((WORK / "json").glob("p*.json")):
        page = json.loads(jf.read_text())
        n = page["pdf_page"]
        pg = doc[n - 1]
        W, H_ = pg.rect.width, pg.rect.height
        im = None
        for r in page.get("regions", []):
            if r["kind"] == "text" or len(r.get("bbox_norm", [])) != 4:
                continue
            x0, y0, x1, y1 = [min(max(v, 0), 1) for v in r["bbox_norm"]]
            if x1 - x0 < 0.02 or y1 - y0 < 0.02:
                continue
            pt = [x0 * W, y0 * H_, x1 * W, y1 * H_]
            pt2, refined = refine_bbox(pg, pt, r["kind"])
            im = im or Image.open(WORK / "pages" / f"p{n:03d}.png").convert("RGB")
            s = im.width / W
            px = [max(0, int(pt2[0] * s) - 6), max(0, int(pt2[1] * s) - 6), min(im.width, int(pt2[2] * s) + 6), min(im.height, int(pt2[3] * s) + 6)]
            f = WORK / "crops" / f"p{n:03d}_{r['id']}.jpg"
            im.crop(px).save(f, "JPEG", quality=88)
            out.append({"pdf_page": n, "region": r["id"], "kind": r["kind"], "title": r["title"], "crop": str(f),
                        "bbox_pt": [round(v, 1) for v in pt2], "bbox_px_150dpi": px, "bbox_norm_model": r["bbox_norm"], "refined": refined})
    (WORK / "regions.json").write_text(json.dumps(out, indent=1))
    print("crops", len(out), "refined", sum(o["refined"] for o in out))
    return out


def html_text(h: str) -> str:
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)</t[dh]>", " | ", h)
    h = re.sub(r"(?i)</(tr|p|h\d|li|div|figcaption|caption|table|ul|ol)>|<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)<li[^>]*>", "- ", h)
    h = H.unescape(re.sub(r"<[^>]+>", "", h))
    return "\n".join(re.sub(r"[ \t]+", " ", l).strip(" |") for l in h.splitlines() if l.strip(" |\t"))


def nocomma(s: str) -> str:
    """'2,000' -> '2000 2,000' so full-text matches both spellings of calorie levels / amounts."""
    return s + "\n" + re.sub(r"(?<=\d),(?=\d{3})", "", s) if re.search(r"\d,\d{3}", s) else s


def chunks(text: str, maxw: int = MAXW) -> list[str]:
    paras, out, cur = [p for p in text.split("\n") if p.strip()], [], []
    for p in paras:
        w = p.split()
        while len(w) > maxw:                      # very long paragraph: hard split
            if cur:
                out.append(" \n".join(cur)); cur = []
            out.append(" ".join(w[:maxw])); w = w[maxw:]
        if sum(len(c.split()) for c in cur) + len(w) > maxw and cur:
            out.append("\n".join(cur)); cur = []
        cur.append(" ".join(w))
    if cur:
        out.append("\n".join(cur))
    return out


def lin_table(d: dict) -> list[str]:
    hdr, rows = d["header"], []
    for r in d["rows"]:
        if not r:
            continue
        cells = [f"{(hdr[j] if j < len(hdr) else f'col{j}')}: {c}" for j, c in enumerate(r[1:], 1) if c.strip()]
        rows.append(f"{r[0]} | " + "; ".join(cells))
    return rows


def lin_chart(d: dict) -> list[str]:
    out = [f"Chart type: {d['chart_type']}"]
    for ax in ("x_axis", "y_axis"):
        a = d[ax]
        if a["label"] or a["ticks"]:
            out.append(f"{ax.replace('_', '-')}: {a['label']} ({a['unit']}) ticks {', '.join(a['ticks'][:20])}")
    if d["series"]:
        out.append("Legend: " + "; ".join(d["series"]))
    for p in d["points"]:
        g = p.get("geometry_value")
        v = f"{p['value']} {p['unit']}".strip()
        src = "printed" if p["source"] == "printed" else (f"read off axis; PDF vector-geometry value = {g:g}" if g is not None else "read off axis (approx.)")
        out.append(f"{p['category']} | {p['series']}: {v} ({src})")
    return out


def units() -> list[dict]:
    regs = {(r["pdf_page"], r["region"]): r for r in json.loads((WORK / "regions.json").read_text())} if (WORK / "regions.json").exists() else {}
    U = []
    for jf in sorted((WORK / "json").glob("p*.json")):
        p = json.loads(jf.read_text())
        n, pp, sec = p["pdf_page"], p.get("printed_page", ""), p.get("section", "")
        hdr = f"{DOC} · {sec} · p.{pp or '-'} (PDF p.{n})"
        base = {"pdf_page": n, "printed_page": pp, "section": sec}
        body = html_text(p.get("html", ""))
        summ = " ".join(f"[{r['kind']}] {r['title']}: {r['summary']}" for r in p.get("regions", []))
        U.append({"id": f"dga:p{n:03d}", "kind": "page", **base, "region": "", "title": sec,
                  "text": f"{hdr}\n{summ}\n{body}".strip(), "meta": {}})
        for i, c in enumerate(chunks(body)):
            U.append({"id": f"dga:p{n:03d}:c{i}", "kind": "chunk", **base, "region": "", "title": sec, "text": f"{hdr}\n{c}", "meta": {}})
        f = p.get("facts", [])
        for i in range(0, len(f), 8):
            U.append({"id": f"dga:p{n:03d}:f{i // 8}", "kind": "facts", **base, "region": "", "title": sec,
                      "text": f"{hdr}\n" + "\n".join(f"- {x}" for x in f[i:i + 8]), "meta": {"facts": f[i:i + 8]}})
        for r in p.get("regions", []):
            rg = regs.get((n, r["id"]), {})
            meta = {"crop": rg.get("crop"), "bbox_pt": rg.get("bbox_pt"), "bbox_norm": r["bbox_norm"], "summary": r["summary"], "alt": r["alt"]}
            d = r["data"]
            if r["kind"] == "table":
                body_r = [f"Table: {r['title']}", r["summary"], "Columns: " + " | ".join(d["header"])] + lin_table(d)
                kind = "table"
            elif r["kind"] == "chart":
                body_r = [f"Chart: {r['title']}", r["summary"]] + lin_chart(d)
                kind = "chart"
            elif r["kind"] in ("image", "diagram"):
                body_r = [f"{r['kind'].title()}: {r['title']}", r["summary"], r["alt"]] + (["Elements: " + "; ".join(d["elements"])] if d["elements"] else []) + lin_table(d)
                kind = "image"
            else:
                body_r = [f"Box: {r['title']}", r["summary"]] + d["elements"]
                kind = "box"
            if r["kind"] == "table":                    # one small unit per table row: precise dense hits on a single cell
                for j, row in enumerate(lin_table(d)):
                    U.append({"id": f"dga:p{n:03d}:{r['id']}:row{j}", "kind": "table_row", **base, "region": r["id"], "title": r["title"],
                              "text": f"{hdr}\nTable: {r['title']}\n{row}", "meta": meta})
            txt = "\n".join(x for x in body_r if x)
            parts = chunks(txt, 600) if kind in ("table", "chart") else [txt]
            for j, t in enumerate(parts):
                U.append({"id": f"dga:p{n:03d}:{r['id']}" + (f":{j}" if j else ""), "kind": kind, **base, "region": r["id"],
                          "title": r["title"], "text": f"{hdr}\n" + (t if j == 0 else f"{r['title']} (continued)\n{t}"), "meta": meta})
            if rg.get("crop"):
                U.append({"id": f"dga:img:p{n:03d}:{r['id']}", "kind": "image:crop", **base, "region": r["id"], "title": r["title"],
                          "text": f"{hdr}\n[{r['kind']} crop] {r['title']}: {r['summary']}", "meta": {**meta, "image": rg["crop"]}})
        U.append({"id": f"dga:img:p{n:03d}", "kind": "image:page", **base, "region": "", "title": sec,
                  "text": f"{hdr}\n[page image] {summ}", "meta": {"image": str(WORK / "pages" / f"p{n:03d}.png")}})
    with open(WORK / "units.jsonl", "w") as fh:
        for u in U:
            fh.write(json.dumps(u, ensure_ascii=False) + "\n")
    from collections import Counter
    print("units", len(U), dict(Counter(u["kind"] for u in U)))
    return U


def build() -> None:
    import numpy as np
    import torch
    from gemma_index import model
    crops()
    U = units()
    m = model()
    m.max_seq_length = 1024
    t0 = time.time()
    txt = [i for i, u in enumerate(U) if not u["kind"].startswith("image:")]
    img = [i for i, u in enumerate(U) if u["kind"].startswith("image:")]
    V = [None] * len(U)
    order = sorted(txt, key=lambda i: len(U[i]["text"]))
    for k in range(0, len(order), 8):
        idx = order[k:k + 8]
        ev = m.encode([U[i]["text"] for i in idx], prompt_name="Document", batch_size=8, normalize_embeddings=True, show_progress_bar=False)
        for i, v in zip(idx, ev):
            V[i] = v
        if k % 200 == 0:
            torch.mps.empty_cache()
            print("text", k, "/", len(order), round(time.time() - t0), "s", flush=True)
    try:
        with M._conn() as c:
            have = {r[0]: (r[1], r[2]) for r in c.execute(
                "SELECT id, meta->>'image', embedding::text FROM dga_units WHERE kind LIKE 'image:%%'").fetchall()}
    except Exception:  # noqa: BLE001  (first build: no table yet)
        have = {}
    for i in list(img):
        h = have.get(U[i]["id"])
        if h and h[0] == U[i]["meta"]["image"] and not REEMBED:
            V[i] = np.array(json.loads(h[1]), dtype=np.float32)
            img.remove(i)
    print("image embeddings reused", sum(v is not None for v in V) - len(txt), "to embed", len(img), flush=True)
    for k in range(0, len(img), 4):
        idx = img[k:k + 4]
        ev = m.encode([{"image": U[i]["meta"]["image"]} for i in idx], batch_size=4, normalize_embeddings=True, show_progress_bar=False)
        for i, v in zip(idx, ev):
            V[i] = v
        if k % 80 == 0:
            torch.mps.empty_cache()
            print("images", k, "/", len(img), round(time.time() - t0), "s", flush=True)
    with M._conn() as c:
        c.execute("CREATE EXTENSION IF NOT EXISTS vector")
        c.execute("""CREATE TABLE IF NOT EXISTS dga_units (id text PRIMARY KEY, kind text, pdf_page int, printed_page text,
                     region text, title text, text text, meta jsonb, embedding vector(768), tsv tsvector)""")
        c.execute("CREATE INDEX IF NOT EXISTS dga_units_tsv ON dga_units USING gin(tsv)")
        c.execute("CREATE INDEX IF NOT EXISTS dga_units_page ON dga_units (pdf_page)")
        ids = [u["id"] for u in U]
        c.execute("DELETE FROM dga_units WHERE id = ANY(%s)", (ids,))
        c.execute("DELETE FROM dga_units WHERE NOT (id = ANY(%s))", (ids,))      # drop units that no longer exist
        with c.cursor() as cur:
            cur.executemany("""INSERT INTO dga_units VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,
                               to_tsvector('english', coalesce(%s,'') || ' ' || %s))""",
                            [(u["id"], u["kind"], u["pdf_page"], u["printed_page"], u["region"], u["title"], u["text"],
                              json.dumps({**u["meta"], "section": u["section"]}, ensure_ascii=False), M._vec(np.asarray(v, dtype=np.float32)),
                              u["title"], nocomma(u["text"])) for u, v in zip(U, V)])
        rows = c.execute("SELECT kind, count(*) FROM dga_units GROUP BY 1 ORDER BY 1").fetchall()
    print("dga_units", rows, round(time.time() - t0), "s", flush=True)
    (WORK / "index_build.json").write_text(json.dumps({"rows": dict(rows), "sec": round(time.time() - t0)}))


def stats() -> None:
    """work/stats.json: pages, per-model pages, tokens, cost, regions/units by kind, verification summary, gaps."""
    from collections import Counter
    log = [json.loads(l) for l in (WORK / "extract_log.jsonl").read_text().splitlines() if l.strip()]
    pages = {int(f.stem[1:]): json.loads(f.read_text()) for f in sorted((WORK / "json").glob("p*.json"))}
    calls = [l for l in log if "error" not in l]
    by_model = Counter(p["model"] for p in pages.values())
    U = [json.loads(l) for l in (WORK / "units.jsonl").read_text().splitlines()] if (WORK / "units.jsonl").exists() else []
    ver = json.loads((WORK / "verify.json").read_text())["summary"] if (WORK / "verify.json").exists() else {}
    missing = [n for n in range(1, 165) if n not in pages]
    out = {
        "document": "Dietary Guidelines for Americans 2020-2025 (USDA & HHS, 9th ed., Dec 2020), 164 PDF pages",
        "pages_processed": len(pages), "pages_missing": missing,
        "pages_by_model": dict(by_model),
        "api_calls": len(calls), "api_errors": [l for l in log if "error" in l],
        "tokens": {"input": sum(l["in"] for l in calls), "output": sum(l["out"] for l in calls)},
        "tokens_by_model": {m: {"in": sum(l["in"] for l in calls if l["model"] == m), "out": sum(l["out"] for l in calls if l["model"] == m),
                                "cost_usd": round(sum(l["cost"] for l in calls if l["model"] == m), 4)} for m in by_model},
        "cost_usd_total_incl_reruns": round(sum(l["cost"] for l in calls), 4),
        "regions_by_kind": dict(Counter(r["kind"] for p in pages.values() for r in p.get("regions", []))),
        "facts": sum(len(p.get("facts", [])) for p in pages.values()),
        "units_by_kind": dict(Counter(u["kind"] for u in U)), "units_total": len(U),
        "verification": ver,
        "low_confidence_pages": sorted([(n, p.get("confidence")) for n, p in pages.items() if (p.get("confidence") or 0) < 0.7]),
        "illegible": {n: p["illegible"] for n, p in pages.items() if p.get("illegible")},
        "corrected_pages": sorted(n for n, p in pages.items() if p.get("corrective_note")),
    }
    (WORK / "stats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("verification", "illegible")}, indent=1))


if __name__ == "__main__":
    {"crops": crops, "units": units, "build": build, "stats": stats}[sys.argv[1]]()
