from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from api import anonymise_route

app = FastAPI()
app.include_router(anonymise_route.router)
client = TestClient(app)

TEXT = "Patient Name: <PERSON> Haemoglobin: 13.5 g/dL"


def mock_redaction(_data):
    return SimpleNamespace(redacted_text=TEXT, redacted_image=Image.new("RGB", (2, 2)))


def test_valid_image_returns_only_contract_fields(monkeypatch):
    calls = []
    def redact(data):
        calls.append(data)
        return mock_redaction(data)
    monkeypatch.setattr(anonymise_route, "redact_report", redact)
    response = client.post("/api/v1/anonymise", content=b"synthetic", headers={"content-type": "image/png"})
    assert response.status_code == 200
    assert set(response.json()) == {"results", "reviewRequired"}
    assert response.json()["reviewRequired"] is True
    assert response.json()["results"][0]["testName"] == "Haemoglobin"
    assert response.json()["results"][0]["value"] == 13.5
    assert response.json()["results"][0]["referenceRange"] is None
    assert calls == [b"synthetic"]
    assert "<PERSON>" not in response.text


def test_invalid_image_fails_without_patient_text(monkeypatch):
    def fail(_data):
        raise ValueError("John Smith john.smith@example.com")
    monkeypatch.setattr(anonymise_route, "redact_report", fail)
    response = client.post("/api/v1/anonymise", content=b"invalid", headers={"content-type": "image/png"})
    assert response.status_code == 422
    assert "John Smith" not in response.text
    assert "example.com" not in response.text


def test_multipart_rejected_before_pipeline(monkeypatch):
    monkeypatch.setattr(anonymise_route, "redact_report", lambda _: (_ for _ in ()).throw(AssertionError("called")))
    response = client.post("/api/v1/anonymise", files={"file": ("test.png", b"data", "image/png")})
    assert response.status_code == 415


def test_oversized_rejected_before_pipeline(monkeypatch):
    monkeypatch.setattr(anonymise_route, "MAX_IMAGE_BYTES", 3)
    monkeypatch.setattr(anonymise_route, "redact_report", lambda _: (_ for _ in ()).throw(AssertionError("called")))
    response = client.post("/api/v1/anonymise", content=b"abcd", headers={"content-type": "image/png"})
    assert response.status_code == 413


def test_empty_rejected():
    response = client.post("/api/v1/anonymise", content=b"", headers={"content-type": "image/png"})
    assert response.status_code == 422


def test_malformed_lab_unit_fails_closed(monkeypatch):
    def bad(_data):
        return SimpleNamespace(redacted_text="Patient: <PERSON> Haemoglobin: 135 gid", redacted_image=Image.new("RGB", (2, 2)))
    monkeypatch.setattr(anonymise_route, "redact_report", bad)
    response = client.post("/api/v1/anonymise", content=b"synthetic", headers={"content-type": "image/png"})
    assert response.status_code == 422
    assert "135" not in response.text
