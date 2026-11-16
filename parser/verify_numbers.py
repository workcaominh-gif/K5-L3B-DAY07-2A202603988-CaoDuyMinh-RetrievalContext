"""Cross-check the VLM tier against the PDF text layer, number by number.

    python parser/verify_numbers.py <work_dir>

1. Decode the text layer: the cookbook's fraction font maps fraction glyphs to capital letters. The mapping was
   discovered by the VLM agents (image vs text-layer disagreements) and is applied here deterministically:
       K=½  L=⅓  M=⅔  N=¼  O=¾  V=⅛  W=⅜  X=⅝  Y=⅞
   A letter is only decoded when it stands alone next to a number or a unit ("V cup", "5 Y", "⅞ x W").
2. Pull every quantity from each page's VLM facts (integers, decimals, mixed fractions like "4 ¾", temperatures).
3. A quantity is VERIFIED when it also occurs in the decoded text layer of the same page, IMAGE_ONLY when the page
   region it came from has no text layer (photos, the Nutrition Facts label), and MISMATCH otherwise.
Writes <work>/verify/numbers.json and prints totals + every mismatch for manual review.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

GLYPH = {"K": "½", "L": "⅓", "M": "⅔", "N": "¼", "O": "¾", "V": "⅛", "W": "⅜", "Y": "⅞", "X": "⅝"}
UNIT = r"(?:cups?|tsp|Tbsp|oz|lb|qt|gal|No\.|x|can|inch|”|\"|scoop|pan)"
LONE = re.compile(rf"(?<![A-Za-z])([KLMNOVWXY])(?![A-Za-z])(?=\s*(?:{UNIT}|x\b))|(?<=\d )([KLMNOVWXY])(?![A-Za-z])|(?<=x )([KLMNOVWXY])(?![A-Za-z])")
FRAC = "½⅓⅔¼¾⅛⅜⅝⅞"
QTY = re.compile(rf"\d+(?:\.\d+)?(?:\s*[{FRAC}])?|[{FRAC}]")


def decode(text: str) -> str:
    return LONE.sub(lambda m: GLYPH[next(g for g in m.groups() if g)], text)


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s.replace(",", ""))


def main(work: Path) -> None:
    out, totals = [], {"verified": 0, "image_only": 0, "mismatch": 0}
    for jf in sorted((work / "json").glob("p*.json")):
        page = json.loads(jf.read_text(encoding="utf-8"))
        n = page["pdf_page"]
        raw = (work / "pages" / f"p{n:03d}.txt").read_text(encoding="utf-8")
        text = norm(decode(raw))
        image_only_page = len(raw.strip()) < 30
        figure_text = " ".join(json.dumps(b, ensure_ascii=False) for b in page.get("blocks", []) if b.get("kind") == "figure")
        rows = []
        for fact in page.get("facts", []):
            for q in {m.group(0) for m in QTY.finditer(fact)}:
                if norm(q) in text:
                    status = "verified"
                elif image_only_page or norm(q) in norm(figure_text):
                    status = "image_only"
                else:
                    status = "mismatch"
                totals[status] += 1
                if status == "mismatch":
                    rows.append({"qty": q, "fact": fact})
        out.append({"pdf_page": n, "type": page.get("type"), "mismatches": rows})
    (work / "verify").mkdir(exist_ok=True)
    (work / "verify" / "numbers.json").write_text(json.dumps({"totals": totals, "pages": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("pages", len(out), totals)
    for p in out:
        for r in p["mismatches"]:
            print(f"p{p['pdf_page']:03d} [{p['type']}] {r['qty']!r:8} {r['fact'][:120]}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
