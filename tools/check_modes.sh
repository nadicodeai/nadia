#!/usr/bin/env bash
# tools/check_modes.sh — verify file-mode preservation across the build.
#
# For every executable file in upstream/, check that the corresponding
# file in dist/argo/ (after rename) has the same permission bits. This
# catches regressions in tools/build.py's shutil.copytree behavior or in
# the rename engine's file-rename pass.
#
# Exit 0 on clean, 1 on any mismatch.

set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM="$REPO_ROOT/upstream"
DIST="$REPO_ROOT/dist/argo"

if [ ! -d "$DIST" ]; then
    echo "error: dist/argo/ not present — run 'make build' first" >&2
    exit 2
fi

mismatches=0
checked=0

while IFS= read -r src; do
    rel="${src#$UPSTREAM/}"
    # Apply the simple hermes→argo path rename. Mirrors what the rename
    # engine's filenames pass would do for our case.
    new_rel="$(echo "$rel" | sed 's/hermes/argo/g')"
    dst="$DIST/$new_rel"
    if [ ! -f "$dst" ]; then
        echo "  MISSING $dst (orig=$rel)" >&2
        mismatches=$((mismatches + 1))
        continue
    fi
    src_mode="$(stat -c '%a' "$src")"
    dst_mode="$(stat -c '%a' "$dst")"
    if [ "$src_mode" != "$dst_mode" ]; then
        echo "  MISMATCH $rel→$new_rel src=$src_mode dst=$dst_mode" >&2
        mismatches=$((mismatches + 1))
    fi
    checked=$((checked + 1))
done < <(find "$UPSTREAM" -type f -executable 2>/dev/null)

echo "check_modes: $checked executable file(s) verified; $mismatches mismatch(es)"
[ "$mismatches" -eq 0 ] || exit 1
