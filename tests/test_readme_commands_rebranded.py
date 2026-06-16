"""tests/test_readme_commands_rebranded.py — README quickstart uses `nadia`, not `hermes`.

The installed binary is `nadia` (pyproject [project.scripts]) and config lives in
~/.nadia, but README.md / README.zh-CN.md are engine-excepted so their command
examples and config paths would otherwise ship as `hermes ...` / ~/.hermes —
command-not-found for anyone following the docs. Patch 0014 rebrands the
commands + paths while preserving attribution. This guards the END STATE:

  * the quickstart commands are rebranded (`nadia model`, `nadia setup`, ...),
  * no `hermes <subcommand>` invocations or ~/.hermes paths remain, AND
  * attribution is preserved (the upstream repo + docs URLs survive — the
    rebrand must NOT have over-reached into hermes-agent links).

Requires `make build` to have produced dist/nadia/.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_DIST = Path(__file__).resolve().parent.parent / "dist" / "nadia"
_READMES = ["README.md", "README.zh-CN.md"]

# Subcommands shown in the quickstart; their `hermes <cmd>` form must be gone.
_SUBCOMMANDS = ["model", "tools", "config set", "gateway", "setup", "update", "doctor", "claw migrate"]


def _read(rel: str) -> str:
    return (_DIST / rel).read_text(encoding="utf-8")


@pytest.mark.skipif(not _DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
@pytest.mark.parametrize("rel", _READMES)
def test_quickstart_commands_are_rebranded(rel: str) -> None:
    text = _read(rel)
    assert "nadia model" in text, f"{rel}: quickstart should show `nadia model`"
    # No `hermes <subcommand>` invocations remain.
    for sub in _SUBCOMMANDS:
        assert f"hermes {sub}" not in text, f"{rel}: stale `hermes {sub}` command example"
    # Standalone `hermes` command lines (start of a fenced line) are gone.
    assert not re.search(r"(?m)^hermes(\s|$)", text), f"{rel}: stale bare `hermes` command line"
    # Config dir rebranded.
    assert "~/.hermes" not in text, f"{rel}: stale ~/.hermes config path"


@pytest.mark.skipif(not _DIST.is_dir(), reason="dist/nadia not built (run `make build`)")
@pytest.mark.parametrize("rel", _READMES)
def test_attribution_preserved(rel: str) -> None:
    text = _read(rel)
    # The rebrand must NOT have eaten the upstream attribution URLs.
    assert "NousResearch/hermes-agent" in text, f"{rel}: upstream repo attribution URL was clobbered"
    assert "hermes-agent.nousresearch.com" in text, f"{rel}: upstream docs URL was clobbered"
