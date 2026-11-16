"""Figure-level image index for the PDF: every embedded raster image (banner, dish photo, logo, label photo) becomes
its own searchable item, rendered together with any text printed on top of it.

    python parser/pdf_images.py <pdf> <work_dir>

Why: page images and 60 % tiles drown small elements - a corner section banner ("Whole Grains") is ~1/40 of a page.
Images reused on many pages (the same xref) are stored once with the list of pages and boxes, so a query for a
repeated banner answers "pages 11, 13, 15, ..." instead of picking one at random.

Writes <work>/pdf_figures/x<xref>.png and <work>/pdf_figures.json
  [{xref, file, w, h, pages: [{pdf_page, bbox}], area_share, text_over}]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf
from PIL import Image


def main(pdf: Path, work: Path) -> None:
    out = work / "pdf_figures"
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf)
    figs: dict = {}
    for p in doc:
        area = abs(p.rect)
        page_pix = None
        for info in p.get_image_info(xrefs=True):
            xref = info.get("xref") or 0
            # image boxes are in UNROTATED page space; these pages have /Rotate 90 -> map into display space first
            bbox = (pymupdf.Rect(info["bbox"]) * p.rotation_matrix) & p.rect
            if xref <= 0 or bbox.is_empty or bbox.width < 25 or bbox.height < 15:
                continue                                        # skip masks, rules and tiny ornaments
            f = figs.setdefault(xref, {"xref": xref, "pages": [], "file": f"x{xref}.png"})
            f["pages"].append({"pdf_page": p.number + 1, "bbox": [round(v, 1) for v in bbox]})
            if "w" not in f:                                    # crop the first occurrence from the rendered page,
                if page_pix is None:                            # so text printed over the image is included
                    page_pix = p.get_pixmap(dpi=144)
                    page_img = Image.frombytes("RGB", (page_pix.width, page_pix.height), page_pix.samples)
                k = 144 / 72
                crop = page_img.crop((int(bbox.x0 * k), int(bbox.y0 * k), int(bbox.x1 * k), int(bbox.y1 * k)))
                crop.save(out / f["file"])
                f.update(w=crop.width, h=crop.height, area_share=round(abs(bbox) / area, 3),
                         text_over=" ".join(p.get_text("text", clip=bbox).split())[:200])
    rows = sorted(figs.values(), key=lambda f: (-len(f["pages"]), f["xref"]))
    (work / "pdf_figures.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(len(rows), "unique figures;", sum(len(f["pages"]) for f in rows), "placements")
    for f in rows[:8]:
        print(f"  x{f['xref']}: on {len(f['pages'])} pages {[q['pdf_page'] for q in f['pages']][:8]} · {f['w']}x{f['h']}px · '{f['text_over'][:40]}'")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
