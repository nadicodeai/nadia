"""tests/test_wire_identifier_preservation.py — regression guard for the Nous wire-identifier over-rename bug.

Sibling to test_model_id_preservation.py. NousResearch's backend keys on three
families of EXACT strings the fork sends it: the OAuth device-code ``client_id``
(``hermes-cli``), the Portal attribution tags (``product=hermes-agent`` /
``client=hermes-client-v<version>``), and the model-catalog probe ``User-Agent``
(``hermes-cli/<version>``). The blanket hermes->nadia rebrand rewrote them to
``nadia-*``, which the Nous portal REJECTS — device-code login then fails in the
field with the reported symptom "cannot join the Nous portal, it says nadia-cli".

These are Nous protocol identity, NOT the fork's brand, so the rebrand MUST
preserve them — while STILL rebranding the brand token that shares the literal
``hermes-cli`` value: the internal default *toolset* key (toolsets.py registry,
config.py default ``["hermes-cli"]``, delegate_tool.py comparisons). This test
drives the REAL rename engine (the same code build.py runs) so it catches a config
regression at the engine level without a full `make build`.

Why the shipped dist tests cannot catch this: upstream's own portal-tag test
(tests/agent/test_portal_tags.py) asserts the tag value, but the rename rewrites
the test's EXPECTED literal in lock-step with the source — both became nadia-* and
the assertion stayed green while shipping a portal-broken client. That lock-step
green is the exact failure mode this bug exhibited (and why prior "tests pass"
claims were hollow). The positive build gate tools/check_wire_identifiers.py is
the dist-level companion to this engine-level test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _REPO_ROOT / "nadia-rename.yaml"

# overlay/ hosts the pre-rename engine sources (hermes_sync); import directly via
# sys.path injection — same pattern as tools/rebrand.py and test_model_id_preservation.py.
_OVERLAY = _REPO_ROOT / "overlay"
if str(_OVERLAY) not in sys.path:
    sys.path.insert(0, str(_OVERLAY))

from hermes_sync.config import RenameConfig  # noqa: E402
from hermes_sync.passes.content import _apply_mappings_with_skip_contexts  # noqa: E402


@pytest.fixture(scope="module")
def rename():
    cfg = RenameConfig.load(_CONFIG_PATH)

    def _apply(text: str) -> str:
        return _apply_mappings_with_skip_contexts(text, cfg.mappings, cfg.skip_contexts)

    return _apply


# --- WIRE identifiers: the exact source forms must survive byte-for-byte -------
# (input_line, expected_output) — the brand-named vars around the wire literal
# (e.g. _HERMES_USER_AGENT, hermes_client_tag) rebrand; the WIRE literal does not.

_WIRE_PRESERVED = [
    # OAuth client_id default (auth.py:72) — the reported blocker.
    ('DEFAULT_NOUS_CLIENT_ID = "hermes-cli"',
     'DEFAULT_NOUS_CLIENT_ID = "hermes-cli"'),
    # OAuth client_id runtime literal fallback (auth.py:5043).
    ('        state.get("client_id", "hermes-cli"),',
     '        state.get("client_id", "hermes-cli"),'),
    # --client-id OAuth help text (main.py:11835, 12374).
    ('        help="OAuth client id to use for Nous login (default: hermes-cli)",',
     '        help="OAuth client id to use for Nous login (default: hermes-cli)",'),
    # Catalog-probe User-Agent (model_catalog.py:80 / models.py:23) — brand var renames, UA literal does not.
    ('_HERMES_USER_AGENT = f"hermes-cli/{_HERMES_VERSION}"',
     '_NADIA_USER_AGENT = f"hermes-cli/{_NADIA_VERSION}"'),
    # UA fallback when version import fails (providers/base.py:35).
    ('        return "hermes-cli"',
     '        return "hermes-cli"'),
    # Portal product tag (portal_tags.py) — brand fn name renames, tag literal does not.
    ('    return ["product=hermes-agent", hermes_client_tag()]',
     '    return ["product=hermes-agent", nadia_client_tag()]'),
    # Portal client-release tag (portal_tags.py:55).
    ('    return f"client=hermes-client-v{_hermes_version()}"',
     '    return f"client=hermes-client-v{_nadia_version()}"'),
]


@pytest.mark.parametrize("wire_in, expected", _WIRE_PRESERVED)
def test_nous_wire_identifiers_survive_the_rebrand(rename, wire_in: str, expected: str) -> None:
    assert rename(wire_in) == expected, (
        f"rebrand corrupted a Nous wire identifier:\n  in:  {wire_in!r}\n  got: {rename(wire_in)!r}\n"
        f"  want: {expected!r}\nThe Nous backend keys on the literal value; nadia-* is rejected "
        "(this is the 'cannot join the Nous portal, it says nadia-cli' bug)."
    )


# --- The OVERLOADED toolset key MUST still rebrand (no over-preserve) ----------
# `hermes-cli` is ALSO the internal default toolset key. It must become nadia-cli
# so the product is internally consistent; a too-broad skip_context that preserved
# it would leave a "hermes-cli" toolset in `nadia tools` — the hermes/nadia mixture.

@pytest.mark.parametrize(
    "toolset_in, expected_out",
    [
        ('    "hermes-cli": {', '    "nadia-cli": {'),                        # toolsets.py registry key
        ('default_toolset="hermes-cli"', 'default_toolset="nadia-cli"'),       # platforms.py
        ('config.get("toolsets", ["hermes-cli"])', 'config.get("toolsets", ["nadia-cli"])'),  # config/dump default
        ('if toolset == "hermes-cli":', 'if toolset == "nadia-cli":'),          # delegate_tool comparison
        ('"cli": "hermes-cli",', '"cli": "nadia-cli",'),                        # nous_subscription mapping
    ],
)
def test_toolset_key_still_rebrands(rename, toolset_in: str, expected_out: str) -> None:
    assert rename(toolset_in) == expected_out, (
        f"toolset key {toolset_in!r} should rebrand to {expected_out!r}, got {rename(toolset_in)!r} — "
        "a wire skip_context is too broad and is over-preserving the internal toolset key."
    )
