import json

import pytest
from core import report_formats
from core.gotest_format import parse_go_test_json
from core.jest_format import parse_jest_json
from core.junit import parse_junit_xml

# Maven Surefire-style JUnit XML — same schema as pytest's, dotted Java classname
JUNIT_JAVA_XML = """<testsuite name="com.example.OrderServiceTest" tests="2">
  <testcase classname="com.example.OrderServiceTest" name="testConcurrentCheckout" time="0.482">
    <failure message="expected:&lt;100&gt; but was:&lt;80&gt;">
      java.lang.AssertionError: expected:&lt;100&gt; but was:&lt;80&gt;
      at com.example.OrderServiceTest.testConcurrentCheckout(OrderServiceTest.java:42)
    </failure>
  </testcase>
  <testcase classname="com.example.OrderServiceTest" name="testRefund" time="0.05">
    <error message="NullPointerException">java.lang.NullPointerException</error>
  </testcase>
</testsuite>
"""

JEST_JSON = json.dumps(
    {
        "testResults": [
            {
                "name": "src/order.test.js",
                "testResults": [
                    {
                        "title": "processes an order",
                        "fullName": "Order processes an order",
                        "status": "passed",
                        "duration": 12,
                    },
                    {
                        "title": "handles a refund",
                        "fullName": "Order handles a refund",
                        "status": "failed",
                        "duration": 8,
                        "failureMessages": ["Error: expected 100 to be 80\n  at Object.<anonymous>"],
                    },
                    {
                        "title": "skipped one",
                        "fullName": "Order skipped one",
                        "status": "pending",
                        "duration": 0,
                    },
                ],
            }
        ]
    }
)

GO_TEST_NDJSON = "\n".join(
    json.dumps(event)
    for event in [
        {"Action": "run", "Package": "pkg/order", "Test": "TestCheckout"},
        {"Action": "output", "Package": "pkg/order", "Test": "TestCheckout", "Output": "=== RUN   TestCheckout\n"},
        {
            "Action": "output",
            "Package": "pkg/order",
            "Test": "TestCheckout",
            "Output": "    order_test.go:10: expected 100, got 80\n",
        },
        {"Action": "fail", "Package": "pkg/order", "Test": "TestCheckout", "Elapsed": 0.02},
        {"Action": "run", "Package": "pkg/order", "Test": "TestRefund"},
        {"Action": "pass", "Package": "pkg/order", "Test": "TestRefund", "Elapsed": 0.01},
        {"Action": "pass", "Package": "pkg/order"},  # package-level summary, no Test key
    ]
)


def test_junit_parser_handles_java_style_classname_and_error_tag():
    results = parse_junit_xml(JUNIT_JAVA_XML)
    assert len(results) == 2
    assert results[0].test_id == "com.example.OrderServiceTest::testConcurrentCheckout"
    assert results[0].outcome == "failed"
    assert results[1].outcome == "error"


def test_jest_parser_maps_status_and_converts_duration_to_seconds():
    results = parse_jest_json(JEST_JSON)
    assert len(results) == 3
    passed, failed, skipped = results
    assert passed.outcome == "passed"
    assert passed.duration == 0.012
    assert failed.outcome == "failed"
    assert "expected 100 to be 80" in failed.message
    assert skipped.outcome == "skipped"


def test_gotest_parser_aggregates_output_and_skips_package_summary():
    results = parse_go_test_json(GO_TEST_NDJSON)
    assert len(results) == 2
    failed = next(r for r in results if r.test_id == "pkg/order::TestCheckout")
    assert failed.outcome == "failed"
    assert "expected 100, got 80" in failed.message
    passed = next(r for r in results if r.test_id == "pkg/order::TestRefund")
    assert passed.outcome == "passed"
    assert passed.duration == 0.01


def test_registry_dispatches_by_format_name():
    assert len(report_formats.parse_report("junit", JUNIT_JAVA_XML)) == 2
    assert len(report_formats.parse_report("jest-json", JEST_JSON)) == 3
    assert len(report_formats.parse_report("go-test-json", GO_TEST_NDJSON)) == 2


def test_registry_rejects_unknown_format():
    with pytest.raises(ValueError, match="unsupported report format"):
        report_formats.parse_report("cobol-test-xml", "")
