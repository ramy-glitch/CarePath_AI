"""In-memory anonymisation for this server. Synthetic reports only. The upload is not stored."""

from .privacy import RedactionResult, redact_report

__all__ = ["RedactionResult", "redact_report"]
