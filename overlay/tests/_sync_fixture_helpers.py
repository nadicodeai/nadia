"""overlay/tests/_sync_fixture_helpers.py — shared scaffolding for the
sync-fixture integration tests (``test_sync_fixture.py`` and
``test_sync_fixture_ac3.py``).

These helpers are deliberately small and self-contained: they wrap
``subprocess.run`` with text/utf-8 wiring, build a signing-free git
environment, and unpack the zstd-compressed baseline tarballs that the
fixtures ship. They reference no hermes-/argo-specific identifiers, so
they survive the rename engine unchanged when the overlay ships into
``dist/argo/tests/``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Invoke *cmd* in *cwd* with text/utf-8 wiring.

    Captures stdout+stderr. When *check* is True, raises
    :class:`AssertionError` on non-zero exit with cwd/stdout/stderr in
    the message — the integration-test convention used by both
    ``test_sync_fixture.py`` and ``test_sync_fixture_ac3.py``.
    """
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\n"
            f"cwd: {cwd}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def git_env_no_signing() -> dict[str, str]:
    """Return a copy of ``os.environ`` with git signing/identity neutralised.

    Used by integration tests so a developer's global ``user.signingkey``
    or commit.gpgsign setting cannot leak into the test repos.
    """
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "argo-test",
            "GIT_AUTHOR_EMAIL": "argo-test@example.invalid",
            "GIT_COMMITTER_NAME": "argo-test",
            "GIT_COMMITTER_EMAIL": "argo-test@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    return env


def extract_baseline_tree(tarball: Path, dest: Path) -> None:
    """Extract a zstd-compressed baseline tarball into *dest*.

    ``dest`` is created if it does not already exist. The tarball is
    decoded via ``tar --use-compress-program=unzstd`` so the host must
    have either ``unzstd`` or ``zstd`` on PATH (the integration tests
    skip themselves otherwise).
    """
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "tar",
            "--use-compress-program=unzstd",
            "-xf",
            str(tarball),
            "-C",
            str(dest),
        ],
        check=True,
    )
