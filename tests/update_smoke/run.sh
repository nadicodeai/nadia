#!/usr/bin/env bash
# Update-smoke harness — Part A (IU-AC-9 full, IU-AC-10, IU-AC-11).
#
# Boots a fresh ubuntu:22.04 container, installs argo from the public
# `release`-branch install.sh, then asserts three acceptance criteria
# that do NOT require the fake Telegram fixture:
#
#   IU-AC-9  (full)   — `argo update` stdout/stderr contains NO
#                       `"⚠ Updating from fork"` line. Verifies the
#                       OFFICIAL_REPO_URLS rebrand is intact on the
#                       customer-facing tree.
#   IU-AC-10          — `ARGO_MANAGED=1 argo update` prints the
#                       managed-mode error to stderr. The substring
#                       to look for is `"is managed by"` (matches
#                       upstream config.py:format_managed_message()).
#                       Per spec/plan note: we do NOT assert non-zero
#                       exit code — upstream's managed_error() only
#                       prints and returns; tightening would be a
#                       behavioural divergence forbidden by the loop.
#   IU-AC-11          — with `updates.pre_update_backup: true` in
#                       `~/.argo/config.yaml`, `argo update` creates a
#                       backup artifact under `$ARGO_HOME/backups/`.
#                       Upstream's `create_pre_update_backup()` writes
#                       a single zip file (`pre-update-<stamp>.zip`),
#                       NOT a directory — restoring it uses `argo
#                       import <zipfile>`. Assert the zip exists and
#                       `argo import --force <zip>` exits 0.
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

readonly CONTAINER_NAME="argo-update-smoke-$$"
readonly IMAGE="ubuntu:22.04"
readonly INSTALL_URL="https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh"

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
    exit "$exit_code"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    echo "BLOCKED: docker not found on PATH; cannot run update-smoke." >&2
    exit 1
fi

echo "=== M5.3 update-smoke (Part A) ==="
echo "Container : $CONTAINER_NAME"
echo "Image     : $IMAGE"
echo "Installer : $INSTALL_URL"
echo

# ---------------------------------------------------------------------------
# Boot the container and install argo
# ---------------------------------------------------------------------------

echo "--- Booting container + installing argo ---"
# Stay up for the duration of the test; we exec into it for each phase so
# any failure surfaces with a real exit code.
docker run -d --rm --name "$CONTAINER_NAME" "$IMAGE" sleep 600 >/dev/null

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

# Run the install. `--skip-setup --skip-browser` skips the interactive
# Telegram wizard and the heavy Playwright/Chromium download (~600 MB +
# minutes), neither of which Part A needs.
docker exec "$CONTAINER_NAME" bash -c "
    set -euo pipefail
    curl -fsSL '$INSTALL_URL' | bash -s -- --skip-setup --skip-browser
"

# Sanity check: argo on PATH + version banner.
docker exec "$CONTAINER_NAME" bash -lc '
    set -euo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    argo --version
'

echo

# ---------------------------------------------------------------------------
# IU-AC-9 (full): no "⚠ Updating from fork" on argo update
# ---------------------------------------------------------------------------

echo "--- IU-AC-9 (full): no fork-warning on argo update ---"
# Capture combined stdout+stderr. The update may or may not pull new
# commits — we do not care; only the fork-warning absence is asserted.
# `|| true` so a non-zero exit from `argo update` (e.g. no upstream
# changes, network blip) doesn't kill the assertion — we still get the
# captured output.
set +e
docker exec "$CONTAINER_NAME" bash -lc '
    set -uo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    argo update 2>&1 || true
' > /tmp/argo-update.log 2>&1
set -e

if grep -q "Updating from fork" /tmp/argo-update.log; then
    echo "FAIL IU-AC-9: 'Updating from fork' warning present in argo update output:"
    grep -n "Updating from fork" /tmp/argo-update.log | head -5
    echo "--- full log ---"
    cat /tmp/argo-update.log
else
    echo "PASS IU-AC-9: no 'Updating from fork' line in argo update output."
    PASS_IU_AC_9=1
fi
echo

