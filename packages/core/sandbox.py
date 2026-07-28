"""Docker sandbox for running a target repo's test suite under strict limits.

Network is only reachable while building the sandbox image (installing deps via
`docker build`); every actual test-execution run goes through `docker run
--network none` plus CPU/RAM/pids/time limits. ponytail: no read-only rootfs or
seccomp profile yet — resource limits + no network + timeout are the enforced
boundary for now; tighten if this ever runs against untrusted third-party repos.
"""

import re
import subprocess
import uuid
from pathlib import Path

MEM_LIMIT = "512m"
CPU_LIMIT = "1.0"
PIDS_LIMIT = "128"
BUILD_TIMEOUT = 300
RUN_TIMEOUT = 60

# JUnit classname::name identifiers only — no shell metacharacters, no path traversal
TEST_ID_RE = re.compile(r"^[\w./:-]+$")


class SandboxError(Exception):
    pass


def validate_test_id(test_id: str) -> str:
    if not TEST_ID_RE.match(test_id):
        raise SandboxError(f"invalid test id: {test_id!r}")
    return test_id


def to_pytest_node_id(test_id: str) -> str:
    """Best-effort conversion from JUnit classname::name to a pytest node id.

    ponytail: assumes the classname mirrors the module's file path (true for
    plain function tests without a wrapping class) — doesn't handle nested
    TestClass methods or non-standard rootdirs. Good enough for MVP.
    """
    classname, sep, name = test_id.rpartition("::")
    if not sep:
        return test_id
    path = classname.replace(".", "/") + ".py"
    return f"{path}::{name}"


def build_image(repo_dir: Path, tag: str) -> None:
    proc = subprocess.run(
        ["docker", "build", "-t", tag, str(repo_dir)],
        capture_output=True,
        text=True,
        timeout=BUILD_TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise SandboxError(f"sandbox image build failed:\n{proc.stderr[-2000:]}")


def remove_image(tag: str) -> None:
    subprocess.run(["docker", "rmi", "-f", tag], capture_output=True, timeout=30, check=False)


def run_pytest(image: str, args: list[str], junit_out: Path, timeout: int = RUN_TIMEOUT) -> str:
    """Run pytest inside the sandbox image, no network, resource-limited, with a
    JUnit XML report written to junit_out. Returns combined stdout+stderr."""
    container = f"flakyradar-{uuid.uuid4().hex[:12]}"
    cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        container,
        "--network",
        "none",
        "--memory",
        MEM_LIMIT,
        "--cpus",
        CPU_LIMIT,
        "--pids-limit",
        PIDS_LIMIT,
        "-v",
        f"{junit_out.parent}:/sandbox_out",
        image,
        "pytest",
        *args,
        "-q",
        f"--junitxml=/sandbox_out/{junit_out.name}",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "kill", container], capture_output=True, check=False)
        raise SandboxError(f"pytest run timed out after {timeout}s") from exc
    return (proc.stdout + proc.stderr)[-4000:]
