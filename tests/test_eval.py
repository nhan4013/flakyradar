from core import eval as eval_mod
from core.retrieval import Candidate


def test_macro_f1_perfect_prediction():
    assert eval_mod.macro_f1(["a", "b"], ["a", "b"], ["a", "b"]) == 1.0


def test_macro_f1_all_wrong():
    assert eval_mod.macro_f1(["a", "a"], ["b", "b"], ["a", "b"]) == 0.0


def test_evaluate_classifier_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert eval_mod.evaluate_classifier([("t", "trace", "msg", "unknown")]) is None


def test_evaluate_classifier_with_mocked_llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        "core.eval.llm.classify_root_cause",
        lambda test_id, stack_trace, message: {"category": "timing_flakiness"},
    )
    samples = [("t1", "trace", "msg", "timing_flakiness"), ("t2", "trace", "msg", "network")]
    result = eval_mod.evaluate_classifier(samples)
    assert result["n"] == 2
    assert result["accuracy"] == 0.5


def test_precision_at_k_finds_the_right_match():
    # 3+ candidates avoid BM25's degenerate zero-IDF case at N=2 (a term in exactly
    # half the tiny corpus gets idf=0), so text + vector signals agree cleanly.
    candidates = [
        Candidate(id=1, text="lock race condition fix", embedding=[1.0, 0.0, 0.0]),
        Candidate(id=2, text="timeout threshold fix", embedding=[0.0, 1.0, 0.0]),
        Candidate(id=3, text="mock the http client fix", embedding=[0.0, 0.0, 1.0]),
    ]
    cases = [
        ("lock race condition", [0.9, 0.1, 0.0], candidates, {1}),
        ("timeout threshold", [0.1, 0.9, 0.0], candidates, {2}),
        ("mock http client", [0.0, 0.1, 0.9], candidates, {3}),
    ]
    result = eval_mod.precision_at_k(cases, k=1)
    assert result["precision_at_k"] == 1.0
    assert result["n"] == 3


def test_precision_at_k_no_cases():
    result = eval_mod.precision_at_k([], k=3)
    assert result["precision_at_k"] == 0.0
