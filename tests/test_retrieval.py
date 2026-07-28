from core.retrieval import Candidate, hybrid_rank


def _candidates():
    return [
        Candidate(id=1, text="fixed by adding a lock around charge card", embedding=[1.0, 0.0]),
        Candidate(id=2, text="fixed by raising the timeout threshold", embedding=[0.0, 1.0]),
    ]


def test_hybrid_rank_prefers_vector_and_text_match():
    ranked = hybrid_rank("lock around charge card race", [0.9, 0.1], _candidates(), k=1)
    assert ranked[0][0].id == 1


def test_hybrid_rank_empty_candidates():
    assert hybrid_rank("anything", [1.0, 0.0], [], k=3) == []


def test_hybrid_rank_respects_k():
    ranked = hybrid_rank("timeout threshold", [0.0, 1.0], _candidates(), k=1)
    assert len(ranked) == 1
