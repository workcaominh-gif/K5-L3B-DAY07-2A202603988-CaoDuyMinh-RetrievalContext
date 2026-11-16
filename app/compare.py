"""Side-by-side retrieval comparison for the web UI ("So sánh truy xuất" tab).

Two corpora, each with the exact methods its benchmark measured:
  kitchen  Kitchen KB (USDA cookbook + 2 videos), app/retrieval.py METHODS; gold = FAQ citations (parser/eval_text.py hit)
  day6     Day 6 EU AI Act + GDPR store, eval/run_day6.py Day6 methods; gold = Day 6 is_hit (doc + page + full quote)
A run returns top-k per method with hit flags (when a benchmark question is picked), latency and Claude cost.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "parser"))
sys.path.insert(0, str(ROOT / "eval"))
WORK = Path("/Volumes/T7 Dev/AI20K/day7/work")
HAIKU_PRICE = (0.10, 0.50)                      # USD / MTok in, out (same as eval/run_day6.py PRICE)
LLM = {"hybrid_rerank", "rewrite"}
_lock = threading.Lock()                        # Day6 holds one psycopg connection + BM25; runs are serialised
_day6 = None

DAY6_METHODS = {
    "dense": "Dense · bge-small (baseline Day 6)",
    "bm25": "BM25 · Okapi",
    "hybrid": "Hybrid · RRF(dense, BM25)",
    "hybrid_rerank": "Hybrid + rerank · Claude Haiku 5.5",
    "rewrite": "Query rewrite ×3 · Haiku 5.5 → hybrid → RRF",
    "dense_gemma": "Dense · EmbeddingGemma-300m (cấu hình khoá)",
}


def _faq() -> list[dict]:
    import eval_text as E
    out = []
    for i, it in enumerate(json.loads((WORK / "kb" / "packages" / "faq.json").read_text())):
        pages, vids = E.gold_of(it)
        out.append({"id": f"faq{i + 1:02d}", "question": it["q"], "type": it.get("type"), "answer": it.get("a"),
                    "gold": [f"tr.{p}" for p in sorted(pages)] + [f"{v} @{t // 60}:{t % 60:02d}" for v, t in vids]})
    return out


def _day6_questions() -> list[dict]:
    qs = [json.loads(l) for l in (ROOT / "benchmark/day6_eu/questions.jsonl").read_text().splitlines() if l.strip()]
    return [{"id": q["id"], "split": q["split"], "type": q.get("type"), "question": q["question"],
             "answerable": q.get("answerable", True), "answer": q.get("expected_answer"),
             "gold": [f"{q['gold_source_id']} tr.{q['gold_page']}"] if q.get("answerable", True) and q.get("gold_source_id") else []}
            for q in qs]


def meta() -> dict:
    import retrieval as R
    res = ROOT / "eval" / "results"
    kt = json.loads((res / "kitchen" / "text_eval.json").read_text())
    bench = {"kitchen": {"note": kt.get("note"), "n": kt["n"], "rows": {m: {"hit1": v["h1"], "hit3": v["h3"], "hit5": v["h5"]}
                                                                       for m, v in kt["methods"].items()}}}
    for split in ("dev", "test"):
        f = res / f"day6_{split}.json"
        if f.exists():
            d = json.loads(f.read_text())["results"]
            bench[f"day6_{split}"] = {"n": next(iter(d.values()))["n"], "rows": {m: {k: v[k] for k in ("hit1", "hit3", "mrr10", "seconds", "cost_usd")}
                                                                                 for m, v in d.items()}}
    return {"corpora": {
        "kitchen": {"label": "Kitchen KB · sách USDA 148 trang + 2 video", "methods": R.METHODS, "llm": sorted(LLM & set(R.METHODS)),
                    "default": ["dense_bge", "lexical", "hybrid_bge", "dense_gemma"], "questions": _faq()},
        "day6": {"label": "Day 6 · EU AI Act + GDPR (572 trang, phần bắt buộc)", "methods": DAY6_METHODS, "llm": sorted(LLM),
                 "default": ["dense", "bm25", "hybrid", "dense_gemma"], "questions": _day6_questions()}},
        "bench": bench}


def _clip(s: str, n: int = 260) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


def _summary(flags: list[bool]) -> dict:
    rr = next((1 / (i + 1) for i, f in enumerate(flags) if f), 0.0)
    return {"hit1": bool(flags[:1] and flags[0]), "hit3": any(flags[:3]), "rr": round(rr, 3)}


def _kitchen(query: str, methods: list[str], k: int, gold, no_pkg: bool = True) -> list[dict]:
    import retrieval as R
    import eval_text as E
    out = []
    for m in methods:
        t0 = time.time()
        try:
            rows = R.retrieve(query, m, k + 15 if no_pkg else k)
            usage = next((r["rerank_usage"] for r in rows if r.get("rerank_usage")), (0, 0))
            err = next((r["rerank_error"] for r in rows if r.get("rerank_error")), None)
            if no_pkg:                                          # the FAQ benchmark excludes packages (FAQ was written from them)
                rows = [r for r in rows if r["kind"] not in ("package", "text:package")][:k]
        except Exception as e:                                  # one method failing must not hide the others
            out.append({"method": m, "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        ms = int((time.time() - t0) * 1000)
        items = []
        for r in rows:
            mt = r.get("meta") or {}
            pg, t = mt.get("pdf_page"), mt.get("t") if mt.get("t") is not None else mt.get("t0")
            vid = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", mt.get("link") or "")
            where = f"tr.{pg}" if pg else (f"video {vid.group(1)[:4]}… @{int(t) // 60}:{int(t) % 60:02d}" if vid and t is not None else r["kind"])
            thumb = (f"/media/page/{pg}" if pg else f"/media/still/{vid.group(1)}/{int(t)}" if vid and t is not None else None)
            items.append({"id": r["id"], "kind": r["kind"], "where": where, "text": _clip(r["text"]), "thumb": thumb,
                          "rerank": r.get("rerank"), "hit": E.hit(mt, *gold) if gold else None})
        cost = (usage[0] * HAIKU_PRICE[0] + usage[1] * HAIKU_PRICE[1]) / 1e6
        out.append({"method": m, "ms": ms, "cost_usd": round(cost, 5), "items": items, **({"warning": "Rerank lỗi, đang hiện thứ tự hybrid: " + err} if err else {}),
                    **(_summary([i["hit"] for i in items]) if gold else {})})
    return out


def _day6_run(query: str, methods: list[str], k: int, q: dict | None) -> list[dict]:
    global _day6
    import run_day6 as D
    if _day6 is None:
        _day6 = D.Day6()
    st = _day6
    flt = (q or {}).get("filter")
    fns = {"dense": lambda: (st.dense(query, flt), None), "bm25": lambda: (st.bm25_ids(query, flt), None),
           "hybrid": lambda: (st.hybrid(query, flt), None), "hybrid_rerank": lambda: (st.rerank(query, flt), None),
           "rewrite": lambda: st.rewrite(query, flt), "dense_gemma": lambda: (st.gemma(query, flt), None)}
    out = []
    for m in methods:
        u0, t0 = list(st.usage), time.time()
        try:
            ids, extra = fns[m]()
        except Exception as e:
            out.append({"method": m, "error": f"{type(e).__name__}: {e}"[:200]})
            continue
        ms = int((time.time() - t0) * 1000)
        cost = ((st.usage[0] - u0[0]) * D.PRICE[0] + (st.usage[1] - u0[1]) * D.PRICE[1]) / 1e6
        flags = [D.is_hit(q, {**st.chunks[c], "page_end": st.chunks[c]["page_end"] or st.chunks[c]["page"]}) for c in ids[:10]] \
            if q and q.get("answerable", True) else None
        items = []
        for j, c in enumerate(ids[:k]):
            ch = st.chunks[c]
            art = ch.get("article") or ch.get("annex")
            items.append({"id": c, "kind": ch["document_id"], "text": _clip(ch["text"]), "thumb": None,
                          "where": f"{ch['document_id']} tr.{ch['page']}" + (f" · {art}" if art else ""),
                          "hit": flags[j] if flags else None})
        out.append({"method": m, "ms": ms, "cost_usd": round(cost, 5), "items": items,
                    **({"queries": extra} if extra else {}), **(_summary(flags) if flags else {})})
    return out


def run(corpus: str, qid: str | None, text: str | None, methods: list[str], k: int = 5, no_pkg: bool = True) -> dict:
    k = max(1, min(10, int(k)))
    if corpus == "kitchen":
        import retrieval as R
        methods = [m for m in methods if m in R.METHODS]
        q = next((x for x in _faq() if x["id"] == qid), None) if qid else None
        query = q["question"] if q else (text or "").strip()
    elif corpus == "day6":
        methods = [m for m in methods if m in DAY6_METHODS]
        raw = [json.loads(l) for l in (ROOT / "benchmark/day6_eu/questions.jsonl").read_text().splitlines() if l.strip()]
        q = next((x for x in raw if x["id"] == qid), None) if qid else None
        query = q["question"] if q else (text or "").strip()
    else:
        raise ValueError("unknown corpus")
    if not query or len(query) > 500:
        raise ValueError("empty or too long query")
    if not methods:
        raise ValueError("no method selected")
    with _lock:
        if corpus == "kitchen":
            gold = None
            if q:
                import eval_text as E
                item = json.loads((WORK / "kb" / "packages" / "faq.json").read_text())[int(qid[3:]) - 1]
                gold = E.gold_of(item)
            cols = _kitchen(query, methods, k, gold, no_pkg)
        else:
            cols = _day6_run(query, methods, k, q)
    return {"corpus": corpus, "query": query, "qid": qid if q else None, "graded": bool(q and q.get("answerable", True)),
            "answerable": (q or {}).get("answerable", True), "columns": cols}
