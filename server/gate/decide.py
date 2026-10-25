"""Accept the model reply only when it marks the retrieved passages as covering the result."""

from __future__ import annotations

import json
from collections.abc import Sequence

from gate.fixed_message import fixed_message
from passages.citation_payload import citation_payload
from retrieval.corpus_loader import Passage

MAX_EXPLANATION_CHARS = 4000


def uncovered() -> dict:
    """Fixed message and no passages. Used when retrieval or the model declines."""
    return {"covered": False, "explanation": fixed_message(), "passages": []}


def decide(model_text: str, passages: Sequence[Passage]) -> dict:
    """Keep the explanation only for a covered reply that cites at least one passage."""
    parsed = _parse(model_text)
    if parsed is None or not passages or parsed.get("covered") is not True:
        return uncovered()
    explanation = parsed.get("explanation")
    if not isinstance(explanation, str):
        return uncovered()
    explanation = explanation.strip()
    if not explanation or len(explanation) > MAX_EXPLANATION_CHARS:
        return uncovered()
    return {
        "covered": True,
        "explanation": explanation,
        "passages": citation_payload(passages),
    }


def _parse(model_text: str) -> dict | None:
    text = model_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    return value
