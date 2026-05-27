"""overlay/tests/test_sync_resume.py — regression tests for the resume path.

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

``overlay/tests/`` is excluded from ``pytest.ini``'s ``testpaths`` because
most files there reference ``argo_*`` identifiers that only exist post-
rename in ``dist/argo/tests/``. This file exercises the pre-rename
``tools/sync.py`` directly and is safe to invoke explicitly with::

    pytest overlay/tests/test_sync_resume.py -v
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# tools/ is not a package; extend sys.path so we can import sync directly
# (same pattern as tests/test_parity_runner.py).
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
    monkeypatch.setattr(sync, "_copy_patches_back", lambda: ["0005-foo.patch"])
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
    monkeypatch.setattr(sync, "_copy_patches_back", lambda: [])
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
