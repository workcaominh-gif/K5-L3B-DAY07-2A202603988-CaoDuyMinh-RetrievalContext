"""Enrichment (slide 7): metadata enrichment, context decomposition, graph extraction. Deterministic code over the
VLM outputs; LLM summaries / knowledge packages are produced afterwards by the compile agents (parser/COMPILE_SPEC.md).

    python parser/enrich.py <work_dir>

Writes <work>/kb/:
  recipes.json   one record per recipe: category, award, pages (pdf + printed), meal components, servings/yield,
                 ingredients (25/50 servings, weight/measure, source page), CCP temperatures, oven settings,
                 nutrients per serving, allergens (rule-based, with the ingredient that triggered it), videos
  units.jsonl    retrieval units, each with text + metadata + provenance:
                   page  (whole page, HTML -> text, layout order)       fact (one atomic statement = decomposition)
                   video_segment (transcript + on-screen text, timestamp link)
  kg_edges.jsonl graph store: (subject, relation, object, attrs, source)
"""
from __future__ import annotations

import html as H
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ALLERGENS = {  # FDA major food allergens -> keywords in ingredient names
    "milk": r"\b(milk|cheese|mozzarella|cheddar|parmesan|yogurt|butter|cream|ricotta|monterey)\b",
    "egg": r"\beggs?\b",
    "wheat/gluten": r"\b(wheat|flour|pasta|penne|rotini|spaghetti|macaroni|noodles?|lasagna|tortillas?|rolls?|buns?|breads?|couscous|panko|crumbs|crust|pitas?|bulgur|barley)\b",
    "soy": r"\b(soy|tofu|edamame)\b",
    "fish": r"\b(fish|pollock|cod|tilapia|salmon|tuna|swai)\b",
    "peanut": r"\bpeanut",
    "tree nuts": r"\b(almond|walnut|pecan|cashew|pistachio|hazelnut)\b",
    "sesame": r"\bsesame\b",
}
NUTR = ["Calories", "Protein", "Carbohydrate", "Total Fat", "Saturated Fat", "Cholesterol", "Vitamin A", "Vitamin C",
        "Iron", "Calcium", "Sodium", "Dietary Fiber"]


def text_of(html: str) -> str:
    html = re.sub(r"</(p|h\d|li|tr|div|figcaption|header|footer|table)>", "\n", html)
    html = re.sub(r"<(td|th)[^>]*>", " | ", html)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", H.unescape(re.sub(r"<[^>]+>", "", html)))).strip()


GENERIC = {"liquid", "fresh", "frozen", "canned", "dried", "dry", "ground", "raw", "cooked", "low-sodium", "reduced-fat", "fat-free"}


def ing_name(s: str) -> str:
    """Ingredient key: first comma part, unless it is only a generic form word ("Liquid, whole egg" -> "whole egg")."""
    s = re.sub(r"^\*", "", s).strip()
    parts = [p.strip().lower() for p in re.split(r",|\(|\n", s) if p.strip()]
    if len(parts) > 1 and parts[0] in GENERIC:
        return parts[1]
    return parts[0] if parts else s.lower()


