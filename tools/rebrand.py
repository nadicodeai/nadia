#!/usr/bin/env python3
"""tools/rebrand.py — run the rename engine against a target directory.

Build-time entry point for the hermes→argo rebrand. Imports the engine
from `overlay/hermes_sync/` directly via `sys.path` injection (NOT from
`dist/argo/argo_sync/`), so the build pipeline works on a cold start
where `dist/` doesn't exist yet.

Usage
-----

    python tools/rebrand.py <target-dir>

The target directory is mutated in place: content rewrites, file renames,
directory renames, per the legacy rename engine's pass order (content →
filenames → directories).

Idempotency
-----------

Re-running against an already-renamed tree produces zero diffs. This is
inherited from the engine (legacy AC-3) and re-verified by
`tools/build.py`'s manifest hash check.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Inject overlay/ onto sys.path BEFORE importing the engine. This is the
# critical M1 architectural fix: the engine must be importable from the
# source tree, not from a not-yet-built dist/.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_OVERLAY = _REPO_ROOT / "overlay"
if not _OVERLAY.is_dir():
    print(f"error: overlay/ not found at {_OVERLAY}", file=sys.stderr)
    raise SystemExit(2)
sys.path.insert(0, str(_OVERLAY))

# Engine import after sys.path is configured.
from hermes_sync.config import RenameConfig  # noqa: E402  # ty: ignore[unresolved-import]
from hermes_sync.engine import RenameEngine  # noqa: E402  # ty: ignore[unresolved-import]
from hermes_sync.errors import ArgoSyncError  # noqa: E402  # ty: ignore[unresolved-import]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rebrand.py",
        description="Run the hermes→argo rename engine against a target tree.",
    )
    parser.add_argument("target", type=Path, help="directory to rename in place")
    parser.add_argument(
        "--rename-yaml",
        type=Path,
        default=_REPO_ROOT / "argo-rename.yaml",
        help="path to argo-rename.yaml (default: repo root)",
    )
    parser.add_argument(
        "--upstream-sha",
        default="",
        help="upstream sha to record in the engine's manifest (optional)",
    )
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help=(
            "skip writing .argo/sync-manifest.json; emit {\"files_touched\": [...]} "
            "JSON to stdout instead. Used by tools/build.py to preserve AC-8 "
            "determinism (engine manifest carries wall-clock ran_at)."
        ),
    )
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target not a directory: {args.target}", file=sys.stderr)
        return 1
    if not args.rename_yaml.is_file():
        print(f"error: rename yaml not found: {args.rename_yaml}", file=sys.stderr)
        return 1

    try:
        cfg = RenameConfig.load(args.rename_yaml)
        engine = RenameEngine(cfg)
        if args.no_manifest:
            # No on-disk sync-manifest. Print the touched-files list as JSON to
            # stdout so `tools/build.py` can fold it into the build-manifest.
            # This is the deterministic path: no wall-clock `ran_at` is ever
            # written to disk, so SOURCE_DATE_EPOCH determinism is preserved
            # without patching overlay/hermes_sync/ (which is lifted verbatim).
            touched = engine.apply(args.target)
            try:
                rel = sorted(
                    str(p.relative_to(args.target.resolve())).replace("\\", "/")
                    for p in (Path(t).resolve() for t in touched)
                )
            except ValueError:
                # Fallback: at least one path was not under target — emit as-is.
                rel = sorted(str(p) for p in touched)
            import json

            sys.stdout.write(json.dumps({"files_touched": rel}, sort_keys=True))
            sys.stdout.write("\n")
            n = len(rel)
        else:
            manifest_path = engine.apply_and_write_manifest(
                args.target, upstream_sha=args.upstream_sha
            )
            import json

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            n = len(data.get("files_touched", []))
    except ArgoSyncError as exc:
        print(f"rebrand failed: {exc}", file=sys.stderr)
        return 1

    # Counter line goes to stderr in --no-manifest mode so stdout stays
    # parseable JSON. Otherwise keep the legacy stdout behaviour for
    # interactive invocations.
    msg = f"rebrand: {n} files touched in {args.target}"
    if args.no_manifest:
        print(msg, file=sys.stderr)
    else:
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
