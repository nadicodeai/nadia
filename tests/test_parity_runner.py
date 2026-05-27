"""tests/test_parity_runner.py — unit + integration tests for parity_runner.

Default suite (no marker) covers pure-Python behavior — normalization
mapping, diff function, exit-code mismatch detection — without invoking
docker. The single ``@pytest.mark.integration`` test drives the real
runner against the locally-built ``:dev`` and locally-pulled legacy
``:latest`` images; it skips gracefully if either is missing so the
default ``pytest tests/`` run never depends on the local docker state.

Baseline image note
-------------------

M6 uses ``ghcr.io/nadicodeai/argo-agent:latest`` as the parity baseline
because the ``:0.14.0`` tag referenced in ``.shepherd/spec.md`` was
never pushed to GHCR. The legacy repository's pyproject.toml does
report version 0.14.0, so ``:latest`` is functionally equivalent in
intent — but in practice the ``:latest`` image as pulled at the time
M6.2a landed reports ``Hermes Agent v0.8.0``, indicating the legacy
publisher never tagged v0.14.0 either. If a future legacy release
publishes a real ``:0.14.0`` tag, update spec FR-16 and the runner's
``DEFAULT_LEGACY_IMAGE`` accordingly and re-pin AC-7's gate.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "tools" / "parity_runner.py"

# Import the runner module directly so we can unit-test the helpers
# without round-tripping through subprocess. tools/ is not a package,
# so we extend sys.path here.
sys.path.insert(0, str(REPO_ROOT / "tools"))
import parity_runner  # noqa: E402


# ---------------------------------------------------------------------------
# Pure-Python tests — no docker, run by default.
# ---------------------------------------------------------------------------


def test_normalization_case_preserving() -> None:
    """``hermes``/``Hermes``/``HERMES`` map to the right case-preserving forms."""
    assert parity_runner._normalize_hermes("Hermes Agent") == "Argo Agent"
    assert parity_runner._normalize_hermes("hermes_cli") == "argo_cli"
    assert parity_runner._normalize_hermes("HERMES_HOME") == "ARGO_HOME"
    assert parity_runner._normalize_hermes("hermes-agent") == "argo-agent"
    assert parity_runner._normalize_hermes("HermesAgent") == "ArgoAgent"
    assert parity_runner._normalize_hermes("hermes: error: x") == "argo: error: x"


def test_normalization_keeps_unmapped_strings() -> None:
    """Text without any hermes-prefix variant is untouched."""
    untouched = "the quick brown fox jumps over 0xDEADBEEF\n"
    assert parity_runner._normalize_hermes(untouched) == untouched
    # Strings that merely contain ``argo`` (the target) are likewise inert.
    assert parity_runner._normalize_hermes("argo --version") == "argo --version"


def test_normalization_is_idempotent() -> None:
    """Applying the substitution twice equals applying it once."""
    src = (
        "Hermes Agent v0.8.0\n"
        "Project: /opt/hermes\n"
        "hermes: error: unrecognized arguments: --static\n"
        "HERMES_HOME=/opt/data\n"
    )
    once = parity_runner._normalize_hermes(src)
    twice = parity_runner._normalize_hermes(once)
    assert once == twice


def test_normalization_handles_composite_before_bare() -> None:
    """Longer composites must shadow ``hermes`` so we don't double-rewrite."""
    # If the engine applied ``hermes → argo`` before ``hermes_cli → argo_cli``
    # the latter would never fire and the output would have ``argo_cli`` only
    # via the bare rule; for ``hermes_tools_mcp_server`` the bare rule would
    # produce ``argo_tools_mcp_server`` correctly too — but for asymmetric
    # mappings like ``HERMES_HOME → ARGO_HOME`` the composite MUST win.
    assert (
        parity_runner._normalize_hermes("export HERMES_HOME=/x")
        == "export ARGO_HOME=/x"
    )
    assert (
        parity_runner._normalize_hermes("from hermes_tools_mcp_server import x")
        == "from argo_tools_mcp_server import x"
    )


def test_diff_empty_on_match() -> None:
    """``_diff`` returns empty string when normalized legacy == new."""
    legacy = "Argo Agent v0.14.0\nProject: /opt/argo\n"
    new = "Argo Agent v0.14.0\nProject: /opt/argo\n"
    assert parity_runner._diff(legacy, new, surface="version") == ""


