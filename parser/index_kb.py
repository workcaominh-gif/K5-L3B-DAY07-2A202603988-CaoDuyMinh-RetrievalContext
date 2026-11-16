"""Indexing + Storage (slide 7): vector store (pgvector), graph store (Postgres edges table), object store (URIs).

    python parser/index_kb.py <work_dir>        # needs DATABASE_URL (Day 6 Postgres) and the Day 6 venv

Tables (same Postgres as Day 6, new tables, Day 6 tables untouched):
  kb_cook   (id, kind, source_id, text, meta jsonb, tsv tsvector, embedding vector(384))
            kind = page | fact | video_segment | package (wiki / SOP / FAQ / glossary sections)
            embedding = BAAI/bge-small-en-v1.5 (same model + document handling as Day 6), tsv for BM25-style lexical search
  kg_edges  (s, rel, o, attrs jsonb, source)
Object store: page images, video frames and HTML stay on disk; meta.object holds obj:// URIs that map to
/Volumes/T7 Dev/AI20K/day7/work/... (pages/pNNN.png, video/<id>/frames/f_###.jpg).
Re-running replaces both tables (idempotent).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DAY6 = Path(__file__).resolve().parents[3] / "Day 6" / "K5-L3B-DAY06-2A202603988-DataIngestion" / "starter"
sys.path.insert(0, str(DAY6))


def package_units(work: Path) -> list[dict]:
    """Split compiled knowledge packages into sections (one unit per ## heading / FAQ item)."""
    units = []
    pk = work / "kb" / "packages"
    for md in sorted(pk.glob("**/*.md")):
        text = md.read_text(encoding="utf-8")
        front = {}
        if text.startswith("---"):
            _, fm, text = text.split("---", 2)
            front = {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in fm.splitlines() if ":" in l)}
        title = front.get("recipe") or md.stem
        for k, sec in enumerate(re.split(r"\n(?=## )", text)):
            if len(sec.strip()) > 40:
                units.append({"id": f"pkg:{md.stem}:{k:02d}", "kind": "package", "source_id": f"pkg:{md.parent.name}/{md.stem}",
                              "text": f"{title}\n{sec.strip()}", "package": md.parent.name if md.parent != pk else md.stem,
                              "recipe": front.get("recipe")})
    faq = pk / "faq.json"
    if faq.exists():
        for k, x in enumerate(json.loads(faq.read_text(encoding="utf-8"))):
            units.append({"id": f"pkg:faq:{k:03d}", "kind": "package", "source_id": "pkg:faq", "package": "faq",
                          "text": f"Q: {x['q']}\nA: {x['a']}", "citations": x.get("citations"), "faq_type": x.get("type")})
    return units


def main(work: Path) -> None:
    from dotenv import load_dotenv
    import psycopg
    from src.embeddings import MyEmbedder
    load_dotenv(DAY6 / ".env")
    units = [json.loads(l) for l in (work / "kb" / "units.jsonl").read_text(encoding="utf-8").splitlines()]
    units += package_units(work)
    for u in units:
        if u.get("pdf_page"):
            u["object"] = f"obj://cookbook/pages/p{u['pdf_page']:03d}.png"
    edges = [json.loads(l) for l in (work / "kb" / "kg_edges.jsonl").read_text(encoding="utf-8").splitlines()]
    emb = MyEmbedder("BAAI/bge-small-en-v1.5")
    vecs = emb.embed_documents([u["text"] for u in units])
    with psycopg.connect(os.environ["DATABASE_URL"]) as c:
        c.execute("DROP TABLE IF EXISTS kb_cook; DROP TABLE IF EXISTS kg_edges;")
        c.execute("""CREATE TABLE kb_cook (id text PRIMARY KEY, kind text, source_id text, text text, meta jsonb,
                     tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED, embedding vector(384))""")
        c.execute("CREATE INDEX kb_cook_tsv ON kb_cook USING gin (tsv)")
        c.execute("CREATE TABLE kg_edges (s text, rel text, o text, attrs jsonb, source text)")
        with c.cursor() as cur:
            cur.executemany("INSERT INTO kb_cook (id, kind, source_id, text, meta, embedding) VALUES (%s,%s,%s,%s,%s,%s::vector)",
                            [(u["id"], u["kind"], u.get("source_id"), u["text"],
                              json.dumps({k: v for k, v in u.items() if k not in ("id", "kind", "source_id", "text")}, ensure_ascii=False),
                              "[" + ",".join(f"{x:.6f}" for x in v) + "]") for u, v in zip(units, vecs)])
            cur.executemany("INSERT INTO kg_edges VALUES (%s,%s,%s,%s,%s)",
                            [(e["s"], e["rel"], str(e["o"]), json.dumps(e.get("attrs") or {}, ensure_ascii=False), e["source"]) for e in edges])
        n = c.execute("SELECT kind, count(*) FROM kb_cook GROUP BY 1 ORDER BY 1").fetchall()
    print("kb_cook", n, "kg_edges", len(edges), "dims", emb.dimensions)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
