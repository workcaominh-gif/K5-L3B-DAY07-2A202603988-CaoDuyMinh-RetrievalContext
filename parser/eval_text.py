"""Text retrieval A/B on the 48 FAQ questions (6 types x 8): which retrieval method puts the cited evidence on top?

    python parser/eval_text.py <work_dir>

Gold = the FAQ item's citations: cookbook pages ("[cookbook p.12]") and video moments ("...?t=21"). A retrieved item
is a HIT if it points to a gold page (pdf_page, or any page of a reused figure) or to the gold video within ±10 s.
Methods (same corpus units; only the ranker changes):
  dense_bge      bge-small cosine on kb_cook                   (Day 6 model)
  lexical        Postgres full-text, OR of content words, ts_rank_cd
  hybrid_bge     RRF(dense_bge, lexical)                        (current app)
  dense_gemma    EmbeddingGemma 2 on the text units of kb_mm
  hybrid_gemma   RRF(dense_gemma, lexical)
  gemma_all      EmbeddingGemma 2 over ALL modalities in kb_mm (text + page images + figures + frames + audio)
Caveat: the FAQ was written by an LLM from these same units, so absolute scores are optimistic; the comparison
between methods on identical questions is what this measures. Writes <work>/queries/text_eval.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mm_search as M  # noqa: E402

STOP = {"the", "and", "for", "what", "how", "many", "much", "does", "with", "which", "this", "that", "are", "was", "from", "into", "when", "where"}


def gold_of(item: dict) -> tuple[set, list]:
    pages, vids = set(), []
    for c in item.get("citations", []):
        pages |= {int(x) for x in re.findall(r"cookbook p\.(\d+)", c)}
        for vid, t in re.findall(r"youtu\.be/([A-Za-z0-9_-]{11})\?t=(\d+)", c):
            vids.append((vid, int(t)))
    return pages, vids


def hit(meta: dict, pages: set, vids: list) -> bool:
    ps = set(meta.get("pages") or ([meta["pdf_page"]] if meta.get("pdf_page") else []))
    if ps & pages:
        return True
    link, t = meta.get("link") or "", meta.get("t") if meta.get("t") is not None else meta.get("t0")
    m = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", link)
    return bool(m and t is not None and any(m.group(1) == v and abs(int(t) - gt) <= 10 for v, gt in vids))


def rrf(*lists, k=60):
    sc: dict = {}
    for lst in lists:
        for r, i in enumerate(lst, 1):
            sc[i] = sc.get(i, 0) + 1 / (k + r)
    return sorted(sc, key=sc.get, reverse=True)


def main(work: Path) -> None:
    import gemma_index as G
    from src.embeddings import MyEmbedder
    faq = json.loads((work / "kb" / "packages" / "faq.json").read_text())
    bge = MyEmbedder("BAAI/bge-small-en-v1.5")
    with M._conn() as c:
        meta = {r[0]: r[1] for r in c.execute("SELECT id, meta FROM kb_cook").fetchall()}
        mm_meta = {r[0]: r[1] for r in c.execute("SELECT id, meta FROM kb_mm").fetchall()}
    res = {m: {"h1": 0, "h3": 0, "h5": 0} for m in ("dense_bge", "lexical", "hybrid_bge", "dense_gemma", "hybrid_gemma", "gemma_all")}
    by_type: dict = {}
    for it in faq:
        pages, vids = gold_of(it)
        q = it["q"]
        with M._conn() as c:
            v = M._vec(bge.embed_query(q))
            dense = [r[0] for r in c.execute("SELECT id FROM kb_cook WHERE kind <> 'package' ORDER BY embedding<=>%s::vector LIMIT 30", (v,)).fetchall()]
            terms = " | ".join(w for w in re.findall(r"[a-z]{3,}", q.lower()) if w not in STOP) or "zzz"
            lex = [r[0] for r in c.execute("SELECT id FROM kb_cook, to_tsquery('english', %s) q WHERE tsv @@ q AND kind <> 'package' "
                                           "ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 30", (terms,)).fetchall()]
            gv = M._vec(G.embed_query(q))
            g_text = [r[0][3:] for r in c.execute("SELECT id FROM kb_mm WHERE kind LIKE 'text:%%' AND kind <> 'text:package' "
                                                   "ORDER BY embedding<=>%s::vector LIMIT 30", (gv,)).fetchall()]
            g_all = [r[0] for r in c.execute("SELECT id FROM kb_mm WHERE kind <> 'text:package' ORDER BY embedding<=>%s::vector LIMIT 30", (gv,)).fetchall()]
        ranked = {"dense_bge": [meta[i] for i in dense], "lexical": [meta[i] for i in lex], "hybrid_bge": [meta[i] for i in rrf(dense, lex)],
                  "dense_gemma": [meta[i] for i in g_text], "hybrid_gemma": [meta[i] for i in rrf(g_text, lex)],
                  "gemma_all": [mm_meta[i] for i in g_all]}
        for mname, lst in ranked.items():
            hits = [hit(m_, pages, vids) for m_ in lst[:5]]
            for kk, n in (("h1", 1), ("h3", 3), ("h5", 5)):
                ok = any(hits[:n])
                res[mname][kk] += ok
                if kk == "h3":
                    by_type.setdefault(it["type"], {}).setdefault(mname, 0)
                    by_type[it["type"]][mname] += ok
    N = len(faq)
    out = {"n": N, "note": "packages excluded (FAQ was compiled from them); hit = gold page or gold video ±10 s", "methods": res, "hit3_by_type": by_type}
    (work / "queries" / "text_eval.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"{'method':14} Hit@1   Hit@3   Hit@5   (n={N})")
    for mname, r in res.items():
        print(f"{mname:14} {r['h1']:2}/{N}  {r['h3']:2}/{N}  {r['h5']:2}/{N}")
    print("Hit@3 by question type:", json.dumps(by_type))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
