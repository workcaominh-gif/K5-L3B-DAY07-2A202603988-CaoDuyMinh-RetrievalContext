"""Multimodal query layer over the Kitchen KB: text, image, voice, audio clip (Shazam) and humming.

    python parser/mm_search.py index <work_dir>                 # CLIP-embed page images + video keyframes -> kb_image
    python parser/mm_search.py ask   <work_dir> <query>         # query = text, or a path to .png/.jpg/.wav/.m4a/.mp3/.mp4
    python parser/mm_search.py ask   <work_dir> <hum.wav> --hum

Routing for a file query:
  image  -> CLIP image embedding -> nearest pages / video frames (kb_image); the matching page's text units follow.
  audio  -> 1) fingerprint (audio_search.match): if confident, return video + timestamp + that segment's transcript
            2) otherwise STT (faster-whisper) -> the transcript becomes a text query (voice search)
  --hum  -> melody contour + subsequence DTW (audio_search.hum)
Text queries: dense (bge, kb_cook) + lexical (Postgres full-text, OR of terms) fused by RRF; plus CLIP text->image
(kb_image) so "photo of a burrito-like wrap" can find photo pages and frames.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
DAY6 = Path(__file__).resolve().parents[3] / "Day 6" / "K5-L3B-DAY06-2A202603988-DataIngestion" / "starter"
sys.path.insert(0, str(DAY6))
IMG = {".png", ".jpg", ".jpeg", ".webp"}
TILES = {"tl": (0, 0, .6, .6), "tr": (.4, 0, 1, .6), "bl": (0, .4, .6, 1), "br": (.4, .4, 1, 1), "c": (.2, .2, .8, .8)}
T_WORK = Path("/Volumes/T7 Dev/AI20K/day7/work")
AUD = {".wav", ".m4a", ".mp3", ".mp4", ".ogg", ".flac", ".aac"}
_cache: dict = {}


def _conn():
    import psycopg
    from dotenv import load_dotenv
    load_dotenv(DAY6 / ".env")
    return psycopg.connect(os.environ["DATABASE_URL"])


def _clip():
    if "clip" not in _cache:
        from sentence_transformers import SentenceTransformer
        _cache["clip"] = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
    return _cache["clip"]


def _vec(v) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def index(work: Path) -> None:
    from PIL import Image
    items = []
    man = {r["pdf_page"]: r for r in json.loads((work / "manifest.json").read_text())}
    for png in sorted((work / "pages").glob("p*.png")):
        n = int(png.stem[1:])
        items.append({"id": f"img:cookbook:p{n:03d}", "kind": "page_image", "path": str(png), "pdf_page": n,
                      "recipe": man[n]["recipe"], "page_type": man[n]["type"], "source_id": "cookbook"})
    for vj in sorted((work / "video").glob("*/video.json")):
        v = json.loads(vj.read_text())
        ocr_t = {o["frame"]: o["t"] for o in json.loads((vj.parent / "ocr.json").read_text())}
        seg_of = {f: s for s in v.get("segments", []) for f in s.get("frames", [])}
        for f in sorted((vj.parent / "frames").glob("f_*.jpg")):
            s = seg_of.get(f.name, {})
            t = ocr_t.get(f.name, s.get("t0"))
            items.append({"id": f"img:yt:{v['video_id']}:{f.stem}", "kind": "video_frame", "path": str(f), "source_id": f"yt:{v['video_id']}",
                          "t": t, "link": f"https://youtu.be/{v['video_id']}?t={int(t)}" if t is not None else v.get("url"),
                          "video_title": v.get("title"), "segment": (s.get("visual") or "")[:200]})
    for dj in sorted((work / "video").glob("*/dense.json")):           # 1 fps frames (parser/dense_frames.py)
        vid = dj.parent.name
        title = json.loads((dj.parent / "video.json").read_text()).get("title")
        for r in json.loads(dj.read_text()):
            items.append({"id": f"img:yt:{vid}@{r['t']}", "kind": "video_frame_1s", "path": str(dj.parent / "dense" / r["file"]),
                          "source_id": f"yt:{vid}", "t": r["t"], "link": f"https://youtu.be/{vid}?t={r['t']}", "video_title": title,
                          "ocr": r["ocr"][:300], "dhash": r["dhash"]})
    figs = T_WORK / "pdf_figures.json"                                  # embedded PDF images (parser/pdf_images.py)
    if figs.exists():
        for f in json.loads(figs.read_text()):
            pages = [q["pdf_page"] for q in f["pages"]]
            items.append({"id": f"img:cookbook:fig:x{f['xref']}", "kind": "pdf_figure", "path": str(T_WORK / "pdf_figures" / f["file"]),
                          "source_id": "cookbook", "pdf_page": pages[0], "pages": pages, "ocr": f.get("text_over", ""),
                          "recipe": man[pages[0]]["recipe"], "page_type": man[pages[0]]["type"]})
    # crop tiles: 4 quadrants (60 % of each side) + centre (60 %), so a zoomed-in screenshot can match a sub-region
    tiles = []
    for it in items:
        if it["kind"] in ("page_image", "video_frame_1s"):
            for name, box in TILES.items():
                tiles.append({"id": f"{it['id']}#{name}", "kind": "tile", "path": it["path"], "box": box, "parent": it["id"],
                              "source_id": it["source_id"]})
    m = _clip()

    def load(i):
        im = Image.open(i["path"]).convert("RGB")
        if "box" in i:
            w, h = im.size
            x0, y0, x1, y1 = i["box"]
            im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
        return im
    items = items + tiles
    embs = m.encode([load(i) for i in items], batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    with _conn() as c:
        c.execute("DROP TABLE IF EXISTS kb_image")
        c.execute("CREATE TABLE kb_image (id text PRIMARY KEY, kind text, source_id text, meta jsonb, embedding vector(512))")
        with c.cursor() as cur:
            cur.executemany("INSERT INTO kb_image VALUES (%s,%s,%s,%s,%s::vector)",
                            [(i["id"], i["kind"], i["source_id"], json.dumps(i, ensure_ascii=False), _vec(e)) for i, e in zip(items, embs)])
    print("kb_image", len(items), "items")


def _grams(t: str) -> set:
    """Character trigrams of the normalised text (so a cut-off word like 'uash' still matches 'squash')."""
    t = re.sub(r"[^a-z0-9½¼¾⅛⅓⅔]+", " ", (t or "").lower().replace("l ½", "1 ½"))
    return {w[i:i + 3] for w in t.split() if len(w) >= 3 for i in range(len(w) - 2)}


def _ham(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _ncc_best(img_gray, tmpl_gray) -> float:
    """Max normalised cross-correlation of a template over an image (FFT + integral images), in [-1, 1]."""
    import numpy as np
    from scipy.signal import fftconvolve
    th, tw = tmpl_gray.shape
    H, W = img_gray.shape
    if th > H or tw > W or th < 6 or tw < 6:
        return -1.0
    t = tmpl_gray - tmpl_gray.mean()
    tn = np.sqrt((t ** 2).sum())
    if tn < 0.02 * np.sqrt(th * tw):           # a flat template (no texture) cannot be located by correlation
        return -1.0
    num = fftconvolve(img_gray, t[::-1, ::-1], mode="valid")
    s1 = np.pad(img_gray, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    s2 = np.pad(img_gray ** 2, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    win = lambda S: S[th:, tw:] - S[:-th, tw:] - S[th:, :-tw] + S[:-th, :-tw]
    n = th * tw
    var = win(s2) - win(s1) ** 2 / n
    ok = var > (0.02 ** 2) * n                 # skip near-flat windows (white backgrounds): their NCC is numerically unstable
    if not ok.any():
        return -1.0
    ncc = np.where(ok, num / (np.sqrt(np.where(ok, var, 1.0)) * tn), -1.0)
    return float(np.clip(ncc.max(), -1.0, 1.0))


_GRAY: dict = {}


def template_score(query_img, cand_path: str, width: int = 320) -> float:
    """Best NCC of the query (a screenshot or crop of a frame/page) inside the candidate image, over 10 scales
    (query width = 5 % ... 95 % of the candidate width). Identical pixels -> ~1.0; unrelated -> ~0.3."""
    import numpy as np
    from PIL import Image
    if cand_path not in _GRAY:
        im = Image.open(cand_path).convert("L")
        im = im.resize((width, max(8, round(im.height * width / im.width))))
        _GRAY[cand_path] = np.asarray(im, dtype=np.float32) / 255.0
    g = _GRAY[cand_path]
    q = query_img.convert("L")
    best = -1.0
    # crop detection only: the query is 5-60 % of the candidate's width (whole-image matches are left to CLIP/OCR/hash,
    # where resized whole-image correlation is noise - measured: wrong candidates reach 0.94 on a whole-figure query)
    for f in [round(0.05 * 1.21 ** i, 4) for i in range(14) if 0.05 * 1.21 ** i <= 0.6]:
        tw = max(6, round(width * f))
        th = round(q.height * tw / q.width)
        if th > g.shape[0] or th < 6:
            continue
        t = np.asarray(q.resize((tw, th)), dtype=np.float32) / 255.0
        best = max(best, _ncc_best(g, t))
    return best


_IDX: dict = {}


def _image_index() -> dict:
    """All image vectors + texts in memory (≈4.6k x 512 floats) with trigram document frequencies for IDF."""
    if not _IDX:
        import numpy as np
        with _conn() as c:
            rows = c.execute("SELECT id, kind, meta, embedding::text FROM kb_image").fetchall()
        ids, kinds, metas = [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows]
        V = np.array([json.loads(r[3]) for r in rows], dtype=np.float32)
        texts = {}
        for i, k, m in zip(ids, kinds, metas):
            if k == "page_image":
                texts[i] = (T_WORK / "pages" / f"p{m['pdf_page']:03d}.txt").read_text(encoding="utf-8")
            elif k in ("video_frame_1s", "pdf_figure"):
                texts[i] = m.get("ocr") or ""
        grams = {i: _grams(t) for i, t in texts.items()}
        df: dict = {}
        for g in grams.values():
            for x in g:
                df[x] = df.get(x, 0) + 1
        import math
        N = max(1, len(grams))
        _IDX.update(ids=ids, kinds=kinds, metas=metas, V=V, grams=grams, idf={g: math.log(1 + N / d) for g, d in df.items()})
    return _IDX


_GEM: dict = {}


def _gemma_visual() -> dict:
    """EmbeddingGemma 2 image vectors from kb_mm, keyed by the matching kb_image id (pages, figures, 1 s frames)."""
    if not _GEM:
        import numpy as np
        with _conn() as c:
            rows = c.execute("SELECT id, embedding::text FROM kb_mm WHERE kind LIKE 'image:%'").fetchall()
        _GEM["ids"] = [r[0][3:] for r in rows]                       # "mm:img:..." -> "img:..."
        _GEM["V"] = np.array([json.loads(r[1]) for r in rows], dtype=np.float32)
    return _GEM


def image_query(path: Path, k: int = 5, backend: str | None = None) -> list[dict]:
    """Image -> pages / video moments. Each candidate (a page or a 1-second frame) is scored by
         visual = max CLIP cosine over the whole image and its 5 tiles (quadrants + centre) -> robust to zoomed crops
         text   = IDF-weighted share of the query's OCR trigrams found in the candidate's text (rare text counts more,
                  partial words still match)
         dup    = near-duplicate bonus from dHash (exact screenshots)
       score = visual + 0.6 * text + 0.5 * dup. Scene-change keyframes are skipped (approximate times; 1 s frames
       supersede them). Video hits within 3 s of a better hit of the same video are merged."""
    import numpy as np
    from PIL import Image
    import dense_frames as D
    from ocrmac import ocrmac
    X = _image_index()
    img = Image.open(path).convert("RGB")
    v = _clip().encode([img], normalize_embeddings=True)[0]
    sims = X["V"] @ v
    qg = _grams(" ".join(x[0] for x in ocrmac.OCR(str(path), recognition_level="accurate").recognize() if x[1] > 0.3))
    qw = sum(X["idf"].get(g, 1.0) for g in qg)
    q_hash = D.dhash(img)
    best: dict = {}
    backend = backend or os.environ.get("IMAGE_BACKEND", "clip")
    if backend in ("gemma", "fusion"):              # visual signal from EmbeddingGemma 2 (whole image, no tiles)
        import gemma_index as G
        g = _gemma_visual()
        gs = g["V"] @ G.embed_query(str(path))
        gem = {gid: float(sv) for gid, sv in zip(g["ids"], gs)}
    if backend == "gemma":
        best = gem
    else:
        for idx, (rid, kind, meta) in enumerate(zip(X["ids"], X["kinds"], X["metas"])):
            if kind == "video_frame":
                continue
            parent = meta.get("parent") or rid
            if sims[idx] > best.get(parent, -1):
                best[parent] = float(sims[idx])
    if backend == "fusion":                        # average of the two visual signals (each in its own cosine scale)
        best = {pid: (best.get(pid, 0.0) + gem.get(pid, best.get(pid, 0.0))) / 2 for pid in set(best) | set(gem)}
    meta_of = {rid: {**m, "_kind": kd} for rid, kd, m in zip(X["ids"], X["kinds"], X["metas"]) if kd in ("page_image", "video_frame_1s", "pdf_figure")}
    cands = []
    for pid, vis in best.items():
        meta = meta_of.get(pid)
        if meta is None:
            continue
        txt = (sum(X["idf"].get(g, 1.0) for g in qg & X["grams"].get(pid, set())) / qw) if qw else 0.0
        dup = 0.0
        if meta.get("dhash"):
            h = _ham(q_hash, meta["dhash"])
            dup = (12 - h) / 12 if h <= 12 else 0.0
        if meta["_kind"] == "pdf_figure":   # a figure has no OCR-heavy surroundings: judge it on the picture itself
            txt = min(txt, 0.5)
        cands.append({"id": pid, "kind": meta["_kind"],
                      "score": round(vis + 0.6 * txt + 0.5 * dup, 3), "clip": round(vis, 3), "text_overlap": round(txt, 2),
                      "near_duplicate": round(dup, 2),
                      **{x: meta.get(x) for x in ("pdf_page", "pages", "recipe", "page_type", "t", "link", "video_title", "ocr") if meta.get(x) is not None}})
    cands.sort(key=lambda h: -h["score"])
    # Stage 2 - template re-rank of the top 60: a screenshot or crop of a frame/page has the SAME pixels as the original,
    # so pixel correlation finds it even when it is a tiny part of the frame (embeddings see a different "picture").
    paths = {}
    for h in cands[:60]:
        m_ = meta_of[h["id"]]
        if h["kind"] == "video_frame_1s":
            vid = re.search(r"img:yt:([\w-]{11})@", h["id"]).group(1)
            paths[h["id"]] = str(T_WORK / "video" / vid / "dense" / f"t_{int(m_['t']):04d}.jpg")
        elif h["kind"] == "page_image":
            paths[h["id"]] = str(T_WORK / "pages" / f"p{m_['pdf_page']:03d}.png")
        elif h["kind"] == "pdf_figure":
            paths[h["id"]] = str(T_WORK / "pdf_figures" / f"x{h['id'].rsplit(':x', 1)[1]}.png")
    import numpy as np
    pool = [h for h in cands[:60] if h["id"] in paths and Path(paths[h["id"]]).exists()]
    for h in pool:
        h["template"] = round(template_score(img, paths[h["id"]]), 3)
    aspect = img.width / max(1, img.height)
    if 0.25 <= aspect <= 4.0:                        # thin strips (e.g. a 6.7:1 banner) correlate with stripes/texture
        for h in pool:                               # measured: true crops 0.90-0.95, best wrong 0.75-0.80
            h["score"] = round(h["score"] + 3.0 * max(0.0, h["template"] - 0.86), 3)
    cands.sort(key=lambda h: -h["score"])
    out = []
    for h in cands:
        if h.get("t") is not None and any(o.get("t") is not None and o["link"].split("?")[0] == h["link"].split("?")[0]
                                          and abs(o["t"] - h["t"]) <= 3 for o in out):
            continue
        if h.get("t") is not None:
            h["t"] = int(h["t"])
        out.append(h)
        if len(out) >= k:
            break
    return out


def image_search(v, k: int = 5) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT id, kind, meta, 1-(embedding<=>%s::vector) FROM kb_image WHERE kind NOT IN ('tile', 'video_frame') "
                         "ORDER BY embedding<=>%s::vector LIMIT %s",
                         (_vec(v), _vec(v), k)).fetchall()
    return [{"id": r[0], "kind": r[1], "score": round(float(r[3]), 3),
             **{x: r[2].get(x) for x in ("pdf_page", "recipe", "page_type", "t", "link", "video_title", "segment") if r[2].get(x) is not None}} for r in rows]


def text_search(q: str, k: int = 5) -> list[dict]:
    """Hybrid: bge dense + Postgres full-text (OR of content words), fused with RRF (k=60)."""
    from src.embeddings import MyEmbedder
    if "bge" not in _cache:
        _cache["bge"] = MyEmbedder("BAAI/bge-small-en-v1.5")
    v = _vec(_cache["bge"].embed_query(q))
    terms = " | ".join(w for w in re.findall(r"[A-Za-z]{3,}", q.lower()) if w not in {"the", "and", "for", "what", "how", "many", "much", "does", "with", "which"})
    with _conn() as c:
        dense = c.execute("SELECT id FROM kb_cook ORDER BY embedding<=>%s::vector LIMIT 30", (v,)).fetchall()
        lex = c.execute("SELECT id FROM kb_cook, to_tsquery('english', %s) q WHERE tsv @@ q ORDER BY ts_rank_cd(tsv, q) DESC LIMIT 30",
                        (terms or "zzz",)).fetchall()
        rrf: dict = {}
        for lst in (dense, lex):
            for rank, (i,) in enumerate(lst, 1):
                rrf[i] = rrf.get(i, 0) + 1 / (60 + rank)
        top = sorted(rrf, key=rrf.get, reverse=True)[:k]
        rows = {r[0]: r for r in c.execute("SELECT id, kind, text, meta FROM kb_cook WHERE id = ANY(%s)", (top,)).fetchall()}
    return [{"id": i, "kind": rows[i][1], "rrf": round(rrf[i], 4), "text": rows[i][2][:240],
             **{x: rows[i][3].get(x) for x in ("pdf_page", "recipe", "link", "t0") if rows[i][3].get(x) is not None}} for i in top]


def segment_at(work: Path, vid: str, t: float) -> dict | None:
    v = json.loads((work / "video" / vid / "video.json").read_text())
    return next((s for s in v.get("segments", []) if (s.get("t0") or 0) - 1 <= t <= (s.get("t1") or 0) + 1), None)


def audio_query(work: Path, p: Path, force_hum: bool = False) -> dict:
    """One recording, three analyses; the verdict picks the one with real evidence, the others are reported too.
      1. fingerprint (sound from one of the videos) - confident = many aligned hashes, far above the runner-up
      2. speech-to-text (user describes what they want) - kept only if Whisper is confident it is speech
      3. melody (humming) - DTW over key-invariant pitch intervals
    Order: fingerprint > speech > hum (a fingerprint is near-certain; Whisper hallucinates words on pure humming)."""
    import audio_search as A
    from faster_whisper import WhisperModel
    db, y16 = A._db(work), A.load(p, sr=16000)
    fp = A.match(db, A.load(p))
    if "stt" not in _cache:
        _cache["stt"] = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = _cache["stt"].transcribe(y16, vad_filter=True, task="transcribe")
    segs = [s for s in segs if s.no_speech_prob < 0.5 and s.avg_logprob > -0.9]
    transcript = " ".join(s.text.strip() for s in segs).strip()
    hum_hits = A.hum(db, y16)[:3]
    out = {"mode": "audio", "fingerprint": fp, "transcript": transcript, "hum": hum_hits,
           "seconds": round(len(y16) / 16000, 1)}
    if fp.get("confident") and not force_hum:
        seg = segment_at(work, fp["match"], fp["t"])
        out.update(verdict="video_sound", match={"video_id": fp["match"], "t": fp["t"], "link": fp["link"],
                                                  "cite": f"yt:{fp['match']}@{int(fp['t'])}", "segment": seg})
    elif len(transcript.split()) >= 3 and not force_hum:
        out.update(verdict="voice", hits=text_search(transcript))
    elif hum_hits:
        h = hum_hits[0]
        gap = (hum_hits[1]["cost"] - h["cost"]) if len(hum_hits) > 1 else 1.0
        out.update(verdict="hum", match={"video_id": h["video"], "t": h["t_start"], "link": h["link"],
                                         "cite": f"yt:{h['video']}@{int(h['t_start'])}", "cost": h["cost"],
                                         "margin": round(gap, 3), "confident": gap > 0.03,
                                         "segment": segment_at(work, h["video"], h["t_start"])})
    else:
        out.update(verdict="nothing")
    return out


def ask(work: Path, query: str, hum: bool = False, backend: str | None = None) -> dict:
    import audio_search as A
    p = Path(query)
    if p.suffix.lower() in IMG and p.exists():
        from PIL import Image
        return {"mode": "image", "backend": backend or "clip", "hits": image_query(p, backend=backend)}
    if p.suffix.lower() in AUD and p.exists():
        return audio_query(work, p, hum)
    clip_t = _clip().encode([query], normalize_embeddings=True)[0]
    return {"mode": "text", "hits": text_search(query), "image_hits": image_search(clip_t, 3)}


if __name__ == "__main__":
    cmd, work = sys.argv[1], Path(sys.argv[2])
    if cmd == "index":
        index(work)
    else:
        print(json.dumps(ask(work, sys.argv[3], hum="--hum" in sys.argv), indent=1, ensure_ascii=False, default=str))
