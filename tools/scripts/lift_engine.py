#!/usr/bin/env python3
"""lift_engine.py — one-shot textual rewrite of the legacy rename engine.

The legacy `nadia_sync/` engine uses its own package name (`nadia_sync`) in
absolute imports, docstrings, and exception qualifiers. When we lift it into
`overlay/hermes_sync/`, those references would still say `nadia_sync` and the
package would not be importable from the new path.

Worse, the engine's purpose is to rewrite `hermes_*` → `nadia_*` at build
time. If overlay/hermes_sync/ retains `nadia_sync` literals, the engine's own
pass would not touch them, and the built dist/nadia/ would have a confused
mix of `nadia_sync` and `nadia_sync` (no change). We want the engine in
*overlay* to read as `hermes_sync` so the build-time rename pass produces
`nadia_sync` in dist/.

Solution: at lift time, rewrite every `nadia_sync` token in the engine's
source to `hermes_sync`. The engine is then importable from
`overlay/hermes_sync/` and renames itself back to `nadia_sync` at build.

Usage
-----

    # Forward direction (legacy → overlay):
    python tools/scripts/lift_engine.py \\
        --source ~/Code/nadia-agent/nadia_sync \\
        --target overlay/hermes_sync

    # Reverse direction (round-trip verification):
    python tools/scripts/lift_engine.py --reverse \\
        --source overlay/hermes_sync \\
        --target /tmp/engine-roundtrip
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

# Files we rewrite. Conservatively limited to text formats the engine
# actually uses; binary or unrelated files are copied verbatim.
TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".md", ".txt", ".cfg", ".json"}


def _rewrite_text(text: str, *, reverse: bool) -> str:
    """Rewrite nadia_sync ↔ hermes_sync tokens.

    Conservative substitution: only the literal substring `nadia_sync` (or
    `hermes_sync` in reverse mode) is replaced. We do not match adjacent
    chars; the engine's own source never uses `nadia_sync_x` or similar,
    so simple `str.replace` is safe and traceable.
    """
    if reverse:
        return text.replace("hermes_sync", "nadia_sync")
    return text.replace("nadia_sync", "hermes_sync")


def _copy_with_rewrite(src: Path, dst: Path, *, reverse: bool) -> int:
    """Copy *src* tree to *dst*, rewriting tokens in text files.

    Returns the number of files whose content was touched by the rewrite.
    """
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    touched = 0
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        if any(part == "__pycache__" for part in path.parts):
            continue
        rel = path.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            new_text = _rewrite_text(text, reverse=reverse)
            out.write_text(new_text, encoding="utf-8")
            if new_text != text:
                touched += 1
        else:
            shutil.copy2(path, out)
    return touched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lift_engine.py")
    parser.add_argument("--source", required=True, type=Path, help="source directory")
    parser.add_argument("--target", required=True, type=Path, help="target directory")
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="reverse the rewrite (hermes_sync → nadia_sync, for round-trip verification)",
    )
    args = parser.parse_args(argv)
    if not args.source.is_dir():
        print(f"error: source not a directory: {args.source}", file=sys.stderr)
        return 1
    touched = _copy_with_rewrite(args.source, args.target, reverse=args.reverse)
    direction = "hermes_sync → nadia_sync" if args.reverse else "nadia_sync → hermes_sync"
    print(f"lift_engine: {direction} ({touched} files rewritten) → {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
