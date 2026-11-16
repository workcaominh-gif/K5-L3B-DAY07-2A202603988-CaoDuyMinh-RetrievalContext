"""Label agent outputs and aggregate them with the lab's starter/agent_metrics.py.

    python eval/score_agent.py            # every eval/results/agent_<config>_<split>.json

Labels (DRAFT - the student reviews them; the report lists the test rows read by hand):
  answer_grade 0/1/2     Claude Haiku 5.5 judge, given the question, the gold answer + evidence quote and the agent answer
                         (gold is used only to GRADE, never by the agent). Abstaining on an answerable question = 0.
  citation_support[i]    per citation: the judge reads the cited chunk's full text and decides whether it supports the
                         claim it is attached to; a deterministic hint is given (does the chunk contain the full gold quote?)
  abstention_correct     unanswerable questions: the agent abstained AND made no unsupported factual claim.
Outputs eval/results/{cases,traces,reviews}_<config>_<split>.json and metrics_<config>_<split>.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "starter"))
import run_day6 as R  # noqa: E402
from agent_metrics import aggregate  # noqa: E402

SCHEMA = {"type": "object", "properties": {
    "answer_grade": {"type": "integer"}, "citation_support": {"type": "array", "items": {"type": "boolean"}},
    "abstention_correct": {"type": "boolean"}, "reason": {"type": "string"}},
    "required": ["answer_grade", "citation_support", "abstention_correct", "reason"], "additionalProperties": False}


def judge(st: R.Day6, q: dict, row: dict) -> dict:
    cites = row["citations"]
    docs = "\n".join(f'<cited i="{k}" id="{c}" contains_full_gold_quote="{R.is_hit(q, {**st.chunks[c], "page_end": st.chunks[c]["page_end"] or st.chunks[c]["page"]}) if q.get("answerable", True) else "n/a"}">'
                     f'{" ".join(st.chunks[c]["text"].split())[:1500]}</cited>' for k, c in enumerate(cites) if c in st.chunks)
    gold = (f"Gold answer: {q['expected_answer']}\nGold evidence quote: {q['evidence_quote']}" if q.get("answerable", True)
            else f"This question has NO answer in the corpus ({q['absence_reason']}). Correct behaviour: abstain without inventing facts.")
    prompt = f"""You grade a RAG agent strictly. Question: {q['question']}
{gold}
Agent status: {row['status']}
Agent answer:
<answer>{row['answer']}</answer>
Cited chunks (in citation order):
{docs or '(none)'}

Return JSON:
- answer_grade: for an answerable question 2 = correct and complete with conditions, 1 = partly correct / missing a key
  condition, 0 = wrong, unsupported or abstained. For a no-answer question put 0.
- citation_support: one boolean per cited chunk, in order ({len(cites)} items): true only if that chunk's text supports the
  claim it is attached to.
- abstention_correct: for a no-answer question, true only if the agent abstained and stated no unsupported fact; otherwise false.
- reason: one sentence."""
    d = st._haiku_json(prompt, SCHEMA, max_tokens=4000)
    if d is None:
        raise RuntimeError(f"judge failed on {q['id']}")
    sup = [bool(x) for x in d["citation_support"]][:len(cites)]
    sup += [False] * (len(cites) - len(sup))
    grade = 0 if row["status"] == "abstain" and q.get("answerable", True) else max(0, min(2, int(d["answer_grade"])))
    rev = {"query_id": q["id"], "citation_support": sup, "reason": d["reason"], "labeler": "draft: claude-haiku-5-5 judge"}
    if q.get("answerable", True):
        rev["answer_grade"] = grade
    else:
        rev["abstention_correct"] = bool(d["abstention_correct"]) and row["status"] == "abstain"
    return rev


def main() -> None:
    qs = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "benchmark/day6_eu/questions.jsonl").read_text().splitlines() if l.strip()}
    st = R.Day6()
    out = ROOT / "eval" / "results"
    table = []
    for f in sorted(out.glob("agent_*_*.json")):
        cfg, split = f.stem.split("_")[1:3]
        rows = json.loads(f.read_text())["rows"]
        cases = [{"id": r["query_id"], "split": split, "answerable": r["answerable"]} for r in rows]
        traces = [{k: r[k] for k in ("query_id", "status", "events", "citations")} for r in rows]
        reviews = [judge(st, qs[r["query_id"]], r) for r in rows if r["status"] != "error"]
        m = aggregate(cases, traces, reviews)
        ans = [r for r in rows if r["answerable"]]
        m.update(config=cfg, split=split, context_evidence_rate=f"{sum(bool(r['context_evidence']) for r in ans)}/{len(ans)}",
                 searches_per_q=round(sum(r["searches"] for r in rows) / len(rows), 2),
                 cost_usd=round(sum(r["cost_usd"] for r in rows), 3), median_seconds=sorted(r["seconds"] for r in rows)[len(rows) // 2],
                 judge_cost_usd=round((st.usage[0] * R.PRICE[0] + st.usage[1] * R.PRICE[1]) / 1e6, 4))
        for name, obj in (("cases", cases), ("traces", traces), ("reviews", reviews), ("metrics", m)):
            (out / f"{name}_{cfg}_{split}.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
        g, cv, ab, fa = m["grounded_answer"], m["citation_validity"], m["abstention"], m["false_abstention"]
        table.append(f"| {cfg} | {split} | {m['tool_use']['n']}/{m['tool_use']['N']} | {m['searches_per_q']} | "
                     f"{g['0']}/{g['1']}/{g['2']} · {g['mean']:.2f} | {cv['n']}/{cv['N']} | {m['answer_citation_coverage']['n']}/{m['answer_citation_coverage']['N']} | "
                     f"{ab['n']}/{ab['N']} | {fa['n']}/{fa['N']} | {m['context_evidence_rate']} | ${m['cost_usd']} · {m['median_seconds']} s |")
    print("| Cấu hình | Split | Tool use | Lượt tìm/câu | Grounded 0/1/2 · TB | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm | Context Evidence | Chi phí · thời gian TV |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    print("\n".join(table))


if __name__ == "__main__":
    main()
