import json

from fastapi.testclient import TestClient

import app as app_module


def _client(monkeypatch):
    monkeypatch.setattr(app_module, "load_index", lambda: {"ready": True})
    return TestClient(app_module.app)


def test_catalog_lists_the_pack_without_identifiers(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/fixtures")
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["fixtures"]]
    assert "S02" in ids
    assert "F03" in ids
    text = json.dumps(body)
    assert "Ama" not in text
    assert "Mensah" not in text
    assert "999" not in text
    s02 = next(item for item in body["fixtures"] if item["id"] == "S02")
    assert "Neutrophils 1.6" in s02["label"]
    assert "Duffy-null" in s02["detail"]


def test_s02_returns_printed_results_and_the_declared_context(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/fixtures/S02")
    assert response.status_code == 200
    body = response.json()
    neutrophils = next(row for row in body["lab"]["results"] if row["testName"] == "Neutrophils")
    assert neutrophils["value"] == 1.6
    assert neutrophils["flag"] == "low"
    assert neutrophils["referenceRange"] == {"low": 1.9, "high": 8.0}
    assert body["ageBand"] == "30-39"
    assert body["context"]["duffy"] == "yes"
    text = json.dumps(body)
    assert "Ama" not in text
    assert "NHS" not in text
    assert "999" not in text


def test_blurry_fixture_is_refused(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/fixtures/F03")
    assert response.status_code == 422
    assert "Ama" not in response.text
    assert "Grant" not in response.text


def test_unknown_fixture_is_not_found(monkeypatch):
    with _client(monkeypatch) as client:
        response = client.get("/fixtures/S99")
    assert response.status_code == 404
