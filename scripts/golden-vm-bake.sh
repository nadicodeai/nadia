#!/usr/bin/env bash
# Bake a forward-deployed Nadia golden VM baseline.

set -euo pipefail

NADIA_HOME="${NADIA_HOME:-${HOME}/.nadia}"
NADIA_INSTALL_DIR="${NADIA_INSTALL_DIR:-}"
INSTALL_URL="${NADIA_INSTALL_URL:-https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh}"

DRY_RUN=0
PRINT_PACKAGES=0
SKIP_OS_PACKAGES=0
CLEAN_STATE=1
PROVISION_ARGS=()

usage() {
    cat <<'USAGE'
Usage: scripts/golden-vm-bake.sh [options]

Installs the VM baseline for forward-deployed Nadia engineers by running
scripts/nadia-fde-provision.sh with Ubuntu/Debian OS packages enabled, then
cleaning customer-specific state before snapshot.

Options:
  --dry-run                 Print actions without changing the machine.
  --print-python-packages   Print the Python package surface and exit.
  --skip-nadia-install       Do not run the public Nadia installer.
  --skip-os-packages        Do not install apt packages.
  --skip-browser            Skip browser/node provisioning in this bake pass.
  --no-clean                Leave mutable Nadia runtime state in place.
  --allow-lazy-installs     Do not force security.allow_lazy_installs=false.
  -h, --help                Show this help.

Environment:
  NADIA_HOME                 Defaults to ~/.nadia.
  NADIA_INSTALL_DIR          Overrides auto-discovery of the Nadia venv location.
  NADIA_INSTALL_URL          Overrides the public release install.sh URL.
USAGE
}

log() {
    printf '%s\n' "$*"
}

die() {
    printf 'golden-vm-bake: %s\n' "$*" >&2
    exit 1
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
            PROVISION_ARGS+=("$1")
            shift
            ;;
        --print-python-packages)
            PRINT_PACKAGES=1
            PROVISION_ARGS+=("$1")
            shift
            ;;
        --skip-nadia-install|--skip-browser|--allow-lazy-installs)
            PROVISION_ARGS+=("$1")
            shift
            ;;
        --skip-os-packages)
            SKIP_OS_PACKAGES=1
            shift
            ;;
        --no-clean)
            CLEAN_STATE=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
done

install_customer_init() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local source_script="${script_dir}/nadia-customer-init"
    [ -f "${source_script}" ] || die "missing ${source_script}"
    log "install nadia-customer-init command"
    run_root install -m 0755 "${source_script}" /usr/local/bin/nadia-customer-init
}

clean_state() {
    [ "${CLEAN_STATE}" -eq 1 ] || return 0
    log "clean mutable customer state before snapshot"
    run rm -rf \
        "${NADIA_HOME}/sessions" \
        "${NADIA_HOME}/logs" \
        "${NADIA_HOME}/gateway" \
        "${NADIA_HOME}/profiles"
    run rm -f \
        "${NADIA_HOME}/.env" \
        "${NADIA_HOME}/honcho.json" \
        "${NADIA_HOME}/auth.json"
}

main() {
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    if [ "${PRINT_PACKAGES}" -eq 1 ]; then
        "${script_dir}/nadia-fde-provision.sh" "${PROVISION_ARGS[@]}"
        return 0
    fi
    if [ "${SKIP_OS_PACKAGES}" -eq 0 ]; then
        PROVISION_ARGS+=(--with-os-packages)
    fi
    "${script_dir}/nadia-fde-provision.sh" "${PROVISION_ARGS[@]}"
    clean_state
    log "golden VM bake completed"
}

main
