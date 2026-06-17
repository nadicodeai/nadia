"""tests/test_nadia_release.py — pure-function coverage for tools/nadia_release.py.

Mirrors the upstream pure helpers cited in the module docstring of
``tools/nadia_release.py`` (``upstream/scripts/release.py:1390-1436``):

- ``_bump_semver`` for patch / minor / major bumps.
- ``_format_today_calver`` for the ``YYYY.M.D`` no-zero-pad format.
- ``_validate_calver`` / ``_validate_semver`` reject malformed inputs.
- ``_rewrite_version_file`` / ``_rewrite_pyproject_version`` substitute the
  expected lines on known fixtures.

These tests stay hermetic — no subprocess, no filesystem writes outside
``tmp_path`` (none needed for pure functions), no git.

Run with::

    pytest tests/test_nadia_release.py -v
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

# Load tools/nadia_release.py by absolute path. Register in sys.modules under
# the same name BEFORE exec_module so that @dataclass(frozen=True) can look
# itself up during class processing (a known CPython 3.12+ behavior — see
# https://github.com/python/cpython/issues/97576).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "tools" / "nadia_release.py"
_MODULE_NAME = "nadia_release_under_test"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
nadia_release = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = nadia_release
_spec.loader.exec_module(nadia_release)


# ---------------------------------------------------------------------------
# _bump_semver
# ---------------------------------------------------------------------------


class TestBumpSemver:
    def test_patch_increments_z(self) -> None:
        assert nadia_release._bump_semver("0.14.0", "patch") == "0.14.1"

    def test_patch_from_nonzero_z(self) -> None:
        assert nadia_release._bump_semver("0.14.7", "patch") == "0.14.8"

    def test_minor_zeros_z_and_increments_y(self) -> None:
        assert nadia_release._bump_semver("0.14.7", "minor") == "0.15.0"

    def test_major_zeros_y_z_and_increments_x(self) -> None:
        assert nadia_release._bump_semver("0.14.7", "major") == "1.0.0"

    def test_unknown_part_raises(self) -> None:
        with pytest.raises(nadia_release.VersionParseError):
            nadia_release._bump_semver("0.14.0", "build")

    def test_non_triple_raises(self) -> None:
        with pytest.raises(nadia_release.VersionParseError):
            nadia_release._bump_semver("0.14", "patch")

    def test_non_integer_component_raises(self) -> None:
        with pytest.raises(nadia_release.VersionParseError):
            nadia_release._bump_semver("0.14.x", "patch")


# ---------------------------------------------------------------------------
# _format_today_calver
# ---------------------------------------------------------------------------


class TestFormatTodayCalver:
    def test_no_zero_padding_single_digit_month(self) -> None:
        assert nadia_release._format_today_calver(date(2026, 5, 28)) == "2026.5.28"

    def test_no_zero_padding_single_digit_day(self) -> None:
        assert nadia_release._format_today_calver(date(2026, 5, 1)) == "2026.5.1"

    def test_double_digit_month_and_day(self) -> None:
        assert nadia_release._format_today_calver(date(2026, 12, 31)) == "2026.12.31"

    def test_default_calls_date_today(self) -> None:
        # Just shape — current year / month / day are non-zero-padded.
        out = nadia_release._format_today_calver()
        parts = out.split(".")
        assert len(parts) == 3
        # Each part is plain integer text (no leading zero unless it IS "0",
        # which never happens for year/month/day).
        for piece in parts:
            assert piece == str(int(piece)), f"unexpected padding: {out}"


# ---------------------------------------------------------------------------
# _validate_calver / _validate_semver
# ---------------------------------------------------------------------------


class TestValidators:
    @pytest.mark.parametrize(
        "value", ["2026.5.28", "2026.12.31", "2026.1.1", "2026.5.28.2"]
    )
    def test_calver_accepts_valid(self, value: str) -> None:
        nadia_release._validate_calver(value)  # no raise

    @pytest.mark.parametrize(
        "value", ["2026.5", "2026.05.28", "v2026.5.28", "2026.5.28-rc1", ""]
    )
    def test_calver_rejects_invalid(self, value: str) -> None:
        with pytest.raises(nadia_release.VersionParseError):
            nadia_release._validate_calver(value)

    @pytest.mark.parametrize("value", ["0.14.0", "1.2.3", "10.20.30"])
    def test_semver_accepts_valid(self, value: str) -> None:
        nadia_release._validate_semver(value)  # no raise

    @pytest.mark.parametrize(
        "value", ["0.14", "0.14.0-rc1", "v0.14.0", "0.14.0.1", ""]
    )
    def test_semver_rejects_invalid(self, value: str) -> None:
        with pytest.raises(nadia_release.VersionParseError):
            nadia_release._validate_semver(value)


# ---------------------------------------------------------------------------
# _rewrite_version_file
# ---------------------------------------------------------------------------


_INIT_FIXTURE = '''"""Nadia CLI - Unified command-line interface for Nadia Agent."""

import os
import sys

__version__ = "0.14.0"
__release_date__ = "2026.5.16"

# downstream usage here
print(__version__)
'''


class TestRewriteVersionFile:
    def test_substitutes_both_strings(self) -> None:
        out = nadia_release._rewrite_version_file(
            _INIT_FIXTURE,
            new_version="0.14.1",
            new_release_date="2026.5.28",
        )
        assert '__version__ = "0.14.1"' in out
        assert '__release_date__ = "2026.5.28"' in out
        # Old values are gone.
        assert '__version__ = "0.14.0"' not in out
        assert '__release_date__ = "2026.5.16"' not in out

    def test_preserves_other_content(self) -> None:
        out = nadia_release._rewrite_version_file(
            _INIT_FIXTURE,
            new_version="0.14.1",
            new_release_date="2026.5.28",
        )
        # Docstring and tail preserved.
        assert "Nadia CLI" in out
        assert "print(__version__)" in out

    def test_idempotent_when_already_at_target(self) -> None:
        # Running twice yields the same result.
        first = nadia_release._rewrite_version_file(
            _INIT_FIXTURE,
            new_version="0.14.1",
            new_release_date="2026.5.28",
        )
        second = nadia_release._rewrite_version_file(
            first,
            new_version="0.14.1",
            new_release_date="2026.5.28",
        )
        assert first == second

    def test_no_match_returns_unchanged(self) -> None:
        text = "no version markers here\n"
        out = nadia_release._rewrite_version_file(
            text, new_version="9.9.9", new_release_date="2099.1.1"
        )
        assert out == text


# ---------------------------------------------------------------------------
# _rewrite_pyproject_version
# ---------------------------------------------------------------------------


_PYPROJECT_FIXTURE = """[project]
name = "nadia-agent"
version = "0.14.0"
description = "Nadia Agent"
requires-python = ">=3.11"

