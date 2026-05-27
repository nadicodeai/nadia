#!/usr/bin/env python3
"""tools/sync.py — upstream sync workflow (spec FR-8 / FR-9 / FR-10).

Maintainer-facing entry point invoked by `make sync` / `make sync-resume`
/ `make sync-reset`.

Pipeline (default, no flags — FR-8):

1. Verify working tree is clean (`git status --porcelain` empty).
2. Refuse if `.sync-workdir/` already carries state from a prior
   interrupted sync (`--resume` or `--reset` required).
3. `git subtree pull --prefix=upstream <upstream-url> main --squash`.
4. Update `upstream/.commit` with the new HEAD SHA.
5. Populate `.sync-workdir/` by copying `upstream/*` and apply the
   quilt series via `quilt push -a`.
6. On quilt success, run `make build` as the verification gate
   (FR-12 leakage + FR-14 assertions).
7. Stage `upstream/`, `upstream/.commit`, any refreshed patches and
   amend the subtree merge commit with
   `sync: upstream <short-sha> (<n> patches refreshed)`.

`--resume` (FR-9):
   Re-runs `quilt refresh` in `.sync-workdir/`, copies refreshed
   patches back to `patches/`, re-runs `quilt push -a`, then `make
   build`, then commits.

`--reset`:
   Wipes `.sync-workdir/` and exits.

`--upstream-url URL`:
   Overrides the default upstream URL. Required for the
   `sync-fixture-200/` integration test.

Domain errors are subclasses of :class:`SyncError`. All file I/O uses
``encoding="utf-8"``. All subprocess calls use ``text=True,
encoding="utf-8"``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_DIR = REPO_ROOT / "upstream"
UPSTREAM_COMMIT_FILE = UPSTREAM_DIR / ".commit"
PATCHES_DIR = REPO_ROOT / "patches"
SERIES_FILE = PATCHES_DIR / "series"
SYNC_WORKDIR = REPO_ROOT / ".sync-workdir"
SYNC_STATE_FILE = SYNC_WORKDIR / ".sync-state.json"

DEFAULT_UPSTREAM_URL = "https://github.com/NousResearch/hermes-agent"
DEFAULT_UPSTREAM_BRANCH = "main"


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class SyncError(RuntimeError):
    """Base class for sync-pipeline failures.

    Carries a *step* label identifying which stage failed (used by
    callers / CI to bucket errors).
    """

    def __init__(self, message: str, *, step: str = "sync") -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


class WorkingTreeDirtyError(SyncError):
    """Working tree is dirty; user must commit or stash first."""


class StaleSyncWorkdirError(SyncError):
    """`.sync-workdir/` carries unresolved state from a prior sync."""


class SubtreePullConflictError(SyncError):
    """`git subtree pull` produced merge conflicts in `upstream/`."""


class QuiltPushFailedError(SyncError):
    """`quilt push -a` failed inside `.sync-workdir/`."""


class BuildVerificationFailedError(SyncError):
    """`make build` failed during the sync verification step."""


class ResumeStateMissingError(SyncError):
    """`--resume` requested but no `.sync-workdir/` state exists."""


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    print(f"→ {msg}")


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with text/utf-8 wiring; raise on non-zero if *check*."""
    kwargs: dict[str, object] = {
        "text": True,
        "encoding": "utf-8",
        "cwd": str(cwd) if cwd else None,
    }
    if env is not None:
        kwargs["env"] = env
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    result = subprocess.run(cmd, check=False, **kwargs)  # type: ignore[call-overload]
    if check and result.returncode != 0:
        out = (result.stdout or "") if capture else ""
        err = (result.stderr or "") if capture else ""
        raise SyncError(
            f"command failed: {' '.join(cmd)}\nstdout: {out}\nstderr: {err}",
            step=cmd[0],
        )
    return result


def _git(repo: Path, *args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["git", *args], cwd=repo, capture=capture, check=check)


def _git_out(repo: Path, *args: str) -> str:
    return _git(repo, *args, capture=True, check=True).stdout.strip()


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def _write_sync_state(state: dict[str, str]) -> None:
    SYNC_WORKDIR.mkdir(parents=True, exist_ok=True)
    SYNC_STATE_FILE.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read_sync_state() -> dict[str, str] | None:
    if not SYNC_STATE_FILE.is_file():
        return None
    return json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))


