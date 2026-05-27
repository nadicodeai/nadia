#!/usr/bin/env python3
"""tools/generate_rename_defaults.py — bake argo-rename.yaml into Python constants.

Reads ``argo-rename.yaml`` at the repo root and writes a generated module to
``overlay/hermes_cli/_rename_defaults.py`` containing the mappings,
exceptions, skip_contexts, and the derived probe token as plain Python
constants.

Why this exists
---------------

``argo doctor --static`` loads ``argo-rename.yaml`` at runtime to drive the
leakage scan. Inside the published Docker image (``ghcr.io/nadicodeai/argo``)
the yaml is intentionally absent: ``argo-rename.yaml`` is build-time config
only and the Dockerfile does not copy it into the runtime stage (spec FR-7).

To keep ``argo doctor --static`` self-contained in the runtime image we bake
the mappings + exceptions + skip_contexts as a tiny Python constants module
that ships with ``argo_cli`` (the renamed ``hermes_cli`` overlay package).

``argo-rename.yaml`` REMAINS the single source of truth — this generator runs
during ``tools/build.py`` and produces the constants module fresh on every
build, so the two cannot drift.

Output schema
-------------

The generated module exports four module-level constants:

- ``MAPPINGS``       — ``tuple[tuple[str, str], ...]`` sorted longest-from-first.
- ``EXCEPTION_PATHS`` — ``tuple[str, ...]`` of path globs.
- ``SKIP_CONTEXTS``  — ``tuple[str, ...]`` of regex strings.
- ``PROBE_TOKEN``    — the bare lowercase upstream identifier (``str``).
- ``GENERATED_FROM`` — the basename of the yaml file the constants were
  generated from (``"argo-rename.yaml"`` — string literal kept out of the
  rename engine's content-rewrite via the file's own exception entry).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_YAML = _REPO_ROOT / "argo-rename.yaml"
_DEFAULT_OUT = _REPO_ROOT / "overlay" / "hermes_cli" / "_rename_defaults.py"


class GenerateError(RuntimeError):
    """Raised when generation fails (bad yaml, missing required keys, etc.)."""

    def __init__(self, message: str, *, step: str) -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load *path* and return the parsed YAML mapping."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GenerateError(f"cannot read {path}: {exc}", step="read") from exc
    try:
        data: object = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise GenerateError(f"yaml parse error in {path}: {exc}", step="parse") from exc
    if not isinstance(data, dict):
        raise GenerateError(
            f"top-level value must be a mapping, got {type(data).__name__!r}",
            step="parse",
        )
    return data


def _extract_mappings(data: dict[str, Any]) -> list[tuple[str, str]]:
    raw = data.get("mappings", [])
    if not isinstance(raw, list):
        raise GenerateError("'mappings' must be a list", step="mappings")
    out: list[tuple[str, str]] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict) or "from" not in entry or "to" not in entry:
            raise GenerateError(
                f"mappings[{i}] must be a dict with 'from' and 'to' keys",
                step="mappings",
            )
        f, t = entry["from"], entry["to"]
        if not isinstance(f, str) or not isinstance(t, str):
            raise GenerateError(
                f"mappings[{i}] 'from' and 'to' must be strings",
                step="mappings",
            )
        if not f:
            raise GenerateError(
                f"mappings[{i}] 'from' must not be empty",
                step="mappings",
            )
        out.append((f, t))
    # Sort longest-from-first to mirror RenameConfig.load semantics.
    out.sort(key=lambda p: len(p[0]), reverse=True)
    return out


def _extract_exception_paths(data: dict[str, Any]) -> list[str]:
    raw = data.get("exceptions", [])
    if not isinstance(raw, list):
        raise GenerateError("'exceptions' must be a list", step="exceptions")
    out: list[str] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict) or "path" not in entry:
            raise GenerateError(
                f"exceptions[{i}] must be a dict with a 'path' key",
                step="exceptions",
            )
        p = entry["path"]
        if not isinstance(p, str):
            raise GenerateError(
                f"exceptions[{i}] 'path' must be a string",
                step="exceptions",
            )
        out.append(p)
    return out


def _extract_skip_contexts(data: dict[str, Any]) -> list[str]:
    raw = data.get("skip_contexts", [])
    if not isinstance(raw, list):
        raise GenerateError("'skip_contexts' must be a list", step="skip_contexts")
    out: list[str] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, str):
            raise GenerateError(
                f"skip_contexts[{i}] must be a string",
                step="skip_contexts",
            )
        out.append(entry)
    return out


def _derive_probe_token(mappings: list[tuple[str, str]]) -> str:
    candidates = [f for f, _ in mappings if f.isalpha() and f.islower()]
    if not candidates:
        raise GenerateError(
            "no bare lowercase alpha 'from' key — cannot derive probe token",
            step="probe",
        )
    return sorted(candidates, key=lambda s: len(s))[0]


def _render_module(
    *,
    mappings: list[tuple[str, str]],
    exception_paths: list[str],
    skip_contexts: list[str],
    probe_token: str,
    source_basename: str,
) -> str:
    """Render the constants module body as a deterministic str."""
    header = (
        '"""Auto-generated rename constants for `argo doctor --static`.\n'
        "\n"
        "DO NOT EDIT BY HAND. Generated by ``tools/generate_rename_defaults.py``\n"
        "from ``argo-rename.yaml`` (the single source of truth). The build\n"
        "pipeline (``tools/build.py``) regenerates this file before copying the\n"
        "overlay into ``dist/argo/``.\n"
        "\n"
        "Used as a fallback by ``argo_cli.doctor_leakage`` when no\n"
        "``argo-rename.yaml`` is available at runtime (the published\n"
        "``ghcr.io/nadicodeai/argo`` image case, where build-time config is not\n"
        "shipped per spec FR-7).\n"
        '"""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        f"GENERATED_FROM: str = {source_basename!r}\n"
        "\n"
    )

    mappings_lines = ["MAPPINGS: tuple[tuple[str, str], ...] = ("]
    for f, t in mappings:
        mappings_lines.append(f"    ({f!r}, {t!r}),")
    mappings_lines.append(")")
    mappings_block = "\n".join(mappings_lines) + "\n\n"

    exc_lines = ["EXCEPTION_PATHS: tuple[str, ...] = ("]
    for p in exception_paths:
        exc_lines.append(f"    {p!r},")
    exc_lines.append(")")
    exc_block = "\n".join(exc_lines) + "\n\n"

    skip_lines = ["SKIP_CONTEXTS: tuple[str, ...] = ("]
    for s in skip_contexts:
        skip_lines.append(f"    {s!r},")
    skip_lines.append(")")
    skip_block = "\n".join(skip_lines) + "\n\n"

    probe_block = f"PROBE_TOKEN: str = {probe_token!r}\n"

    return header + mappings_block + exc_block + skip_block + probe_block


