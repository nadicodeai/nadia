"""Regression tests for the CI-side Nadia release bump."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "tools" / "apply_release_bump.py"
_MODULE_NAME = "apply_release_bump_under_test"
_spec = importlib.util.spec_from_file_location(_MODULE_NAME, _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
apply_release_bump = importlib.util.module_from_spec(_spec)
sys.modules[_MODULE_NAME] = apply_release_bump
_spec.loader.exec_module(apply_release_bump)


def test_apply_release_bump_updates_cli_python_and_desktop_versions(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist" / "nadia"
    (dist / "nadia_cli").mkdir(parents=True)
    (dist / "apps" / "desktop").mkdir(parents=True)
    (dist / "nadia_cli" / "__init__.py").write_text(
        '__version__ = "0.15.1"\n__release_date__ = "2026.6.16"\n',
        encoding="utf-8",
    )
    (dist / "pyproject.toml").write_text(
        '[project]\nname = "nadia-agent"\nversion = "0.15.1"\n',
        encoding="utf-8",
    )
    (dist / "apps" / "desktop" / "package.json").write_text(
        json.dumps({"name": "nadia", "version": "0.15.1"}) + "\n",
        encoding="utf-8",
    )
    (dist / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "nadia-agent",
                "version": "1.0.0",
                "packages": {
                    "": {"name": "nadia-agent", "version": "1.0.0"},
                    "apps/desktop": {"name": "nadia", "version": "0.15.1"},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rc = apply_release_bump.main(
        [
            "--version",
            "0.16.0",
            "--release-date",
            "2026.6.17",
            "--dist-root",
            str(dist),
        ]
    )

    assert rc == 0
    assert '__version__ = "0.16.0"' in (
        dist / "nadia_cli" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert '__release_date__ = "2026.6.17"' in (
        dist / "nadia_cli" / "__init__.py"
    ).read_text(encoding="utf-8")
    assert 'version = "0.16.0"' in (dist / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    desktop_package = json.loads(
        (dist / "apps" / "desktop" / "package.json").read_text(encoding="utf-8")
    )
    package_lock = json.loads((dist / "package-lock.json").read_text(encoding="utf-8"))
    assert desktop_package["version"] == "0.16.0"
    assert package_lock["packages"][""]["version"] == "1.0.0"
    assert package_lock["packages"]["apps/desktop"]["version"] == "0.16.0"
