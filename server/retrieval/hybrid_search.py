"""Fuse keyword and embedding ranks, then apply the embedding-score gate.

Reciprocal rank fusion orders the passages. It is not the acceptance score.
"""

from dataclasses import dataclass

from config import settings
from retrieval.corpus_loader import Passage, RetrievalIndex, ScoredHit
from retrieval.cutoff import accepts
from retrieval.embedding_search import search as embedding_search
from retrieval.keyword_search import search as keyword_search


@dataclass(frozen=True)
class RetrievalResult:
    passages: tuple[Passage, ...]
    best_embedding_score: float | None
    accepted: bool

    def citations(self) -> list[dict]:
        """Passage records safe to show. Empty when the embedding score is below the cutoff."""
        if not self.accepted:
            return []
        return [passage.as_record() for passage in self.passages]


def build_query(*, analyte: str, band: str, question: str = "") -> str:
    parts = [analyte.strip(), band.strip(), question.strip()]
    return " ".join(part for part in parts if part)


def search(
    index: RetrievalIndex,
    query: str,
    *,
    top_k: int | None = None,
    cutoff: float | None = None,
) -> RetrievalResult:
    text = query.strip()
    if not text:
        return RetrievalResult(passages=(), best_embedding_score=None, accepted=False)

    keyword_hits = keyword_search(index, text)
    embedding_hits = embedding_search(index, text)
    fused_ids = _reciprocal_rank_fusion(keyword_hits, embedding_hits)
    limit = settings.HYBRID_TOP_K if top_k is None else top_k
    passages = tuple(index.passages[passage_id] for passage_id in fused_ids[:limit] if passage_id in index.passages)
    best_embedding_score = embedding_hits[0].score if embedding_hits else None
    return RetrievalResult(
        passages=passages,
        best_embedding_score=best_embedding_score,
        accepted=accepts(best_embedding_score, cutoff),
    )


def _reciprocal_rank_fusion(*ranked_lists: list[ScoredHit]) -> list[str]:
    fused: dict[str, float] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            fused[hit.passage_id] = fused.get(hit.passage_id, 0.0) + 1.0 / (settings.RRF_K + rank)
    return sorted(fused, key=fused.__getitem__, reverse=True)
