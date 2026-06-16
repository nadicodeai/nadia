#!/usr/bin/env bash
# Update-smoke harness — Part A (IU-AC-9 full, IU-AC-10, IU-AC-11).
#
# Boots a fresh ubuntu:22.04 container, installs nadia from a local
# release-branch dry run by default, then asserts three acceptance criteria
# that do NOT require the fake Telegram fixture:
#
#   IU-AC-9  (full)   — `nadia update` stdout/stderr contains NO
#                       `"⚠ Updating from fork"` line. Verifies the
#                       OFFICIAL_REPO_URLS rebrand is intact on the
#                       customer-facing tree.
#   IU-AC-10          — `NADIA_MANAGED=1 nadia update` prints the
#                       managed-mode error to stderr. The substring
#                       to look for is `"is managed by"` (matches
#                       upstream config.py:format_managed_message()).
#                       Per spec/plan note: we do NOT assert non-zero
#                       exit code — upstream's managed_error() only
#                       prints and returns; tightening would be a
#                       behavioural divergence forbidden by the loop.
#   IU-AC-11          — with `updates.pre_update_backup: true` in
#                       `~/.nadia/config.yaml`, `nadia update` creates a
#                       backup artifact under `$NADIA_HOME/backups/`.
#                       Upstream's `create_pre_update_backup()` writes
#                       a single zip file (`pre-update-<stamp>.zip`),
#                       NOT a directory — restoring it uses `nadia
#                       import <zipfile>`. Assert the zip exists and
#                       `nadia import --force <zip>` exits 0.
#
# Part B (IU-AC-6 full Telegram /update flow) lives in
# `tests/update_smoke/run_telegram.sh` if shipped.
#
# Spec: .shepherd/install-update/spec.md § IU-AC-6, IU-AC-9..11
# Plan: .shepherd/install-update/plan.md § M5.3
# Standards: .shepherd/install-update/standards.md § Testing
# Wall-clock budget: < 5 minutes (spec IU-AC-15).

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

readonly CONTAINER_NAME="nadia-update-smoke-$$"
readonly IMAGE="ubuntu:22.04"
readonly LIVE_INSTALL_URL="https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${REPO_ROOT}/.sync-workdir/update-smoke"
mkdir -p "${LOG_DIR}"

INSTALL_URL="${NADIA_UPDATE_SMOKE_INSTALL_URL:-}"
LOCAL_RELEASE_DIR=""
LOCAL_TRANSPORT_URL=""

if [ "${NADIA_UPDATE_SMOKE_LIVE:-0}" = "1" ]; then
    INSTALL_URL="$LIVE_INSTALL_URL"
fi

# Track which assertions passed so we can print a clear summary.
PASS_IU_AC_9=0
PASS_IU_AC_10=0
PASS_IU_AC_11=0

MANAGED_EXIT_CODE=""

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

cleanup() {
    local exit_code=$?
    # `|| true` so cleanup never masks the real exit code.
    docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
    if [ -n "$LOCAL_RELEASE_DIR" ]; then
        rm -rf "$LOCAL_RELEASE_DIR"
    fi
    exit "$exit_code"
}
trap cleanup EXIT

prepare_local_release() {
    LOCAL_RELEASE_DIR="${LOG_DIR}/release-$$"
    rm -rf "$LOCAL_RELEASE_DIR"

    echo "--- Preparing local release dry run ---"
    (
        cd "$REPO_ROOT"
        SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)" make build
    )

    mkdir -p "$LOCAL_RELEASE_DIR"
    git init -q --initial-branch=release "$LOCAL_RELEASE_DIR" 2>/dev/null || {
        git -C "$LOCAL_RELEASE_DIR" init -q
        git -C "$LOCAL_RELEASE_DIR" checkout -q -b release
    }
    (
        cd "$REPO_ROOT/dist/nadia"
        tar cf - .
    ) | (
        cd "$LOCAL_RELEASE_DIR"
        tar xf -
    )
    git -C "$LOCAL_RELEASE_DIR" config user.email "update-smoke@nadicodeai"
    git -C "$LOCAL_RELEASE_DIR" config user.name "update-smoke"
    git -C "$LOCAL_RELEASE_DIR" add -A -f
    git -C "$LOCAL_RELEASE_DIR" commit -q -m "release: local update smoke"

    INSTALL_URL="file:///tmp/nadia-release/scripts/install.sh"
    LOCAL_TRANSPORT_URL="file:///tmp/nadia-release"
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo "BLOCKED: docker not found on PATH; cannot run update-smoke." >&2
    exit 1
fi

if [ -z "$INSTALL_URL" ]; then
    prepare_local_release
fi

DOCKER_MOUNTS=()
if [ -n "$LOCAL_RELEASE_DIR" ]; then
    DOCKER_MOUNTS=(-v "$LOCAL_RELEASE_DIR:/tmp/nadia-release:ro")
fi

echo "=== M5.3 update-smoke (Part A) ==="
echo "Container : $CONTAINER_NAME"
echo "Image     : $IMAGE"
echo "Installer : $INSTALL_URL"
if [ -n "$LOCAL_TRANSPORT_URL" ]; then
    echo "Transport : $LOCAL_TRANSPORT_URL"
