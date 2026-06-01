"""Contracts for the forward-deployed golden VM helper scripts."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BAKE_SCRIPT = REPO_ROOT / "scripts" / "golden-vm-bake.sh"
INIT_SCRIPT = REPO_ROOT / "scripts" / "argo-customer-init"


def _run_script(script: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [str(script), *args],
        cwd=REPO_ROOT,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_bake_script_declares_fde_dependency_surface() -> None:
    result = _run_script(BAKE_SCRIPT, "--print-python-packages")

    assert result.returncode == 0, result.stderr
    packages = set(result.stdout.splitlines())
    assert {
        "honcho-ai==2.0.1",
        "python-telegram-bot[webhooks]==22.6",
        "edge-tts==7.2.7",
        "ddgs",
    }.issubset(packages)
    assert all("TOKEN" not in package.upper() for package in packages)


def test_bake_dry_run_disables_runtime_lazy_installs(tmp_path: Path) -> None:
    argo_home = tmp_path / "argo-home"
    install_dir = tmp_path / "argo-install"
    result = _run_script(
        BAKE_SCRIPT,
        "--dry-run",
        "--skip-argo-install",
        "--skip-os-packages",
        "--skip-browser",
        env={
            "ARGO_HOME": str(argo_home),
            "ARGO_INSTALL_DIR": str(install_dir),
        },
    )

    assert result.returncode == 0, result.stderr
    assert f"write {argo_home}/config.yaml security.allow_lazy_installs=false" in result.stdout
    assert "honcho-ai==2.0.1" in result.stdout
    assert "python-telegram-bot[webhooks]==22.6" in result.stdout


def test_customer_init_writes_profile_local_files(tmp_path: Path) -> None:
    argo_home = tmp_path / "argo-home"
    profile_home = argo_home / "profiles" / "acme-prod"
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "argo.log"
    bin_dir.mkdir()
    argo_home.mkdir()
    (argo_home / "SOUL.md.template").write_text(
        "Customer: {{PROFILE}}\nWorkspace: {{HONCHO_WORKSPACE}}\n",
        encoding="utf-8",
    )
    (argo_home / "honcho.json.template").write_text(
        json.dumps({"environment": "customer"}),
        encoding="utf-8",
    )
    fake_argo = bin_dir / "argo"
    fake_argo.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            printf '%s\n' "$*" >> "${ARGO_FAKE_LOG}"
            if [ "${1:-}" = "profile" ] && [ "${2:-}" = "create" ]; then
                mkdir -p "${ARGO_HOME}/profiles/${3}"
            fi
            exit 0
            """
        ),
        encoding="utf-8",
    )
    fake_argo.chmod(fake_argo.stat().st_mode | stat.S_IXUSR)

    result = _run_script(
        INIT_SCRIPT,
        "--profile",
        "acme-prod",
        "--honcho-workspace",
        "acme-workspace",
        "--honcho-peer",
        "fde-01",
        "--honcho-api-key",
        "honcho-secret",
        "--telegram-token",
        "123456789:abcdefghijklmnopqrstuvwxyzABCDE",
        "--telegram-allowed-users",
        "42,84",
        "--telegram-home-channel",
        "-10012345",
        "--skip-gateway",
        "--yes",
        env={
            "ARGO_HOME": str(argo_home),
            "ARGO_FAKE_LOG": str(log_path),
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        },
    )

    assert result.returncode == 0, result.stderr
    assert profile_home.is_dir()
    config = yaml.safe_load((profile_home / "config.yaml").read_text(encoding="utf-8"))
    assert config["memory"]["provider"] == "honcho"
    assert config["security"]["allow_lazy_installs"] is False
    assert config["gateway"]["platform"] == "telegram"

    honcho = json.loads((profile_home / "honcho.json").read_text(encoding="utf-8"))
    assert honcho["apiKey"] == "honcho-secret"
    assert honcho["workspace"] == "acme-workspace"
    assert honcho["peerName"] == "fde-01"
    assert honcho["environment"] == "customer"

    env_text = (profile_home / ".env").read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN=123456789:abcdefghijklmnopqrstuvwxyzABCDE" in env_text
    assert "TELEGRAM_ALLOWED_USERS=42,84" in env_text
    assert "TELEGRAM_HOME_CHANNEL=-10012345" in env_text
    assert oct((profile_home / ".env").stat().st_mode & 0o777) == "0o600"

    soul_text = (profile_home / "SOUL.md").read_text(encoding="utf-8")
    assert "Customer: acme-prod" in soul_text
    assert "Workspace: acme-workspace" in soul_text
    assert "profile create acme-prod" in log_path.read_text(encoding="utf-8")


def test_customer_init_rejects_missing_required_values(tmp_path: Path) -> None:
    result = _run_script(
        INIT_SCRIPT,
        "--profile",
        "missing-secrets",
        "--yes",
        "--skip-gateway",
        env={"ARGO_HOME": str(tmp_path / "argo-home")},
    )

    assert result.returncode == 2
    assert "missing required value" in result.stderr
