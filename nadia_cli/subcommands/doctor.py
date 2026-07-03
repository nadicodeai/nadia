"""``nadia doctor`` subcommand parser.

Extracted verbatim from ``nadia_cli/main.py:main()`` (god-file Phase 2).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_doctor_parser(subparsers, *, cmd_doctor: Callable) -> None:
    """Attach the ``doctor`` subcommand to ``subparsers``."""
    # =========================================================================
    # doctor command
    # =========================================================================
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check configuration and dependencies",
        description="Diagnose issues with Nadia Agent setup",
    )
    doctor_parser.add_argument(
        "--fix", action="store_true", help="Attempt to fix issues automatically"
    )
    doctor_parser.add_argument(
        "--ack",
        metavar="ADVISORY_ID",
        default=None,
        help=(
            "Acknowledge a security advisory by ID and exit. After ack, the "
            "advisory will no longer trigger startup banners. Run `nadia "
            "doctor` first to see active advisories and their IDs."
        ),
    )
    # Let enabled plugins contribute extra flags onto this existing command
    # (e.g. the brand-leakage doctor's `doctor --static` / `--live`) via
    # register_cli_arguments("doctor", ...). Gated on `doctor` actually being
    # the invoked command so the hot no-arg / chat paths pay no plugin-discovery
    # cost. Scan argv for the first non-flag token (the subcommand) rather than
    # testing argv[1] exactly, so leading top-level flags (e.g.
    # `nadia --verbose doctor`) still wire the plugin flags. Claiming plugins
    # handle the invocation through the cli_command_dispatch hook consulted in
    # cmd_doctor.
    import sys as _sys
    _first_cmd = next((a for a in _sys.argv[1:] if not a.startswith("-")), None)
    if _first_cmd == "doctor":
        try:
            from nadia_cli.plugins import apply_plugin_arguments
            apply_plugin_arguments("doctor", doctor_parser)
        except Exception:
            pass
    doctor_parser.set_defaults(func=cmd_doctor)
