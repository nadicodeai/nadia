"""Regression test for build.py's upstream→dist copy excluding bytecode caches.

Running tests against the tracked tree (e.g. `PYTHONPATH=upstream pytest`) or an
editable install leaves untracked `__pycache__/*.pyc` behind in `upstream/`.
`_copy_upstream` used to copy those verbatim into `dist/nadia/`, where the
China-strip step then tripped on an orphan compiled artifact whose `*.py`
source had been pruned (`un-denylisted China path survived prune:
tools/__pycache__/feishu_doc_tool.cpython-311.pyc`). Bytecode is never source —
the copy MUST skip it so the build is deterministic regardless of working-tree
pollution.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# tools/ is not a package; extend sys.path so we can import build directly.
sys.path.insert(0, str(REPO_ROOT / "tools"))
import build  # noqa: E402


def test_copy_upstream_excludes_pycache_and_pyc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream = tmp_path / "upstream"
    (upstream / "tools" / "__pycache__").mkdir(parents=True)
    # Real source — must be copied.
    (upstream / "tools" / "feishu_doc_tool.py").write_text("x = 1\n", encoding="utf-8")
    # Nested bytecode pollution — must be skipped.
    (upstream / "tools" / "__pycache__" / "feishu_doc_tool.cpython-311.pyc").write_bytes(b"\x00")
    # Top-level bytecode pollution — must be skipped.
    (upstream / "__pycache__").mkdir()
    (upstream / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\x00")
    # Tracking file — excluded by existing behaviour.
    (upstream / ".commit").write_text("sha\n", encoding="utf-8")

    dist = tmp_path / "dist"
    dist.mkdir()
    monkeypatch.setattr(build, "UPSTREAM_DIR", upstream)
    monkeypatch.setattr(build, "DIST_DIR", dist)

    build._copy_upstream()

    # Real source survived.
    assert (dist / "tools" / "feishu_doc_tool.py").is_file()
    # No bytecode caches anywhere in the build output.
    assert list(dist.rglob("__pycache__")) == []
    assert list(dist.rglob("*.pyc")) == []
    # The tracking file is still excluded.
    assert not (dist / ".commit").exists()