def generate(yaml_path: Path, out_path: Path) -> str:
    """Generate the constants module from *yaml_path* into *out_path*.

    Returns the rendered module text (also written to disk).
    """
    data = _load_yaml(yaml_path)
    mappings = _extract_mappings(data)
    exception_paths = _extract_exception_paths(data)
    skip_contexts = _extract_skip_contexts(data)
    probe_token = _derive_probe_token(mappings)
    rendered = _render_module(
        mappings=mappings,
        exception_paths=exception_paths,
        skip_contexts=skip_contexts,
        probe_token=probe_token,
        source_basename=yaml_path.name,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_rename_defaults.py",
        description=(
            "Generate overlay/hermes_cli/_rename_defaults.py from argo-rename.yaml "
            "so the leakage scanner has a runtime-available fallback config."
        ),
    )
    parser.add_argument(
        "--rename-yaml",
        type=Path,
        default=_DEFAULT_YAML,
        help="path to argo-rename.yaml (default: repo root)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=_DEFAULT_OUT,
        help="path to write the generated module to",
    )
    args = parser.parse_args(argv)

    if not args.rename_yaml.is_file():
        print(f"error: rename yaml not found: {args.rename_yaml}", file=sys.stderr)
        return 2

    try:
        generate(args.rename_yaml, args.out)
    except GenerateError as exc:
        print(f"generate_rename_defaults: {exc}", file=sys.stderr)
        return 1

    print(f"generate_rename_defaults: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
