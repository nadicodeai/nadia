"""Regression tests for update fork-origin detection."""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path
from typing import Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_MAIN = REPO_ROOT / "dist" / "nadia" / "nadia_cli" / "main.py"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _load_get_origin_url():
    source = DIST_MAIN.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_get_origin_url"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "subprocess": subprocess,
        "Path": Path,
        "Optional": Optional,
    }
    exec(compile(module, str(DIST_MAIN), "exec"), namespace)
    return namespace["_get_origin_url"]


@pytest.mark.skipif(not DIST_MAIN.is_file(), reason="dist/nadia not built (run `make build`)")
def test_get_origin_url_ignores_insteadof_transport_rewrite(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    official = "https://github.com/nadicodeai/argo.git"
    local_transport = "file:///tmp/nadia-release"
    assert _git(repo, "remote", "add", "origin", official).returncode == 0
    assert (
        _git(
            repo,
            "config",
            f"url.{local_transport}.insteadOf",
            official,
        ).returncode
        == 0
    )

    expanded = _git(repo, "remote", "get-url", "origin")
    assert expanded.stdout.strip() == local_transport

    get_origin_url = _load_get_origin_url()
    assert get_origin_url(["git"], repo) == official
