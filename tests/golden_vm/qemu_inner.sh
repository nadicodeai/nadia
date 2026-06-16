#!/usr/bin/env bash
# Runs inside the disposable Docker runner used by run_qemu.sh.

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

SSH_KEY=/work/id_ed25519
BASE_IMG=/work/jammy-server-cloudimg-amd64.img
GOLDEN_DISK=/work/golden.qcow2
CUSTOMER_DISK=/work/customer.qcow2
SEED_ISO=/work/seed.iso
USER_DATA=/work/user-data
META_DATA=/work/meta-data
HTTP_PID=/work/http.pid

VM_USER=fde
BAKE_PORT=2222
CUSTOMER_PORT=2223

log() {
    printf '==> %s\n' "$*"
}

ssh_common() {
    ssh \
        -i "${SSH_KEY}" \
        -o StrictHostKeyChecking=no \
        -o UserKnownHostsFile=/dev/null \
        -o LogLevel=ERROR \
        "$@"
}

ssh_exec() {
    local port="$1"
    shift
    ssh_common -p "${port}" "${VM_USER}@127.0.0.1" "$@"
}

ssh_script() {
    local port="$1"
    shift
    ssh_common -p "${port}" "${VM_USER}@127.0.0.1" "bash -s" "$@"
}

wait_for_ssh() {
    local port="$1"
    local serial_log="$2"
    for _ in $(seq 1 180); do
        if ssh_exec "${port}" "cloud-init status --wait >/dev/null 2>&1"; then
            return 0
        fi
        sleep 2
    done
    echo "FAIL: timed out waiting for SSH on port ${port}" >&2
    tail -200 "${serial_log}" >&2 || true
    return 1
}

start_vm() {
    local disk="$1"
    local port="$2"
    local name="$3"
    local pidfile="/work/${name}.pid"
    local serial_log="/work/${name}.serial.log"

    rm -f "${pidfile}" "${serial_log}"
    qemu-system-x86_64 \
        -enable-kvm \
        -cpu host \
        -m 4096 \
        -smp 2 \
        -drive "file=${disk},if=virtio,format=qcow2" \
        -drive "file=${SEED_ISO},if=virtio,format=raw" \
        -netdev "user,id=net0,hostfwd=tcp::${port}-:22" \
        -device virtio-net-pci,netdev=net0 \
        -display none \
        -serial "file:${serial_log}" \
        -daemonize \
        -pidfile "${pidfile}"
    wait_for_ssh "${port}" "${serial_log}"
}

stop_vm() {
    local port="$1"
    local name="$2"
    local pidfile="/work/${name}.pid"
    ssh_exec "${port}" "sudo shutdown -h now" || true
    for _ in $(seq 1 60); do
        if [ ! -f "${pidfile}" ] || ! kill -0 "$(cat "${pidfile}")" >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
    done
    if [ -f "${pidfile}" ]; then
        kill "$(cat "${pidfile}")" >/dev/null 2>&1 || true
    fi
}

log "install QEMU runner dependencies"
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    ca-certificates \
    cloud-image-utils \
    curl \
    openssh-client \
    python3 \
    qemu-system-x86 \
    qemu-utils

log "create cloud-init seed"
ssh-keygen -q -t ed25519 -N "" -f "${SSH_KEY}"
PUBKEY="$(cat "${SSH_KEY}.pub")"
cat >"${USER_DATA}" <<EOF
#cloud-config
users:
  - name: ${VM_USER}
    groups: sudo
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: true
    ssh_authorized_keys:
      - ${PUBKEY}
ssh_pwauth: false
package_update: false
EOF
cat >"${META_DATA}" <<'EOF'
instance-id: nadia-golden-vm-smoke
local-hostname: nadia-golden-vm
EOF
cloud-localds "${SEED_ISO}" "${USER_DATA}" "${META_DATA}"

log "download Ubuntu 22.04 cloud image"
curl -fsSL \
    https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img \
    -o "${BASE_IMG}"

log "start local repo HTTP server for guest script fetches"
python3 -m http.server 8000 --directory /repo --bind 0.0.0.0 >/work/http.log 2>&1 &
echo "$!" >"${HTTP_PID}"

log "create and boot golden VM disk"
qemu-img create -f qcow2 -F qcow2 -b "${BASE_IMG}" "${GOLDEN_DISK}" 30G
start_vm "${GOLDEN_DISK}" "${BAKE_PORT}" "golden"

log "bake golden VM"
ssh_script "${BAKE_PORT}" <<'EOS'
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

curl -fsSL http://10.0.2.2:8000/scripts/golden-vm-bake.sh -o /tmp/golden-vm-bake.sh
curl -fsSL http://10.0.2.2:8000/scripts/nadia-fde-provision.sh -o /tmp/nadia-fde-provision.sh
curl -fsSL http://10.0.2.2:8000/scripts/nadia-customer-init -o /tmp/nadia-customer-init
chmod +x /tmp/golden-vm-bake.sh /tmp/nadia-fde-provision.sh /tmp/nadia-customer-init

/tmp/golden-vm-bake.sh --skip-browser

nadia --version
"$HOME/.nadia/nadia-agent/venv/bin/python" - <<'PY'
import importlib
for module in ("honcho", "telegram", "edge_tts", "ddgs"):
    importlib.import_module(module)
print("imports ok")
PY
grep -q "allow_lazy_installs: false" "$HOME/.nadia/config.yaml"
test ! -d "$HOME/.nadia/profiles"
EOS

log "shut down baked golden VM"
stop_vm "${BAKE_PORT}" "golden"
qemu-img info "${GOLDEN_DISK}" | tee /work/golden.qcow2.info

log "create customer clone from golden disk"
qemu-img create -f qcow2 -F qcow2 -b "${GOLDEN_DISK}" "${CUSTOMER_DISK}" 30G
start_vm "${CUSTOMER_DISK}" "${CUSTOMER_PORT}" "customer"

log "run customer initialization in cloned VM"
ssh_script "${CUSTOMER_PORT}" <<'EOS'
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

nadia --version
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

PROFILE_HOME="$HOME/.nadia/profiles/smokeprod"
test -f "${PROFILE_HOME}/config.yaml"
test -f "${PROFILE_HOME}/honcho.json"
test -f "${PROFILE_HOME}/.env"
test -f "${PROFILE_HOME}/SOUL.md"
grep -q "allow_lazy_installs: false" "${PROFILE_HOME}/config.yaml"
grep -q "provider: honcho" "${PROFILE_HOME}/config.yaml"
grep -q "platform: telegram" "${PROFILE_HOME}/config.yaml"
grep -q "fake-honcho-key" "${PROFILE_HOME}/honcho.json"
grep -q "TELEGRAM_BOT_TOKEN=123456789:abcdefghijklmnopqrstuvwxyzABCDE" "${PROFILE_HOME}/.env"
test "$(stat -c '%a' "${PROFILE_HOME}/.env")" = "600"

nadia -p smokeprod --version
systemctl --version >/dev/null
EOS

log "shut down customer VM"
stop_vm "${CUSTOMER_PORT}" "customer"

log "real VM golden image smoke passed"
