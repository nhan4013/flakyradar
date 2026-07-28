"""Root-cause classification for a failure cluster, via Claude structured outputs."""

import json
import os

import anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

CATEGORIES = [
    "race_condition",
    "test_order_dependency",
    "timing_flakiness",
    "network",
    "resource_leak",
    "unknown",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "confidence": {"type": "number"},
        "explanation": {"type": "string"},
        "suggested_fix": {"type": "string"},
    },
    "required": ["category", "confidence", "explanation", "suggested_fix"],
    "additionalProperties": False,
}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def classify_root_cause(test_id: str, stack_trace: str, message: str) -> dict:
    prompt = (
        f"Test: {test_id}\n"
        f"Failure message: {message}\n"
        f"Stack trace:\n{stack_trace}\n\n"
        "This test is flaky (it flips between pass and fail on the same commit). "
        "Classify the most likely root cause."
    )
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return {
            "category": "unknown",
            "confidence": 0.0,
            "explanation": "Classification declined by safety policy.",
            "suggested_fix": "",
        }
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestion": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["suggestion", "confidence"],
    "additionalProperties": False,
}


def suggest_fix(
    test_id: str, stack_trace: str, message: str, similar_fixes: list[dict]
) -> dict:
    """Suggest a fix grounded in past fixes for similar flaky tests (RAG)."""
    if not similar_fixes:
        return {"suggestion": "", "confidence": 0.0}
    evidence_text = "\n".join(
        f"- Similar failure fixed via commit {f['commit_sha']}: {f['description']}"
        for f in similar_fixes
    )
    prompt = (
        f"Test: {test_id}\n"
        f"Failure message: {message}\n"
        f"Stack trace:\n{stack_trace}\n\n"
        f"Past similar flaky-test fixes on this project:\n{evidence_text}\n\n"
        "Suggest a concrete fix for this test, referencing the most relevant past fix "
        "by commit if it applies."
    )
    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=512,
        output_config={"format": {"type": "json_schema", "schema": SUGGEST_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return {"suggestion": "", "confidence": 0.0}
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
