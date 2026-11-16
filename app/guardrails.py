"""Guardrails and boundaries around the agent. Layers: input -> tool calls -> tool results -> output.

Input   : size limit, empty check, prompt-injection heuristics (flagged + logged; the request is still answered
          inside the boundary, never with elevated behaviour), secrets/PII never echoed.
Tools   : allowlist (tools.TOOLS), JSON-schema argument check, numeric clamps inside each tool, per-turn budget
          (MAX_STEPS tool calls, MAX_TOKENS_TURN), per-tool timeout via errors -> observation, never a crash.
Results : every tool result is wrapped as <untrusted_data> before the model sees it; instruction-like lines inside
          retrieved content are neutralised (document text is data, not instructions).
Output  : every [cite:...] must be an id that a tool returned in THIS turn; unknown ids are removed; an answer
          with factual content but no valid citation is replaced by an abstention. Allergen answers get the
          "rule-based, check the label" caveat if the model omitted it.
"""
from __future__ import annotations

import json
import re

MAX_INPUT_CHARS = 2000
MAX_STEPS = 8                 # model rounds (Thought -> Action[s]) per user turn
MAX_CALLS = 24                # tool calls per user turn; parallel calls in one round count individually
MAX_DUPLICATE_CALLS = 3       # identical (tool, arguments) repeats per turn before tools are refused
MAX_VERIFIER_NUDGES = 2       # self-correction retries per turn
REPEAT_SIM = 0.85             # word-trigram Jaccard above which an answer counts as a repeat of an earlier one
MAX_TOKENS_TURN = 60_000      # input+output tokens per user turn (cost boundary)
INJECTION = re.compile(r"(ignore (all|any|the|previous|prior) (instructions|rules)|disregard .*instructions|system prompt|"
                       r"you are now|developer mode|jailbreak|reveal .*(prompt|key|token)|api[_ -]?key|\bsudo\b)", re.I)
SECRET = re.compile(r"(sk-ant-[A-Za-z0-9_-]{10,}|hf_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")
CITE = re.compile(r"\[cite:([^\]\s]+)\]")
ABSTAIN = "Không đủ bằng chứng trong kho tài liệu để trả lời câu này."
ABSTAIN_EN = "Not enough evidence in the knowledge base to answer this."
VI = re.compile(r"[ăâđêôơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ]", re.I)
SCOPE = "[out_of_scope]"


def check_input(text: str) -> dict:
    flags = []
    if not text.strip():
        return {"ok": False, "reason": "empty", "flags": flags}
    if len(text) > MAX_INPUT_CHARS:
        return {"ok": False, "reason": f"message longer than {MAX_INPUT_CHARS} characters", "flags": flags}
    if INJECTION.search(text):
        flags.append("possible_prompt_injection")
    if SECRET.search(text):
        flags.append("secret_in_input")
        text = SECRET.sub("[REDACTED]", text)
    return {"ok": True, "text": text, "flags": flags}


def check_tool_call(name: str, args: dict, tools: list[dict]) -> str | None:
    spec = next((t for t in tools if t["name"] == name), None)
    if spec is None:
        return f"tool '{name}' is not allowed"
    schema = spec["input_schema"]
    for k in schema.get("required", []):
        if k not in args:
            return f"missing argument '{k}'"
    for k, v in args.items():
        p = schema["properties"].get(k)
        if p is None:
            return f"unknown argument '{k}'"
        t = p.get("type")
        if (t == "string" and not isinstance(v, str)) or (t == "integer" and not isinstance(v, int)) or \
           (t == "number" and not isinstance(v, (int, float))):
            return f"argument '{k}' must be {t}"
        if "enum" in p and v not in p["enum"]:
            return f"argument '{k}' must be one of {p['enum']}"
        if isinstance(v, str) and len(v) > 500:
            return f"argument '{k}' too long"
    return None


def wrap_result(name: str, result: dict) -> str:
    s = json.dumps(result, ensure_ascii=False, default=str)
    s = INJECTION.sub(lambda m: f"[neutralised:{m.group(0)[:20]}]", s)
    s = SECRET.sub("[REDACTED]", s)
    return f'<untrusted_data tool="{name}">\n{s[:12000]}\n</untrusted_data>'


def collect_ids(obj, out: set) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("cite", "id") and isinstance(v, str):
                out.add(v)
            collect_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_ids(v, out)


_BARE = re.compile(r"\[(?!cite:)\s*((?:img:)?(?:cookbook|yt|pkg)[^\]\[]*?)\s*\]")


def normalize_citations(answer: str) -> str:
    """Accept the variants models write - [cookbook:p131], [cite: x], [a; b] - as [cite:...] tags (one id per tag)."""
    def bare(m):
        ids = [x.strip() for x in re.split(r"[;,]\s*|\s+", m.group(1)) if re.match(r"(?:img:)?(?:cookbook|yt|pkg):", x.strip())]
        return "".join(f"[cite:{i}]" for i in ids) if ids else m.group(0)
    answer = re.sub(r"\[cite:\s+", "[cite:", answer)
    answer = re.sub(r"\[cite:([^\]]+?)[;,]\s*([^\]]+)\]", lambda m: "".join(f"[cite:{x.strip()}]" for x in re.split(r"[;,]", m.group(1) + "," + m.group(2))), answer)
    return _BARE.sub(bare, answer)


