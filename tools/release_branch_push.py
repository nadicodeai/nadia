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
- Release history is LINEAR: each release commits ON TOP OF the previous
  release tip, so consecutive releases share ancestry. This lets the
  customer ``git pull --ff-only origin release`` fast-forward cleanly
  (no "refusing to merge unrelated histories") and makes
  ``git rev-list --count HEAD..origin/release`` meaningful. We achieve
  this by fetching the current remote tip and committing on top of it;
  only the first bootstrap (no remote branch yet) uses an orphan commit.
- Force-push uses ``--force-with-lease``, never ``--force``. Because the
  history is now linear the push is normally a fast-forward, but we keep
  ``--force-with-lease`` as a safety belt (and to recover if a release is
  ever amended).
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

# Bot identity used for the release commit. Mirrors the bootstrap
# script's "no global config writes" rule by injecting the identity via
# per-invocation ``git -c`` flags rather than ``git config``.
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


def _prepare_scratch() -> Path:
    """Wipe and recreate an empty ``.sync-workdir/release-push/repo`` dir.

    The dist tree is NOT copied here: in the linear-history path the scratch
    must first check out the previous release (which requires an empty
    working tree), and only then is the dist tree copied in by
    :func:`_copy_dist_into_scratch`. Keeping the copy separate lets both the
    orphan and linear paths share the same ordering discipline.
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
    return scratch


def _strip_release_workflows(scratch: Path) -> None:
    """Remove ``.github/workflows/`` from the storefront tree before commit.

    The ``release`` branch is a real branch on nadicodeai/argo, and CI pushes
    it with the Actions ``GITHUB_TOKEN``. GitHub forbids that token from
    creating or updating any file under ``.github/workflows/``: it lacks the
    ``workflow`` OAuth scope, and that scope CANNOT be granted to GITHUB_TOKEN
    (``workflows`` is not even a valid key in a workflow ``permissions:``
    block). So when an upstream sync added a new workflow file
    (build-windows-installer.yml, new in subtree pull 6c9482e8), the
    force-push to ``release`` was rejected: "refusing to allow a GitHub App to
    create or update workflow ... without `workflows` permission".

    Customers do not need our (renamed-upstream) CI workflows, and leaving them
    on the storefront branch risks them spuriously triggering on ``release``.
    So we drop the whole ``.github/workflows/`` dir from the PUSHED tree only.
    dist/argo/ itself — the native install, the tarball release asset, and the
    Docker image — is untouched; this exclusion is storefront-branch-specific.

    Idempotent: the first push after this change deletes the workflow files
    that earlier releases left on the branch; every push thereafter produces a
    tree with no ``.github/workflows/`` at all, so GITHUB_TOKEN never sees a
    workflow-file change.
    """
    workflows = scratch / ".github" / "workflows"
    if workflows.exists():
        _log(
            "storefront: dropping .github/workflows/ "
            "(GITHUB_TOKEN cannot push workflow files)"
        )
        try:
            shutil.rmtree(workflows)
        except OSError as exc:
            raise ScratchSetupError(
                f"could not strip .github/workflows from {scratch}: {exc}",
                step="scratch",
            ) from exc


def _copy_dist_into_scratch(dist_root: Path, scratch: Path) -> None:
    """Copy ``dist_root`` contents into ``scratch`` (mirrors ``cp -a
    <dist>/. <scratch>/``): the renamed tree becomes the scratch repo's
    root (NOT nested under a ``dist/argo/`` subdir)."""
    _log(f"scratch: copying {dist_root} → {scratch}")
    try:
        # symlinks=True preserves any symlinks the rename engine produced
        # (e.g. binaries). dirs_exist_ok handles the existing scratch dir
        # (empty on the orphan path; cleared via `git rm` on the linear one).
        shutil.copytree(dist_root, scratch, symlinks=True, dirs_exist_ok=True)
    except OSError as exc:
        raise ScratchSetupError(
            f"could not copy {dist_root} into {scratch}: {exc}",
            step="scratch",
        ) from exc
    # Storefront branch must not carry CI workflow files — GITHUB_TOKEN cannot
    # push them. See _strip_release_workflows() for the full rationale.
    _strip_release_workflows(scratch)


# ---------------------------------------------------------------------------
# Git: init + (linear or orphan) branch + commit
# ---------------------------------------------------------------------------


def _commit_release(
    scratch: Path,
    dist_root: Path,
    branch: str,
    source_sha: str,
    *,
    remote_url: str,
    base_sha: str | None,
) -> str:
    """Initialise ``scratch`` (an EMPTY dir) as a git repo on ``branch``,
    populate it with the dist tree, and commit; return the commit SHA.

    History is LINEAR when the remote branch already exists. We fetch the
    current remote tip (``base_sha``, resolved earlier via ``ls-remote``)
    and check the new branch out from it so the release commit has the
    previous release as its parent. The checked-out prior release is then
    cleared (``git rm -rfq .``) and the freshly built dist tree is copied
    in, so the release commit's diff is exactly "previous release → this
    release". Doing the checkout while the working tree is empty avoids
    git's "untracked working tree files would be overwritten" abort.

    First-bootstrap case (``base_sha is None``): no remote branch exists
    yet, so we fall back to an orphan branch — the original behaviour —
    and just copy the dist tree in.

    ``--allow-empty`` is passed so a release whose tree is byte-identical
    to the previous one still produces a commit (the pipeline must always
    advance the branch tip).

    Identity is injected via ``git -c user.email=... -c user.name=...``
    flags so we never mutate the operator's global config.
    """
    _log(f"git init -q in {scratch}")
    _run(["git", "init", "-q"], cwd=scratch, step="git-init")

    if base_sha is None:
        # First bootstrap: no prior release to build on; orphan it. The
        # scratch is empty, so just lay down the dist tree.
        _log(f"git checkout --orphan {branch} (first bootstrap, no remote tip)")
        _run(
            ["git", "checkout", "--orphan", branch, "-q"],
            cwd=scratch,
            step="git-checkout",
        )
        _copy_dist_into_scratch(dist_root, scratch)
    else:
        # Linear: base this release on the current remote tip so customers
        # can fast-forward. Fetch the exact SHA (not just the branch name)
        # to avoid races with concurrent pushes between ls-remote and now.
        _log(f"git fetch {remote_url} {base_sha} (base on previous release tip)")
        _run(
            ["git", "fetch", "-q", "--depth", "1", remote_url, base_sha],
            cwd=scratch,
            step="git-fetch",
        )
        # Checkout into the still-empty working tree (no overwrite conflict).
        _log(f"git checkout -b {branch} {base_sha}")
        _run(
            ["git", "checkout", "-q", "-b", branch, base_sha],
            cwd=scratch,
            step="git-checkout",
        )
        # Clear the checked-out prior release, then lay down the new tree.
        _log("git rm -rfq . (clear prior release tree)")
        _run(["git", "rm", "-rfq", "."], cwd=scratch, step="git-rm")
        _copy_dist_into_scratch(dist_root, scratch)

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
            "--allow-empty",
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


def _resolve_remote_lease(remote_url: str, branch: str) -> str | None:
    """Look up the remote's current SHA for ``branch`` via ``ls-remote``.

    Returns the SHA string, or ``None`` if the branch does not exist
    remotely (first bootstrap). This SHA serves two purposes:

    1. It is the base commit the new release is built on top of (linear
       history) — see :func:`_commit_release`.
    2. It is the explicit lease value for ``--force-with-lease``, since the
       scratch repo has no remote-tracking ref for git to discover
       implicitly.

    Resolved once, before the scratch repo exists, so it does not need a
    ``cwd``.
    """
    result = subprocess.run(
        ["git", "ls-remote", remote_url, f"refs/heads/{branch}"],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise PushFailedError(
            f"git ls-remote failed (exit {result.returncode})\n"
            f"stderr: {result.stderr}",
            step="push",
        )
    line = result.stdout.strip().splitlines()
    if not line:
        return None
    return line[0].split("\t", 1)[0]


def _push_or_describe(
    scratch: Path,
    remote_url: str,
    branch: str,
    *,
    lease_sha: str | None,
    dry_run: bool,
) -> None:
    """Force-with-lease push the scratch's release branch to remote_url.

    On ``--dry-run``: prints the planned command and returns; never
    contacts the remote.

    Because the release commit is now based on the current remote tip
    (linear history), the push is normally a plain fast-forward. We still
    use ``--force-with-lease`` as a safety belt. The scratch repo is a
    fresh ``git init`` with no remote-tracking ref, so a bare
    ``--force-with-lease`` would reject as "stale info"; we pass the
    remote's current SHA (``lease_sha``, resolved earlier via
    ``ls-remote``) as the explicit lease value:
    ``--force-with-lease=<branch>:<expected-sha>``.

    First-bootstrap case (``lease_sha is None``, no remote branch yet):
    pass plain ``--force-with-lease`` (no lease key) — git treats it as
    "succeed only if ref does not exist remotely", which is exactly the
    bootstrap invariant.
    """
    if lease_sha is None:
        lease_flag = "--force-with-lease"
    else:
        lease_flag = f"--force-with-lease={branch}:{lease_sha}"
    push_cmd = [
        "git",
        "push",
        lease_flag,
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
    # Resolve the current remote tip up front: it is both the base for the
    # linear release commit and the explicit --force-with-lease value. In
    # dry-run we still resolve it so the staged commit mirrors what a real
    # push would produce (linear when the branch exists, orphan otherwise).
    base_sha = _resolve_remote_lease(remote_url, branch)
    scratch = _prepare_scratch()
    commit_sha = _commit_release(
        scratch,
        dist_root,
        branch,
        source_sha,
        remote_url=remote_url,
        base_sha=base_sha,
    )
    _push_or_describe(
        scratch,
        remote_url,
        branch,
        lease_sha=base_sha,
        dry_run=dry_run,
    )
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
