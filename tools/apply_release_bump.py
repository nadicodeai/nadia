#!/usr/bin/env python3
"""tools/apply_release_bump.py — apply the version + release-date bump to dist/argo/.

Companion to ``tools/argo_release.py``. ``argo_release.py`` runs locally on
the workshop machine, bumps the version + release-date inside the locally
built ``dist/argo/``, and tags ``main`` HEAD. ``release.yml`` then runs on
the tag push, re-builds ``dist/argo/`` from scratch on CI, and force-pushes
that tree to the ``release`` branch. The CI re-build does NOT carry the
version bump on its own (the source ``upstream/hermes_cli/__init__.py``
stays at upstream's pristine value); so this script reproduces the bump on
the CI side from the annotated tag message.

The annotated tag message argo_release.py writes is:

    Argo Agent v<VERSION> (<RELEASE_DATE>)

That message is parsed here. Without it, the script falls back to the
``--version`` and ``--release-date`` flags.

This script is workshop-side tooling; it does NOT go through the rename
engine and never lands on the ``release`` branch.

Usage
-----

    python tools/apply_release_bump.py --from-tag v2026.5.28
    python tools/apply_release_bump.py --version 0.14.1 --release-date 2026.5.28

Exit codes: 0 ok / 1 user error / 2 unexpected.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_ROOT_DEFAULT = REPO_ROOT / "dist" / "argo"

# Mirrors argo_release.py — keep in sync.
_VERSION_RE = re.compile(r'__version__\s*=\s*"[^"]+"')
_RELEASE_DATE_RE = re.compile(r'__release_date__\s*=\s*"[^"]+"')
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*"[^"]+"', re.MULTILINE)

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_CALVER_RE = re.compile(r"^\d{4}\.\d+\.\d+(?:\.\d+)?$")

# Tag message format: "Argo Agent v<VERSION> (<RELEASE_DATE>)"
_TAG_MSG_RE = re.compile(
    r"Argo Agent v(?P<version>\d+\.\d+\.\d+)\s+\((?P<release_date>\d{4}\.\d+\.\d+(?:\.\d+)?)\)"
)


def _log(msg: str) -> None:
    print(f"→ {msg}", file=sys.stderr)


def _read_tag_message(tag: str) -> tuple[str, str]:
    """Return (version, release_date) parsed from the annotated tag's message."""
    result = subprocess.run(
        ["git", "tag", "-l", "--format=%(contents:subject)", tag],
        cwd=REPO_ROOT,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    subject = result.stdout.strip()
    if not subject:
        raise SystemExit(f"tag {tag!r} has no annotated subject")
    m = _TAG_MSG_RE.search(subject)
    if not m:
        raise SystemExit(
            f"tag {tag!r} subject does not match 'Argo Agent v<X.Y.Z> "
            f"(<YYYY.M.D>)': {subject!r}"
        )
    return m.group("version"), m.group("release_date")


def _rewrite_file(path: Path, pattern: re.Pattern[str], replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    if not pattern.search(text):
        raise SystemExit(f"pattern {pattern.pattern!r} not found in {path}")
    new = pattern.sub(replacement, text)
    if new != text:
        path.write_text(new, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply argo_release.py's version+release-date bump to dist/argo/.",
    )
    parser.add_argument(
        "--from-tag",
        help="Read version + release-date from the annotated tag message.",
    )
    parser.add_argument("--version", help="Explicit version override (e.g. 0.14.1).")
    parser.add_argument(
        "--release-date", help="Explicit release-date override (e.g. 2026.5.28)."
    )
    parser.add_argument(
        "--dist-root",
        type=Path,
        default=DIST_ROOT_DEFAULT,
        help="Path to the built dist/argo/ tree (default: dist/argo).",
    )
    args = parser.parse_args(argv)

    if args.from_tag and (args.version or args.release_date):
        parser.error("--from-tag is mutually exclusive with --version / --release-date")
    if args.from_tag:
        version, release_date = _read_tag_message(args.from_tag)
    else:
        if not args.version or not args.release_date:
            parser.error("--version and --release-date both required without --from-tag")
        version = args.version
        release_date = args.release_date

    if not _SEMVER_RE.match(version):
        raise SystemExit(f"version must match X.Y.Z (got {version!r})")
    if not _CALVER_RE.match(release_date):
        raise SystemExit(f"release-date must match YYYY.M.D[.N] (got {release_date!r})")

    dist_root = args.dist_root
    init_path = dist_root / "argo_cli" / "__init__.py"
    pyproject_path = dist_root / "pyproject.toml"
    if not init_path.is_file():
        raise SystemExit(f"missing {init_path} — run `make build` first")
    if not pyproject_path.is_file():
        raise SystemExit(f"missing {pyproject_path} — run `make build` first")

    _log(f"applying bump: version={version}, release_date={release_date}")
    _rewrite_file(init_path, _VERSION_RE, f'__version__ = "{version}"')
    _rewrite_file(init_path, _RELEASE_DATE_RE, f'__release_date__ = "{release_date}"')
    _rewrite_file(pyproject_path, _PYPROJECT_VERSION_RE, f'version = "{version}"')

    verify_text = init_path.read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in verify_text:
        raise SystemExit(f"verify failed: __version__ not set in {init_path}")
    if f'__release_date__ = "{release_date}"' not in verify_text:
        raise SystemExit(f"verify failed: __release_date__ not set in {init_path}")
    _log("verify ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
