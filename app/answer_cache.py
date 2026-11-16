"""Answer cache: reuse a verified final answer for a repeated standalone question (0 tokens, ~0 s).

Scope (to stay correct):
  - only first turns of a session (no conversation history) and only questions without attachments;
  - only answers that passed the output guardrail with >= 1 valid citation and no abstention / errors;
  - keyed by KB version (row counts of kb_cook / kb_image / kg_edges + system-prompt hash): any re-index or prompt
    change invalidates every entry automatically.
Lookup: exact match on the normalised question, else semantic match (bge cosine >= 0.95) on the question.
Stored in <work>/cache/answers.jsonl (question, embedding, answer payload, source trace session, created).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata

import numpy as np

import tools as T

SIM = 0.95
PATH = T.WORK / "cache" / "answers.jsonl"
_mem: list[dict] | None = None
_counts: list | None = None


def norm(q: str) -> str:
    q = unicodedata.normalize("NFC", q).lower().strip()
    return re.sub(r"[\s?.!,;:]+", " ", q).strip()


def kb_version(system_prompt: str) -> str:
    """Row counts of the stores + system prompt + retrieval method/backend (passed in the prompt key)."""
    global _counts
    if _counts is None:
        with T.M._conn() as c:
            _counts = [c.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("kb_cook", "kb_image", "kg_edges")]
    return hashlib.sha1(f"{_counts}|{system_prompt}".encode()).hexdigest()[:12]


def _embed(q: str) -> np.ndarray:
    from src.embeddings import MyEmbedder
    if "bge" not in T.M._cache:
        T.M._cache["bge"] = MyEmbedder("BAAI/bge-small-en-v1.5")
    return np.array(T.M._cache["bge"].embed_query(q), dtype=np.float32)


def _load() -> list[dict]:
    global _mem
    if _mem is None:
        _mem = [json.loads(l) for l in PATH.read_text(encoding="utf-8").splitlines()] if PATH.exists() else []
    return _mem


def lookup(question: str, system_prompt: str) -> dict | None:
    ver, nq = kb_version(system_prompt), norm(question)
    rows = [r for r in _load() if r["kb_version"] == ver]
    for r in rows:
        if r["norm"] == nq:
            return {**r["payload"], "cache": {"kind": "exact", "similarity": 1.0, "of": r["question"], "trace_session": r["session"]}}
    if not rows:
        return None
    v = _embed(question)
    sims = np.array([r["emb"] for r in rows], dtype=np.float32) @ v
    k = int(np.argmax(sims))
    if sims[k] >= SIM:
        r = rows[k]
        return {**r["payload"], "cache": {"kind": "semantic", "similarity": round(float(sims[k]), 3), "of": r["question"], "trace_session": r["session"]}}
    return None


def store(question: str, system_prompt: str, payload: dict, session: str) -> None:
    if payload.get("abstained") or not payload.get("citations") or payload.get("flags"):
        return
    PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"question": question, "norm": norm(question), "kb_version": kb_version(system_prompt), "session": session,
           "created": round(time.time()), "emb": [round(float(x), 5) for x in _embed(question)],
           "payload": {k: payload.get(k) for k in ("answer", "citations", "abstained", "flags", "steps", "tokens", "cost_usd", "seconds", "media")}}
    _load().append(row)
    with open(PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
