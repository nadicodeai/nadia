"""Validation tests for the full argo-rename.yaml configuration (T3.1).

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
_CONFIG_PATH = _REPO_ROOT / "argo-rename.yaml"

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
    """argo-rename.yaml must load cleanly."""
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

    The rename config maps hermes-* identifiers to argo-* identifiers.
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
    """Key mappings must produce the correct 'to' (argo-side) values."""
    mapping_dict = dict(config.mappings)
    expected = {
        "HermesAgent": "ArgoAgent",
        "hermes-agent": "argo-agent",
        "hermes_agent": "argo_agent",
        "hermes_cli": "argo_cli",
        "HERMES_HOME": "ARGO_HOME",
        "HERMES_": "ARGO_",
        "Hermes": "Argo",
        "HERMES": "ARGO",
        "hermes": "argo",
    }
    for from_, to_ in expected.items():
        assert mapping_dict.get(from_) == to_, (
            f"Mapping {from_!r} -> expected {to_!r}, got {mapping_dict.get(from_)!r}"
        )


def test_exceptions_contains_self_test_protection(config: RenameConfig) -> None:
    """exceptions must protect this test file (it contains hermes-* literals).

    The repo-root rename test file itself contains the hermes-* string
    literals as fixture data. When the engine runs on ``dist/argo/`` it
    never sees this repo-root file, but the exception entry is kept so
    runtime ``argo doctor --static`` (which can scan arbitrary trees
    including a checkout-style layout) does not flag it.
    """
    paths = {rule.path for rule in config.exceptions}
    assert "tests/test_full_rename_config.py" in paths, (
        f"tests/test_full_rename_config.py not in exceptions paths: {paths}"
    )


def test_exceptions_contains_rename_defaults(config: RenameConfig) -> None:
    """exceptions must contain the generated ``_rename_defaults.py`` glob.

    ``tools/generate_rename_defaults.py`` bakes the rename config into a
    Python module so ``argo doctor --static`` works in the published image
    where ``argo-rename.yaml`` is absent (issue #4). That module legitimately
    contains every hermes-* FROM key as a string literal — the engine MUST
    NOT rewrite its contents.
    """
    paths = {rule.path for rule in config.exceptions}
    assert "*/_rename_defaults.py" in paths, (
        f"*/_rename_defaults.py not in exceptions paths: {paths}"
    )


def test_exceptions_contains_argo_metadata(config: RenameConfig) -> None:
    """exceptions must contain the ``.argo/**`` build/sync manifest glob.

    The manifests record pre-rename file paths (hermes_cli/foo.py →
    argo_cli/foo.py) and ship with the artifact for introspection
    (``argo --version --verbose``). They are intentionally allowed to
    contain hermes-* string literals.
    """
    paths = {rule.path for rule in config.exceptions}
    assert ".argo/**" in paths, (
        f".argo/** not in exceptions paths: {paths}"
    )


def test_skip_contexts_non_empty(config: RenameConfig) -> None:
    """skip_contexts must contain at least the URL and hash patterns."""
    assert len(config.skip_contexts) >= 2, (
        f"Expected >= 2 skip_contexts, got {len(config.skip_contexts)}"
    )
    # At least one pattern should handle URLs
    url_patterns = [p for p in config.skip_contexts if "http" in p]
    assert url_patterns, "No URL-matching skip_context found"


def test_longer_argo_agent_before_shorter_argo(config: RenameConfig) -> None:
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


def test_argo_home_before_argo_bare(config: RenameConfig) -> None:
    """'HERMES_HOME' must appear before bare 'HERMES' entry.

    HERMES_HOME (10 chars) must shadow HERMES (6 chars) in longest-first order.
    """
    froms = [f for f, _ in config.mappings]
    assert "HERMES_HOME" in froms, "HERMES_HOME not in mappings"
    assert "HERMES" in froms, "HERMES not in mappings"
    assert froms.index("HERMES_HOME") < froms.index("HERMES"), (
        "HERMES_HOME must come before HERMES in sorted order"
    )
