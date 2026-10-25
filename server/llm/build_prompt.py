"""Assemble one chat request from the lab JSON, the question, and accepted passages."""

from __future__ import annotations

import json
from collections.abc import Sequence

from llm.system_prompt import SYSTEM_PROMPT
from retrieval.corpus_loader import Passage


def build_messages(
    *,
    lab: dict,
    question: str,
    passages: Sequence[Passage],
    history: Sequence[dict] = (),
) -> list[dict[str, str]]:
    """System instruction, earlier turns, then this turn with the passages attached."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend({"role": turn["role"], "content": turn["content"]} for turn in history)
    messages.append({"role": "user", "content": _user_content(lab, question, passages)})
    return messages


def _user_content(lab: dict, question: str, passages: Sequence[Passage]) -> str:
    blocks = [
        f"{number}. id: {passage.id}\ntitle: {passage.title}\ntext: {passage.text}"
        for number, passage in enumerate(passages, start=1)
    ]
    lab_text = json.dumps(lab, ensure_ascii=False)
    return f"Lab result:\n{lab_text}\n\nQuestion:\n{question}\n\nPassages:\n" + "\n\n".join(blocks)
