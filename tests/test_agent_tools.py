from core import agent_tools


def test_read_test_source_returns_file_content(tmp_path):
    (tmp_path / "test_foo.py").write_text("def test_x():\n    assert True\n")
    content = agent_tools.read_test_source(tmp_path, "test_foo.py")
    assert "def test_x" in content


def test_read_test_source_rejects_path_traversal(tmp_path):
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("secret")
    result = agent_tools.read_test_source(tmp_path, "../secret.txt")
    assert result.startswith("error:")


def test_read_test_source_rejects_missing_file(tmp_path):
    result = agent_tools.read_test_source(tmp_path, "nope.py")
    assert result.startswith("error:")


def test_check_shared_fixtures_finds_conftest(tmp_path):
    (tmp_path / "conftest.py").write_text("import pytest\n\n@pytest.fixture\ndef db(): ...\n")
    (tmp_path / "tests").mkdir()
    result = agent_tools.check_shared_fixtures(tmp_path, "tests.test_foo::test_bar")
    assert "conftest.py" in result
    assert "db" in result


def test_check_shared_fixtures_reports_none_found(tmp_path):
    result = agent_tools.check_shared_fixtures(tmp_path, "tests.test_foo::test_bar")
    assert "no conftest.py" in result


def test_rerun_test_aggregates_pass_fail(tmp_path, monkeypatch):
    outcomes = iter(["passed", "failed", "passed"])

    def fake_run_pytest(image, args, junit_out, timeout=60):
        junit_out.write_text(_junit_for(next(outcomes)))
        return ""

    monkeypatch.setattr("core.agent_tools.sandbox.run_pytest", fake_run_pytest)
    result = agent_tools.rerun_test("img", tmp_path, "tests.test_foo::test_bar", n=3)
    assert "2/3 passed" in result
    assert "1/3 failed" in result


def test_rerun_test_clamps_n(tmp_path, monkeypatch):
    calls = []

    def fake_run_pytest(image, args, junit_out, timeout=60):
        calls.append(1)
        junit_out.write_text(_junit_for("passed"))
        return ""

    monkeypatch.setattr("core.agent_tools.sandbox.run_pytest", fake_run_pytest)
    agent_tools.rerun_test("img", tmp_path, "tests.test_foo::test_bar", n=999)
    assert len(calls) == agent_tools.MAX_RERUNS


def test_run_in_isolation_reports_failure(tmp_path, monkeypatch):
    def fake_run_pytest(image, args, junit_out, timeout=60):
        junit_out.write_text(_junit_for("failed", message="boom"))
        return ""

    monkeypatch.setattr("core.agent_tools.sandbox.run_pytest", fake_run_pytest)
    result = agent_tools.run_in_isolation("img", tmp_path, "tests.test_foo::test_bar")
    assert "failed" in result
    assert "boom" in result


def _junit_for(outcome: str, message: str = "boom") -> str:
    if outcome == "passed":
        return '<testsuite><testcase classname="tests.test_foo" name="test_bar" time="0.1"/></testsuite>'
    return (
        '<testsuite><testcase classname="tests.test_foo" name="test_bar" time="0.1">'
        f'<failure message="{message}">trace</failure></testcase></testsuite>'
    )
