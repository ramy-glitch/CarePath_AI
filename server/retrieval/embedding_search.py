"""Vector search over passage title and explanation text.

Scores are cosine similarities from the embedding model. The hybrid cutoff reads these
scores and does not read the fused rank.
"""

from retrieval.corpus_loader import RetrievalIndex, ScoredHit


def search(index: RetrievalIndex, query: str) -> list[ScoredHit]:
    matches = index.vector_retriever.retrieve(query)
    hits = [
        ScoredHit(passage_id=match.node.node_id, score=float(match.score))
        for match in matches
        if match.score is not None and match.score > 0 and match.node.node_id in index.passages
    ]
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits
