#!/usr/bin/env python3
"""tools/run_assertions.py — per-patch grep-assertion runner (FR-14).

Each load-bearing patch in `patches/series` may declare a file at
`patches/asserts/<patch-basename>.txt` containing grep patterns that
MUST be satisfied in the built `dist/nadia/` tree. If any pattern fails,
the build fails — catching the legacy failure mode where `quilt refresh`
after manual conflict resolution silently dropped fork-feature lines.

Assertion file format
---------------------

```
# Comments start with '#'. Blank lines ignored.

# Fixed-string pattern (default): the literal string must appear
# somewhere under dist/nadia/.
ghcr.io/nadicodeai/nadia

# Path-restricted: the pattern must appear in files matching the glob.
path:nadia_cli/main.py
path:.github/workflows/* if: false

# Regex (slower but flexible): the regex must match somewhere.
regex:^def cmd_nadia_update

# Path + regex combined: the regex must match in files matching the glob.
path:nadia_cli/main.py regex:cmd_nadia_update
```

Exit codes
----------

- 0: all assertions satisfied.
- 1: one or more failures (per-assertion stderr report).
- 2: usage error.

`patches/asserts/manifest.txt` (optional) lists patches whose assertion
file is REQUIRED. A patch listed in the manifest but missing an
assertion file is an error.

Repo root
---------

By default, the runner derives the repo root from its own location
(`Path(__file__).parent.parent`, NOT resolved — so a symlinked
`tools/run_assertions.py` in a test fake-repo stays scoped to that
fake repo). Override explicitly with `--repo-root`.
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from dataclasses import dataclass
from pathlib import Path


def _default_repo_root() -> Path:
    return Path(__file__).parent.parent


@dataclass(frozen=True)
class Assertion:
    """Parsed assertion line."""

    raw: str
    path_glob: str | None
    regex: re.Pattern[str] | None
    literal: str | None
    source_file: Path
    source_lineno: int


def parse_assertion(line: str, source: Path, lineno: int) -> Assertion | None:
    """Parse a single non-comment line. Returns None for blank/comment lines."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    path_glob: str | None = None
    rest = stripped

    if rest.startswith("path:"):
        parts = rest.split(maxsplit=1)
        path_glob = parts[0][len("path:") :]
        rest = parts[1] if len(parts) > 1 else ""

    if rest.startswith("regex:"):
        pattern_src = rest[len("regex:") :].strip()
        try:
            return Assertion(
                raw=stripped,
                path_glob=path_glob,
                regex=re.compile(pattern_src),
                literal=None,
                source_file=source,
                source_lineno=lineno,
            )
        except re.error as exc:
            raise ValueError(f"{source}:{lineno}: invalid regex: {exc}") from exc

    literal = rest
    return Assertion(
        raw=stripped,
        path_glob=path_glob,
        regex=None,
        literal=literal if literal else None,
        source_file=source,
        source_lineno=lineno,
    )


def load_assertions(asserts_file: Path) -> list[Assertion]:
    out: list[Assertion] = []
    for lineno, line in enumerate(
        asserts_file.read_text(encoding="utf-8").splitlines(), start=1
    ):
        parsed = parse_assertion(line, asserts_file, lineno)
        if parsed is not None:
            out.append(parsed)
    return out


def iter_files(target: Path, path_glob: str | None) -> list[Path]:
    files: list[Path] = []
    for p in target.rglob("*"):
        if not p.is_file():
            continue
        rel = str(p.relative_to(target))
        if path_glob is None or fnmatch.fnmatch(rel, path_glob):
            files.append(p)
    return files


def check_assertion(target: Path, a: Assertion) -> bool:
    """Return True if the assertion is satisfied somewhere under target."""
    files = iter_files(target, a.path_glob)
    if a.path_glob is not None and not files:
        return False
    if a.literal is None and a.regex is None:
        return bool(files)
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if a.literal is not None and a.literal in text:
            return True
        if a.regex is not None and a.regex.search(text):
            return True
    return False


def applied_patches_from_series(series_path: Path) -> list[str]:
    if not series_path.exists():
        return []
    return [
        ln.strip()
        for ln in series_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def required_patches_from_manifest(manifest_path: Path) -> list[str]:
    if not manifest_path.exists():
        return []
    return [
        ln.strip()
        for ln in manifest_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def run(repo_root: Path, target: Path, *, verbose: bool = False) -> int:
    patches_dir = repo_root / "patches"
    asserts_dir = patches_dir / "asserts"
    series_path = patches_dir / "series"
    manifest_path = asserts_dir / "manifest.txt"

    applied = applied_patches_from_series(series_path)
    required = set(required_patches_from_manifest(manifest_path))

    failures: list[tuple[Assertion, str]] = []
    checked_patches: list[str] = []
    missing_required: list[str] = []

    for patch_name in applied:
        stem = Path(patch_name).stem
        asserts_file = asserts_dir / f"{stem}.txt"
        if not asserts_file.is_file():
            if patch_name in required:
                missing_required.append(patch_name)
            continue
        try:
            assertions = load_assertions(asserts_file)
        except ValueError as exc:
            print(f"✗ {exc}", file=sys.stderr)
            return 1
        if verbose:
            print(f"  checking {patch_name}: {len(assertions)} assertion(s)")
        for a in assertions:
            if not check_assertion(target, a):
                failures.append((a, patch_name))
        checked_patches.append(patch_name)

    if missing_required:
        print(
            "✗ patches in patches/asserts/manifest.txt have no assertion file:",
            file=sys.stderr,
        )
        for p in missing_required:
            print(f"  - {p}", file=sys.stderr)
        return 1

    if failures:
        print(
            f"✗ {len(failures)} assertion failure(s) across {len({p for _, p in failures})} patch(es):",
            file=sys.stderr,
        )
        for a, patch in failures:
            print(
                f"  [{patch}] {a.source_file.name}:{a.source_lineno}: {a.raw}",
                file=sys.stderr,
            )
        return 1

    total = sum(
        len(load_assertions(asserts_dir / f"{Path(p).stem}.txt"))
        for p in checked_patches
    )
    print(
        f"run_assertions: {total} assertion(s) across {len(checked_patches)} patch(es) satisfied"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_assertions.py",
        description="Enforce per-patch grep assertions over the built tree.",
    )
    parser.add_argument("target", type=Path, help="built tree (typically dist/nadia/)")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="nadia repo root (default: derived from script location).",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target not a directory: {args.target}", file=sys.stderr)
        return 2
    if not args.repo_root.is_dir():
        print(f"error: repo root not a directory: {args.repo_root}", file=sys.stderr)
        return 2

    return run(args.repo_root, args.target, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
