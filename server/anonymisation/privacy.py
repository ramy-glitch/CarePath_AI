"""In-memory OCR plus identifier masking for synthetic blood-test images.

Demo only. Automated detection is not complete de-identification.
The image and the raw OCR text are not logged or written to disk.
"""

from dataclasses import dataclass

from PIL import Image

from .ocr import extract_report, open_image
from .redact_image import mask_image, spans_map_to_tokens
from .redact_text import find_identifiers, mask_text


@dataclass
class RedactionResult:
    redacted_text: str
    redacted_image: Image.Image
    removed_categories: list[str]
    ocr_confidence: float | None
    review_required: bool = True


def redact_report(data: bytes, analyzer=None, anonymizer=None) -> RedactionResult:
    """Detect Presidio spans and cover their OCR bounding boxes.

    All detected tokens overlapping an entity span are masked. The resulting
    image must still receive human visual review because OCR and named-entity
    recognition may miss identifiers.
    """
    if analyzer is None:
        from presidio_analyzer import AnalyzerEngine

        analyzer = AnalyzerEngine()
    if anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine

        anonymizer = AnonymizerEngine()
    image = open_image(data)
    text, tokens = extract_report(image)
    findings = find_identifiers(text, analyzer)
    spans = [(int(item.start), int(item.end)) for item in findings]
    spans_map_to_tokens(tokens, spans)
    redacted = mask_image(image, tokens, spans)
    masked_text = mask_text(text, anonymizer, findings)
    confidences = [token.confidence for token in tokens if token.confidence >= 0]
    return RedactionResult(
        redacted_text=masked_text,
        redacted_image=redacted,
        removed_categories=sorted({str(item.entity_type) for item in findings}),
        ocr_confidence=round(sum(confidences) / len(confidences), 1) if confidences else None,
    )
