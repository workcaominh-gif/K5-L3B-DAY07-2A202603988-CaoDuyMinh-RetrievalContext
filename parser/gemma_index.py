"""One multimodal index with EmbeddingGemma 2 (google/embeddinggemma-2, Apache 2.0): text, images and audio share one
768-d space, so any input can retrieve any modality.

    python parser/gemma_index.py build <work_dir> <video_dir>      # -> Postgres table kb_mm
    python parser/gemma_index.py query <work_dir> <text | image path | audio path> [k]

Items (all with the same metadata conventions as kb_cook / kb_image so the agent tools can cite them):
  text   every unit of kb_cook (pages, facts, video segments, packages)        prompt: Document (title: none)
  image  148 page images, every embedded PDF figure, every 1-second video frame  (no prompt for media)
  audio  5-second windows with 2.5-second hop over both videos (16 kHz mono)
Queries: text -> prompt "SearchQuery"; images / audio -> no prompt (per the model card).
Model card notes honoured: float32 (fp16 can produce NaNs), L2-normalised vectors, cosine similarity.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mm_search as M  # noqa: E402

MODEL = "google/embeddinggemma-2"
_m = None


def model():
    global _m
    if _m is None:
        import torch
        from sentence_transformers import SentenceTransformer
        _m = SentenceTransformer(MODEL, model_kwargs={"torch_dtype": torch.float32})
    return _m


def _norm(x) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    return x / np.linalg.norm(x, axis=-1, keepdims=True)


def audio_windows(mp4: Path, win: float = 5.0, hop: float = 2.5) -> list[tuple[float, np.ndarray]]:
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(pcm, dtype=np.float32)
    n, h = int(win * 16000), int(hop * 16000)
    return [(round(s / 16000, 1), y[s:s + n]) for s in range(0, max(1, len(y) - n + 1), h)]


def build(work: Path, vdir: Path) -> None:
    m = model()
    items: list[dict] = []
    vecs: list[np.ndarray] = []
    t0 = time.time()
    # text: reuse the exact units of kb_cook
    with M._conn() as c:
        rows = c.execute("SELECT id, kind, source_id, text, meta FROM kb_cook").fetchall()
    import torch
    m.max_seq_length = 1024                     # whole-page units can be ~6k chars; cap to keep MPS memory bounded
    order = sorted(range(len(rows)), key=lambda i: len(rows[i][3]))      # similar lengths per batch = less padding
    tv = [None] * len(rows)
    for i in range(0, len(order), 8):
        idx = order[i:i + 8]
        ev = m.encode([rows[j][3] for j in idx], prompt_name="Document", batch_size=8, normalize_embeddings=True, show_progress_bar=False)
        for j, v in zip(idx, ev):
            tv[j] = v
        if i % 800 == 0 and hasattr(torch, "mps"):
            torch.mps.empty_cache()
    for r, v in zip(rows, tv):
        items.append({"id": "mm:" + r[0], "kind": "text:" + r[1], "source_id": r[2], "meta": {**r[4], "text": r[3][:400], "unit_id": r[0]}})
        vecs.append(v)
    print("text", len(rows), round(time.time() - t0), "s", flush=True)
    if hasattr(torch, "mps"):
        torch.mps.empty_cache()
    # images: pages, PDF figures, 1-second frames
    man = {r["pdf_page"]: r for r in json.loads((work / "manifest.json").read_text())}
    imgs = [(f"mm:img:cookbook:p{n:03d}", "image:page", "cookbook", str(work / "pages" / f"p{n:03d}.png"),
             {"pdf_page": n, "recipe": man[n]["recipe"], "page_type": man[n]["type"]}) for n in sorted(man)]
    figs = json.loads((work / "pdf_figures.json").read_text()) if (work / "pdf_figures.json").exists() else []
    imgs += [(f"mm:img:cookbook:fig:x{f['xref']}", "image:figure", "cookbook", str(work / "pdf_figures" / f["file"]),
              {"pdf_page": f["pages"][0]["pdf_page"], "pages": [q["pdf_page"] for q in f["pages"]], "ocr": f.get("text_over", ""),
               "recipe": man[f["pages"][0]["pdf_page"]]["recipe"]}) for f in figs]
    for dj in sorted((work / "video").glob("*/dense.json")):
        vid = dj.parent.name
        for r in json.loads(dj.read_text()):
            imgs.append((f"mm:img:yt:{vid}@{r['t']}", "image:frame", f"yt:{vid}", str(dj.parent / "dense" / r["file"]),
                         {"t": r["t"], "link": f"https://youtu.be/{vid}?t={r['t']}", "ocr": r["ocr"][:300], "dhash": r["dhash"]}))
    for i in range(0, len(imgs), 4):
        batch = imgs[i:i + 4]
        ev = m.encode([{"image": p} for _, _, _, p, _ in batch], batch_size=4, normalize_embeddings=True, show_progress_bar=False)
        for (iid, kind, src, _p, meta), v in zip(batch, ev):
            items.append({"id": iid, "kind": kind, "source_id": src, "meta": meta})
            vecs.append(v)
        if i % 160 == 0:
            torch.mps.empty_cache() if hasattr(torch, "mps") else None
            print("images", i + len(batch), "/", len(imgs), round(time.time() - t0), "s", flush=True)
    # audio windows
    for mp4 in sorted(vdir.glob("*.mp4")):
        vid = mp4.stem
        wins = audio_windows(mp4)
        for i in range(0, len(wins), 8):
            batch = wins[i:i + 8]
            ev = m.encode([{"text": "<|audio|>", "audio": [a]} for _, a in batch], batch_size=8, normalize_embeddings=True, show_progress_bar=False)
            for (t, _a), v in zip(batch, ev):
                items.append({"id": f"mm:aud:yt:{vid}@{t}", "kind": "audio:window", "source_id": f"yt:{vid}",
                              "meta": {"t": int(t), "t_end": int(t + 5), "link": f"https://youtu.be/{vid}?t={int(t)}"}})
                vecs.append(v)
        print("audio", vid, len(wins), "windows", round(time.time() - t0), "s", flush=True)
    V = _norm(np.vstack(vecs))
    with M._conn() as c:
        c.execute("DROP TABLE IF EXISTS kb_mm")
        c.execute("CREATE TABLE kb_mm (id text PRIMARY KEY, kind text, source_id text, meta jsonb, embedding vector(768))")
        with c.cursor() as cur:
            cur.executemany("INSERT INTO kb_mm VALUES (%s,%s,%s,%s,%s::vector)",
                            [(it["id"], it["kind"], it["source_id"], json.dumps(it["meta"], ensure_ascii=False), M._vec(v)) for it, v in zip(items, V)])
        n = c.execute("SELECT kind, count(*) FROM kb_mm GROUP BY 1 ORDER BY 1").fetchall()
    print("kb_mm", n, round(time.time() - t0), "s total", flush=True)


def embed_query(q: str) -> np.ndarray:
    m, p = model(), Path(q)
    if p.suffix.lower() in M.IMG and p.exists():
        return _norm(m.encode({"image": str(p)}))
    if p.suffix.lower() in M.AUD and p.exists():
        from audio_search import load
        return _norm(m.encode({"text": "<|audio|>", "audio": [load(p, sr=16000)]}))
    return _norm(m.encode(q, prompt_name="SearchQuery"))


def search(q: str, k: int = 8, kinds: tuple[str, ...] | None = None) -> list[dict]:
    v = embed_query(q)
    sql, args = "SELECT id, kind, meta, 1-(embedding<=>%s::vector) FROM kb_mm", [M._vec(v)]
    if kinds:
        sql += " WHERE kind = ANY(%s)"
        args.append(list(kinds))
    with M._conn() as c:
        rows = c.execute(sql + " ORDER BY embedding<=>%s::vector LIMIT %s", args + [M._vec(v), k]).fetchall()
    return [{"id": r[0], "kind": r[1], "score": round(float(r[3]), 3), **{x: r[2].get(x) for x in ("pdf_page", "pages", "t", "link", "recipe", "text") if r[2].get(x) is not None}} for r in rows]


if __name__ == "__main__":
    cmd, work = sys.argv[1], Path(sys.argv[2])
    if cmd == "build":
        build(work, Path(sys.argv[3]))
    else:
        for h in search(sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8):
            print(h)
