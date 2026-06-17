"""overlay/tests/test_sync_fixture_ac3.py — AC-3 single non-overlapping
patch sync.

Exercises ``tests/fixtures/sync-fixture-ac3/`` end-to-end against the
``quilt push -a`` step that ``tools/sync.py`` ultimately drives:

1. Extract ``baseline-tree.tar.zst`` into a tmpdir simulating a pinned
   "upstream" worktree at the fixture's baseline.
2. ``git init`` + commit the baseline.
3. ``git apply upstream-refactor.patch`` + commit — replicates the
   "upstream refactored away from our insertion point" scenario.
4. Drop ``fork-flag.patch`` into a quilt patches/ dir and run
   ``QUILT_PATCHES=patches quilt push -a`` against the refactored tree.
5. Assert: exit code 0; no ``.rej`` or ``.orig`` files; the final
   ``baseline.py`` contains BOTH the refactor markers AND the fork
   addition; every pattern in ``asserts.txt`` is present.

Spec AC-3: *Given `patches/series` contains one patch that adds a
`--static` flag to `hermes_cli/main.py`, and upstream refactors
`hermes_cli/main.py` away from the patch's insertion lines, when
`make sync` runs, then `quilt push -a` succeeds without manual
intervention.*

The fixture's `baseline.py` stands in for `hermes_cli/main.py`; the
geometry (head-of-file refactor vs tail-of-file fork insertion) is what
the spec is asserting a property about.

Marked ``@pytest.mark.integration``; skipped by default. Re-enable with
``pytest -m integration``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

# overlay/tests/ is not a Python package (no __init__.py — overlay files
# ship as a flat copy into dist/nadia/tests/), so import the sibling
# helpers module via sys.path.
sys.path.insert(0, str(Path(__file__).parent))
from _sync_fixture_helpers import (  # noqa: E402
    extract_baseline_tree as _extract_baseline_tree_impl,
    git_env_no_signing as _git_env_no_signing,
    run as _run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sync-fixture-ac3"
BASELINE_TARBALL = FIXTURE_DIR / "baseline-tree.tar.zst"
UPSTREAM_REFACTOR_PATCH = FIXTURE_DIR / "upstream-refactor.patch"
FORK_FLAG_PATCH = FIXTURE_DIR / "fork-flag.patch"
ASSERTS_FILE = FIXTURE_DIR / "asserts.txt"
FIXTURE_README = FIXTURE_DIR / "README.md"


def _have_fixture() -> bool:
    return (
        BASELINE_TARBALL.is_file()
        and UPSTREAM_REFACTOR_PATCH.is_file()
        and FORK_FLAG_PATCH.is_file()
        and ASSERTS_FILE.is_file()
        and FIXTURE_README.is_file()
    )


def _extract_baseline_tree(dest: Path) -> None:
    """Extract this fixture's baseline tarball into *dest*."""
    _extract_baseline_tree_impl(BASELINE_TARBALL, dest)


def _load_asserts() -> list[str]:
    """Read non-comment, non-blank patterns from ``asserts.txt``."""
    patterns: list[str] = []
    for raw in ASSERTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


@pytest.mark.integration
@pytest.mark.skipif(
    not BASELINE_TARBALL.is_file(),
    reason=f"fixture missing: {BASELINE_TARBALL}",
)
def test_ac3_non_overlapping_quilt_push_succeeds(tmp_path: Path) -> None:
    """AC-3: fork patch + upstream refactor on disjoint lines coexist.

    No manual intervention; ``quilt push -a`` exits 0; no ``.rej``
    files; the final file contains both edits.
    """

    if not _have_fixture():
        pytest.skip("sync-fixture-ac3 incomplete")
    if shutil.which("quilt") is None:
        pytest.skip("quilt not installed on this host")
    if shutil.which("unzstd") is None and shutil.which("zstd") is None:
        pytest.skip("zstd/unzstd not installed on this host")

    env = _git_env_no_signing()

    # 1. Extract baseline.
    worktree = tmp_path / "worktree"
    _extract_baseline_tree(worktree)
    baseline_py = worktree / "baseline.py"
    assert baseline_py.is_file(), "tarball did not contain baseline.py"

    # 2. git init + commit baseline.
    _run(["git", "init", "--initial-branch=main", "-q"], cwd=worktree, env=env)
    _run(["git", "add", "-A"], cwd=worktree, env=env)
    _run(["git", "commit", "-q", "-m", "baseline"], cwd=worktree, env=env)

    # 3. Apply upstream-refactor.patch as a second commit.
    _run(
        ["git", "apply", "--check", str(UPSTREAM_REFACTOR_PATCH)],
        cwd=worktree,
        env=env,
    )
    _run(
        ["git", "apply", str(UPSTREAM_REFACTOR_PATCH)],
        cwd=worktree,
        env=env,
    )
    _run(["git", "add", "-A"], cwd=worktree, env=env)
    _run(
        ["git", "commit", "-q", "-m", "upstream refactor"],
        cwd=worktree,
        env=env,
    )

    # Sanity: post-refactor file has the new symbols and not the old
    # one-arg signature.
    refactored = baseline_py.read_text(encoding="utf-8")
    assert "def _existing_message" in refactored
    assert "def cmd_existing(args, *, verbose=False)" in refactored
    assert "def cmd_existing(args):\n" not in refactored

    # 4. Stage the fork-flag patch in a quilt patches/ dir and push.
    patches_dir = worktree / "patches"
    patches_dir.mkdir()
    shutil.copy2(FORK_FLAG_PATCH, patches_dir / "fork-flag.patch")
    (patches_dir / "series").write_text("fork-flag.patch\n", encoding="utf-8")

    quilt_env = env.copy()
    quilt_env["QUILT_PATCHES"] = "patches"
    push_result = _run(
        ["quilt", "push", "-a"],
        cwd=worktree,
        env=quilt_env,
        check=False,
    )
    assert push_result.returncode == 0, (
        "quilt push -a failed (AC-3 violation: non-overlapping patch did "
        "NOT apply cleanly):\n"
        f"stdout: {push_result.stdout}\nstderr: {push_result.stderr}"
    )

    # 5a. No .rej or .orig files anywhere in the worktree.
    rejects = [
        str(p.relative_to(worktree))
        for p in worktree.rglob("*")
        if p.is_file() and p.suffix in {".rej", ".orig"}
    ]
    assert not rejects, f"unexpected reject/orig files left behind: {rejects}"

    # 5b. Final file contains BOTH the refactor AND the fork addition.
    final = baseline_py.read_text(encoding="utf-8")
    # Refactor markers (proves the refactor survived).
    assert "def _existing_message" in final, (
        "post-quilt file lost the upstream refactor's helper function"
    )
    assert "upstream existing behavior (refactored)" in final
    assert "def cmd_existing(args, *, verbose=False)" in final
    # Fork addition (proves the patch landed).
    assert "def cmd_new_flag" in final, (
        "post-quilt file missing the fork's cmd_new_flag"
    )
    assert "nadia fork: --new-flag invoked" in final

    # 5c. Every pattern from asserts.txt is present in the final file.
    patterns = _load_asserts()
    assert patterns, "asserts.txt produced no patterns to check"
    missing = [pat for pat in patterns if pat not in final]
    assert not missing, (
        f"asserts.txt patterns not found in final baseline.py: {missing}\n"
        f"--- final baseline.py ---\n{final}"
    )
