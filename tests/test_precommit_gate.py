"""Regression tests for the .githooks/pre-commit build gate.

These exist so the hook's behaviour is PROVEN by an automated test against a
throwaway git repo — never by live-firing a broken commit against the real
working tree. (On 2026-05-31 the hook was "tested" by actually committing
broken patches to the repo three times, each leaving a junk commit that needed
a manual reset. That affordance is removed here: if you want to know the hook
works, run this test.)

The hook itself shells out to `make build` + `make leakage-static`. To keep
these tests fast and deterministic we point them at a fake Makefile whose
targets pass/fail on a sentinel, so we exercise the HOOK'S decision logic
(which paths trigger the gate, does a gate failure block the commit) without a
multi-minute real build.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_SRC = REPO_ROOT / ".githooks" / "pre-commit"

FAKE_MAKEFILE = """\
build:
\t@test ! -f FAIL_BUILD
leakage-static:
\t@test ! -f FAIL_LEAK
"""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A throwaway git repo with the real hook installed and a fake Makefile."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    hooks = repo / ".githooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text(HOOK_SRC.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(hooks / "pre-commit", 0o755)
    _git(repo, "config", "core.hooksPath", ".githooks")
    (repo / "Makefile").write_text(FAKE_MAKEFILE, encoding="utf-8")
    (repo / "patches").mkdir()
    # Seed an initial commit so HEAD exists (bypass hook for the seed only).
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md", "Makefile", ".githooks")
    _git(repo, "commit", "-q", "--no-verify", "-m", "seed")
    return repo


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def test_gated_commit_passes_when_build_green(sandbox: Path) -> None:
    """A patches/ commit is allowed when the gate passes."""
    (sandbox / "patches" / "0001.patch").write_text("x\n", encoding="utf-8")
    _git(sandbox, "add", "patches/0001.patch")
    before = _head(sandbox)
    res = _git(sandbox, "commit", "-m", "add patch")
    assert res.returncode == 0, res.stderr
    assert _head(sandbox) != before, "commit should have been created"


def test_gated_commit_blocked_when_build_fails(sandbox: Path) -> None:
    """The exact failure that shipped a broken patch: build red -> commit BLOCKED."""
    (sandbox / "FAIL_BUILD").write_text("", encoding="utf-8")
    (sandbox / "patches" / "0001.patch").write_text("x\n", encoding="utf-8")
    _git(sandbox, "add", "patches/0001.patch")
    before = _head(sandbox)
    res = _git(sandbox, "commit", "-m", "broken patch")
    assert res.returncode != 0, "hook MUST block a commit when make build fails"
    assert _head(sandbox) == before, "HEAD must be unchanged when the gate blocks"


def test_gated_commit_blocked_when_leakage_fails(sandbox: Path) -> None:
    """leakage-static red also blocks."""
    (sandbox / "FAIL_LEAK").write_text("", encoding="utf-8")
    (sandbox / "patches" / "0001.patch").write_text("x\n", encoding="utf-8")
    _git(sandbox, "add", "patches/0001.patch")
    before = _head(sandbox)
    res = _git(sandbox, "commit", "-m", "leaky patch")
    assert res.returncode != 0
    assert _head(sandbox) == before


def test_non_gated_commit_skips_gate(sandbox: Path) -> None:
    """A docs-only commit must NOT run the gate (so it passes even if build is red)."""
    (sandbox / "FAIL_BUILD").write_text("", encoding="utf-8")
    (sandbox / "NOTES.md").write_text("notes\n", encoding="utf-8")
    _git(sandbox, "add", "NOTES.md")
    before = _head(sandbox)
    res = _git(sandbox, "commit", "-m", "docs only")
    assert res.returncode == 0, "non-gated paths must bypass the gate entirely"
    assert _head(sandbox) != before


@pytest.mark.parametrize("path", ["overlay/x.py", "tools/x.py", "nadia-rename.yaml"])
def test_all_gated_paths_trigger(sandbox: Path, path: str) -> None:
    """Every build-affecting path triggers the gate, not just patches/."""
    (sandbox / "FAIL_BUILD").write_text("", encoding="utf-8")
    target = sandbox / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n", encoding="utf-8")
    _git(sandbox, "add", path)
    before = _head(sandbox)
    res = _git(sandbox, "commit", "-m", f"touch {path}")
    assert res.returncode != 0, f"{path} must trigger the gate"
    assert _head(sandbox) == before
