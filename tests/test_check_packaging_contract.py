"""tests/test_check_packaging_contract.py — the packaging-drift gate's tests.

Uses synthetic fake-repo fixtures (oracle + shipped Dockerfile + manifest written
under tmp_path) so each drift class is exercised in isolation, plus one
integration assertion against the real built tree. The negative cases are the
point: they prove the gate goes RED when upstream drift is not mirrored.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from check_packaging_contract import (  # noqa: E402
    PackagingContractError,
    check_packaging_contract,
    main,
)

# Minimal oracle resembling the renamed-upstream Dockerfile: a digest-pinned
# node base, an s6 version pin, an apt closure, and install extras.
_ORACLE = """\
FROM node:22-bookworm-slim@sha256:AAAA AS node_source
FROM debian:13.4
ARG S6_OVERLAY_VERSION=3.2.3.0
ARG S6_OVERLAY_NOARCH_SHA256=""" + ("a" * 64) + """
RUN apt-get install -y --no-install-recommends ca-certificates curl ffmpeg && rm -rf /x
RUN uv sync --frozen --extra all --extra anthropic
ENTRYPOINT [ "/init", "/opt/nadia/docker/main-wrapper.sh" ]
"""

# A shipped Dockerfile that honors the contract: same node digest, same s6 pin,
# carries the apt deps, and (for the synthetic case) installs the extras.
_SHIPPED_OK = """\
FROM node:22-bookworm-slim@sha256:AAAA AS node_source
FROM python:3.13-slim-bookworm
ARG S6_OVERLAY_VERSION=3.2.3.0
ARG S6_OVERLAY_NOARCH_SHA256=""" + ("a" * 64) + """
RUN apt-get install -y --no-install-recommends ca-certificates curl ffmpeg && rm -rf /x
RUN pip install -e ".[all,anthropic]"
ENTRYPOINT [ "/init", "/opt/nadia/docker/main-wrapper.sh" ]
"""

_EMPTY_MANIFEST = "from_exceptions: []\napt_exceptions: []\nextras_exceptions: []\n"


def _make_repo(tmp_path: Path, *, oracle: str, shipped: str, manifest: str) -> Path:
    (tmp_path / "dist" / "nadia").mkdir(parents=True)
    (tmp_path / "dist" / "nadia" / "Dockerfile").write_text(oracle, encoding="utf-8")
    (tmp_path / "Dockerfile").write_text(shipped, encoding="utf-8")
    (tmp_path / "packaging-overrides.yaml").write_text(manifest, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------- green path

def test_matching_shipped_dockerfile_passes_clean(tmp_path):
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=_SHIPPED_OK, manifest=_EMPTY_MANIFEST)
    assert check_packaging_contract(repo) == []


# ---------------------------------------------------------- FROM digest drift

def test_node_digest_drift_is_flagged(tmp_path):
    shipped = _SHIPPED_OK.replace("sha256:AAAA AS node_source", "sha256:BBBB AS node_source")
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=shipped, manifest=_EMPTY_MANIFEST)
    violations = check_packaging_contract(repo)
    assert any("node" in v and "drifted" in v for v in violations), violations


def test_node_reverted_to_apt_install_is_flagged(tmp_path):
    # Simulate the actual Node-18 bug: shipped drops the node FROM entirely
    # (apt-installs nodejs instead). The oracle still pins node:22.
    shipped = "\n".join(
        ln for ln in _SHIPPED_OK.splitlines() if "node_source" not in ln
    )
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=shipped, manifest=_EMPTY_MANIFEST)
    violations = check_packaging_contract(repo)
    assert any("no 'node' image" in v for v in violations), violations


def test_from_exception_silences_a_missing_image(tmp_path):
    oracle = _ORACLE.replace(
        "FROM debian:13.4",
        "FROM ghcr.io/astral-sh/uv:1@sha256:CCCC AS uv_source\nFROM debian:13.4",
    )
    manifest = "from_exceptions:\n  - image: uv\n    why: pip not uv\n    issue: '#2'\n"
    repo = _make_repo(tmp_path, oracle=oracle, shipped=_SHIPPED_OK, manifest=manifest)
    assert check_packaging_contract(repo) == []


# ----------------------------------------------------------- pinned ARG drift

def test_s6_version_bump_is_flagged(tmp_path):
    oracle = _ORACLE.replace("S6_OVERLAY_VERSION=3.2.3.0", "S6_OVERLAY_VERSION=3.9.9.9")
    repo = _make_repo(tmp_path, oracle=oracle, shipped=_SHIPPED_OK, manifest=_EMPTY_MANIFEST)
    violations = check_packaging_contract(repo)
    assert any("S6_OVERLAY_VERSION" in v and "drifted" in v for v in violations), violations


# ------------------------------------------------------------- apt superset

def test_upstream_added_apt_dep_is_flagged(tmp_path):
    oracle = _ORACLE.replace("ca-certificates curl ffmpeg", "ca-certificates curl ffmpeg libsndfile1")
    repo = _make_repo(tmp_path, oracle=oracle, shipped=_SHIPPED_OK, manifest=_EMPTY_MANIFEST)
    violations = check_packaging_contract(repo)
    assert any("libsndfile1" in v for v in violations), violations


def test_apt_exception_silences_a_dropped_dep(tmp_path):
    oracle = _ORACLE.replace("ca-certificates curl ffmpeg", "ca-certificates curl ffmpeg docker-cli")
    manifest = "apt_exceptions:\n  - package: docker-cli\n    kind: omit\n    why: unused\n"
    repo = _make_repo(tmp_path, oracle=oracle, shipped=_SHIPPED_OK, manifest=manifest)
    assert check_packaging_contract(repo) == []


# -------------------------------------------------------------- extras

def test_uninstalled_upstream_extra_is_flagged(tmp_path):
    # Shipped installs no extras (bare pip -e .), oracle installs all+anthropic.
    shipped = _SHIPPED_OK.replace('pip install -e ".[all,anthropic]"', "pip install -e .")
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=shipped, manifest=_EMPTY_MANIFEST)
    violations = check_packaging_contract(repo)
    assert any("'all'" in v for v in violations) and any("'anthropic'" in v for v in violations), violations


def test_extras_exception_silences_the_gap(tmp_path):
    shipped = _SHIPPED_OK.replace('pip install -e ".[all,anthropic]"', "pip install -e .")
    manifest = (
        "extras_exceptions:\n"
        "  - extra: all\n    why: lazy\n"
        "  - extra: anthropic\n    why: lazy\n"
    )
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=shipped, manifest=manifest)
    assert check_packaging_contract(repo) == []


# --------------------------------------------------------- stale exceptions

def test_stale_apt_exception_is_flagged(tmp_path):
    # 'ghost' is allowlisted but upstream never installs it -> obsolete exception.
    manifest = "apt_exceptions:\n  - package: ghost\n    kind: omit\n    why: gone\n"
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=_SHIPPED_OK, manifest=manifest)
    violations = check_packaging_contract(repo)
    assert any("stale apt_exceptions" in v and "ghost" in v for v in violations), violations


def test_stale_extras_exception_is_flagged(tmp_path):
    manifest = "extras_exceptions:\n  - extra: removed-extra\n    why: gone\n"
    repo = _make_repo(tmp_path, oracle=_ORACLE, shipped=_SHIPPED_OK, manifest=manifest)
    violations = check_packaging_contract(repo)
    assert any("stale extras_exceptions" in v for v in violations), violations


# ------------------------------------------------------------ structural

def test_missing_oracle_is_structural_error(tmp_path):
    (tmp_path / "Dockerfile").write_text(_SHIPPED_OK, encoding="utf-8")
    (tmp_path / "packaging-overrides.yaml").write_text(_EMPTY_MANIFEST, encoding="utf-8")
    with pytest.raises(PackagingContractError) as exc:
        check_packaging_contract(tmp_path)
    assert exc.value.step == "oracle"


def test_main_exit_2_when_oracle_missing(tmp_path, capsys):
    (tmp_path / "Dockerfile").write_text(_SHIPPED_OK, encoding="utf-8")
    (tmp_path / "packaging-overrides.yaml").write_text(_EMPTY_MANIFEST, encoding="utf-8")
    assert main(["--repo-root", str(tmp_path)]) == 2
    assert "make build" in capsys.readouterr().err


def test_main_exit_1_on_violation(tmp_path, capsys):
    shipped = _SHIPPED_OK.replace("sha256:AAAA AS node_source", "sha256:BBBB AS node_source")
    _make_repo(tmp_path, oracle=_ORACLE, shipped=shipped, manifest=_EMPTY_MANIFEST)
    assert main(["--repo-root", str(tmp_path)]) == 1


# ------------------------------------------------ integration: real tree

def test_real_tree_honors_the_contract():
    if not (_REPO_ROOT / "dist" / "nadia" / "Dockerfile").exists():
        pytest.skip("dist/nadia/Dockerfile absent — run `make build` first")
    assert check_packaging_contract(_REPO_ROOT) == []
