#!/usr/bin/env bash
# Docker-backed smoke for the golden VM scripts.
#
# This uses an Ubuntu 22.04 container as a disposable VM surrogate. It runs the
# real release installer through scripts/golden-vm-bake.sh, preinstalls the FDE
# dependency surface, then creates a customer profile through nadia-customer-init.

set -euo pipefail

KEEP_CONTAINER=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --keep-container)
            KEEP_CONTAINER=1
            shift
            ;;
        -h|--help)
            sed -n '1,20p' "$0"
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
LOG_DIR="${REPO_ROOT}/.sync-workdir/golden-vm-smoke"
mkdir -p "${LOG_DIR}"

if command -v uuidgen >/dev/null 2>&1; then
    UUID="$(uuidgen | tr -d '-' | head -c 16)"
else
    UUID="$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
CONTAINER="nadia-golden-vm-smoke-${UUID}"
LOG_FILE="${LOG_DIR}/${UUID}.log"

echo "golden-vm-smoke: container=${CONTAINER}"
echo "golden-vm-smoke: log=${LOG_FILE}"

cleanup() {
    local exit_code=$?
    if [ "${KEEP_CONTAINER}" -eq 0 ]; then
        docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    else
        echo "golden-vm-smoke: --keep-container set; container left running"
    fi
    exit "${exit_code}"
}
trap cleanup EXIT

CONTAINER_SCRIPT=$(cat <<'EOS'
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export NADIA_HOME=/root/.nadia

echo "==> bake golden VM baseline"
/repo/scripts/golden-vm-bake.sh --skip-browser

echo "==> assert nadia command"
nadia --version

echo "==> assert imports"
/usr/local/lib/nadia-agent/venv/bin/python - <<'PY'
import importlib
for module in ("honcho", "telegram", "edge_tts", "ddgs"):
    importlib.import_module(module)
print("imports ok")
PY

echo "==> customer init"
nadia-customer-init \
  --profile smokeprod \
  --honcho-workspace smoke-workspace \
  --honcho-peer fde-smoke \
  --honcho-api-key fake-honcho-key \
  --telegram-token 123456789:abcdefghijklmnopqrstuvwxyzABCDE \
  --telegram-allowed-users 42,84 \
  --telegram-home-channel -10012345 \
  --skip-gateway \
  --yes

echo "==> assert profile files"
test -f /root/.nadia/profiles/smokeprod/config.yaml
test -f /root/.nadia/profiles/smokeprod/honcho.json
test -f /root/.nadia/profiles/smokeprod/.env
test -f /root/.nadia/profiles/smokeprod/SOUL.md
grep -q "allow_lazy_installs: false" /root/.nadia/profiles/smokeprod/config.yaml
grep -q "provider: honcho" /root/.nadia/profiles/smokeprod/config.yaml
grep -q "platform: telegram" /root/.nadia/profiles/smokeprod/config.yaml
grep -q "fake-honcho-key" /root/.nadia/profiles/smokeprod/honcho.json
grep -q "TELEGRAM_BOT_TOKEN=123456789:abcdefghijklmnopqrstuvwxyzABCDE" /root/.nadia/profiles/smokeprod/.env
test "$(stat -c '%a' /root/.nadia/profiles/smokeprod/.env)" = "600"

echo "==> assert nadia can address profile"
nadia -p smokeprod --version

echo "==> golden VM smoke passed"
EOS
)

set +e
START_TS="$(date +%s)"
docker run \
    --name "${CONTAINER}" \
    --volume "${REPO_ROOT}:/repo:ro" \
    ubuntu:22.04 \
    bash -lc "${CONTAINER_SCRIPT}" 2>&1 | tee "${LOG_FILE}"
DOCKER_EXIT=${PIPESTATUS[0]}
END_TS="$(date +%s)"
set -e

echo "golden-vm-smoke: docker wall-clock $(( END_TS - START_TS ))s; docker exit ${DOCKER_EXIT}"
if [ "${DOCKER_EXIT}" -ne 0 ]; then
    echo "golden-vm-smoke: FAILED - see ${LOG_FILE}"
    exit "${DOCKER_EXIT}"
fi

echo "golden-vm-smoke: PASSED"
