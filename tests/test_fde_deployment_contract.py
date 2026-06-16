"""Contracts for the customer FDE deployment modalities."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_fde_python_package_surface_is_shared_across_modalities() -> None:
    provision = _read("scripts/nadia-fde-provision.sh")
    provision_ps1 = _read("scripts/nadia-fde-provision.ps1")
    dockerfile = _read("Dockerfile")

    for package in (
        "honcho-ai==2.0.1",
        "python-telegram-bot[webhooks]==22.6",
        "edge-tts==7.2.7",
        "ddgs",
    ):
        assert package in provision
        assert package in provision_ps1
        assert package in dockerfile


def test_build_copies_fde_helpers_to_release_scripts_tree() -> None:
    build_py = _read("tools/build.py")

    for script in (
        "nadia-fde-provision.sh",
        "nadia-fde-provision.ps1",
        "nadia-customer-init",
        "nadia-customer-init.ps1",
    ):
        assert script in build_py
    assert "_copy_fde_scripts()" in build_py


def test_makefile_exposes_customer_deployment_targets() -> None:
    makefile = _read("Makefile")

    for target in (
        "fde-container:",
        "fde-container-smoke:",
        "fde-vm-image:",
        "fde-live-smoke:",
        "golden-vm-qemu-smoke:",
    ):
        assert target in makefile


def test_vm_artifact_target_preserves_qcow2_and_real_qemu_contract() -> None:
    image_script = _read("scripts/fde-vm-image.sh")
    qemu_script = _read("tests/golden_vm/run_qemu.sh")
    qemu_inner = _read("tests/golden_vm/qemu_inner.sh")

    assert "nadia-fde-ubuntu-22.04.qcow2" in image_script
    assert "--artifact-dir" in qemu_script
    assert "qemu-system-x86_64" in qemu_inner
    assert "create customer clone from golden disk" in qemu_inner


def test_live_acceptance_requires_real_telegram_and_honcho_credentials() -> None:
    live = _read("tests/fde_live/run.sh")

    assert "FDE_HONCHO_API_KEY" in live
    assert "FDE_TELEGRAM_BOT_TOKEN" in live
    assert "FDE_TELEGRAM_ALLOWED_USERS" in live
    assert "exit 77" in live
    assert "nadia -p \"${PROFILE}\" honcho status" in live
    assert "nadia -p \"${PROFILE}\" gateway status" in live
