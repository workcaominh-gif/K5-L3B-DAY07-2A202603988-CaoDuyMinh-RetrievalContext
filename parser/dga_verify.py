"""Verify the vision extraction (work/json/pNNN.json) against the PDF itself.

    python parser/dga_verify.py                 # -> work/verify.json + summary on stdout
    python parser/dga_verify.py --fix [max]     # also re-run pages with many printed-number mismatches (corrective note)

(a) Printed numbers: every number in table cells, chart points marked "printed" and facts must occur in the page's
    text layer (normalised: thousands commas removed, "1 ½" == "1½", "1/2" == "½", "%" ignored). Table cells and
    printed chart labels are hard checks; facts are reported separately (a fact may legitimately restate a number
    from the page in another form, e.g. "2,000-calorie" -> "2000").
(b) Vector charts: for every chart region with "read_off_axis" points, find a vertical numeric tick column inside the
    region (page.get_text("dict") spans), fit y -> value, then read the exact value of every dot (small square filled
    path) and every range bar (constant-width filled path; top/bottom edge = high/low) from page.get_drawings().
    Columns are clustered by x and mapped in order onto the model's categories; the model's read-off values are
    compared with the geometry values (tolerance 0.2 x tick step). Geometry values are stored and used by the index;
    dots / range ends the model skipped are added from geometry (added_by = "pdf_geometry"). Idempotent: points
    are only added once (a rerun finds them present).
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PDF = Path("/Volumes/T7 Dev/AI20K/day7/dga/raw/dga_2020_2025.pdf")
WORK = Path("/Volumes/T7 Dev/AI20K/day7/dga/work")
FR = {"½": .5, "¼": .25, "¾": .75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": .125, "⅜": .375, "⅝": .625, "⅞": .875}
SLASH = {"1/2": "½", "1/4": "¼", "3/4": "¾", "1/3": "⅓", "2/3": "⅔", "1/8": "⅛", "3/8": "⅜", "5/8": "⅝", "7/8": "⅞"}
NUM = re.compile(r"\d+(?:\.\d+)?[ \u00a0]?[½¼¾⅓⅔⅛⅜⅝⅞]?|[½¼¾⅓⅔⅛⅜⅝⅞]")


def norm_nums(s: str) -> list[str]:
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)
    for a, b in SLASH.items():
        s = re.sub(rf"(?<!\d){re.escape(a)}(?!\d)", b, s)
    out = []
    for m in NUM.findall(s):
        t = m.replace(" ", "").replace("\u00a0", "")
        t = re.sub(r"^(\d+)\.0+$", r"\1", t)
        out.append(t)
    return out


def check_numbers(page: dict, layer: str) -> dict:
    have = set(norm_nums(layer))
    # also allow integer and fraction parts separately (text layer may split "1" and "½" across spans)
    have |= {re.sub(r"[½¼¾⅓⅔⅛⅜⅝⅞]", "", t) for t in have} | {t[-1] for t in have if t and t[-1] in FR}
    res = {"table_cells": [0, 0], "chart_printed": [0, 0], "facts": [0, 0], "mismatches": []}

    def chk(kind, s, where):
        for t in norm_nums(s):
            res[kind][0] += 1
            if t in have:
                res[kind][1] += 1
            else:
                res["mismatches"].append({"kind": kind, "num": t, "in": s[:120], "where": where})
    for r in page.get("regions", []):
        d = r["data"]
        if r["kind"] == "table":
            for row in d["rows"]:
                for c in row:
                    chk("table_cells", c, r["id"])
        for p in d["points"]:
            if p["source"] == "printed":
                chk("chart_printed", p["value"], r["id"])
    for f in page.get("facts", []):
        chk("facts", f, "fact")
    return res


def _val(s: str) -> float | None:
    s = s.replace(",", "").strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)?\s*([½¼¾⅓⅔⅛⅜⅝⅞])?", s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return float(m.group(1) or 0) + FR.get(m.group(2) or "", 0)


def chart_geometry(pg, region: dict) -> dict:
    W, H = pg.rect.width, pg.rect.height
    x0, y0, x1, y1 = region["bbox_norm"]
    box = (x0 * W - 15, y0 * H - 15, x1 * W + 15, y1 * H + 15)
    inb = lambda r: r[0] >= box[0] and r[2] <= box[2] and r[1] >= box[1] and r[3] <= box[3]
    nums = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if re.fullmatch(r"\d+(?:\.\d+)?", t) and inb(s["bbox"]):
                    nums.append((round(s["bbox"][2]), float(t), (s["bbox"][1] + s["bbox"][3]) / 2, s["bbox"][2]))
    cols = defaultdict(list)
    for xr, v, yc, xe in nums:
        cols[xr // 4].append((v, yc, xe))
    axis = max(cols.values(), key=len, default=[])
    axis = sorted(axis, key=lambda t: t[1])
    if len(axis) < 4 or not all(axis[i][0] > axis[i + 1][0] for i in range(len(axis) - 1)):
        return {"status": "no_vertical_axis"}
    # least squares y -> value
    ys, vs = [a[1] for a in axis], [a[0] for a in axis]
    my, mv = statistics.mean(ys), statistics.mean(vs)
    slope = sum((y - my) * (v - mv) for y, v in zip(ys, vs)) / sum((y - my) ** 2 for y in ys)
    f = lambda y: mv + slope * (y - my)
    step = abs(vs[0] - vs[1])
    top, bot, ax_x = min(ys) - 3, max(ys) + 3, max(a[2] for a in axis)
    groups = defaultdict(list)
    for g in pg.get_drawings():
        if not g.get("fill"):
            continue
        r = g["rect"]
        if r.x0 < ax_x or r.x1 > box[2] or r.y0 < top or r.y1 > bot or r.width < 3 or r.width > 25:
            continue
        groups[tuple(round(c, 2) for c in g["fill"])].append(r)
    dots, bars = [], []
    for col, rs in groups.items():
        ws = [r.width for r in rs]
        if len(rs) >= 2 and all(abs(r.width - r.height) < 1.5 and r.width < 13 for r in rs):
            dots += [((r.x0 + r.x1) / 2, f((r.y0 + r.y1) / 2)) for r in rs]
        elif len(rs) >= 2 and max(ws) - min(ws) < 1.0 and 8 <= statistics.mean(ws) <= 25 and \
                sum(r.height >= r.width * 0.9 for r in rs) >= len(rs) * 0.6:
            bars += [((r.x0 + r.x1) / 2, f(r.y1), f(r.y0)) for r in rs]
    if not dots and not bars:
        return {"status": "no_marks"}
    xs = sorted([d[0] for d in dots] + [b[0] for b in bars])
    centers = []
    for x in xs:
        if centers and abs(x - centers[-1][-1]) < 8:
            centers[-1].append(x)
        else:
            centers.append([x])
    centers = [statistics.mean(c) for c in centers]
    columns = []
    for cx in centers:
        d = [round(v, 2) for x, v in dots if abs(x - cx) < 8]
        b = [(round(lo, 2), round(hi, 2)) for x, lo, hi in bars if abs(x - cx) < 8]
        columns.append({"x": round(cx, 1), "dot": d[0] if d else None, "low": b[0][0] if b else None, "high": b[0][1] if b else None})
    return {"status": "ok", "tick_step": step, "axis_ticks": vs, "columns": columns}


def compare(region: dict, geo: dict) -> dict:
    pts = region["data"]["points"]
    cats = list(dict.fromkeys(p["category"] for p in pts if p["source"] == "read_off_axis"))
    cols = geo["columns"]
    if len(cats) != len(cols):
        return {"status": "column_count_mismatch", "model_categories": len(cats), "geometry_columns": len(cols)}
    tol = 0.2 * (geo["tick_step"] or 1)
    rows, ok = [], 0
    for p in pts:
        if p["source"] != "read_off_axis" or p["category"] not in cats or p.get("added_by"):
            continue
        c = cols[cats.index(p["category"])]
        s = p["series"].lower()
        key = "low" if s.endswith("low") else "high" if s.endswith("high") else "dot"
        g, m = c[key], _val(p["value"])
        if g is None or m is None:
            continue
        good = abs(g - m) <= tol
        ok += good
        rows.append({"category": p["category"], "series": p["series"], "model": m, "geometry": g, "ok": good})
        p["geometry_value"] = g
    # fill points the model skipped (typically range-bar ends) with the exact geometry values
    have = {(p["category"], "low" if p["series"].lower().endswith("low") else "high" if p["series"].lower().endswith("high") else "dot")
            for p in pts}
    rng = next((s.split("(")[0].strip() for s in region["data"]["series"] if "range" in s.lower()), "Recommended Intake Ranges")
    dot = next((p["series"] for p in pts if not p["series"].lower().endswith(("low", "high"))), "Average Intakes")
    added = sum(1 for p in pts if p.get("added_by"))
    for cat, c in zip(cats, cols):
        unit = next((p["unit"] for p in pts if p["category"] == cat), "")
        for key, series in (("dot", dot), ("low", f"{rng} low"), ("high", f"{rng} high")):
            if c[key] is not None and (cat, key) not in have:
                pts.append({"series": series, "category": cat, "value": f"{c[key]:.2f}".rstrip("0").rstrip("."), "unit": unit,
                            "source": "read_off_axis", "geometry_value": c[key], "added_by": "pdf_geometry"})
                added += 1
    return {"status": "compared", "n": len(rows), "ok": ok, "tolerance": tol, "points_added_from_geometry": added,
            "max_abs_err": round(max((abs(r["model"] - r["geometry"]) for r in rows), default=0), 3),
            "mismatches": [r for r in rows if not r["ok"]], "values": rows}


def main(fix: int = 0) -> None:
    import fitz
    doc = fitz.open(PDF)
    pages, summ = {}, defaultdict(lambda: [0, 0])
    charts = {"regions": 0, "compared": 0, "points": 0, "points_ok": 0, "points_added_from_geometry": 0, "status": defaultdict(int)}
    for jf in sorted((WORK / "json").glob("p*.json")):
        page = json.loads(jf.read_text())
        n = page["pdf_page"]
        layer = (WORK / "pages" / f"p{n:03d}.txt").read_text(errors="replace")
        nc = check_numbers(page, layer)
        for k in ("table_cells", "chart_printed", "facts"):
            summ[k][0] += nc[k][0]
            summ[k][1] += nc[k][1]
        rec = {"numbers": nc, "charts": {}}
        changed = False
        for r in page.get("regions", []):
            if r["kind"] != "chart" or not any(p["source"] == "read_off_axis" for p in r["data"]["points"]):
                continue
            charts["regions"] += 1
            geo = chart_geometry(doc[n - 1], r)
            res = compare(r, geo) if geo["status"] == "ok" else {"status": geo["status"]}
            if geo["status"] == "ok":
                res["geometry"] = geo
            charts["status"][res["status"]] += 1
            if res["status"] == "compared":
                charts["compared"] += 1
                charts["points"] += res["n"]
                charts["points_ok"] += res["ok"]
                charts["points_added_from_geometry"] += res["points_added_from_geometry"]
                changed = True
            rec["charts"][r["id"]] = res
        if changed:          # geometry values are written back next to the model value (used by the index)
            jf.write_text(json.dumps(page, ensure_ascii=False, indent=1))
        pages[n] = rec
    hard = [(n, [m for m in r["numbers"]["mismatches"] if m["kind"] != "facts"]) for n, r in pages.items()]
    bad = sorted([(n, m) for n, m in hard if len(m) >= 3], key=lambda t: -len(t[1]))
    if fix:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import dga_extract as E
        tri = json.loads((WORK / "triage.json").read_text())
        for n, ms in bad[:fix]:
            nums = sorted({m["num"] for m in ms})[:30]
            note = (f"A previous extraction of this page produced numbers that do not occur in the text layer: {', '.join(nums)}. "
                    "Re-read every table cell and printed label; copy each number exactly from the text layer, keep fractions "
                    "as printed (e.g. '1 ½'), and do not compute or convert values in table cells.")
            print("re-run", n, nums, flush=True)
            E.extract(n, E.SONNET if tri[str(n)]["model"] == E.HAIKU else tri[str(n)]["model"], note)
        return main(0)
    out = {"summary": {
        "pages": len(pages),
        "printed_numbers": {k: {"checked": v[0], "found_in_text_layer": v[1], "rate": round(v[1] / max(v[0], 1), 4)} for k, v in summ.items()},
        "pages_with_>=3_hard_mismatches": [n for n, _ in bad],
        "charts": {**charts, "status": dict(charts["status"]),
                   "point_agreement": round(charts["points_ok"] / max(charts["points"], 1), 4)}},
        "pages": pages}
    (WORK / "verify.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--fix") + 1]) if "--fix" in sys.argv and len(sys.argv) > sys.argv.index("--fix") + 1
         else (8 if "--fix" in sys.argv else 0))
