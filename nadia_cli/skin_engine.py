"""Nadia CLI skin/theme engine.

Nadia exposes one generated skin on every surface. Legacy built-in skin
presets and user YAML skins are intentionally ignored so appearance choice is
limited to light/dark/system mode outside the CLI skin engine.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from nadia_cli._nadia_skin import NADIA_SKIN_DATA as _NADIA_SKIN_DATA


# =============================================================================
# Skin data structure
# =============================================================================

@dataclass
class SkinConfig:
    """Complete skin configuration."""
    name: str
    description: str = ""
    colors: Dict[str, str] = field(default_factory=dict)
    spinner: Dict[str, Any] = field(default_factory=dict)
    branding: Dict[str, str] = field(default_factory=dict)
    tool_prefix: str = "┊"
    tool_emojis: Dict[str, str] = field(default_factory=dict)  # per-tool emoji overrides
    banner_logo: str = ""    # Rich-markup ASCII art logo (replaces NADIA_AGENT_LOGO)
    banner_hero: str = ""    # Rich-markup hero art (replaces NADIA_CADUCEUS)

    def get_color(self, key: str, fallback: str = "") -> str:
        """Get a color value with fallback."""
        return self.colors.get(key, fallback)

    def get_spinner_wings(self) -> List[Tuple[str, str]]:
        """Get spinner wing pairs, or empty list if none."""
        raw = self.spinner.get("wings", [])
        result = []
        for pair in raw:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                result.append((str(pair[0]), str(pair[1])))
        return result

    def get_branding(self, key: str, fallback: str = "") -> str:
        """Get a branding value with fallback."""
        return self.branding.get(key, fallback)


# =============================================================================
# Built-in skin definitions
# =============================================================================

_SINGLE_SKIN_NAME = "nadia"
_BUILTIN_SKINS: Dict[str, Dict[str, Any]] = {_SINGLE_SKIN_NAME: _NADIA_SKIN_DATA}


# =============================================================================
# Skin loading and management
# =============================================================================

_active_skin: Optional[SkinConfig] = None
_active_skin_name: str = _SINGLE_SKIN_NAME
# User YAML skin discovery is intentionally absent; Nadia ships one generated skin.


def _mapping_or_empty(value: Any, *, section: str, skin_name: str) -> Dict[str, Any]:
    """Return a mapping value or an empty dict when the section type is invalid."""
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    logger.warning(
        "Skin '%s' has invalid '%s' section type (%s); ignoring section",
        skin_name,
        section,
        type(value).__name__,
    )
    return {}


def _build_skin_config(data: Dict[str, Any]) -> SkinConfig:
    """Build a SkinConfig from generated Nadia skin data."""
    skin_name = str(data.get("name", "unknown"))
    color_overrides = _mapping_or_empty(data.get("colors"), section="colors", skin_name=skin_name)
    spinner_overrides = _mapping_or_empty(data.get("spinner"), section="spinner", skin_name=skin_name)
    branding_overrides = _mapping_or_empty(data.get("branding"), section="branding", skin_name=skin_name)
    emoji_overrides = _mapping_or_empty(data.get("tool_emojis"), section="tool_emojis", skin_name=skin_name)

    return SkinConfig(
        name=skin_name,
        description=data.get("description", ""),
        colors=dict(color_overrides),
        spinner=dict(spinner_overrides),
        branding=dict(branding_overrides),
        tool_prefix=data.get("tool_prefix", "|"),
        tool_emojis=emoji_overrides,
        banner_logo=data.get("banner_logo", ""),
        banner_hero=data.get("banner_hero", ""),
    )


def list_skins() -> List[Dict[str, str]]:
    """List the single generated Nadia skin.

    Returns list of {"name": ..., "description": ..., "source": "builtin"}.
    """
    data = _BUILTIN_SKINS[_SINGLE_SKIN_NAME]
    return [{
        "name": _SINGLE_SKIN_NAME,
        "description": data.get("description", ""),
        "source": "builtin",
    }]


def load_skin(name: str) -> SkinConfig:
    """Load the generated Nadia skin, regardless of requested legacy name."""
    return _build_skin_config(_BUILTIN_SKINS[_SINGLE_SKIN_NAME])


def get_active_skin() -> SkinConfig:
    """Get the currently active skin config (cached)."""
    global _active_skin
    if _active_skin is None:
        _active_skin = load_skin(_active_skin_name)
    return _active_skin


def set_active_skin(name: str) -> SkinConfig:
    """Resolve any requested skin to the generated Nadia skin."""
    global _active_skin, _active_skin_name
    _active_skin_name = _SINGLE_SKIN_NAME
    _active_skin = load_skin(_SINGLE_SKIN_NAME)
    return _active_skin


def get_active_skin_name() -> str:
    """Get the name of the currently active skin."""
    return _active_skin_name


def init_skin_from_config(config: dict) -> None:
    """Initialize the single generated skin at startup.

    Legacy ``display.skin`` values are ignored.
    """
    set_active_skin(_SINGLE_SKIN_NAME)


# =============================================================================
# Convenience helpers for CLI modules
# =============================================================================


def get_active_prompt_symbol(fallback: str = "❯") -> str:
    """Return the interactive prompt symbol with a single trailing space.

    Skins store ``prompt_symbol`` as a bare token (no spaces). The trailing
    space is appended here so callers can drop it straight into a rendered
    prompt without hand-rolling whitespace.
    """
    try:
        raw = get_active_skin().get_branding("prompt_symbol", fallback)
    except Exception:
        raw = fallback

    cleaned = (raw or fallback).strip()

    return f"{cleaned or fallback.strip()} "



def get_active_help_header(fallback: str = "(^_^)? Available Commands") -> str:
    """Get the /help header from the active skin."""
    try:
        return get_active_skin().get_branding("help_header", fallback)
    except Exception:
        return fallback



def get_active_goodbye(fallback: str = "Goodbye! ⚕") -> str:
    """Get the goodbye line from the active skin."""
    try:
        return get_active_skin().get_branding("goodbye", fallback)
    except Exception:
        return fallback



def get_prompt_toolkit_style_overrides() -> Dict[str, str]:
    """Return prompt_toolkit style overrides derived from the active skin.

    These are layered on top of the CLI's base TUI style so /skin can refresh
    the live prompt_toolkit UI immediately without rebuilding the app.
    """
    try:
        skin = get_active_skin()
    except Exception:
        return {}

    # Input/prompt: leave unset by default so the typed text inherits
    # the terminal's foreground color (readable in both light and dark
    # color schemes).  Skins can opt into a colored prompt by setting
    # `prompt` explicitly in their YAML.
    prompt = skin.get_color("prompt", "")
    input_rule = skin.get_color("input_rule", "#CD7F32")
    title = skin.get_color("banner_title", "#FFD700")
    text = skin.get_color("banner_text", "#FFF8DC")
    dim = skin.get_color("banner_dim", "#555555")
    label = skin.get_color("ui_label", title)
    warn = skin.get_color("ui_warn", "#FF8C00")
    error = skin.get_color("ui_error", "#FF6B6B")
    status_bg = skin.get_color("status_bar_bg", "#1a1a2e")
    status_text = skin.get_color("status_bar_text", text)
    status_strong = skin.get_color("status_bar_strong", title)
    status_dim = skin.get_color("status_bar_dim", dim)
    status_good = skin.get_color("status_bar_good", skin.get_color("ui_ok", "#8FBC8F"))
    status_warn = skin.get_color("status_bar_warn", warn)
    status_bad = skin.get_color("status_bar_bad", skin.get_color("banner_accent", warn))
    status_critical = skin.get_color("status_bar_critical", error)
    voice_bg = skin.get_color("voice_status_bg", status_bg)
    menu_bg = skin.get_color("completion_menu_bg", "#1a1a2e")
    menu_current_bg = skin.get_color("completion_menu_current_bg", "#333355")
    menu_meta_bg = skin.get_color("completion_menu_meta_bg", menu_bg)
    menu_meta_current_bg = skin.get_color("completion_menu_meta_current_bg", menu_current_bg)

    return {
        # Typed input always uses terminal default fg/bg so it's
        # readable in both light and dark Terminal.app modes.  The
        # skin's `prompt` color (if any) only styles the prompt symbol,
        # NOT the user's typed text.
        "input-area": "",
        "placeholder": f"{dim} italic",
        "prompt": prompt,
        "prompt-working": f"{dim} italic",
        "hint": f"{dim} italic",
        "status-bar": f"bg:{status_bg} {status_text}",
        "status-bar-strong": f"bg:{status_bg} {status_strong} bold",
        "status-bar-dim": f"bg:{status_bg} {status_dim}",
        "status-bar-good": f"bg:{status_bg} {status_good} bold",
        "status-bar-warn": f"bg:{status_bg} {status_warn} bold",
        "status-bar-bad": f"bg:{status_bg} {status_bad} bold",
        "status-bar-critical": f"bg:{status_bg} {status_critical} bold",
        "input-rule": input_rule,
        "image-badge": f"{label} bold",
        "completion-menu": f"bg:{menu_bg} {text}",
        "completion-menu.completion": f"bg:{menu_bg} {text}",
        "completion-menu.completion.current": f"bg:{menu_current_bg} {title}",
        "completion-menu.meta.completion": f"bg:{menu_meta_bg} {dim}",
        "completion-menu.meta.completion.current": f"bg:{menu_meta_current_bg} {label}",
        "clarify-border": input_rule,
        "clarify-title": f"{title} bold",
        "clarify-question": f"{text} bold",
        "clarify-choice": dim,
        "clarify-selected": f"{title} bold",
        "clarify-active-other": f"{title} italic",
        "clarify-countdown": input_rule,
        "sudo-prompt": f"{error} bold",
        "sudo-border": input_rule,
        "sudo-title": f"{error} bold",
        "sudo-text": text,
        "approval-border": input_rule,
        "approval-title": f"{warn} bold",
        "approval-desc": f"{text} bold",
        "approval-cmd": f"{dim} italic",
        "approval-choice": dim,
        "approval-selected": f"{title} bold",
        "voice-status": f"bg:{voice_bg} {label}",
        "voice-status-recording": f"bg:{voice_bg} {error} bold",
    }
