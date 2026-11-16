"""Dense video frame index: one frame per second, with OCR text and a perceptual hash.

    python parser/dense_frames.py <work_dir> <video_dir>

Why: scene-change keyframes (ffmpeg select=gt(scene,0.12)) miss slides that fade in over the same layout - e.g. the
"1 ½ cups of corn = 3 half cups of corn" card at 3:59 of eSKtPtW0X2o had no keyframe, so an image query landed on a
look-alike blue card. Sampling every second closes the coverage gap; OCR text separates look-alike cards; a
difference hash (dHash, 64 bit) finds the exact frame when the query is a screenshot of the video.

Writes <work>/video/<id>/dense/t_0000.jpg ... and <work>/video/<id>/dense.json [{t, file, ocr, dhash}].
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


def dhash(img: Image.Image, n: int = 8) -> str:
    g = img.convert("L").resize((n + 1, n), Image.LANCZOS)
    px = list(g.getdata())
    bits = "".join("1" if px[r * (n + 1) + c] > px[r * (n + 1) + c + 1] else "0" for r in range(n) for c in range(n))
    return f"{int(bits, 2):016x}"


def main(work: Path, vdir: Path) -> None:
    from ocrmac import ocrmac
    for mp4 in sorted(vdir.glob("*.mp4")):
        vid = mp4.stem
        out = work / "video" / vid / "dense"
        out.mkdir(parents=True, exist_ok=True)
        if not any(out.glob("t_*.jpg")):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf", "fps=1,scale=640:-2", "-q:v", "4",
                            "-start_number", "0", str(out / "t_%04d.jpg")], check=True)
        rows = []
        for f in sorted(out.glob("t_*.jpg")):
            t = int(f.stem[2:])                          # fps=1 with start_number 0: file k is the frame at ~k s
            im = Image.open(f)
            # "accurate" reads small banner text the fast mode skips (e.g. the CACFP banner under a title card)
            text = " ".join(x[0] for x in ocrmac.OCR(str(f), recognition_level="accurate").recognize() if x[1] > 0.3)
            rows.append({"t": t, "file": f.name, "ocr": text, "dhash": dhash(im)})
        (work / "video" / vid / "dense.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        print(vid, len(rows), "frames,", sum(bool(r["ocr"]) for r in rows), "with text")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
