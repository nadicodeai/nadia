"""tests/test_install_url_release_branch.py — guard the install one-liner branch.

The customer-runnable rebranded tree and the install scripts live ONLY on the
`release` branch (main is the workshop: upstream/ + patches/ + overlay/, not a
runnable install). Upstream hardcodes `/main/scripts/install.*` in the README,
the install scripts (incl. install.cmd's live bootstrap), the `nadia update` /
uninstall reinstall hints, and ~30 docs pages. Left unfixed, every one of those
one-liners 404s for customers.

The fix is split: README*/CONTRIBUTING are engine-excepted (so patch 0002 hard-
codes /release/), and every other file is corrected by the nadia-rename.yaml
mapping `NousResearch/hermes-agent/main/scripts/install ->
nadicodeai/argo/release/scripts/install`. This test asserts the END STATE on the
built tree: NO `/main/scripts/install` survives anywhere a customer can see it,
and the key entry points carry the /release/ form.

Requires `make build` to have produced dist/nadia/ (CI builds before tests).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DIST = _REPO_ROOT / "dist" / "nadia"

# The 404-ing form (post-rename: org is already nadicodeai/argo) that must not
# appear anywhere in the shipped tree.
_BAD = "nadicodeai/argo/main/scripts/install"

# Build cruft / VCS dirs that are NOT part of the customer-facing surface.
# .pc/ is quilt's per-patch backup state (pre-patch snapshots); it is not a live
# file a customer ever executes or reads. (Its presence in dist is a separate
# hygiene item.)
_SKIP_DIRS = {".pc", ".git", "__pycache__", "node_modules", ".nadia"}


def _iter_text_files(root: Path):
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        try:
            yield p, p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue


@pytest.mark.skipif(not _DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
def test_no_main_branch_install_url_anywhere_in_dist() -> None:
    offenders = [
        str(p.relative_to(_DIST))
        for p, text in _iter_text_files(_DIST)
        if _BAD in text
    ]
    assert not offenders, (
        f"{len(offenders)} shipped file(s) still reference the 404-ing "
        f"{_BAD!r} install URL: {offenders[:20]}"
    )


@pytest.mark.skipif(not _DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
@pytest.mark.parametrize(
    "rel_path, needle",
    [
        ("README.md", "nadicodeai/argo/release/scripts/install.sh"),
        ("README.zh-CN.md", "nadicodeai/argo/release/scripts/install.sh"),
        ("scripts/install.sh", "nadicodeai/argo/release/scripts/install"),
        ("scripts/install.ps1", "nadicodeai/argo/release/scripts/install.ps1"),
        ("scripts/install.cmd", "nadicodeai/argo/release/scripts/install.ps1"),  # live bootstrap
        ("nadia_cli/main.py", "nadicodeai/argo/release/scripts/install.sh"),       # update reinstall hint
        ("nadia_cli/uninstall.py", "nadicodeai/argo/release/scripts/install.sh"),  # uninstall reinstall hint
    ],
)
def test_key_entrypoints_use_release_branch(rel_path: str, needle: str) -> None:
    f = _DIST / rel_path
    assert f.is_file(), f"expected shipped file {rel_path} missing from dist/nadia"
    assert needle in f.read_text(encoding="utf-8"), (
        f"{rel_path} should reference the release-branch install URL ({needle!r})"
    )