def _clear_sync_workdir() -> None:
    if SYNC_WORKDIR.exists():
        shutil.rmtree(SYNC_WORKDIR)


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def _is_working_tree_clean(repo: Path) -> bool:
    """Return True if no untracked or modified files.

    `.sync-workdir/` is gitignored, so it does not affect cleanliness.
    """
    status = _git_out(repo, "status", "--porcelain")
    return status == ""


def _check_clean_or_die(repo: Path) -> None:
    if not _is_working_tree_clean(repo):
        raise WorkingTreeDirtyError(
            "working tree has uncommitted changes; commit or stash them first",
            step="preconditions",
        )


def _read_upstream_commit() -> str:
    if not UPSTREAM_COMMIT_FILE.is_file():
        raise SyncError(
            f"{UPSTREAM_COMMIT_FILE} missing; this repo has not been bootstrapped",
            step="preconditions",
        )
    return UPSTREAM_COMMIT_FILE.read_text(encoding="utf-8").strip()


def _write_upstream_commit(sha: str) -> None:
    UPSTREAM_COMMIT_FILE.write_text(sha + "\n", encoding="utf-8")


def _short_sha(sha: str, length: int = 8) -> str:
    return sha[:length]


# ---------------------------------------------------------------------------
# git subtree pull
# ---------------------------------------------------------------------------


