"""Deterministic checker for benchmark/dga/questions.jsonl against the ORIGINAL PDF.

Checks
  * ids unique, required fields present, split/group counts match the frozen spec
  * every evidence `quote` is a substring of that page's PyMuPDF text layer
    (whitespace / ligatures / curly quotes / dashes normalised)
  * every table/figure evidence item has a bbox inside the page and an existing crop file
  * printed_page matches the "Page N" label found on the PDF page
  * no-evidence items: absence_check present; every pattern re-run over all pages -> 0 hits;
    control pattern -> >= control_min_hits hits (proves the search works)
  * answerable items cite >= 1 evidence item; multihop items cite >= 2 distinct pages/refs

Run:
  "/Volumes/T7 Dev/AI20K/day6/venv/bin/python" -W ignore eval/dga_verify_benchmark.py
Exit code 0 = pass, 1 = failures (listed).
"""
import collections
import json
import os
import re
import sys

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QFILE = os.path.join(ROOT, "benchmark", "dga", "questions.jsonl")
PDF = os.environ.get("DGA_PDF", "/Volumes/T7 Dev/AI20K/day7/dga/raw/dga_2020_2025.pdf")
SHA256 = "ceea04ce1a7c13a95a170f3548ed3926ad6dd49599bd730fb58bc9c02711d16e"

SPEC = {
    "test": {"table": 6, "image": 5, "chart": 5, "multihop": 4, "text": 4, "none": 6},
    "dev": {"table": 4, "image": 3, "chart": 4, "multihop": 3, "text": 4, "none": 4},
}
TOTAL = {"test": 30, "dev": 22}
GROUPS = ["table", "image", "chart", "multihop", "text", "none"]


