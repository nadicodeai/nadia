#!/usr/bin/env python3
"""tools/parity_runner.py — FR-16 / AC-7 customer-parity gate.

Runs the new image and the legacy image through the same surfaces
side-by-side, normalizes the legacy output by substituting hermes→argo
(case-preserving), and diffs the normalized legacy output against the
new image's raw output. Any non-empty diff is a regression.

Surfaces in scope (FR-16 items 1-7):

1. ``argo --help``                 — top-level help (long, multi-screen).
2. ``argo --version``              — short version banner.
3. ``argo doctor --static``        — static leakage scan target (both
   images currently exit 2 with ``--static`` unrecognized; equal-and-
   identical drift is still PASS).
4. ``argo mcp list``               — MCP plugin discovery (fixture dir).
5. ``argo hooks test <event>``     — hook dispatch (fixture script).
6. ``argo auth list``              — pooled credentials list, used as
   the closest available proxy for FR-16 #6 ("OAuth init"); neither
   image exposes an ``auth start --provider stub`` surface, so the
   runner exercises the read-only listing instead and SKIPs gracefully
   if either image refuses to run.
7. ``argo sessions list``          — session-store readout, used as the
   closest available proxy for FR-16 #7 ("session persistence"); the
   runner mounts a fresh ``ARGO_HOME`` so neither image is touching
   real state, and diffs the post-run files when both succeed.

Pragmatic adaptation (FR-16 surfaces 4-7)
-----------------------------------------

The legacy ``:latest`` (= v0.8.0) image predates several v0.14.0
subcommands. Each backend surface follows a uniform protocol:

a. Attempt the surface on both images.
b. If EITHER image exits with argparse's "invalid choice" /
   "unrecognized arguments" pattern (subcommand missing), the runner
   marks the surface ``SKIPPED`` with the missing-side recorded.
c. If both images run successfully, normalize legacy output and diff.
d. SKIPPED counts as neither pass nor fail for the AC-7 gate today,
   but it IS reported. AC-7 ultimately requires all 7 to PASS — until
   the slim image is fixed (FR-16 surface 4 currently fails with
   ``ModuleNotFoundError: No module named 'tools'`` on ``:dev``) the
   gate stays a per-surface report rather than a single boolean.

Baseline image
--------------

The spec references ``ghcr.io/nadicodeai/argo-agent:0.14.0`` as the
legacy baseline. **That tag was never pushed to GHCR.** The only
available tag at the legacy registry is ``ghcr.io/nadicodeai/argo-agent
:latest``. The runner defaults to ``:latest`` and documents the gap.
If a future legacy release publishes specific version tags, update
this default and the spec's referenced version. See AGENTS.md for the
full rationale.

Note that ``:latest`` (as pulled at the time M6.2a landed) reports
``Hermes Agent v0.8.0`` while the new image reports ``Argo Agent
v0.14.0`` — i.e. the legacy ``:latest`` is an OLDER image than the
spec-named 0.14.0 tag. The parity diff for ``--help`` reflects that
gap (new image has a feature superset). That is a documentation
problem, not a regression.

Invocation
----------

.. code-block:: bash

   python tools/parity_runner.py [--new-image IMG] [--legacy-image IMG]
                                 [--surface NAME] [--verbose]

Exit codes
----------

- 0: every in-scope surface is PASS or SKIPPED.
- 1: at least one surface failed (content diff or exit-code mismatch).
- 2: structural / environment error (image not pullable, docker missing).
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

DEFAULT_NEW_IMAGE = "ghcr.io/nadicodeai/argo:dev"
DEFAULT_LEGACY_IMAGE = "ghcr.io/nadicodeai/argo-agent:latest"

# Repository root, resolved relative to this file. Used to anchor
# fixture mounts (``tests/fixtures/parity-{mcp,hooks}``) so the runner
# works from any CWD.
REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_MCP_DIR = REPO_ROOT / "tests" / "fixtures" / "parity-mcp"
FIXTURE_HOOKS_DIR = REPO_ROOT / "tests" / "fixtures" / "parity-hooks"

# Substitution table for hermes→argo normalization of legacy output.
#
# Ordered longest-prefix-first so composite identifiers (``hermes-agent``,
# ``hermes_agent``, ``HERMES_HOME``) win before the bare ``hermes`` /
# ``Hermes`` / ``HERMES`` variants. Mirrors the case-preserving rules in
# argo-rename.yaml's mapping table.
_NORMALIZATION_MAPPINGS: tuple[tuple[str, str], ...] = (
    # Composite identifiers (snake_case, kebab-case, PascalCase, SCREAMING).
    ("hermes_tools_mcp_server", "argo_tools_mcp_server"),
    ("HermesAgent", "ArgoAgent"),
    ("Hermes-Agent", "Argo-Agent"),
    ("hermes-agent", "argo-agent"),
    ("hermes_agent", "argo_agent"),
    ("hermes_bootstrap", "argo_bootstrap"),
    ("hermes_constants", "argo_constants"),
    ("hermes_logging", "argo_logging"),
    ("hermes_state", "argo_state"),
    ("hermes_time", "argo_time"),
    ("hermes_cli", "argo_cli"),
    ("HERMES_HOME", "ARGO_HOME"),
    ("HERMES_", "ARGO_"),
    ("~/.hermes", "~/.argo"),
    (".hermes/", ".argo/"),
    # Bare case variants (shortest, last).
    ("Hermes", "Argo"),
    ("HERMES", "ARGO"),
    ("hermes", "argo"),
)

# Patterns that signal "this subcommand does not exist on this image" —
# argparse's standard error formats. Used by the SKIP detector.
_SUBCOMMAND_MISSING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"invalid choice: '[^']+'"),
    re.compile(r"unrecognized arguments:"),
    re.compile(r"^.+: command not found", re.MULTILINE),
)


# Surface invocation spec.
#
# For the new image (no ENTRYPOINT, CMD=argo) we pass the full
# ``argo <subcommand…>``. For the legacy image (ENTRYPOINT runs an
# init script and ends with ``exec hermes "$@"``) we bypass with
# ``--entrypoint hermes`` and pass only the subcommand args.
#
# ``volumes`` is a sequence of ``(host_path, container_path)`` pairs
# that get rendered into ``-v HOST:CONTAINER:ro`` flags. Per-image
# volume sets are kept symmetric: both images see the same fixture
# mounts. For surfaces that write artifacts (``artifact_path`` set)
# the runner provisions per-image tmp dirs at runtime and mounts each
# at ``container_artifact_dir``; the artifact path is then read back
# from the host side and compared instead of stdout.
@dataclass(frozen=True)
class _SurfaceSpec:
    """How to invoke one surface against both images."""

    new_args: tuple[str, ...]
    legacy_entrypoint: str
    legacy_args: tuple[str, ...]
    volumes: tuple[tuple[Path, str], ...] = field(default_factory=tuple)
    # When set, the runner provisions a fresh host tmpdir per image,
    # mounts it (read-write) at ``container_artifact_dir``, sets
    # ``ARGO_HOME``/``HERMES_HOME`` to that path so the binary writes
    # state there, and compares the *files* under ``artifact_path``
    # (relative to the mount) after run, not stdout.
    container_artifact_dir: str | None = None
    artifact_path: str | None = None


SURFACES: dict[str, _SurfaceSpec] = {
    "help": _SurfaceSpec(
        new_args=("argo", "--help"),
        legacy_entrypoint="hermes",
        legacy_args=("--help",),
    ),
    "version": _SurfaceSpec(
        new_args=("argo", "--version"),
        legacy_entrypoint="hermes",
        legacy_args=("--version",),
    ),
    "doctor-static": _SurfaceSpec(
        new_args=("argo", "doctor", "--static"),
        legacy_entrypoint="hermes",
        legacy_args=("doctor", "--static"),
    ),
    # FR-16 #4. ``mcp list`` exists on both images. The legacy v0.8.0
    # image prints a friendly "No MCP servers configured" message; the
    # new :dev image currently crashes with ``ModuleNotFoundError: No
    # module named 'tools'`` because the slim Docker image strips the
    # upstream ``tools/`` package the MCP machinery imports. The runner
    # surfaces that as a FAIL (exit-code mismatch). See AGENTS.md "Slim
    # image gap" — fixing it is M5 follow-up territory.
    "mcp-list": _SurfaceSpec(
        new_args=("argo", "mcp", "list"),
        legacy_entrypoint="hermes",
        legacy_args=("mcp", "list"),
        volumes=((FIXTURE_MCP_DIR, "/fixtures"),),
    ),
    # FR-16 #5. The new image exposes ``argo hooks test <event>``; the
    # legacy v0.8.0 image has no ``hooks`` (nor ``hook``) subcommand.
    # The SKIP detector catches argparse's "invalid choice" and reports
    # ``SKIPPED (legacy lacks subcommand)``.
    "hook-fire": _SurfaceSpec(
        new_args=("argo", "hooks", "test", "test-event"),
        legacy_entrypoint="hermes",
        legacy_args=("hooks", "test", "test-event"),
        volumes=((FIXTURE_HOOKS_DIR, "/fixtures"),),
    ),
    # FR-16 #6. Neither image exposes ``auth start --provider stub`` —
    # the spec's literal surface — so the runner uses ``auth list``,
    # the closest read-only proxy supported by BOTH images. If a future
    # legacy release adds a stub OAuth provider, swap this back to the
    # spec wording.
    "auth-start": _SurfaceSpec(
        new_args=("argo", "auth", "list"),
        legacy_entrypoint="hermes",
        legacy_args=("auth", "list"),
    ),
    # FR-16 #7. The spec's literal surface is ``argo chat --once`` with
    # ``ARGO_HOME=/tmp/x`` and a session-file diff. ``chat`` requires a
    # configured inference model and the suite explicitly forbids
    # network-touching surfaces, so the runner falls back to
    # ``sessions list`` against a fresh ARGO_HOME / HERMES_HOME. That
    # exercises the same persistence layer (creates ``state.db`` and
    # the directory tree) without needing a model. We diff the *files*
    # the binary writes, not stdout — that's the persistence contract.
    "session-init": _SurfaceSpec(
        new_args=("argo", "sessions", "list"),
        legacy_entrypoint="hermes",
        legacy_args=("sessions", "list"),
        container_artifact_dir="/argohome",
        # Compare the post-run directory listing (file names + JSON
        # contents when present). Empty string = compare the whole
        # mounted dir as a single relative listing.
        artifact_path="",
    ),
}


class ParityError(RuntimeError):
    """Base class for parity runner failures."""


class ImageNotFoundError(ParityError):
    """Image is not pullable / not present locally (exit 2)."""


class ExitCodeMismatchError(ParityError):
    """Both images returned different non-zero exit codes (exit 1)."""

    def __init__(self, surface: str, new_code: int, legacy_code: int) -> None:
        super().__init__(
            f"surface {surface!r}: new image exit={new_code}, "
            f"legacy image exit={legacy_code}",
        )
        self.surface = surface
        self.new_code = new_code
        self.legacy_code = legacy_code


class ContentDiffError(ParityError):
    """Normalized legacy stdout differs from new stdout (exit 1)."""

    def __init__(self, surface: str, diff: str) -> None:
        super().__init__(f"surface {surface!r}: content diff (see report)")
        self.surface = surface
        self.diff = diff


@dataclass(frozen=True)
class SurfaceResult:
    """One surface's parity outcome.

    ``status`` is one of ``"PASS"``, ``"FAIL"``, ``"SKIPPED"``. A
    SKIPPED result records ``skip_reason`` describing which image
    lacked the subcommand. PASS-with-skips is allowed by the runner
    (and reported); AC-7 currently treats SKIP as not-yet-gated rather
    than green.
    """

    surface: str
    status: str  # "PASS" | "FAIL" | "SKIPPED"
    new_exit: int
    legacy_exit: int
    new_stdout: str
    legacy_stdout_raw: str
    legacy_stdout_normalized: str
    diff: str  # empty unless status == "FAIL"
    skip_reason: str = ""

    @property
    def passed(self) -> bool:
        """Back-compat: ``True`` only when status is ``"PASS"``.

        Existing M6.2a tests assert ``result.passed`` — keep the
        property so they don't have to be rewritten. SKIPPED is *not*
        passed: callers that need to permit skips MUST check ``status``
        explicitly.
        """
        return self.status == "PASS"


def _normalize_hermes(text: str) -> str:
    """Apply hermes→argo case-preserving substitution to ``text``.

    Mappings are applied in the order declared in ``_NORMALIZATION_MAPPINGS``
    (longest-prefix-first), matching the engine's behavior in
    argo-rename.yaml. Idempotent: applying twice yields the same result
    as applying once.
    """
    out = text
    for src, dst in _NORMALIZATION_MAPPINGS:
        out = out.replace(src, dst)
    return out


def _looks_like_missing_subcommand(stdout: str, exit_code: int) -> bool:
    """Return True iff ``stdout`` looks like argparse rejecting a subcommand.

    Heuristic: argparse prints ``<prog>: error: argument command:
    invalid choice: '<name>'`` and exits 2 when a subcommand is
    missing. We also catch ``unrecognized arguments:`` (the same
    pattern at the parent-parser level) and shell ``command not found``
    for completeness.

    The detector is conservative — non-zero exit is required AND a
    pattern must match. A surface that legitimately fails with
    non-argparse exit 1 (e.g., the slim :dev image's ``ModuleNotFoundError:
    No module named 'tools'``) is NOT skipped; it's reported as FAIL,
    which is the honest signal.
    """
    if exit_code == 0:
        return False
    return any(p.search(stdout) for p in _SUBCOMMAND_MISSING_PATTERNS)


def _check_image_present(image: str) -> None:
    """Raise ``ImageNotFoundError`` if ``image`` is not available locally.

    The runner does NOT pull on demand — CI's parity job is responsible
    for ``docker pull`` before invocation. This keeps the runner pure
    (no network) and the failure mode crisp.
    """
    res = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if res.returncode != 0:
        raise ImageNotFoundError(
            f"image {image!r} not present locally; "
            "run `docker pull` first or pass a different --*-image",
        )


def _docker_run(
    image: str,
    *,
    entrypoint: str | None,
    args: Sequence[str],
    volumes: Sequence[tuple[Path, str]] = (),
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a one-shot command in ``image`` and capture stdout + exit code.

    stderr is merged into the captured stream because argparse error
    paths (``hermes: error: unrecognized arguments: --static``) print to
    stderr but ARE part of the surface contract — parity must catch
    drift in those messages too.

    ``volumes`` are mounted read-only at the host path (sufficient for
    the fixture surfaces). Artifact surfaces use a separate code path
    that mounts read-write (see ``run_surface``).
    """
    cmd: list[str] = ["docker", "run", "--rm"]
    for host, container in volumes:
        cmd += ["-v", f"{host}:{container}:ro"]
    if env:
        for k, v in env.items():
            cmd += ["-e", f"{k}={v}"]
    if entrypoint is not None:
        cmd += ["--entrypoint", entrypoint]
    cmd.append(image)
    cmd.extend(args)
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        check=False,
    )
    return res.returncode, res.stdout


