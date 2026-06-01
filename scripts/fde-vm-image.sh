#!/usr/bin/env bash
# Produce the first importable Argo FDE VM artifact.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUT_DIR="${ARGO_FDE_IMAGE_DIR:-${REPO_ROOT}/dist/images}"
ARTIFACT_NAME="${ARGO_FDE_IMAGE_NAME:-argo-fde-ubuntu-22.04.qcow2}"

mkdir -p "${OUT_DIR}"

"${REPO_ROOT}/tests/golden_vm/run_qemu.sh" \
    --artifact-dir "${OUT_DIR}" \
    --artifact-name "${ARTIFACT_NAME}"

printf 'fde-vm-image: artifact=%s\n' "${OUT_DIR}/${ARTIFACT_NAME}"
printf 'fde-vm-image: sha256=%s\n' "${OUT_DIR}/${ARTIFACT_NAME}.sha256"
printf 'fde-vm-image: log=%s\n' "${OUT_DIR}/${ARTIFACT_NAME}.build.log"
