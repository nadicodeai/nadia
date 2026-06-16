"""Tests for the NadicodeAI token to Nadia skin generator."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "tools" / "gen_nadia_skin.py"
MODULE_NAME = "gen_nadia_skin_under_test"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "nadicode.dtcg.sample.json"


def _load_module():
    spec = importlib.util.spec_from_file_location(MODULE_NAME, MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def test_generator_emits_complete_python_and_tui_key_sets(tmp_path: Path) -> None:
    """A valid DTCG file produces both shipped artifacts with every mapped key."""
    generator = _load_module()
    python_output = tmp_path / "_nadia_skin.py"
    typescript_output = tmp_path / "nadiaTheme.generated.ts"

    generator.generate(FIXTURE, python_output, typescript_output)

    python_text = python_output.read_text(encoding="utf-8")
    ts_text = typescript_output.read_text(encoding="utf-8")
    assert '"banner_title": "#50e3c2"' in python_text
    assert '"status_symbol": ">"' in python_text
    assert '"banner_logo": ""' in python_text
    assert "⣿⡈⢳⣄" in python_text
    assert "████" not in python_text
    assert "NADICODEAI DEFAULT SKIN" not in python_text
    assert "seam + nodes" not in python_text
    assert "primary: '#50e3c2'" in ts_text
    assert set(generator.PYTHON_COLOR_TOKENS) == {
        "banner_border",
        "banner_title",
        "banner_accent",
        "banner_dim",
        "banner_text",
        "ui_accent",
        "ui_label",
        "ui_ok",
        "ui_error",
        "ui_warn",
        "prompt",
        "input_rule",
        "response_border",
        "status_bar_bg",
        "status_bar_text",
        "status_bar_dim",
        "status_bar_good",
        "status_bar_warn",
        "status_bar_bad",
        "status_bar_critical",
        "status_bar_strong",
        "session_label",
        "session_border",
        "selection_bg",
        "voice_status_bg",
        "completion_menu_bg",
        "completion_menu_current_bg",
        "completion_menu_meta_bg",
        "completion_menu_meta_current_bg",
    }
    assert set(generator.TUI_COLOR_TOKENS) == {
        "primary",
        "accent",
        "border",
        "text",
        "muted",
        "completionBg",
        "completionCurrentBg",
        "completionMetaBg",
        "completionMetaCurrentBg",
        "label",
        "ok",
        "error",
        "warn",
        "prompt",
        "sessionLabel",
        "sessionBorder",
        "statusBg",
        "statusFg",
        "statusGood",
        "statusWarn",
        "statusBad",
        "statusCritical",
        "selectionBg",
        "diffAdded",
        "diffRemoved",
        "diffAddedWord",
        "diffRemovedWord",
        "shellDollar",
    }


def test_generator_output_is_byte_stable(tmp_path: Path) -> None:
    """Two generations from the same token file are byte-identical."""
    generator = _load_module()
    first_py = tmp_path / "first.py"
    first_ts = tmp_path / "first.ts"
    second_py = tmp_path / "second.py"
    second_ts = tmp_path / "second.ts"

    generator.generate(FIXTURE, first_py, first_ts)
    generator.generate(FIXTURE, second_py, second_ts)

    assert first_py.read_bytes() == second_py.read_bytes()
    assert first_ts.read_bytes() == second_ts.read_bytes()


def test_token_change_reflows_generated_outputs(tmp_path: Path) -> None:
    """Changing a source token changes both outputs, proving the map is live."""
    generator = _load_module()
    changed = tmp_path / "changed.json"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["nadicode"]["color"]["cyan"]["$value"]["hex"] = "#51e3c2"
    changed.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    baseline_py = tmp_path / "baseline.py"
    baseline_ts = tmp_path / "baseline.ts"
    changed_py = tmp_path / "changed.py"
    changed_ts = tmp_path / "changed.ts"

    generator.generate(FIXTURE, baseline_py, baseline_ts)
    generator.generate(changed, changed_py, changed_ts)

    assert baseline_py.read_bytes() != changed_py.read_bytes()
    assert baseline_ts.read_bytes() != changed_ts.read_bytes()
    assert "#51e3c2" in changed_py.read_text(encoding="utf-8")
    assert "#51e3c2" in changed_ts.read_text(encoding="utf-8")


def test_missing_mapped_token_fails_loudly(tmp_path: Path) -> None:
    """A removed DS token is a hard generator error, not a silent fallback."""
    generator = _load_module()
    broken = tmp_path / "broken.json"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del data["nadicode"]["color"]["flag-red"]
    broken.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")

    with pytest.raises(generator.TokenGenerationError, match="flag-red"):
        generator.generate(broken, tmp_path / "out.py", tmp_path / "out.ts")


def test_top_level_color_container_is_supported(tmp_path: Path) -> None:
    """The generator accepts both historical DS container shapes."""
    generator = _load_module()
    flattened = tmp_path / "flattened.json"
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    flattened.write_text(
        json.dumps({"color": data["nadicode"]["color"]}, sort_keys=True),
        encoding="utf-8",
    )

    skin = generator.build_skin_data(flattened)

    assert skin["colors"]["banner_title"] == "#50e3c2"
