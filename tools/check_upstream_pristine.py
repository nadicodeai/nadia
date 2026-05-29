#!/usr/bin/env python3
"""tools/check_upstream_pristine.py — FR-15 upstream-pristine CI gate.

Verifies that the working tree's ``upstream/`` directory matches the
git tree as of the most recent commit produced by the *sync automation*
(``make sync``) or by the subtree bootstrap. Any drift — either an
uncommitted edit in the working tree, or a feature-branch/PR commit that
touches ``upstream/`` outside the sync automation — fails the gate.

Background
----------

Upstream's SHA (recorded in ``upstream/.commit``) is NOT a ref in our
repo: ``git subtree --squash`` brings in the tree as a squashed commit
but does NOT preserve upstream's commit objects in our object DB. So we
cannot resolve that SHA locally. The strategy (per ``.shepherd/plan.md``
Task M4.1 strategy A — "Sync-commit anchored diff") is to anchor a diff
to the last *sync* commit and diff ``upstream/`` against ``HEAD``.

Anchoring correctly matters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The naive anchor — "the most recent commit that *touched* ``upstream/``"
(``git log -1 -- upstream/``) — is broken: the range
``last_touch..HEAD -- upstream/`` is *always empty* for committed edits,
because any commit that edits ``upstream/`` *becomes* ``last_touch``. A
feature-branch / PR / malicious committed edit to ``upstream/`` would
therefore sail through the gate, and only uncommitted working-tree drift
would ever be caught.

Instead we anchor to the most recent commit whose *subject* matches the
sync/bootstrap convention emitted by ``tools/sync.py`` and
``tools/bootstrap_release_branch.sh`` (see :data:`_SYNC_SUBJECT_PATTERNS`)
and diff ``anchor..HEAD -- upstream/``. Any commit that touched
``upstream/`` *after* the last real sync is then flagged as drift. If no
sync-convention commit exists on the current history (e.g. an unusual
fork point), we fall back to the merge-base with ``origin/main`` and then
to the root commit, so that *some* committed ``upstream/`` edit since the
fork is always detected rather than silently passing.

Equivalent CLI:

.. code-block:: bash

   ANCHOR=$(git log -1 --extended-regexp \
              --grep='^sync: ' --grep='^subtree: ' \
              --grep='bootstrap upstream subtree' \
              --grep="^Merge commit .* as 'upstream'" --format=%H)
   git diff --quiet "$ANCHOR" HEAD -- upstream/   # committed drift
   git diff --quiet HEAD -- upstream/             # uncommitted drift

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

# Subjects emitted by the sync/bootstrap automation, used to anchor the
# committed-drift diff. These are extended-regexp patterns matched against
# the commit *subject* (``%s``):
#
#   ``^sync: ``                         tools/sync.py _stage_and_commit()
#   ``^subtree: ``                      tools/sync.py _subtree_pull()
#   ``bootstrap upstream subtree``      the M1.x subtree bootstrap commit
#   ``^Merge commit .* as 'upstream'``  the raw `git subtree` merge commit
#
# The patterns are deliberately specific (note the trailing space after the
# ``sync:``/``subtree:`` prefixes, and ``bootstrap upstream subtree`` rather
# than a bare ``bootstrap``) so an unrelated feature commit — e.g.
# ``feat(M2.2): tools/bootstrap_release_branch.sh`` — is NOT mistaken for a
# sync anchor.
_SYNC_SUBJECT_PATTERNS: tuple[str, ...] = (
    "^sync: ",
    "^subtree: ",
    "bootstrap upstream subtree",
    "^Merge commit .* as 'upstream'",
)


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


def _assert_upstream_tracked(repo_root: Path) -> None:
    """Raise (exit 2) if no commit on the current branch ever touched ``upstream/``.

    A repo whose ``upstream/`` exists only as untracked files (never
    committed) has no baseline to diff against; that is a structural
    failure, not drift.
    """
    result = _git_or_raise(
        ["log", "-1", "--format=%H", "--", "upstream/"],
        cwd=repo_root,
        step="upstream-tracked",
        what="git log",
    )
    if not result.stdout.strip():
        raise UpstreamPristineError(
            "no commit on the current branch has ever touched upstream/ — "
            "bootstrap missing?",
            step="upstream-tracked",
        )


def _root_sha(repo_root: Path) -> str:
    """Return the (oldest) root commit SHA of the current history."""
    result = _git_or_raise(
        ["rev-list", "--max-parents=0", "HEAD"],
        cwd=repo_root,
        step="root-sha",
        what="git rev-list",
    )
    # A repo may have multiple roots (e.g. after a subtree merge); the last
    # line is the oldest. Any of them predates every upstream/ edit, so the
    # exact choice only affects which extra paths show up if upstream/ is
    # already dirty — drift is still detected either way.
    lines = [line for line in result.stdout.splitlines() if line]
    if not lines:  # pragma: no cover - HEAD always has a root
        raise UpstreamPristineError(
            "could not determine a root commit for HEAD",
            step="root-sha",
        )
    return lines[-1]


def _sync_anchor_sha(repo_root: Path) -> str:
    """Return the SHA to anchor the committed-drift diff against.

    Prefers the most recent commit whose subject matches the sync/bootstrap
    convention (:data:`_SYNC_SUBJECT_PATTERNS`). Falls back to the merge-base
    with ``origin/main`` and finally to the root commit, so that any
    committed ``upstream/`` edit since the last real sync (or since the fork
    point) is detected rather than silently passing.
    """
    grep_args: list[str] = ["--extended-regexp"]
    for pattern in _SYNC_SUBJECT_PATTERNS:
        grep_args += ["--grep", pattern]
    result = _git_or_raise(
        ["log", "-1", "--format=%H", *grep_args, "HEAD"],
        cwd=repo_root,
        step="sync-anchor",
        what="git log (sync anchor)",
    )
    sha = result.stdout.strip()
    if sha:
        return sha

    # No sync-convention commit on this history. Fall back to the merge-base
    # with origin/main (the fork point), then to the root commit.
    merge_base = _run_git(
        ["merge-base", "HEAD", "origin/main"],
        cwd=repo_root,
    )
    if merge_base.returncode == 0 and merge_base.stdout.strip():
        return merge_base.stdout.strip()
    return _root_sha(repo_root)


def _committed_drift(repo_root: Path, anchor_sha: str) -> list[str]:
    """Return paths under ``upstream/`` that differ between anchor and HEAD."""
    result = _git_or_raise(
        ["diff", "--name-only", anchor_sha, "HEAD", "--", "upstream/"],
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
    """Run the gate. Returns ``(is_pristine, drifted_paths, anchor_sha)``.

    ``anchor_sha`` is the sync/bootstrap commit the committed-drift diff was
    anchored to (the third tuple element is retained for API compatibility).
    """
    _verify_repo_structure(repo_root)
    _assert_upstream_tracked(repo_root)
    anchor_sha = _sync_anchor_sha(repo_root)
    committed = _committed_drift(repo_root, anchor_sha)
    uncommitted = _uncommitted_drift(repo_root)
    # De-duplicate while preserving order.
    seen: set[str] = set()
    drifted: list[str] = []
    for path in [*committed, *uncommitted]:
        if path not in seen:
            seen.add(path)
            drifted.append(path)
    return (not drifted, drifted, anchor_sha)


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
