"""ReAct tool implementations for the diagnostic agent (Phase 3). Each tool runs
against a git checkout of the target repo inside the Docker sandbox (see
sandbox.py for the execution boundary: no network, resource limits, timeout).
"""

from pathlib import Path

from core import junit, sandbox

MAX_RERUNS = 20


def rerun_test(image: str, workdir: Path, test_id: str, n: int = 10) -> str:
    n = max(1, min(n, MAX_RERUNS))
    node_id = sandbox.to_pytest_node_id(sandbox.validate_test_id(test_id))
    passed = failed = 0
    last_failure = ""
    for i in range(n):
        junit_out = workdir / f"rerun_{i}.xml"
        sandbox.run_pytest(image, [node_id], junit_out)
        for r in _safe_parse(junit_out):
            if r.outcome == "passed":
                passed += 1
            else:
                failed += 1
                last_failure = r.message or last_failure
    summary = f"{passed}/{n} passed, {failed}/{n} failed"
    return f"{summary}; last failure: {last_failure}" if failed else summary


def run_with_random_order(image: str, workdir: Path, test_id: str) -> str:
    node_id = sandbox.to_pytest_node_id(sandbox.validate_test_id(test_id))
    module_path = node_id.split("::")[0]
    junit_out = workdir / "random_order.xml"
    sandbox.run_pytest(image, [module_path, "-p", "randomly"], junit_out)
    return _report_for(junit_out, node_id, "with the full module run in random order")


def run_in_isolation(image: str, workdir: Path, test_id: str) -> str:
    node_id = sandbox.to_pytest_node_id(sandbox.validate_test_id(test_id))
    junit_out = workdir / "isolation.xml"
    sandbox.run_pytest(image, [node_id], junit_out)
    return _report_for(junit_out, node_id, "run alone, isolated from the rest of the suite")


def read_test_source(repo_dir: Path, path: str, max_chars: int = 4000) -> str:
    repo_root = repo_dir.resolve()
    target = (repo_dir / path).resolve()
    if not target.is_relative_to(repo_root) or not target.is_file():
        return f"error: {path!r} is not a readable file inside the repo"
    return target.read_text(errors="replace")[:max_chars]


def check_shared_fixtures(repo_dir: Path, test_id: str) -> str:
    repo_root = repo_dir.resolve()
    classname = test_id.split("::")[0]
    test_path = (repo_dir / (classname.replace(".", "/") + ".py")).resolve()
    directory = test_path.parent if test_path.is_relative_to(repo_root) else repo_root

    found = []
    while True:
        conftest = directory / "conftest.py"
        if conftest.is_file():
            found.append(f"# {conftest.relative_to(repo_root)}\n{conftest.read_text(errors='replace')[:2000]}")
        if directory == repo_root:
            break
        directory = directory.parent
    return "\n\n".join(found) or "no conftest.py found on the path to this test"


def _safe_parse(junit_path: Path) -> list:
    if not junit_path.exists():
        return []
    try:
        return junit.parse_junit_xml(junit_path.read_text())
    except Exception:  # noqa: BLE001 — malformed/partial JUnit output shouldn't crash the tool
        return []


def _report_for(junit_out: Path, node_id: str, context: str) -> str:
    target_name = node_id.split("::")[-1]
    match = next((r for r in _safe_parse(junit_out) if r.test_id.endswith(target_name)), None)
    if match is None:
        return f"test not found in results ({context})"
    if match.outcome == "passed":
        return f"passed {context}"
    return f"failed {context}: {match.message}"
