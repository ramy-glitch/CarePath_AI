import hashlib
import json

import pytest
from llama_index.core.embeddings import BaseEmbedding

from retrieval.corpus_loader import load_index, load_passages
from retrieval.cutoff import accepts
from retrieval.hybrid_search import build_query, search
from retrieval.keyword_search import search as keyword_search


class OverlapEmbedding(BaseEmbedding):
    """Stable token-overlap vectors so tests never call Ollama."""

    def _vector(self, text: str) -> list[float]:
        tokens = set()
        for raw in text.lower().replace("_", " ").split():
            token = "".join(character for character in raw if character.isalnum())
            if not token:
                continue
            tokens.add(token)
            if token in {"hemoglobin", "hb"}:
                tokens.add("haemoglobin")
            if token == "below":
                tokens.add("low")
            if token == "above":
                tokens.add("high")
            if token == "inside":
                tokens.add("normal")
        vector = [0.0] * 512
        for token in tokens:
            bucket = int(hashlib.sha256(token.encode()).hexdigest(), 16) % 512
            vector[bucket] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._vector(query)


@pytest.fixture(scope="module")
def index():
    return load_index(embed_model=OverlapEmbedding())


def test_corpus_loads_every_panel():
    passages = load_passages()
    assert len(passages) == 99
    assert {passage.panel for passage in passages} == {
        "full_blood_count",
        "urea_and_electrolytes",
        "liver_tests",
        "hba1c",
        "lipids",
        "thyroid",
        "iron_studies",
    }


def test_bm25_ranks_the_alias_and_band(index):
    hits = keyword_search(index, "Hb low")
    assert hits[0].passage_id == "fbc-haemoglobin-low"


def test_alias_query_ranks_the_matching_band(index):
    result = search(index, build_query(analyte="Hb", band="low"), cutoff=0.0)
    assert result.accepted
    assert result.passages[0].id == "fbc-haemoglobin-low"
    assert result.passages[0].simulated_url == "https://example.nhs.uk/explain/haemoglobin"


def test_keyword_text_is_what_bm25_indexes(index):
    haemoglobin = index.passages["fbc-haemoglobin-low"]
    assert "Hb" in haemoglobin.keyword_text()
    assert "carries oxygen" not in haemoglobin.keyword_text()
    assert "carries oxygen" in haemoglobin.embedding_text()


def test_weak_embedding_score_returns_no_citations(index):
    result = search(index, "Hb low", cutoff=0.99)
    assert result.best_embedding_score is not None
    assert result.accepted is False
    assert result.citations() == []
    assert result.passages


def test_empty_query_is_not_accepted(index):
    result = search(index, "   ")
    assert result.accepted is False
    assert result.passages == ()
    assert result.citations() == []


def test_cutoff_compares_embedding_score_only():
    assert accepts(0.35, cutoff=0.35)
    assert accepts(0.34, cutoff=0.35) is False
    assert accepts(None, cutoff=0.0) is False


def test_citation_record_matches_the_passage_schema(index):
    record = search(index, "sodium high", cutoff=0.0).citations()[0]
    assert set(record) == {
        "id",
        "panel",
        "analyte",
        "aliases",
        "band",
        "title",
        "text",
        "simulatedUrl",
    }
    assert record["simulatedUrl"].startswith("https://example.nhs.uk/explain/")


def test_startup_stores_the_index_without_building_a_real_one(monkeypatch):
    import app as app_module
    from fastapi.testclient import TestClient

    monkeypatch.setattr(app_module, "load_index", lambda: {"ready": True})
    with TestClient(app_module.app):
        assert app_module.app.state.retrieval == {"ready": True}
    assert app_module.app.state.retrieval is None


def test_broken_corpus_is_rejected(tmp_path):
    path = tmp_path / "passages.json"
    path.write_text(json.dumps([{"id": "missing"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        load_passages(path)
