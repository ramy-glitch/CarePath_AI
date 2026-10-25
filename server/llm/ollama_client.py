"""One non-streaming call to the local chat model.

The embedding model that builds the retrieval index is separate. This client never stores the request.
"""

from __future__ import annotations

import json
import logging

import httpx
from ollama import Client, ResponseError

from config import settings

logger = logging.getLogger(__name__)


class ModelUnavailable(Exception):
    """Ollama did not return a usable reply. The message carries no request content."""


def complete(messages: list[dict[str, str]]) -> str:
    """Return the model's JSON text. Thinking mode stays off so the reply can be discarded whole."""
    try:
        with Client(host=settings.OLLAMA_BASE_URL, timeout=settings.CHAT_TIMEOUT_SECONDS) as client:
            response = client.chat(
                model=settings.CHAT_MODEL,
                messages=messages,
                stream=False,
                think=False,
                format=_coverage_schema(),
            )
    except (OSError, ResponseError, httpx.HTTPError) as exc:
        logger.warning("Ollama chat failed: %s", type(exc).__name__)
        raise ModelUnavailable from exc

    content = response.message.content
    if not isinstance(content, str) or not content.strip():
        logger.warning("Ollama chat failed: empty reply")
        raise ModelUnavailable
    return content


def _coverage_schema() -> dict:
    raw = json.loads(settings.COVERAGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": raw["required"],
        "properties": raw["properties"],
    }
