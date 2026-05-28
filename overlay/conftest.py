"""overlay/conftest.py — argo rootdir conftest.

After `make build` this lands at `dist/argo/conftest.py`, pytest's
rootdir conftest. Pytest discovers conftests top-down from rootdir
before walking `testpaths`, so this is loaded ahead of
`dist/argo/tests/conftest.py` and any per-directory conftests.

What it does
------------
Reads `argo-xfail.yml` (sitting next to this file) and applies
`pytest.mark.xfail(reason=..., strict=False)` to every collected item
whose `nodeid` appears in the manifest. See `argo-xfail.yml` for the
schema, lifecycle, and the UCS-AC-4 contract that pins this design.

Why a rootdir conftest, not a plugin
------------------------------------
- Zero install cost — pytest auto-discovers conftests; no `entry_points`
  shuffle in `pyproject.toml`.
- Zero patches against `upstream/tests/conftest.py` (which becomes
  `dist/argo/tests/conftest.py`). Pure additive; sync cost = 0.
- The hook fires at collection time, before any test body runs, so the
  XFAIL marker is in place for the runner's own reporting.

Why `strict=False`
------------------
An XPASS (test we marked XFAIL but it actually passed) should be a
hint that upstream fixed the test or the rebrand engine caught up — not
a red CI. We surface XPASS in the report and triage it later.

Imports kept minimal (`pytest`, `yaml`, stdlib) so this loads even when
the venv that runs it does not yet have `[all,dev]` installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_MANIFEST_NAME = "argo-xfail.yml"


def _load_xfail_entries(manifest_path: Path) -> list[dict[str, Any]]:
    """Return the list of XFAIL entries from the manifest.

    Tolerant of:
    - missing file (returns []) — lets the conftest ship before the
      manifest does, and lets local dev runs without the manifest work.
    - empty `xfails:` list (returns []) — the M2 ship state.
    - malformed entries (skipped silently in production; the M2 unit
      test covers the well-formed path).
    """
    if not manifest_path.is_file():
        return []

    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return []

    if not isinstance(raw, dict):
        return []

    xfails = raw.get("xfails") or []
    if not isinstance(xfails, list):
        return []

    valid: list[dict[str, Any]] = []
    for entry in xfails:
        if not isinstance(entry, dict):
            continue
        nodeid = entry.get("nodeid")
        reason = entry.get("reason")
        if not isinstance(nodeid, str) or not isinstance(reason, str):
            continue
        if not nodeid or not reason:
            continue
        valid.append({"nodeid": nodeid, "reason": reason})
    return valid


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001 — required by pytest hook signature
    items: list[pytest.Item],
) -> None:
    """Apply `xfail` marker to every collected item whose nodeid matches.

    Pytest calls this once per session, with `items` mutated in place.
    We never remove or reorder items — only annotate matches.
    """
    manifest_path = Path(__file__).parent / _MANIFEST_NAME
    entries = _load_xfail_entries(manifest_path)
    if not entries:
        return

    by_nodeid = {entry["nodeid"]: entry["reason"] for entry in entries}
    for item in items:
        reason = by_nodeid.get(item.nodeid)
        if reason is None:
            continue
        item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
