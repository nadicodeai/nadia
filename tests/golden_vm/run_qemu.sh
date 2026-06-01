#!/usr/bin/env bash
# Real VM smoke for the golden VM flow.
#
# The host does not need QEMU installed. This wrapper starts a privileged Ubuntu
# runner container with /dev/kvm, installs QEMU inside that container, then boots
# an Ubuntu 22.04 cloud image as a real VM.

set -euo pipefail

KEEP_WORKDIR=0
ARTIFACT_DIR=""
ARTIFACT_NAME="argo-fde-ubuntu-22.04.qcow2"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --keep-workdir)
            KEEP_WORKDIR=1
            shift
            ;;
        --artifact-dir)
            ARTIFACT_DIR="${2:-}"
            [ -n "${ARTIFACT_DIR}" ] || { echo "FAIL: --artifact-dir requires a value" >&2; exit 2; }
            KEEP_WORKDIR=1
            shift 2
            ;;
        --artifact-name)
            ARTIFACT_NAME="${2:-}"
            [ -n "${ARTIFACT_NAME}" ] || { echo "FAIL: --artifact-name requires a value" >&2; exit 2; }
            shift 2
            ;;
        -h|--help)
            sed -n '1,24p' "$0"
            exit 0
            ;;
        *)
            echo "FAIL: unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${REPO_ROOT}/.sync-workdir/golden-vm-qemu"
mkdir -p "${LOG_DIR}"

if command -v uuidgen >/dev/null 2>&1; then
    UUID="$(uuidgen | tr -d '-' | head -c 16)"
else
    UUID="$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
WORKDIR="${LOG_DIR}/${UUID}"
LOG_FILE="${LOG_DIR}/${UUID}.log"
mkdir -p "${WORKDIR}"

cleanup() {
    local exit_code=$?
    if [ "${KEEP_WORKDIR}" -eq 0 ]; then
        rm -rf "${WORKDIR}"
    else
        echo "golden-vm-qemu: --keep-workdir set; kept ${WORKDIR}"
    fi
    exit "${exit_code}"
}
trap cleanup EXIT

if [ ! -e /dev/kvm ]; then
    echo "FAIL: /dev/kvm is not available; cannot run a real accelerated VM" >&2
    exit 1
fi

echo "golden-vm-qemu: workdir=${WORKDIR}"
echo "golden-vm-qemu: log=${LOG_FILE}"

set +e
START_TS="$(date +%s)"
docker run \
    --rm \
    --privileged \
    --device /dev/kvm \
    --volume "${REPO_ROOT}:/repo:ro" \
    --volume "${WORKDIR}:/work" \
    ubuntu:22.04 \
    bash /repo/tests/golden_vm/qemu_inner.sh 2>&1 | tee "${LOG_FILE}"
DOCKER_EXIT=${PIPESTATUS[0]}
END_TS="$(date +%s)"
set -e

echo "golden-vm-qemu: wall-clock $(( END_TS - START_TS ))s; docker exit ${DOCKER_EXIT}"
if [ "${DOCKER_EXIT}" -ne 0 ]; then
    echo "golden-vm-qemu: FAILED - see ${LOG_FILE}"
    exit "${DOCKER_EXIT}"
fi

if [ -n "${ARTIFACT_DIR}" ]; then
    mkdir -p "${ARTIFACT_DIR}"
    cp "${WORKDIR}/golden.qcow2" "${ARTIFACT_DIR}/${ARTIFACT_NAME}"
    if [ -f "${WORKDIR}/golden.qcow2.info" ]; then
        cp "${WORKDIR}/golden.qcow2.info" "${ARTIFACT_DIR}/${ARTIFACT_NAME}.info"
    elif command -v qemu-img >/dev/null 2>&1; then
        qemu-img info "${ARTIFACT_DIR}/${ARTIFACT_NAME}" > "${ARTIFACT_DIR}/${ARTIFACT_NAME}.info"
    else
        {
            echo "qemu-img unavailable on host; runner did not produce qemu info"
            stat -c 'size: %s bytes' "${ARTIFACT_DIR}/${ARTIFACT_NAME}"
        } > "${ARTIFACT_DIR}/${ARTIFACT_NAME}.info"
    fi
    sha256sum "${ARTIFACT_DIR}/${ARTIFACT_NAME}" > "${ARTIFACT_DIR}/${ARTIFACT_NAME}.sha256"
    cp "${LOG_FILE}" "${ARTIFACT_DIR}/${ARTIFACT_NAME}.build.log"
    echo "golden-vm-qemu: artifact=${ARTIFACT_DIR}/${ARTIFACT_NAME}"
fi

echo "golden-vm-qemu: PASSED"
