"""tests/test_dockerfile_release_stamp.py — the image release-date stamp.

`make build` regenerates dist/argo/ from pristine upstream/, so the image's
argo_cli/__init__.py carries UPSTREAM's __release_date__ unless the build
re-stamps the Argo release date. build.py._stamp_release_date does that from
$ARGO_RELEASE_DATE (the one value a hermetic docker build can't read off the git
tag itself). These tests pin the behaviour and the Dockerfile/workflow wiring so
the Docker surface can never again ship a release reporting the upstream date
(the v2026.6.5 image shipped 2026.5.29 because this stamp did not exist).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import build  # noqa: E402

_UPSTREAM_INIT = (
    "import sys\n\n"
    '__version__ = "0.15.1"\n'
    '__release_date__ = "2026.5.29"\n'
)


@pytest.fixture
def fake_dist(tmp_path, monkeypatch):
    """Point build.DIST_DIR at a temp tree holding a post-rebrand version file."""
    init_path = tmp_path / "argo_cli" / "__init__.py"
    init_path.parent.mkdir(parents=True)
    init_path.write_text(_UPSTREAM_INIT, encoding="utf-8")
    monkeypatch.setattr(build, "DIST_DIR", tmp_path)
    return init_path


# ----------------------------------------------------- _stamp_release_date

def test_stamp_overwrites_upstream_date_when_env_set(fake_dist, monkeypatch):
    monkeypatch.setenv("ARGO_RELEASE_DATE", "2026.6.5")
    assert build._stamp_release_date() == "2026.6.5"
    assert '__release_date__ = "2026.6.5"' in fake_dist.read_text(encoding="utf-8")


def test_stamp_leaves_version_untouched(fake_dist, monkeypatch):
    # __version__ tracks upstream verbatim; the stamp must not touch it.
    monkeypatch.setenv("ARGO_RELEASE_DATE", "2026.6.5")
    build._stamp_release_date()
    assert '__version__ = "0.15.1"' in fake_dist.read_text(encoding="utf-8")


def test_stamp_is_noop_when_env_unset(fake_dist, monkeypatch):
    monkeypatch.delenv("ARGO_RELEASE_DATE", raising=False)
    assert build._stamp_release_date() is None
    # Dev build keeps upstream's date — honest for an unreleased tree.
    assert '__release_date__ = "2026.5.29"' in fake_dist.read_text(encoding="utf-8")


def test_stamp_is_noop_when_env_blank(fake_dist, monkeypatch):
    monkeypatch.setenv("ARGO_RELEASE_DATE", "   ")
    assert build._stamp_release_date() is None
    assert '__release_date__ = "2026.5.29"' in fake_dist.read_text(encoding="utf-8")


def test_stamp_rejects_non_calver_date(fake_dist, monkeypatch):
    monkeypatch.setenv("ARGO_RELEASE_DATE", "not-a-date")
    with pytest.raises(build.BuildError, match="release-date"):
        build._stamp_release_date()


def test_stamp_accepts_four_segment_calver(fake_dist, monkeypatch):
    # YYYY.M.D.N (a same-day re-release) is a valid calver shape.
    monkeypatch.setenv("ARGO_RELEASE_DATE", "2026.6.5.2")
    assert build._stamp_release_date() == "2026.6.5.2"
    assert '__release_date__ = "2026.6.5.2"' in fake_dist.read_text(encoding="utf-8")


# ----------------------------------------------------- Dockerfile / workflow wiring

def test_dockerfile_passes_release_date_into_make_build():
    text = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "ARG ARGO_RELEASE_DATE" in text, (
        "Dockerfile must declare ARG ARGO_RELEASE_DATE"
    )
    assert "ENV ARGO_RELEASE_DATE" in text, (
        "Dockerfile must export ARGO_RELEASE_DATE so `make build` (build.py) sees it"
    )


def test_publish_workflow_threads_release_date_into_both_variants():
    text = (_REPO_ROOT / ".github" / "workflows" / "docker-publish.yml").read_text(
        encoding="utf-8"
    )
    assert text.count("--build-arg ARGO_RELEASE_DATE=") >= 2, (
        "both the slim and full buildx invocations must pass ARGO_RELEASE_DATE"
    )
    assert "Verify image reports the release date" in text, (
        "docker-publish.yml must gate the published image's __release_date__"
    )
