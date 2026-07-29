"""Parser for Jest's native `--json` output (no jest-junit reporter needed).

Users who already emit JUnit XML from Jest (via jest-junit) can use the
existing junit.parse_junit_xml instead — same schema as pytest/JUnit Java.
"""

import json

from core.junit import ParsedResult

STATUS_MAP = {
    "passed": "passed",
    "failed": "failed",
    "pending": "skipped",
    "skipped": "skipped",
    "todo": "skipped",
}


def parse_jest_json(text: str) -> list[ParsedResult]:
    data = json.loads(text)
    results: list[ParsedResult] = []
    for file_result in data.get("testResults", []):
        file_name = file_result.get("name", "")
        for test in file_result.get("testResults", []):
            outcome = STATUS_MAP.get(test.get("status", ""), "skipped")
            failure_messages = test.get("failureMessages") or []
            trace = failure_messages[0] if failure_messages else ""
            message = trace.splitlines()[0] if trace else ""
            full_name = test.get("fullName") or test.get("title", "")
            results.append(
                ParsedResult(
                    test_id=f"{file_name}::{full_name}",
                    outcome=outcome,
                    duration=(test.get("duration") or 0) / 1000.0,
                    message=message,
                    stack_trace=trace,
                )
            )
    return results
