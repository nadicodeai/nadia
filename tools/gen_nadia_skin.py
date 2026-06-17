#!/usr/bin/env python3
"""Generate Nadia terminal skin artifacts from NadicodeAI DTCG tokens."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DS_TOKENS = (
    REPO_ROOT
    / "tools"
    / "skin-gen"
    / "node_modules"
    / "@nadicodeai"
    / "design-system"
    / "dist"
    / "tokens"
    / "nadicode.dtcg.json"
)
DEFAULT_PYTHON_OUTPUT = REPO_ROOT / "overlay" / "hermes_cli" / "_nadia_skin.py"
DEFAULT_TYPESCRIPT_OUTPUT = REPO_ROOT / "overlay" / "ui-tui" / "src" / "nadiaTheme.generated.ts"


class TokenGenerationError(RuntimeError):
    """Raised when the design-system token file cannot satisfy the skin map."""


PYTHON_COLOR_TOKENS: dict[str, str] = {
    "banner_border": "cyan-deep",
    "banner_title": "cyan",
    "banner_accent": "link",
    "banner_dim": "muted",
    "banner_text": "selection-fg",
    "ui_accent": "link",
    "ui_label": "cyan-deep",
    "ui_ok": "success",
    "ui_error": "flag-red",
    "ui_warn": "warning",
    "prompt": "selection-fg",
    "input_rule": "link-deep",
    "response_border": "cyan",
    "status_bar_bg": "primary",
    "status_bar_text": "muted",
    "status_bar_dim": "muted",
    "status_bar_good": "success",
    "status_bar_warn": "warning",
    "status_bar_bad": "error-deep",
    "status_bar_critical": "flag-red",
    "status_bar_strong": "cyan",
    "session_label": "cyan-deep",
    "session_border": "link-deep",
    "selection_bg": "link-deep",
    "voice_status_bg": "primary",
    "completion_menu_bg": "primary",
    "completion_menu_current_bg": "link-deep",
    "completion_menu_meta_bg": "primary",
    "completion_menu_meta_current_bg": "link",
}

TUI_COLOR_TOKENS: dict[str, str] = {
    "primary": "cyan",
    "accent": "link",
    "border": "cyan-deep",
    "text": "selection-fg",
    "muted": "muted",
    "completionBg": "primary",
    "completionCurrentBg": "link-deep",
    "completionMetaBg": "primary",
    "completionMetaCurrentBg": "link",
    "label": "cyan-deep",
    "ok": "success",
    "error": "error",
    "warn": "warning",
    "prompt": "selection-fg",
    "sessionLabel": "cyan-deep",
    "sessionBorder": "link-deep",
    "statusBg": "primary",
    "statusFg": "muted",
    "statusGood": "success",
    "statusWarn": "warning",
    "statusBad": "error-deep",
    "statusCritical": "flag-red",
    "selectionBg": "link-deep",
    "diffAdded": "success",
    "diffRemoved": "error",
    "diffAddedWord": "state-running",
    "diffRemovedWord": "state-blocked",
    "shellDollar": "cyan",
}

NADIA_BANNER_LOGO = ""
NADIA_BANNER_HERO_TEMPLATE = """[{link_deep}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣿⡈⢳⣄⠀⠀⠀⣹⣏⠀⠀⠀⣠⡞⢁⣿⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{link_deep}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣈⡻⣦⣿⠀⠀⠀⣿⣿⠀⠀⠀⣿⣴⢟⣁⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{link_deep}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⠛⠃⢸⡟⢷⣄⠀⣽⣯⠀⣠⡾⢻⡇⠘⠛⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{link_deep}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠳⣄⣻⠆⣿⣿⠰⣟⣠⠞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{link_deep}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣾⣿⣾⣿⣿⣷⣿⣷⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{link}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣴⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣦⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{link}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢠⣾⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⡄⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{cyan_deep}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣿⣿⣿⣿⣿⡿⠿⣿⣿⣿⣿⣿⣿⠿⢿⣿⣿⣿⣿⣿⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{selection_fg}]⠀⠀⠀⠀⠀⠀⠀⠀⠀⣸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣇⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{selection_fg}]⠀⠀⠀⠀⠀⠀⠀⠀⢠⡟⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⢻⡄⠀⠀⠀⠀⠀⠀⠀⠀[/]
[{cyan}]⠀⠀⠀⠀⠀⠀⠀⢀⣾⠁⠘⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠃⠈⣷⡀⠀⠀⠀⠀⠀⠀⠀[/]
[{cyan}]⠀⠀⠀⠀⠀⣀⣠⡾⠃⠀⠀⠀⠙⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠋⠀⠀⠀⠘⢷⣄⣀⠀⠀⠀⠀⠀[/]
[{link}]⠀⠀⠀⢀⡾⠋⠁⠀⠀⠀⠀⠀⢀⠀⠈⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠁⠀⡀⠀⠀⠀⠀⠀⠈⠙⢷⡀⠀⠀⠀[/]
[{link}]⠀⠀⢀⡾⠁⠀⠀⠀⠀⠀⠀⠀⠹⣆⠀⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⠀⣰⠏⠀⠀⠀⠀⠀⠀⠀⠈⢷⡀⠀⠀[/]
[{link_deep}]⠀⠀⣼⠃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠳⠶⣽⣶⣤⣤⣤⣤⣶⣯⠶⠞⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠘⣧⠀⠀[/]
[{link_deep}]⠀⢰⡏⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢘⣏⣛⣛⣛⣛⣹⡃⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢹⡆⠀[/]
[{flag_red}]⢀⣿⠁⠀⠀⠀⢠⣤⡄⠀⠀⠀⠀⠀⠀⠀⠀⣭⣭⣭⣭⣭⣭⠀⠀⠀⠀⠀⠀⠀⠀⢠⣤⡄⠀⠀⠀⠈⣿⡀[/]
[{flag_red}]⣼⠇⠀⠀⠀⠀⠈⠉⠁⠀⠀⠀⠀⠀⠀⠀⠀⢩⣭⣭⣭⣭⡍⠀⠀⠀⠀⠀⠀⠀⠀⠈⠉⠁⠀⠀⠀⠀⠸⣧[/]"""

SPINNER = {
    "waiting_faces": ["(◎)", "(◈)", "(⬡)", "(⊕)", "(⊗)"],
    "thinking_faces": ["(◎)", "(◈)", "(⬡)", "(⌁)", "(⊗)"],
    "thinking_verbs": [
        "routing",
        "reading",
        "checking",
        "mapping",
        "editing",
        "reviewing",
        "composing",
        "verifying",
    ],
    "wings": [
        ["⟨◎", "◎⟩"],
        ["⟨◈", "◈⟩"],
        ["⟨⬡", "⬡⟩"],
        ["⟨⌁", "⌁⟩"],
    ],
}

BRANDING = {
    "agent_name": "Nadia",
    "welcome": "Welcome to Nadia. Type your message or /help for commands.",
    "goodbye": "Goodbye.",
    "response_label": " Nadia ",
    "prompt_symbol": ">",
    "status_symbol": ">",
    "help_header": "[?] Commands",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise TokenGenerationError(f"token file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise TokenGenerationError(f"invalid token JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise TokenGenerationError(f"token file root must be an object: {path}")
    return data


def _color_container(data: dict[str, Any]) -> dict[str, Any]:
    nested = data.get("nadicode")
    if isinstance(nested, dict) and isinstance(nested.get("color"), dict):
        return nested["color"]
    top_level = data.get("color")
    if isinstance(top_level, dict):
        return top_level
    raise TokenGenerationError("DTCG token file must contain nadicode.color or color")


def _extract_hex(colors: dict[str, Any], token_name: str) -> str:
    raw = colors.get(token_name)
    if not isinstance(raw, dict):
        raise TokenGenerationError(f"missing mapped token: {token_name}")
    value = raw.get("$value")
    if not isinstance(value, dict):
        raise TokenGenerationError(f"mapped token has no $value object: {token_name}")
    hex_value = value.get("hex")
    if not isinstance(hex_value, str):
        raise TokenGenerationError(f"mapped token has no $value.hex string: {token_name}")
    normalized = hex_value.lower()
    if not re.fullmatch(r"#[0-9a-f]{6}", normalized):
        raise TokenGenerationError(f"mapped token is not a six-digit hex color: {token_name}")
    return normalized


def _token_values(ds_tokens: Path) -> dict[str, str]:
    colors = _color_container(_read_json(ds_tokens))
    required_tokens = sorted(set(PYTHON_COLOR_TOKENS.values()) | set(TUI_COLOR_TOKENS.values()))
    return {name: _extract_hex(colors, name) for name in required_tokens}


def _format_template(template: str, values: dict[str, str]) -> str:
    return template.format(
        cyan=values["cyan"],
        cyan_deep=values["cyan-deep"],
        flag_red=values["flag-red"],
        link=values["link"],
        link_deep=values["link-deep"],
        mute=values["muted"],
        selection_fg=values["selection-fg"],
    )


def _package_label(ds_tokens: Path) -> str:
    package_json = ds_tokens.parent.parent.parent / "package.json"
    if not package_json.exists():
        return "unknown"
    try:
        package = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "unknown"
    name = package.get("name", "@nadicodeai/design-system")
    version = package.get("version", "unknown")
    return f"{name}@{version}"


def build_skin_data(ds_tokens: Path) -> dict[str, Any]:
    """Build the Python skin data object from a DTCG token file."""
    values = _token_values(Path(ds_tokens))
    return {
        "name": "nadia",
        "description": "NadicodeAI ink - design-system driven",
        "colors": {key: values[token] for key, token in PYTHON_COLOR_TOKENS.items()},
        "spinner": SPINNER,
        "branding": BRANDING,
        "tool_prefix": "|",
        "banner_logo": NADIA_BANNER_LOGO,
        "banner_hero": _format_template(NADIA_BANNER_HERO_TEMPLATE, values),
    }


def build_tui_data(ds_tokens: Path) -> dict[str, Any]:
    """Build the ui-tui theme data object from a DTCG token file."""
    values = _token_values(Path(ds_tokens))
    colors = {key: values[token] for key, token in TUI_COLOR_TOKENS.items()}
    return {
        "dark_colors": colors,
        "light_colors": colors,
        "brand": {
            "name": "Nadia",
            "icon": "",
            "prompt": ">",
            "welcome": "Type your message or /help for commands.",
            "goodbye": "Goodbye.",
            "tool": "|",
            "helpHeader": "Commands",
        },
        "banner_logo": NADIA_BANNER_LOGO,
        "banner_hero": _format_template(NADIA_BANNER_HERO_TEMPLATE, values),
    }


def _python_artifact(ds_tokens: Path) -> str:
    header = _package_label(ds_tokens)
    body = json.dumps(build_skin_data(ds_tokens), indent=4, ensure_ascii=False)
    return (
        "# Generated by tools/gen_nadia_skin.py. Do not edit by hand.\n"
        f"# Source design system: {header}\n"
        "from __future__ import annotations\n\n"
        f"NADIA_SKIN_DATA = {body}\n"
    )


def _ts_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _ts_object(name: str, value: dict[str, str], type_name: str) -> str:
    lines = [f"export const {name}: {type_name} = {{"]
    for key, item in value.items():
        lines.append(f"  {key}: '{item}',")
    lines.append("}")
    return "\n".join(lines)


def _typescript_artifact(ds_tokens: Path) -> str:
    header = _package_label(ds_tokens)
    data = build_tui_data(ds_tokens)
    brand = data["brand"]
    assert isinstance(brand, dict)
    lines = [
        "// Generated by tools/gen_nadia_skin.py. Do not edit by hand.",
        f"// Source design system: {header}",
        "import type { ThemeBrand, ThemeColors } from './theme.js'",
        "",
        _ts_object("NADIA_DARK_THEME_COLORS", data["dark_colors"], "ThemeColors"),
        "",
        _ts_object("NADIA_LIGHT_THEME_COLORS", data["light_colors"], "ThemeColors"),
        "",
        "export const NADIA_BRAND: ThemeBrand = {",
    ]
    for key, item in brand.items():
        lines.append(f"  {key}: {_ts_string(str(item))},")
    lines.extend(
        [
            "}",
            "",
            f"export const NADIA_BANNER_LOGO = {_ts_string(str(data['banner_logo']))}",
            f"export const NADIA_BANNER_HERO = {_ts_string(str(data['banner_hero']))}",
            "",
        ]
    )
    return "\n".join(lines)


def generate(ds_tokens: Path, python_output: Path, typescript_output: Path) -> None:
    """Generate the committed Python and TypeScript overlay artifacts."""
    ds_tokens = Path(ds_tokens)
    python_output = Path(python_output)
    typescript_output = Path(typescript_output)
    python_output.parent.mkdir(parents=True, exist_ok=True)
    typescript_output.parent.mkdir(parents=True, exist_ok=True)
    python_output.write_text(_python_artifact(ds_tokens), encoding="utf-8")
    typescript_output.write_text(_typescript_artifact(ds_tokens), encoding="utf-8")


def preview(ds_tokens: Path) -> str:
    """Return the CP-A art preview text."""
    skin = build_skin_data(ds_tokens)
    thinking_faces = [str(face) for face in SPINNER["thinking_faces"]]
    thinking_verbs = [str(verb) for verb in SPINNER["thinking_verbs"]]
    return "\n\n".join(
        [
            "CP-A Nadia banner_logo candidate:",
            str(skin["banner_logo"]),
            "CP-A Nadia banner_hero candidate:",
            str(skin["banner_hero"]),
            "Spinner:",
            ", ".join(thinking_faces) + " / " + ", ".join(thinking_verbs),
        ]
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ds-tokens", type=Path, default=DEFAULT_DS_TOKENS)
    parser.add_argument("--python-output", type=Path, default=DEFAULT_PYTHON_OUTPUT)
    parser.add_argument("--typescript-output", type=Path, default=DEFAULT_TYPESCRIPT_OUTPUT)
    parser.add_argument("--preview", action="store_true", help="print the CP-A art preview instead of writing files")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.preview:
            print(preview(args.ds_tokens))
        else:
            generate(args.ds_tokens, args.python_output, args.typescript_output)
    except TokenGenerationError as exc:
        print(f"gen_nadia_skin: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
