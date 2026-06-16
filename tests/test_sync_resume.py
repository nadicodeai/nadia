"""tests/test_sync_resume.py — regression tests for the resume path.

Pins issue #3: ``tools/sync.py --resume`` invokes ``quilt push -a`` to
replay the patch series after a sync-conflict resolution. When the series
is ALREADY fully applied (which happens if the operator manually ran
``quilt push -a`` mid-resolve), quilt exits 2 with::

    File series fully applied, ends at patch ...

on stderr. That is success — every patch is on disk and the workdir is in
the post-push state we want. The pre-fix code raised
:class:`QuiltPushFailedError` on any non-zero exit, surfacing the user-
facing symptom ``[resume-patches] quilt push -a failed after resume``.

These tests exercise the helper directly and the resume flow via
``unittest.mock``, so they do NOT need a real quilt repo or a populated
``.sync-workdir/``.

Layout note
-----------

This file lives at repo-root ``tests/`` because it exercises the
build-time ``tools/sync.py`` directly; it must not ship to customers
under ``dist/nadia/tests/``. Run with::

    pytest tests/test_sync_resume.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# tools/ is not a package; extend sys.path so we can import sync directly.
sys.path.insert(0, str(REPO_ROOT / "tools"))
import sync  # noqa: E402


# ---------------------------------------------------------------------------
# _quilt_push_is_success — pure helper, no I/O.
# ---------------------------------------------------------------------------


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Build a CompletedProcess shaped like the real quilt push result."""
    return subprocess.CompletedProcess(
        args=["quilt", "push", "-a"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_exit_zero_is_success() -> None:
    """quilt exit 0 with a normal push log → success."""
    result = _completed(0, stdout="Applying patch 0001-foo.patch\n")
    assert sync._quilt_push_is_success(result) is True


def test_exit_two_with_fully_applied_marker_is_success() -> None:
    """quilt exit 2 with 'File series fully applied' on stderr → success.

    This is the issue-#3 regression: every patch is already on disk; the
    resume path MUST NOT raise.
    """
    result = _completed(
        2,
        stderr=(
            "File series fully applied, ends at patch "
            "/path/to/patches/0008-doctor-static-live-wiring.patch\n"
        ),
    )
    assert sync._quilt_push_is_success(result) is True


def test_exit_two_marker_on_stdout_is_also_success() -> None:
    """Some quilt builds put the marker on stdout instead of stderr.

    The helper concatenates both streams before scanning, so either
    location should trigger the success path.
    """
    result = _completed(
        2,
        stdout="File series fully applied, ends at patch 0008-foo.patch\n",
    )
    assert sync._quilt_push_is_success(result) is True


def test_exit_two_without_marker_is_failure() -> None:
    """quilt exit 2 with no 'File series fully applied' marker → genuine failure."""
    result = _completed(
        2,
        stderr="Patch 0005-foo.patch does not apply (enforce with -f)\n",
    )
    assert sync._quilt_push_is_success(result) is False


def test_exit_one_is_failure() -> None:
    """Any other non-zero exit (e.g. 1) is a genuine failure."""
    result = _completed(1, stderr="quilt: some other error\n")
    assert sync._quilt_push_is_success(result) is False


# ---------------------------------------------------------------------------
# run_resume — full resume flow with subprocess mocked.
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_resume_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect sync's module-level paths into tmp_path with a primed state file.

    Returns the tmp ``.sync-workdir/`` path so the test can assert on
    cleanup behavior.
    """
    workdir = tmp_path / ".sync-workdir"
    workdir.mkdir()
    state_file = workdir / ".sync-state.json"
    state_file.write_text(
        '{"phase": "patches", '
        '"failing_patch": "patches/0005-foo.patch", '
        '"upstream_sha": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef", '
        '"previous_sha": "cafebabecafebabecafebabecafebabecafebabe"}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(sync, "SYNC_WORKDIR", workdir)
    monkeypatch.setattr(sync, "SYNC_STATE_FILE", state_file)
    monkeypatch.setattr(sync, "REPO_ROOT", tmp_path)
    return workdir


def test_run_resume_treats_fully_applied_exit_2_as_success(
    fake_resume_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: resume against an already-fully-applied series exits 0.

    Pre-fix this surfaced as
    ``✗ sync failed: [resume-patches] quilt push -a failed after resume``.
    Post-fix the resume completes normally: build verification + commit
    + workdir cleanup all run, and the function returns 0.
    """
    refresh_result = _completed(0, stdout="Refreshed patch patches/0005-foo.patch\n")
    push_result = _completed(
        2,
        stderr=(
            "File series fully applied, ends at patch "
            "patches/0008-doctor-static-live-wiring.patch\n"
        ),
    )

    # Stub every subprocess-driven helper the resume path touches.
    monkeypatch.setattr(sync, "_quilt_refresh_top", lambda: refresh_result)
    monkeypatch.setattr(sync, "_quilt_push_all", lambda: push_result)
    monkeypatch.setattr(sync, "_refreshed_patches", lambda _repo: ["0005-foo.patch"])
    monkeypatch.setattr(sync, "_run_make_build", lambda _repo: None)
    commit_calls: list[tuple[str, list[str], bool]] = []

    def _fake_stage_and_commit(
        _repo: Path,
        upstream_sha: str,
        refreshed_patches: list[str],
        amend: bool,
    ) -> None:
        commit_calls.append((upstream_sha, refreshed_patches, amend))

    monkeypatch.setattr(sync, "_stage_and_commit", _fake_stage_and_commit)

    rc = sync.run_resume()

    assert rc == 0
    # Commit was attempted with the resume-flow signature (amend=False).
    assert commit_calls == [
        ("deadbeefdeadbeefdeadbeefdeadbeefdeadbeef", ["0005-foo.patch"], False)
    ]
    # Workdir was cleaned up on success — the visible signal that the
    # resume completed, instead of being left half-applied for retry.
    assert not fake_resume_state.exists()


def test_run_resume_genuine_quilt_failure_still_raises(
    fake_resume_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression-guard: a real quilt failure (exit 2 without the marker, or
    exit 1) MUST still raise :class:`QuiltPushFailedError`. The fix narrows
    the success window — it does not swallow every non-zero exit.
    """
    refresh_result = _completed(0, stdout="")
    push_result = _completed(2, stderr="Patch 0008-foo.patch does not apply\n")

    monkeypatch.setattr(sync, "_quilt_refresh_top", lambda: refresh_result)
    monkeypatch.setattr(sync, "_quilt_push_all", lambda: push_result)
    monkeypatch.setattr(sync, "_refreshed_patches", lambda _repo: [])
    monkeypatch.setattr(sync, "_quilt_top", lambda: "patches/0008-foo.patch")
    # Should never be reached on this path; assert so if it ever is.
    monkeypatch.setattr(
        sync,
        "_run_make_build",
        mock.Mock(side_effect=AssertionError("make build must not run on failure")),
    )

    with pytest.raises(sync.QuiltPushFailedError) as excinfo:
        sync.run_resume()

    assert excinfo.value.step == "resume-patches"
    # Workdir is preserved so the operator can resolve and retry.
    assert fake_resume_state.exists()


# ---------------------------------------------------------------------------
# Build-verification failure leaves a resumable state (BUG FIX).
#
# Before the fix, a BuildVerificationFailedError from _run_make_build exited
# run_default / run_resume WITHOUT writing .sync-state.json (unlike the
# quilt-push-failure branch). Result: an un-amended subtree commit + dirty
# tree + a .sync-workdir/ with no state file → `make sync-resume` died with
# ResumeStateMissingError and `make sync` died on the dirty tree. The fix
# writes a `verify-build` state record BEFORE the build call so the operator
# can fix the cause and run `make sync-resume`.
# ---------------------------------------------------------------------------


def test_run_make_build_failure_message_carries_recovery_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The BuildVerificationFailedError message points at `make sync-resume`.

    Before the fix the error gave no recovery hint at all; the operator was
    left with a dirty tree and no documented next step.
    """
    monkeypatch.setattr(
        sync, "_run", lambda *_a, **_k: _completed(1, stdout="", stderr="leak found\n")
    )
    with pytest.raises(sync.BuildVerificationFailedError) as excinfo:
        sync._run_make_build(REPO_ROOT)
    msg = str(excinfo.value)
    assert "make sync-resume" in msg
    assert "make sync-reset" in msg


@pytest.fixture
def sync_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect sync's module-level paths into tmp_path (no primed state).

    Returns the tmp ``.sync-workdir/`` path (not yet created).
    """
    workdir = tmp_path / ".sync-workdir"
    state_file = workdir / ".sync-state.json"
    monkeypatch.setattr(sync, "SYNC_WORKDIR", workdir)
    monkeypatch.setattr(sync, "SYNC_STATE_FILE", state_file)
    monkeypatch.setattr(sync, "REPO_ROOT", tmp_path)
    return workdir


def test_run_default_build_failure_writes_resumable_state_first(
    sync_paths: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_default: a build failure leaves a verify-build state on disk.

    Asserts the state file:
      * is written BEFORE _run_make_build runs (captured at raise time), and
      * carries the schema run_resume reads back (upstream_sha + previous_sha).
    """
    new_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    old_sha = "cafebabecafebabecafebabecafebabecafebabe"

    monkeypatch.setattr(sync, "_check_clean_or_die", lambda _repo: None)
    monkeypatch.setattr(sync, "_read_upstream_commit", lambda: old_sha)
    monkeypatch.setattr(sync, "_subtree_pull", lambda *_a, **_k: new_sha)
    monkeypatch.setattr(sync, "_write_upstream_commit", lambda _sha: None)
    monkeypatch.setattr(sync, "_populate_sync_workdir", lambda: None)
    monkeypatch.setattr(sync, "_read_series", lambda: ["0001-foo.patch"])
    monkeypatch.setattr(sync, "_quilt_push_all", lambda: _completed(0))
    monkeypatch.setattr(sync, "_refreshed_patches", lambda _repo: [])
    # _stage_and_commit / _clear_sync_workdir must NOT run on the failure path.
    monkeypatch.setattr(
        sync,
        "_stage_and_commit",
        mock.Mock(side_effect=AssertionError("commit must not run on build failure")),
    )
    monkeypatch.setattr(
        sync,
        "_clear_sync_workdir",
        mock.Mock(side_effect=AssertionError("workdir must NOT be cleared on failure")),
    )

    # Capture the on-disk state at the moment the build is invoked, proving the
    # write happens BEFORE the build (not after).
    state_at_build_time: dict[str, object] = {}

    def _failing_build(_repo: Path) -> None:
        st = sync._read_sync_state()
        if st is not None:
            state_at_build_time.update(st)
        raise sync.BuildVerificationFailedError("boom", step="verify-build")

    monkeypatch.setattr(sync, "_run_make_build", _failing_build)

    with pytest.raises(sync.BuildVerificationFailedError) as excinfo:
        sync.run_default("https://example/upstream", "main")

    assert excinfo.value.step == "verify-build"

    # State existed BEFORE the build ran.
    assert state_at_build_time.get("phase") == "verify-build"
    assert state_at_build_time.get("upstream_sha") == new_sha
    assert state_at_build_time.get("previous_sha") == old_sha

    # And it is still on disk after the failure — run_resume can read it.
    persisted = sync._read_sync_state()
    assert persisted is not None
    assert persisted["phase"] == "verify-build"
    assert persisted["upstream_sha"] == new_sha
    assert persisted["previous_sha"] == old_sha
    # Schema matches what run_resume requires (upstream_sha is mandatory there).
    assert set(persisted) >= {"phase", "failing_patch", "upstream_sha", "previous_sha"}


def test_run_resume_build_failure_writes_resumable_state_first(
    fake_resume_state: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_resume: a build failure re-records a verify-build state on disk.

    The state must remain readable so a *second* `make sync-resume` (after the
    operator fixes the build) can continue rather than dying with
    ResumeStateMissingError.
    """
    new_sha = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    prev_sha = "cafebabecafebabecafebabecafebabecafebabe"

    monkeypatch.setattr(sync, "_quilt_refresh_top", lambda: _completed(0))
    monkeypatch.setattr(
        sync,
        "_quilt_push_all",
        lambda: _completed(2, stderr="File series fully applied, ends at patch X\n"),
    )
    monkeypatch.setattr(sync, "_refreshed_patches", lambda _repo: [])
    monkeypatch.setattr(
        sync,
        "_stage_and_commit",
        mock.Mock(side_effect=AssertionError("commit must not run on build failure")),
    )

    state_at_build_time: dict[str, object] = {}

    def _failing_build(_repo: Path) -> None:
        st = sync._read_sync_state()
        if st is not None:
            state_at_build_time.update(st)
        raise sync.BuildVerificationFailedError("boom", step="verify-build")

    monkeypatch.setattr(sync, "_run_make_build", _failing_build)

    with pytest.raises(sync.BuildVerificationFailedError):
        sync.run_resume()

    # State existed BEFORE the build ran, with verify-build phase + preserved shas.
    assert state_at_build_time.get("phase") == "verify-build"
    assert state_at_build_time.get("upstream_sha") == new_sha
    assert state_at_build_time.get("previous_sha") == prev_sha

    # Workdir + state survive for a follow-up `make sync-resume`.
    assert fake_resume_state.exists()
    persisted = sync._read_sync_state()
    assert persisted is not None
    assert persisted["phase"] == "verify-build"
    assert persisted["upstream_sha"] == new_sha


# ---------------------------------------------------------------------------
# _refreshed_patches + _stage_and_commit — conflict-resolution patch staging.
#
# BUG FIX: quilt operates on the repo's patches/ dir directly during a sync
# (QUILT_PATCHES → patches/), so a `quilt refresh` resolving a conflict
# rewrites patches/NNNN.patch in place. The old _copy_patches_back() looked in
# a non-existent .sync-workdir/patches/, always returned [], and _stage_and_commit
# never staged the refreshed patch — so the sync commit carried the STALE patch
# while the (working-tree-driven) verification build passed deceptively. A fresh
# checkout of that commit would then fail to apply the patch.
# ---------------------------------------------------------------------------


def _git_init_repo(path: Path) -> None:
    """Initialise a throwaway git repo with deterministic identity + no hooks."""
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    for k, v in (
        ("user.email", "t@example.com"),
        ("user.name", "Test"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", "/dev/null"),  # never fire the real pre-commit gate
    ):
        subprocess.run(["git", "-C", str(path), "config", k, v], check=True)


def test_refreshed_patches_detects_modified_and_new_patch(tmp_path: Path) -> None:
    """A quilt refresh rewrites patches/ in place; detection diffs against HEAD."""
    repo = tmp_path
    _git_init_repo(repo)
    patches = repo / "patches"
    patches.mkdir()
    tracked = patches / "0005-foo.patch"
    tracked.write_text("hunk before\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)

    # Clean tree → nothing refreshed.
    assert sync._refreshed_patches(repo) == []

    # Simulate `quilt refresh`: rewrite a tracked patch in place...
    tracked.write_text("hunk AFTER conflict resolution\n", encoding="utf-8")
    # ...and a brand-new patch quilt could add (untracked).
    (patches / "0099-new.patch").write_text("new\n", encoding="utf-8")

    assert sync._refreshed_patches(repo) == ["0005-foo.patch", "0099-new.patch"]


def test_stage_and_commit_includes_refreshed_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refreshed patch MUST land in the sync commit (the core regression)."""
    repo = tmp_path
    _git_init_repo(repo)
    (repo / "upstream").mkdir()
    commit_file = repo / "upstream" / ".commit"
    commit_file.write_text("old-sha\n", encoding="utf-8")
    patches = repo / "patches"
    patches.mkdir()
    patch = patches / "0005-foo.patch"
    patch.write_text("stale hunk\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed"], check=True)

    monkeypatch.setattr(sync, "UPSTREAM_COMMIT_FILE", commit_file)
    commit_file.write_text("new-sha\n", encoding="utf-8")
    # Simulate the in-place quilt refresh of the resolved patch.
    patch.write_text("resolved hunk\n", encoding="utf-8")

    sync._stage_and_commit(repo, "newsha1234567890", ["0005-foo.patch"], amend=False)

    committed = subprocess.run(
        ["git", "-C", str(repo), "show", "HEAD:patches/0005-foo.patch"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert committed == "resolved hunk\n", "refreshed patch was not committed"
    subject = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert subject.startswith("sync: upstream "), subject