def main(work: Path) -> None:
    man = {r["pdf_page"]: r for r in json.loads((work / "manifest.json").read_text())}
    pages = {int(f.stem[1:]): json.loads(f.read_text()) for f in sorted((work / "json").glob("p*.json"))}
    kb = work / "kb"
    kb.mkdir(exist_ok=True)
    R: dict = defaultdict(lambda: {"pages": [], "ingredients": [], "ccp": [], "oven": [], "nutrients": {},
                                   "allergens": {}, "categories": Counter(), "videos": []})
    units, edges = [], []

    for n, p in pages.items():
        m = man[n]
        recipe = m["recipe"]                       # TOC-derived name is the canonical key
        cat = p.get("category") or m.get("category")
        htmlp = work / "html" / f"p{n:03d}.html"
        body = text_of(htmlp.read_text(encoding="utf-8")) if htmlp.exists() else ""
        meta = {"source_id": "cookbook", "pdf_page": n, "printed_page": p.get("printed_page"), "page_type": p.get("type"),
                "recipe": recipe, "category": cat, "modality": "pdf", "extractor": f"vlm-{m['tier']}",
                "confidence": p.get("confidence")}
        if body:
            units.append({"id": f"cookbook:p{n:03d}", "kind": "page", "text": body, **meta})
        for k, f in enumerate(p.get("facts", [])):
            units.append({"id": f"cookbook:p{n:03d}:f{k:03d}", "kind": "fact", "text": f, **meta})
        if not recipe:
            continue
        r = R[recipe]
        r["pages"].append({"pdf_page": n, "printed_page": p.get("printed_page"), "type": p.get("type")})
        if cat:
            r["categories"][cat] += 1
        for b in p.get("blocks", []):
            if b.get("kind") in ("figure", "heading", "paragraph") and re.search(r"WINNER", (b.get("text") or "") + (b.get("caption") or ""), re.I):
                r.setdefault("award", re.search(r"((GRAND PRIZE|POPULAR CHOICE|1ST PLACE|2ND PLACE)\s+WINNER)",
                                                ((b.get("text") or "") + " " + (b.get("caption") or "")).upper()).group(1)
                             if re.search(r"(GRAND PRIZE|POPULAR CHOICE|1ST PLACE|2ND PLACE)\s+WINNER",
                                          ((b.get("text") or "") + " " + (b.get("caption") or "")).upper()) else None)
            mc = re.search(r"Mea[lt] Components:\s*([^\n|]+)", b.get("text") or "")   # page prints "Meat" twice
            if mc and not r.get("meal_components"):
                r["meal_components"] = re.split(r"\s{2,}", mc.group(1).strip())[0]
            rows = b.get("rows") or []
            if b.get("kind") != "table" or not rows:
                continue
            head = [str(c) for c in rows[0]]
            if head and head[0].startswith("Ingredients") and len(head) >= 5:
                for row in rows[1:]:
                    row = [str(c) for c in row] + [""] * 6
                    if row[0].strip():
                        ing = {"name": row[0].strip(), "key": ing_name(row[0]), "w25": row[1], "m25": row[2],
                               "w50": row[3], "m50": row[4], "pdf_page": n}
                        r["ingredients"].append(ing)
                        edges.append({"s": recipe, "rel": "has_ingredient", "o": ing["key"],
                                      "attrs": {k: ing[k] for k in ("name", "w25", "m25", "w50", "m50")},
                                      "source": f"cookbook:p{n:03d}"})
                    step = row[5]
                    for t in re.findall(r"(\d{2,3}) ?°F", step):
                        kind = "ccp" if "Critical Control Point" in step else "oven"
                        r[kind].append({"temp_F": int(t), "text": re.sub(r"\s+", " ", step)[:300], "pdf_page": n})
            flat = " ".join(" ".join(map(str, row)) for row in rows)
            for name in NUTR:
                mm = re.search(rf"{name}\s*\|?\s*([\d.]+\s*(?:g|mg|IU)?)", flat)
                if mm and name not in r["nutrients"]:
                    r["nutrients"][name] = {"value": mm.group(1).strip(), "pdf_page": n}
            if head[:3] == ["Serving", "Yield", "Volume"] and len(rows) > 1:
                r["serving_yield"] = {"rows": rows[1:], "pdf_page": n}

    # videos -> segments + link to recipes by name mention
    for vj in sorted((work / "video").glob("*/video.json")):
        v = json.loads(vj.read_text())
        for k, s in enumerate(v.get("segments", [])):
            text = " ".join(filter(None, [s.get("topic"), s.get("transcript"), " / ".join(s.get("on_screen_text") or []), s.get("visual")]))
            units.append({"id": f"yt:{v['video_id']}:s{k:03d}", "kind": "video_segment", "text": text, "source_id": f"yt:{v['video_id']}",
                          "video_title": v.get("title"), "t0": s.get("t0"), "t1": s.get("t1"), "link": s.get("link"),
                          "modality": "video", "extractor": "stt+captions+frame_ocr+vlm", "recipe": None})
        for k, f in enumerate(v.get("facts", [])):
            ts = re.search(r"\((\d{1,2}):(\d{2})", f)          # facts carry "(m:ss)" -> make the moment addressable
            t0 = int(ts.group(1)) * 60 + int(ts.group(2)) if ts else None
            units.append({"id": f"yt:{v['video_id']}:f{k:03d}", "kind": "fact", "text": f, "source_id": f"yt:{v['video_id']}",
                          "video_title": v.get("title"), "modality": "video", "extractor": "vlm-sonnet", "recipe": None,
                          "t0": t0, "link": f"https://youtu.be/{v['video_id']}?t={t0}" if t0 is not None else v.get("url")})
        edges.append({"s": f"yt:{v['video_id']}", "rel": "is_video", "o": v.get("title"), "attrs": {"url": v.get("url")}, "source": f"yt:{v['video_id']}"})
        for name in R:
            if name.lower() in (v.get("title") or "").lower():
                R[name]["videos"].append(v["video_id"])
                edges.append({"s": f"yt:{v['video_id']}", "rel": "demonstrates", "o": name, "attrs": {}, "source": f"yt:{v['video_id']}"})

    # Video recipes (not in the cookbook): ingredients from the on-screen ingredient card, allergens also from any fact
    # that names/shows them (e.g. "3 large eggs" card, or "a raw egg" seen in a frame) - each edge cites the second.
    video_recipes = {}
    for vj in sorted((work / "video").glob("*/video.json")):
        v = json.loads(vj.read_text())
        vid = v["video_id"]
        name = re.sub(r"^(CACFP Cooking Video:|Team Nutrition Cooks!)\s*|\s*(Video|Ages? [\d–-]+.*)$", "", v.get("title") or vid).strip() + " (video)"
        rec = {"recipe": name, "category": "Video recipe (not in the cookbook)", "award": None, "meal_components": None, "pages": [],
               "ingredients": [], "ccp": [], "oven": [], "nutrients_per_serving": {}, "serving_yield": None, "allergens": {}, "videos": [vid]}

        def tsec(f):
            m = re.search(r"\(~?(\d{1,2}):(\d{2})", f)
            return int(m.group(1)) * 60 + int(m.group(2)) if m else 0
        card = next((f for f in v.get("facts", []) if "Full recipe from the on-screen card" in f), None)
        ct = vj.parent / "card_times.json"
        card_t = json.loads(ct.read_text()) if ct.exists() else {}
        if card:
            t = tsec(card)
            for item in card.rsplit(": ", 1)[1].rstrip(".").split(", "):
                # second at which THIS item appears on the card (facts quote items as 'item' (m:ss)), else card start
                at = next((f for f in v["facts"] if f"'{item}'" in f and f is not card), None)
                m_at = re.search(re.escape(f"'{item}'") + r"\s*\((\d{1,2}):(\d{2})\)", at or "")
                t = int(m_at.group(1)) * 60 + int(m_at.group(2)) if m_at else (tsec(at) if at else tsec(card))
                t = card_t.get(item, t)                  # OCR-verified first second on screen (parser/card_times.py)
                key = re.sub(r"^[\d½¼¾⅛⅓⅔\s]+(cups?|teaspoons?|tablespoons?|of|large|medium-sized|\s)*", "", item).strip().lower()
                rec["ingredients"].append({"name": item, "key": key, "evidence": "on-screen ingredient card", "t": t})
                edges.append({"s": name, "rel": "has_ingredient", "o": key, "attrs": {"name": item, "evidence": "on-screen card"},
                              "source": f"yt:{vid}@{t}"})
        # with an ingredient card, allergens come from its items only (named, exact); without one, from facts that
        # mention/show the food - but never from serving suggestions ("likes them with ... skim milk")
        sources = [(f"{i['name']} (on-screen ingredient card)", i["t"]) for i in rec["ingredients"]] if card else \
                  [(f, tsec(f)) for f in v.get("facts", []) if not re.search(r"likes? (them|it) with|serve[ds]? with|at dinner", f, re.I)]
        for f, t in sources:
            for a, rx in ALLERGENS.items():
                if re.search(rx, f, re.I) and a not in rec["allergens"]:
                    how = "named on the on-screen ingredient card" if card else \
                          "named on screen / in speech" if re.search(r"card|says|caption|grain-rich", f, re.I) else "seen in the video only, not named"
                    rec["allergens"][a] = [f"{f[:140]} ({how})"]
                    edges.append({"s": name, "rel": "contains_allergen", "o": a, "attrs": {"via": [f[:160]], "evidence": how},
                                  "source": f"yt:{vid}@{t}"})
        edges.append({"s": name, "rel": "in_category", "o": rec["category"], "attrs": {}, "source": f"yt:{vid}@0"})
        edges.append({"s": f"yt:{vid}", "rel": "demonstrates", "o": name, "attrs": {}, "source": f"yt:{vid}@0"})
        video_recipes[name] = rec

    out = {}
    for name, r in R.items():
        cat = r["categories"].most_common(1)[0][0] if r["categories"] else None
        for ing in r["ingredients"]:
            for a, rx in ALLERGENS.items():
                if re.search(rx, ing["name"], re.I):
                    r["allergens"].setdefault(a, []).append(ing["name"])
        rec = {"recipe": name, "category": cat, "award": r.get("award"), "meal_components": r.get("meal_components"),
               "pages": r["pages"], "ingredients": r["ingredients"], "ccp": r["ccp"], "oven": r["oven"],
               "nutrients_per_serving": r["nutrients"], "serving_yield": r.get("serving_yield"),
               "allergens": {a: sorted(set(v)) for a, v in r["allergens"].items()}, "videos": r["videos"]}
        out[name] = rec
        edges.append({"s": name, "rel": "in_category", "o": cat, "attrs": {}, "source": "manifest+vlm"})
        for a, ings in rec["allergens"].items():
            edges.append({"s": name, "rel": "contains_allergen", "o": a, "attrs": {"via": ings}, "source": "rule:FDA-major-allergens"})
        for c in r["ccp"]:
            edges.append({"s": name, "rel": "ccp_temp_F", "o": c["temp_F"], "attrs": {"text": c["text"]}, "source": f"cookbook:p{c['pdf_page']:03d}"})
        # recipe-level metadata onto its units
        for u in units:
            if u.get("recipe") == name:
                u.update({"category": u.get("category") or cat, "award": rec["award"], "allergens": sorted(rec["allergens"])})
    out.update(video_recipes)
    (kb / "recipes.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (kb / "units.jsonl").write_text("\n".join(json.dumps(u, ensure_ascii=False) for u in units), encoding="utf-8")
    (kb / "kg_edges.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in edges), encoding="utf-8")
    print("recipes", len(out), "units", Counter(u["kind"] for u in units), "edges", Counter(e["rel"] for e in edges))
    for name, rec in sorted(out.items()):
        print(f"  {name[:34]:34} {str(rec['category'])[:12]:12} {str(rec['award'])[:20]:20} ing={len(rec['ingredients']):2} "
              f"ccp={len(rec['ccp'])} nutr={len(rec['nutrients_per_serving']):2} allergens={','.join(rec['allergens'])}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
