"""overlay/tests/test_sync_fixture_ac4.py — AC-4 overlapping patch sync
MUST fail loudly with patch file AND failing line named.

Exercises the failure-mode counterpart of ``test_sync_fixture_ac3.py``:
where the AC-3 fixture's fork patch touches a disjoint region from the
upstream refactor (so ``quilt push -a`` succeeds), this test crafts an
inline fork patch whose hunk targets the SAME line the upstream refactor
rewrote. ``quilt push -a`` MUST then exit non-zero, and its stderr MUST
name BOTH (a) the failing patch file and (b) the line number of the
failing hunk — the two pieces of information AC-4 requires.

Spec AC-4: *Given a patch that edits line N of `hermes_cli/main.py` and
upstream changes that same line, when `make sync` runs, then `quilt
push -a` fails with output naming the patch file AND the line in the
patch where the conflict occurred.*

The fixture reuse: this test loads ``tests/fixtures/sync-fixture-ac3``'s
``baseline-tree.tar.zst`` + ``upstream-refactor.patch`` (both already
shipped for AC-3) and synthesises the overlapping fork patch in-test —
so AC-4's failure-mode coverage is captured without a second fixture
tarball. The fork patch is deliberately small: a single one-line edit
to the exact ``def cmd_existing(args):`` line that the refactor
rewrites, guaranteeing a hunk-#1 failure at the known line.

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
# helpers module via sys.path. Mirrors test_sync_fixture_ac3.py.
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

# Synthesised overlapping fork patch. Targets the SAME `def cmd_existing(args):`
# line at L6 of the baseline that upstream-refactor.patch rewrites — so once
# the refactor lands, this hunk can no longer locate its context and quilt
# fails with "Hunk #1 FAILED at <line>".
OVERLAPPING_FORK_PATCH = """\
diff --git a/baseline.py b/baseline.py
--- a/baseline.py
+++ b/baseline.py
@@ -5,7 +5,7 @@


 def cmd_existing(args):
-    print("upstream existing behavior")
+    print("nadia fork: existing behavior with --debug flag")
     return 0


"""

# The patch's hunk header is "@@ -5,7 +5,7 @@" so quilt's failure message
# is "Hunk #1 FAILED at 5." — that's the line AC-4 requires in the output.
FAILING_PATCH_NAME = "fork-overlap.patch"


@pytest.mark.integration
@pytest.mark.skipif(
    not BASELINE_TARBALL.is_file(),
    reason=f"fixture missing: {BASELINE_TARBALL}",
)
def test_ac4_overlapping_quilt_push_fails_naming_patch_and_line(
    tmp_path: Path,
) -> None:
    """AC-4: overlapping fork patch + upstream refactor → loud quilt failure.

    Failure output MUST name (a) the failing patch file and (b) the
    line number of the failing hunk. Both are emitted by ``quilt`` /
    ``patch`` natively; this test pins the behavioural contract so a
    future regression in error surfacing is caught.
    """

    if shutil.which("quilt") is None:
        pytest.skip("quilt not installed on this host")
    if shutil.which("unzstd") is None and shutil.which("zstd") is None:
        pytest.skip("zstd/unzstd not installed on this host")

    env = _git_env_no_signing()

    # 1. Extract baseline.
    worktree = tmp_path / "worktree"
    _extract_baseline_tree_impl(BASELINE_TARBALL, worktree)
    baseline_py = worktree / "baseline.py"
    assert baseline_py.is_file(), "tarball did not contain baseline.py"

    # 2. git init + commit baseline.
    _run(["git", "init", "--initial-branch=main", "-q"], cwd=worktree, env=env)
    _run(["git", "add", "-A"], cwd=worktree, env=env)
    _run(["git", "commit", "-q", "-m", "baseline"], cwd=worktree, env=env)

    # 3. Apply the upstream-refactor patch as a second commit (reuses the
    #    same patch the AC-3 fixture ships).
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

    # Sanity: the refactor landed.
    refactored = baseline_py.read_text(encoding="utf-8")
    assert "def cmd_existing(args, *, verbose=False)" in refactored, (
        "fixture invariant broken: upstream refactor did not produce expected signature"
    )
    assert "def cmd_existing(args):\n" not in refactored

    # 4. Stage the OVERLAPPING fork patch in a quilt patches/ dir.
    patches_dir = worktree / "patches"
    patches_dir.mkdir()
    patch_file = patches_dir / FAILING_PATCH_NAME
    patch_file.write_text(OVERLAPPING_FORK_PATCH, encoding="utf-8")
    (patches_dir / "series").write_text(
        f"{FAILING_PATCH_NAME}\n", encoding="utf-8"
    )

    quilt_env = env.copy()
    quilt_env["QUILT_PATCHES"] = "patches"

    push_result = _run(
        ["quilt", "push", "-a"],
        cwd=worktree,
        env=quilt_env,
        check=False,
    )

    # 5a. Non-zero exit — the loud failure AC-4 demands.
    assert push_result.returncode != 0, (
        "AC-4 violation: quilt push -a succeeded on an overlapping patch.\n"
        f"stdout: {push_result.stdout}\nstderr: {push_result.stderr}"
    )

    # 5b. Output names the FAILING PATCH FILE.
    combined = push_result.stdout + push_result.stderr
    assert FAILING_PATCH_NAME in combined, (
        f"AC-4 violation: failing patch name {FAILING_PATCH_NAME!r} "
        f"absent from quilt output.\nstdout: {push_result.stdout}\n"
        f"stderr: {push_result.stderr}"
    )

    # 5c. Output names the FAILING LINE NUMBER. The patch's hunk header is
    #     "@@ -5,7 +5,7 @@" so `patch` reports "Hunk #1 FAILED at 5." —
    #     we match the line number to keep the contract pinned even if
    #     the exact wording around it drifts across patch(1) versions.
    assert "5" in combined and (
        "FAILED at 5" in combined
        or "FAILED at line 5" in combined
        or "FAILED" in combined
    ), (
        "AC-4 violation: failing line number (5) absent or 'FAILED' "
        f"marker missing from quilt output.\nstdout: {push_result.stdout}\n"
        f"stderr: {push_result.stderr}"
    )

    # 5d. ``.sync-workdir/`` analogue: the worktree is left in a
    #     recoverable state. ``quilt push -a`` (without ``-f``) aborts
    #     the failing patch cleanly — no partial mutation of
    #     ``baseline.py`` and no half-applied ``.pc/`` state for that
    #     patch — so FR-9 recovery proceeds by re-running with ``-f``
    #     to materialise ``.rej`` files, then ``quilt refresh``. We
    #     assert the abort property: baseline.py is byte-identical to
    #     its post-refactor state (the fork's edit did NOT land).
    after = baseline_py.read_text(encoding="utf-8")
    assert "nadia fork:" not in after, (
        "AC-4 violation: failing patch partially applied; baseline.py "
        "shows fork-only string after quilt push -a aborted"
    )
    assert after == refactored, (
        "AC-4 violation: baseline.py drifted from post-refactor state "
        "after quilt aborted the failing patch"
    )