def _subtree_pull(repo: Path, upstream_url: str, branch: str) -> str:
    """Run `git subtree pull --squash`; return the new upstream HEAD SHA.

    Raises :class:`SubtreePullConflictError` on merge conflict.
    """
    _log(f"git subtree pull --prefix=upstream {upstream_url} {branch} --squash")
    result = _git(
        repo,
        "subtree",
        "pull",
        "--prefix=upstream",
        upstream_url,
        branch,
        "--squash",
        "-m",
        f"subtree: pull from {upstream_url} {branch} --squash",
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        # Detect merge conflicts (subtree leaves the index half-merged).
        conflicting = _git(
            repo, "diff", "--name-only", "--diff-filter=U", capture=True, check=False
        ).stdout
        files = [f for f in conflicting.splitlines() if f]
        if files:
            raise SubtreePullConflictError(
                "git subtree pull produced merge conflicts in:\n"
                + "\n".join(f"  {f}" for f in files)
                + "\n\nResolve conflicts in upstream/, `git add` them, "
                "then `git commit`, then re-run `make sync`.",
                step="subtree-pull",
            )
        raise SyncError(
            f"git subtree pull failed\nstdout: {result.stdout}\nstderr: {result.stderr}",
            step="subtree-pull",
        )

    # Determine the new upstream HEAD SHA. The subtree-squash commit's
    # message contains the SHA on its first parent's "git-subtree-split:"
    # trailer, but the more direct approach is to read the upstream HEAD
    # from the remote we just pulled — but we did not register a remote.
    # Instead, parse the squash commit message: `git log -1 HEAD^2 |
    # grep git-subtree-split`.
    new_sha = _extract_subtree_sha_from_log(repo)
    return new_sha


def _extract_subtree_sha_from_log(repo: Path) -> str:
    """Read the most recent `git-subtree-split:` trailer from the log.

    `git subtree --squash` writes a squash commit whose message body
    contains `git-subtree-split: <sha>`. We walk the recent log for
    the latest such trailer.
    """
    log = _git(
        repo,
        "log",
        "-50",
        "--all",
        "--pretty=format:%H%n%B%n---END---",
        capture=True,
        check=True,
    ).stdout
    # Walk newest-first; first match wins.
    for entry in log.split("---END---"):
        for line in entry.splitlines():
            line = line.strip()
            if line.startswith("git-subtree-split:"):
                return line.split(":", 1)[1].strip()
    raise SyncError(
        "could not locate git-subtree-split trailer after subtree pull",
        step="subtree-pull",
    )


# ---------------------------------------------------------------------------
# Series + workdir
# ---------------------------------------------------------------------------


def _read_series() -> list[str]:
    if not SERIES_FILE.is_file():
        return []
    return [
        line.strip()
        for line in SERIES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _populate_sync_workdir() -> None:
    """Copy `upstream/*` to `.sync-workdir/`. Replaces existing contents."""
    _log(f"populate {SYNC_WORKDIR} from upstream/")
    if SYNC_WORKDIR.exists():
        shutil.rmtree(SYNC_WORKDIR)
    SYNC_WORKDIR.mkdir(parents=True)
    for item in UPSTREAM_DIR.iterdir():
        if item.name == ".commit":
            continue  # tracking file, not part of the source tree
        dst = SYNC_WORKDIR / item.name
        if item.is_dir():
            shutil.copytree(item, dst, symlinks=True)
        else:
            shutil.copy2(item, dst)


def _quilt_env() -> dict[str, str]:
    return {
        **os.environ,
        "QUILT_PATCHES": str(PATCHES_DIR),
        "QUILT_SERIES": "series",
    }


def _quilt_push_all() -> subprocess.CompletedProcess[str]:
    """Run `quilt push -a` in `.sync-workdir/`. Returns the CompletedProcess."""
    return _run(
        ["quilt", "push", "-a"],
        cwd=SYNC_WORKDIR,
        env=_quilt_env(),
        capture=True,
        check=False,
    )


def _quilt_push_is_success(result: subprocess.CompletedProcess[str]) -> bool:
    """Return True if a `quilt push -a` invocation should be treated as success.

    Quilt exits 0 on a normal push that applied at least one patch. It exits
    2 with the message ``File series fully applied, ends at patch ...`` on
    stderr when invoked against a series that is already fully applied
    (which happens during ``--resume`` if the operator manually ran
    ``quilt push -a`` mid-resolve). That state is success, not failure —
    every patch is on disk and the workdir is in the post-push state we
    want. Treat it accordingly.
    """
    if result.returncode == 0:
        return True
    if result.returncode == 2:
        combined = (result.stdout or "") + (result.stderr or "")
        if "File series fully applied" in combined:
            return True
    return False


def _quilt_refresh_top() -> subprocess.CompletedProcess[str]:
    return _run(
        ["quilt", "refresh"],
        cwd=SYNC_WORKDIR,
        env=_quilt_env(),
        capture=True,
        check=False,
    )


def _quilt_top() -> str:
    """Name of the currently applied (top) patch, or empty if none applied."""
    result = _run(
        ["quilt", "top"],
        cwd=SYNC_WORKDIR,
        env=_quilt_env(),
        capture=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _copy_patches_back() -> list[str]:
    """Copy any refreshed patches from `.sync-workdir/patches/` to `patches/`.

    Returns the list of patch filenames touched (relative to `patches/`).
    Quilt rewrites only the patch files it refreshes; we copy any patch
    that differs from the repo's copy.
    """
    workdir_patches = SYNC_WORKDIR / "patches"
    if not workdir_patches.is_dir():
        return []
    touched: list[str] = []
    for patch in workdir_patches.iterdir():
        if patch.name in {"series", ".quilt_patches", ".quilt_series"}:
            continue
        if not patch.is_file():
            continue
        repo_copy = PATCHES_DIR / patch.name
        if not repo_copy.is_file():
            continue
        a = patch.read_bytes()
        b = repo_copy.read_bytes()
        if a != b:
            shutil.copy2(patch, repo_copy)
            touched.append(patch.name)
    return sorted(touched)


# ---------------------------------------------------------------------------
# Build verification
# ---------------------------------------------------------------------------


def _run_make_build(repo: Path) -> None:
    _log("verification: make build")
    result = _run(["make", "build"], cwd=repo, capture=True, check=False)
    if result.returncode != 0:
        raise BuildVerificationFailedError(
            "make build failed during sync verification:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
            step="verify-build",
        )


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------


def _stage_and_commit(
    repo: Path, upstream_sha: str, refreshed_patches: list[str], amend: bool
) -> None:
    """Stage upstream/, upstream/.commit, refreshed patches; commit (or amend)."""
    _git(repo, "add", "upstream", check=False)
    _git(repo, "add", str(UPSTREAM_COMMIT_FILE.relative_to(repo)), check=False)
    for name in refreshed_patches:
        _git(repo, "add", f"patches/{name}", check=False)

    msg = (
        f"sync: upstream {_short_sha(upstream_sha)} "
        f"({len(refreshed_patches)} patches refreshed)"
    )

    if amend:
        # Replace the subtree merge commit message with our sync: format
        # while keeping all staged content (the subtree merge itself).
        #
        # Failure mode: if `git commit --amend` exits non-zero (e.g. a
        # pre-commit hook rejects), `_git` raises SyncError and the
        # subtree-merge commit on HEAD keeps its original auto-generated
        # message; the refreshed patches stay staged in the index for the
        # operator to inspect with `git status` and recover manually
        # (re-run amend, or commit fresh + `git reset --soft HEAD^`).
        _git(repo, "commit", "--amend", "-m", msg, check=True)
        _log(f"amended commit: {msg}")
        return

    # Resume / fresh commit path: check if anything to commit
    status = _git_out(repo, "status", "--porcelain")
    if not status:
        _log(f"nothing to commit (sync was a no-op at {_short_sha(upstream_sha)})")
        return
    _git(repo, "commit", "-m", msg, check=True)
    _log(f"committed: {msg}")


# ---------------------------------------------------------------------------
# Default flow (FR-8)
# ---------------------------------------------------------------------------


def run_default(upstream_url: str, branch: str) -> int:
    repo = REPO_ROOT
    _check_clean_or_die(repo)

    if SYNC_STATE_FILE.is_file():
        raise StaleSyncWorkdirError(
            f"{SYNC_STATE_FILE} exists from a prior interrupted sync.\n"
            "Run `make sync-resume` (after resolving the conflict in "
            ".sync-workdir/) or `make sync-reset` to discard.",
            step="preconditions",
        )

    old_sha = _read_upstream_commit()
    _log(f"current upstream pin: {_short_sha(old_sha)}")

    # 1. Subtree pull. Auto-commits a merge commit on success.
    new_sha = _subtree_pull(repo, upstream_url, branch)

    if new_sha == old_sha:
        _log(f"already up-to-date at {_short_sha(new_sha)}; nothing to sync")
        # subtree pull is a no-op in that case; no new commit was made.
        # Defensive: verify HEAD is unchanged.
        return 0

    _log(f"new upstream pin: {_short_sha(new_sha)}")

    # 2. Update upstream/.commit
    _write_upstream_commit(new_sha)

    # 3. Populate workdir + push patches
    _populate_sync_workdir()

    if not _read_series():
        _log("patch series is empty; skipping quilt push")
        refreshed: list[str] = []
    else:
        _log("apply patch series via quilt push -a")
        result = _quilt_push_all()
        if not _quilt_push_is_success(result):
            top = _quilt_top()
            _write_sync_state(
                {
                    "phase": "patches",
                    "failing_patch": top,
                    "upstream_sha": new_sha,
                    "previous_sha": old_sha,
                }
            )
            raise QuiltPushFailedError(
                "quilt push -a failed.\n"
                f"failing patch: {top or '(unknown)'}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}\n\n"
                "The .sync-workdir/ directory has been left in a half-applied\n"
                "state. Resolve the conflict by hand inside .sync-workdir/,\n"
                "then run `make sync-resume`. To abandon and start over,\n"
                "run `make sync-reset`.",
                step="patches",
            )
        refreshed = _copy_patches_back()

    # 4. Verification build
    _run_make_build(repo)

    # 5. Commit. Amend the subtree merge commit with the sync: message
    # so a single commit on main carries both the merge and our label.
    _stage_and_commit(repo, new_sha, refreshed, amend=True)

    # 6. Success: clear the workdir.
    _clear_sync_workdir()
    return 0


# ---------------------------------------------------------------------------
# Resume flow (FR-9)
# ---------------------------------------------------------------------------


def run_resume() -> int:
    repo = REPO_ROOT
    state = _read_sync_state()
    if state is None:
        raise ResumeStateMissingError(
            f"{SYNC_STATE_FILE} not found; nothing to resume",
            step="resume",
        )

    new_sha = state.get("upstream_sha", "")
    if not new_sha:
        raise SyncError(
            "sync state missing 'upstream_sha' field; cannot resume",
            step="resume",
        )
    failing = state.get("failing_patch", "")
    _log(f"resuming sync of upstream {_short_sha(new_sha)} (failing patch: {failing or '<unknown>'})")

    if not SYNC_WORKDIR.is_dir():
        raise ResumeStateMissingError(
            f"{SYNC_WORKDIR} not found; nothing to resume",
            step="resume",
        )

    # 1. Refresh the top (resolved) patch.
    _log("quilt refresh (regenerate the resolved patch)")
    refresh_result = _quilt_refresh_top()
    if refresh_result.returncode != 0:
        raise SyncError(
            f"quilt refresh failed\nstdout: {refresh_result.stdout}\nstderr: {refresh_result.stderr}",
            step="resume-refresh",
        )

    # 2. Copy refreshed patches back to patches/
    refreshed = _copy_patches_back()
    _log(f"refreshed patches copied back: {refreshed or '(none changed)'}")

    # 3. Re-run quilt push -a to confirm the remainder applies.
    #    Quilt exits 2 with "File series fully applied" on stderr when the
    #    operator manually pushed the series mid-resolve; that is success.
    _log("re-run quilt push -a to confirm the rest of the series applies")
    push_result = _quilt_push_all()
    if not _quilt_push_is_success(push_result):
        top = _quilt_top()
        _write_sync_state(
            {
                "phase": "patches",
                "failing_patch": top,
                "upstream_sha": new_sha,
                "previous_sha": state.get("previous_sha", ""),
            }
        )
        raise QuiltPushFailedError(
            "quilt push -a failed after resume; another patch needs resolution.\n"
            f"failing patch: {top or '(unknown)'}\n"
            f"stdout: {push_result.stdout}\nstderr: {push_result.stderr}\n\n"
            "Resolve in .sync-workdir/, then run `make sync-resume` again.",
            step="resume-patches",
        )

    # 4. Verification build
    _run_make_build(repo)

    # 5. Commit. On resume the subtree merge commit already exists; we
    # are now adding the refreshed patches and possibly tweaking
    # upstream/.commit. Make a regular commit if anything is staged.
    _stage_and_commit(repo, new_sha, refreshed, amend=False)

    # 6. Success: clear the workdir.
    _clear_sync_workdir()
    return 0


# ---------------------------------------------------------------------------
# Reset flow
# ---------------------------------------------------------------------------


def run_reset() -> int:
    if SYNC_WORKDIR.exists():
        _log(f"wipe {SYNC_WORKDIR}")
        shutil.rmtree(SYNC_WORKDIR)
    else:
        _log(f"{SYNC_WORKDIR} does not exist; nothing to do")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tools/sync.py",
        description=(
            "Upstream sync workflow (spec FR-8/FR-9). Pulls the hermes-agent "
            "subtree, re-applies the quilt patch series in .sync-workdir/, "
            "runs `make build` as verification, and commits."
        ),
    )
    p.add_argument(
        "--upstream-url",
        default=os.environ.get("ARGO_SYNC_UPSTREAM_URL", DEFAULT_UPSTREAM_URL),
        metavar="URL",
        help=(
            "Upstream repository URL "
            f"(default: {DEFAULT_UPSTREAM_URL}; "
            "or env ARGO_SYNC_UPSTREAM_URL)."
        ),
    )
    p.add_argument(
        "--upstream-branch",
        default=DEFAULT_UPSTREAM_BRANCH,
        metavar="BRANCH",
        help=f"Upstream branch to pull (default: {DEFAULT_UPSTREAM_BRANCH}).",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume a half-applied sync after manual conflict resolution.",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Wipe .sync-workdir/ and exit.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.resume and args.reset:
        print("✗ --resume and --reset are mutually exclusive", file=sys.stderr)
        return 2

    try:
        if args.reset:
            return run_reset()
        if args.resume:
            return run_resume()
        return run_default(args.upstream_url, args.upstream_branch)
    except SyncError as exc:
        print(f"✗ sync failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
