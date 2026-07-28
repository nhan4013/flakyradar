"""Hybrid BM25 + vector retrieval over resolved fixes, combined via reciprocal rank fusion.

Pure algorithm — no DB, no network — so it's fully unit-testable offline. Callers
(see services.find_similar_fixes) build Candidate objects from the database.
"""

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

RRF_K = 60


@dataclass
class Candidate:
    id: int
    text: str  # BM25 corpus text (fix description + failure message/stack trace)
    embedding: list[float]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def hybrid_rank(
    query_text: str,
    query_embedding: list[float],
    candidates: list[Candidate],
    k: int = 3,
) -> list[tuple[Candidate, float]]:
    """Rank candidates by BM25 text match fused with vector similarity (RRF)."""
    if not candidates:
        return []

    tokenized_corpus = [c.text.lower().split() for c in candidates]
    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(query_text.lower().split())
    vector_scores = [_cosine(query_embedding, c.embedding) for c in candidates]

    bm25_rank = sorted(range(len(candidates)), key=lambda i: -bm25_scores[i])
    vector_rank = sorted(range(len(candidates)), key=lambda i: -vector_scores[i])

    rrf_score = [0.0] * len(candidates)
    for rank, idx in enumerate(bm25_rank):
        rrf_score[idx] += 1.0 / (RRF_K + rank + 1)
    for rank, idx in enumerate(vector_rank):
        rrf_score[idx] += 1.0 / (RRF_K + rank + 1)

    order = sorted(range(len(candidates)), key=lambda i: -rrf_score[i])[:k]
    return [(candidates[i], rrf_score[i]) for i in order]
