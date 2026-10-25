"""Anonymised lab JSON in, explanation out. The request is not stored."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from gate.decide import decide, uncovered
from llm.build_prompt import build_messages
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
        return uncovered()
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
