"""Spec AC-8 verification gate (formal).

Two builds at the same git SHA with the same SOURCE_DATE_EPOCH MUST
produce byte-identical dist/argo/ trees. This test is the formal version
of the M5.3 acceptance check; the M5.1 inline note in AGENTS.md is the
maintainer-facing reminder.

The test is `@pytest.mark.integration` because each `make build` runs the
full pipeline (rm dist/argo, copy upstream, quilt push -a, copy overlay,
rebrand, assertions, manifest write). Two consecutive runs typically
take 30-90s on a developer laptop and could exceed 2 min on a slow CI
runner; not appropriate for the default `pytest -m 'not integration'`
gate (spec § Code Style → Tests).

The repo's pre-existing dist/ contents (if any) are snapshotted at the
start of the test and restored at the end so this test is hermetic and
re-entrant.

Maps to: spec AC-8, plan M5.3, NFR-4.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
DIST_ARGO = DIST_DIR / "argo"

# Spec AC-8: "SOURCE_DATE_EPOCH=<commit-timestamp>". The value itself is
# arbitrary as long as both builds use the same one. Picked a stable
# round number unrelated to wall-clock so the test is reproducible
# across machines / branches.
DETERMINISM_EPOCH = "1700000000"


def _have(cmd: str) -> bool:
    """Return True iff ``cmd`` is on $PATH."""
    return shutil.which(cmd) is not None


def _hash_tree(root: Path) -> str:
    """Hash a directory tree as `sha256( sorted "<sha256>  <relpath>\\n" lines )`.

    File-content-only — does not include mtime, owner, or mode bits.
    Spec AC-8 defines determinism as "the dist/argo/ directory tree is
    bit-identical", which we operationalize as identical file contents
    at identical relative paths. Mode preservation is a SEPARATE gate
    (M2.3); we do not entangle it here.
    """
    lines: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        lines.append(f"{h.hexdigest()}  {rel}")
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _run_build(epoch: str | None) -> None:
    """Run ``make clean && make build``, optionally with SOURCE_DATE_EPOCH set.

    Runs from REPO_ROOT, surfaces stdout/stderr to the test log on failure.
    """
    env = os.environ.copy()
    if epoch is not None:
        env["SOURCE_DATE_EPOCH"] = epoch
    else:
        env.pop("SOURCE_DATE_EPOCH", None)

    # `make clean` removes any pre-existing dist/. We invoke it explicitly
    # to make the test independent of whatever state the developer's
    # workspace is in.
    subprocess.run(
        ["make", "clean"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["make", "build"],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        # Surface the build log so the test failure is debuggable.
        raise AssertionError(
            "make build failed (exit %d)\n--- stdout ---\n%s\n--- stderr ---\n%s"
            % (
                result.returncode,
                result.stdout.decode("utf-8", "replace"),
                result.stderr.decode("utf-8", "replace"),
            )
        )


@pytest.fixture
def preserved_dist(tmp_path: Path):
    """Snapshot dist/ before the test; restore it after.

    AC-8's two builds clobber dist/argo/. Without this fixture, running
    the test would silently destroy whatever the developer had in dist/
    from a prior `make build`. With it, we move dist/ aside, run the
    test, then move it back. If dist/ doesn't exist (clean workspace),
    we simply ensure dist/ doesn't exist at the end.
    """
    backup = tmp_path / "dist-backup"
    had_dist = DIST_DIR.exists()
    if had_dist:
        shutil.move(str(DIST_DIR), str(backup))
    try:
        yield
    finally:
        # Remove whatever the test left behind, then restore.
        if DIST_DIR.exists():
            shutil.rmtree(DIST_DIR)
        if had_dist:
            shutil.move(str(backup), str(DIST_DIR))


@pytest.mark.integration
def test_dist_argo_bit_identical_across_two_builds_with_sde(preserved_dist):
    """Spec AC-8 verification gate.

    Two builds at the same git SHA with the same SOURCE_DATE_EPOCH MUST
    produce byte-identical dist/argo/ trees.
    """
    # Skip gracefully if the build pipeline's host requirements aren't
    # met — the test is moot on a runner that can't build at all.
    if not _have("make"):
        pytest.skip("make not on PATH; AC-8 determinism check skipped")
    if not _have("quilt"):
        pytest.skip("quilt not on PATH; AC-8 determinism check skipped")

    # Build #1 — record tree hash.
    _run_build(epoch=DETERMINISM_EPOCH)
    assert DIST_ARGO.exists(), "first make build did not produce dist/argo/"
    h1 = _hash_tree(DIST_ARGO)

    # Build #2 — same epoch, same SHA. Hash MUST match.
    _run_build(epoch=DETERMINISM_EPOCH)
    assert DIST_ARGO.exists(), "second make build did not produce dist/argo/"
    h2 = _hash_tree(DIST_ARGO)

    assert h1 == h2, (
        f"AC-8 violated: dist/argo/ differs across two builds at the same SHA "
        f"with SOURCE_DATE_EPOCH={DETERMINISM_EPOCH}.\n"
        f"  build1 tree-hash: {h1}\n"
        f"  build2 tree-hash: {h2}\n"
        f"Determinism regressions usually mean a tool is reading wall-clock time, "
        f"a uuid generator, or os.urandom; check tools/build.py and tools/rebrand.py."
    )

    # Best-effort sanity: a third build WITHOUT SOURCE_DATE_EPOCH.
    # Per spec AC-8 the determinism gate is conditional on
    # SOURCE_DATE_EPOCH being set; running unset is allowed to diverge
    # (e.g., if a tool legitimately stamps wall-clock when no SDE is set).
    # We DO expect it to match h1 in the current implementation — the
    # build manifest uses datetime.now(UTC) which DOES vary across runs.
    # Therefore we record this third hash but do NOT assert equality;
    # we surface a soft-warning via the pytest log if it differs, which
    # is the documented "best-effort" behavior in the task spec.
    _run_build(epoch=None)
    h3 = _hash_tree(DIST_ARGO)
    if h3 != h1:
        # Soft signal: print to capture-stdout for visibility in -v runs.
        # This is informational; build-manifest.json's `ran_at` field is
        # known to vary without SOURCE_DATE_EPOCH.
        print(
            f"\n[AC-8 soft-note] dist/argo/ tree-hash without SOURCE_DATE_EPOCH "
            f"({h3}) differs from epoch-locked hash ({h1}). Expected — "
            f"manifest's ran_at is wall-clock when SDE is unset."
        )
