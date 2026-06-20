"""Resolve NADIA_HOME for standalone skill scripts.

Skill scripts may run outside the Nadia process (e.g. system Python,
nix env, CI) where ``nadia_constants`` is not importable.  This module
provides the same ``get_nadia_home()`` and ``display_nadia_home()``
contracts as ``nadia_constants`` without requiring it on ``sys.path``.

When ``nadia_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``nadia_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``NADIA_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from nadia_constants import display_nadia_home as display_nadia_home
    from nadia_constants import get_nadia_home as get_nadia_home
except (ModuleNotFoundError, ImportError):

    def get_nadia_home() -> Path:
        """Return the Nadia home directory (default: ~/.nadia).

        Mirrors ``nadia_constants.get_nadia_home()``."""
        val = os.environ.get("NADIA_HOME", "").strip()
        return Path(val) if val else Path.home() / ".nadia"

    def display_nadia_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``nadia_constants.display_nadia_home()``."""
        home = get_nadia_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