[tool.uv]
# nested table with its own 'version = "..."' that MUST NOT be rewritten —
# only the top-level project.version line gets touched.
dev-dependencies = []
"""


class TestRewritePyprojectVersion:
    def test_rewrites_top_level_version_only(self) -> None:
        out = nadia_release._rewrite_pyproject_version(
            _PYPROJECT_FIXTURE, new_version="0.14.1"
        )
        assert 'version = "0.14.1"' in out
        assert 'version = "0.14.0"' not in out

    def test_preserves_other_content(self) -> None:
        out = nadia_release._rewrite_pyproject_version(
            _PYPROJECT_FIXTURE, new_version="0.14.1"
        )
        assert 'name = "nadia-agent"' in out
        assert "[tool.uv]" in out

    def test_no_match_returns_unchanged(self) -> None:
        text = "[project]\nname = \"nadia-agent\"\n"
        out = nadia_release._rewrite_pyproject_version(text, new_version="9.9.9")
        assert out == text


# ---------------------------------------------------------------------------
# _resolve_repo_root sanity (one integration-ish check that fails cleanly
# outside a git repo — uses tmp_path which is not a git repo).
# ---------------------------------------------------------------------------


class TestResolveRepoRoot:
    def test_raises_outside_git_repo(self, tmp_path: Path) -> None:
        with pytest.raises(nadia_release.NotAGitRepoError):
            nadia_release._resolve_repo_root(tmp_path)
