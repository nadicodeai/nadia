#!/usr/bin/env bash
# Provision the shared Forward Deployed Engineer baseline on Linux or macOS.

set -euo pipefail

ARGO_HOME="${ARGO_HOME:-${HOME}/.argo}"
ARGO_INSTALL_DIR="${ARGO_INSTALL_DIR:-}"
INSTALL_URL="${ARGO_INSTALL_URL:-https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh}"

DRY_RUN=0
SKIP_ARGO_INSTALL=0
SKIP_OS_PACKAGES=1
SKIP_BROWSER=0
INSTALL_INIT=1
PRINT_PACKAGES=0
DISABLE_LAZY_INSTALLS=1

FDE_PYTHON_PACKAGES=(
    "honcho-ai==2.0.1"
    "python-telegram-bot[webhooks]==22.6"
    "edge-tts==7.2.7"
    "ddgs"
)

FDE_APT_PACKAGES=(
    ca-certificates
    curl
    git
    ffmpeg
    ripgrep
    xz-utils
    procps
    openssh-client
    make
    gcc
    g++
    python3
    python3-dev
    python3-venv
    python3-pip
    libffi-dev
)

usage() {
    cat <<'USAGE'
Usage: scripts/argo-fde-provision.sh [options]

Installs the shared customer deployment baseline:
Argo, Honcho, Telegram, Edge TTS, ddgs, customer templates, argo-customer-init,
and security.allow_lazy_installs=false.

Options:
  --dry-run                 Print actions without changing the machine.
  --print-python-packages   Print the Python package surface and exit.
  --with-os-packages        Install Ubuntu/Debian apt package baseline.
  --skip-argo-install       Do not run the public Argo installer.
  --skip-browser            Skip browser/node provisioning in this pass.
  --skip-init-install       Do not install argo-customer-init onto PATH.
  --allow-lazy-installs     Do not force security.allow_lazy_installs=false.
  -h, --help                Show this help.

Environment:
  ARGO_HOME                 Defaults to ~/.argo.
  ARGO_INSTALL_DIR          Overrides auto-discovery of the Argo venv location.
  ARGO_INSTALL_URL          Overrides the public release install.sh URL.
USAGE
}

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'argo-fde-provision: %s\n' "$*" >&2
    exit "${2:-1}"
}

run() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        printf 'DRY-RUN:'
        printf ' %q' "$@"
        printf '\n'
    else
        "$@"
    fi
}

sudo_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        command -v sudo >/dev/null 2>&1 || die "sudo is required for this action"
        sudo "$@"
    fi
}

run_root() {
    if [ "${DRY_RUN}" -eq 1 ]; then
        printf 'DRY-RUN:'
        if [ "$(id -u)" -ne 0 ]; then
            printf ' sudo'
        fi
        printf ' %q' "$@"
        printf '\n'
    else
        sudo_cmd "$@"
    fi
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --print-python-packages)
            PRINT_PACKAGES=1
            shift
            ;;
        --with-os-packages)
            SKIP_OS_PACKAGES=0
            shift
            ;;
        --skip-argo-install)
            SKIP_ARGO_INSTALL=1
            shift
            ;;
        --skip-browser)
            SKIP_BROWSER=1
            shift
            ;;
        --skip-init-install)
            INSTALL_INIT=0
            shift
            ;;
        --allow-lazy-installs)
            DISABLE_LAZY_INSTALLS=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1" 2
            ;;
    esac
done

if [ "${PRINT_PACKAGES}" -eq 1 ]; then
    printf '%s\n' "${FDE_PYTHON_PACKAGES[@]}"
    exit 0
fi

install_os_packages() {
    [ "${SKIP_OS_PACKAGES}" -eq 0 ] || return 0
    command -v apt-get >/dev/null 2>&1 || die "--with-os-packages currently supports Ubuntu/Debian apt-get only"
    log "install apt package baseline"
    run_root apt-get update
    run_root apt-get install -y --no-install-recommends "${FDE_APT_PACKAGES[@]}"
}

install_argo() {
    [ "${SKIP_ARGO_INSTALL}" -eq 0 ] || return 0
    local tmp_install="/tmp/argo-install.sh"
    log "install Argo from ${INSTALL_URL}"
    run curl -fsSL "${INSTALL_URL}" -o "${tmp_install}"
    run chmod +x "${tmp_install}"
    local install_args=(--skip-setup)
    if [ "${SKIP_BROWSER}" -eq 1 ]; then
        install_args+=(--skip-browser)
    fi
    run bash "${tmp_install}" "${install_args[@]}"
}

discover_install_dir() {
    if [ -n "${ARGO_INSTALL_DIR}" ]; then
        printf '%s\n' "${ARGO_INSTALL_DIR}"
        return 0
    fi
    if [ -d "${ARGO_HOME}/argo-agent" ]; then
        printf '%s\n' "${ARGO_HOME}/argo-agent"
        return 0
    fi
    if [ -d "/usr/local/lib/argo-agent" ]; then
        printf '%s\n' "/usr/local/lib/argo-agent"
        return 0
    fi
    printf '%s\n' "${ARGO_HOME}/argo-agent"
}

