"""JUnit XML parser. Uses defusedxml — input crosses a trust boundary."""

from dataclasses import dataclass

from defusedxml import ElementTree


@dataclass
class ParsedResult:
    test_id: str
    outcome: str  # passed | failed | error | skipped
    duration: float
    message: str
    stack_trace: str


def parse_junit_xml(xml_text: str) -> list[ParsedResult]:
    root = ElementTree.fromstring(xml_text)
    suites = root.iter("testsuite") if root.tag == "testsuites" else [root]
    results: list[ParsedResult] = []
    for suite in suites:
        for case in suite.iter("testcase"):
            classname = case.get("classname", "")
            name = case.get("name", "")
            test_id = f"{classname}::{name}" if classname else name
            try:
                duration = float(case.get("time") or 0.0)
            except ValueError:
                duration = 0.0
            outcome, message, trace = "passed", "", ""
            for child in case:
                tag = child.tag
                if tag in ("failure", "error", "skipped"):
                    outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
                    message = child.get("message") or ""
                    trace = (child.text or "").strip()
                    break
            results.append(
                ParsedResult(
                    test_id=test_id,
                    outcome=outcome,
                    duration=duration,
                    message=message,
                    stack_trace=trace,
                )
            )
    return results
