"""OCR a blood-test image in memory. Token boxes stay with the text so redaction can cover those words on the image."""

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError
from pytesseract import Output

TESSERACT_PATH = "/opt/anaconda3/envs/carepath-ocr/bin/tesseract"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 10_000_000


@dataclass(frozen=True)
class OCRToken:
    text: str
    start: int
    end: int
    box: tuple[int, int, int, int]
    confidence: float


def open_image(data: bytes) -> Image.Image:
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
        tokens.append(
            OCRToken(
                word,
                start,
                pos,
                (left, top, left + width, top + height),
                float(raw["conf"][i]),
            )
        )
    if not tokens:
        raise ValueError("OCR produced no readable text; do not continue")
    return "".join(parts), tokens
