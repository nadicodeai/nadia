#!/usr/bin/env python3
"""tools/verify_no_leakage.py — config-aware static leakage scanner.

Spec FR-12. Scans a target directory (typically `dist/argo/`) for
case-insensitive `hermes` occurrences and reports any hit NOT covered by
`argo-rename.yaml`'s `exceptions:` (path globs) or `skip_contexts:` (regex
patterns).

A naive `grep -i hermes` is insufficient and explicitly forbidden —
`argo-rename.yaml` itself contains `hermes` literals as FROM keys, and the
engine's own pass code legitimately contains `hermes` in skip_contexts'
URL allowlists.

Exit codes
----------
- 0: clean (every `hermes` occurrence is exception-covered).
- 1: leakage detected.
- 2: usage error.

Usage
-----
    python tools/verify_no_leakage.py <target-dir> \\
        [--rename-yaml <path>] [--verbose]
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path
from typing import Iterable

import yaml

# Files we do not scan at all (binary or huge; case-insensitive grep would
# either error or produce false positives).
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2", ".zst", ".xz",
    ".so", ".dylib", ".dll", ".o", ".a",
    ".pyc", ".pyo",
    ".mp3", ".mp4", ".webm", ".mov",
}

# Directories we never recurse into.
SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv"}


class LeakageReport:
    """Collects per-file hits with line numbers."""

    def __init__(self) -> None:
        self.hits: dict[Path, list[tuple[int, str]]] = {}

    def add(self, path: Path, lineno: int, line: str) -> None:
        self.hits.setdefault(path, []).append((lineno, line.rstrip()))

    def any_hits(self) -> bool:
        return bool(self.hits)

    def file_count(self) -> int:
        return len(self.hits)

    def total_lines(self) -> int:
        return sum(len(v) for v in self.hits.values())


def load_config(yaml_path: Path) -> tuple[list[str], list[re.Pattern[str]]]:
    """Return (exception_globs, compiled_skip_context_regexes)."""
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    exceptions = [e["path"] for e in data.get("exceptions", []) if "path" in e]
    skip_contexts = [re.compile(s) for s in data.get("skip_contexts", [])]
    return exceptions, skip_contexts


def path_is_excepted(rel_path: str, globs: Iterable[str]) -> bool:
    """True if rel_path matches any exception glob.

    Globs are matched via fnmatch — the same semantics the rename engine
    uses. Trailing `/**` is treated as a recursive directory match.
    """
    for g in globs:
        if fnmatch.fnmatch(rel_path, g):
            return True
        # Manual `/**` handling for prefix-style globs like "foo/**"
        if g.endswith("/**") and rel_path.startswith(g[:-3] + "/"):
            return True
    return False


def line_is_only_skip_context_hermes(
    line: str, regexes: list[re.Pattern[str]]
) -> bool:
    """True if every `hermes` in *line* is covered by a skip_contexts match.

    We collect all positions of `hermes` (case-insensitive), then check that
    each position is inside at least one skip_contexts regex span.
    """
    positions = [m.start() for m in re.finditer(r"hermes", line, re.IGNORECASE)]
    if not positions:
        return True

    covered: set[int] = set()
    for rx in regexes:
        for m in rx.finditer(line):
            start, end = m.start(), m.end()
            for pos in positions:
                if start <= pos < end:
                    covered.add(pos)

    return len(covered) == len(positions)


def scan_file(
    path: Path,
    rel: str,
    skip_contexts: list[re.Pattern[str]],
    report: LeakageReport,
) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        # Non-UTF8 or unreadable; treat as binary, skip.
        return
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "hermes" not in line.lower():
            continue
        if line_is_only_skip_context_hermes(line, skip_contexts):
            continue
        report.add(path, lineno, line)


def scan(
    target: Path,
    yaml_path: Path,
    *,
    verbose: bool = False,
) -> LeakageReport:
    exception_globs, skip_contexts = load_config(yaml_path)
    report = LeakageReport()

    for path in target.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        rel = str(path.relative_to(target))
        if path_is_excepted(rel, exception_globs):
            if verbose:
                print(f"  [excepted] {rel}")
            continue
        scan_file(path, rel, skip_contexts, report)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_no_leakage.py",
        description="Scan a target tree for case-insensitive 'hermes' leakage.",
    )
    parser.add_argument("target", type=Path, help="directory to scan (e.g. dist/argo/)")
    parser.add_argument(
        "--rename-yaml",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "argo-rename.yaml",
        help="path to argo-rename.yaml",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target not a directory: {args.target}", file=sys.stderr)
        return 2
    if not args.rename_yaml.is_file():
        print(f"error: rename yaml not found: {args.rename_yaml}", file=sys.stderr)
        return 2

    report = scan(args.target, args.rename_yaml, verbose=args.verbose)

    if not report.any_hits():
        print(f"verify_no_leakage: no leakage detected in {args.target}")
        return 0

    print(
        f"verify_no_leakage: LEAKAGE — {report.file_count()} file(s), "
        f"{report.total_lines()} line(s)",
        file=sys.stderr,
    )
    for path, hits in sorted(report.hits.items()):
        for lineno, line in hits:
            print(f"  {path}:{lineno}: {line[:120]}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
