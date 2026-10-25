"""Process settings. Patient data is not configured or stored here."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = PROJECT_ROOT / "corpus" / "passages.json"
FIXTURE_PACK = PROJECT_ROOT / "tests" / "fixtures" / "carepath_data" / "scenarios.json"

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "qwen3:1.7b"
CHAT_TIMEOUT_SECONDS = 60
COVERAGE_SCHEMA_PATH = PROJECT_ROOT / "shared" / "contracts" / "coverage.schema.json"

KEYWORD_TOP_K = 8
EMBEDDING_TOP_K = 8
HYBRID_TOP_K = 3
RRF_K = 60

# Starting gate. evaluation/tune_cutoff.py replaces this after an offline run.
# The value is a cosine similarity from the embedding retriever, not a fused rank.
EMBEDDING_SCORE_CUTOFF = 0.35
