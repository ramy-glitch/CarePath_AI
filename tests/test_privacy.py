from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from carepath import privacy


class FakeAnalyzer:
    def analyze(self, *, text, entities, language):
        assert "John Smith" in text
        assert "Haemoglobin" in text
        start = text.index("John Smith")
        return [SimpleNamespace(start=start, end=start + len("John Smith"), entity_type="PERSON")]


class FakeAnonymizer:
    def anonymize(self, *, text, analyzer_results):
        result = text
        for item in reversed(analyzer_results):
            result = result[:item.start] + "<PERSON>" + result[item.end:]
        return SimpleNamespace(text=result)


def test_masks_name_preserves_test_value(monkeypatch):
    image = Image.new("RGB", (420, 120), "white")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    names = ["John", "Smith", "Haemoglobin", "13.5", "g/dL"]
    monkeypatch.setattr(privacy.pytesseract, "image_to_data", lambda *args, **kwargs: {
        "text": names,
        "left": [10, 70, 10, 160, 230],
        "top": [10, 10, 60, 60, 60],
        "width": [50, 50, 130, 50, 40],
        "height": [20] * 5,
        "conf": [97] * 5,
    })
    output = privacy.redact_report(image_bytes.getvalue(), FakeAnalyzer(), FakeAnonymizer())
    assert output.removed_categories == ["PERSON"]
    assert "John" not in output.redacted_text
    assert "Haemoglobin 13.5 g/dL" in output.redacted_text
    assert output.redacted_image.getpixel((15, 15)) == (0, 0, 0)
    assert output.redacted_image.getpixel((170, 65)) == (255, 255, 255)
    assert output.review_required is True


def test_invalid_image_fails_closed():
    try:
        privacy.redact_report(b"not an image", FakeAnalyzer(), FakeAnonymizer())
    except ValueError as exc:
        assert "invalid image" in str(exc)
    else:
        raise AssertionError("Invalid image was accepted")
