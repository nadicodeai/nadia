# syntax=docker/dockerfile:1.6
#
# Multi-stage Dockerfile for ghcr.io/nadicodeai/argo.
#
# Stage 1 (builder): apt {git, quilt, make, ca-certificates}; copies repo
#   and runs `make build` to produce dist/argo/.
# Stage 2 (runtime): python:3.13-slim-bookworm; copies ONLY dist/argo/ →
#   /opt/argo. Strips argo_sync/ per spec OQ-10. Installs upstream's
#   runtime deps via `pip install -e .` into a venv inside the image.
#
# Maps to spec FR-7 (Docker image), FR-11 (no PyPI), OQ-10 (strip
# argo_sync from final image), AC-8 (determinism via SOURCE_DATE_EPOCH),
# NFR-3 (image size ≤5% over legacy — best-effort at M5.1; full parity
# is M6).
#
# Multi-arch (linux/arm64) is OQ-4 — deferred to release.yml. PR-time
# builds are amd64-only for speed (see make image).
#
# Determinism: SOURCE_DATE_EPOCH is forwarded into the runtime env so
# `argo --version --verbose` and any timestamp-emitting code path inside
# the image can honor it. Docker layer hashes are explicitly NOT a gate
# (spec AC-8 rationale).

ARG PYTHON_VERSION=3.13-slim-bookworm

# ---------- Stage 1: builder ----------------------------------------------
FROM python:${PYTHON_VERSION} AS builder

ARG SOURCE_DATE_EPOCH
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}

# Build-time deps:
#   git, ca-certificates → required by quilt's git-format patches and any
#       upstream tooling that shells out to git during the install.
#   quilt → applies patches/ on top of upstream/ inside `make build`.
#   make  → orchestrates the build target.
# Native compile toolchain (gcc, libffi-dev, python3-dev) is required by a
# handful of upstream runtime deps (pydantic-core, psutil, cryptography
# wheels for non-amd64 arches). On linux/amd64 most wheels are prebuilt so
# this stage stays lean; keeping the toolchain present preserves arm64
# build viability when M5.2 / release.yml turns on multi-arch.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        quilt \
        make \
        ca-certificates \
        gcc \
        libffi-dev \
        python3-dev && \
    rm -rf /var/lib/apt/lists/*

# pyyaml is the rename engine's only non-stdlib import (spec § Tech Stack:
# "Build-time rename engine uses stdlib + pyyaml"). Installed at build
# time only; never carried into the runtime stage.
RUN pip install --no-cache-dir pyyaml==6.0.3

WORKDIR /src
COPY . /src

# Run the renamer build pipeline: copies upstream/, applies patches/,
# layers overlay/, runs the rename engine, writes dist/argo/.
# The resulting tree is what the runtime stage ships.
RUN make build

# ---------- Stage 2: runtime ----------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

ARG SOURCE_DATE_EPOCH
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}

# Runtime apt deps kept to the minimum needed by upstream's argo runtime.
#   ca-certificates → outbound TLS to model APIs.
#   git → some upstream code paths shell out to `git` (skill clones, etc.).
# Anything heavier (node, npm, playwright, ffmpeg, s6-overlay) is
# intentionally NOT in this minimal M5.1 image. Full parity with the
# legacy s6-supervised image is M6's problem; M5.1 only needs to satisfy
# the spec AC-7 minimum surface (argo --help / --version exit 0).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git && \
    rm -rf /var/lib/apt/lists/*

ARG ARGO_HOME=/home/argo/.argo
ENV ARGO_HOME=${ARGO_HOME}
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/argo/.venv/bin:${PATH}"

# Non-root user, mirrors legacy convention (uid 10000 used `/opt/data` as
# home; M5.1 uses /home/argo for simplicity — the path is contained by
# ARGO_HOME so user code doesn't depend on it).
RUN useradd -m -u 10000 -s /bin/bash argo

# Copy ONLY the renamed tree from the builder. Nothing else (upstream/,
# patches/, overlay/, tools/, .shepherd/, scripts/, argo-rename.yaml are
# all build-time-only and MUST NOT appear in the runtime image — spec
# FR-7).
COPY --from=builder --chown=argo:argo /src/dist/argo /opt/argo

# Strip the rename engine from the runtime image per spec OQ-10.
# argo_sync/ is a build-time tool, not a runtime API. Keeping it in
# the runtime image would let customers re-run the rename engine
# against the shipped tree (small attack surface; pointless capability).
# Also strip tests/ (dev-only) and tools/ (build-time) if they snuck
# through — defense in depth against spec leakage.
RUN rm -rf /opt/argo/argo_sync /opt/argo/tests /opt/argo/tools

# Install upstream's runtime deps. Upstream's pyproject.toml lists the
# package and its dep closure; `pip install -e .` resolves and installs
# them into a venv at /opt/argo/.venv. `argo` ends up on PATH via the
# venv's bin/ directory (ENV PATH above).
WORKDIR /opt/argo
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --upgrade pip && \
    .venv/bin/pip install --no-cache-dir -e . && \
    chown -R argo:argo /opt/argo/.venv

# Drop privileges. From here on the container runs as the argo user.
USER argo
WORKDIR /home/argo

# Volume for $ARGO_HOME so customers can mount persistent state.
VOLUME ["/home/argo/.argo"]

# Default invocation: the renamed `argo` console script (from
# argo_cli.main:main in pyproject's [project.scripts]).
CMD ["argo"]
