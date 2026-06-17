"""tests/test_verify_no_leakage.py — fixtures for the static leakage scanner.

Validates tools/verify_no_leakage.py against two fixture trees:

- tests/fixtures/leakage_positive/  → MUST report leakage (exit 1).
  Contains literal `hermes` references outside any exception/skip_context.
  Includes mixed-case stylized brand strings (HeRmEs / HERMES) per OQ-16.

- tests/fixtures/leakage_negative/  → MUST be clean (exit 0).
  Contains `hermes` inside skip_context-covered URLs and inside an
  exception-listed file (nadia-rename.yaml itself).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNER = REPO_ROOT / "tools" / "verify_no_leakage.py"
POSITIVE = REPO_ROOT / "tests" / "fixtures" / "leakage_positive"
NEGATIVE = REPO_ROOT / "tests" / "fixtures" / "leakage_negative"


def _run(target: Path, rename_yaml: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCANNER),
            str(target),
            "--rename-yaml",
            str(rename_yaml),
        ],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_positive_fixture_reports_leakage() -> None:
    """A file with an uncovered `hermes` token MUST be detected."""
    result = _run(POSITIVE, POSITIVE / "nadia-rename.yaml")
    assert result.returncode == 1, (
        f"expected exit 1, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "LEAKAGE" in result.stderr
    # The planted hermes_thing line must be among the hits.
    assert "hermes_thing" in result.stderr


def test_positive_fixture_catches_stylized_brand_strings() -> None:
    """Mixed-case `HeRmEs` and `HERMES` must be reported (case-insensitive)."""
    result = _run(POSITIVE, POSITIVE / "nadia-rename.yaml")
    assert result.returncode == 1
    # The stylized.md file's lines should appear in stderr (case-insensitive
    # match, so the scanner finds HeRmEs and HERMES).
    assert "stylized.md" in result.stderr


def test_negative_fixture_no_leakage() -> None:
    """URL-bounded and exception-listed `hermes` MUST be tolerated."""
    result = _run(NEGATIVE, NEGATIVE / "nadia-rename.yaml")
    assert result.returncode == 0, (
        f"expected exit 0, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "no leakage detected" in result.stdout
