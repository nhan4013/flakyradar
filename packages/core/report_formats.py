"""Registry mapping a report format name to its parser. Every parser returns
list[junit.ParsedResult], so the rest of the ingest pipeline is format-agnostic.
"""

from core.gotest_format import parse_go_test_json
from core.jest_format import parse_jest_json
from core.junit import ParsedResult, parse_junit_xml

PARSERS = {
    # covers pytest, JUnit (Java/Maven Surefire), and Jest via jest-junit — same XML schema
    "junit": parse_junit_xml,
    "jest-json": parse_jest_json,
    "go-test-json": parse_go_test_json,
}


def parse_report(report_format: str, text: str) -> list[ParsedResult]:
    parser = PARSERS.get(report_format)
    if parser is None:
        raise ValueError(f"unsupported report format: {report_format!r}")
    return parser(text)
