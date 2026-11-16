"""Build the manual-review sheet for the DGA test run (no API calls).

    python eval/dga_review_sheet.py            # -> eval/results/dga/REVIEW_test.md
    python eval/dga_review_sheet.py --adopt "Ho Ten" t01,t02,...   # ONLY after reading those questions yourself:
        copies the proposed labels of the listed ids into manual_review_test.json under your name (use --adopt "Ho Ten" all
        for every id). Override any label you disagree with by editing manual_review_test.json directly.

Inputs: benchmark/dga/questions.jsonl (gold), eval/results/dga/agent_vision_test.json (trace),
eval/results/dga/labels_vision_test.json (automatic DRAFT labels), eval/results/dga/manual_review_test.json
(human labels: {query_id: {"pass": bool, "reason": str, "reviewer": str}}). The official label of a question is the
human label when present, otherwise it is still pending. Both the automatic and the human pass rates are printed.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "eval" / "results" / "dga"
GROUPS = ["table", "image", "chart", "multihop", "text", "none"]


def main() -> None:
    Q = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "benchmark/dga/questions.jsonl").read_text().splitlines() if l.strip()}
    rows = {r["query_id"]: r for r in json.loads((RES / "agent_vision_test.json").read_text())["rows"]}
    labs = {l["query_id"]: l for l in json.loads((RES / "labels_vision_test.json").read_text())["labels"]}
    mf = RES / "manual_review_test.json"
    man = json.loads(mf.read_text()) if mf.exists() else {}
    pf = RES / "proposed_review_test.json"           # assistant's proposals after checking the original crops; NOT human labels
    prop = json.loads(pf.read_text()) if pf.exists() else {}
    ids = sorted(i for i, q in Q.items() if q["split"] == "test")
    auto, human, proposed, pending = Counter(), Counter(), Counter(), []
    out = ["# Duyệt tay benchmark test DGA (cấu hình chốt `vision`)", "",
           "Mỗi câu: câu hỏi, đáp án gold + vùng bằng chứng (crop trong `benchmark/dga/crops/`), câu trả lời và citation của agent,",
           "nhãn tự động (DRAFT: kiểm citation tất định + judge Sonnet 5.5) và nhãn duyệt tay (`manual_review_test.json`).", ""]
    for i in ids:
        q, r, l = Q[i], rows[i], labs[i]
        h = man.get(i)
        auto[(q["group"], l["pass"])] += 1
        proposed[(q["group"], prop[i]["pass"] if i in prop else l["pass"])] += 1
        if h:
            human[(q["group"], h["pass"])] += 1
        else:
            pending.append(i)
        ev = "; ".join(f"p.{e['pdf_page']} {e.get('ref') or e['kind']}" + (f" ([crop]({'../../../' + e['crop']}))" if e.get("crop") else "")
                       for e in q.get("evidence", []))
        cc = l.get("citation_check") or {}
        miss = [e["ref"] for e in cc.get("evidence", []) if not e.get("satisfied_by")]
        out += [f"## {i} · {q['group']}", "", f"**Hỏi:** {q['question']}", "",
                f"**Gold:** {q.get('expected_answer') or 'abstain — ' + (q.get('near_topic') or '')}", "",
                f"**Bằng chứng gold:** {ev or '—'}", "",
                f"**Agent ({r['status']}, {r['seconds']} s, ${r['cost_usd']}):** " + " ".join(r["answer"].split())[:1500], "",
                f"**Citation:** {', '.join(r['citations']) or '—'}", "",
                f"**Nhãn tự động:** {'ĐẠT' if l['pass'] else 'KHÔNG ĐẠT'} — {l.get('reason', '')}"
                + (f" · vùng gold chưa được cite: {miss}" if miss and q['answerable'] else ""), "",
                *([f"**Đề xuất (chưa phải nhãn duyệt tay):** {'ĐẠT' if prop[i]['pass'] else 'KHÔNG ĐẠT'} — {prop[i]['reason']}", ""] if i in prop else []),
                f"**Nhãn duyệt tay:** " + (f"{'ĐẠT' if h['pass'] else 'KHÔNG ĐẠT'} — {h['reason']} ({h.get('reviewer', '')})" if h else "_chờ duyệt_"), ""]
    n = len(ids)

    def line(c: Counter, name: str) -> str:
        tot = sum(v for (g, p), v in c.items() if p)
        per = " | ".join(f"{sum(v for (g2, p), v in c.items() if g2 == g and p)}/{sum(1 for i in ids if Q[i]['group'] == g)}" for g in GROUPS)
        return f"| {name} | {tot}/{n} ({100 * tot / n:.1f}%) | {per} |"
    head = ["## Tổng hợp", "", "| Nhãn | Đạt | " + " | ".join(GROUPS) + " |", "|---" * (len(GROUPS) + 2) + "|",
            line(auto, "Tự động (DRAFT)"), line(proposed, "Tự động + đề xuất sau khi xem crop gốc (chưa duyệt tay)"), line(human, f"Duyệt tay ({n - len(pending)}/{n} câu đã duyệt)"), "",
            f"Câu chưa duyệt tay: {', '.join(pending) or 'không'}", ""]
    (RES / "REVIEW_test.md").write_text("\n".join(out[:5] + head + out[5:]) + "\n", encoding="utf-8")
    print("\n".join(head))


def adopt(name: str, ids: str) -> None:
    prop = json.loads((RES / "proposed_review_test.json").read_text())
    mf = RES / "manual_review_test.json"
    man = json.loads(mf.read_text()) if mf.exists() else {}
    for i in (sorted(prop) if ids == "all" else ids.split(",")):
        man[i] = {"pass": prop[i]["pass"], "reason": prop[i]["reason"],
                  "reviewer": f"{name} (đã đọc câu hỏi, câu trả lời, crop gốc và xác nhận nhãn đề xuất)"}
    mf.write_text(json.dumps(dict(sorted(man.items())), ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    import sys
    if "--adopt" in sys.argv:
        k = sys.argv.index("--adopt")
        adopt(sys.argv[k + 1], sys.argv[k + 2])
    main()
