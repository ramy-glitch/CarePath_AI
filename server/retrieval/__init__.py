"""In-memory hybrid retrieval over the synthetic corpus."""

from retrieval.corpus_loader import Passage, load_index
from retrieval.hybrid_search import RetrievalResult, build_query, search

__all__ = ["Passage", "RetrievalResult", "build_query", "load_index", "search"]
