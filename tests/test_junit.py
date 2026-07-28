from core.junit import parse_junit_xml

SIMPLE = """<?xml version="1.0"?>
<testsuite name="pytest" tests="2">
  <testcase classname="tests.test_foo" name="test_pass" time="0.01"/>
  <testcase classname="tests.test_foo" name="test_fail" time="0.02">
    <failure message="AssertionError: boom">Traceback...</failure>
  </testcase>
</testsuite>
"""

NESTED = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="pytest">
    <testcase classname="a" name="b" time="0.5">
      <skipped message="not ready"/>
    </testcase>
  </testsuite>
</testsuites>
"""


def test_parses_pass_and_failure():
    results = parse_junit_xml(SIMPLE)
    assert len(results) == 2
    assert results[0].test_id == "tests.test_foo::test_pass"
    assert results[0].outcome == "passed"
    assert results[1].outcome == "failed"
    assert results[1].message == "AssertionError: boom"
    assert results[1].stack_trace == "Traceback..."


def test_parses_nested_testsuites_and_skipped():
    results = parse_junit_xml(NESTED)
    assert len(results) == 1
    assert results[0].test_id == "a::b"
    assert results[0].outcome == "skipped"


def test_handles_missing_time_attr():
    xml = '<testsuite><testcase classname="a" name="b"/></testsuite>'
    results = parse_junit_xml(xml)
    assert results[0].duration == 0.0
