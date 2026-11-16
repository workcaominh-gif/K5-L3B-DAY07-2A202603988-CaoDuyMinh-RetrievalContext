"""Verify the exact second each on-screen ingredient-card item appears (the VLM's times can be ~1 s early).

    python parser/card_times.py <work_dir> <video_dir>

For every video whose facts contain "Full recipe from the on-screen card", OCR one frame per second (Apple Vision) from
the card's first timestamp up to +60 s and record the first second each item is visible.
Writes <work>/video/<id>/card_times.json  {item: seconds}; enrich.py prefers these over the VLM's times.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9½¼¾⅛⅓⅔]+", "", s.lower().replace("•", ""))


def main(work: Path, vdir: Path) -> None:
    from ocrmac import ocrmac
    for vj in sorted((work / "video").glob("*/video.json")):
        v = json.loads(vj.read_text())
        card = next((f for f in v.get("facts", []) if "Full recipe from the on-screen card" in f), None)
        if not card:
            continue
        m = re.search(r"\((\d{1,2}):(\d{2})", card)
        start = int(m.group(1)) * 60 + int(m.group(2))
        items = card.rsplit(": ", 1)[1].rstrip(".").split(", ")
        found: dict = {}
        with tempfile.TemporaryDirectory() as td:
            for t in range(max(0, start - 3), start + 60):
                f = Path(td) / f"{t}.jpg"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(vdir / f"{v['video_id']}.mp4"),
                                "-frames:v", "1", str(f)], check=True)
                text = norm(" ".join(x[0] for x in ocrmac.OCR(str(f)).recognize()))
                for it in items:
                    key = norm(re.sub(r"^\d+\s*", "", it))          # match without the leading number (OCR splits it)
                    if it not in found and key and key in text:
                        found[it] = t
                if len(found) == len(items):
                    break
        (vj.parent / "card_times.json").write_text(json.dumps(found, indent=1, ensure_ascii=False), encoding="utf-8")
        print(v["video_id"], found, "missing:", [i for i in items if i not in found])


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
