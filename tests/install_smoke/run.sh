#!/usr/bin/env bash
# tests/install_smoke/run.sh — Docker-driven install.sh smoke harness (M5.2).
#
# Boots a clean ubuntu:22.04 container, downloads the renamed install.sh
# from a local storefront dry run by default, runs it, and asserts the five invariants
# that the customer install path MUST hold:
#
#   1. ~/.nadia/.install_method exists and reads "git"        (IU-AC-5)
#   2. `nadia --version` exits 0                              (IU-AC-4 exit)
#   3. `nadia --version` matches the hermes banner regex      (IU-AC-4 banner)
#   4. `nadia update --check` does NOT print the fork warning (IU-AC-9 static)
#   5. ~/.hermes/.install_method does NOT exist              (leakage check)
#
# Also enforces a generous wall-clock ceiling (10 min) as a partial
# proxy for IU-NFR-1 (install ≤ hermes + 10%). The hermes baseline
# is not measured locally; the ceiling here is a hard guardrail.
#
# Usage:
#   bash tests/install_smoke/run.sh [--live]
#                                   [--url <override>]
#                                   [--repo-url <override>]
#                                   [--branch <override>]
#                                   [--keep-container]
#
# Defaults to a local release-branch dry run built from dist/nadia, because
# the public nadicodeai/nadia repo rename is a separate approval gate. Use
# --live to fetch the public release URL after that public action is approved.
# Override --url to point at a fork or local web server during development;
# --repo-url is exported as NADIA_REPO_URL_HTTPS/NADIA_REPO_URL_SSH for the
# installer clone step. The local default instead uses git insteadOf so the
# checkout records the official Nadia origin while transport stays local.
# --branch is passed through to install.sh as `--branch <branch>` (NOT the
# release branch of the file fetch — the URL controls that).

set -euo pipefail

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------

LIVE_URL="https://raw.githubusercontent.com/nadicodeai/nadia/release/scripts/install.sh"
URL=""
REPO_URL=""
BRANCH=""
KEEP_CONTAINER=0
LOCAL_RELEASE_DIR=""
LOCAL_TRANSPORT_URL=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --live)
            URL="${LIVE_URL}"
            shift
            ;;
        --url)
            URL="$2"
            shift 2
            ;;
        --repo-url)
            REPO_URL="$2"
            shift 2
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --keep-container)
            KEEP_CONTAINER=1
            shift
            ;;
        -h|--help)
            sed -n '1,30p' "$0"
            exit 0
            ;;
        *)
            echo "FAIL: unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Paths + container id
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${REPO_ROOT}/.sync-workdir/install-smoke"
mkdir -p "${LOG_DIR}"

# Random hex id; uuidgen may not be on every box, so fall back to /dev/urandom.
if command -v uuidgen >/dev/null 2>&1; then
    UUID="$(uuidgen | tr -d '-' | head -c 16)"
else
    UUID="$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi
CONTAINER="nadia-install-smoke-${UUID}"
LOG_FILE="${LOG_DIR}/${UUID}.log"

prepare_local_release() {
    LOCAL_RELEASE_DIR="${LOG_DIR}/${UUID}-release"
    rm -rf "${LOCAL_RELEASE_DIR}"

    echo "install-smoke: preparing local release dry run"
    (
        cd "${REPO_ROOT}"
        SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)" make build
    )

    mkdir -p "${LOCAL_RELEASE_DIR}"
    git init -q --initial-branch=release "${LOCAL_RELEASE_DIR}" 2>/dev/null || {
        git -C "${LOCAL_RELEASE_DIR}" init -q
        git -C "${LOCAL_RELEASE_DIR}" checkout -q -b release
    }
    (
        cd "${REPO_ROOT}/dist/nadia"
        tar cf - .
    ) | (
        cd "${LOCAL_RELEASE_DIR}"
        tar xf -
    )
    git -C "${LOCAL_RELEASE_DIR}" config user.email "install-smoke@nadicodeai"
    git -C "${LOCAL_RELEASE_DIR}" config user.name "install-smoke"
    git -C "${LOCAL_RELEASE_DIR}" add -A -f
    git -C "${LOCAL_RELEASE_DIR}" commit -q -m "release: local install smoke"

    URL="file:///tmp/nadia-release/scripts/install.sh"
    LOCAL_TRANSPORT_URL="file:///tmp/nadia-release"
}

if [[ -z "${URL}" ]]; then
    prepare_local_release
fi

DOCKER_MOUNTS=()
if [[ -n "${LOCAL_RELEASE_DIR}" ]]; then
    DOCKER_MOUNTS=(-v "${LOCAL_RELEASE_DIR}:/tmp/nadia-release:ro")
fi

echo "install-smoke: container=${CONTAINER}"
echo "install-smoke: url=${URL}"
if [[ -n "${REPO_URL}" ]]; then
    echo "install-smoke: repo-url=${REPO_URL}"