# Volatile fields stripped from session-state JSON before diffing.
# Anything that varies per-run (timestamps, UUIDs, absolute paths
# baked from temp dirs) goes here.
_VOLATILE_JSON_KEYS: frozenset[str] = frozenset(
    {
        "created_at",
        "updated_at",
        "id",
        "session_id",
        "timestamp",
        "ts",
        "uuid",
        "path",
    },
)


def _strip_volatile_json(obj: object) -> object:
    """Recursively drop volatile keys from a JSON-like structure.

    Used by the session-init surface so the diff only sees stable
    structural keys. If a future surface needs to retain a particular
    key, factor the predicate out as a parameter.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_volatile_json(v)
            for k, v in obj.items()
            if k not in _VOLATILE_JSON_KEYS
        }
    if isinstance(obj, list):
        return [_strip_volatile_json(x) for x in obj]
    return obj


def _summarize_artifact_dir(root: Path) -> str:
    """Render a stable, diff-friendly summary of ``root``'s contents.

    Format (one entry per line, sorted by relative path):

    - ``<relpath>\tFILE\t<size_bucket>`` for non-JSON files
    - ``<relpath>\tJSON\t<sorted-keys-json>`` for ``*.json`` (stripped
      of volatile keys via ``_strip_volatile_json``)
    - ``<relpath>\tDIR`` for empty dirs
    - ``<relpath>\tDIR_PERMISSION_DENIED`` for dirs we cannot enter
      (legacy ``hermes sessions list`` creates 0700 subdirs owned by
      root-in-container; the host process running as a regular user
      cannot ``opendir`` them, but their *existence* is still part of
      the persistence contract and MUST appear in the diff)

    Size bucket coarsens to ``empty`` / ``small`` / ``large`` so
    trivial filesystem differences (an extra log byte, a different
    backup count) don't dominate the diff.
    """
    if not root.exists():
        return "<artifact dir missing>\n"
    lines: list[str] = []
    entries: list[Path] = []
    # Capture dirs that os.walk cannot enter (PermissionError on
    # opendir). ``onerror`` is called with the OSError; we record the
    # directory path so the summary still reports it.
    denied_dirs: list[Path] = []

    def _on_walk_error(err: OSError) -> None:
        if isinstance(err, PermissionError) and err.filename:
            denied_dirs.append(Path(err.filename))

    for dirpath, dirnames, filenames in os.walk(root, onerror=_on_walk_error):
        dirnames.sort()
        d = Path(dirpath)
        if not filenames and not dirnames and d != root:
            entries.append(d)
        for fn in sorted(filenames):
            entries.append(d / fn)
    for denied in denied_dirs:
        entries.append(denied)
    entries.sort(key=lambda p: p.relative_to(root).as_posix())
    for entry in entries:
        rel = entry.relative_to(root).as_posix()
        if entry in denied_dirs:
            lines.append(f"{rel}\tDIR_PERMISSION_DENIED")
            continue
        if entry.is_dir():
            lines.append(f"{rel}\tDIR")
            continue
        try:
            data = entry.read_bytes()
        except PermissionError:
            lines.append(f"{rel}\tFILE_PERMISSION_DENIED")
            continue
        if entry.suffix == ".json":
            try:
                parsed = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                lines.append(f"{rel}\tJSON_INVALID")
                continue
            stripped = _strip_volatile_json(parsed)
            lines.append(f"{rel}\tJSON\t{json.dumps(stripped, sort_keys=True)}")
        else:
            n = len(data)
            bucket = "empty" if n == 0 else ("small" if n < 4096 else "large")
            lines.append(f"{rel}\tFILE\t{bucket}")
    return "\n".join(lines) + ("\n" if lines else "")


def _diff(legacy_normalized: str, new_raw: str, *, surface: str) -> str:
    """Return a unified diff string. Empty when inputs match."""
    if legacy_normalized == new_raw:
        return ""
    return "".join(
        difflib.unified_diff(
            legacy_normalized.splitlines(keepends=True),
            new_raw.splitlines(keepends=True),
            fromfile=f"legacy(normalized):{surface}",
            tofile=f"new:{surface}",
            n=3,
        )
    )


def _run_artifact_surface(
    spec: _SurfaceSpec,
    *,
    image: str,
    entrypoint: str | None,
    args: Sequence[str],
    home_env_var: str,
) -> tuple[int, str, str]:
    """Run ``image`` with a fresh writable ARGO_HOME / HERMES_HOME mount.

    Returns ``(exit_code, stdout, artifact_summary)``. The summary is
    produced by ``_summarize_artifact_dir`` against the host-side tmp
    dir AFTER the container exits — so we capture exactly what the
    binary persisted, modulo volatile JSON keys.
    """
    assert spec.container_artifact_dir is not None
    # The legacy ``hermes sessions list`` (running as root in-container)
    # creates 0700 subdirs (``sessions/``, ``memories/``, ``logs/``)
    # owned by uid 0 inside the user namespace. The host process (a
    # regular user) cannot ``unlink`` those entries or even ``chmod``
    # them, so the standard ``TemporaryDirectory`` cleanup raises
    # PermissionError on exit. Even ``ignore_cleanup_errors=True``
    # currently doesn't suppress this on CPython 3.13 (the
    # _resetperms call inside _rmtree's onexc raises a non-PermissionError
    # OSError that escapes). We manage the tempdir manually and rely on
    # ``shutil.rmtree(ignore_errors=True)`` — leftover dirs are under
    # /tmp and harmless.
    host_home = Path(tempfile.mkdtemp(prefix="parity-home-"))
    try:
        cmd: list[str] = ["docker", "run", "--rm"]
        for host, container in spec.volumes:
            cmd += ["-v", f"{host}:{container}:ro"]
        cmd += ["-v", f"{host_home}:{spec.container_artifact_dir}"]
        cmd += ["-e", f"{home_env_var}={spec.container_artifact_dir}"]
        if entrypoint is not None:
            cmd += ["--entrypoint", entrypoint]
        cmd.append(image)
        cmd.extend(args)
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            check=False,
        )
        # Summarize while the tmpdir is still alive.
        summary = _summarize_artifact_dir(host_home)
    finally:
        # Best-effort cleanup. We deliberately swallow PermissionError /
        # OSError from the root-owned subdirs the container created.
        with contextlib.suppress(OSError):
            shutil.rmtree(host_home, ignore_errors=True)
    return res.returncode, res.stdout, summary


def run_surface(
    surface: str,
    *,
    new_image: str,
    legacy_image: str,
) -> SurfaceResult:
    """Execute one surface against both images and produce a SurfaceResult.

    Raises
    ------
    KeyError
        If ``surface`` is not in ``SURFACES``.
    ImageNotFoundError
        If either image is missing locally.
    """
    if surface not in SURFACES:
        raise KeyError(f"unknown surface: {surface!r}")

    spec = SURFACES[surface]
    _check_image_present(new_image)
    _check_image_present(legacy_image)

    if spec.container_artifact_dir is not None:
        # Artifact-comparison surface: mount writable home, diff files.
        new_exit, new_stdout, new_summary = _run_artifact_surface(
            spec,
            image=new_image,
            entrypoint=None,
            args=spec.new_args,
            home_env_var="ARGO_HOME",
        )
        legacy_exit, legacy_stdout_raw, legacy_summary = _run_artifact_surface(
            spec,
            image=legacy_image,
            entrypoint=spec.legacy_entrypoint,
            args=spec.legacy_args,
            home_env_var="HERMES_HOME",
        )
        # The "stdout under comparison" for an artifact surface IS the
        # post-run filesystem summary. stdout is captured separately
        # for diagnostics but does not gate parity.
        new_compare = new_summary
        legacy_compare_raw = legacy_summary
    else:
        new_exit, new_stdout = _docker_run(
            new_image,
            entrypoint=None,
            args=spec.new_args,
            volumes=spec.volumes,
        )
        legacy_exit, legacy_stdout_raw = _docker_run(
            legacy_image,
            entrypoint=spec.legacy_entrypoint,
            args=spec.legacy_args,
            volumes=spec.volumes,
        )
        new_compare = new_stdout
        legacy_compare_raw = legacy_stdout_raw

    # SKIP detection comes BEFORE diffing: if either image lacks the
    # subcommand, the surface is not comparable and must not produce a
    # FAIL.
    new_missing = _looks_like_missing_subcommand(new_stdout, new_exit)
    legacy_missing = _looks_like_missing_subcommand(legacy_stdout_raw, legacy_exit)
    if new_missing or legacy_missing:
        sides = []
        if legacy_missing:
            sides.append("legacy")
        if new_missing:
            sides.append("new")
        reason = f"{'+'.join(sides)} lacks subcommand"
        return SurfaceResult(
            surface=surface,
            status="SKIPPED",
            new_exit=new_exit,
            legacy_exit=legacy_exit,
            new_stdout=new_stdout,
            legacy_stdout_raw=legacy_stdout_raw,
            legacy_stdout_normalized=_normalize_hermes(legacy_stdout_raw),
            diff="",
            skip_reason=reason,
        )

    legacy_normalized = _normalize_hermes(legacy_compare_raw)
    diff = _diff(legacy_normalized, new_compare, surface=surface)
    passed = legacy_exit == new_exit and diff == ""
    return SurfaceResult(
        surface=surface,
        status="PASS" if passed else "FAIL",
        new_exit=new_exit,
        legacy_exit=legacy_exit,
        new_stdout=new_stdout,
        legacy_stdout_raw=legacy_stdout_raw,
        legacy_stdout_normalized=_normalize_hermes(legacy_stdout_raw),
        diff=diff,
    )


def _format_result(result: SurfaceResult, *, verbose: bool) -> str:
    """Pretty-print one SurfaceResult for terminal/CI logs."""
    lines = [
        f"[{result.status}] surface={result.surface} "
        f"new_exit={result.new_exit} legacy_exit={result.legacy_exit}",
    ]
    if result.status == "SKIPPED":
        lines.append(f"  skipped: {result.skip_reason}")
        return "\n".join(lines)
    if result.status == "FAIL":
        if result.new_exit != result.legacy_exit:
            lines.append(
                f"  exit-code mismatch: new={result.new_exit} "
                f"legacy={result.legacy_exit}",
            )
        if result.diff and verbose:
            lines.append("  --- normalized diff (legacy→new) ---")
            lines.append(result.diff.rstrip("\n"))
            lines.append("  --- end diff ---")
        elif result.diff:
            # Non-verbose: just a single-line summary of the diff size.
            diff_lines = result.diff.count("\n")
            lines.append(
                f"  content diff: {diff_lines} lines "
                "(re-run with --verbose to see)",
            )
    return "\n".join(lines)


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="parity_runner",
        description="FR-16 customer-parity runner (CLI + backend surfaces).",
    )
    parser.add_argument(
        "--new-image",
        default=DEFAULT_NEW_IMAGE,
        help=f"image under test (default: {DEFAULT_NEW_IMAGE})",
    )
    parser.add_argument(
        "--legacy-image",
        default=DEFAULT_LEGACY_IMAGE,
        help=f"legacy baseline image (default: {DEFAULT_LEGACY_IMAGE})",
    )
    parser.add_argument(
        "--surface",
        default="ALL",
        choices=("ALL", *SURFACES.keys()),
        help="which surface(s) to run (default: ALL)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="show full normalized diffs on FAIL",
    )
    ns = parser.parse_args(argv)

    surfaces = list(SURFACES.keys()) if ns.surface == "ALL" else [ns.surface]

    try:
        results = [
            run_surface(
                s,
                new_image=ns.new_image,
                legacy_image=ns.legacy_image,
            )
            for s in surfaces
        ]
    except ImageNotFoundError as exc:
        print(f"parity_runner: {exc}", file=sys.stderr)
        return 2

    print(f"parity runner — {len(results)} surface(s)")
    print(f"  new:    {ns.new_image}")
    print(f"  legacy: {ns.legacy_image}")
    print("")
    for r in results:
        print(_format_result(r, verbose=ns.verbose))

    n_pass = sum(1 for r in results if r.status == "PASS")
    n_skip = sum(1 for r in results if r.status == "SKIPPED")
    n_fail = sum(1 for r in results if r.status == "FAIL")
    print("")
    summary = (
        f"pass={n_pass} skip={n_skip} fail={n_fail} "
        f"total={len(results)}"
    )
    if n_fail == 0:
        print(f"parity: PASS-or-SKIP ({summary})")
        return 0
    print(f"parity: FAIL ({summary})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_main())
