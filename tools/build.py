#!/usr/bin/env python3
"""tools/build.py — produce dist/nadia/ from upstream + patches + overlay.

Pipeline (spec FR-4):

1. Clean slate: `rm -rf dist/nadia/`.
2. Copy `upstream/*` → `dist/nadia/` (preserving file modes).
3. `cd dist/nadia && quilt push -a` to apply the patch series.
4. Copy `overlay/*` → `dist/nadia/` (failing if any path collides
   post-patch).
5. Copy customer-facing FDE helper scripts into `dist/nadia/scripts/`.
6. Prune `packaging-strip.yaml` denylisted paths from `dist/nadia/` (fork
   denylist; removes the China-platform surface from BOTH the native install
   and the image without patching hot upstream files — see that file's header).
7. Run `tools/rebrand.py dist/nadia/` to apply the hermes→nadia rename.
8. Run `tools/run_assertions.py` (if present, M3.1) to enforce per-patch
   grep assertions.
9. Write `dist/nadia/.nadia/build-manifest.json` (deterministic JSON,
   sort_keys=True, indent=2).

Exits non-zero on any step failure with a clear error message and the
offending path/patch.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist" / "nadia"
UPSTREAM_DIR = REPO_ROOT / "upstream"
OVERLAY_DIR = REPO_ROOT / "overlay"
PATCHES_DIR = REPO_ROOT / "patches"
ASSERTS_DIR = PATCHES_DIR / "asserts"
RENAME_YAML = REPO_ROOT / "nadia-rename.yaml"
# Overlay constants module baked from nadia-rename.yaml so `nadia doctor --static`
# works in the published image where the yaml is intentionally absent
# (issue #4). Regenerated on every build to keep the yaml as single source of
# truth.
RENAME_DEFAULTS = OVERLAY_DIR / "hermes_cli" / "_rename_defaults.py"
STRIP_YAML = REPO_ROOT / "packaging-strip.yaml"
FDE_SCRIPT_NAMES = (
    "nadia-fde-provision.sh",
    "nadia-fde-provision.ps1",
    "nadia-customer-init",
    "nadia-customer-init.ps1",
)

# China-platform filename tokens for the post-prune residual scan. Distinctive
# enough to avoid false positives — note NOT "lark" (collides with the `lark`
# parser library; the China files are named feishu/dingtalk/wecom/weixin/qqbot/
# yuanbao). Matched against FILE NAMES only, never file content: the inert
# enum/branch refs intentionally left in gateway/run.py & gateway/config.py are
# never-executed dead code (see packaging-strip.yaml header), so scanning
# content would false-positive on them.
_CHINA_RESIDUAL_TOKENS = ("feishu", "dingtalk", "wecom", "weixin", "qqbot", "yuanbao")
# Code dirs scanned for surviving China-named files after the prune. Covers the
# whole gateway/ (not just platforms/) and hermes_cli/ — the latter because
# hermes_cli/dingtalk_auth.py was a real first-pass miss the narrower scan did
# not catch. Kept to code trees (china PLATFORM additions land here); docs under
# website/ are handled by the china-docs denylist group, not this hard scan.
_RESIDUAL_SCAN_DIRS = ("gateway", "hermes_cli", "tools", "skills")

# Release-date stamp. The banner's "(YYYY.M.D)" comes from __release_date__ in
# nadia_cli/__init__.py; since the build regenerates that file from pristine
# upstream/, the value arrives as upstream's. A release build overrides it via
# $NADIA_RELEASE_DATE (see _stamp_release_date). Mirrors the calver shape used by
# tools/nadia_release.py / tools/apply_release_bump.py.
_RELEASE_DATE_RE = re.compile(r'__release_date__\s*=\s*"[^"]+"')
_CALVER_RE = re.compile(r"^\d{4}\.\d+\.\d+(?:\.\d+)?$")


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
    _log("copy upstream/ → dist/nadia/ (preserving modes)")
    if not UPSTREAM_DIR.is_dir():
        raise BuildError("copy-upstream", f"upstream/ not found at {UPSTREAM_DIR}")
    # shutil.copytree preserves modes by default; we exclude .commit and any
    # vcs metadata that might leak in.
    #
    # Skip Python bytecode caches: running tests against upstream/ (e.g.
    # `PYTHONPATH=upstream pytest`) leaves untracked __pycache__/*.pyc behind,
    # and copying them verbatim lands compiled artifacts in dist/nadia/ — which
    # the China-strip step then trips on (a stripped *.py whose orphan *.pyc
    # survives the prune reads as un-denylisted drift). They are never source.
    for item in UPSTREAM_DIR.iterdir():
        if item.name == ".commit":
            continue  # tracking file, not part of the source tree
        if item.name == "__pycache__" or item.suffix in (".pyc", ".pyo"):
            continue  # bytecode cache / build artifact — never ship
        dst = DIST_DIR / item.name
        if item.is_dir():
            shutil.copytree(
                item, dst, symlinks=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )
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


def _strip_quilt_state() -> None:
    """Remove quilt's ``.pc/`` bookkeeping from ``dist/nadia/`` after patches apply.

    ``quilt push -a`` leaves a ``.pc/`` tree of per-patch backup copies inside
    ``dist/nadia/``. It is build-only state (needed for ``pop``/``refresh``, which
    the build never does), so shipping it would bloat the release tarball and the
    Docker image with pre-rename backup files (e.g. stale ``/main/`` install
    URLs that no longer exist in the live tree). Strip it so the artifact — and
    the rename pass that follows — only sees the real renamed tree.
    """
    pc_dir = DIST_DIR / ".pc"
    if pc_dir.exists():
        _log(f"strip quilt state: {pc_dir}")
        shutil.rmtree(pc_dir)


def _regenerate_rename_defaults() -> None:
    """Regenerate overlay/hermes_cli/_rename_defaults.py from nadia-rename.yaml.

    Keeps the baked Python constants in lock-step with the yaml on every
    build. The published Docker image relies on this module for
    ``nadia doctor --static`` since nadia-rename.yaml is not shipped at
    runtime (spec FR-7, issue #4).
    """
    _log("rename-defaults: tools/generate_rename_defaults.py")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "generate_rename_defaults.py"),
            "--rename-yaml",
            str(RENAME_YAML),
            "--out",
            str(RENAME_DEFAULTS),
        ],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise BuildError(
            "rename-defaults",
            f"tools/generate_rename_defaults.py failed\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )


def _copy_overlay() -> list[str]:
    """Copy overlay/* into dist/nadia/. Fails on path collision.

    Returns sorted list of overlay file paths relative to dist/nadia/.
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


def _copy_fde_scripts() -> list[str]:
    """Copy customer-facing FDE helpers into the release tree's scripts dir."""
    added: list[str] = []
    scripts_dir = DIST_DIR / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for name in FDE_SCRIPT_NAMES:
        src = REPO_ROOT / "scripts" / name
        if not src.is_file():
            raise BuildError("fde-scripts", f"missing customer helper script: scripts/{name}")
        dst = scripts_dir / name
        if dst.exists():
            raise BuildError("fde-scripts", f"refusing to overwrite existing dist script: scripts/{name}")
        shutil.copy2(src, dst)
        added.append(f"scripts/{name}")
    _log(f"fde-scripts: copied {len(added)} files")
    return added


def _load_strip_doc() -> dict:
    """Parse packaging-strip.yaml into a dict (empty if the file is absent)."""
    if not STRIP_YAML.is_file():
        return {}
    import yaml  # pyyaml is a maintainer-flow prerequisite (see AGENTS.md)

    return yaml.safe_load(STRIP_YAML.read_text(encoding="utf-8")) or {}


def _load_strip_groups() -> list[dict]:
    """Return the path-prune groups declared in packaging-strip.yaml."""
    groups = _load_strip_doc().get("groups", []) or []
    if not isinstance(groups, list):
        raise BuildError("strip", "packaging-strip.yaml: 'groups' must be a list")
    return groups


def _strip_excluded_paths() -> list[str]:
    """Remove packaging-strip.yaml denylisted paths from dist/nadia/.

    Runs after overlay and BEFORE rebrand, on the assembled (still hermes-named)
    tree. Two self-policing guards keep the denylist honest across upstream
    syncs (see packaging-strip.yaml header for the full rationale):

      * STALE entry — a denylisted path that no longer exists raises, so the
        entry gets re-reviewed instead of silently masking upstream drift.
      * RESIDUAL China file — after pruning, any China-named file/dir left under
        _RESIDUAL_SCAN_DIRS raises (an upstream sync added a new China platform
        we have not denylisted), enforcing "no leftovers" at the file level.

    Returns the sorted list of removed repo-relative paths (for the manifest).
    """
    removed: list[str] = []
    for group in _load_strip_groups():
        for raw in group.get("paths", []) or []:
            rel = str(raw).strip()
            if not rel:
                continue
            target = DIST_DIR / rel
            if not target.exists():
                raise BuildError(
                    "strip",
                    f"stale packaging-strip.yaml entry: {rel!r} not found in "
                    f"dist/nadia/ (upstream renamed or removed it?). Re-review "
                    f"the entry in group {group.get('name', '?')!r}.",
                )
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(rel)

    # "No leftovers" assert: no China-named code may survive in the scan dirs.
    for scan_rel in _RESIDUAL_SCAN_DIRS:
        scan_dir = DIST_DIR / scan_rel
        if not scan_dir.is_dir():
            continue
        for entry in scan_dir.rglob("*"):
            name = entry.name.lower()
            if any(tok in name for tok in _CHINA_RESIDUAL_TOKENS):
                rel = entry.relative_to(DIST_DIR)
                raise BuildError(
                    "strip",
                    f"un-denylisted China path survived prune: {rel} (an upstream "
                    f"sync likely added it). Add it to packaging-strip.yaml.",
                )

    removed.sort()
    _log(f"strip: removed {len(removed)} denylisted paths")
    return removed


def _apply_content_edits() -> list[str]:
    """Apply packaging-strip.yaml ``content_edits`` (find→replace) to dist/nadia/.

    For China references that live INLINE inside a KEPT upstream file — where a
    path-prune cannot help and the fork carries no quilt patch. Today: the
    yuanbao example in the ``send_message`` tool description (model-facing) and
    the China keys in the gateway setup-menu builder (user-facing). Runs after
    the path-prune and BEFORE rebrand, on hermes-named content; anchors are
    chosen rename-invariant. This is a build-time content transform (the same
    class as the rebrand rename) — NOT a quilt patch; patches/ and upstream/
    stay pristine.

    Each rule's ``find`` MUST occur at least once: a missing anchor (upstream
    rewrote the spot) raises, so the edit can never silently no-op and leave the
    leftover behind — the same loud-on-drift contract as the path-prune.
    """
    applied: list[str] = []
    for rule in _load_strip_doc().get("content_edits", []) or []:
        rel = str(rule.get("file", "")).strip()
        find = rule.get("find")
        replace = rule.get("replace", "")
        name = rule.get("name", rel)
        if not rel or find is None:
            raise BuildError("content-edit", f"content_edits rule missing file/find: {rule!r}")
        target = DIST_DIR / rel
        if not target.is_file():
            raise BuildError("content-edit", f"content_edits target not found: {rel!r}")
        text = target.read_text(encoding="utf-8")
        if find not in text:
            raise BuildError(
                "content-edit",
                f"stale content_edits anchor in {rel!r} (rule {name!r}): find-string "
                f"not present — upstream likely rewrote it. Re-review the rule.",
            )
        target.write_text(text.replace(find, replace), encoding="utf-8")
        applied.append(name)
    if applied:
        _log(f"content-edits: applied {len(applied)} edits")
    return sorted(set(applied))


def _run_rebrand(upstream_sha: str) -> list[str]:
    """Run tools/rebrand.py against dist/nadia/. Returns sorted files-touched list.

    Invokes rebrand.py with ``--no-manifest`` so the rename engine does NOT
    write its own ``.nadia/sync-manifest.json`` (which would carry a
    wall-clock ``ran_at`` not honouring ``SOURCE_DATE_EPOCH``, breaking
    AC-8 determinism). Instead, rebrand.py emits the touched-files list
    as a single JSON object on stdout; we parse it and fold the list into
    the authoritative ``build-manifest.json`` written below
    (spec FR-6: one manifest is enough).
    """
    _log("rename: tools/rebrand.py dist/nadia/ (--no-manifest, JSON on stdout)")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "tools" / "rebrand.py"),
            str(DIST_DIR),
            "--upstream-sha",
            upstream_sha,
            "--no-manifest",
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
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BuildError(
            "rename",
            f"tools/rebrand.py emitted non-JSON stdout: {exc}\nstdout: {result.stdout}",
        ) from exc
    files = data.get("files_touched", [])
    if not isinstance(files, list):
        raise BuildError(
            "rename",
            f"tools/rebrand.py JSON missing files_touched list: {data!r}",
        )
    return sorted(str(f) for f in files)


def _stamp_release_date() -> str | None:
    """Stamp the Nadia release date into dist/nadia/nadia_cli/__init__.py.

    ``make build`` regenerates the tree from pristine ``upstream/``, so the
    rebuilt ``__release_date__`` is UPSTREAM's value. For a RELEASE build the
    Nadia calver date (the git tag, e.g. ``v2026.6.5``) must replace it, or the
    image's ``nadia --version`` disagrees with the native install — which
    ``release.yml`` stamps post-build. The date comes from ``$NADIA_RELEASE_DATE``
    because its natural source, the git tag, is unreachable inside the hermetic
    docker builder (``.dockerignore`` excludes ``.git``). Unset → no-op: dev
    builds (PR / main / local) keep upstream's date, honest for an unreleased
    tree. ``__version__`` is left alone — it tracks upstream verbatim, so the
    rebuilt value is already correct.

    Runs AFTER rebrand (the file is ``nadia_cli/__init__.py`` by then). Returns
    the stamped date, or ``None`` when no stamp was requested.
    """
    date = os.environ.get("NADIA_RELEASE_DATE", "").strip()
    if not date:
        _log("release-date: NADIA_RELEASE_DATE unset — keeping upstream value (dev build)")
        return None
    if not _CALVER_RE.match(date):
        raise BuildError(
            "release-date", f"NADIA_RELEASE_DATE not YYYY.M.D[.N]: {date!r}"
        )
    init_path = DIST_DIR / "nadia_cli" / "__init__.py"
    if not init_path.is_file():
        raise BuildError("release-date", f"version file missing after rebrand: {init_path}")
    text = init_path.read_text(encoding="utf-8")
    if not _RELEASE_DATE_RE.search(text):
        raise BuildError(
            "release-date", f"__release_date__ assignment not found in {init_path}"
        )
    init_path.write_text(
        _RELEASE_DATE_RE.sub(f'__release_date__ = "{date}"', text), encoding="utf-8"
    )
    _log(f"release-date: stamped __release_date__ = {date!r}")
    return date


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


def _write_build_manifest(
    *,
    upstream_sha: str,
    patches_applied: list[str],
    overlay_files_added: list[str],
    paths_stripped: list[str],
    content_edits_applied: list[str],
    files_touched_by_rename: list[str],
    assertions_checked: list[str],
) -> Path:
    manifest_dir = DIST_DIR / ".nadia"
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
        "content_edits_applied": sorted(content_edits_applied),
        "files_touched_by_rename": files_touched_by_rename,
        "overlay_files_added": overlay_files_added,
        "paths_stripped": sorted(paths_stripped),
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
    _strip_quilt_state()
    _regenerate_rename_defaults()
    overlay_added = _copy_overlay()
    fde_scripts_added = _copy_fde_scripts()
    stripped = _strip_excluded_paths()
    content_edited = _apply_content_edits()
    touched = _run_rebrand(upstream_sha)
    _stamp_release_date()
    assertions = _run_assertions(applied)
    _write_build_manifest(
        upstream_sha=upstream_sha,
        patches_applied=applied,
        overlay_files_added=overlay_added + fde_scripts_added,
        paths_stripped=stripped,
        content_edits_applied=content_edited,
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
