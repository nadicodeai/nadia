#!/usr/bin/env python3
"""tools/nadia_release.py — workshop-side release driver (IU-FR-5, IU-AC-4, IU-AC-13).

Workshop layout means ``__version__`` and ``__release_date__`` live ONLY inside
the built ``dist/nadia/nadia_cli/__init__.py`` (gitignored on ``main``) — never as
a commit on ``main``. This script bumps those values in-place inside the built
``dist/nadia/``, tags ``main`` HEAD with the CalVer tag, builds a deterministic
tarball, creates the GitHub Release object (via ``gh release create``) **before**
pushing the tag, then pushes the tag (firing ``.github/workflows/release.yml``).

It mirrors upstream's release driver shape but works from the workshop layout:

* ``upstream/scripts/release.py:1383-1409`` — ``get_current_version`` /
  ``bump_version`` semver-bump shape. Mirrored at :func:`_bump_semver`.
* ``upstream/scripts/release.py:1412-1426`` — ``update_version_files``
  in-place regex rewrite for ``__version__``, ``__release_date__``, and the
  top-level ``version`` in ``pyproject.toml``. Mirrored at
  :func:`_rewrite_version_file` and :func:`_rewrite_pyproject_version`.
* ``upstream/scripts/release.py:1887-1918`` — ``gh release create`` invocation
  shape. Mirrored at :func:`_gh_release_create`.

Companion: ``.github/workflows/release.yml`` (separate M4.2 task) fires on the
tag push and force-pushes ``dist/nadia/`` to ``release`` + uploads assets. Its
first release-object consumer (``gh release view <tag>`` in the "Apply release
bump" step) runs only AFTER checkout + setup + ``make build`` + leakage — so it
does NOT require the release object at tag-push time, only minutes later. We
therefore push the tag FIRST and create the release object immediately after
(seconds later, winning the race with wide margin). The reverse order is not
merely suboptimal — it is INFEASIBLE: ``gh release create <tag>`` rejects a tag
that exists locally but is not on the remote, so the create must follow the
push (mirrors upstream/scripts/release.py:1972 push → :2011 create). The
workflow re-attaches assets via ``gh release upload --clobber`` (idempotent),
so attaching them here is a harmless bonus the workflow later clobbers.

Pipeline (default invocation, no ``--dry-run``):

1. Resolve repo root via ``git rev-parse --show-toplevel``; refuse if cwd is
   not inside a git repo.
2. Refuse a dirty worktree (``git status --porcelain`` must be empty).
3. Resolve current ``__version__`` / ``__release_date__`` from
   ``dist/nadia/nadia_cli/__init__.py`` if it exists; otherwise from
   ``upstream/hermes_cli/__init__.py`` (workshop fallback before first build).
4. Compute new values: bump per ``--bump`` (default ``patch``) unless
   ``--version`` is supplied; release-date defaults to today as ``YYYY.M.D``
   (no zero-padding) unless ``--release-date`` is supplied.
5. ``make build`` unless ``--skip-build`` (verifies ``dist/nadia/`` exists).
6. Regex-rewrite ``dist/nadia/nadia_cli/__init__.py`` (the two version strings)
   and ``dist/nadia/pyproject.toml`` (the top-level ``version`` line).
7. Verify the rewrites by reading the files back and re-grepping.
8. Run ``make leakage-static``; abort on failure.
9. Run ``python tools/run_assertions.py dist/nadia``; abort on failure.
10. ``git tag -a v<release-date>`` pointing at workshop ``main`` HEAD.
11. Build the deterministic tarball under
    ``.sync-workdir/release-artifacts/nadia-v<release-date>.tar.gz`` using
    ``SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)`` and tar's
    ``--mtime``/``--sort``/``--owner``/``--group``/``--numeric-owner`` flags.
12. Compute sha256 sums of the tarball + ``dist/nadia/scripts/install.sh``
    (+ ``install.ps1`` if present); write ``sha256sums.txt``.
13. ``git push <remote> v<release-date>`` (unless ``--no-push``/``--dry-run``) —
    fires ``release.yml``. Pushing the tag is a prerequisite for the next step.
14. Run ``gh release create`` with the renamed banner title, the assets above,
    and notes generated from ``git log <prev-tag>..<new-tag>`` (or the
    first-release note when ``--first-release`` is passed). This runs AFTER the
    push because ``gh`` refuses to create a release for an unpushed tag; the
    release object is created seconds after the push, well before
    ``release.yml``'s ``gh release view`` step needs it.
15. Print a summary (tag, version, release date, tarball path, sha256sums
    path, GitHub release URL).

Style
-----

Match ``tools/build.py`` / ``tools/sync.py``:

* Typed argparse; ``subprocess.run(..., check=False)`` followed by an explicit
  returncode check inside a small wrapper that raises a typed error.
* No ``shell=True``. Tar is invoked via an explicit argv list.
* Every file read/write uses ``encoding="utf-8"`` (ruff ``PLW1514``).
* No bare ``except Exception``; catch typed errors at the entry point.
* Stderr logging via ``→`` (info) and ``✗`` (failure) prefixes.

Exit codes
----------

* 0 — success.
* 1 — user error or aborted by gate.
* 2 — unexpected internal failure.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT_DEFAULT = Path(__file__).resolve().parent.parent
DIST_DIR_REL = Path("dist") / "nadia"
ARTIFACTS_DIR_REL = Path(".sync-workdir") / "release-artifacts"

VERSION_FILE_REL = DIST_DIR_REL / "nadia_cli" / "__init__.py"
PYPROJECT_FILE_REL = DIST_DIR_REL / "pyproject.toml"
UPSTREAM_VERSION_FILE_REL = Path("upstream") / "hermes_cli" / "__init__.py"

INSTALL_SH_REL = DIST_DIR_REL / "scripts" / "install.sh"
INSTALL_PS1_REL = DIST_DIR_REL / "scripts" / "install.ps1"

# Regexes mirror upstream/scripts/release.py:1416-1435.
_VERSION_RE = re.compile(r'__version__\s*=\s*"([^"]+)"')
_RELEASE_DATE_RE = re.compile(r'__release_date__\s*=\s*"([^"]+)"')
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)

# CalVer: ``YYYY.M.D`` with no leading zeros on month/day (matches the
# format ``_format_today_calver`` emits — and what upstream's release.py
# tags use). Same-day re-cuts append ``.N`` (also no leading zero).
_CALVER_RE = re.compile(
    r"^\d{4}\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:\.(?:0|[1-9]\d*))?$"
)
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class ReleaseError(RuntimeError):
    """Release-driver failure tagged with a pipeline step label.

    *step* identifies which stage produced the error; callers / CI use it to
    bucket failures.
    """

    def __init__(self, message: str, *, step: str = "release") -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


class NotAGitRepoError(ReleaseError):
    """Current directory is not inside a git repo."""


class DirtyWorktreeError(ReleaseError):
    """Working tree has uncommitted changes."""


class VersionParseError(ReleaseError):
    """Could not parse current version strings."""


class GateFailedError(ReleaseError):
    """A pipeline gate (leakage / assertions / rewrite verify) failed."""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    print(f"→ {msg}", file=sys.stderr)


def _err(msg: str) -> None:
    print(f"✗ {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Subprocess helper (mirrors sync.py:_run pattern)
# ---------------------------------------------------------------------------


def _run(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture: bool = False,
    check: bool = True,
    dry_run: bool = False,
    step: str = "run",
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with text/utf-8 wiring; raise on non-zero if *check*.

    When *dry_run* is true, log the command and return a synthetic
    ``CompletedProcess`` with returncode 0 and empty stdout/stderr.
    """
    if dry_run:
        _log(f"DRY-RUN $ {' '.join(cmd)}" + (f"  (cwd={cwd})" if cwd else ""))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

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
        raise ReleaseError(
            f"command failed: {' '.join(cmd)}\nstdout: {out}\nstderr: {err}",
            step=step,
        )
    return result


