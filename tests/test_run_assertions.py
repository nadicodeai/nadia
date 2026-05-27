"""tests/test_run_assertions.py — assertion-runner fixtures.

Validates tools/run_assertions.py against synthetic patch + assertion
configurations under tmp_path. Three scenarios:

1. Satisfied assertion (literal match) → exit 0.
2. Failed assertion (literal not in target) → exit 1, reports the patch.
3. Regex-form assertion satisfied → exit 0.
4. Path-restricted assertion that matches → exit 0.
5. Path-restricted assertion whose glob matches no files → exit 1.
6. Required patch missing its assertion file → exit 1.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "tools" / "run_assertions.py"


def _run_in(repo: Path, target: Path) -> subprocess.CompletedProcess[str]:
    """Run runner with --repo-root pointing at the fake repo."""
    env = os.environ.copy()
    return subprocess.run(
        [sys.executable, str(RUNNER), str(target), "--repo-root", str(repo)],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )


def _make_fake_repo(tmp_path: Path) -> Path:
    """Scaffold a minimal repo layout that run_assertions.py understands."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "patches").mkdir()
    (repo / "patches" / "asserts").mkdir()
    (repo / "patches" / "series").write_text("", encoding="utf-8")
    (repo / "patches" / "asserts" / "manifest.txt").write_text("", encoding="utf-8")
    return repo


def _add_patch(repo: Path, patch_name: str, asserts_lines: list[str], required: bool = False) -> None:
    series = repo / "patches" / "series"
    series.write_text(series.read_text() + patch_name + "\n", encoding="utf-8")
    if asserts_lines:
        (repo / "patches" / "asserts" / f"{Path(patch_name).stem}.txt").write_text(
            "\n".join(asserts_lines) + "\n", encoding="utf-8"
        )
    if required:
        manifest = repo / "patches" / "asserts" / "manifest.txt"
        manifest.write_text(manifest.read_text() + patch_name + "\n", encoding="utf-8")


def test_satisfied_literal_assertion(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    _add_patch(repo, "0001-test.patch", ["MAGIC_TOKEN_OK"])
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.py").write_text("x = 'MAGIC_TOKEN_OK'\n", encoding="utf-8")
    result = _run_in(repo, target)
    assert result.returncode == 0, result.stderr


def test_failed_literal_assertion(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    _add_patch(repo, "0001-test.patch", ["MAGIC_TOKEN_MISSING"])
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.py").write_text("nothing useful here\n", encoding="utf-8")
    result = _run_in(repo, target)
    assert result.returncode == 1
    assert "0001-test.patch" in result.stderr
    assert "MAGIC_TOKEN_MISSING" in result.stderr


def test_satisfied_regex_assertion(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    _add_patch(repo, "0001-test.patch", ["regex:def\\s+cmd_argo_\\w+"])
    target = tmp_path / "target"
    target.mkdir()
    (target / "f.py").write_text("def cmd_argo_update(args): pass\n", encoding="utf-8")
    result = _run_in(repo, target)
    assert result.returncode == 0, result.stderr


def test_path_restricted_match(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    _add_patch(repo, "0001-test.patch", ["path:.github/workflows/* if: false"])
    target = tmp_path / "target"
    (target / ".github" / "workflows").mkdir(parents=True)
    (target / ".github" / "workflows" / "ci.yml").write_text(
        "jobs:\n  x:\n    if: false\n", encoding="utf-8"
    )
    result = _run_in(repo, target)
    assert result.returncode == 0, result.stderr


def test_path_restricted_zero_files_fails(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    _add_patch(repo, "0001-test.patch", ["path:nonexistent/dir/* foo"])
    target = tmp_path / "target"
    target.mkdir()
    result = _run_in(repo, target)
    assert result.returncode == 1
    assert "0001-test.patch" in result.stderr


def test_required_patch_missing_asserts(tmp_path: Path) -> None:
    repo = _make_fake_repo(tmp_path)
    _add_patch(repo, "0001-test.patch", [], required=True)
    target = tmp_path / "target"
    target.mkdir()
    result = _run_in(repo, target)
    assert result.returncode == 1
    assert "0001-test.patch" in result.stderr
    assert "no assertion file" in result.stderr
