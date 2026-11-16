"""Processing step 1: classify every PDF page and build a work packet for the VLM tier.

    python parser/prepare_pages.py <pdf> <work_dir>

For each page writes   <work>/pages/p###.png   (page image, 110 dpi, honours /Rotate)
                       <work>/pages/p###.txt   (text layer, reference for exact numbers - may contain broken glyphs)
and <work>/manifest.json with page type, printed page number, category, recipe and the route (which model tier).

Page types (rules, checked against the contact sheets):
  cover / blank / toc / front   fixed front-matter pages
  photo        image covers > 60% of the page (full-bleed dish photo, often with overlaid text)
  story        recipe intro page ("Our Story", school team members)
  table        recipe table page ("Ingredients" + "Directions" header)
  tips         everything else (tip sheets, marketing guide, allergens, food safety)
Route: table / toc / pages with embedded raster text (Nutrition label) -> sonnet; story / tips / photo -> haiku.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

CATS = ["Whole Grains", "Dark Green and Orange Vegetables", "Dry Beans and Peas"]
FOOTER = re.compile(r"Recipes for Healthy Kids Cookbook for Child Care Centers|Teamnutrition\.usda\.gov", re.I)


def page_type(i: int, text: str, cov: float) -> str:
    if i == 1:
        return "cover"
    if len(text.strip()) < 30:
        return "blank" if cov < 0.3 else "photo"
    if i == 3:
        return "toc"
    if cov > 0.6:
        return "photo"
    if ("Ingredients" in text and "Directions" in text) or "Nutrients Per Serving" in text:
        return "table"
    if "Our Story" in text:
        return "story"
    return "front" if i < 10 else "tips"


def main(pdf: Path, work: Path) -> None:
    out = work / "pages"
    out.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf)
    rows, recipe = [], None
    for p in doc:
        i = p.number + 1
        text = p.get_text("text")
        cov = min(1.0, sum(abs(pymupdf.Rect(x["bbox"]) & p.rect) for x in p.get_image_info()) / abs(p.rect))
        t = page_type(i, text, cov)
        lines = [l.strip() for l in text.splitlines() if l.strip() and not FOOTER.search(l)]
        printed = next((int(l) for l in lines[:3] + lines[-3:] if l.isdigit() and int(l) < 200), None)
        cat = next((c for c in CATS if c in text), None)
        if t in ("story", "table"):        # recipe title = first non-number, non-category line
            title = next((l for l in lines if not l.isdigit() and l not in CATS and len(l) > 3), None)
            if t == "story":
                recipe = title
        raster_text = t in ("tips", "front") and any(
            (x["width"] * x["height"]) > 40000 for x in p.get_image_info())       # e.g. Nutrition Facts photo on p.47
        tier = "sonnet" if t in ("table", "toc") or raster_text else "haiku"
        p.get_pixmap(dpi=110).save(out / f"p{i:03d}.png")
        (out / f"p{i:03d}.txt").write_text(text, encoding="utf-8")
        rows.append({"pdf_page": i, "printed_page": printed, "type": t, "category": cat,
                     "recipe": recipe if t in ("story", "table") else None, "img_cov": round(cov, 2),
                     "raster_text": raster_text, "tier": tier})
    # Recipe names come from the table of contents (PDF p.3), not from page text: the text layer puts the story
    # paragraph before the title. TOC text layer lists the featured recipes with their numbers, then the
    # 27 other names in reading order, then their 27 printed page numbers. Printed page n == PDF page n + 2.
    toc = [l.strip() for l in doc[2].get_text("text").splitlines() if l.strip()]
    starts = [(8, "Porcupine Sliders"), (50, "Tasty Tots"), (96, "Tuscan Smoked Turkey and Bean Soup")]
    names = [l for l in toc[toc.index("Dry Beans and Peas") + 1:] if not l.isdigit() and "Winner" not in l]
    nums = [int(l) for l in toc[toc.index("Dry Beans and Peas") + 1:] if l.isdigit()]
    assert len(names) == len(nums) == 27, (len(names), len(nums))
    starts = sorted(starts + list(zip(nums, names)))
    for r in rows:
        if r["type"] in ("photo", "story", "table") and r["pdf_page"] >= 10:
            r["recipe"] = max((s for s in starts if s[0] + 2 <= r["pdf_page"]), default=(0, None))[1]
    (work / "toc.json").write_text(json.dumps([{"recipe": n, "printed_start": s, "pdf_start": s + 2}
                                               for s, n in starts], indent=1, ensure_ascii=False), encoding="utf-8")
    (work / "manifest.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    from collections import Counter
    print(Counter(r["type"] for r in rows), Counter(r["tier"] for r in rows))
    print(sorted({r["recipe"] for r in rows if r["recipe"]}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
