"""Root-cause classification + fix suggestions.

Default provider is Anthropic (Claude), via structured outputs. Set
LLM_PROVIDER=openai-compatible to point this at any OpenAI-compatible chat
completions endpoint instead (OpenAI, Azure OpenAI, OpenRouter, Groq,
Together, self-hosted Ollama/vLLM, ...) via LLM_BASE_URL + LLM_API_KEY +
LLM_MODEL — so any provider/model works, not just Claude.
"""

import json
import os

import anthropic

PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
OPENAI_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

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

SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestion": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["suggestion", "confidence"],
    "additionalProperties": False,
}

_anthropic_client: anthropic.Anthropic | None = None
_openai_client = None


def has_credentials() -> bool:
    if PROVIDER == "openai-compatible":
        return bool(os.environ.get("LLM_API_KEY"))
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic()
    return _anthropic_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai

        _openai_client = openai.OpenAI(
            base_url=os.environ.get("LLM_BASE_URL") or None,
            api_key=os.environ.get("LLM_API_KEY"),
        )
    return _openai_client


def _extract_json(text: str) -> dict:
    """Best-effort JSON extraction — not every OpenAI-compatible model honors a
    "JSON only" instruction strictly, so strip a markdown code fence if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.removesuffix("```").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def _chat_json(prompt: str, fallback: dict) -> dict:
    """Send prompt to the OpenAI-compatible endpoint, asking for JSON-only output."""
    response = _get_openai_client().chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Respond with only a single JSON object matching the "
                "requested fields. No prose, no markdown fences.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    text = response.choices[0].message.content or ""
    try:
        return _extract_json(text)
    except (json.JSONDecodeError, IndexError):
        return fallback


def classify_root_cause(test_id: str, stack_trace: str, message: str) -> dict:
    prompt = (
        f"Test: {test_id}\n"
        f"Failure message: {message}\n"
        f"Stack trace:\n{stack_trace}\n\n"
        "This test is flaky (it flips between pass and fail on the same commit). "
        "Classify the most likely root cause. Return JSON with keys: "
        f"category (one of {CATEGORIES}), confidence (0-1 number), explanation "
        "(string), suggested_fix (string)."
    )
    fallback = {
        "category": "unknown",
        "confidence": 0.0,
        "explanation": "Model did not return valid JSON.",
        "suggested_fix": "",
    }
    if PROVIDER == "openai-compatible":
        return _chat_json(prompt, fallback)

    response = _get_anthropic_client().messages.create(
        model=MODEL,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return {**fallback, "explanation": "Classification declined by safety policy."}
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


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
        "by commit if it applies. Return JSON with keys: suggestion (string), "
        "confidence (0-1 number)."
    )
    fallback = {"suggestion": "", "confidence": 0.0}
    if PROVIDER == "openai-compatible":
        return _chat_json(prompt, fallback)

    response = _get_anthropic_client().messages.create(
        model=MODEL,
        max_tokens=512,
        output_config={"format": {"type": "json_schema", "schema": SUGGEST_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        return fallback
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
