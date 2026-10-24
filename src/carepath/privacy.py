"""In-memory OCR + PII masking for synthetic blood test images.

Demo only. Automated detection is not complete de-identification.
Never log or persist raw OCR text or original images.
"""
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pytesseract
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError
from pytesseract import Output

TESSERACT_PATH = "/opt/anaconda3/envs/carepath-ocr/bin/tesseract"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 10_000_000
ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"]


@dataclass(frozen=True)
class OCRToken:
    text: str
    start: int
    end: int
    box: tuple[int, int, int, int]
    confidence: float


@dataclass
class RedactionResult:
    redacted_text: str
    redacted_image: Image.Image
    removed_categories: list[str]
    ocr_confidence: float | None
    review_required: bool = True


def _open_image(data: bytes) -> Image.Image:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image is empty or exceeds the size limit")
    try:
        image = Image.open(BytesIO(data))
        if image.width * image.height > MAX_PIXELS:
            raise ValueError("Image resolution exceeds the safety limit")
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Unsupported or invalid image") from exc


def extract_report(image: Image.Image) -> tuple[str, list[OCRToken]]:
    """OCR in memory; return text and token coordinates for image masking."""
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    raw: dict[str, Any] = pytesseract.image_to_data(
        image, config="--psm 6", output_type=Output.DICT
    )
    parts: list[str] = []
    tokens: list[OCRToken] = []
    pos = 0
    for i, value in enumerate(raw["text"]):
        word = str(value).strip()
        if not word:
            continue
        if parts:
            parts.append(" ")
            pos += 1
        start = pos
        parts.append(word)
        pos += len(word)
        left, top = int(raw["left"][i]), int(raw["top"][i])
        width, height = int(raw["width"][i]), int(raw["height"][i])
        tokens.append(OCRToken(word, start, pos, (left, top, left + width, top + height), float(raw["conf"][i])))
    if not tokens:
        raise ValueError("OCR produced no readable text; do not continue")
    return "".join(parts), tokens


def redact_report(data: bytes, analyzer=None, anonymizer=None) -> RedactionResult:
    """Detect Presidio spans and cover their OCR bounding boxes.

    All detected tokens overlapping an entity span are masked. The resulting
    image must still receive human visual review because OCR/NER may miss PII.
    """
    if analyzer is None:
        from presidio_analyzer import AnalyzerEngine
        analyzer = AnalyzerEngine()
    if anonymizer is None:
        from presidio_anonymizer import AnonymizerEngine
        anonymizer = AnonymizerEngine()
    image = _open_image(data)
    text, tokens = extract_report(image)
    findings = analyzer.analyze(text=text, entities=ENTITIES, language="en")
    spans = [(int(item.start), int(item.end)) for item in findings]
    for start, end in spans:
        if not any(token.start < end and start < token.end for token in tokens):
            raise ValueError("Detected identifier cannot be mapped to image; do not continue")
    redacted = image.copy()
    draw = ImageDraw.Draw(redacted)
    for token in tokens:
        if any(token.start < end and start < token.end for start, end in spans):
            x1, y1, x2, y2 = token.box
            draw.rectangle((max(0, x1 - 3), max(0, y1 - 3), min(image.width, x2 + 3), min(image.height, y2 + 3)), fill="black")
    masked_text = anonymizer.anonymize(text=text, analyzer_results=findings).text
    confidences = [token.confidence for token in tokens if token.confidence >= 0]
    return RedactionResult(
        redacted_text=masked_text,
        redacted_image=redacted,
        removed_categories=sorted({str(item.entity_type) for item in findings}),
        ocr_confidence=round(sum(confidences) / len(confidences), 1) if confidences else None,
    )
