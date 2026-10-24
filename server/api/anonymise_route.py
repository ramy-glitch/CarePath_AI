"""Stateless anonymisation endpoint for synthetic PNG/JPEG blood-test images.

POST /api/v1/anonymise with image bytes (not multipart/form-data).
No chat, model or retrieval integration; no patient-specific server state.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from anonymisation.discard_original import discard_original
from anonymisation.ocr import MAX_IMAGE_BYTES
from anonymisation.privacy import redact_report
from anonymisation.to_lab_json import to_lab_json

router = APIRouter(prefix="/api/v1", tags=["anonymisation"])


class ReferenceRange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    low: float
    high: float


class LabResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    testName: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    referenceRange: ReferenceRange | None
    flag: Literal["low", "normal", "high", "unknown"]


class AnonymisedReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    results: list[LabResult] = Field(min_length=1)
    reviewRequired: Literal[True]


@router.post("/anonymise", response_model=AnonymisedReport)
async def anonymise(request: Request) -> AnonymisedReport:
    """Return only lab JSON; fail closed without echoing patient content."""
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(415, "Only PNG or JPEG image bodies are supported")

    original = bytearray()
    redaction = None
    try:
        async for chunk in request.stream():
            if len(original) + len(chunk) > MAX_IMAGE_BYTES:
                raise HTTPException(413, "Image exceeds size limit")
            original.extend(chunk)
        if not original:
            raise HTTPException(422, "Empty image")

        # Existing API takes bytes. This creates a temporary immutable copy;
        # do not claim that the Python process securely wipes all memory.
        redaction = redact_report(bytes(original))
        document = to_lab_json(redaction.redacted_text)
        return AnonymisedReport.model_validate(document)
    except HTTPException:
        raise
    except (ValueError, OSError, ValidationError):
        # Never echo source text, detailed parser errors, or identifiers.
        raise HTTPException(422, "Image could not be safely anonymised and parsed") from None
    finally:
        if redaction is not None:
            redaction.redacted_image.close()
        discard_original(original)