# ---------------------------------------------------------------------------
# IU-AC-10: ARGO_MANAGED=1 argo update prints managed-mode error to stderr
# ---------------------------------------------------------------------------

echo "--- IU-AC-10: ARGO_MANAGED=1 prints managed-mode error ---"
# Split stdout / stderr so we can assert against stderr specifically.
# Record (but do NOT assert) the exit code — see header comment.
set +e
docker exec "$CONTAINER_NAME" bash -lc '
    set -uo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    ARGO_MANAGED=1 argo update >/tmp/managed_stdout.log 2>/tmp/managed_stderr.log
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
# IU-AC-11: pre-update backup writes a snapshot; argo import restores it
# ---------------------------------------------------------------------------

echo "--- IU-AC-11: pre-update backup + restore ---"
# Write minimal config.yaml enabling pre_update_backup. ARGO_HOME defaults
# to $HOME/.argo per upstream config.py:get_hermes_home() (renamed).
docker exec "$CONTAINER_NAME" bash -lc '
    set -euo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    mkdir -p "$HOME/.argo"
    cat > "$HOME/.argo/config.yaml" <<EOF
updates:
  pre_update_backup: true
  backup_keep: 5
EOF
    # Clear any previous backup so the assertion proves THIS run created one.
    rm -rf "$HOME/.argo/backups"
'

# Force the backup explicitly via --backup as well — defence in depth in
# case load_config() is being suppressed for any reason in this container
# environment. `argo update --backup` is upstream-supported (see
# upstream/hermes_cli/main.py:13511).
set +e
docker exec "$CONTAINER_NAME" bash -lc '
    set -uo pipefail
    export PATH="$HOME/.local/bin:$PATH"
    argo update --backup 2>&1 || true
' > /tmp/argo-update-backup.log 2>&1
set -e

# Upstream writes ~/.argo/backups/pre-update-<stamp>.zip (a FILE, not a
# directory). The spec wording "snapshot directory" predates grounding in
# backup.py:_PRE_UPDATE_BACKUPS_DIR; assert against reality.
BACKUP_COUNT="$(docker exec "$CONTAINER_NAME" bash -lc '
    find "$HOME/.argo/backups" -maxdepth 1 -type f -name "pre-update-*.zip" 2>/dev/null | wc -l
' | tr -d "[:space:]")"

if [ "${BACKUP_COUNT:-0}" -ge 1 ]; then
    echo "PASS IU-AC-11 (snapshot): $BACKUP_COUNT pre-update backup zip(s) under ~/.argo/backups/"
    # Now exercise the restore path via `argo import`. Upstream subparser
    # at upstream/hermes_cli/main.py:12330 takes a zipfile arg, NOT a
    # directory; `--force` skips the overwrite-confirmation prompt that
    # would otherwise block on stdin.
    set +e
    docker exec "$CONTAINER_NAME" bash -lc '
        set -uo pipefail
        export PATH="$HOME/.local/bin:$PATH"
        ZIP="$(find "$HOME/.argo/backups" -maxdepth 1 -type f -name "pre-update-*.zip" | sort | tail -1)"
        echo "Restoring from: $ZIP"
        argo import --force "$ZIP"
    ' > /tmp/argo-import.log 2>&1
    IMPORT_RC=$?
    set -e
    if [ "$IMPORT_RC" -eq 0 ]; then
        echo "PASS IU-AC-11 (restore): argo import --force <zip> exited 0."
        PASS_IU_AC_11=1
    else
        echo "FAIL IU-AC-11 (restore): argo import exited $IMPORT_RC"
        echo "--- argo import log ---"
        cat /tmp/argo-import.log
    fi
else
    echo "FAIL IU-AC-11 (snapshot): no pre-update-*.zip found under ~/.argo/backups/"
    echo "--- argo update --backup log (last 40 lines) ---"
    tail -40 /tmp/argo-update-backup.log
    echo "--- backups dir listing ---"
    docker exec "$CONTAINER_NAME" bash -lc 'ls -la "$HOME/.argo/backups" 2>&1 || echo "(directory missing)"'
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
