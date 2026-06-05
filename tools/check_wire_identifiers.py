#!/usr/bin/env python3
"""tools/check_wire_identifiers.py — assert Nous wire-protocol identities survive the rebrand.

Positive companion to ``tools/verify_no_leakage.py``. The leakage scanner catches
*under*-rename (a stray ``hermes`` leaked into the shipped tree). This checker
catches the opposite failure mode — *over*-rename — which leakage is structurally
blind to: when the blanket ``hermes -> argo`` rename rewrites a string that the
Nous backend keys on (OAuth client_id, Portal attribution tags, the model-catalog
User-Agent the WAF allow-lists), the value silently becomes ``argo-*`` and there is
no ``hermes`` left for the leak scan to flag. The artifact ships green and the
agent then fails to join the Nous portal in the field with "it says argo-cli".

This gate asserts each of those exact wire values is STILL PRESENT in ``dist/argo/``.
A missing value means ``argo-rename.yaml``'s ``skip_contexts`` no longer protects it
(an upstream refactor drifted an anchor, or the skip entry was removed) — the build
fails loudly here instead of shipping a portal-broken release.

Exit codes
----------
- 0: every required wire identifier is present.
- 1: at least one was clobbered by the rename.
- 2: usage error (target not a built dist tree).

Usage
-----
    python tools/check_wire_identifiers.py dist/argo/
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WireCheck:
    """One required literal that MUST survive the rebrand in a given dist file."""

    rel_path: str          # path under dist/argo/ (post-rename: hermes_cli -> argo_cli)
    literal: str           # exact substring that must be present
    why: str               # what breaks in the field if it is missing


# Each literal is sent to (or recognised by) a Nous endpoint and is protected by a
# matching skip_contexts entry in argo-rename.yaml. Keep the two in lock-step.
WIRE_CHECKS: tuple[WireCheck, ...] = (
    WireCheck(
        "argo_cli/auth.py",
        'DEFAULT_NOUS_CLIENT_ID = "hermes-cli"',
        "OAuth device-code client_id the Nous portal whitelists; argo-cli is rejected (login fails to join).",
    ),
    WireCheck(
        "agent/portal_tags.py",
        "product=hermes-agent",
        "Nous Portal product-attribution tag sent on every request.",
    ),
    WireCheck(
        "agent/portal_tags.py",
        "client=hermes-client-v",
        "Nous Portal client-release tag (client=hermes-client-v<version>).",
    ),
    WireCheck(
        "argo_cli/model_catalog.py",
        "hermes-cli/",
        "User-Agent for the Nous model-catalog probe; some catalogs WAF-403 an unknown UA.",
    ),
    WireCheck(
        "argo_cli/models.py",
        "hermes-cli/",
        "User-Agent for the Nous model-catalog probe (second copy).",
    ),
    WireCheck(
        "providers/base.py",
        "hermes-cli/",
        "ProviderProfile.fetch_models catalog-probe User-Agent.",
    ),
    WireCheck(
        "providers/base.py",
        'return "hermes-cli"',
        "Stable UA fallback when the version import fails.",
    ),
)


def run(dist: Path) -> list[str]:
    """Return a list of human-readable failure messages (empty == all present)."""
    failures: list[str] = []
    for chk in WIRE_CHECKS:
        target = dist / chk.rel_path
        if not target.is_file():
            failures.append(
                f"{chk.rel_path}: file missing from dist (expected to contain {chk.literal!r})"
            )
            continue
        text = target.read_text(encoding="utf-8", errors="strict")
        if chk.literal not in text:
            failures.append(
                f"{chk.rel_path}: required wire identifier {chk.literal!r} NOT FOUND — "
                f"the hermes->argo rename clobbered it. {chk.why} "
                f"Restore the matching skip_contexts anchor in argo-rename.yaml."
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_wire_identifiers.py",
        description="Assert Nous wire-protocol identifiers survived the rebrand in a built dist tree.",
    )
    parser.add_argument("target", type=Path, help="built dist directory (e.g. dist/argo/)")
    args = parser.parse_args(argv)

    if not args.target.is_dir():
        print(f"error: target not a directory: {args.target}", file=sys.stderr)
        return 2

    failures = run(args.target)
    if failures:
        print(
            f"check_wire_identifiers: FAIL — {len(failures)} Nous wire identifier(s) clobbered by rename:",
            file=sys.stderr,
        )
        for msg in failures:
            print(f"  ✗ {msg}", file=sys.stderr)
        return 1

    print(
        f"check_wire_identifiers: OK — all {len(WIRE_CHECKS)} Nous wire identifiers survived in {args.target}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
