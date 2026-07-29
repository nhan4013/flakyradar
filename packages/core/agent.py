"""Sandboxed ReAct diagnostic agent (Phase 3).

Manual tool-use loop (not an SDK tool runner) so step budget, token budget,
and per-call audit logging are fully explicit and deterministic — see
plan.md Phase 3: "giới hạn số step + chi phí token mỗi lần chẩn đoán".

Default provider is Anthropic (Claude). Set LLM_PROVIDER=openai-compatible to
run the same loop against any OpenAI-compatible chat completions endpoint
(OpenAI, Azure OpenAI, OpenRouter, Groq, self-hosted Ollama/vLLM, ...) via
LLM_BASE_URL + LLM_API_KEY + LLM_MODEL — same env vars as packages/core/llm.py.
"""

import json
import os
from pathlib import Path

import anthropic

from core import agent_tools, llm

PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")
OPENAI_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "8"))
MAX_TOKENS_BUDGET = int(os.environ.get("AGENT_MAX_TOKENS", "50000"))

SYSTEM_PROMPT = (
    "You are a test-flakiness diagnostic agent. You have tools to investigate a "
    "flaky test in a real, sandboxed checkout of its repository: rerun it, run it "
    "in random order, run it in isolation, read source files, and inspect shared "
    "fixtures. Use them to figure out why the test is flaky, then call "
    "report_diagnosis exactly once to finish. Ground your diagnosis in what the "
    "tools actually showed you — don't guess."
)

TOOLS = [
    {
        "name": "rerun_test",
        "description": "Re-run the failing test N times (max 20) in the sandbox and report the pass/fail split.",
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "number of reruns, 1-20"}},
            "required": ["n"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_with_random_order",
        "description": "Run the test's module with pytest-randomly to check for order-dependency.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_in_isolation",
        "description": "Run only this test, isolated from the rest of the suite.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "read_test_source",
        "description": "Read a source file from the repo (path relative to repo root) to inspect the test or its fixtures.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_shared_fixtures",
        "description": "Read conftest.py files on the path to this test to find shared/module-scoped fixtures.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "report_diagnosis",
        "description": "Finish the investigation and report the diagnosis. Call this exactly once when done.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": llm.CATEGORIES},
                "confidence": {"type": "number"},
                "explanation": {"type": "string"},
                "reproduced": {"type": "boolean"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["category", "confidence", "explanation", "reproduced", "evidence"],
            "additionalProperties": False,
        },
    },
]

_client: anthropic.Anthropic | None = None
_openai_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai

        _openai_client = openai.OpenAI(
            base_url=os.environ.get("LLM_BASE_URL") or None,
            api_key=os.environ.get("LLM_API_KEY"),
        )
    return _openai_client


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def _budget_exceeded_report(reason: str) -> dict:
    return {
        "category": "unknown",
        "confidence": 0.0,
        "explanation": reason,
        "reproduced": False,
        "evidence": [],
    }


def run_diagnostic_agent(
    image: str,
    workdir: Path,
    repo_dir: Path,
    test_id: str,
    stack_trace: str,
    message: str,
) -> tuple[dict, list[dict]]:
    """Runs the ReAct loop. Returns (report, steps) — steps is the full audit log."""
    if PROVIDER == "openai-compatible":
        return _run_openai_loop(image, workdir, repo_dir, test_id, stack_trace, message)
    return _run_anthropic_loop(image, workdir, repo_dir, test_id, stack_trace, message)


def _run_anthropic_loop(
    image: str, workdir: Path, repo_dir: Path, test_id: str, stack_trace: str, message: str
) -> tuple[dict, list[dict]]:
    messages = [
        {
            "role": "user",
            "content": (
                f"Test: {test_id}\nFailure message: {message}\nStack trace:\n{stack_trace}\n\n"
                "Investigate and diagnose why this test is flaky."
            ),
        }
    ]
    steps: list[dict] = []
    client = _get_client()
    tokens_spent = 0

    for step_index in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        tokens_spent += response.usage.input_tokens + response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break

        tool_results = []
        for call in tool_uses:
            if call.name == "report_diagnosis":
                steps.append(
                    {"step": step_index, "tool": call.name, "input": call.input, "output": "finished"}
                )
                return call.input, steps

            output = _execute_tool(call.name, call.input, image, workdir, repo_dir, test_id)
            steps.append({"step": step_index, "tool": call.name, "input": call.input, "output": output})
            tool_results.append({"type": "tool_result", "tool_use_id": call.id, "content": output})
        messages.append({"role": "user", "content": tool_results})

        if tokens_spent >= MAX_TOKENS_BUDGET:
            return _budget_exceeded_report(
                f"Stopped: token budget ({MAX_TOKENS_BUDGET}) exhausted after {step_index + 1} steps."
            ), steps

    return _budget_exceeded_report(
        f"Agent did not conclude within the {MAX_STEPS}-step budget."
    ), steps


def _run_openai_loop(
    image: str, workdir: Path, repo_dir: Path, test_id: str, stack_trace: str, message: str
) -> tuple[dict, list[dict]]:
    openai_tools = _to_openai_tools(TOOLS)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Test: {test_id}\nFailure message: {message}\nStack trace:\n{stack_trace}\n\n"
                "Investigate and diagnose why this test is flaky."
            ),
        },
    ]
    steps: list[dict] = []
    client = _get_openai_client()
    tokens_spent = 0

    for step_index in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=messages, tools=openai_tools
        )
        usage = response.usage
        if usage is not None:
            tokens_spent += (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)

        choice = response.choices[0].message
        messages.append(choice.model_dump(exclude_none=True))

        tool_calls = choice.tool_calls or []
        if not tool_calls:
            break

        for call in tool_calls:
            name = call.function.name
            try:
                tool_input = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_input = {}

            if name == "report_diagnosis":
                steps.append({"step": step_index, "tool": name, "input": tool_input, "output": "finished"})
                return tool_input, steps

            output = _execute_tool(name, tool_input, image, workdir, repo_dir, test_id)
            steps.append({"step": step_index, "tool": name, "input": tool_input, "output": output})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

        if tokens_spent >= MAX_TOKENS_BUDGET:
            return _budget_exceeded_report(
                f"Stopped: token budget ({MAX_TOKENS_BUDGET}) exhausted after {step_index + 1} steps."
            ), steps

    return _budget_exceeded_report(
        f"Agent did not conclude within the {MAX_STEPS}-step budget."
    ), steps


def _execute_tool(
    name: str, tool_input: dict, image: str, workdir: Path, repo_dir: Path, test_id: str
) -> str:
    try:
        if name == "rerun_test":
            return agent_tools.rerun_test(image, workdir, test_id, n=tool_input.get("n", 10))
        if name == "run_with_random_order":
            return agent_tools.run_with_random_order(image, workdir, test_id)
        if name == "run_in_isolation":
            return agent_tools.run_in_isolation(image, workdir, test_id)
        if name == "read_test_source":
            return agent_tools.read_test_source(repo_dir, tool_input.get("path", ""))
        if name == "check_shared_fixtures":
            return agent_tools.check_shared_fixtures(repo_dir, test_id)
        return f"error: unknown tool {name}"
    except Exception as exc:  # noqa: BLE001 — sandbox/tool errors surface to the agent, not a crash
        return f"error: {exc}"
