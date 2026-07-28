"""Shallow-clone a project's repo at a specific commit into a scratch directory,
so the diagnostic agent can run the real test suite.

ponytail: public repos, or a repo_url with embedded credentials — no separate
auth/token flow yet.
"""

import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def checkout(repo_url: str, commit_sha: str, dest: Path, timeout: int = 120) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    _run(["git", "init"], dest, timeout)
    _run(["git", "remote", "add", "origin", repo_url], dest, timeout)
    _run(["git", "fetch", "--depth", "1", "origin", commit_sha], dest, timeout)
    _run(["git", "checkout", "FETCH_HEAD"], dest, timeout)


def _run(cmd: list[str], cwd: Path, timeout: int) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise GitError(f"{' '.join(cmd)} failed:\n{proc.stderr[-2000:]}")
