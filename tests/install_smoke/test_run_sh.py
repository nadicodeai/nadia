"""Pytest wrapper for the install-smoke harness (M5.2).

Spec: ``.shepherd/install-update/spec.md`` § IU-AC-4, IU-AC-5, IU-AC-9,
IU-AC-15. Plan: ``.shepherd/install-update/plan.md`` § M5.2.

This is a *thin* wrapper. The actual assertion machinery lives inside
``tests/install_smoke/run.sh`` so the same harness drives both
``make install-smoke`` (developer workflow) and CI (the install-smoke
GitHub Actions job). All this test does is shell out, wait, and bubble
up exit-code + tail-of-output on failure.

Marked ``slow`` because a clean Docker pull + apt update + uv venv +
git clone routinely runs 1-4 minutes; the default pytest.ini timeout
(30s) does not apply here (we pass our own 900s timeout to
``subprocess.run``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RUN_SH = REPO_ROOT / "tests" / "install_smoke" / "run.sh"


@pytest.mark.slow
@pytest.mark.timeout(900)  # default pytest.ini timeout is 30s; this harness is Docker-heavy
def test_install_smoke_run_sh_exits_zero() -> None:
    """`bash tests/install_smoke/run.sh` exits 0 on a local release dry run."""
    if os.environ.get("SKIP_DOCKER_SMOKE") == "1":
        pytest.skip("SKIP_DOCKER_SMOKE=1 set; skipping Docker-driven smoke test")
    if shutil.which("docker") is None:
        pytest.skip("docker not on PATH; skipping install-smoke")

    assert RUN_SH.is_file(), f"run.sh missing at {RUN_SH}"

    result = subprocess.run(
        ["bash", str(RUN_SH)],
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        check=False,
    )

    if result.returncode != 0:
        # Surface the last ~60 lines on failure so CI logs are actionable.
        tail = "\n".join(result.stdout.splitlines()[-60:])
        pytest.fail(
            f"install-smoke run.sh exited {result.returncode}\n"
            f"--- last 60 lines of output ---\n{tail}\n"
        )
