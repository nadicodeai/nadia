"""Product-surface checks for Nadia Agent distribution metadata."""

from __future__ import annotations

import json
import hashlib
import struct
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST = REPO_ROOT / "dist" / "nadia"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


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
    assert build["icon"] == "assets/nadia-icon"
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
def test_desktop_packaging_paths_follow_nadia_agent_name() -> None:
    desktop_test = (
        DIST / "apps" / "desktop" / "scripts" / "test-desktop.mjs"
    ).read_text(encoding="utf-8")
    desktop_main = (DIST / "apps" / "desktop" / "electron" / "main.cjs").read_text(
        encoding="utf-8"
    )
    bootstrap = (
        DIST
        / "apps"
        / "bootstrap-installer"
        / "src-tauri"
        / "src"
        / "bootstrap.rs"
    ).read_text(encoding="utf-8")
    update = (
        DIST / "apps" / "bootstrap-installer" / "src-tauri" / "src" / "update.rs"
    ).read_text(encoding="utf-8")
    uninstall = (
        DIST / "apps" / "desktop" / "electron" / "desktop-uninstall.cjs"
    ).read_text(encoding="utf-8")
    cli_main = (DIST / "nadia_cli" / "main.py").read_text(encoding="utf-8")
    cli_uninstall = (DIST / "nadia_cli" / "gui_uninstall.py").read_text(
        encoding="utf-8"
    )
    install_sh = (DIST / "scripts" / "install.sh").read_text(encoding="utf-8")
    bootstrap_runner = (
        DIST / "apps" / "desktop" / "electron" / "bootstrap-runner.cjs"
    ).read_text(encoding="utf-8")

    assert "Nadia Agent.app" in desktop_test
    assert "Nadia Agent.exe" in desktop_test
    assert "Nadia-Agent-${PACKAGE_JSON.version}" in desktop_test
    assert "Nadia.app" not in desktop_test
    assert "Nadia.exe" not in desktop_test
    assert "Nadia-${PACKAGE_JSON.version}" not in desktop_test

    assert "Nadia Agent.app" in desktop_main
    assert "'Nadia.app'" not in desktop_main

    assert "Nadia Agent.app" in bootstrap
    assert "Nadia Agent.exe" in bootstrap
    assert "Nadia.app" not in bootstrap
    assert "Nadia.exe" not in bootstrap

    assert "Nadia Agent.app" in update
    assert 'for image in ["nadia.exe", "Nadia Agent.exe"]' in update
    assert "Nadia.app" not in update

    assert "Nadia Agent.exe" in uninstall
    assert "Nadia Agent$/i.test(dir)" in uninstall
    assert "Hermes" not in uninstall

    assert "Nadia Agent.app/Contents/MacOS/Nadia Agent" in cli_main
    assert '"win-unpacked" / "Nadia Agent.exe"' in cli_main
    assert '"linux-unpacked" / "Nadia Agent"' in cli_main
    assert "Nadia.app/Contents/MacOS/Nadia" not in cli_main
    assert "Nadia.exe" not in cli_main

    assert "/Applications/Nadia Agent.app" in cli_uninstall
    assert '"Programs" / "Nadia Agent"' in cli_uninstall
    assert '"Nadia Agent"' in cli_uninstall
    assert "/Applications/Nadia.app" not in cli_uninstall

    assert "apps/desktop -> Nadia Agent.app" in install_sh
    assert "linux-unpacked/Nadia Agent" in install_sh
    assert "mac-arm64/Nadia Agent.app" in install_sh
    assert "apps/desktop -> Nadia.app" not in install_sh
    assert "mac-arm64/Nadia.app" not in install_sh

    assert "const DESKTOP_INSTALL_BRANCH = 'release'" in bootstrap_runner
    assert (
        "raw.githubusercontent.com/nadicodeai/nadia/${DESKTOP_INSTALL_BRANCH}/scripts/${scriptName}"
        in bootstrap_runner
    )
    assert (
        "raw.githubusercontent.com/nadicodeai/nadia/${commit}/scripts/${scriptName}"
        not in bootstrap_runner
    )
    assert "args.push('--commit', installStamp.commit)" not in bootstrap_runner
    assert "args.push('-Commit', installStamp.commit)" not in bootstrap_runner


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_live_product_chrome_identifies_nadicodeai_not_nous() -> None:
    rels = [
        "nadia_cli/banner.py",
        "ui-tui/src/components/branding.tsx",
        "nadia_cli/dashboard_auth/login_page.py",
        "web/src/components/SidebarFooter.tsx",
    ]
    combined = "\n".join((DIST / rel).read_text(encoding="utf-8") for rel in rels)

    assert "Nadia Agent by NadicodeAI" in combined
    assert "NadicodeAI" in combined
    assert "Based on Hermes Agent by Nous Research" not in combined
    assert "Nadia Agent by Nous Research" not in combined
    assert "An AI agent from NadicodeAI" not in combined


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_desktop_app_icons_use_canonical_nadia_face() -> None:
    expected_hashes = {
        "apps/desktop/assets/nadia-icon.png": "3458cb7c0fd80634390b6bd413eaffab7607bdd0f2794460c2c5417444001301",
        "apps/desktop/assets/nadia-icon.ico": "6cbe729ad7bf502f26bc23aaec63032d43569e4c25fc6dc95d56d15518f27523",
        "apps/desktop/assets/nadia-icon.icns": "19e648e6c6253eaefcb81299a96f3be9835514fdfd99ec83d2e822affdfde710",
        "apps/desktop/public/nadia-apple-touch-icon.png": "e8a56daa5e8a94dec15770dfacfbd591034fcf768c49e5fb64c0e1a20d828bd8",
    }

    for rel, digest in expected_hashes.items():
        assert _sha256(DIST / rel) == digest

    assert _png_size(DIST / "apps" / "desktop" / "assets" / "nadia-icon.png") == (
        1024,
        1024,
    )
    assert _png_size(
        DIST / "apps" / "desktop" / "public" / "nadia-apple-touch-icon.png"
    ) == (180, 180)


@pytest.mark.skipif(not DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_customer_install_and_download_links_are_nadia_owned() -> None:
    rels = [
        "README.md",
        "README.zh-CN.md",
        "README.ur-pk.md",
        "apps/desktop/README.md",
        "website/docusaurus.config.ts",
        "website/docs/index.mdx",
        "website/docs/getting-started/installation.md",
        "website/docs/getting-started/quickstart.md",
        "website/docs/reference/faq.md",
        "website/docs/guides/run-nemotron-3-ultra-free.md",
        "skills/autonomous-ai-agents/nadia-agent/SKILL.md",
        "scripts/install.sh",
        "scripts/install.ps1",
        "scripts/install.cmd",
    ]
    combined = "\n".join((DIST / rel).read_text(encoding="utf-8") for rel in rels)

    assert "https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/install.sh" in combined
    assert "https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/install.ps1" in combined
    assert "https://github.com/nadicodeai/nadia/releases/latest" in combined
    assert "https://docs.nadicode.ai/nadia" in combined

    assert "hermes-agent.nousresearch.com/install.sh" not in combined
    assert "hermes-agent.nousresearch.com/install.ps1" not in combined
    assert "hermes-agent.nousresearch.com/desktop" not in combined
    assert "hermes-agent.nousresearch.com/docs" not in combined
    assert "NousResearch/nadia-agent" not in combined


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