def norm(s):
    rep = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl",
           "’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-",
           "­": "", " ": " "}
    for a, b in rep.items():
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def main():
    import hashlib
    fails = []
    with open(PDF, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    if sha != SHA256:
        fails.append(f"PDF sha256 mismatch: {sha}")
    doc = fitz.open(PDF)
    pages = [norm(p.get_text()) for p in doc]
    n_pages = len(pages)
    if n_pages != 164:
        fails.append(f"expected 164 pages, got {n_pages}")

    qs = [json.loads(l) for l in open(QFILE, encoding="utf-8") if l.strip()]
    ids = [q["id"] for q in qs]
    dup = [k for k, v in collections.Counter(ids).items() if v > 1]
    if dup:
        fails.append(f"duplicate ids: {dup}")

    counts = collections.Counter((q["split"], q["group"]) for q in qs)
    for split, spec in SPEC.items():
        n = sum(1 for q in qs if q["split"] == split)
        if n != TOTAL[split]:
            fails.append(f"{split}: {n} questions, expected {TOTAL[split]}")
        for g, want in spec.items():
            if counts[(split, g)] != want:
                fails.append(f"{split}/{g}: {counts[(split, g)]} != {want}")
        prefix = "t" if split == "test" else "d"
        for q in qs:
            if q["split"] == split and not q["id"].startswith(prefix):
                fails.append(f"{q['id']}: id prefix does not match split {split}")

    # duplicate questions across splits
    qtexts = collections.Counter(norm(q["question"]).lower() for q in qs)
    for t, c in qtexts.items():
        if c > 1:
            fails.append(f"duplicate question text: {t[:60]}")

    n_quotes = n_crops = n_abs_pat = 0
    for q in qs:
        qid = q["id"]
        for k in ("id", "split", "group", "tags", "question", "answerable", "evidence", "rationale"):
            if k not in q:
                fails.append(f"{qid}: missing field {k}")
        if q["group"] not in GROUPS:
            fails.append(f"{qid}: bad group {q['group']}")
        if q["group"] == "none":
            if q.get("answerable") is not False or q.get("expected_behavior") != "abstain":
                fails.append(f"{qid}: none item must be answerable=false, expected_behavior=abstain")
            ac = q.get("absence_check")
            if not ac or not ac.get("patterns") or not ac.get("control_pattern"):
                fails.append(f"{qid}: missing absence_check patterns/control")
                continue
            if not q.get("near_topic"):
                fails.append(f"{qid}: missing near_topic")
            for pat in ac["patterns"]:
                n_abs_pat += 1
                rx = re.compile(pat, re.I)
                hits = [i + 1 for i, t in enumerate(pages) if rx.search(t)]
                if hits:
                    fails.append(f"{qid}: absence pattern {pat!r} hits pages {hits[:10]}")
            rx = re.compile(ac["control_pattern"], re.I)
            chits = sum(1 for t in pages if rx.search(t))
            if chits < ac.get("control_min_hits", 1):
                fails.append(f"{qid}: control pattern {ac['control_pattern']!r} only {chits} page hits")
            continue

        if q.get("answerable") is not True or not q.get("expected_answer"):
            fails.append(f"{qid}: answerable item needs answerable=true and expected_answer")
        ev = q.get("evidence") or []
        if not ev:
            fails.append(f"{qid}: no evidence")
        if q["group"] == "multihop":
            distinct = {(e["pdf_page"], e["ref"]) for e in ev}
            pgs = {e["pdf_page"] for e in ev}
            if len(pgs) < 2 or len(distinct) < 2:
                fails.append(f"{qid}: multihop needs evidence from >= 2 pages")
        for e in ev:
            p = e.get("pdf_page")
            if not isinstance(p, int) or not 1 <= p <= n_pages:
                fails.append(f"{qid}: bad pdf_page {p}")
                continue
            m = re.search(r"Page (\d{1,3})\b", doc[p - 1].get_text())
            if m and e.get("printed_page") != int(m.group(1)):
                fails.append(f"{qid}: printed_page {e.get('printed_page')} != label {m.group(1)} on PDF p{p}")
            if e.get("kind") not in ("text", "table", "figure"):
                fails.append(f"{qid}: bad kind {e.get('kind')}")
            if e.get("quote"):
                n_quotes += 1
                if norm(e["quote"]) not in pages[p - 1]:
                    fails.append(f"{qid}: quote not found on PDF p{p}: {e['quote'][:70]!r}")
            elif e.get("kind") == "text":
                fails.append(f"{qid}: text evidence without quote")
            if e.get("kind") in ("table", "figure"):
                bb = e.get("bbox")
                rect = doc[p - 1].rect
                if not bb or len(bb) != 4:
                    fails.append(f"{qid}: table/figure evidence without bbox")
                else:
                    r = fitz.Rect(bb)
                    if r.is_empty or not (rect.x0 - 0.5 <= r.x0 and rect.y0 - 0.5 <= r.y0 and r.x1 <= rect.x1 + 0.5 and r.y1 <= rect.y1 + 0.5):
                        fails.append(f"{qid}: bbox {bb} outside page {list(rect)}")
                crop = e.get("crop")
                if not crop or not os.path.isfile(os.path.join(ROOT, crop)):
                    fails.append(f"{qid}: crop missing {crop}")
                else:
                    n_crops += 1
                    if os.path.getsize(os.path.join(ROOT, crop)) > 160_000:
                        fails.append(f"{qid}: crop too large {crop}")
                if q["group"] == "chart" and e.get("kind") == "figure" and not e.get("reading"):
                    fails.append(f"{qid}: chart figure evidence without reading note")

    # summary
    print(f"PDF: {PDF}\nsha256 ok: {sha == SHA256}   pages: {n_pages}   questions: {len(qs)}\n")
    head = f"{'split':6} " + " ".join(f"{g:>9}" for g in GROUPS) + f" {'total':>7}"
    print(head)
    print("-" * len(head))
    for split in ("dev", "test"):
        row = [counts[(split, g)] for g in GROUPS]
        print(f"{split:6} " + " ".join(f"{c:>9}" for c in row) + f" {sum(row):>7}")
        print(f"{'spec':6} " + " ".join(f"{SPEC[split][g]:>9}" for g in GROUPS) + f" {TOTAL[split]:>7}")
    print(f"\nquotes checked: {n_quotes}   crops checked: {n_crops}   absence patterns re-run: {n_abs_pat} (all must be 0 hits)")
    if fails:
        print(f"\nFAIL ({len(fails)}):")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("\nPASS")


if __name__ == "__main__":
    main()
