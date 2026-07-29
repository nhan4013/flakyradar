"""Parser for `go test -json` output (newline-delimited JSON test events).

No extra tooling needed on the Go side — `go test -json ./...` is stdlib.
"""

import json

from core.junit import ParsedResult

TERMINAL_ACTIONS = {"pass": "passed", "fail": "failed", "skip": "skipped"}


def parse_go_test_json(text: str) -> list[ParsedResult]:
    output_by_test: dict[str, list[str]] = {}
    results: list[ParsedResult] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        test_name = event.get("Test")
        if not test_name:
            continue  # package-level event (no individual test), skip
        key = f"{event.get('Package', '')}::{test_name}"
        action = event.get("Action")
        if action == "output":
            output_by_test.setdefault(key, []).append(event.get("Output", ""))
        elif action in TERMINAL_ACTIONS:
            output_lines = output_by_test.pop(key, [])
            outcome = TERMINAL_ACTIONS[action]
            results.append(
                ParsedResult(
                    test_id=key,
                    outcome=outcome,
                    duration=float(event.get("Elapsed", 0.0)),
                    message=_first_failure_line(output_lines) if outcome == "failed" else "",
                    stack_trace="".join(output_lines),
                )
            )
    return results


def _first_failure_line(lines: list[str]) -> str:
    for raw in lines:
        stripped = raw.strip()
        if stripped and not stripped.startswith(("=== RUN", "--- ")):
            return stripped
    return ""
