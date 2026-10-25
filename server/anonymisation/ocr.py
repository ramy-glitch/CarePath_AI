"""OCR a blood-test image in memory. Token boxes stay with the text so redaction can cover those words on the image."""

import shutil
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError
from pytesseract import Output, TesseractNotFoundError

# The first existing binary wins. The Linux path is the project environment;
# the Windows paths are the usual Tesseract installer locations.
TESSERACT_CANDIDATES = (
    "/opt/anaconda3/envs/carepath-ocr/bin/tesseract",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 10_000_000


def tesseract_command() -> str:
    for candidate in TESSERACT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("tesseract")
    if found:
        return found
    raise OSError("Tesseract is not installed")


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
    pytesseract.pytesseract.tesseract_cmd = tesseract_command()
    try:
        raw: dict[str, Any] = pytesseract.image_to_data(
            image, config="--psm 6", output_type=Output.DICT
        )
    except TesseractNotFoundError as exc:
        raise OSError("Tesseract is not installed") from exc
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