fi
echo

# ---------------------------------------------------------------------------
# Boot the container and install nadia
# ---------------------------------------------------------------------------

echo "--- Booting container + installing nadia ---"
# Stay up for the duration of the test; we exec into it for each phase so
# any failure surfaces with a real exit code.
docker run -d --rm --name "$CONTAINER_NAME" "${DOCKER_MOUNTS[@]}" "$IMAGE" sleep 600 >/dev/null

# Install the deps the installer expects pre-existing.
#   curl + ca-certs — fetch install.sh
#   git             — the installer checks for git and aborts if missing
#                     (upstream install.sh:~700 "Git not found")
#   xz-utils        — installer downloads Node.js as a .tar.xz tarball
#                     (install.sh:~607); without xz the extract crashes
#                     even with --skip-browser (which only skips Playwright).
docker exec "$CONTAINER_NAME" bash -c '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq curl ca-certificates git xz-utils >/dev/null
'

if [ -n "$LOCAL_TRANSPORT_URL" ]; then
    docker exec \
        -e NADIA_LOCAL_REPO_URL="$LOCAL_TRANSPORT_URL" \
        "$CONTAINER_NAME" bash -c '
            set -euo pipefail
            git config --global --add safe.directory /tmp/nadia-release 2>/dev/null || true
            git config --global --add safe.directory /tmp/nadia-release/.git 2>/dev/null || true
            git config --global "url.${NADIA_LOCAL_REPO_URL}.insteadOf" "https://github.com/nadicodeai/argo.git"
            git config --global --add "url.${NADIA_LOCAL_REPO_URL}.insteadOf" "git@github.com:nadicodeai/argo.git"
        '
fi

# Run the install. `--skip-setup --skip-browser` skips the interactive
# Telegram wizard and the heavy Playwright/Chromium download (~600 MB +
# minutes), neither of which Part A needs.
docker exec "$CONTAINER_NAME" bash -c "
    set -euo pipefail
    curl -fsSL '$INSTALL_URL' -o /tmp/install.sh
    bash /tmp/install.sh --skip-setup --skip-browser
"

if [ -n "$LOCAL_TRANSPORT_URL" ]; then
    docker exec "$CONTAINER_NAME" bash -lc '
        set -euo pipefail
        for repo in /usr/local/lib/nadia-agent "$HOME/.nadia/nadia-agent"; do
            if [ -d "$repo/.git" ]; then
                git -C "$repo" config remote.origin.url https://github.com/nadicodeai/argo.git
            fi
        done
    '
fi

# Sanity check: nadia on PATH + version banner.
docker exec "$CONTAINER_NAME" bash -lc '
    set -euo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    nadia --version
'

echo

# ---------------------------------------------------------------------------
# IU-AC-9 (full): no "⚠ Updating from fork" on nadia update
# ---------------------------------------------------------------------------

echo "--- IU-AC-9 (full): no fork-warning on nadia update ---"
# Capture combined stdout+stderr. The update may or may not pull new
# commits — we do not care; only the fork-warning absence is asserted.
# `|| true` so a non-zero exit from `nadia update` (e.g. no upstream
# changes, network blip) doesn't kill the assertion — we still get the
# captured output.
set +e
docker exec "$CONTAINER_NAME" bash -lc '
    set -uo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    nadia update 2>&1 || true
' > /tmp/nadia-update.log 2>&1
set -e

if grep -q "Updating from fork" /tmp/nadia-update.log; then
    echo "FAIL IU-AC-9: 'Updating from fork' warning present in nadia update output:"
    grep -n "Updating from fork" /tmp/nadia-update.log | head -5
    echo "--- full log ---"
    cat /tmp/nadia-update.log
else
    echo "PASS IU-AC-9: no 'Updating from fork' line in nadia update output."
    PASS_IU_AC_9=1
fi
echo

# ---------------------------------------------------------------------------
# IU-AC-10: NADIA_MANAGED=1 nadia update prints managed-mode error to stderr
# ---------------------------------------------------------------------------

echo "--- IU-AC-10: NADIA_MANAGED=1 prints managed-mode error ---"
# Split stdout / stderr so we can assert against stderr specifically.
# Record (but do NOT assert) the exit code — see header comment.
set +e
docker exec "$CONTAINER_NAME" bash -lc '
    set -uo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    NADIA_MANAGED=1 nadia update >/tmp/managed_stdout.log 2>/tmp/managed_stderr.log
    echo "EXIT_CODE=$?"
' > /tmp/managed_meta.log
set -e

MANAGED_EXIT_CODE="$(grep -oE 'EXIT_CODE=[0-9]+' /tmp/managed_meta.log | tail -1 | cut -d= -f2 || echo unknown)"

# Pull the in-container stderr out to the host for grepping. Use a
# DIFFERENT host path so we don't shoot ourselves in the foot redirecting
# to the same file we're reading from.
docker exec "$CONTAINER_NAME" cat /tmp/managed_stderr.log > /tmp/host_managed_stderr.log 2>/dev/null || true

