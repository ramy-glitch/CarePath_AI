"""Citation records returned to the browser. The browser deletes them after they are shown."""

from __future__ import annotations

from collections.abc import Sequence

from retrieval.corpus_loader import Passage


def citation_payload(passages: Sequence[Passage]) -> list[dict]:
    return [passage.as_record() for passage in passages]
