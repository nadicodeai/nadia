"""overlay/conftest.py — argo rootdir conftest.

After `make build` this lands at `dist/argo/conftest.py`, pytest's
rootdir conftest. Pytest discovers conftests top-down from rootdir
before walking `testpaths`, so this is loaded ahead of
`dist/argo/tests/conftest.py` and any per-directory conftests.

What it does: reads `argo-xfail.yml` (sitting next to this file) and
applies `pytest.mark.xfail(reason=..., strict=False)` to every collected
item whose `nodeid` appears in the manifest. The manifest itself is the
canonical doc for entry shape, category taxonomy, lifecycle, and the
`strict=False` rationale — see `argo-xfail.yml`.

It also reads `argo-allow-socket.yml` and applies
`pytest.mark.enable_socket` to every collected item whose `nodeid`
appears there — re-granting outbound network to the handful of tests
that genuinely need it while the dist gate runs hermetic
(`--disable-socket`) by default. See that manifest for the rationale.

Why a rootdir conftest, not a plugin:

- Zero install cost — pytest auto-discovers conftests; no `entry_points`
  shuffle in `pyproject.toml`.
- Zero patches against `upstream/tests/conftest.py` (which becomes
  `dist/argo/tests/conftest.py`). Pure additive; sync cost = 0.
- The hook fires at collection time, before any test body runs, so the
  XFAIL marker is in place for the runner's own reporting.

Imports kept minimal (`pytest`, `yaml`, stdlib) so this loads even when
the venv that runs it does not yet have `[all,dev]` installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

_MANIFEST_NAME = "argo-xfail.yml"
_ALLOW_SOCKET_MANIFEST = "argo-allow-socket.yml"


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


def _load_allow_socket_nodeids(manifest_path: Path) -> set[str]:
    """Return the set of nodeids re-granted outbound network.

    Tolerant of a missing file / non-dict root / non-list entries / malformed
    entries, exactly like :func:`_load_xfail_entries`: the conftest must load
    even before the manifest ships and must never break collection.
    """
    if not manifest_path.is_file():
        return set()
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return set()
    if not isinstance(raw, dict):
        return set()
    entries = raw.get("allow_socket") or []
    if not isinstance(entries, list):
        return set()
    nodeids: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("nodeid"), str) and entry["nodeid"]:
            nodeids.add(entry["nodeid"])
    return nodeids


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001 — required by pytest hook signature
    items: list[pytest.Item],
) -> None:
    """Annotate collected items from the argo manifests.

    Applies `xfail` (from `argo-xfail.yml`) and `enable_socket` (from
    `argo-allow-socket.yml`) to every collected item whose nodeid matches.
    Pytest calls this once per session, with `items` mutated in place. We
    never remove or reorder items — only annotate matches.
    """
    here = Path(__file__).parent
    entries = _load_xfail_entries(here / _MANIFEST_NAME)
    allow_socket = _load_allow_socket_nodeids(here / _ALLOW_SOCKET_MANIFEST)
    if not entries and not allow_socket:
        return

    by_nodeid = {entry["nodeid"]: entry["reason"] for entry in entries}
    for item in items:
        reason = by_nodeid.get(item.nodeid)
        if reason is not None:
            item.add_marker(pytest.mark.xfail(reason=reason, strict=False))
        if item.nodeid in allow_socket:
            item.add_marker(pytest.mark.enable_socket)
