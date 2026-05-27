#!/usr/bin/env python3
"""tools/parity_runner.py — FR-16 / AC-7 customer-parity gate.

Runs the new image and the legacy image through the same CLI surfaces
side-by-side, normalizes the legacy output by substituting hermes→argo
(case-preserving), and diffs the normalized legacy stdout against the
new image's raw stdout. Any non-empty diff is a regression.

Surfaces in scope for M6.2a (CLI only):

1. ``argo --help``       — top-level help (long, multi-screen).
2. ``argo --version``    — short version banner.
3. ``argo doctor --static`` — static leakage scan (M3 spec target; both
   images currently exit 2 with ``--static`` unrecognized, which is fine
   as long as both behave identically).

Surfaces 4-7 (API server, MCP, hooks, OAuth, session persistence) are
M6.2b scope and require fixtures and stubs.

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

- 0: all in-scope surfaces report PASS.
- 1: at least one surface failed (content diff or exit-code mismatch).
- 2: structural / environment error (image not pullable, docker missing).
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence

DEFAULT_NEW_IMAGE = "ghcr.io/nadicodeai/argo:dev"
DEFAULT_LEGACY_IMAGE = "ghcr.io/nadicodeai/argo-agent:latest"

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

# Surface name → invocation spec for both images.
#
# For the new image (no ENTRYPOINT, CMD=argo) we pass the full
# ``argo <subcommand…>``. For the legacy image (ENTRYPOINT runs an
# init script and ends with ``exec hermes "$@"``) we bypass with
# ``--entrypoint hermes`` and pass only the subcommand args.
@dataclass(frozen=True)
class _SurfaceSpec:
    """How to invoke one surface against both images."""

    new_args: tuple[str, ...]
    legacy_entrypoint: str
    legacy_args: tuple[str, ...]


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
    """One surface's parity outcome."""

    surface: str
    passed: bool
    new_exit: int
    legacy_exit: int
    new_stdout: str
    legacy_stdout_raw: str
    legacy_stdout_normalized: str
    diff: str  # empty if passed


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
) -> tuple[int, str]:
    """Run a one-shot command in ``image`` and capture stdout + exit code.

    stderr is merged into the captured stream because argparse error
    paths (``hermes: error: unrecognized arguments: --static``) print to
    stderr but ARE part of the surface contract — parity must catch
    drift in those messages too.
    """
    cmd: list[str] = ["docker", "run", "--rm"]
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

    new_exit, new_stdout = _docker_run(
        new_image,
        entrypoint=None,
        args=spec.new_args,
    )
    legacy_exit, legacy_stdout_raw = _docker_run(
        legacy_image,
        entrypoint=spec.legacy_entrypoint,
        args=spec.legacy_args,
    )
    legacy_normalized = _normalize_hermes(legacy_stdout_raw)
    diff = _diff(legacy_normalized, new_stdout, surface=surface)
    passed = legacy_exit == new_exit and diff == ""
    return SurfaceResult(
        surface=surface,
        passed=passed,
        new_exit=new_exit,
        legacy_exit=legacy_exit,
        new_stdout=new_stdout,
        legacy_stdout_raw=legacy_stdout_raw,
        legacy_stdout_normalized=legacy_normalized,
        diff=diff,
    )


def _format_result(result: SurfaceResult, *, verbose: bool) -> str:
    """Pretty-print one SurfaceResult for terminal/CI logs."""
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"[{status}] surface={result.surface} "
        f"new_exit={result.new_exit} legacy_exit={result.legacy_exit}",
    ]
    if not result.passed:
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
        description="FR-16 customer-parity runner (CLI surfaces, M6.2a).",
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

    n_fail = sum(1 for r in results if not r.passed)
    print("")
    if n_fail == 0:
        print(f"parity: PASS ({len(results)}/{len(results)} surfaces)")
        return 0
    print(
        f"parity: FAIL ({n_fail}/{len(results)} surfaces regressed)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(_main())
