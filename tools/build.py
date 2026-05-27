#!/usr/bin/env python3
"""tools/build.py — produce dist/argo/ from upstream + patches + overlay.

Pipeline (spec FR-4):

1. Clean slate: `rm -rf dist/argo/`.
2. Copy `upstream/*` → `dist/argo/` (preserving file modes).
3. `cd dist/argo && quilt push -a` to apply the patch series.
4. Copy `overlay/*` → `dist/argo/` (failing if any path collides
   post-patch).
5. Run `tools/rebrand.py dist/argo/` to apply the hermes→argo rename.
6. Run `tools/run_assertions.py` (if present, M3.1) to enforce per-patch
   grep assertions.
7. Write `dist/argo/.argo/build-manifest.json` (deterministic JSON,
   sort_keys=True, indent=2).

Exits non-zero on any step failure with a clear error message and the
offending path/patch.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist" / "argo"
UPSTREAM_DIR = REPO_ROOT / "upstream"
OVERLAY_DIR = REPO_ROOT / "overlay"
PATCHES_DIR = REPO_ROOT / "patches"
ASSERTS_DIR = PATCHES_DIR / "asserts"
RENAME_YAML = REPO_ROOT / "argo-rename.yaml"


class BuildError(RuntimeError):
    """Build pipeline failure with a step label and a human-readable message."""

    def __init__(self, step: str, message: str) -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


def _log(msg: str) -> None:
    print(f"→ {msg}")


def _run(cmd: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, capturing stdout/stderr; raise on non-zero if check."""
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise BuildError(
            step=cmd[0],
            message=f"command failed: {' '.join(cmd)}\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
    return result


def _clean_dist() -> None:
    _log(f"clean: {DIST_DIR}")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)


def _copy_upstream() -> None:
    _log(f"copy upstream/ → dist/argo/ (preserving modes)")
    if not UPSTREAM_DIR.is_dir():
        raise BuildError("copy-upstream", f"upstream/ not found at {UPSTREAM_DIR}")
    # shutil.copytree preserves modes by default; we exclude .commit and any
    # vcs metadata that might leak in.
    for item in UPSTREAM_DIR.iterdir():
        if item.name == ".commit":
            continue  # tracking file, not part of the source tree
        dst = DIST_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dst, symlinks=True)
        else:
            shutil.copy2(item, dst)


def _apply_patches() -> list[str]:
    """Apply the quilt patch series via `quilt push -a`.

    Returns the list of applied patch filenames. Empty list if series is
    empty (legitimate for M1 / M2).
    """
    series = PATCHES_DIR / "series"
    if not series.exists():
        return []
    # An empty series is a legitimate no-op.
    applied = [
        line.strip()
        for line in series.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not applied:
        _log("patches: series is empty (no-op)")
        return []

    _log(f"apply {len(applied)} patches via quilt push -a")
    # quilt looks for patches in $QUILT_PATCHES relative to cwd (default
    # "patches"). We point it at the repo root's patches/ via the env var.
    env = {**os.environ, "QUILT_PATCHES": str(PATCHES_DIR), "QUILT_SERIES": "series"}
    result = subprocess.run(
        ["quilt", "push", "-a"],
        cwd=str(DIST_DIR),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise BuildError(
            "patches",
            f"quilt push -a failed\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
    return applied


def _copy_overlay() -> list[str]:
    """Copy overlay/* into dist/argo/. Fails on path collision.

    Returns sorted list of overlay file paths relative to dist/argo/.
    """
    if not OVERLAY_DIR.is_dir():
        _log("overlay: directory not present (skipping)")
        return []

    added: list[str] = []
    for src in OVERLAY_DIR.rglob("*"):
        if src.is_dir():
            continue
        if any(part == "__pycache__" for part in src.parts):
            continue
        rel = src.relative_to(OVERLAY_DIR)
        dst = DIST_DIR / rel
        if dst.exists():
            raise BuildError(
                "overlay",
                f"overlay path collides with patched upstream: {rel}",
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        added.append(str(rel))

    added.sort()
    _log(f"overlay: copied {len(added)} files")
    return added


def _run_rebrand(upstream_sha: str) -> int:
    """Run tools/rebrand.py against dist/argo/. Returns files touched count.

    Lets rebrand.py write its own sync-manifest.json under dist/argo/.argo/;
    build.py reads it back to populate the build-manifest's
    files_touched_by_rename field. Both manifests ship in the artifact —
    the sync-manifest documents what the engine did; the build-manifest
    documents the whole pipeline.
    """
    _log("rename: tools/rebrand.py dist/argo/")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "rebrand.py"),
            str(DIST_DIR),
            "--upstream-sha",
            upstream_sha,
        ],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise BuildError(
            "rename",
            f"tools/rebrand.py failed\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
    # Parse the "rebrand: N files touched" line. Best-effort; manifest is
    # the authoritative count.
    n = 0
    for line in result.stdout.splitlines():
        if line.startswith("rebrand:"):
            try:
                n = int(line.split()[1])
            except (IndexError, ValueError):
                pass
    return n


def _run_assertions(applied_patches: list[str]) -> list[str]:
    """Run tools/run_assertions.py if it exists. Returns list of patches checked.

    M3.1 implements the assertion runner. Until then, this step is a no-op
    that simply lists patches with assertion files.
    """
    runner = REPO_ROOT / "tools" / "run_assertions.py"
    if not runner.is_file():
        _log("assertions: tools/run_assertions.py not yet present (M3.1) — skipping")
        return []
    _log(f"assertions: tools/run_assertions.py {DIST_DIR}")
    result = subprocess.run(
        [sys.executable, str(runner), str(DIST_DIR)],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise BuildError(
            "assertions",
            f"tools/run_assertions.py failed\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
    return [p for p in applied_patches if (ASSERTS_DIR / f"{Path(p).stem}.txt").exists()]


def _upstream_sha() -> str:
    commit_file = UPSTREAM_DIR / ".commit"
    if not commit_file.is_file():
        return ""
    return commit_file.read_text(encoding="utf-8").strip()


def _files_touched_by_rename(manifest_dir: Path) -> list[str]:
    """Pull files_touched out of the engine's own manifest if it wrote one."""
    sync_manifest = manifest_dir / ".argo" / "sync-manifest.json"
    if not sync_manifest.is_file():
        return []
    data = json.loads(sync_manifest.read_text(encoding="utf-8"))
    return sorted(data.get("files_touched", []))


def _write_build_manifest(
    *,
    upstream_sha: str,
    patches_applied: list[str],
    overlay_files_added: list[str],
    files_touched_by_rename: list[str],
    assertions_checked: list[str],
) -> Path:
    manifest_dir = DIST_DIR / ".argo"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "build-manifest.json"
    # Honor SOURCE_DATE_EPOCH for reproducibility (spec NFR-4 + AC-8).
    sde = os.environ.get("SOURCE_DATE_EPOCH")
    if sde:
        ran_at = datetime.fromtimestamp(int(sde), tz=timezone.utc).isoformat()
    else:
        ran_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "assertions_checked": sorted(assertions_checked),
        "files_touched_by_rename": files_touched_by_rename,
        "overlay_files_added": overlay_files_added,
        "patches_applied": patches_applied,
        "ran_at": ran_at,
        "upstream_sha": upstream_sha,
    }
    manifest.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    _log(f"manifest: {manifest}")
    return manifest


def build() -> int:
    upstream_sha = _upstream_sha()
    if not upstream_sha:
        raise BuildError("preconditions", "upstream/.commit missing or empty")

    _clean_dist()
    _copy_upstream()
    applied = _apply_patches()
    overlay_added = _copy_overlay()
    _run_rebrand(upstream_sha)
    touched = _files_touched_by_rename(DIST_DIR)
    assertions = _run_assertions(applied)
    _write_build_manifest(
        upstream_sha=upstream_sha,
        patches_applied=applied,
        overlay_files_added=overlay_added,
        files_touched_by_rename=touched,
        assertions_checked=assertions,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build.py")
    parser.parse_args(argv)
    try:
        return build()
    except BuildError as exc:
        print(f"✗ build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
