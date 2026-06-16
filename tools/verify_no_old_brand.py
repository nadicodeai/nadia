#!/usr/bin/env python3
"""Scan a target tree for old fork-brand references.

This is the Nadia migration companion to verify_no_leakage.py. The existing
leakage scanner catches upstream `hermes` under-renames. This scanner catches
the old fork brand, `argo`, after the fork brand has moved to Nadia.

The live GitHub repository still uses the historical `nadicodeai/argo` slug.
That repository identifier is allowed; product names, commands, paths, and env
vars must still be Nadia.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2", ".zst", ".xz",
    ".so", ".dylib", ".dll", ".o", ".a",
    ".pyc", ".pyo",
    ".mp3", ".mp4", ".webm", ".mov",
}

SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}

# Catch brand-shaped tokens without flagging common substrings such as Cargo,
# argomento, argument, or argon2.
OLD_BRAND_RE = re.compile(
    r"(?<![A-Za-z])(?:"
    r"ARGO[A-Z0-9_]*\b|"
    r"Argo(?:[A-Z][A-Za-z0-9_]*|[-_][A-Za-z0-9_-]*|\b)|"
    r"argo(?:[A-Z][A-Za-z0-9_]*|[-_][A-Za-z0-9_-]*|\b)"
    r")"
)

ALLOWED_REPO_SLUG_RE = re.compile(
    r"(?:"
    r"https://github\.com/nadicodeai/argo(?:\.git)?(?:/[^\s\"'<>)]*)?(?=$|[\s\"'<>),.;])|"
    r"git@github\.com:nadicodeai/argo(?:\.git)?(?=$|[\s\"'<>),.;])|"
    r"raw\.githubusercontent\.com/nadicodeai/argo(?:/[^\s\"'<>)]*)?(?=$|[\s\"'<>),.;])|"
    r"\bnadicodeai/argo(?=$|[^A-Za-z0-9_-])"
    r")"
)


@dataclass(frozen=True)
class Hit:
    path: Path
    lineno: int | None
    text: str


class OldBrandReport:
    def __init__(self) -> None:
        self.hits: list[Hit] = []

    def add_path(self, path: Path, rel: str) -> None:
        self.hits.append(Hit(path=path, lineno=None, text=rel))

    def add_line(self, path: Path, lineno: int, line: str) -> None:
        self.hits.append(Hit(path=path, lineno=lineno, text=line.rstrip()))

    def any_hits(self) -> bool:
        return bool(self.hits)

    def file_count(self) -> int:
        return len({hit.path for hit in self.hits})


def scan_file(path: Path, report: OldBrandReport) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        return

    for lineno, line in enumerate(text.splitlines(), start=1):
        searchable_line = ALLOWED_REPO_SLUG_RE.sub("", line)
        if OLD_BRAND_RE.search(searchable_line):
            report.add_line(path, lineno, line)


def scan(target: Path) -> OldBrandReport:
    report = OldBrandReport()

    for path in target.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue

        rel = str(path.relative_to(target))
        if OLD_BRAND_RE.search(rel):
            report.add_path(path, rel)

        if not path.is_file():
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        scan_file(path, report)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_no_old_brand.py",
        description="Scan a target tree for old Argo fork-brand references.",
    )
    parser.add_argument("target", type=Path, help="directory to scan, for example dist/nadia/")
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target not a directory: {args.target}", file=sys.stderr)
        return 2

    report = scan(args.target)
    if not report.any_hits():
        print(f"verify_no_old_brand: no old-brand references detected in {args.target}")
        return 0

    print(
        f"verify_no_old_brand: OLD BRAND LEAKAGE - {report.file_count()} file(s), "
        f"{len(report.hits)} hit(s)",
        file=sys.stderr,
    )
    for hit in report.hits:
        if hit.lineno is None:
            print(f"  {hit.path}: path contains old brand: {hit.text}", file=sys.stderr)
        else:
            print(f"  {hit.path}:{hit.lineno}: {hit.text[:120]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
