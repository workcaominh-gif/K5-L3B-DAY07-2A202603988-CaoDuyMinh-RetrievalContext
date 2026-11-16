"""Search over dga_units (Dietary Guidelines 2020-2025).

    python parser/dga_search.py "<query>" [method] [k]      # method: lexical | dense | hybrid | dense_mm (default hybrid)
    python parser/dga_search.py --page 90
    python parser/dga_search.py --region dga:p090:r1

search(query, method, k) -> [{id, kind, pdf_page, printed_page, region, title, text, crop, score}]
  lexical   Postgres full-text (english), OR of query terms, ts_rank_cd          (text units only)
  dense     EmbeddingGemma 2 "SearchQuery" prompt, cosine, text units only
  hybrid    RRF(dense, lexical), k_rrf = 60, 50 candidates per list
  dense_mm  EmbeddingGemma 2 over text + image rows (image:crop, image:page): text queries can hit visuals
get_page(n)      -> page record: units of the page, JSON extraction (html, facts, regions), page image path
get_region(id)   -> region data (table rows / chart points incl. geometry values / image elements) + crop path + bbox
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mm_search as M  # noqa: E402

WORK = Path("/Volumes/T7 Dev/AI20K/day7/dga/work")
COLS = "id, kind, pdf_page, printed_page, region, title, text, meta"
STOP = set("a an and are as at be by for from how in is it of on or that the this to was what when which who with does do per".split())


def _row(r, score) -> dict:
    meta = r[7] or {}
    return {"id": r[0], "kind": r[1], "pdf_page": r[2], "printed_page": r[3], "region": r[4], "title": r[5], "text": r[6],
            "crop": meta.get("crop") or meta.get("image"), "bbox_pt": meta.get("bbox_pt"), "score": round(float(score), 4)}


def lexical(q: str, k: int = 10) -> list[dict]:
    q = re.sub(r"(?<=\d),(?=\d{3})", "", q)
    terms = [t for t in re.findall(r"[A-Za-z0-9]+", q.lower()) if t not in STOP]
    if not terms:
        return []
    with M._conn() as c:
        rows = c.execute(f"""WITH q AS (SELECT to_tsquery('english', %s) AS tq)
            SELECT {COLS}, ts_rank_cd(tsv, q.tq) FROM dga_units, q
            WHERE kind NOT LIKE 'image:%%' AND tsv @@ q.tq ORDER BY 9 DESC LIMIT %s""",
                         (" | ".join(terms), k)).fetchall()
    return [_row(r, r[8]) for r in rows]


def _dense(q: str, k: int, mm: bool) -> list[dict]:
    from gemma_index import embed_query
    v = M._vec(embed_query(q))
    where = "" if mm else "WHERE kind NOT LIKE 'image:%%'"
    with M._conn() as c:
        rows = c.execute(f"SELECT {COLS}, 1-(embedding<=>%s::vector) FROM dga_units {where} ORDER BY embedding<=>%s::vector LIMIT %s",
                         (v, v, k)).fetchall()
    return [_row(r, r[8]) for r in rows]


def dense(q: str, k: int = 10) -> list[dict]:
    return _dense(q, k, False)


def dense_mm(q: str, k: int = 10) -> list[dict]:
    return _dense(q, k, True)


def hybrid(q: str, k: int = 10, n: int = 50, krrf: int = 60) -> list[dict]:
    lists = [dense(q, n), lexical(q, n)]
    score, rec = {}, {}
    for L in lists:
        for i, h in enumerate(L):
            score[h["id"]] = score.get(h["id"], 0) + 1 / (krrf + i + 1)
            rec.setdefault(h["id"], h)
    return [{**rec[i], "score": round(s, 5)} for i, s in sorted(score.items(), key=lambda t: -t[1])[:k]]


METHODS = {"lexical": lexical, "dense": dense, "hybrid": hybrid, "dense_mm": dense_mm}


def search(query: str, method: str = "hybrid", k: int = 10) -> list[dict]:
    return METHODS[method](query, k)


def get_page(n: int) -> dict:
    jf = WORK / "json" / f"p{int(n):03d}.json"
    page = json.loads(jf.read_text()) if jf.exists() else {}
    with M._conn() as c:
        rows = c.execute(f"SELECT {COLS} FROM dga_units WHERE pdf_page=%s AND kind NOT LIKE 'image:%%' ORDER BY id", (int(n),)).fetchall()
    return {"pdf_page": int(n), "printed_page": page.get("printed_page"), "section": page.get("section"),
            "html": page.get("html"), "facts": page.get("facts", []),
            "regions": [{"id": r["id"], "kind": r["kind"], "title": r["title"], "summary": r["summary"]} for r in page.get("regions", [])],
            "page_image": str(WORK / "pages" / f"p{int(n):03d}.png"), "units": [_row(r + (0,), 0) for r in rows]}


def get_region(rid: str) -> dict:
    """rid: 'dga:p090:r1' (unit id), 'dga:img:p090:r1' or 'p090:r1' / (90, 'r1')."""
    m = re.search(r"p(\d{3})[:_](r\d+)", rid)
    if not m:
        return {"error": f"bad region id {rid}"}
    n, reg = int(m.group(1)), m.group(2)
    page = json.loads((WORK / "json" / f"p{n:03d}.json").read_text())
    r = next((x for x in page["regions"] if x["id"] == reg), None)
    if r is None:
        return {"error": f"no region {reg} on PDF page {n}"}
    regs = {(x["pdf_page"], x["region"]): x for x in json.loads((WORK / "regions.json").read_text())}
    g = regs.get((n, reg), {})
    return {"id": f"dga:p{n:03d}:{reg}", "pdf_page": n, "printed_page": page.get("printed_page"), "kind": r["kind"],
            "title": r["title"], "summary": r["summary"], "alt": r["alt"], "data": r["data"],
            "crop": g.get("crop"), "bbox_pt": g.get("bbox_pt"), "bbox_px_150dpi": g.get("bbox_px_150dpi")}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--page":
        print(json.dumps(get_page(int(a[1])), ensure_ascii=False, indent=1)[:4000])
    elif a[0] == "--region":
        print(json.dumps(get_region(a[1]), ensure_ascii=False, indent=1)[:4000])
    else:
        for h in search(a[0], a[1] if len(a) > 1 else "hybrid", int(a[2]) if len(a) > 2 else 8):
            print(h["score"], h["id"], h["kind"], f"p.{h['printed_page']} (pdf {h['pdf_page']})", (h["title"] or "")[:70], "|", h["crop"] or "")