# ---------------------------------------------------------------------------
# Repo + worktree preconditions
# ---------------------------------------------------------------------------


def _resolve_repo_root(cwd: Path) -> Path:
    """Return ``git rev-parse --show-toplevel`` from *cwd*.

    Raises :class:`NotAGitRepoError` if cwd is not inside a git repo.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise NotAGitRepoError(
            f"not a git repo (cwd={cwd}): {result.stderr.strip()}",
            step="preconditions",
        )
    return Path(result.stdout.strip())


def _require_clean_worktree(repo: Path, *, dry_run: bool) -> None:
    """Refuse to proceed if the worktree is dirty.

    The ``--dry-run`` mode skips this check so callers can preview a run on a
    workshop that already has in-progress edits.
    """
    if dry_run:
        _log("skipping clean-worktree check (--dry-run)")
        return
    status = _run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture=True,
        check=True,
        step="preconditions",
    ).stdout
    if status.strip():
        raise DirtyWorktreeError(
            "working tree has uncommitted changes; commit or stash them first\n"
            + status,
            step="preconditions",
        )


def _git_head_sha(repo: Path) -> str:
    return _run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture=True,
        check=True,
        step="git",
    ).stdout.strip()


def _git_head_commit_epoch(repo: Path) -> int:
    """Return the unix timestamp of ``HEAD`` (for ``SOURCE_DATE_EPOCH``)."""
    out = _run(
        ["git", "log", "-1", "--format=%ct"],
        cwd=repo,
        capture=True,
        check=True,
        step="git",
    ).stdout.strip()
    return int(out)


def _previous_release_tag(repo: Path, *, exclude: str) -> str | None:
    """Return the most recent existing CalVer tag, excluding *exclude*.

    Used to bound the ``git log <prev>..<new>`` range that produces release
    notes. CalVer tags (``v20*``) sort correctly under
    ``--sort=-version:refname`` so the first entry that is not the tag we are
    about to cut is the immediate predecessor. Returns ``None`` when no prior
    tag exists (the genuine first cut).
    """
    out = _run(
        ["git", "tag", "-l", "v20*", "--sort=-version:refname"],
        cwd=repo,
        capture=True,
        check=True,
        step="release-notes",
    ).stdout
    for line in out.splitlines():
        tag = line.strip()
        if tag and tag != exclude:
            return tag
    return None


def _commit_log_since(repo: Path, prev_tag: str, *, head: str) -> str:
    """Return a bulleted ``git log <prev_tag>..<head>`` body for release notes.

    Each commit becomes a ``- <subject> (<short-sha>)`` line. *head* is the
    revision the new tag points at (``HEAD`` in normal runs).
    """
    out = _run(
        ["git", "log", "--no-merges", "--pretty=format:- %s (%h)", f"{prev_tag}..{head}"],
        cwd=repo,
        capture=True,
        check=True,
        step="release-notes",
    ).stdout.strip()
    return out


# ---------------------------------------------------------------------------
# Version resolution + bumping
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VersionState:
    """Current and computed-new version strings for a release run."""

    current_version: str
    current_release_date: str
    new_version: str
    new_release_date: str
    tag_name: str


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_current_versions(repo: Path) -> tuple[str, str, Path]:
    """Return ``(version, release_date, source_path)`` from the workshop tree.

    Prefer ``dist/nadia/nadia_cli/__init__.py`` (post-build state) and fall back
    to ``upstream/hermes_cli/__init__.py`` when the build hasn't run yet.
    """
    candidates: list[Path] = [
        repo / VERSION_FILE_REL,
        repo / UPSTREAM_VERSION_FILE_REL,
    ]
    for source in candidates:
        if not source.is_file():
            continue
        text = _read_text(source)
        v_match = _VERSION_RE.search(text)
        d_match = _RELEASE_DATE_RE.search(text)
        if v_match and d_match:
            return v_match.group(1), d_match.group(1), source
    raise VersionParseError(
        "could not locate __version__/__release_date__ in either "
        f"{VERSION_FILE_REL} or {UPSTREAM_VERSION_FILE_REL}",
        step="resolve-versions",
    )


def _bump_semver(current: str, part: str) -> str:
    """Mirror ``upstream/scripts/release.py:1390-1409`` bump_version shape.

    Increment one component of a semver triple; lower-order components reset
    to zero (a bump of *minor* zeros patch; a bump of *major* zeros minor and
    patch).
    """
    pieces = current.split(".")
    if len(pieces) != 3:
        raise VersionParseError(
            f"expected dotted semver triple, got {current!r}",
            step="bump",
        )
    try:
        major, minor, patch = (int(p) for p in pieces)
    except ValueError as exc:
        raise VersionParseError(
            f"non-integer semver component in {current!r}: {exc}",
            step="bump",
        ) from exc
    if part == "patch":
        patch += 1
    elif part == "minor":
        minor += 1
        patch = 0
    elif part == "major":
        major += 1
        minor = 0
        patch = 0
    else:
        raise VersionParseError(
            f"unknown bump part: {part!r} (expected patch/minor/major)",
            step="bump",
        )
    return f"{major}.{minor}.{patch}"


def _format_today_calver(today: date | None = None) -> str:
    """Format today (or *today*) as ``YYYY.M.D`` with no zero-padding."""
    d = today if today is not None else date.today()
    return f"{d.year}.{d.month}.{d.day}"


def _validate_calver(value: str) -> None:
    if not _CALVER_RE.match(value):
        raise VersionParseError(
            f"release-date must match YYYY.M.D[.N] (got {value!r})",
            step="resolve-versions",
        )


def _validate_semver(value: str) -> None:
    if not _SEMVER_RE.match(value):
        raise VersionParseError(
            f"version must match X.Y.Z (got {value!r})",
            step="resolve-versions",
        )


def _resolve_versions(
    repo: Path,
    *,
    bump_part: str,
    version_override: str | None,
    release_date_override: str | None,
) -> VersionState:
    current_version, current_release_date, _ = _parse_current_versions(repo)
    if version_override is not None:
        _validate_semver(version_override)
        new_version = version_override
    else:
        new_version = _bump_semver(current_version, bump_part)
    if release_date_override is not None:
        _validate_calver(release_date_override)
        new_release_date = release_date_override
    else:
        new_release_date = _format_today_calver()
    return VersionState(
        current_version=current_version,
        current_release_date=current_release_date,
        new_version=new_version,
        new_release_date=new_release_date,
        tag_name=f"v{new_release_date}",
    )


# ---------------------------------------------------------------------------
# In-place file rewrites (mirrors upstream/scripts/release.py:1412-1436)
# ---------------------------------------------------------------------------


def _rewrite_version_file(text: str, *, new_version: str, new_release_date: str) -> str:
    """Apply the two regex substitutions in :func:`update_version_files`.

    Cites ``upstream/scripts/release.py:1414-1426``.
    """
    text = _VERSION_RE.sub(f'__version__ = "{new_version}"', text)
    text = _RELEASE_DATE_RE.sub(f'__release_date__ = "{new_release_date}"', text)
    return text


def _rewrite_pyproject_version(text: str, *, new_version: str) -> str:
    """Rewrite the top-level ``version = "..."`` in pyproject.toml.

    Cites ``upstream/scripts/release.py:1429-1436``.
    """
    return _PYPROJECT_VERSION_RE.sub(f'version = "{new_version}"', text)


def _apply_rewrites(repo: Path, state: VersionState, *, dry_run: bool) -> None:
    """Rewrite the two files; verify both rewrites by reading them back.

    In ``--dry-run`` mode, log the *planned* before→after lines but do not
    write to disk; the dist/nadia/ tree may not even exist yet, so the
    file-existence preconditions are also dry-run-suppressed.
    """
    init_path = repo / VERSION_FILE_REL
    pyproject_path = repo / PYPROJECT_FILE_REL

    if dry_run:
        _log(
            f"DRY-RUN rewrite {VERSION_FILE_REL}: "
            f'__version__ "{state.current_version}" → "{state.new_version}", '
            f'__release_date__ "{state.current_release_date}" → '
            f'"{state.new_release_date}"'
        )
        _log(
            f"DRY-RUN rewrite {PYPROJECT_FILE_REL}: "
            f'version "{state.current_version}" → "{state.new_version}"'
        )
        return

    if not init_path.is_file():
        raise GateFailedError(
            f"missing post-build version file: {init_path}",
            step="rewrite",
        )
    if not pyproject_path.is_file():
        raise GateFailedError(
            f"missing post-build pyproject: {pyproject_path}",
            step="rewrite",
        )

    init_before = _read_text(init_path)
    init_after = _rewrite_version_file(
        init_before,
        new_version=state.new_version,
        new_release_date=state.new_release_date,
    )
    pyproject_before = _read_text(pyproject_path)
    pyproject_after = _rewrite_pyproject_version(
        pyproject_before, new_version=state.new_version
    )

    init_path.write_text(init_after, encoding="utf-8")
    pyproject_path.write_text(pyproject_after, encoding="utf-8")

    # Verify (re-read + re-grep) — abort if the rewrite did not land.
    verify_init = _read_text(init_path)
    if f'__version__ = "{state.new_version}"' not in verify_init:
        raise GateFailedError(
            f"verify failed: __version__ not rewritten in {init_path}",
            step="verify-rewrite",
        )
    if f'__release_date__ = "{state.new_release_date}"' not in verify_init:
        raise GateFailedError(
            f"verify failed: __release_date__ not rewritten in {init_path}",
            step="verify-rewrite",
        )
    verify_pyproject = _read_text(pyproject_path)
    if f'version = "{state.new_version}"' not in verify_pyproject:
        raise GateFailedError(
            f"verify failed: version not rewritten in {pyproject_path}",
            step="verify-rewrite",
        )
    _log(f"rewrote {VERSION_FILE_REL} and {PYPROJECT_FILE_REL}; verify OK")


# ---------------------------------------------------------------------------
# Build + gates
# ---------------------------------------------------------------------------


def _run_make_build(repo: Path, *, skip: bool, dry_run: bool) -> None:
    if skip:
        _log("skipping `make build` (--skip-build)")
        return
    _log("make build")
    _run(
        ["make", "build"],
        cwd=repo,
        check=True,
        dry_run=dry_run,
        step="build",
    )
    if not dry_run and not (repo / DIST_DIR_REL).is_dir():
        raise GateFailedError(
            f"`make build` reported success but {DIST_DIR_REL} does not exist",
            step="build",
        )


def _run_leakage_static(repo: Path, *, dry_run: bool) -> None:
    _log("make leakage-static")
    _run(
        ["make", "leakage-static"],
        cwd=repo,
        check=True,
        dry_run=dry_run,
        step="leakage-static",
    )


def _run_assertions(repo: Path, *, dry_run: bool) -> None:
    _log("python tools/run_assertions.py dist/nadia")
    _run(
        [sys.executable, str(repo / "tools" / "run_assertions.py"), str(repo / DIST_DIR_REL)],
        cwd=repo,
        check=True,
        dry_run=dry_run,
        step="assertions",
    )


# ---------------------------------------------------------------------------
# Tag + push
# ---------------------------------------------------------------------------


def _create_tag(repo: Path, state: VersionState, *, dry_run: bool) -> None:
    head = "HEAD" if dry_run else _git_head_sha(repo)
    title = f"Nadia Agent v{state.new_version} ({state.new_release_date})"
    _log(f"git tag -a {state.tag_name} -m {title!r} {head}")
    _run(
        ["git", "tag", "-a", state.tag_name, "-m", title, head],
        cwd=repo,
        check=True,
        dry_run=dry_run,
        step="tag",
    )


def _push_tag(repo: Path, state: VersionState, *, remote: str, dry_run: bool) -> None:
    _log(f"git push {remote} {state.tag_name}")
    _run(
        ["git", "push", remote, state.tag_name],
        cwd=repo,
        check=True,
        dry_run=dry_run,
        step="push-tag",
    )


# ---------------------------------------------------------------------------
# Deterministic tarball
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReleaseAssets:
    tarball: Path
    install_sh: Path
    install_ps1: Path | None
    sha256sums: Path


def _build_tarball(repo: Path, state: VersionState, *, dry_run: bool) -> Path:
    """Build the deterministic tarball under ``.sync-workdir/release-artifacts/``.

    Uses ``SOURCE_DATE_EPOCH`` derived from the HEAD commit timestamp + tar's
    determinism flags (``--mtime``, ``--sort``, ``--owner``, ``--group``,
    ``--numeric-owner``) to satisfy IU-AC-12 (byte-identical tarballs).
    """
    artifacts_dir = repo / ARTIFACTS_DIR_REL
    tarball = artifacts_dir / f"nadia-{state.tag_name}.tar.gz"
    dist_dir = repo / DIST_DIR_REL
    if not dry_run:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        if not dist_dir.is_dir():
            raise GateFailedError(
                f"cannot tar: {dist_dir} does not exist",
                step="tarball",
            )
    if dry_run:
        sde = 0
    else:
        sde = _git_head_commit_epoch(repo)
    cmd = [
        "tar",
        f"--mtime=@{sde}",
        "--sort=name",
        "--owner=0",
        "--group=0",
        "--numeric-owner",
        "-czf",
        str(tarball),
        "-C",
        str(dist_dir),
        ".",
    ]
    env = {**os.environ, "SOURCE_DATE_EPOCH": str(sde)}
    _log(f"tar (deterministic) → {tarball.relative_to(repo)}")
    _run(cmd, cwd=repo, env=env, check=True, dry_run=dry_run, step="tarball")
    return tarball


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_sha256sums(repo: Path, paths: list[Path], *, dry_run: bool) -> Path:
    """Write a ``sha256sums.txt`` file next to the tarball.

    The format matches ``sha256sum`` output: ``<hex>  <basename>``.
    """
    sums_path = repo / ARTIFACTS_DIR_REL / "sha256sums.txt"
    if dry_run:
        _log(f"DRY-RUN sha256sums for {[p.name for p in paths]} → {sums_path}")
        return sums_path
    lines = []
    for p in paths:
        lines.append(f"{_sha256_of_file(p)}  {p.name}")
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _log(f"sha256sums written → {sums_path.relative_to(repo)}")
    return sums_path


def _collect_assets(repo: Path, state: VersionState, *, dry_run: bool) -> ReleaseAssets:
    tarball = _build_tarball(repo, state, dry_run=dry_run)
    install_sh = repo / INSTALL_SH_REL
    install_ps1 = repo / INSTALL_PS1_REL
    if not dry_run and not install_sh.is_file():
        raise GateFailedError(
            f"missing installer asset: {install_sh}", step="assets"
        )
    ps1: Path | None = install_ps1 if (dry_run or install_ps1.is_file()) else None
    asset_paths: list[Path] = [tarball, install_sh]
    if ps1 is not None:
        asset_paths.append(ps1)
    sums = _write_sha256sums(repo, asset_paths, dry_run=dry_run)
    return ReleaseAssets(
        tarball=tarball, install_sh=install_sh, install_ps1=ps1, sha256sums=sums
    )


# ---------------------------------------------------------------------------
# GitHub release (mirrors upstream/scripts/release.py:1887-1918)
# ---------------------------------------------------------------------------


def _release_notes(
    repo: Path,
    state: VersionState,
    *,
    first_release: bool,
    dry_run: bool,
) -> str:
    """Build the release-notes body for ``gh release create``.

    On the genuine first cut (``--first-release``), or when no prior CalVer tag
    exists, emit the static first-release note. Otherwise generate a changelog
    from ``git log <prev-tag>..<new-tag>`` so every release ships its own notes
    (the previous code hardcoded "First CalVer release" on EVERY release).
    """
    changelog_url = (
        f"https://github.com/nadicodeai/argo/commits/{state.tag_name}"
    )
    if first_release:
        _log("--first-release: emitting static first-release note")
        return f"First CalVer release. See changelog at {changelog_url}."

    # In dry-run the new tag has not been created, so resolve the previous tag
    # against HEAD; otherwise the new annotated tag already exists locally and
    # is excluded from the predecessor search.
    head = "HEAD" if dry_run else state.tag_name
    prev_tag = _previous_release_tag(repo, exclude=state.tag_name)
    if prev_tag is None:
        _log("no prior CalVer tag found; falling back to first-release note")
        return f"First CalVer release. See changelog at {changelog_url}."

    body = _commit_log_since(repo, prev_tag, head=head)
    _log(f"release notes generated from {prev_tag}..{head}")
    header = f"Changes since {prev_tag}:"
    if not body:
        body = "- (no commits since previous tag)"
    return f"{header}\n\n{body}\n\nSee changelog at {changelog_url}."


def _gh_release_create(
    repo: Path,
    state: VersionState,
    assets: ReleaseAssets,
    notes: str,
    *,
    dry_run: bool,
) -> str | None:
    """Invoke ``gh release create`` with the renamed banner title.

    Cites ``upstream/scripts/release.py:1887-1918``. Returns the release URL
    (printed by ``gh``) or ``None`` in ``--dry-run`` mode. *notes* is supplied
    by :func:`_release_notes` (per-release changelog, not a hardcoded string).
    """
    title = f"Nadia Agent v{state.new_version} ({state.new_release_date})"
    cmd: list[str] = [
        "gh", "release", "create", state.tag_name,
        "--title", title,
        "--notes", notes,
        str(assets.tarball),
        str(assets.install_sh),
    ]
    if assets.install_ps1 is not None:
        cmd.append(str(assets.install_ps1))
    cmd.append(str(assets.sha256sums))
    _log(f"gh release create {state.tag_name} ({title!r})")
    result = _run(
        cmd, cwd=repo, capture=True, check=True, dry_run=dry_run, step="gh-release"
    )
    if dry_run:
        return None
    return result.stdout.strip() or None


# ---------------------------------------------------------------------------
# Pipeline entrypoint
# ---------------------------------------------------------------------------


@dataclass
class CliArgs:
    bump: str
    first_release: bool
    dry_run: bool
    release_date: str | None
    version: str | None
    no_push: bool
    skip_build: bool
    remote: str


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nadia_release.py",
        description=(
            "Workshop-side release driver: bump version + release-date in "
            "dist/nadia/, tag main HEAD, build deterministic tarball, create the "
            "GitHub Release object, then push the tag (firing release.yml)."
        ),
    )
    p.add_argument(
        "--bump",
        choices=["patch", "minor", "major"],
        default="patch",
        help="Which semver part to bump in __version__ (default: patch).",
    )
    p.add_argument(
        "--first-release",
        action="store_true",
        help=(
            "Behave like upstream's --first-release flag: skip the "
            "changelog-from-previous-tag logic and use the static first-release "
            "note instead. Required for the genuine first CalVer cut."
        ),
    )
    p.add_argument(
        "--release-date",
        default=None,
        help=(
            "Override the CalVer (default: today as YYYY.M.D with no "
            "zero-padding). For repeat runs on the same day, pass e.g. "
            "2026.5.28.2."
        ),
    )
    p.add_argument(
        "--version",
        default=None,
        help="Override __version__ explicitly (e.g., 0.14.1).",
    )
    p.add_argument(
        "--no-push",
        action="store_true",
        help=(
            "Stop before ANY remote mutation: create the local annotated tag "
            "and build the assets, but do NOT push the tag and do NOT create "
            "the GitHub Release (gh cannot create a release for an unpushed "
            "tag). release.yml is not fired. The command prints the manual "
            "`git push` + `gh release create` line to finish later."
        ),
    )
    p.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip `make build` (assumes dist/nadia/ already exists). Useful for re-runs.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print every shell command + write target without doing them.",
    )
    p.add_argument(
        "--remote",
        default="origin",
        help="Git remote for `git push <remote> <tag>` (default: origin).",
    )
    return p


def _summary(
    state: VersionState,
    assets: ReleaseAssets,
    *,
    release_url: str | None,
    pushed: bool,
) -> str:
    bits: list[str] = [
        "",
        "Release summary:",
        f"  tag           : {state.tag_name}",
        f"  version       : {state.new_version} (was {state.current_version})",
        f"  release date  : {state.new_release_date} (was {state.current_release_date})",
        f"  tarball       : {assets.tarball}",
        f"  sha256sums    : {assets.sha256sums}",
        f"  github release: {release_url or '(no URL returned)'}",
    ]
    if pushed:
        bits.append("  tag pushed    : yes (release.yml fired)")
    else:
        bits.append("  tag pushed    : no (--no-push / --dry-run; release.yml not fired)")
    return "\n".join(bits)


def run(args: CliArgs) -> int:
    cwd = Path.cwd()
    repo = _resolve_repo_root(cwd)
    _require_clean_worktree(repo, dry_run=args.dry_run)

    state = _resolve_versions(
        repo,
        bump_part=args.bump,
        version_override=args.version,
        release_date_override=args.release_date,
    )
    _log(
        f"versions resolved: {state.current_version} → {state.new_version}; "
        f"{state.current_release_date} → {state.new_release_date}; "
        f"tag={state.tag_name}"
    )

    _run_make_build(repo, skip=args.skip_build, dry_run=args.dry_run)
    _apply_rewrites(repo, state, dry_run=args.dry_run)
    _run_leakage_static(repo, dry_run=args.dry_run)
    _run_assertions(repo, dry_run=args.dry_run)

    # Create the annotated tag locally and build the assets/notes, THEN push
    # the tag, THEN create the GitHub Release object — in that order.
    #
    # Ordering is load-bearing and mirrors upstream/scripts/release.py, which
    # pushes the tag (release.py:1972 `git push origin HEAD --tags`) BEFORE
    # `gh release create` (release.py:2011). `gh release create <tag>` refuses
    # a tag that exists locally but is absent on the remote ("tag <t> exists
    # locally but has not been pushed ... please push it before continuing or
    # specify the `--target` flag") — so the create MUST follow the push. The
    # earlier "create before push" ordering was infeasible against `gh` and is
    # the bug this reorder fixes.
    #
    # Does this re-introduce the race release.yml worried about? No. release.yml
    # fires on the tag push, but its first release-object consumer
    # (`gh release view <tag>` in the "Apply release bump" step) runs only AFTER
    # checkout + nadia-setup + `make build` + `make leakage-static` — minutes of
    # runway. Creating the release object in the very next local step (seconds
    # after the push) wins that race with a wide margin. The workflow re-uploads
    # assets via `gh release upload --clobber`, so attaching them here is a
    # harmless convenience.
    _create_tag(repo, state, dry_run=args.dry_run)
    assets = _collect_assets(repo, state, dry_run=args.dry_run)
    notes = _release_notes(
        repo, state, first_release=args.first_release, dry_run=args.dry_run
    )

    pushed = not args.no_push
    if pushed:
        _push_tag(repo, state, remote=args.remote, dry_run=args.dry_run)
        release_url = _gh_release_create(
            repo, state, assets, notes, dry_run=args.dry_run
        )
    else:
        # --no-push: stop before ANY remote mutation. A GitHub Release cannot be
        # created for an unpushed tag (see ordering note above), so we skip the
        # create too and print the manual finish command (mirrors upstream's
        # manual-publish fallback at release.py:2018-2023). The local annotated
        # tag + built assets are left in place for that manual step.
        release_url = None
        _log("skipping tag push + release create (--no-push); release.yml NOT fired")
        _log(
            f"to finish manually: git push {args.remote} {state.tag_name} && "
            f"gh release create {state.tag_name} "
            f"--title 'Nadia Agent v{state.new_version} ({state.new_release_date})' "
            f"--notes-file <notes-file> {assets.tarball} {assets.install_sh} "
            f"{assets.sha256sums}"
        )

    print(
        _summary(state, assets, release_url=release_url, pushed=pushed and not args.dry_run),
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    args = CliArgs(
        bump=ns.bump,
        first_release=ns.first_release,
        dry_run=ns.dry_run,
        release_date=ns.release_date,
        version=ns.version,
        no_push=ns.no_push,
        skip_build=ns.skip_build,
        remote=ns.remote,
    )
    try:
        return run(args)
    except ReleaseError as exc:
        _err(str(exc))
        return 1
    except (OSError, ValueError) as exc:
        _err(f"unexpected: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
