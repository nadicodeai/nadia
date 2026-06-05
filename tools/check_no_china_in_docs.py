#!/usr/bin/env python3
"""tools/check_no_china_in_docs.py — fail the build if shipped docs reference a stripped China platform.

packaging-strip.yaml removes the China messaging platforms (Feishu/Lark, DingTalk,
WeCom, Weixin/WeChat, QQ Bot, Yuanbao) from the CODE — adapters, tools, skills, the
leaf doc pages, and the zh-Hans locale. But the rest of the docs tree (landing page,
the messaging hub, the env-var / tools / toolsets reference tables, guides) still
enumerates, tabulates, and LINKS those platforms. The result shipped to
docs.nadicode.ai/argo advertises features the product does not have and links to
pages the strip deleted (live 404s).

build.py's residual scan only checks code FILE NAMES under gateway/hermes_cli/tools/
skills — it never looks at website/ CONTENT, so this whole class was invisible. This
gate closes that hole: it scans the shipped docs tree for China-platform tokens and
fails the build on any hit, so a scrub gap (or a new platform an upstream sync adds
to a shared doc) can never silently ship again.

Token set is deliberately MESSAGING-PLATFORM-specific. It excludes bare "tencent" and
bare "qq" because Tencent TokenHub is a kept model *provider* (TOKENHUB_* env vars are
legitimate) and "qq" collides with *.qq.com hostnames in non-China platform configs.

Exit codes
----------
- 0: no China-platform reference in the scanned docs tree.
- 1: at least one reference shipped.
- 2: usage error.

Usage
-----
    python tools/check_no_china_in_docs.py dist/argo/website/
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Messaging-platform tokens (case-insensitive, word-boundary). Curated to match the
# stripped platforms only — NOT bare "tencent"/"qq" (false positives on the kept
# TokenHub provider and on *.qq.com hostnames).
_CHINA_DOC_TOKENS = (
    "feishu",
    "lark",          # only ever appears as "Feishu/Lark" in these docs
    "dingtalk",
    "wecom",
    "weixin",
    "wechat",
    "yuanbao",
    "qqbot",
)
# qqbot is also written "QQ Bot" / "QQBot"; match the spaced form explicitly.
_CHINA_DOC_RE = re.compile(
    r"\b(?:" + "|".join(_CHINA_DOC_TOKENS) + r")\b|qq[ -]?bot",
    re.IGNORECASE,
)

_TEXT_SUFFIXES = {".md", ".mdx", ".ts", ".tsx", ".js", ".json", ".txt"}
_SKIP_DIRS = {"node_modules", ".docusaurus", "build", ".git", "__pycache__"}


def scan(root: Path) -> list[tuple[str, int, str]]:
    """Return [(rel_path, lineno, line)] for every China-platform reference."""
    hits: list[tuple[str, int, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(root))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _CHINA_DOC_RE.search(line):
                hits.append((rel, lineno, line.strip()))
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_no_china_in_docs.py",
        description="Fail if shipped docs reference a stripped China messaging platform.",
    )
    parser.add_argument("target", type=Path, help="docs tree to scan (e.g. dist/argo/website/)")
    parser.add_argument(
        "--list-files", action="store_true", help="print only the offending files, not every line"
    )
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target not a directory: {args.target}", file=sys.stderr)
        return 2

    hits = scan(args.target)
    if not hits:
        print(f"check_no_china_in_docs: OK — no China-platform reference in {args.target}")
        return 0

    files = sorted({rel for rel, _, _ in hits})
    print(
        f"check_no_china_in_docs: FAIL — {len(hits)} China-platform reference(s) in "
        f"{len(files)} shipped doc file(s):",
        file=sys.stderr,
    )
    if args.list_files:
        for rel in files:
            n = sum(1 for r, _, _ in hits if r == rel)
            print(f"  {n:>3}  {rel}", file=sys.stderr)
    else:
        for rel, lineno, line in hits:
            print(f"  {rel}:{lineno}: {line[:140]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
