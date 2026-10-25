"""Accept a retrieval only when the best embedding similarity clears the cutoff."""

from config import settings


def accepts(embedding_score: float | None, cutoff: float | None = None) -> bool:
    limit = settings.EMBEDDING_SCORE_CUTOFF if cutoff is None else cutoff
    return embedding_score is not None and embedding_score >= limit
