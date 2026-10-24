"""Cover OCR boxes that overlap a detected identifier. The image is a copy; the upload is left unchanged."""

from PIL import Image, ImageDraw

from .ocr import OCRToken


def spans_map_to_tokens(tokens: list[OCRToken], spans: list[tuple[int, int]]) -> None:
    for start, end in spans:
        if not any(token.start < end and start < token.end for token in tokens):
            raise ValueError("Detected identifier cannot be mapped to image; do not continue")


def mask_image(image: Image.Image, tokens: list[OCRToken], spans: list[tuple[int, int]]) -> Image.Image:
    redacted = image.copy()
    draw = ImageDraw.Draw(redacted)
    for token in tokens:
        if any(token.start < end and start < token.end for start, end in spans):
            x1, y1, x2, y2 = token.box
            draw.rectangle(
                (
                    max(0, x1 - 3),
                    max(0, y1 - 3),
                    min(image.width, x2 + 3),
                    min(image.height, y2 + 3),
                ),
                fill="black",
            )
    return redacted