python_bin_for_install() {
    local install_dir="$1"
    if [ -x "${install_dir}/venv/bin/python" ]; then
        printf '%s\n' "${install_dir}/venv/bin/python"
        return 0
    fi
    if [ "${DRY_RUN}" -eq 1 ]; then
        printf '%s\n' "${install_dir}/venv/bin/python"
        return 0
    fi
    die "Argo venv python not found at ${install_dir}/venv/bin/python"
}

install_python_packages() {
    local python_bin="$1"
    log "preinstall FDE Python packages"
    for package in "${FDE_PYTHON_PACKAGES[@]}"; do
        log "python package ${package}"
    done
    if [ "${DRY_RUN}" -eq 1 ] || "${python_bin}" -m pip --version >/dev/null 2>&1; then
        run "${python_bin}" -m pip install -U "${FDE_PYTHON_PACKAGES[@]}"
        return 0
    fi
    local uv_bin=""
    if command -v uv >/dev/null 2>&1; then
        uv_bin="$(command -v uv)"
    elif [ -x "${HOME}/.local/bin/uv" ]; then
        uv_bin="${HOME}/.local/bin/uv"
    fi
    if [ -n "${uv_bin}" ]; then
        run "${uv_bin}" pip install --python "${python_bin}" -U "${FDE_PYTHON_PACKAGES[@]}"
        return 0
    fi
    run "${python_bin}" -m ensurepip --upgrade
    run "${python_bin}" -m pip install -U "${FDE_PYTHON_PACKAGES[@]}"
}

write_templates() {
    log "write customer templates under ${ARGO_HOME}"
    if [ "${DRY_RUN}" -eq 1 ]; then
        log "write ${ARGO_HOME}/SOUL.md.template"
        log "write ${ARGO_HOME}/honcho.json.template"
        return 0
    fi
    mkdir -p "${ARGO_HOME}"
    cat >"${ARGO_HOME}/SOUL.md.template" <<'EOF'
# Customer Operating Context

Profile: {{PROFILE}}
Honcho workspace: {{HONCHO_WORKSPACE}}
Honcho peer: {{HONCHO_PEER}}

Use this file for customer-specific operating context, preferences, boundaries,
and escalation notes. Do not put long-lived secrets here.
EOF
    cat >"${ARGO_HOME}/honcho.json.template" <<'EOF'
{
  "aiPeer": "argo",
  "contextCadence": 1,
  "dialecticCadence": 2,
  "dialecticDepth": 1,
  "environment": "production",
  "pinUserPeer": true,
  "recallMode": "hybrid",
  "writeFrequency": "async"
}
EOF
}

write_lazy_policy() {
    local python_bin="$1"
    [ "${DISABLE_LAZY_INSTALLS}" -eq 1 ] || return 0
    log "write ${ARGO_HOME}/config.yaml security.allow_lazy_installs=false"
    if [ "${DRY_RUN}" -eq 1 ]; then
        return 0
    fi
    mkdir -p "${ARGO_HOME}"
    "${python_bin}" - "${ARGO_HOME}/config.yaml" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

path = Path(sys.argv[1])
data = {}
if path.exists():
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
if not isinstance(data, dict):
    data = {}
security = data.setdefault("security", {})
if not isinstance(security, dict):
    security = {}
    data["security"] = security
security["allow_lazy_installs"] = False
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
PY
}

install_customer_init() {
    [ "${INSTALL_INIT}" -eq 1 ] || return 0
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local source_script="${script_dir}/argo-customer-init"
    [ -f "${source_script}" ] || die "missing ${source_script}"
    local link_dir="/usr/local/bin"
    if [ "$(id -u)" -ne 0 ] && ! sudo -n true >/dev/null 2>&1; then
        link_dir="${HOME}/.local/bin"
        run mkdir -p "${link_dir}"
        log "install argo-customer-init command to ${link_dir}"
        run install -m 0755 "${source_script}" "${link_dir}/argo-customer-init"
        return 0
    fi
    log "install argo-customer-init command to ${link_dir}"
    run_root install -m 0755 "${source_script}" "${link_dir}/argo-customer-init"
}

install_browser_tools() {
    [ "${SKIP_BROWSER}" -eq 0 ] || return 0
    local install_dir="$1"
    log "verify browser tooling"
    if [ -f "${install_dir}/package.json" ]; then
        run bash -lc "cd $(printf '%q' "${install_dir}") && npm install"
    fi
    if command -v npx >/dev/null 2>&1 || [ "${DRY_RUN}" -eq 1 ]; then
        run bash -lc "cd $(printf '%q' "${install_dir}") && npx playwright install --with-deps chromium"
    else
        die "npx not found; run without --skip-browser during install or install Node first"
    fi
}

verify_imports() {
    local python_bin="$1"
    log "verify preinstalled imports"
    run "${python_bin}" - <<'PY'
import importlib

for module in ("honcho", "telegram", "edge_tts", "ddgs"):
    importlib.import_module(module)
print("fde imports ok")
PY
}

main() {
    install_os_packages
    install_argo
    local install_dir
    install_dir="$(discover_install_dir)"
    local python_bin
    python_bin="$(python_bin_for_install "${install_dir}")"
    install_python_packages "${python_bin}"
    write_templates
    write_lazy_policy "${python_bin}"
    install_customer_init
    install_browser_tools "${install_dir}"
    verify_imports "${python_bin}"
    log "FDE provision completed"
}

main
