#!/usr/bin/env bash
# tools/check_legacy_untouched.sh — verify the legacy argo-agent repo
# remains untouched (spec G5, AC-10).
#
# Modes:
#   (no args)    Compute the current legacy-repo tree hash and write it +
#                the legacy repo's current commit SHA to
#                .shepherd/legacy-baseline.sha256. Used ONCE at M2.4a.
#   --verify     Recompute the current hash; compare against the recorded
#                baseline; exit 0 on match, 1 on drift.
#
# The hash is content-based (sha256 of sorted file contents) — a touch
# that changes mtime but not content does NOT flip the hash. That matches
# AC-10's intent: "untouched" means the bytes are the same.

set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEGACY_DIR="$HOME/Code/argo-agent"
BASELINE_FILE="$REPO_ROOT/.shepherd/legacy-baseline.sha256"

# Excluded paths (volatile, irrelevant to "tree-content untouched"):
#   .git/             — VCS internals (pack timestamps, refs, etc.)
#   __pycache__/      — Python bytecode
#   *.pyc, *.pyo      — Python bytecode
#   .venv/            — virtualenv (if any)
#   node_modules/     — JS deps (if any)
#   dist/, build/     — build outputs
#   .sync-workdir/    — sync state
#   .pytest_cache/    — pytest cache
EXCLUDES=(
    -not -path "*/.git/*"
    -not -path "*/__pycache__/*"
    -not -name "*.pyc"
    -not -name "*.pyo"
    -not -path "*/.venv/*"
    -not -path "*/node_modules/*"
    -not -path "*/dist/*"
    -not -path "*/build/*"
    -not -path "*/.sync-workdir/*"
    -not -path "*/.pytest_cache/*"
)

compute_hash() {
    if [ ! -d "$LEGACY_DIR" ]; then
        echo "error: legacy dir not present: $LEGACY_DIR" >&2
        exit 2
    fi
    # Hash file contents in path-sorted order so the result is deterministic.
    ( cd "$LEGACY_DIR" && \
      find . -type f "${EXCLUDES[@]}" -print0 | \
      LC_ALL=C sort -z | \
      xargs -0 sha256sum | \
      sha256sum | \
      awk '{print $1}' )
}

legacy_head_sha() {
    git -C "$LEGACY_DIR" log -1 --format='%H'
}

mode="${1:-record}"

case "$mode" in
    record)
        hash="$(compute_hash)"
        head="$(legacy_head_sha)"
        mkdir -p "$REPO_ROOT/.shepherd"
        {
            echo "# Legacy-repo baseline (spec G5, AC-10)."
            echo "# Recorded at M2.4a. Recomputed by --verify mode."
            echo "# Format: <tree-hash> <legacy-HEAD-sha>"
            echo "$hash $head"
        } > "$BASELINE_FILE"
        echo "Recorded baseline: $hash"
        echo "Legacy HEAD:        $head"
        echo "→ $BASELINE_FILE"
        ;;
    --verify|verify)
        if [ ! -f "$BASELINE_FILE" ]; then
            echo "error: $BASELINE_FILE does not exist; record first" >&2
            exit 2
        fi
        recorded="$(grep -v '^#' "$BASELINE_FILE" | head -1)"
        recorded_hash="$(echo "$recorded" | awk '{print $1}')"
        recorded_head="$(echo "$recorded" | awk '{print $2}')"
        current_hash="$(compute_hash)"
        current_head="$(legacy_head_sha)"
        if [ "$current_hash" = "$recorded_hash" ] && [ "$current_head" = "$recorded_head" ]; then
            echo "legacy untouched: hash=$current_hash head=$current_head"
            exit 0
        fi
        echo "✗ LEGACY REPO DRIFTED" >&2
        [ "$current_hash" != "$recorded_hash" ] && \
            echo "  tree-hash:  recorded=$recorded_hash current=$current_hash" >&2
        [ "$current_head" != "$recorded_head" ] && \
            echo "  legacy HEAD: recorded=$recorded_head current=$current_head" >&2
        exit 1
        ;;
    *)
        echo "usage: $0 [--verify]" >&2
        exit 2
        ;;
esac
