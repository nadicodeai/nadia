"""tests/test_dockerfile_facets.py — unit tests for the Dockerfile facet parser.

Drives tools/dockerfile_facets.parse_facets over hand-written fragments AND the
real repo Dockerfiles (./Dockerfile shipped, dist/nadia/Dockerfile oracle) so the
extractor is proven against the exact text the packaging-contract gate parses.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS = _REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from dockerfile_facets import parse_facets  # noqa: E402


# ---------------------------------------------------------------- FROM parsing

def test_from_with_digest_and_stage_is_split_into_parts():
    facets = parse_facets(
        "FROM node:22-bookworm-slim@sha256:7af0 AS node_source\n"
    )
    ref = facets.image_by_name("node")
    assert ref is not None
    assert ref.image == "node"
    assert ref.tag == "22-bookworm-slim"
    assert ref.digest == "sha256:7af0"
    assert ref.stage == "node_source"


def test_from_registry_path_image_basename_matches():
    facets = parse_facets(
        "FROM ghcr.io/astral-sh/uv:0.11.6-python3.13-trixie@sha256:b3c5 AS uv_source\n"
    )
    ref = facets.image_by_name("uv")
    assert ref is not None
    assert ref.image == "ghcr.io/astral-sh/uv"
    assert ref.digest == "sha256:b3c5"


def test_from_argref_tag_is_preserved_verbatim():
    facets = parse_facets("FROM python:${PYTHON_VERSION} AS builder\n")
    ref = facets.image_by_name("python")
    assert ref is not None
    assert ref.tag == "${PYTHON_VERSION}"
    assert ref.digest is None


def test_bare_stage_reference_has_no_tag_or_digest():
    facets = parse_facets(
        "FROM python:3.13 AS runtime-slim\nFROM runtime-slim AS runtime-full\n"
    )
    images = [f.image for f in facets.froms]
    assert images == ["python", "runtime-slim"]


# ----------------------------------------------------------------- ARG parsing

def test_arg_with_default_is_captured():
    facets = parse_facets("ARG S6_OVERLAY_VERSION=3.2.3.0\n")
    assert facets.args["S6_OVERLAY_VERSION"] == "3.2.3.0"


def test_arg_without_default_is_none():
    facets = parse_facets("ARG TARGETARCH\n")
    assert facets.args["TARGETARCH"] is None


# ----------------------------------------------------------- apt extraction

def test_apt_packages_extracted_from_multiline_run_without_flags_or_comments():
    body = (
        "# a comment line that must be ignored\n"
        "RUN apt-get update && \\\n"
        "    apt-get install -y --no-install-recommends \\\n"
        "        ffmpeg \\\n"
        "        curl \\\n"
        "        python3-dev && \\\n"
        "    rm -rf /var/lib/apt/lists/*\n"
    )
    facets = parse_facets(body)
    assert facets.apt_packages == {"ffmpeg", "curl", "python3-dev"}
    # rm/var/lib tokens after && must NOT leak in.
    assert "rm" not in facets.apt_packages
    assert "update" not in facets.apt_packages


def test_apt_single_line_install_list_is_extracted():
    body = (
        "RUN apt-get update && "
        "apt-get install -y --no-install-recommends "
        "ca-certificates curl python3 docker-cli xz-utils && "
        "rm -rf /var/lib/apt/lists/*\n"
    )
    facets = parse_facets(body)
    assert {"ca-certificates", "curl", "python3", "docker-cli", "xz-utils"} <= facets.apt_packages
    assert "rm" not in facets.apt_packages


def test_inline_comment_tokens_in_prose_are_not_packages():
    # A prose comment mentioning 'ffmpeg' must not become an apt package.
    body = (
        "#   ffmpeg                -> voice mode audio pipeline.\n"
        "RUN apt-get install -y curl && rm -rf /x\n"
    )
    facets = parse_facets(body)
    assert facets.apt_packages == {"curl"}


# -------------------------------------------------------- ENV / ENTRYPOINT

def test_env_key_value_pairs_are_captured():
    facets = parse_facets('ENV NADIA_WEB_DIST=/opt/nadia/nadia_cli/web_dist\n')
    assert facets.env["NADIA_WEB_DIST"] == "/opt/nadia/nadia_cli/web_dist"


def test_entrypoint_exec_vector_is_parsed():
    facets = parse_facets('ENTRYPOINT [ "/init", "/opt/nadia/docker/main-wrapper.sh" ]\n')
    assert facets.entrypoint == ("/init", "/opt/nadia/docker/main-wrapper.sh")


def test_empty_cmd_vector_is_empty_tuple_not_none():
    facets = parse_facets("CMD [ ]\n")
    assert facets.cmd == ()


def test_last_entrypoint_wins_across_stages():
    facets = parse_facets(
        'ENTRYPOINT ["a"]\nFROM x AS y\nENTRYPOINT [ "/init", "w" ]\n'
    )
    assert facets.entrypoint == ("/init", "w")


# --------------------------------------------------------------- extras

def test_uv_sync_extras_are_collected():
    facets = parse_facets(
        "RUN uv sync --frozen --extra all --extra messaging --extra anthropic\n"
    )
    assert facets.install_extras == {"all", "messaging", "anthropic"}


def test_bare_pip_editable_install_has_no_extras():
    facets = parse_facets("RUN pip install --no-cache-dir -e .\n")
    assert facets.install_extras == frozenset()


def test_pip_bracket_extras_are_collected():
    facets = parse_facets('RUN pip install -e ".[all,messaging]"\n')
    assert facets.install_extras == {"all", "messaging"}


# ------------------------------------------------ real repo Dockerfiles

@pytest.fixture(scope="module")
def shipped_facets():
    return parse_facets((_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def oracle_facets():
    oracle = _REPO_ROOT / "dist" / "nadia" / "Dockerfile"
    if not oracle.exists():
        pytest.skip("dist/nadia/Dockerfile absent — run `make build` first")
    return parse_facets(oracle.read_text(encoding="utf-8"))


def test_shipped_node_pin_matches_oracle(shipped_facets, oracle_facets):
    ship = shipped_facets.image_by_name("node")
    oracle = oracle_facets.image_by_name("node")
    assert ship is not None and oracle is not None
    assert ship.digest == oracle.digest, "node base digest drifted from upstream"


def test_shipped_s6_pins_match_oracle(shipped_facets, oracle_facets):
    for arg in (
        "S6_OVERLAY_VERSION",
        "S6_OVERLAY_NOARCH_SHA256",
        "S6_OVERLAY_X86_64_SHA256",
        "S6_OVERLAY_AARCH64_SHA256",
        "S6_OVERLAY_SYMLINKS_SHA256",
    ):
        assert shipped_facets.args.get(arg) == oracle_facets.args.get(arg), arg


def test_shipped_entrypoint_matches_oracle(shipped_facets, oracle_facets):
    assert shipped_facets.entrypoint is not None
    assert oracle_facets.entrypoint is not None
    assert shipped_facets.entrypoint[0] == oracle_facets.entrypoint[0] == "/init"
    assert Path(shipped_facets.entrypoint[1]).name == Path(oracle_facets.entrypoint[1]).name
    assert shipped_facets.entrypoint[1] == "/opt/nadia/docker/main-wrapper.sh"


def test_oracle_installs_provider_extras(oracle_facets):
    # Guards the test's own premise: upstream eagerly installs these.
    assert {"all", "messaging", "anthropic", "bedrock", "azure-identity"} <= oracle_facets.install_extras
