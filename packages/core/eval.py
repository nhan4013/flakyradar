"""Eval harness: classifier accuracy/F1 (needs ANTHROPIC_API_KEY) and retrieval
precision@k (pure, runs offline). See scripts/run_eval.py for the CLI report."""

import os

from core import llm, retrieval


def macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    scores = []
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        score = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        scores.append(score)
    return sum(scores) / len(scores) if scores else 0.0


def evaluate_classifier(samples: list[tuple[str, str, str, str]]) -> dict | None:
    """samples: (test_id, stack_trace, message, true_category). None if no API key."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    y_true, y_pred = [], []
    for test_id, stack_trace, message, label in samples:
        result = llm.classify_root_cause(test_id, stack_trace, message)
        y_true.append(label)
        y_pred.append(result["category"])
    accuracy = sum(1 for t, p in zip(y_true, y_pred, strict=True) if t == p) / len(y_true)
    f1 = macro_f1(y_true, y_pred, llm.CATEGORIES)
    return {"accuracy": accuracy, "macro_f1": f1, "n": len(y_true)}


def precision_at_k(
    cases: list[tuple[str, list[float], list[retrieval.Candidate], set[int]]], k: int = 3
) -> dict:
    """cases: (query_text, query_embedding, candidates, relevant_candidate_ids)."""
    if not cases:
        return {"precision_at_k": 0.0, "k": k, "n": 0}
    scores = []
    for query_text, query_embedding, candidates, relevant_ids in cases:
        ranked = retrieval.hybrid_rank(query_text, query_embedding, candidates, k=k)
        hits = sum(1 for c, _ in ranked if c.id in relevant_ids)
        scores.append(hits / k)
    return {"precision_at_k": sum(scores) / len(scores), "k": k, "n": len(cases)}
