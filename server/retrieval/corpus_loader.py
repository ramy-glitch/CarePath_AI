"""Load the synthetic corpus and build the in-memory keyword and embedding indexes.

The indexes contain only corpus/passages.json. A lab result is a query and is never inserted.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from llama_index.core.schema import TextNode

from config import settings

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("id", "panel", "analyte", "aliases", "band", "title", "text", "simulatedUrl")
BANDS = frozenset({"low", "normal", "high"})


@dataclass(frozen=True)
class Passage:
    id: str
    panel: str
    analyte: str
    aliases: tuple[str, ...]
    band: str
    title: str
    text: str
    simulated_url: str

    def keyword_text(self) -> str:
        """Aliases, title, and band. BM25 does not index the explanation body."""
        alias_text = " ".join(self.aliases)
        analyte_text = self.analyte.replace("_", " ")
        return f"{alias_text} {analyte_text} {self.title} {self.band}"

    def embedding_text(self) -> str:
        """Title and explanation. Embeddings do not index the alias list."""
        return f"{self.title}\n{self.text}"

    def as_record(self) -> dict:
        return {
            "id": self.id,
            "panel": self.panel,
            "analyte": self.analyte,
            "aliases": list(self.aliases),
            "band": self.band,
            "title": self.title,
            "text": self.text,
            "simulatedUrl": self.simulated_url,
        }


@dataclass(frozen=True)
class ScoredHit:
    passage_id: str
    score: float


@dataclass
class RetrievalIndex:
    passages: dict[str, Passage]
    keyword_retriever: object
    vector_retriever: object


def load_passages(path: Path | None = None) -> list[Passage]:
    corpus_path = path or settings.CORPUS_PATH
    raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Corpus at {corpus_path} must be a non-empty list")
    passages = [_passage(item) for item in raw]
    ids = [passage.id for passage in passages]
    if len(ids) != len(set(ids)):
        raise ValueError("Corpus contains duplicate passage ids")
    return passages


def load_index(path: Path | None = None, embed_model=None) -> RetrievalIndex:
    """Build both indexes. Uses the local Ollama embedding model when embed_model is omitted."""
    passages = load_passages(path)
    if embed_model is None:
        from llama_index.embeddings.ollama import OllamaEmbedding

        embed_model = OllamaEmbedding(
            model_name=settings.EMBEDDING_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
    index = build_index(passages, embed_model)
    logger.info("Indexed %s synthetic passages", len(passages))
    return index


def build_index(passages: list[Passage], embed_model) -> RetrievalIndex:
    from llama_index.core import VectorStoreIndex
    from llama_index.retrievers.bm25 import BM25Retriever

    by_id = {passage.id: passage for passage in passages}
    keyword_nodes = [_node(passage, passage.keyword_text()) for passage in passages]
    embedding_nodes = [_node(passage, passage.embedding_text()) for passage in passages]
    top_k = min(settings.KEYWORD_TOP_K, len(passages))
    embedding_k = min(settings.EMBEDDING_TOP_K, len(passages))

    keyword_retriever = BM25Retriever.from_defaults(
        nodes=keyword_nodes,
        similarity_top_k=top_k,
        skip_stemming=False,
    )
    vector_index = VectorStoreIndex(embedding_nodes, embed_model=embed_model, show_progress=False)
    vector_retriever = vector_index.as_retriever(similarity_top_k=embedding_k)
    return RetrievalIndex(
        passages=by_id,
        keyword_retriever=keyword_retriever,
        vector_retriever=vector_retriever,
    )


def _passage(item: object) -> Passage:
    if not isinstance(item, dict):
        raise ValueError("Each corpus entry must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in item]
    if missing:
        raise ValueError(f"Corpus entry missing {', '.join(missing)}")
    band = str(item["band"])
    if band not in BANDS:
        raise ValueError(f"Passage {item.get('id')} has band {band!r}")
    aliases = tuple(str(alias).strip() for alias in item["aliases"] if str(alias).strip())
    if not aliases:
        raise ValueError(f"Passage {item.get('id')} has no aliases")
    return Passage(
        id=str(item["id"]),
        panel=str(item["panel"]),
        analyte=str(item["analyte"]),
        aliases=aliases,
        band=band,
        title=str(item["title"]),
        text=str(item["text"]),
        simulated_url=str(item["simulatedUrl"]),
    )


def _node(passage: Passage, text: str) -> TextNode:
    metadata = {
        "panel": passage.panel,
        "analyte": passage.analyte,
        "band": passage.band,
        "simulated_url": passage.simulated_url,
    }
    return TextNode(
        id_=passage.id,
        text=text,
        metadata=metadata,
        excluded_embed_metadata_keys=list(metadata.keys()),
        excluded_llm_metadata_keys=list(metadata.keys()),
    )
