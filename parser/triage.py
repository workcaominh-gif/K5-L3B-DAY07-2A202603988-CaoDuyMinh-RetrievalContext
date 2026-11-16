"""Stage 0 of the parser: per-page triage. Decides which route each PDF page needs.

    python parser/triage.py <pdf> <out_dir>

Signals per page (cheap, no model calls):
  chars          characters in the text layer (0 -> scanned / outlined text -> OCR route)
  words_ok       share of text-layer words that look like real words (low -> broken font encoding -> OCR)
  fonts          distinct fonts; decorative fonts (script/display) -> stylised text, check with OCR/VLM
  images, img_cov  embedded images and the share of the page they cover (photos, illustrations)
  drawings       vector paths (lines/rects): many -> table grid or chart
  tables         tables found by PyMuPDF's table finder
  rotation       page /Rotate (landscape booklet pages)
  spread         page wider than tall after rotation -> 2-up booklet spread, split before OCR
Score = how many of the hard signals fire; route = list of parsers the page needs.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

PLAIN_FONT = re.compile(r"(arial|helvetica|times|minion|myriad|calibri|garamond|frutiger|univers|futura|gill|verdana|tahoma|symbol|zapf)", re.I)
WORD = re.compile(r"^[A-Za-z][a-z]+$|^\d+([./]\d+)?$")


def triage(pdf: Path) -> list[dict]:
    doc = fitz.open(pdf)
    out = []
    for p in doc:
        text = p.get_text("text")
        words = text.split()
        ok = sum(bool(WORD.match(w.strip(".,;:()!?\"'"))) for w in words) / max(1, len(words))
        fonts = sorted({f[3] for f in p.get_fonts(full=True)})
        deco = [f for f in fonts if not PLAIN_FONT.search(f)]
        area = abs(p.rect)
        imgs = p.get_image_info()
        cov = min(1.0, sum(abs(fitz.Rect(i["bbox"]) & p.rect) for i in imgs) / area) if imgs else 0.0
        drawings = len(p.get_drawings())
        try:
            tables = len(p.find_tables().tables)
        except Exception:                      # table finder can fail on odd pages; record, don't hide
            tables = -1
        w, h = p.rect.width, p.rect.height     # p.rect already honours /Rotate
        sig = {
            "no_text_layer": len(text.strip()) < 30,
            "broken_encoding": len(words) > 20 and ok < 0.6,
            "decorative_fonts": len(deco) > 0,
            "photo_heavy": cov > 0.35,
            "table": tables > 0,
            "chart_or_grid": drawings > 150,
            "spread": w > h * 1.2,
        }
        route = ["text_layer"]
        if sig["spread"]:
            route.insert(0, "split_spread")
        if sig["no_text_layer"] or sig["broken_encoding"] or sig["decorative_fonts"]:
            route.append("ocr")
        if sig["table"] or sig["chart_or_grid"]:
            route.append("table_extract")
        if sig["photo_heavy"] or sig["chart_or_grid"] or sig["decorative_fonts"]:
            route.append("vlm")
        out.append({"page": p.number + 1, "rotation": p.rotation, "size": [round(w), round(h)],
                    "chars": len(text), "words_ok": round(ok, 2), "fonts": fonts, "decorative": deco,
                    "images": len(imgs), "img_cov": round(cov, 2), "drawings": drawings, "tables": tables,
                    "signals": [k for k, v in sig.items() if v], "score": sum(sig.values()), "route": route})
    return out


if __name__ == "__main__":
    pdf, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = triage(pdf)
    (out_dir / "triage.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    from collections import Counter
    print(len(rows), "pages")
    print("signals:", Counter(s for r in rows for s in r["signals"]))
    print("routes :", Counter("+".join(r["route"]) for r in rows).most_common(8))
    for r in sorted(rows, key=lambda r: -r["score"])[:15]:
        print(r["page"], r["score"], r["signals"], "chars", r["chars"], "ok", r["words_ok"], "img", r["img_cov"],
              "draw", r["drawings"], "tbl", r["tables"], "deco", r["decorative"][:3])
