#!/usr/bin/env python3
"""tools/check_upstream_pristine.py — FR-15 upstream-pristine CI gate.

Verifies that the working tree's ``upstream/`` directory matches the
git tree of the most recent commit that touched ``upstream/`` (i.e.
the last ``make sync`` commit, or the bootstrap commit). Any drift —
either an uncommitted edit in the working tree or a feature-branch
commit that touches ``upstream/`` outside the sync automation — fails
the gate.

Background
----------

Upstream's SHA (recorded in ``upstream/.commit``) is NOT a ref in our
repo: ``git subtree --squash`` brings in the tree as a squashed commit
but does NOT preserve upstream's commit objects in our object DB. So we
cannot resolve that SHA locally. The strategy here (per ``.shepherd/
plan.md`` Task M4.1 strategy A — "Sync-commit anchored diff") is to find
the most recent commit on the current branch whose touched paths include
something under ``upstream/`` and diff the working tree against it.

Equivalent CLI:

.. code-block:: bash

   LAST_SYNC_SHA=$(git log -1 --format=%H -- upstream/)
   git diff --quiet "$LAST_SYNC_SHA" HEAD -- upstream/
   git diff --quiet HEAD -- upstream/                       # uncommitted

Exit codes
----------

- 0: ``upstream/`` is pristine relative to the last sync/bootstrap commit
  AND the working tree has no uncommitted edits under ``upstream/``.
- 1: drift detected; offending paths printed to stderr.
- 2: structural / usage error (e.g. not a git repo, ``upstream/`` missing,
  ``upstream/.commit`` missing, no commit ever touched ``upstream/``, or
  ``upstream/.commit`` exists but ``upstream/`` is otherwise empty).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


class UpstreamPristineError(RuntimeError):
    """Structural failure (exit 2) — repo is not in a state we can check."""

    def __init__(self, message: str, *, step: str) -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


def _run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run ``git`` with ``args`` in ``cwd``. Never raises on non-zero exit."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _git_or_raise(
    args: list[str], *, cwd: Path, step: str, what: str
) -> subprocess.CompletedProcess[str]:
    """Run ``git`` and raise :class:`UpstreamPristineError` on non-zero exit.

    *what* is a short description of the operation used in the error
    message (e.g. ``"git log"``); *step* is the label propagated to the
    typed error for CI bucketing.
    """
    result = _run_git(args, cwd=cwd)
    if result.returncode != 0:
        raise UpstreamPristineError(
            f"{what} failed: {result.stderr.strip()}",
            step=step,
        )
    return result


def _verify_repo_structure(repo_root: Path) -> None:
    """Defensive checks: repo exists, ``upstream/`` exists and is non-trivial."""
    if not (repo_root / ".git").exists():
        raise UpstreamPristineError(
            f"{repo_root} is not a git repository (no .git entry)",
            step="repo-check",
        )
    upstream_dir = repo_root / "upstream"
    if not upstream_dir.is_dir():
        raise UpstreamPristineError(
            f"{upstream_dir} does not exist or is not a directory",
            step="upstream-dir",
        )
    commit_file = upstream_dir / ".commit"
    if not commit_file.is_file():
        raise UpstreamPristineError(
            f"{commit_file} is missing — bootstrap incomplete?",
            step="commit-file",
        )
    # Defensive: if .commit exists but upstream/ has nothing else, the subtree
    # bootstrap is incomplete and the pristine gate has no signal to compute.
    other_entries = [p for p in upstream_dir.iterdir() if p.name != ".commit"]
    if not other_entries:
        raise UpstreamPristineError(
            f"{upstream_dir} contains only .commit — bootstrap incomplete?",
            step="upstream-empty",
        )


def _last_sync_sha(repo_root: Path) -> str:
    """Return SHA of the most recent commit that touched ``upstream/``."""
    result = _git_or_raise(
        ["log", "-1", "--format=%H", "--", "upstream/"],
        cwd=repo_root,
        step="last-sync-sha",
        what="git log",
    )
    sha = result.stdout.strip()
    if not sha:
        raise UpstreamPristineError(
            "no commit on the current branch has ever touched upstream/ — "
            "bootstrap missing?",
            step="last-sync-sha",
        )
    return sha


def _committed_drift(repo_root: Path, last_sync_sha: str) -> list[str]:
    """Return paths under ``upstream/`` that differ between HEAD and last sync."""
    result = _git_or_raise(
        ["diff", "--name-only", last_sync_sha, "HEAD", "--", "upstream/"],
        cwd=repo_root,
        step="committed-diff",
        what="git diff",
    )
    return [line for line in result.stdout.splitlines() if line]


def _uncommitted_drift(repo_root: Path) -> list[str]:
    """Return paths under ``upstream/`` that differ between HEAD and worktree."""
    # Tracked changes (modifications, deletions).
    tracked = _git_or_raise(
        ["diff", "--name-only", "HEAD", "--", "upstream/"],
        cwd=repo_root,
        step="worktree-diff",
        what="git diff (worktree)",
    )
    # Untracked files inside upstream/.
    untracked = _git_or_raise(
        ["ls-files", "--others", "--exclude-standard", "--", "upstream/"],
        cwd=repo_root,
        step="untracked-scan",
        what="git ls-files",
    )
    paths: list[str] = []
    paths.extend(line for line in tracked.stdout.splitlines() if line)
    paths.extend(line for line in untracked.stdout.splitlines() if line)
    return paths


def check_upstream_pristine(repo_root: Path) -> tuple[bool, list[str], str]:
    """Run the gate. Returns ``(is_pristine, drifted_paths, last_sync_sha)``."""
    _verify_repo_structure(repo_root)
    last_sync_sha = _last_sync_sha(repo_root)
    committed = _committed_drift(repo_root, last_sync_sha)
    uncommitted = _uncommitted_drift(repo_root)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    drifted: list[str] = []
    for path in [*committed, *uncommitted]:
        if path not in seen:
            seen.add(path)
            drifted.append(path)
    return (not drifted, drifted, last_sync_sha)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify upstream/ matches the last make-sync (or bootstrap) "
            "commit. Exits 0 on clean, 1 on drift, 2 on structural errors."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="Repo root (default: parent of this script's tools/ dir).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress the human-readable success summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root: Path = args.repo_root
    try:
        is_pristine, drifted, last_sync_sha = check_upstream_pristine(repo_root)
    except UpstreamPristineError as exc:
        print(f"check_upstream_pristine: {exc}", file=sys.stderr)
        return 2
    if not is_pristine:
        print(
            "check_upstream_pristine: drift detected — upstream/ edited "
            f"outside `make sync`/`make bootstrap` (last sync commit "
            f"{last_sync_sha[:12]}). Drifted paths:",
            file=sys.stderr,
        )
        for path in drifted:
            print(f"  {path}", file=sys.stderr)
        return 1
    if not args.quiet:
        short = last_sync_sha[:12]
        print(f"upstream pristine: HEAD == sync-commit {short}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