def test_diff_nonempty_on_mismatch() -> None:
    """``_diff`` returns a unified diff string with file headers on mismatch."""
    legacy = "Argo Agent v0.8.0\n"
    new = "Argo Agent v0.14.0\n"
    out = parity_runner._diff(legacy, new, surface="version")
    assert out != ""
    assert "legacy(normalized):version" in out
    assert "new:version" in out
    assert "-Argo Agent v0.8.0" in out
    assert "+Argo Agent v0.14.0" in out


def test_diff_after_normalization_matches() -> None:
    """End-to-end: legacy raw → normalize → diff vs new → empty when content
    only differs by brand-string."""
    legacy_raw = "Hermes Agent v0.14.0 (2026.5.16)\nProject: /opt/hermes\n"
    new_raw = "Argo Agent v0.14.0 (2026.5.16)\nProject: /opt/argo\n"
    legacy_normalized = parity_runner._normalize_hermes(legacy_raw)
    assert parity_runner._diff(legacy_normalized, new_raw, surface="x") == ""


def test_parity_error_hierarchy() -> None:
    """Subclasses all extend ``ParityError`` which extends ``RuntimeError``."""
    assert issubclass(parity_runner.ParityError, RuntimeError)
    assert issubclass(parity_runner.ImageNotFoundError, parity_runner.ParityError)
    assert issubclass(
        parity_runner.ExitCodeMismatchError, parity_runner.ParityError
    )
    assert issubclass(parity_runner.ContentDiffError, parity_runner.ParityError)


def test_surfaces_in_scope() -> None:
    """M6.2a defines exactly three CLI surfaces."""
    assert set(parity_runner.SURFACES) == {"help", "version", "doctor-static"}


def test_runner_help_succeeds() -> None:
    """``python tools/parity_runner.py --help`` returns 0 and lists surfaces."""
    res = subprocess.run(
        [sys.executable, str(RUNNER), "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "FR-16" in res.stdout
    assert "--new-image" in res.stdout
    assert "--legacy-image" in res.stdout
    assert "doctor-static" in res.stdout


def test_runner_rejects_unknown_surface() -> None:
    """argparse choices reject unknown --surface; exit 2."""
    res = subprocess.run(
        [sys.executable, str(RUNNER), "--surface", "not-a-surface"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 2
    assert "invalid choice" in res.stderr


def test_runner_image_not_found_exits_2() -> None:
    """A bogus ``--new-image`` produces a structural exit 2, not 1."""
    res = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--surface",
            "version",
            "--new-image",
            "ghcr.io/nadicodeai/this-image-definitely-does-not-exist:nope",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 2
    assert "not present locally" in res.stderr


# ---------------------------------------------------------------------------
# Integration test — exercises the real runner against real images.
# ---------------------------------------------------------------------------


def _docker_image_present(image: str) -> bool:
    """True iff ``image`` is locally available (no pull attempted)."""
    res = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return res.returncode == 0


@pytest.mark.integration
def test_parity_runner_against_real_images() -> None:
    """Drive every CLI surface against the locally-available images.

    Skips when either image is missing (CI is responsible for pulling /
    building before invoking this gate). When both images are present
    the runner MUST produce a per-surface report; AC-7 will eventually
    require exit 0, but the current legacy ``:latest`` is older than
    the new ``:dev`` so non-zero is expected until the baseline tag is
    re-pinned (see module docstring).
    """
    new_image = parity_runner.DEFAULT_NEW_IMAGE
    legacy_image = parity_runner.DEFAULT_LEGACY_IMAGE
    if not _docker_image_present(new_image):
        pytest.skip(f"{new_image} not present; run `make image` first")
    if not _docker_image_present(legacy_image):
        pytest.skip(f"{legacy_image} not present; `docker pull` first")

    res = subprocess.run(
        [sys.executable, str(RUNNER), "--verbose"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    # The runner MUST print one [PASS|FAIL] line per surface regardless
    # of outcome; that's the contract that gates AC-7 for CLI surfaces.
    assert "surface=help" in res.stdout
    assert "surface=version" in res.stdout
    assert "surface=doctor-static" in res.stdout
    # Exit code is 0 (all pass) or 1 (regression). Anything else (2)
    # would be a structural failure, which means the gate itself is
    # broken — fail the test in that case.
    assert res.returncode in (0, 1), (
        f"runner returned structural-error exit {res.returncode}; "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )
