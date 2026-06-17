"""Validation tests for the full nadia-rename.yaml configuration (T3.1).

Asserts structural correctness, required identifier coverage, and ordering
constraints for the production rename config.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _REPO_ROOT / "nadia-rename.yaml"

# overlay/ hosts the pre-rename engine sources (hermes_sync). Repo-root tests
# import them directly via sys.path injection — same pattern as
# tools/rebrand.py lines 34-40.
_OVERLAY = _REPO_ROOT / "overlay"
if str(_OVERLAY) not in sys.path:
    sys.path.insert(0, str(_OVERLAY))

from hermes_sync.config import RenameConfig  # noqa: E402


@pytest.fixture(scope="module")
def config() -> RenameConfig:
    return RenameConfig.load(_CONFIG_PATH)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_config_loads_without_error(config: RenameConfig) -> None:
    """nadia-rename.yaml must load cleanly."""
    assert config is not None


def test_mappings_count_ge_15(config: RenameConfig) -> None:
    """At least 15 mapping entries must be present."""
    assert len(config.mappings) >= 15, (
        f"Expected >= 15 mappings, got {len(config.mappings)}"
    )


def test_mappings_sorted_longest_first(config: RenameConfig) -> None:
    """Mappings must be sorted by descending length of the 'from' key."""
    lengths = [len(from_) for from_, _ in config.mappings]
    assert lengths == sorted(lengths, reverse=True), (
        "Mappings are not sorted longest-from-first: "
        + str([(f, len(f)) for f, _ in config.mappings])
    )


def test_required_identifiers_present(config: RenameConfig) -> None:
    """All required 'from' identifiers must be in the mappings.

    The rename config maps hermes-* identifiers to nadia-* identifiers.
    We verify the hermes-side (from) keys are all present.
    """
    from_keys = {from_ for from_, _ in config.mappings}
    required = {
        "HermesAgent",
        "hermes-agent",
        "hermes_agent",
        "hermes_cli",
        "hermes_bootstrap",
        "hermes_constants",
        "hermes_state",
        "hermes_time",
        "hermes_logging",
        "hermes_tools_mcp_server",
        "HERMES_HOME",
        "HERMES_",
        "~/.hermes",
        ".hermes/",
        "Hermes",
        "HERMES",
        "hermes",
    }
    missing = required - from_keys
    assert not missing, f"Missing required 'from' keys: {sorted(missing)}"


def test_required_to_values_correct(config: RenameConfig) -> None:
    """Key mappings must produce the correct 'to' (nadia-side) values."""
    mapping_dict = dict(config.mappings)
    expected = {
        "HermesAgent": "NadiaAgent",
        "hermes-agent": "nadia-agent",
        "hermes_agent": "nadia_agent",
        "hermes_cli": "nadia_cli",
        "HERMES_HOME": "NADIA_HOME",
        "HERMES_": "NADIA_",
        "Hermes": "Nadia",
        "HERMES": "NADIA",
        "hermes": "nadia",
    }
    for from_, to_ in expected.items():
        assert mapping_dict.get(from_) == to_, (
            f"Mapping {from_!r} -> expected {to_!r}, got {mapping_dict.get(from_)!r}"
        )


def test_docs_site_mapping_present(config: RenameConfig) -> None:
    """The self-referential docs path must map to the live Nadia docs site.

    The fork publishes the renamed docs at docs.nadicode.ai/nadia/ (built from
    dist/nadia/website/). The mapping rewrites the upstream Docusaurus host +
    '/docs/' baseUrl together so e.g.
    ``hermes-agent.nousresearch.com/docs/user-guide/cli`` becomes
    ``docs.nadicode.ai/nadia/user-guide/cli``.
    """
    mapping_dict = dict(config.mappings)
    assert (
        mapping_dict.get("hermes-agent.nousresearch.com/docs")
        == "docs.nadicode.ai/nadia"
    ), (
        "docs-site mapping missing/wrong: "
        f"got {mapping_dict.get('hermes-agent.nousresearch.com/docs')!r}"
    )


def test_product_url_mappings_present(config: RenameConfig) -> None:
    """Customer install, docs, and desktop URLs must point at Nadia surfaces."""
    mapping_dict = dict(config.mappings)
    expected = {
        "hermes-agent.nousresearch.com/docs": "docs.nadicode.ai/nadia",
        "hermes-agent.nousresearch.com/install.sh": "raw.githubusercontent.com/nadicodeai/nadia/release/scripts/install.sh",
        "hermes-agent.nousresearch.com/install.ps1": "raw.githubusercontent.com/nadicodeai/nadia/release/scripts/install.ps1",
        "hermes-agent.nousresearch.com/desktop": "github.com/nadicodeai/nadia/releases/latest",
    }
    for from_, to_ in expected.items():
        assert mapping_dict.get(from_) == to_, (
            f"Mapping {from_!r} -> expected {to_!r}, got {mapping_dict.get(from_)!r}"
        )


def test_bare_host_and_pypi_not_rewritten(config: RenameConfig) -> None:
    """The bare upstream host and PyPI package must NOT be rewritten.

    Product paths under ``hermes-agent.nousresearch.com`` are mapped above. The
    bare host itself (the OpenRouter HTTP-Referer attribution header) and
    ``pypi.org/p/hermes-agent`` (the real upstream PyPI package) stay on the
    upstream host as attribution and must never appear as mapping keys.
    """
    from_keys = {from_ for from_, _ in config.mappings}
    assert "hermes-agent.nousresearch.com" not in from_keys, (
        "bare upstream host must not be a mapping key (attribution surface)"
    )
    assert "pypi.org/p/hermes-agent" not in from_keys, (
        "upstream PyPI package must not be a mapping key (attribution surface)"
    )


def test_product_paths_released_from_url_preservation(config: RenameConfig) -> None:
    """The URL skip_context must release product paths so mappings can fire.

    The negative-lookahead URL guard preserves upstream URLs from rewriting. The
    product-path lookahead makes docs, install scripts, and desktop download
    paths rewritable while keeping the bare host and /llms.txt preserved.
    """
    import re

    url_patterns = [p for p in config.skip_contexts if p.startswith("https?://")]
    assert url_patterns, "no URL-guard skip_context found"
    guard = url_patterns[0]
    rx = re.compile(guard)
    for url in (
        "https://hermes-agent.nousresearch.com/docs/user-guide/cli",
        "https://hermes-agent.nousresearch.com/install.sh",
        "https://hermes-agent.nousresearch.com/install.ps1",
        "https://hermes-agent.nousresearch.com/desktop",
    ):
        assert not rx.match(url), f"{url} is still preserved; mapping cannot fire"

    # The bare host (HTTP-Referer) and unrelated upstream paths stay preserved.
    assert rx.match("https://hermes-agent.nousresearch.com"), (
        "bare upstream host must stay preserved (attribution)"
    )
    assert rx.match("https://hermes-agent.nousresearch.com/llms.txt"), (
        "/llms.txt must stay preserved (upstream static endpoint)"
    )


def test_exceptions_contains_self_test_protection(config: RenameConfig) -> None:
    """exceptions must protect this test file (it contains hermes-* literals).

    The repo-root rename test file itself contains the hermes-* string
    literals as fixture data. When the engine runs on ``dist/nadia/`` it
    never sees this repo-root file, but the exception entry is kept so
    runtime ``nadia doctor --static`` (which can scan arbitrary trees
    including a checkout-style layout) does not flag it.
    """
    paths = {rule.path for rule in config.exceptions}
    assert "tests/test_full_rename_config.py" in paths, (
        f"tests/test_full_rename_config.py not in exceptions paths: {paths}"
    )


def test_exceptions_contains_rename_defaults(config: RenameConfig) -> None:
    """exceptions must contain the generated ``_rename_defaults.py`` glob.

    ``tools/generate_rename_defaults.py`` bakes the rename config into a
    Python module so ``nadia doctor --static`` works in the published image
    where ``nadia-rename.yaml`` is absent (issue #4). That module legitimately
    contains every hermes-* FROM key as a string literal — the engine MUST
    NOT rewrite its contents.
    """
    paths = {rule.path for rule in config.exceptions}
    assert "*/_rename_defaults.py" in paths, (
        f"*/_rename_defaults.py not in exceptions paths: {paths}"
    )


def test_exceptions_contains_nadia_metadata(config: RenameConfig) -> None:
    """exceptions must contain the ``.nadia/**`` build/sync manifest glob.

    The manifests record pre-rename file paths (hermes_cli/foo.py →
    nadia_cli/foo.py) and ship with the artifact for introspection
    (``nadia --version --verbose``). They are intentionally allowed to
    contain hermes-* string literals.
    """
    paths = {rule.path for rule in config.exceptions}
    assert ".nadia/**" in paths, (
        f".nadia/** not in exceptions paths: {paths}"
    )


def test_skip_contexts_non_empty(config: RenameConfig) -> None:
    """skip_contexts must contain at least the URL and hash patterns."""
    assert len(config.skip_contexts) >= 2, (
        f"Expected >= 2 skip_contexts, got {len(config.skip_contexts)}"
    )
    # At least one pattern should handle URLs
    url_patterns = [p for p in config.skip_contexts if "http" in p]
    assert url_patterns, "No URL-matching skip_context found"


def test_longer_nadia_agent_before_shorter_nadia(config: RenameConfig) -> None:
    """'hermes_agent' must appear before 'hermes' in the sorted mapping list.

    Longer from-keys must shadow shorter ones; hermes_agent (12 chars)
    must come before hermes (6 chars) to avoid partial replacement.
    """
    froms = [f for f, _ in config.mappings]
    assert "hermes_agent" in froms, "hermes_agent not in mappings"
    assert "hermes" in froms, "hermes not in mappings"
    assert froms.index("hermes_agent") < froms.index("hermes"), (
        "hermes_agent must come before hermes in the sorted order"
    )


def test_nadia_home_before_nadia_bare(config: RenameConfig) -> None:
    """'HERMES_HOME' must appear before bare 'HERMES' entry.

    HERMES_HOME (10 chars) must shadow HERMES (6 chars) in longest-first order.
    """
    froms = [f for f, _ in config.mappings]
    assert "HERMES_HOME" in froms, "HERMES_HOME not in mappings"
    assert "HERMES" in froms, "HERMES not in mappings"
    assert froms.index("HERMES_HOME") < froms.index("HERMES"), (
        "HERMES_HOME must come before HERMES in sorted order"
    )
