import pytest
from core import sandbox


def test_to_pytest_node_id_converts_dotted_classname():
    assert sandbox.to_pytest_node_id("tests.test_foo::test_bar") == "tests/test_foo.py::test_bar"


def test_to_pytest_node_id_passthrough_without_separator():
    assert sandbox.to_pytest_node_id("bare_name") == "bare_name"


def test_validate_test_id_accepts_normal_id():
    assert sandbox.validate_test_id("tests.test_foo::test_bar") == "tests.test_foo::test_bar"


@pytest.mark.parametrize("bad_id", ["a; rm -rf /", "a && echo hi", "a`whoami`", "a$(whoami)"])
def test_validate_test_id_rejects_shell_metacharacters(bad_id):
    with pytest.raises(sandbox.SandboxError):
        sandbox.validate_test_id(bad_id)


def test_real_sandbox_runs_pytest_with_no_network(tmp_path):
    """End-to-end against the real Docker daemon: build an image for a tiny repo
    with one passing test, run it in the sandbox, and confirm JUnit output is
    produced. Requires a working `docker` on PATH (true in this dev environment
    and on GitHub Actions ubuntu-latest runners)."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "Dockerfile").write_text(
        "FROM python:3.12-slim\nWORKDIR /workspace\nCOPY . .\nRUN pip install pytest\n"
    )
    (repo_dir / "test_flaky.py").write_text("def test_always_passes():\n    assert True\n")

    tag = "flakyradar-sandbox-test"
    try:
        sandbox.build_image(repo_dir, tag)
        junit_out = tmp_path / "out.xml"
        junit_out.parent.mkdir(exist_ok=True)
        sandbox.run_pytest(tag, ["test_flaky.py::test_always_passes"], junit_out)
        assert junit_out.exists()
        assert "test_always_passes" in junit_out.read_text()
    finally:
        sandbox.remove_image(tag)
