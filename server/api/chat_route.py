"""Anonymised lab JSON in, explanation out. The request is not stored."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gate.decide import decide, uncovered
from llm.build_prompt import build_messages
from passages.citation_payload import citation_payload
from llm.ollama_client import ModelUnavailable, complete
from retrieval import build_query, search
from retrieval.corpus_loader import Passage

router = APIRouter()

_BANDS = frozenset({"low", "normal", "high"})


class ReferenceRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low: float
    high: float


class LabRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    testName: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    referenceRange: ReferenceRange | None
    flag: Literal["low", "normal", "high", "unknown"]


class LabResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[LabRow] = Field(min_length=1)
    reviewRequired: Literal[True]


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def content_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("History content is empty")
        return stripped


class ChatTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab: LabResult
    question: str = Field(min_length=1, max_length=2000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=20)

    @field_validator("question")
    @classmethod
    def question_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question is empty")
        return stripped


class CitedPassage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    panel: str
    analyte: str
    aliases: list[str]
    band: Literal["low", "normal", "high"]
    title: str
    text: str
    simulatedUrl: str


class ChatTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    covered: bool
    explanation: str = Field(min_length=1)
    passages: list[CitedPassage]


_EXTRA_ANALYTES = {
    "white blood cells": "white_cell_count",
    "white cells": "white_cell_count",
}
_RANGE_NOT_CONFIRMED = (
    "The range on this result was not confirmed, so this does not say whether the number is high or low."
)


def _norm(value: str) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in value).split())


def _matches(passage: Passage, test_name: str) -> bool:
    needle = _norm(test_name)
    if _EXTRA_ANALYTES.get(needle) == passage.analyte:
        return True
    names = [passage.analyte.replace("_", " "), *passage.aliases]
    return any(_norm(name) == needle for name in names)


def _definition(text: str) -> str:
    sentence = text.strip().split(". ", 1)[0].strip().rstrip(".")
    return f"{sentence}."


def _prefer(passages: list[Passage]) -> Passage:
    for band in ("normal", "low", "high"):
        for passage in passages:
            if passage.band == band:
                return passage
    return passages[0]


def explain_without_a_band(index, lab: LabResult, _question: str) -> dict | None:
    """A row with no confirmed range can still say what the test is.

    The band-specific sentences in the library are not shown, because they would
    claim the result is high, low, or normal.
    """
    catalog = getattr(index, "passages", None)
    if not isinstance(catalog, dict):
        return None
    explanations: list[str] = []
    shown: list[Passage] = []
    seen: set[str] = set()
    for row in lab.results:
        if row.flag in _BANDS:
            continue
        matched = [passage for passage in catalog.values() if _matches(passage, row.testName)]
        if not matched:
            continue
        chosen = _prefer(matched)
        if chosen.id in seen:
            continue
        seen.add(chosen.id)
        definition = _definition(chosen.text)
        explanations.append(definition)
        shown.append(replace(chosen, title=row.testName, text=definition))
    if not explanations:
        return None
    return {
        "covered": True,
        "explanation": f"{' '.join(explanations)} {_RANGE_NOT_CONFIRMED}",
        "passages": citation_payload(shown),
    }


def accepted_passages(index, lab: LabResult, question: str) -> list[Passage]:
    """Search once per flagged row. A full panel does not fit in one top-3 query."""
    found: list[Passage] = []
    seen: set[str] = set()
    for row in lab.results:
        if row.flag not in _BANDS:
            continue
        query = build_query(analyte=row.testName, band=row.flag, question=question)
        result = search(index, query)
        if not result.accepted:
            continue
        for passage in result.passages:
            if passage.id in seen:
                continue
            seen.add(passage.id)
            found.append(passage)
    return found


def answer_turn(index, body: ChatTurnRequest) -> dict:
    """Retrieve, then call the model only when at least one passage clears the cutoff."""
    passages = accepted_passages(index, body.lab, body.question)
    if not passages:
        explained = explain_without_a_band(index, body.lab, body.question)
        return explained if explained is not None else uncovered()
    messages = build_messages(
        lab=body.lab.model_dump(),
        question=body.question,
        passages=passages,
        history=[turn.model_dump() for turn in body.history],
    )
    return decide(complete(messages), passages)


@router.post("/chat", response_model=ChatTurnResponse)
def chat_turn(body: ChatTurnRequest, request: Request) -> dict:
    index = getattr(request.app.state, "retrieval", None)
    if index is None:
        raise HTTPException(status_code=503, detail="The explanation service is unavailable.")
    try:
        return answer_turn(index, body)
    except ModelUnavailable:
        raise HTTPException(status_code=503, detail="The explanation service is unavailable.") from None
