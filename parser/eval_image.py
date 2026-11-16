"""Benchmark image -> video moment search on synthetic screenshots.

    python parser/eval_image.py <work_dir> <video_dir> [--crop] [--n 40] [--seed 11] [--tag name]

full (default): whole frame, slightly cropped, rescaled, JPEG q=45 (a phone screenshot of the player)
--crop        : a random 30-55 % region of the frame (someone zooms into part of the screen), JPEG q=45
Hit = top result is the right video with |Δt| <= 2 s (also reported: <= 5 s, right video).
Results are appended to <work>/queries/image_eval_runs.json so before/after runs can be compared.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mm_search as M  # noqa: E402

BACKEND = sys.argv[sys.argv.index("--backend") + 1] if "--backend" in sys.argv else "clip"


def main(work: Path, vdir: Path, crop: bool, n: int, seed: int, tag: str) -> None:
    rng = random.Random(seed)
    dur = {"QhkDOr6kmi4": 140, "eSKtPtW0X2o": 470}
    cases = [(v, rng.uniform(1, dur[v] - 3)) for v in rng.choices(list(dur), weights=[1, 3], k=n)]
    td = Path(tempfile.mkdtemp())
    ok2 = ok5 = okv = 0
    rows = []
    for i, (vid, t) in enumerate(cases):
        f = td / f"q{i}.jpg"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", str(vdir / f"{vid}.mp4"), "-frames:v", "1", str(f)], check=True)
        im = Image.open(f).convert("RGB")
        w, h = im.size
        if crop:
            s = rng.uniform(.30, .55)
            cw, ch = int(w * s), int(h * s * rng.uniform(.8, 1.2))
            x, y = rng.randint(0, w - cw), rng.randint(0, max(0, h - ch))
            im = im.crop((x, y, x + cw, y + ch))
        else:
            im = im.crop((int(w * .04), int(h * .05), int(w * .97), int(h * .95))).resize((int(w * .6), int(h * .55)))
        im.save(f, quality=45)
        top = M.image_query(f, k=1, backend=BACKEND)[0]
        same = (top.get("link") or "").startswith(f"https://youtu.be/{vid}") and top.get("t") is not None
        d = abs(top["t"] - t) if same else None
        okv += same
        ok2 += d is not None and d <= 2
        ok5 += d is not None and d <= 5
        rows.append({"video": vid, "t": round(t, 1), "top": top["id"], "dt": None if d is None else round(d, 1)})
    res = {"tag": tag, "backend": BACKEND, "mode": "crop" if crop else "full", "n": n, "seed": seed, "right_video": okv, "hit_2s": ok2, "hit_5s": ok5,
           "time": time.strftime("%Y-%m-%d %H:%M"), "misses": [r for r in rows if r["dt"] is None or r["dt"] > 2][:15]}
    p = work / "queries" / "image_eval_runs.json"
    runs = json.loads(p.read_text()) if p.exists() else []
    runs.append(res)
    p.write_text(json.dumps(runs, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"[{tag}] {BACKEND} {res['mode']}: right video {okv}/{n} · ±2 s {ok2}/{n} · ±5 s {ok5}/{n}")


if __name__ == "__main__":
    a = sys.argv
    main(Path(a[1]), Path(a[2]), "--crop" in a, int(a[a.index("--n") + 1]) if "--n" in a else 40,
         int(a[a.index("--seed") + 1]) if "--seed" in a else 11, a[a.index("--tag") + 1] if "--tag" in a else "run")
