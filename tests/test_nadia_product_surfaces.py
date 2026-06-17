"""Product-surface checks for Nadia Agent distribution metadata."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "dist" / "nadia"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_desktop_bundle_metadata_identifies_nadia_agent() -> None:
    package = _read_json(DIST / "apps" / "desktop" / "package.json")
    build = package["build"]

    assert package["productName"] == "Nadia Agent"
    assert package["author"] == "NadicodeAI"
    assert build["appId"] == "ai.nadicode.nadia"
    assert build["productName"] == "Nadia Agent"
    assert build["executableName"] == "Nadia Agent"
    assert build["protocols"][0]["name"] == "Nadia Agent Protocol"
    assert build["artifactName"] == "Nadia-Agent-${version}-${os}-${arch}.${ext}"
    assert build["mac"]["extendInfo"]["CFBundleDisplayName"] == "Nadia Agent"
    assert build["mac"]["extendInfo"]["CFBundleName"] == "Nadia Agent"
    assert build["dmg"]["title"] == "Install Nadia Agent"
    assert build["win"]["legalTrademarks"] == "Nadia Agent"
    assert build["nsis"]["shortcutName"] == "Nadia Agent"
    assert build["nsis"]["uninstallDisplayName"] == "Nadia Agent"
    assert build["linux"]["maintainer"] == "NadicodeAI <support@nadicode.ai>"


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_windows_exe_resource_metadata_identifies_nadia_agent() -> None:
    resource_script = (
        DIST / "apps" / "desktop" / "scripts" / "set-exe-identity.cjs"
    ).read_text(encoding="utf-8")

    assert "ProductName: 'Nadia Agent'" in resource_script
    assert "FileDescription: 'Nadia Agent'" in resource_script
    assert "CompanyName: 'NadicodeAI'" in resource_script
    assert "LegalCopyright: 'Copyright (c) 2026 NadicodeAI'" in resource_script
    assert "ProductName: 'Hermes'" not in resource_script
    assert "CompanyName: 'Nous Research'" not in resource_script


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_bootstrap_installer_metadata_identifies_nadia_agent_setup() -> None:
    package = _read_json(DIST / "apps" / "bootstrap-installer" / "package.json")
    conf = _read_json(
        DIST / "apps" / "bootstrap-installer" / "src-tauri" / "tauri.conf.json"
    )
    cargo = tomllib.loads(
        (DIST / "apps" / "bootstrap-installer" / "src-tauri" / "Cargo.toml").read_text(
            encoding="utf-8"
        )
    )

    assert package["description"].startswith("Nadia Agent Setup,")
    assert cargo["package"]["description"].startswith("Nadia Agent Setup,")
    assert cargo["package"]["authors"] == ["NadicodeAI <support@nadicode.ai>"]
    assert conf["productName"] == "Nadia Agent Setup"
    assert conf["identifier"] == "ai.nadicode.nadia.setup"
    assert conf["app"]["windows"][0]["title"] == "Nadia Agent Setup"
    assert conf["bundle"]["shortDescription"] == "Nadia Agent Setup"
    assert conf["bundle"]["publisher"] == "NadicodeAI"
    assert conf["bundle"]["copyright"] == "Copyright © 2026 NadicodeAI"


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_profile_builder_is_nadia_branded() -> None:
    page = (DIST / "web" / "src" / "pages" / "ProfileBuilderPage.tsx").read_text(
        encoding="utf-8"
    )

    assert "<H2>New Nadia profile</H2>" in page
    assert 'placeholder="What this Nadia profile is for"' in page
    assert "Argo" not in page
    assert "argo" not in page
    assert "Hermes" not in page
    assert "hermes" not in page
