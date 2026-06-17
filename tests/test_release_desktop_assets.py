"""Release workflow checks for downloadable Nadia desktop installers."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _workflow() -> dict:
    return yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))


def _step_text(job: dict) -> str:
    return "\n".join(str(step) for step in job["steps"])


def test_release_workflow_builds_native_desktop_assets() -> None:
    workflow = _workflow()
    jobs = workflow["jobs"]

    assert "prepare-release-tree" in jobs
    assert jobs["desktop-macos"]["needs"] == "prepare-release-tree"
    assert jobs["desktop-windows"]["needs"] == "prepare-release-tree"
    assert set(jobs["publish"]["needs"]) == {
        "prepare-release-tree",
        "desktop-macos",
        "desktop-windows",
    }

    macos = _step_text(jobs["desktop-macos"])
    assert "macos-latest" == jobs["desktop-macos"]["runs-on"]
    assert "npm run dist:mac:dmg" in macos
    assert "Nadia-Agent-*.dmg" in macos
    assert "desktop-macos-assets" in macos

    windows = _step_text(jobs["desktop-windows"])
    assert "windows-latest" == jobs["desktop-windows"]["runs-on"]
    assert "npm run dist:win:nsis" in windows
    assert "Nadia-Agent-*.exe" in windows
    assert "desktop-windows-assets" in windows


def test_release_publish_uploads_desktop_assets_and_checksums() -> None:
    workflow = _workflow()
    publish = _step_text(workflow["jobs"]["publish"])

    assert "desktop-macos-assets" in publish
    assert "desktop-windows-assets" in publish
    assert "sha256sums.txt" in publish
    assert "gh release upload" in publish
    assert "release-assets" in publish