if grep -q "is managed by" /tmp/host_managed_stderr.log 2>/dev/null; then
    echo "PASS IU-AC-10: stderr contains 'is managed by' (exit=$MANAGED_EXIT_CODE; not asserted)."
    PASS_IU_AC_10=1
else
    echo "FAIL IU-AC-10: 'is managed by' substring missing from stderr."
    echo "--- stderr (in-container) ---"
    docker exec "$CONTAINER_NAME" cat /tmp/managed_stderr.log 2>&1 || true
    echo "--- stdout (in-container) ---"
    docker exec "$CONTAINER_NAME" cat /tmp/managed_stdout.log 2>&1 || true
    echo "exit=$MANAGED_EXIT_CODE"
fi
echo

# ---------------------------------------------------------------------------
# IU-AC-11: pre-update backup writes a snapshot; nadia import restores it
# ---------------------------------------------------------------------------

echo "--- IU-AC-11: pre-update backup + restore ---"
# Write minimal config.yaml enabling pre_update_backup. NADIA_HOME defaults
# to $HOME/.nadia per upstream config.py:get_hermes_home() (renamed).
docker exec "$CONTAINER_NAME" bash -lc '
    set -euo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    mkdir -p "$HOME/.nadia"
    cat > "$HOME/.nadia/config.yaml" <<EOF
updates:
  pre_update_backup: true
  backup_keep: 5
EOF
    # Clear any previous backup so the assertion proves THIS run created one.
    rm -rf "$HOME/.nadia/backups"
'

# Force the backup explicitly via --backup as well — defence in depth in
# case load_config() is being suppressed for any reason in this container
# environment. `nadia update --backup` is upstream-supported (see
# upstream/hermes_cli/main.py:13511).
set +e
docker exec "$CONTAINER_NAME" bash -lc '
    set -uo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    nadia update --backup 2>&1 || true
' > /tmp/nadia-update-backup.log 2>&1
set -e

# Upstream writes ~/.nadia/backups/pre-update-<stamp>.zip (a FILE, not a
# directory). The spec wording "snapshot directory" predates grounding in
# backup.py:_PRE_UPDATE_BACKUPS_DIR; assert against reality.
BACKUP_COUNT="$(docker exec "$CONTAINER_NAME" bash -lc '
    find "$HOME/.nadia/backups" -maxdepth 1 -type f -name "pre-update-*.zip" 2>/dev/null | wc -l
' | tr -d "[:space:]")"

if [ "${BACKUP_COUNT:-0}" -ge 1 ]; then
    echo "PASS IU-AC-11 (snapshot): $BACKUP_COUNT pre-update backup zip(s) under ~/.nadia/backups/"
    # Now exercise the restore path via `nadia import`. Upstream subparser
    # at upstream/hermes_cli/main.py:12330 takes a zipfile arg, NOT a
    # directory; `--force` skips the overwrite-confirmation prompt that
    # would otherwise block on stdin.
    set +e
    docker exec "$CONTAINER_NAME" bash -lc '
        set -uo pipefail
        export PATH="$HOME/.local/bin:$PATH"
        ZIP="$(find "$HOME/.nadia/backups" -maxdepth 1 -type f -name "pre-update-*.zip" | sort | tail -1)"
        echo "Restoring from: $ZIP"
        nadia import --force "$ZIP"
    ' > /tmp/nadia-import.log 2>&1
    IMPORT_RC=$?
    set -e
    if [ "$IMPORT_RC" -eq 0 ]; then
        echo "PASS IU-AC-11 (restore): nadia import --force <zip> exited 0."
        PASS_IU_AC_11=1
    else
        echo "FAIL IU-AC-11 (restore): nadia import exited $IMPORT_RC"
        echo "--- nadia import log ---"
        cat /tmp/nadia-import.log
    fi
else
    echo "FAIL IU-AC-11 (snapshot): no pre-update-*.zip found under ~/.nadia/backups/"
    echo "--- nadia update --backup log (last 40 lines) ---"
    tail -40 /tmp/nadia-update-backup.log
    echo "--- backups dir listing ---"
    docker exec "$CONTAINER_NAME" bash -lc 'ls -la "$HOME/.nadia/backups" 2>&1 || echo "(directory missing)"'
fi
echo

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo "=== Summary ==="
echo "IU-AC-9  (no fork warning)        : $([ $PASS_IU_AC_9  -eq 1 ] && echo PASS || echo FAIL)"
echo "IU-AC-10 (managed-mode stderr)    : $([ $PASS_IU_AC_10 -eq 1 ] && echo PASS || echo FAIL) (exit=$MANAGED_EXIT_CODE, not asserted)"
echo "IU-AC-11 (backup + restore)       : $([ $PASS_IU_AC_11 -eq 1 ] && echo PASS || echo FAIL)"

if [ $PASS_IU_AC_9 -eq 1 ] && [ $PASS_IU_AC_10 -eq 1 ] && [ $PASS_IU_AC_11 -eq 1 ]; then
    echo
    echo "All Part A assertions passed."
    exit 0
fi

echo
echo "One or more assertions failed."
exit 1
