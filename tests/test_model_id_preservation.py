"""tests/test_model_id_preservation.py — regression guard for the Nous model-id over-rename bug.

NousResearch's LLMs are literally named "Hermes 2/3/4". Those model identifiers
are external (the Nous portal at inference.nousresearch.com, Hugging Face, and
OpenRouter serve them under those exact names), so the hermes->argo rebrand MUST
NOT rewrite them — doing so makes every Nous model call 404 and silently breaks
the model_switch.py non-agentic guardrail (whose detector regex is a "hermes"
literal). At the same time, BRAND tokens (hermes_cli, hermes-agent, "Hermes
Agent", the upstream repo url NousResearch/hermes-agent) MUST still rebrand.

This test drives the REAL rename engine (the same code build.py runs) over
representative strings, so it catches a future regression directly at the engine
level without needing a full `make build`. The shipped dist tests cannot catch
this regression: their own model-id literals would rename in lock-step with a
broken detector, keeping CI green (the exact failure mode this bug exhibited).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _REPO_ROOT / "argo-rename.yaml"

# overlay/ hosts the pre-rename engine sources (hermes_sync). Repo-root tests
# import them directly via sys.path injection — same pattern as
# tools/rebrand.py and tests/test_full_rename_config.py.
_OVERLAY = _REPO_ROOT / "overlay"
if str(_OVERLAY) not in sys.path:
    sys.path.insert(0, str(_OVERLAY))

from hermes_sync.config import RenameConfig  # noqa: E402
from hermes_sync.passes.content import _apply_mappings_with_skip_contexts  # noqa: E402


@pytest.fixture(scope="module")
def rename(config_path: Path = _CONFIG_PATH):
    cfg = RenameConfig.load(_CONFIG_PATH)

    def _apply(text: str) -> str:
        return _apply_mappings_with_skip_contexts(text, cfg.mappings, cfg.skip_contexts)

    return _apply


# --- The real Nous Hermes model identifiers the rebrand MUST preserve --------

# (input, why) — each MUST survive the rename byte-for-byte.
_MODEL_IDS_PRESERVED = [
    "hermes-3-405b",                              # nous provider fallback_models
    "hermes-3-70b",                               # nous provider fallback_models
    "hermes-4-405b",
    "Hermes-4-405B",
    "Hermes-4-70B",
    "NousResearch/Hermes-3-Llama-3.1-70B",
    "NousResearch/Hermes3",
    "nousresearch/hermes-4-405b",
    "openrouter/hermes3:70b",
    "openrouter/nousresearch/hermes-4-405b",
    "Nous-Hermes-llama-1b-v1",                    # Hugging Face repo (no version digit)
    "nous-hermes-2-mistral",
    "Hermes 3",                                   # the "Hermes 3 & 4" warning prose
    "hermes_4_70b",
    "Hermes-4.3-36B",
]


@pytest.mark.parametrize("model_id", _MODEL_IDS_PRESERVED)
def test_nous_hermes_model_ids_survive_the_rebrand(rename, model_id: str) -> None:
    assert rename(model_id) == model_id, (
        f"rebrand corrupted the Nous model id {model_id!r} -> {rename(model_id)!r}; "
        "this breaks Nous-provider model calls (the portal has no 'argo-*' model)"
    )


def test_nous_provider_fallback_models_line_is_untouched(rename) -> None:
    line = '    fallback_models=(\n        "hermes-3-405b",\n        "hermes-3-70b",\n    ),'
    assert rename(line) == line


def test_non_agentic_detector_regex_literal_keeps_hermes(rename) -> None:
    # model_switch.py: _NOUS_*_NON_AGENTIC_RE pattern. The "hermes" inside the
    # regex MUST stay or the guardrail stops matching real Hermes model names.
    regex_literal = r'r"(?:^|[/:])hermes[-_ ]?[34](?:[-_.:]|$)"'
    out = rename(regex_literal)
    assert "hermes[-_ ]?[34]" in out, f"detector regex literal was rebranded: {out!r}"
    # And the preserved regex must still match a real Hermes model name.
    pat = re.compile(r"(?:^|[/:])hermes[-_ ]?[34](?:[-_.:]|$)", re.IGNORECASE)
    assert pat.search("Hermes-4-405B")
    assert pat.search("NousResearch/Hermes-3-Llama-3.1-70B")


# --- BRAND tokens that MUST still rebrand (no false protection) ---------------

@pytest.mark.parametrize(
    "brand_in, expected_out",
    [
        ("hermes-agent", "argo-agent"),
        ("hermes_cli", "argo_cli"),
        ("Hermes Agent", "Argo Agent"),
        ("hermes_constants", "argo_constants"),
        # the upstream REPO url must point at the fork, NOT be mistaken for a model id
        ("https://github.com/NousResearch/hermes-agent.git",
         "https://github.com/nadicodeai/argo.git"),
        ("hermes-brain:qwen3-14b-ctx16k", "argo-brain:qwen3-14b-ctx16k"),  # not a Hermes 3/4 id
    ],
)
def test_brand_tokens_still_rebrand(rename, brand_in: str, expected_out: str) -> None:
    assert rename(brand_in) == expected_out, (
        f"brand token {brand_in!r} should rebrand to {expected_out!r}, "
        f"got {rename(brand_in)!r} — model-id skip_context is too broad"
    )
