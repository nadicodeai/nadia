"""tests/test_check_upstream_pristine.py — FR-15 gate tests.

Validates `tools/check_upstream_pristine.py` against the real repo
(clean state, synthetic-drift, and structural-failure cases). The
drift fixture mutates a tracked file under `upstream/` and MUST
self-clean before the test returns — the rest of the suite assumes
`upstream/` is pristine.

Scenarios:

1. Clean state: default repo → exit 0.
2. Synthetic drift: mutate `upstream/README.md` → exit 1, path named.
3. Synthetic drift (untracked): add an untracked file under `upstream/`
   → exit 1, path named.
4. Empty-upstream defensive: a fake repo where `upstream/.commit`
   exists but no other files exist → exit 2.
5. Missing-`.commit` defensive: a fake repo where `upstream/` exists
   but `upstream/.commit` is absent → exit 2.
6. Quiet mode: clean state with `-q` produces no stdout summary.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_upstream_pristine.py"


def _run(
    *extra_args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the checker with optional extra args; default cwd is repo root."""
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra_args],
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


@contextmanager
def _temporarily_modified(path: Path, addition: str) -> Iterator[None]:
    """Append ``addition`` to ``path`` for the duration of the with-block.

    Restores the original bytes on exit even if the test raises.
    """
    original = path.read_bytes()
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(addition)
        yield
    finally:
        path.write_bytes(original)


@contextmanager
def _temporary_untracked(path: Path, content: str) -> Iterator[None]:
    """Create an untracked file at ``path`` for the duration of the with-block."""
    try:
        path.write_text(content, encoding="utf-8")
        yield
    finally:
        if path.exists():
            path.unlink()


def test_clean_state_exits_zero() -> None:
    """Default repo state should be pristine."""
    result = _run()
    assert result.returncode == 0, (
        f"expected 0, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Success summary names the sync commit.
    assert "upstream pristine" in result.stdout
    assert "sync-commit" in result.stdout


def test_quiet_mode_suppresses_summary() -> None:
    """`-q` produces no stdout on success."""
    result = _run("-q")
    assert result.returncode == 0
    assert result.stdout == ""


def test_synthetic_drift_in_tracked_file_detected() -> None:
    """Mutating a tracked file under upstream/ → exit 1, file named in stderr."""
    target = REPO_ROOT / "upstream" / "README.md"
    assert target.is_file(), "test prerequisite: upstream/README.md must exist"
    with _temporarily_modified(target, "\n# argo-drift-fixture\n"):
        result = _run()
        assert result.returncode == 1, (
            f"expected 1, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "drift detected" in result.stderr
        assert "upstream/README.md" in result.stderr
    # Post-condition: the file MUST be back to its committed state.
    diff = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "upstream/README.md"],
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert diff.stdout.strip() == "", (
        f"drift fixture leaked: {diff.stdout!r}"
    )


def test_synthetic_drift_untracked_file_detected() -> None:
    """An untracked file under upstream/ → exit 1, file named in stderr."""
    target = REPO_ROOT / "upstream" / "argo_drift_untracked.txt"
    # Refuse to clobber if a stray file is already there.
    assert not target.exists(), (
        f"test prerequisite: {target} must not pre-exist"
    )
    with _temporary_untracked(target, "synthetic drift\n"):
        result = _run()
        assert result.returncode == 1
        assert "drift detected" in result.stderr
        assert "argo_drift_untracked.txt" in result.stderr
    assert not target.exists(), "untracked fixture leaked"


def _scaffold_fake_repo(root: Path) -> None:
    """Init a real git repo at ``root`` so the script's git calls succeed."""
    subprocess.run(
        ["git", "init", "--quiet", "--initial-branch=main"],
        cwd=str(root),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=str(root),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(root),
        check=True,
    )


def test_empty_upstream_dir_exits_2(tmp_path: Path) -> None:
    """upstream/.commit present but no other files → structural error (exit 2)."""
    fake = tmp_path / "fake-repo"
    fake.mkdir()
    _scaffold_fake_repo(fake)
    (fake / "upstream").mkdir()
    (fake / "upstream" / ".commit").write_text("deadbeef\n", encoding="utf-8")
    result = _run("--repo-root", str(fake), cwd=fake)
    assert result.returncode == 2, (
        f"expected 2, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "bootstrap incomplete" in result.stderr


def test_missing_commit_file_exits_2(tmp_path: Path) -> None:
    """upstream/ exists but .commit absent → structural error (exit 2)."""
    fake = tmp_path / "fake-repo"
    fake.mkdir()
    _scaffold_fake_repo(fake)
    (fake / "upstream").mkdir()
    (fake / "upstream" / "some-file.txt").write_text("x\n", encoding="utf-8")
    result = _run("--repo-root", str(fake), cwd=fake)
    assert result.returncode == 2
    assert ".commit" in result.stderr


def test_missing_upstream_dir_exits_2(tmp_path: Path) -> None:
    """upstream/ dir missing entirely → structural error (exit 2)."""
    fake = tmp_path / "fake-repo"
    fake.mkdir()
    _scaffold_fake_repo(fake)
    result = _run("--repo-root", str(fake), cwd=fake)
    assert result.returncode == 2
    assert "upstream" in result.stderr


def test_not_a_git_repo_exits_2(tmp_path: Path) -> None:
    """A directory with upstream/ files but no .git → structural error."""
    fake = tmp_path / "not-a-repo"
    fake.mkdir()
    (fake / "upstream").mkdir()
    (fake / "upstream" / ".commit").write_text("deadbeef\n", encoding="utf-8")
    (fake / "upstream" / "f.txt").write_text("x\n", encoding="utf-8")
    result = _run("--repo-root", str(fake), cwd=fake)
    assert result.returncode == 2
    assert "git repository" in result.stderr


def test_no_history_touched_upstream_exits_2(tmp_path: Path) -> None:
    """A real git repo where no commit ever touched upstream/ → exit 2."""
    fake = tmp_path / "fake-repo"
    fake.mkdir()
    _scaffold_fake_repo(fake)
    (fake / "upstream").mkdir()
    (fake / "upstream" / ".commit").write_text("deadbeef\n", encoding="utf-8")
    (fake / "upstream" / "f.txt").write_text("x\n", encoding="utf-8")
    # Make a commit that does NOT include upstream/ — `upstream/` is untracked.
    (fake / "README.md").write_text("hi\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=str(fake),
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init", "--quiet"],
        cwd=str(fake),
        check=True,
    )
    result = _run("--repo-root", str(fake), cwd=fake)
    assert result.returncode == 2
    assert "bootstrap" in result.stderr.lower() or "no commit" in result.stderr.lower()


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_exits_zero(flag: str) -> None:
    """`--help` / `-h` exit 0 — basic argparse sanity check."""
    result = _run(flag)
    assert result.returncode == 0
    assert "upstream" in result.stdout.lower()