def check_output(answer: str, allowed: set, question: str = "") -> dict:
    answer = normalize_citations(answer)
    if SCOPE in answer:                      # deliberate scope refusal (medical, off-topic): keep the model's wording
        return {"answer": linkify_videos(answer.replace(SCOPE, "")).strip(), "citations": [], "abstained": True, "flags": ["out_of_scope_refusal"]}
    used = CITE.findall(answer)
    bad = [c for c in used if c not in allowed]
    for c in bad:                      # keep the gap visible: an uncited claim must not look sourced
        answer = answer.replace(f"[cite:{c}]", " ⚠ *không có nguồn*")
    good = [c for c in dict.fromkeys(used) if c in allowed]
    abstained = ABSTAIN[:20] in answer or "not enough evidence" in answer.lower() or "không đủ bằng chứng" in answer.lower()
    flags = [f"removed_unverified_citation:{c}" for c in bad]
    if not good and not abstained:
        flags.append("no_valid_citation->abstain")
        answer, abstained = (ABSTAIN if VI.search(question) else ABSTAIN_EN), True
    if re.search(r"allergen|dị ứng|allergy", answer, re.I) and "label" not in answer.lower() and "nhãn" not in answer.lower():
        answer += "\n\n_Lưu ý: thông tin dị ứng được suy ra từ tên nguyên liệu, hãy kiểm tra nhãn sản phẩm thực tế._"
        flags.append("added_allergen_caveat")
    linked = linkify_videos(answer)
    if linked != answer:
        flags.append("linkified_bare_video_id")
    return {"answer": linked.strip(), "citations": good, "abstained": abstained, "flags": flags}


YT = re.compile(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{11})(?:\?t=|&t=)?(\d+)?")


def collect_media(obj, out: dict) -> None:
    """cite id -> playable moment / page thumbnail, harvested from tool observations (for the UI to embed)."""
    if isinstance(obj, dict):
        cid = obj.get("cite") or obj.get("id")
        if isinstance(cid, str):
            link = obj.get("link") or obj.get("source") or ""
            m = YT.search(link) if isinstance(link, str) else None
            t = obj.get("t") if obj.get("t") is not None else obj.get("t0")
            if m:
                out.setdefault(cid, {"type": "video", "video_id": m.group(1),
                                     "t": int(t if t is not None else (m.group(2) or 0))})
            elif obj.get("pdf_page"):
                out.setdefault(cid, {"type": "page", "pdf_page": int(obj["pdf_page"]), "recipe": obj.get("recipe")})
            else:
                mm = re.match(r"(?:img:)?cookbook:p(\d{3})", cid)
                if mm:
                    out.setdefault(cid, {"type": "page", "pdf_page": int(mm.group(1))})
                mv = re.match(r"(?:img:)?yt:([A-Za-z0-9_-]{11})@(\d+)", cid)
                if mv:
                    out.setdefault(cid, {"type": "video", "video_id": mv.group(1), "t": int(mv.group(2))})
        for v in obj.values():
            collect_media(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_media(v, out)


def pick_media(citations: list[str], media: dict, primary: list[str], limit: int = 4) -> list[dict]:
    """Media for the cited ids first, then the top hits of image/audio analyses; one entry per video moment / page."""
    seen, out = set(), []
    for cid in list(citations) + list(primary):
        m = media.get(cid)
        if not m:
            continue
        key = (m["type"], m.get("video_id"), m.get("t") if m["type"] == "video" else m.get("pdf_page"))
        if key in seen:
            continue
        seen.add(key)
        out.append({**m, "cite": cid})
        if len(out) >= limit:
            break
    return out


VIDEOS = {"QhkDOr6kmi4": "Golden Squash Hotcakes", "eSKtPtW0X2o": "Corn and Zucchini Pancakes"}
_VID = re.compile(r"(?<![/:=?\w])`?(QhkDOr6kmi4|eSKtPtW0X2o)`?(?![\w\]])")
_TIME = re.compile(r"^[^\n\[\]]{0,40}?(?:(\d{1,2}):(\d{2})|(\d{1,4})(?:[.,]\d+)?\s*(?:giây|s\b|sec|seconds)|(?:giây|second)\s*(\d{1,4}))")


def linkify_videos(answer: str) -> str:
    """Backstop for the output contract: a bare video id becomes '[Title ▶ m:ss](https://youtu.be/ID?t=S)'.
    The time is taken from the text right after the id (m:ss, or seconds) when present."""
    out, pos = [], 0
    for m in _VID.finditer(answer):
        vid = m.group(1)
        tm = _TIME.match(answer[m.end():])
        t = None
        if tm:
            t = int(tm.group(1)) * 60 + int(tm.group(2)) if tm.group(1) else int(tm.group(3) or tm.group(4))
        label = VIDEOS[vid] + (f" ▶ {t // 60}:{t % 60:02d}" if t is not None else "")
        out.append(answer[pos:m.start()] + f"[{label}](https://youtu.be/{vid}" + (f"?t={t}" if t is not None else "") + ")")
        pos = m.end()
    return "".join(out) + answer[pos:]



def call_key(name: str, args: dict) -> str:
    return name + ":" + json.dumps(args, sort_keys=True, ensure_ascii=False)


def _trigrams(t: str) -> set:
    w = re.findall(r"\w+", re.sub(r"\[cite:[^\]]+\]", "", t.lower()))
    return {" ".join(w[i:i + 3]) for i in range(max(0, len(w) - 2))}


def similarity(a: str, b: str) -> float:
    A, B = _trigrams(a), _trigrams(b)
    return len(A & B) / max(1, len(A | B))


def dedupe_lines(answer: str) -> tuple[str, int]:
    """Remove a line that exactly repeats an earlier non-empty line of the same answer (model stutter)."""
    seen, out, dropped = set(), [], 0
    for line in answer.split("\n"):
        key = re.sub(r"\s+", " ", line.strip().lower())
        if len(key) > 20 and key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(line)
    return "\n".join(out), dropped
