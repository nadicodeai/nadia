"""``nadia setup`` subcommand parser.

Extracted verbatim from ``nadia_cli/main.py:main()`` (god-file Phase 2).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_setup_parser(subparsers, *, cmd_setup: Callable) -> None:
    """Attach the ``setup`` subcommand to ``subparsers``."""
    # =========================================================================
    # setup command
    # =========================================================================
    setup_parser = subparsers.add_parser(
        "setup",
        help="Interactive setup wizard",
        description="Configure Nadia Agent with an interactive wizard. "
        "Run a specific section: nadia setup model|tts|terminal|gateway|tools|agent",
    )
    setup_parser.add_argument(
        "section",
        nargs="?",
        choices=["model", "tts", "terminal", "gateway", "tools", "agent"],
        default=None,
        help="Run a specific setup section instead of the full wizard",
    )
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Non-interactive mode (use defaults/env vars)",
    )
    setup_parser.add_argument(
        "--reset", action="store_true", help="Reset configuration to defaults"
    )
    setup_parser.add_argument(
        "--reconfigure",
        action="store_true",
        help="(Default on existing installs.) Re-run the full wizard, "
        "showing current values as defaults. Kept for backwards "
        "compatibility — a bare 'nadia setup' now does this.",
    )
    setup_parser.add_argument(
        "--quick",
        action="store_true",
        help="On existing installs: only prompt for items that are missing "
        "or unset, instead of running the full reconfigure wizard.",
    )
    setup_parser.add_argument(
        "--portal",
        action="store_true",
        help="One-shot Nadia Agents Portal setup: log in via OAuth, pick a Nadia "
        "model, set Nadia as the inference provider, and opt into the Tool "
        "Gateway. Skips the rest of the wizard.",
    )
    setup_parser.set_defaults(func=cmd_setup)
