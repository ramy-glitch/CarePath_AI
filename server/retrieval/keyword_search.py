"""BM25 over aliases, the analyte name, the title, and the band."""

from retrieval.corpus_loader import RetrievalIndex, ScoredHit


def search(index: RetrievalIndex, query: str) -> list[ScoredHit]:
    matches = index.keyword_retriever.retrieve(query)
    hits = [
        ScoredHit(passage_id=match.node.node_id, score=float(match.score))
        for match in matches
        if match.score is not None and match.score > 0 and match.node.node_id in index.passages
    ]
    hits.sort(key=lambda hit: hit.score, reverse=True)
    return hits
