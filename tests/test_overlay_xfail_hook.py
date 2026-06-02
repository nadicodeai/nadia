"""tests/test_overlay_xfail_hook.py — unit tests for overlay/conftest.py.

Covers UCS-AC-4 infrastructure: the XFAIL manifest loader and the
`pytest_collection_modifyitems` hook in `overlay/conftest.py`.

What this test asserts
----------------------
1. **Empty manifest = no-op.** No items get an `xfail` marker.
2. **Missing manifest = no-op.** Same behavior (we ship the conftest
   into customer trees that may not carry the manifest).
3. **Entry application.** A deliberately-failing test paired with a
   manifest entry pointing at its nodeid is reported as `xfailed`, not
   `failed`.
4. **Per-item isolation.** Only matching nodeids get marked; siblings
   in the same file stay clean.
5. **Malformed entries are skipped silently.** Production safety —
   never blow up collection because of a bad manifest line.
6. **enable_socket injection.** Nodeids in `argo-allow-socket.yml`
   receive the `enable_socket` marker; siblings don't; a missing or
   malformed manifest is a safe no-op.

Strategy
--------
We use pytest's `pytester` fixture (the official testing-of-pytest-
plugins facility) to materialize a temp directory that contains:

- A copy of `overlay/conftest.py` at the temp rootdir (so pytester's
  inner pytest invocation auto-discovers it as its rootdir conftest).
- A fixture `argo-xfail.yml` next to that conftest with the manifest
  content under test.
- A `tests/` subdir with one or more synthetic test files.

The inner pytest then exits, and we read its summary counts (XFAIL /
FAIL / PASS) via `result.assert_outcomes()`.

Why pytester
------------
- It is the official pytest-plugin test harness; no third-party deps.
- It runs a real pytest in a subprocess (or in-process) so the hook
  exercises the same collection path it will at runtime.
- It is already in the maintainer toolchain (`pytest >= 9`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_OVERLAY_CONFTEST = _REPO_ROOT / "overlay" / "conftest.py"


def _stage_conftest(pytester: pytest.Pytester) -> None:
    """Copy overlay/conftest.py into pytester's rootdir."""
    assert _OVERLAY_CONFTEST.is_file(), (
        f"overlay/conftest.py missing at {_OVERLAY_CONFTEST}; "
        "M2 infrastructure not in place."
    )
    shutil.copy2(_OVERLAY_CONFTEST, pytester.path / "conftest.py")


def _write_manifest(pytester: pytest.Pytester, content: str) -> None:
    """Write argo-xfail.yml at pytester's rootdir (next to conftest)."""
    (pytester.path / "argo-xfail.yml").write_text(content, encoding="utf-8")


