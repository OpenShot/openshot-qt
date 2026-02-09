"""Local (and optional OpenAI-assisted) search over ai_metadata.scene_descriptions.

This is used as a fallback when TwelveLabs isn't configured/ready.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, Optional

from classes.logger import log


_WORD_RE = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall((text or "").lower())


def _score_local(query: str, description: str) -> float:
    q = (query or "").strip().lower()
    d = (description or "").strip().lower()
    if not q or not d:
        return 0.0

    if q in d:
        # Strong boost for substring match
        return 10.0 + min(5.0, len(q) / 20.0)

    q_tokens = set(_tokenize(q))
    d_tokens = set(_tokenize(d))
    if not q_tokens or not d_tokens:
        return 0.0

    overlap = len(q_tokens.intersection(d_tokens))
    if overlap == 0:
        return 0.0

    # Simple TF-ish score
    return float(overlap) / math.sqrt(len(q_tokens) * len(d_tokens))


def search_scene_descriptions(
    ai_metadata: Dict[str, Any],
    query: str,
    *,
    top_k: int = 5,
    use_openai_rerank: bool = True,
) -> List[Dict[str, Any]]:
    """Return best matching scene_descriptions entries.

    Each result: {time, description, score, source}
    """
    if not isinstance(ai_metadata, dict) or not ai_metadata.get("analyzed"):
        return []

    scenes = ai_metadata.get("scene_descriptions")
    if not isinstance(scenes, list) or not scenes:
        return []

    scored: List[Dict[str, Any]] = []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        t = float(s.get("time", 0.0) or 0.0)
        desc = (s.get("description") or "").strip()
        if not desc:
            continue
        score = _score_local(query, desc)
        if score <= 0:
            continue
        scored.append({"time": t, "description": desc, "score": float(score), "source": "local"})

    scored.sort(key=lambda x: x["score"], reverse=True)
    candidates = scored[: max(top_k * 5, 20)]

    if not use_openai_rerank or not candidates:
        return candidates[:top_k]

    # Optional rerank using OpenAI if available.
    try:
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
        if not api_key:
            return candidates[:top_k]
        if not os.getenv("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = api_key

        from langchain_openai import ChatOpenAI  # type: ignore

        # Keep it cheap: rerank only top N
        n = min(len(candidates), 20)
        items = candidates[:n]

        prompt = (
            "You are reranking time-coded scene descriptions for a video clip.\n"
            "Return JSON: {\"best\": [{\"idx\": int, \"score\": float, \"why\": str}] }\n"
            "Choose up to {top_k} items most relevant to the query.\n\n"
            "Query: {query}\n\n"
            "Candidates:\n{cands}\n"
        ).format(
            top_k=top_k,
            query=query,
            cands="\n".join([f"{i}: [{items[i]['time']:.2f}] {items[i]['description']}" for i in range(n)]),
        )

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        resp = llm.invoke(prompt)
        text = getattr(resp, "content", "") if resp is not None else ""

        import json

        data = json.loads(text) if isinstance(text, str) else {}
        best = data.get("best") if isinstance(data, dict) else None
        if not isinstance(best, list) or not best:
            return candidates[:top_k]

        reranked: List[Dict[str, Any]] = []
        for b in best:
            if not isinstance(b, dict):
                continue
            idx = b.get("idx")
            if not isinstance(idx, int) or idx < 0 or idx >= n:
                continue
            picked = dict(items[idx])
            picked["source"] = "openai_rerank"
            score_val = b.get("score")
            if isinstance(score_val, (int, float)):
                picked["score"] = float(score_val)
            reranked.append(picked)

        # Fill any gaps with remaining candidates
        seen = {(r["time"], r["description"]) for r in reranked}
        for c in items:
            key = (c["time"], c["description"])
            if key in seen:
                continue
            reranked.append(c)
            if len(reranked) >= top_k:
                break

        return reranked[:top_k]

    except Exception as e:
        log.debug(f"OpenAI rerank unavailable: {e}")
        return candidates[:top_k]
