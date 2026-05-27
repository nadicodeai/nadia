"""hermes_cli.argo_update — no-op stub for the in-container `argo update` UX.

After the build-time rename pass, this module lands at
`dist/argo/argo_cli/argo_update.py`. The argo Docker image is immutable;
the customer-facing update mechanism is `docker pull`. This stub prints
the docker-pull instruction so a customer typing `argo update` (the legacy
muscle memory) gets a helpful pointer instead of an error.

Rationale: spec OQ-6 (resolved). Preserves UX continuity vs the legacy
in-place updater without misleading the customer about an unavailable code
path.

Wired into the CLI dispatch by the equivalent of legacy
`hermes_cli/main.py`'s `update` subparser. The argparse handler imports
`cmd_argo_update` from this module.
"""

from __future__ import annotations

import argparse
import sys

DOCKER_PULL_INSTRUCTION = (
    "argo is distributed as a Docker image. Update with:\n"
    "\n"
    "  docker pull ghcr.io/nadicodeai/argo:latest\n"
    "\n"
    "See https://github.com/nadicodeai/argo for release notes.\n"
)


def cmd_argo_update(args: argparse.Namespace) -> None:
    """Argparse handler: print the docker-pull instruction and exit 0.

    Accepts and ignores any args carried over from the legacy CLI shape
    (--check, --no-backup, etc.) so calls don't error on unknown flags.
    """
    del args
    sys.stdout.write(DOCKER_PULL_INSTRUCTION)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="argo update")
    # Accept and ignore legacy flags so `argo update --check` doesn't error.
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--yes", "-y", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--gateway", action="store_true")
    args = parser.parse_args(argv)
    cmd_argo_update(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
