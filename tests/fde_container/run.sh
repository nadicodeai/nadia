#!/usr/bin/env bash
# Build and validate the FDE customer container path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE="${ARGO_FDE_CONTAINER_IMAGE:-ghcr.io/nadicodeai/argo:fde-dev}"

docker buildx build \
    --build-arg SOURCE_DATE_EPOCH="$(git -C "${REPO_ROOT}" log -1 --format=%ct)" \
    --platform linux/amd64 \
    --target runtime-fde \
    --load \
    -t "${IMAGE}" \
    "${REPO_ROOT}"

docker run --rm \
    --entrypoint /usr/local/bin/argo-customer-init \
    "${IMAGE}" \
    --profile smokeprod \
    --honcho-workspace smoke-workspace \
    --honcho-peer fde-smoke \
    --honcho-api-key fake-honcho-key \
    --telegram-token 123456789:abcdefghijklmnopqrstuvwxyzABCDE \
    --telegram-allowed-users 42,84 \
    --telegram-home-channel -10012345 \
    --skip-gateway \
    --yes

docker run --rm \
    --entrypoint bash \
    "${IMAGE}" \
    -c 'set -euo pipefail
        /opt/argo/.venv/bin/argo --version
        /opt/argo/.venv/bin/python - <<'"'"'PY'"'"'
import importlib
for module in ("honcho", "telegram", "edge_tts", "ddgs"):
    importlib.import_module(module)
print("imports ok")
PY
        test -f /usr/local/bin/argo-customer-init
        test -f /opt/data/SOUL.md.template
        test -f /opt/data/honcho.json.template
    '

docker run --rm "${IMAGE}" --version >/dev/null

printf 'fde-container-smoke: PASSED image=%s\n' "${IMAGE}"
