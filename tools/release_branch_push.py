#!/usr/bin/env python3
"""tools/release_branch_push.py — force-push dist/argo/ to origin/release.

Invoked by ``.github/workflows/release.yml`` after a successful
``make build`` + ``make leakage-static`` gate. Closes the IU-FR-3 /
IU-AC-3 storefront-branch contract: the long-lived ``release`` branch on
``nadicodeai/argo`` carries the renamed ``dist/argo/`` tree only — no
patches/, no .shepherd/, no rename engine source.

Architecture (.shepherd/install-update/standards.md § Architecture):

- ``main`` = workshop. ``release`` = storefront.
- ``dist/argo/`` is gitignored on ``main``; force-pushing to ``release``
  is the only way the renamed tree reaches a tracked git ref.
- Force-push uses ``--force-with-lease``, never ``--force``.
- Commit author identity is set via ``git -c user.email=... -c
  user.name=...`` flags on the commit command; the script NEVER writes
  ``git config --global`` anything (mirrors the bootstrap script's
  refusal to mutate the operator's env).

Companion script: ``tools/bootstrap_release_branch.sh`` (M2.2) is the
one-shot seeder for the same branch; this Python entrypoint is the
recurring CI-driven push that supersedes it on every release.

Usage::

    python tools/release_branch_push.py \\
        --dist-root dist/argo \\
        --remote-url https://github.com/nadicodeai/argo.git \\
        --branch release \\
        --source-sha "$(git rev-parse HEAD)" \\
        [--dry-run]

Exit codes
----------
- 0: pushed (or dry-run staged) successfully.
- 1: domain failure (preconditions, scratch setup, git, push).
- 2: argparse usage error (handled by argparse).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_PARENT = REPO_ROOT / ".sync-workdir" / "release-push"

# Bot identity used for the orphan-branch commit. Mirrors the
# bootstrap script's "no global config writes" rule by injecting the
# identity via per-invocation ``git -c`` flags rather than ``git config``.
COMMIT_AUTHOR_EMAIL = "release-bot@nadicodeai"
COMMIT_AUTHOR_NAME = "argo-release-bot"


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class ReleasePushError(RuntimeError):
    """Base class for release-push pipeline failures.

    Carries a ``step`` label identifying which stage failed (used by CI
    log scrapers and callers to bucket errors).
    """

    def __init__(self, message: str, *, step: str = "release-push") -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


class DistRootMissingError(ReleasePushError):
    """``--dist-root`` does not exist, is empty, or does not look like a
    renamed argo tree."""


class ScratchSetupError(ReleasePushError):
    """Could not prepare the scratch dir under ``.sync-workdir/``."""


class GitCommandError(ReleasePushError):
    """A ``git`` invocation failed inside the scratch dir."""


class PushFailedError(ReleasePushError):
    """The final ``git push --force-with-lease`` failed."""


# ---------------------------------------------------------------------------
# Subprocess wiring
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    print(f"→ {msg}")


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    capture: bool = True,
    check: bool = True,
    step: str = "git",
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess; raise :class:`ReleasePushError` on non-zero if *check*.

    All subprocesses are text/utf-8. Output is captured by default so the
    caller decides what to surface.
    """
    kwargs: dict[str, object] = {
        "text": True,
        "encoding": "utf-8",
        "cwd": str(cwd) if cwd else None,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    result = subprocess.run(cmd, check=False, **kwargs)  # type: ignore[call-overload]
    if check and result.returncode != 0:
        out = (result.stdout or "") if capture else ""
        err = (result.stderr or "") if capture else ""
        raise GitCommandError(
            f"command failed: {' '.join(cmd)}\nstdout: {out}\nstderr: {err}",
            step=step,
        )
    return result


# ---------------------------------------------------------------------------
# Pre-flight: dist-root sanity
# ---------------------------------------------------------------------------


def _verify_dist_root(dist_root: Path) -> None:
    """Refuse to push unless ``dist_root`` looks like a renamed argo tree.

    The sentinel marker is ``argo_cli/main.py`` — the rename engine
    produces it from upstream's ``hermes_cli/main.py``. Its absence
    means either the build did not run or the rename engine did not
    fire; either way the push would ship a broken tree.
    """
    if not dist_root.exists():
        raise DistRootMissingError(
            f"--dist-root does not exist: {dist_root}",
            step="preconditions",
        )
    if not dist_root.is_dir():
        raise DistRootMissingError(
            f"--dist-root is not a directory: {dist_root}",
            step="preconditions",
        )
    # `iterdir` is cheap and short-circuits on first entry; a truly empty
    # dist_root would force-push an empty release tree which is a P0
    # mistake.
    if not any(dist_root.iterdir()):
        raise DistRootMissingError(
            f"--dist-root is empty: {dist_root}",
            step="preconditions",
        )
    sentinel = dist_root / "argo_cli" / "main.py"
    if not sentinel.is_file():
        raise DistRootMissingError(
            f"--dist-root does not look like a renamed argo tree "
            f"(missing sentinel {sentinel.relative_to(dist_root)}); "
            "did `make build` run?",
            step="preconditions",
        )


# ---------------------------------------------------------------------------
# Scratch dir setup
# ---------------------------------------------------------------------------


def _prepare_scratch(dist_root: Path) -> Path:
    """Wipe and recreate ``.sync-workdir/release-push/`` with dist_root contents.

    Uses ``shutil.copytree`` to mirror ``cp -a <dist>/. <scratch>/``:
    the renamed tree becomes the scratch repo's root (NOT nested under
    a ``dist/argo/`` subdir).
    """
    scratch = SCRATCH_PARENT / "repo"
    if SCRATCH_PARENT.exists():
        _log(f"scratch: removing existing {SCRATCH_PARENT}")
        try:
            shutil.rmtree(SCRATCH_PARENT)
        except OSError as exc:
            raise ScratchSetupError(
                f"could not remove existing scratch dir {SCRATCH_PARENT}: {exc}",
                step="scratch",
            ) from exc

    try:
        scratch.mkdir(parents=True)
    except OSError as exc:
        raise ScratchSetupError(
            f"could not create scratch dir {scratch}: {exc}",
            step="scratch",
        ) from exc

    _log(f"scratch: copying {dist_root} → {scratch}")
    try:
        # symlinks=True preserves any symlinks the rename engine produced
        # (e.g. binaries). dirs_exist_ok handles the just-made parent.
        shutil.copytree(dist_root, scratch, symlinks=True, dirs_exist_ok=True)
    except OSError as exc:
        raise ScratchSetupError(
            f"could not copy {dist_root} into {scratch}: {exc}",
            step="scratch",
        ) from exc
    return scratch


# ---------------------------------------------------------------------------
# Git: init + orphan branch + commit
# ---------------------------------------------------------------------------


def _init_orphan_branch(scratch: Path, branch: str, source_sha: str) -> str:
    """Initialise ``scratch`` as a git repo on orphan ``branch``; commit
    everything; return the resulting commit SHA.

    Identity is injected via ``git -c user.email=... -c user.name=...``
    flags so we never mutate the operator's global config.
    """
    _log(f"git init -q in {scratch}")
    _run(["git", "init", "-q"], cwd=scratch, step="git-init")

    _log(f"git checkout --orphan {branch}")
    _run(
        ["git", "checkout", "--orphan", branch, "-q"],
        cwd=scratch,
        step="git-checkout",
    )

    _log("git add -A")
    _run(["git", "add", "-A"], cwd=scratch, step="git-add")

    msg = f"release: build from main@{source_sha}"
    _log(f"git commit -m {msg!r}")
    _run(
        [
            "git",
            "-c",
            f"user.email={COMMIT_AUTHOR_EMAIL}",
            "-c",
            f"user.name={COMMIT_AUTHOR_NAME}",
            "commit",
            "-q",
            "-m",
            msg,
        ],
        cwd=scratch,
        step="git-commit",
    )

    sha = _run(
        ["git", "rev-parse", "HEAD"],
        cwd=scratch,
        step="git-rev-parse",
    ).stdout.strip()
    return sha


# ---------------------------------------------------------------------------
# Push
# ---------------------------------------------------------------------------


def _push_or_describe(
    scratch: Path,
    remote_url: str,
    branch: str,
    *,
    dry_run: bool,
) -> None:
    """Force-with-lease push the scratch's orphan branch to remote_url.

    On ``--dry-run``: prints the planned command and returns; never
    contacts the remote.
    """
    push_cmd = [
        "git",
        "push",
        "--force-with-lease",
        remote_url,
        f"{branch}:{branch}",
    ]
    # Planned-form string for the dry-run log: a copy-pasteable
    # invocation that includes the cwd via `git -C`. We splice the
    # `-C <scratch>` flag in after the `git` token rather than
    # prepending the full argv (which would duplicate `git`).
    planned = " ".join(["git", "-C", str(scratch), *push_cmd[1:]])
    if dry_run:
        _log("[DRY RUN] skipping push")
        print(f"planned: {planned}")
        return

    _log(f"push: {remote_url} ({branch}:{branch}) with --force-with-lease")
    # Capture both streams so a non-zero exit surfaces useful diagnostics
    # in CI logs.
    result = subprocess.run(
        push_cmd,
        cwd=str(scratch),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise PushFailedError(
            f"git push --force-with-lease failed (exit {result.returncode})\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
            step="push",
        )
    # Surface remote messages (e.g. forced-update markers) for log grep.
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(
    *,
    dist_root: Path,
    remote_url: str,
    branch: str,
    source_sha: str,
    dry_run: bool,
) -> int:
    _verify_dist_root(dist_root)
    scratch = _prepare_scratch(dist_root)
    commit_sha = _init_orphan_branch(scratch, branch, source_sha)
    _push_or_describe(scratch, remote_url, branch, dry_run=dry_run)
    # Always print the SHA — both real push and dry-run paths want it
    # for CI logs and operator inspection.
    print(f"scratch commit: {commit_sha}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tools/release_branch_push.py",
        description=(
            "Force-push the renamed dist/argo/ tree to the release branch "
            "on the workshop's remote (IU-FR-3 / IU-AC-3). Uses "
            "--force-with-lease and per-invocation `git -c user.*` flags "
            "so it never mutates the operator's global git config."
        ),
    )
    p.add_argument(
        "--dist-root",
        default="dist/argo",
        metavar="PATH",
        help="Path to the built, renamed argo tree (default: dist/argo).",
    )
    p.add_argument(
        "--remote-url",
        required=True,
        metavar="URL",
        help=(
            "Git remote URL to push to "
            "(e.g. https://x-access-token:TOKEN@github.com/nadicodeai/argo.git)."
        ),
    )
    p.add_argument(
        "--branch",
        default="release",
        metavar="NAME",
        help="Target branch name on the remote (default: release).",
    )
    p.add_argument(
        "--source-sha",
        required=True,
        metavar="SHA",
        help=(
            "Workshop main SHA that produced this build; embedded in the "
            "scratch commit message."
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Build + stage the scratch dir; print the planned push command; skip the push.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    dist_root = Path(args.dist_root).resolve()
    try:
        return run(
            dist_root=dist_root,
            remote_url=args.remote_url,
            branch=args.branch,
            source_sha=args.source_sha,
            dry_run=args.dry_run,
        )
    except ReleasePushError as exc:
        print(f"✗ release-push failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