fi
if [[ -n "${LOCAL_TRANSPORT_URL}" ]]; then
    echo "install-smoke: local-transport=${LOCAL_TRANSPORT_URL}"
fi
echo "install-smoke: log=${LOG_FILE}"

# ---------------------------------------------------------------------------
# Cleanup trap — always runs, even on assertion failure.
# ---------------------------------------------------------------------------

cleanup() {
    local exit_code=$?
    if [[ "${KEEP_CONTAINER}" -eq 0 ]]; then
        docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    else
        echo "install-smoke: --keep-container set; container left running"
    fi
    if [[ -n "${LOCAL_RELEASE_DIR}" && "${KEEP_CONTAINER}" -eq 0 ]]; then
        rm -rf "${LOCAL_RELEASE_DIR}"
    fi
    exit "${exit_code}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Compose the in-container script.
#
# Strict mode inside the container as well. The container is throwaway,
# so we use root + $HOME=/root throughout (matches how `curl|bash` runs
# on a fresh VPS).
# ---------------------------------------------------------------------------

INSTALL_ARGS="--skip-setup --skip-browser"
if [[ -n "${BRANCH}" ]]; then
    INSTALL_ARGS="${INSTALL_ARGS} --branch ${BRANCH}"
fi

# Use a heredoc-without-expansion and inject the variables we need via
# `env` so the script body cannot accidentally interpolate host-side
# values. The container script writes PASS/FAIL lines on its own stdout;
# the host captures + echoes them back.
CONTAINER_SCRIPT=$(cat <<'EOS'
set -euo pipefail

# Mark phase boundaries so the host log is greppable.
echo "==> apt install prereqs"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    curl ca-certificates git python3 python3-venv xz-utils

if [ -n "${NADIA_LOCAL_REPO_URL:-}" ]; then
    git config --global --add safe.directory /tmp/nadia-release 2>/dev/null || true
    git config --global --add safe.directory /tmp/nadia-release/.git 2>/dev/null || true
    git config --global "url.${NADIA_LOCAL_REPO_URL}.insteadOf" "https://github.com/nadicodeai/nadia.git"
    git config --global --add "url.${NADIA_LOCAL_REPO_URL}.insteadOf" "git@github.com:nadicodeai/nadia.git"
fi

echo "==> fetch install.sh from ${INSTALL_URL}"
curl -fsSL "${INSTALL_URL}" -o /tmp/install.sh
chmod +x /tmp/install.sh

echo "==> running install.sh ${INSTALL_ARGS}"
INSTALL_START=$(date +%s)
# shellcheck disable=SC2086  # intentional word-splitting of INSTALL_ARGS
bash /tmp/install.sh ${INSTALL_ARGS}
if [ -n "${NADIA_LOCAL_REPO_URL:-}" ]; then
    for repo in /usr/local/lib/nadia-agent "${HOME}/.nadia/nadia-agent"; do
        if [ -d "${repo}/.git" ]; then
            git -C "${repo}" config remote.origin.url https://github.com/nadicodeai/nadia.git
        fi
    done
fi
INSTALL_END=$(date +%s)
INSTALL_SECS=$(( INSTALL_END - INSTALL_START ))
echo "install wall-clock: ${INSTALL_SECS}s"

# 10-minute hard ceiling. IU-NFR-1 is "≤ hermes + 10%" but hermes
# baseline is not measured in this harness; 600s is a generous guardrail.
if [ "${INSTALL_SECS}" -gt 600 ]; then
    echo "FAIL: install exceeded 600s ceiling (took ${INSTALL_SECS}s) — IU-NFR-1 guardrail"
    exit 1
fi

# The install.sh chooses between ~/.local/bin/nadia (non-root) and
# /usr/local/bin/nadia (root). The container runs as root, so the system
# path wins; resolve via `command -v` so we don't hardcode either.
NADIA_BIN="$(command -v nadia || true)"
INSTALL_METHOD_FILE="${HOME}/.nadia/.install_method"
LEGACY_METHOD_FILE="${HOME}/.hermes/.install_method"

# -----------------------------------------------------------------------
# Assertion 1 — .install_method = git  (IU-AC-5)
# -----------------------------------------------------------------------
if [ ! -f "${INSTALL_METHOD_FILE}" ]; then
    echo "FAIL [IU-AC-5]: ${INSTALL_METHOD_FILE} does not exist"
    exit 1
fi
METHOD_CONTENT="$(cat "${INSTALL_METHOD_FILE}")"
if [ "${METHOD_CONTENT}" != "git" ]; then
    echo "FAIL [IU-AC-5]: ${INSTALL_METHOD_FILE} contains '${METHOD_CONTENT}', expected 'git'"
    exit 1
fi
echo "PASS [IU-AC-5]: ${INSTALL_METHOD_FILE} reads 'git'"

# -----------------------------------------------------------------------
# Assertion 2 — nadia --version exits 0  (IU-AC-4 exit)
# -----------------------------------------------------------------------
if [ -z "${NADIA_BIN}" ] || [ ! -x "${NADIA_BIN}" ]; then
    echo "FAIL [IU-AC-4 exit]: nadia not found on PATH (resolved: '${NADIA_BIN}')"
    echo "  PATH=${PATH}"
    exit 1
fi
echo "  nadia binary: ${NADIA_BIN}"
set +e
VERSION_OUTPUT="$("${NADIA_BIN}" --version 2>&1)"
VERSION_EXIT=$?
set -e
if [ "${VERSION_EXIT}" -ne 0 ]; then
    echo "FAIL [IU-AC-4 exit]: 'nadia --version' exited ${VERSION_EXIT}"
    echo "  output: ${VERSION_OUTPUT}"
    exit 1
fi
echo "PASS [IU-AC-4 exit]: 'nadia --version' exit 0"

# -----------------------------------------------------------------------
# Assertion 3 — banner matches hermes regex  (IU-AC-4 banner)
# -----------------------------------------------------------------------
BANNER_REGEX='Nadia Agent v[0-9]+\.[0-9]+\.[0-9]+ \([0-9]{4}\.[0-9]+\.[0-9]+(\.[0-9]+)?\)'
if echo "${VERSION_OUTPUT}" | grep -qE "${BANNER_REGEX}"; then
    echo "PASS [IU-AC-4 banner]: matches '${BANNER_REGEX}'"
    echo "  banner: $(echo "${VERSION_OUTPUT}" | grep -E "${BANNER_REGEX}" | head -1)"
else
    echo "FAIL [IU-AC-4 banner]: output does not match '${BANNER_REGEX}'"
    echo "  output: ${VERSION_OUTPUT}"
    exit 1
fi

# -----------------------------------------------------------------------
# Assertion 4 — no "Updating from fork" warning  (IU-AC-9 static)
#
# `nadia update --check` is the read-only path; it queries the remote
# without touching anything on disk. The fork warning (printed by
# upstream's _is_fork at hermes_cli/main.py:7319-7332 → main.py:8812-8815)
# fires before the actual update attempt, so --check exercises it.
# -----------------------------------------------------------------------
set +e
UPDATE_OUTPUT="$("${NADIA_BIN}" update --check 2>&1)"
UPDATE_EXIT=$?
set -e
# We deliberately do NOT assert on UPDATE_EXIT — `--check` may return
# non-zero if there's nothing to update; the only thing we care about
# here is the fork warning.
if echo "${UPDATE_OUTPUT}" | grep -q "Updating from fork"; then
    echo "FAIL [IU-AC-9 static]: 'Updating from fork' present in update --check output"
    echo "  output: ${UPDATE_OUTPUT}"
    exit 1
fi
echo "PASS [IU-AC-9 static]: no 'Updating from fork' warning (update --check exit ${UPDATE_EXIT})"

# -----------------------------------------------------------------------
# Assertion 5 — no leakage into legacy ~/.hermes/  (leakage check)
# -----------------------------------------------------------------------
if [ -e "${LEGACY_METHOD_FILE}" ]; then
    echo "FAIL [leakage]: ${LEGACY_METHOD_FILE} exists (install leaked into ~/.hermes/)"
    exit 1
fi
echo "PASS [leakage]: ${LEGACY_METHOD_FILE} does not exist"

echo "==> all assertions passed"
EOS
)

# ---------------------------------------------------------------------------
# Run the container.
#
# - Plain `docker run` (no buildx, no compose).
# - No port mapping; install.sh + nadia are local to the container.
# - Mount nothing from host; the install is a clean-room exercise.
# - tee to log file AND stdout so the maintainer sees live output.
# ---------------------------------------------------------------------------

HOST_START=$(date +%s)
set +e
docker run \
    --name "${CONTAINER}" \
    --rm=false \
    "${DOCKER_MOUNTS[@]}" \
    -e INSTALL_URL="${URL}" \
    -e INSTALL_ARGS="${INSTALL_ARGS}" \
    -e NADIA_LOCAL_REPO_URL="${LOCAL_TRANSPORT_URL}" \
    -e NADIA_REPO_URL="${REPO_URL}" \
    -e NADIA_REPO_URL_HTTPS="${REPO_URL}" \
    -e NADIA_REPO_URL_SSH="${REPO_URL}" \
    ubuntu:22.04 \
    bash -c "${CONTAINER_SCRIPT}" 2>&1 | tee "${LOG_FILE}"
# tee's exit reflects tee, not docker; pull docker's exit from PIPESTATUS.
DOCKER_EXIT=${PIPESTATUS[0]}
set -e
HOST_END=$(date +%s)
HOST_SECS=$(( HOST_END - HOST_START ))

echo "install-smoke: docker wall-clock ${HOST_SECS}s; docker exit ${DOCKER_EXIT}"

if [ "${DOCKER_EXIT}" -ne 0 ]; then
    echo "install-smoke: FAILED — see ${LOG_FILE}"
    exit "${DOCKER_EXIT}"
fi

echo "install-smoke: PASSED"
exit 0
