"""Regression tests for the old fork-brand scanner."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNER = REPO_ROOT / "tools" / "verify_no_old_brand.py"


def _run(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), str(target)],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_reports_old_brand_tokens_in_content(tmp_path: Path) -> None:
    target = tmp_path / "dist"
    target.mkdir()
    (target / "README.md").write_text(
        "Install Argo Agent with argo setup and ARGO_HOME.\n",
        encoding="utf-8",
    )

    result = _run(target)

    assert result.returncode == 1
    assert "OLD BRAND LEAKAGE" in result.stderr
    assert "Argo Agent" in result.stderr
    assert "ARGO_HOME" in result.stderr


def test_reports_old_brand_tokens_in_paths(tmp_path: Path) -> None:
    target = tmp_path / "dist"
    config_dir = target / ".argo"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("ok\n", encoding="utf-8")

    result = _run(target)

    assert result.returncode == 1
    assert ".argo" in result.stderr


def test_reports_old_brand_repository_coordinates(tmp_path: Path) -> None:
    target = tmp_path / "dist"
    target.mkdir()
    (target / "install.sh").write_text(
        "curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh | bash\n",
        encoding="utf-8",
    )

    result = _run(target)

    assert result.returncode == 1
    assert "nadicodeai/argo" in result.stderr


def test_ignores_common_substrings_that_are_not_the_brand(tmp_path: Path) -> None:
    target = tmp_path / "dist"
    target.mkdir()
    (target / "Cargo.toml").write_text(
        "\n".join(
            [
                'name = "bootstrap-installer"',
                'password_hash = "argon2"',
                'italian = "Argomento sconosciuto: {arg}"',
            ]
        ),
        encoding="utf-8",
    )

    result = _run(target)

    assert result.returncode == 0, result.stderr
    assert "no old-brand references detected" in result.stdout