def _write_failing_test(pytester: pytest.Pytester) -> str:
    """Write a tests/ subtree with one failing and one passing test.

    Returns the nodeid of the deliberately-failing test (relative to
    the pytester rootdir, so it matches what pytest emits for `item.nodeid`).
    """
    (pytester.path / "tests").mkdir(exist_ok=True)
    # No __init__.py — pytester's inner pytest treats it as a rootdir
    # collection target, and adding __init__.py would force the
    # outer test runner's `tests` package to shadow the inner.
    (pytester.path / "tests" / "test_sample.py").write_text(
        "def test_will_fail():\n"
        "    assert False, 'deliberately failing under M2 test harness'\n"
        "\n"
        "def test_will_pass():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    return "tests/test_sample.py::test_will_fail"


def test_empty_manifest_is_noop(pytester: pytest.Pytester) -> None:
    """xfails: [] must not mark any items."""
    _stage_conftest(pytester)
    _write_manifest(pytester, "xfails: []\n")
    _write_failing_test(pytester)

    result = pytester.runpytest("-q", "--no-header")

    # 1 deliberately-failing test, 1 passing test, 0 xfails because
    # the manifest is empty.
    result.assert_outcomes(passed=1, failed=1, xfailed=0)


def test_missing_manifest_is_noop(pytester: pytest.Pytester) -> None:
    """A missing argo-xfail.yml must not crash collection or mark items."""
    _stage_conftest(pytester)
    # Deliberately do NOT write a manifest.
    _write_failing_test(pytester)

    result = pytester.runpytest("-q", "--no-header")

    result.assert_outcomes(passed=1, failed=1, xfailed=0)


def test_matching_nodeid_is_xfailed_not_failed(
    pytester: pytest.Pytester,
) -> None:
    """A manifest entry naming a failing test downgrades FAIL → XFAIL."""
    _stage_conftest(pytester)
    failing_nodeid = _write_failing_test(pytester)
    _write_manifest(
        pytester,
        "xfails:\n"
        f"  - nodeid: {failing_nodeid}\n"
        "    reason: deliberately failing under M2 test harness\n"
        "    category: X\n",
    )

    result = pytester.runpytest("-q", "--no-header")

    # The deliberately-failing test is now reported as xfailed, not failed.
    # The sibling passing test remains green.
    result.assert_outcomes(passed=1, failed=0, xfailed=1)


def test_non_matching_entries_leave_other_items_alone(
    pytester: pytest.Pytester,
) -> None:
    """Entries pointing at nonexistent nodeids are silently inert.

    A manifest is allowed to lag behind the test surface (e.g. a test
    was deleted upstream but the XFAIL entry hasn't been pruned yet).
    The non-matching entry MUST NOT raise, MUST NOT mark an unrelated
    item, and MUST NOT affect collection of the items that DO exist.
    """
    _stage_conftest(pytester)
    failing_nodeid = _write_failing_test(pytester)
    _write_manifest(
        pytester,
        "xfails:\n"
        # Matching entry — applies to the deliberately-failing test.
        f"  - nodeid: {failing_nodeid}\n"
        "    reason: deliberately failing under M2 test harness\n"
        "    category: X\n"
        # Non-matching entry — refers to a nodeid that does not exist
        # in the collected items. Must be a silent no-op.
        "  - nodeid: tests/test_sample.py::test_nonexistent\n"
        "    reason: stale entry kept on purpose for this assertion\n"
        "    category: X\n",
    )

    result = pytester.runpytest("-q", "--no-header")

    # The matching entry downgrades the failing test; the non-matching
    # entry has no observable effect — test_will_pass stays a normal pass.
    result.assert_outcomes(passed=1, failed=0, xfailed=1)


def test_malformed_entries_are_skipped_silently(
    pytester: pytest.Pytester,
) -> None:
    """A manifest with bad entries must not crash; good entries still apply."""
    _stage_conftest(pytester)
    failing_nodeid = _write_failing_test(pytester)
    _write_manifest(
        pytester,
        # First entry: missing reason — must be silently dropped.
        # Second entry: not a mapping — must be silently dropped.
        # Third entry: well-formed — must apply.
        "xfails:\n"
        "  - nodeid: tests/test_sample.py::test_will_fail\n"
        "  - just-a-string\n"
        f"  - nodeid: {failing_nodeid}\n"
        "    reason: well-formed entry survives malformed neighbours\n"
        "    category: X\n",
    )

    result = pytester.runpytest("-q", "--no-header")

    result.assert_outcomes(passed=1, failed=0, xfailed=1)


def test_invalid_yaml_is_treated_as_empty_manifest(
    pytester: pytest.Pytester,
) -> None:
    """A YAML parse error must not crash collection; behaves like empty."""
    _stage_conftest(pytester)
    _write_manifest(pytester, "xfails: [\n  this is not valid yaml")
    _write_failing_test(pytester)

    result = pytester.runpytest("-q", "--no-header")

    # No xfails applied because the manifest didn't parse.
    result.assert_outcomes(passed=1, failed=1, xfailed=0)


# --- argo-allow-socket.yml / enable_socket marker injection -----------------
#
# Marker presence is asserted via `request.node.get_closest_marker(...)`, so
# these need NO pytest-socket install in the runner env — we test that the hook
# applies the marker, not pytest-socket's blocking behaviour (that is covered by
# the dist gate itself running hermetic).


def _write_allow_socket_manifest(pytester: pytest.Pytester, content: str) -> None:
    """Write argo-allow-socket.yml at pytester's rootdir (next to conftest)."""
    (pytester.path / "argo-allow-socket.yml").write_text(content, encoding="utf-8")


def _write_marker_introspect_tests(pytester: pytest.Pytester) -> str:
    """Write a tests/ file whose tests assert on their own enable_socket marker.

    Returns the nodeid of the test that EXPECTS the marker, so a manifest can
    name it.
    """
    (pytester.path / "tests").mkdir(exist_ok=True)
    (pytester.path / "tests" / "test_socket_sample.py").write_text(
        "def test_listed(request):\n"
        "    assert request.node.get_closest_marker('enable_socket') is not None\n"
        "\n"
        "def test_unlisted(request):\n"
        "    assert request.node.get_closest_marker('enable_socket') is None\n",
        encoding="utf-8",
    )
    return "tests/test_socket_sample.py::test_listed"


def test_allow_socket_marks_only_listed_nodeid(pytester: pytest.Pytester) -> None:
    """A nodeid in argo-allow-socket.yml gets enable_socket; siblings don't."""
    _stage_conftest(pytester)
    listed = _write_marker_introspect_tests(pytester)
    _write_allow_socket_manifest(
        pytester,
        "allow_socket:\n"
        f"  - nodeid: {listed}\n"
        "    reason: needs the wire for this assertion\n",
    )

    result = pytester.runpytest("-q", "--no-header")

    # test_listed sees the marker, test_unlisted does not — both assertions pass.
    result.assert_outcomes(passed=2, failed=0)


def test_missing_allow_socket_manifest_applies_no_marker(
    pytester: pytest.Pytester,
) -> None:
    """No argo-allow-socket.yml → no enable_socket marker, no crash."""
    _stage_conftest(pytester)
    _write_marker_introspect_tests(pytester)
    # Deliberately write NO allow-socket manifest.

    result = pytester.runpytest("-q", "--no-header")

    # test_listed expects a marker and fails (none applied); test_unlisted passes.
    # The point: collection didn't crash and no marker was injected.
    result.assert_outcomes(passed=1, failed=1)


def test_malformed_allow_socket_manifest_is_skipped_silently(
    pytester: pytest.Pytester,
) -> None:
    """Bad allow-socket entries must not crash; well-formed ones still apply."""
    _stage_conftest(pytester)
    listed = _write_marker_introspect_tests(pytester)
    _write_allow_socket_manifest(
        pytester,
        "allow_socket:\n"
        "  - just-a-string\n"  # not a mapping — dropped
        "  - nodeid: 123\n"  # nodeid not a str — dropped
        f"  - nodeid: {listed}\n"  # well-formed — applies
        "    reason: survives malformed neighbours\n",
    )

    result = pytester.runpytest("-q", "--no-header")

    result.assert_outcomes(passed=2, failed=0)
