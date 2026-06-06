# syntax=docker/dockerfile:1.6
#
# Multi-stage Dockerfile for ghcr.io/nadicodeai/argo.
#
# Stages
# ------
# Stage 1 (builder):       apt {git, quilt, make, gcc, libffi-dev, python3-dev,
#                          ca-certificates}; copies repo and runs `make build`
#                          to produce dist/argo/. Never shipped.
# Stage 2 (runtime-slim):  python:3.13-slim-bookworm; copies ONLY dist/argo/ →
#                          /opt/argo. Strips argo_sync/ per spec OQ-10. Installs
#                          upstream's runtime deps via `pip install -e .` into a
#                          venv inside the image. Result: ~371 MB CLI-only image
#                          tagged `:slim` / `:dev`.
# Stage 3 (runtime-full):  extends runtime-slim with the feature surface the
#                          legacy v0.14.0 image carries — node/npm (TUI web
#                          dashboard), ffmpeg (voice mode), playwright +
#                          chromium (browser-tool MCP), and s6-overlay
#                          (supervised dashboard / gateway). Result: ~4.5 GB
#                          image tagged `:latest` / `:dev-full`.
#
# Spec references
# ---------------
# FR-7  Docker image: multi-stage, ONLY dist/argo/ in final image, never
#       upstream/patches/overlay/tools.
# FR-11 Docker-only (no PyPI).
# OQ-10 Strip argo_sync from final image.
# AC-8  Determinism via SOURCE_DATE_EPOCH (slim path only — full path adds
#       network-fetched npm + chromium + s6-overlay binaries which break
#       byte-determinism by design).
# NFR-3 Image size ≤5% over legacy (resolved by issue #2 via the slim/full
#       split: slim is 92% smaller for CLI-only deploys; full matches legacy
#       surface for customers who need TUI/voice/browser/dashboard).
#
# Multi-arch
# ----------
# release.yml builds both stages for linux/amd64 + linux/arm64 (OQ-4 /
# issue #8). PR-time builds stay amd64-only for speed. s6-overlay tarballs
# are arch-keyed via TARGETARCH (BuildKit auto-populates).
#
# Selecting a stage
# -----------------
#   docker buildx build --target runtime-slim -t argo:slim .
#   docker buildx build --target runtime-full -t argo:latest .
#
# `make image` defaults to runtime-slim. `make image-full` builds runtime-full.
#
# Base image divergence from legacy
# ---------------------------------
# Legacy `~/Code/argo-agent/Dockerfile` builds on `debian:13.4` (trixie)
# and installs Python 3 via apt. The slim+full stages here build on
# `python:3.13-slim-bookworm` (Debian 12 + an upstream-built CPython).
# This is INTENTIONAL: bookworm's stable LTS posture + the python-slim
# base lets pip install -e . land prebuilt wheels for psutil / pydantic-core
# / cryptography without dragging the full build-essential toolchain into
# the runtime layer. Trade-offs vs legacy:
#
#   - glibc differs slightly (bookworm 2.36 vs trixie 2.39). Native deps
#     that linked against trixie's newer glibc may surface manylinux_2_36
#     wheel-resolution warnings; the wheels themselves still work.
#   - libssl is OpenSSL 3.0 (bookworm) vs OpenSSL 3.2 (trixie). All TLS
#     paths in upstream's runtime deps exercise the stdlib `ssl` module,
#     which is satisfied by either.
#   - Python toolchain is upstream's official 3.13.x (slim variant); legacy
#     uses Debian's packaged python3 (3.13.x via trixie). Behaviour is
#     identical for our use; the wheel-resolution surface differs.
#
# This trade-off is locked in for issue #2 — switching base images is
# higher-risk than the SUPERVISION/ENTRYPOINT repair pass demands. Revisit
# (perhaps unifying on trixie + apt python) if the wheel-skew surfaces
# real bugs in the customer-parity surface.

ARG PYTHON_VERSION=3.13-slim-bookworm

# ---------- Node 22 LTS source stage --------------------------------------
# Debian bookworm's apt `nodejs` package is Node 18.x, but the dashboard's
# build toolchain (Vite — web/package-lock.json pins v7.3.2) requires Node
# >=20.19 — on Node 18 `vite build` aborts ("Vite requires Node.js version
# 20.19+ or 22.12+") and the @tailwindcss/oxide native binding fails to load.
# Rather than carry Debian's EOL nodejs, copy node + npm + corepack from the
# official node:22 image into runtime-full below. This mirrors upstream's
# Dockerfile, which copies Node 22 for the same reason. Pinned by digest
# (supply-chain integrity; matches this repo's SHA-pinning stance). The tag
# digest is a multi-arch manifest list, so `COPY --from` resolves per-arch
# under buildx.
FROM node:22-bookworm-slim@sha256:7af03b14a13c8cdd38e45058fd957bf00a72bbe17feac43b1c15a689c029c732 AS node_source

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

# Release-date stamp (the ONE value a hermetic build can't discover itself).
#
# `make build` regenerates dist/argo/ from PRISTINE upstream/, so
# argo_cli/__init__.py would carry upstream's __release_date__, not the Argo
# release date — which is exactly how the v2026.6.5 image shipped reporting
# 2026.5.29. The date IS the release tag (v2026.6.5 → 2026.6.5), but the docker
# build is hermetic: .dockerignore excludes .git (237 MB), so the builder can't
# read the tag. So the single calver value is passed in and build.py stamps it
# (see _stamp_release_date). Empty on dev builds (PR/main) → upstream's date is
# kept, honest for an unreleased tree. docker-publish.yml derives this from the
# release tag automatically — nobody types it.
ARG ARGO_RELEASE_DATE=""
ENV ARGO_RELEASE_DATE=${ARGO_RELEASE_DATE}

# Run the renamer build pipeline: copies upstream/, applies patches/,
# layers overlay/, runs the rename engine, writes dist/argo/.
# The resulting tree is what the runtime stage ships.
RUN make build

# ---------- Stage 2: runtime-slim -----------------------------------------
#
# Minimal CLI runtime. Suitable for headless deployments (CI, batch agents,
# server-side automation) where the TUI dashboard / voice mode / browser
# tools are not needed. ~371 MB.
FROM python:${PYTHON_VERSION} AS runtime-slim

ARG SOURCE_DATE_EPOCH
ENV SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH}

# Runtime apt deps kept to the minimum needed by upstream's argo runtime.
#   ca-certificates → outbound TLS to model APIs.
#   git → some upstream code paths shell out to `git` (skill clones, etc.).
# Anything heavier (node, npm, playwright, ffmpeg, s6-overlay) lives in
# the runtime-full stage. This stage covers the 7 FR-16 parity surfaces
# (help, version, doctor, mcp, hooks, auth, sessions) — anything beyond
# those surfaces (TUI dashboard, voice, browser-tool MCP) requires :full.
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
# home; the slim image uses /home/argo for simplicity — the path is
# contained by ARGO_HOME so user code doesn't depend on it). The full
# stage rebinds ARGO_HOME to /opt/data to match legacy on-disk layout.
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
# Also strip tests/ (dev-only).
#
# NOTE: /opt/argo/tools is intentionally PRESERVED. Upstream's
# pyproject.toml declares `tools` as a runtime package, and several
# argo_cli modules (mcp_config, sessions DB) import from it at
# runtime. The M5.1 implementer's defensive `rm tools/` broke
# `argo mcp list` and `argo sessions list` — caught by the M6 parity
# suite. The strip is now scoped to OUR build-time tools (none of
# which land in dist/) plus upstream's tests; nothing else.
RUN rm -rf /opt/argo/argo_sync /opt/argo/tests

# Install upstream's runtime deps. Upstream's pyproject.toml lists the
# package and its dep closure; `pip install -e .` resolves and installs
# them into a venv at /opt/argo/.venv. `argo` ends up on PATH via the
# venv's bin/ directory (ENV PATH above).
WORKDIR /opt/argo
RUN python -m venv .venv && \
    .venv/bin/pip install --no-cache-dir --upgrade pip && \
    .venv/bin/pip install --no-cache-dir -e . && \
    chown -R argo:argo /opt/argo/.venv

# Ensure ARGO_HOME exists and is writable by the argo user. Without
# this, `argo mcp list` / `argo sessions list` (and anything else that
# does `ensure_argo_home()`) hit PermissionError because the COPY above
# may have created /home/argo/.argo as root. Caught by M6 parity.
RUN mkdir -p "${ARGO_HOME}" && chown -R argo:argo /home/argo

# Drop privileges. From here on the container runs as the argo user.
USER argo
WORKDIR /home/argo

# Volume for $ARGO_HOME so customers can mount persistent state.
VOLUME ["/home/argo/.argo"]

# Default invocation: the renamed `argo` console script (from
# argo_cli.main:main in pyproject's [project.scripts]).
CMD ["argo"]

# ---------- Stage 3: runtime-full -----------------------------------------
#
# Customer-parity runtime. Adds the feature surface legacy v0.14.0 ships:
#
#   node + npm        → TUI web dashboard build / launch (`argo dashboard`,
#                       `argo --tui`, ui-tui/web bundles).
#   ffmpeg            → voice-mode audio capture + transcode pipeline.
#   playwright +
#     chromium (shell)→ browser-tool MCP, agent-browser npm dep.
#   s6-overlay        → in-container supervisor (PID 1 = /init) for the
#                       dashboard, gateway, and per-profile services. Mirrors
#                       legacy ~/Code/argo-agent/Dockerfile's supervision
#                       model so customer-facing service lifecycle behaviour
#                       is preserved.
#
# This stage explicitly trades determinism for parity: chromium binaries
# and s6-overlay tarballs are network-fetched at build time. AC-8
# determinism is only a gate for the slim image (where `dist/argo/`
# tree-hash is the artifact). The full image's reproducibility is
# best-effort and explicitly NOT a gate (spec § Build Reproducibility).
#
# Multi-arch: TARGETARCH is auto-populated by BuildKit. s6-overlay
# tarballs are arch-keyed (x86_64 / aarch64) with checksum verification
# mirroring legacy's supply-chain integrity stance. Chromium and node
# packages come from Debian / Microsoft repos that already publish
# per-arch binaries.
FROM runtime-slim AS runtime-full

USER root

# Disable Python stdout buffering (already set in -slim but restated for
# clarity in this stage's docs/comments since runtime-full is the
# customer-facing default).
ENV PYTHONUNBUFFERED=1

# Store Playwright browsers outside any volume mount so the build-time
# install survives the /opt/data volume overlay at runtime. Mirrors
# legacy Dockerfile line 9.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/argo/.playwright

# Apt deps for the full feature surface. The set tracks legacy
# `~/Code/argo-agent/Dockerfile`'s runtime apt closure (line 18-21) for
# customer-parity. The deltas vs. an "absolute minimum" picture:
#
#   (node + npm)          → TUI dashboard build + launch. NOT apt-installed:
#                           sourced from the node:22 stage just below this
#                           apt block (bookworm's apt nodejs is Node 18, too
#                           old for the Vite web build — needs Node >=20.19).
#   ffmpeg                → voice mode audio pipeline.
#   curl, xz-utils        → s6-overlay tarball fetch + extraction.
#   procps                → ps/top inside the container (legacy parity;
#                           also used by some MCP servers).
#   ripgrep               → `tools/file_operations.py` shells out to `rg`
#                           for file search; the fallback to `find`+`grep`
#                           is correct but markedly slower. Legacy ships it
#                           in the customer-facing image (review #6).
#   openssh-client        → `argo_cli/profile_distribution.py` clones
#                           profile bundles from `git@` / `ssh://` URLs at
#                           runtime; without ssh that path errors out.
#   make, gcc, g++,       → Native-compile toolchain. Two consumers:
#   python3-dev,            (1) `tools/lazy_deps.py` pip-installs platform extras
#   libffi-dev,             (sounddevice, brotlicffi, mautrix[encryption],
#   libolm-dev              asyncpg, …) on first use; some lack manylinux
#                           wheels for arm64 and fall back to source builds.
#                           libolm-dev provides the Olm/Megolm C headers that
#                           mautrix[encryption] (Matrix E2EE) links against;
#                           upstream apt-added it in the 56236b16 sync, mirrored
#                           here so the lazy Matrix-encryption build resolves. It
#                           belongs with the lazy_deps build toolchain, not the
#                           deferred Python extras (packaging-overrides.yaml).
#                           (2) node-gyp builds node-pty 1.1.0's C++ binding at
#                           `npm install` time. node-pty entered the dashboard
#                           npm tree transitively (@streamdown/math →
#                           @nous-research/ui) in the ef3a650f upstream sync and
#                           ships no prebuilt for node 22 / linux, so node-gyp
#                           compiles it — which needs BOTH `make` and a C++
#                           compiler (`g++`); `gcc` alone is insufficient.
#   iputils-ping          → `ping` for in-container network/connectivity triage.
#                           Upstream apt-installs it (ef3a650f); mirrored here
#                           for parity. (python-is-python3 is the other dep
#                           upstream added — NOT mirrored: the python:3.13-slim
#                           base already provides `python`, and apt-installing
#                           it would mis-symlink /usr/bin/python. Recorded as a
#                           base-provided divergence in packaging-overrides.yaml.)
#
# Legacy ALSO carries docker-cli (and the dpkg-dev remainder of build-essential).
# We omit both: docker-cli is only for nested-docker workflows mounting
# /var/run/docker.sock (no customer-facing surface uses it), and dpkg-dev only
# builds .deb packages (nothing here does; libc6-dev headers arrive transitively
# with gcc/g++).
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        xz-utils \
        procps \
        ripgrep \
        iputils-ping \
        openssh-client \
        make \
        gcc \
        g++ \
        python3-dev \
        libffi-dev \
        libolm-dev && \
    rm -rf /var/lib/apt/lists/*

# Node 22 LTS: copy the node binary plus the bundled npm + corepack JS trees
# from the node_source stage (see the node:22 stage near the top of the file).
# Debian bookworm's apt nodejs is Node 18 — too old for the Vite web build
# (needs >=20.19), so node/npm are sourced from the official node:22 image
# instead of apt. Mirrors upstream's Dockerfile.
COPY --chmod=0755 --from=node_source /usr/local/bin/node /usr/local/bin/
COPY --from=node_source /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=node_source /usr/local/lib/node_modules/corepack /usr/local/lib/node_modules/corepack
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    ln -sf /usr/local/lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack

# ---------- s6-overlay install ----------
# Mirrors legacy ~/Code/argo-agent/Dockerfile lines 23-68. /init becomes
# PID 1 below (see ENTRYPOINT). Supplies supervision for the main argo
# process, the dashboard, and per-profile gateways. Multi-arch via
# TARGETARCH; checksum-verified against upstream-published SHA256.
#
# To bump S6_OVERLAY_VERSION, fetch the four `.sha256` files from the
# corresponding release and update the ARGs. A compromised release
# artifact fails the build loudly instead of producing a tampered image.
ARG TARGETARCH
ARG S6_OVERLAY_VERSION=3.2.3.0
ARG S6_OVERLAY_NOARCH_SHA256=b720f9d9340efc8bb07528b9743813c836e4b02f8693d90241f047998b4c53cf
ARG S6_OVERLAY_X86_64_SHA256=a93f02882c6ed46b21e7adb5c0add86154f01236c93cd82c7d682722e8840563
ARG S6_OVERLAY_AARCH64_SHA256=0952056ff913482163cc30e35b2e944b507ba1025d78f5becbb89367bf344581
ARG S6_OVERLAY_SYMLINKS_SHA256=a60dc5235de3ecbcf874b9c1f18d73263ab99b289b9329aa950e8729c4789f0e
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp/
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-noarch.tar.xz /tmp/
RUN set -eu; \
    case "${TARGETARCH:-amd64}" in \
        amd64) s6_arch="x86_64"; s6_arch_sha="${S6_OVERLAY_X86_64_SHA256}" ;; \
        arm64) s6_arch="aarch64"; s6_arch_sha="${S6_OVERLAY_AARCH64_SHA256}" ;; \
        *) echo "Unsupported TARGETARCH=${TARGETARCH} for s6-overlay" >&2; exit 1 ;; \
    esac; \
    curl -fsSL --retry 3 -o /tmp/s6-overlay-arch.tar.xz \
        "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${s6_arch}.tar.xz"; \
    { \
        printf '%s  %s\n' "${S6_OVERLAY_NOARCH_SHA256}" /tmp/s6-overlay-noarch.tar.xz; \
        printf '%s  %s\n' "${s6_arch_sha}" /tmp/s6-overlay-arch.tar.xz; \
        printf '%s  %s\n' "${S6_OVERLAY_SYMLINKS_SHA256}" /tmp/s6-overlay-symlinks-noarch.tar.xz; \
    } > /tmp/s6-overlay.sha256; \
    sha256sum -c /tmp/s6-overlay.sha256; \
    tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz; \
    tar -C / -Jxpf /tmp/s6-overlay-arch.tar.xz; \
    tar -C / -Jxpf /tmp/s6-overlay-symlinks-noarch.tar.xz; \
    rm /tmp/s6-overlay-*.tar.xz /tmp/s6-overlay.sha256

# ---------- npm + playwright install ----------
# The renamed tree in /opt/argo contains the upstream package.json (with
# the agent-browser dep that transitively brings in playwright). Run npm
# install + the workspace installs the same way legacy does. The chromium
# --only-shell build is the headless shell variant (~280 MB instead of
# ~600 MB for full chromium); legacy uses --only-shell for the same
# reason.
#
# npm_config_install_links=false forces npm to install `file:` deps as
# symlinks (the npm 10+ default) even on Debian's older bundled npm 9.x,
# which defaults to install-links=true and installs file deps as *copies*.
# Mirrors legacy's mitigation for the TUI launcher's npm-install loop.
ENV npm_config_install_links=false

WORKDIR /opt/argo
RUN npm install --prefer-offline --no-audit && \
    npx playwright install --with-deps chromium --only-shell && \
    if [ -d web ]; then (cd web && npm install --prefer-offline --no-audit); fi && \
    if [ -d ui-tui ]; then (cd ui-tui && npm install --prefer-offline --no-audit); fi && \
    npm cache clean --force

# Build dashboard + TUI bundles when their source trees are present. The
# rename engine preserves these directories from upstream; absence is
# treated as a no-op so the stage stays robust against upstream layout
# shifts.
RUN if [ -d web ] && [ -f web/package.json ]; then (cd web && npm run build); fi && \
    if [ -d ui-tui ] && [ -f ui-tui/package.json ]; then (cd ui-tui && npm run build); fi

# Re-chown node_modules + ui-tui assets so the argo user can write to
# them at runtime (the TUI launcher's _tui_need_npm_install() may
# trigger a runtime npm install — mirrors legacy line 152-154).
RUN chmod -R a+rX /opt/argo && \
    chown -R argo:argo /opt/argo/.venv && \
    if [ -d /opt/argo/node_modules ]; then chown -R argo:argo /opt/argo/node_modules; fi && \
    if [ -d /opt/argo/ui-tui ]; then chown -R argo:argo /opt/argo/ui-tui; fi

# Point web_server.py at the built dashboard bundle. Upstream's vite build
# emits to argo_cli/web_dist (post-rename); web_server.py reads
# ARGO_WEB_DIST and falls back to a package-relative web_dist only when the
# var is unset. Set it explicitly so the dashboard serves the build output
# regardless of CWD. Mirrors dist/argo/Dockerfile.
ENV ARGO_WEB_DIST=/opt/argo/argo_cli/web_dist

# Match legacy's on-disk layout: ARGO_HOME = /opt/data. Customer state
# bind-mounts to /opt/data via the docker-compose recipe shipped with
# legacy (and any equivalent argo recipe). The slim stage's
# /home/argo/.argo VOLUME declaration is overridden here.
ENV ARGO_HOME=/opt/data
RUN mkdir -p /opt/data && chown argo:argo /opt/data
VOLUME ["/opt/data"]

# ---------- s6-overlay service wiring ----------
# The renamed source tree under /opt/argo/docker/ carries the supervision
# scripts that were lifted from upstream (hermes/main-hermes →
# argo/main-argo) by the build-time rename engine. We install them into
# the canonical s6-overlay paths here so /init sees them at PID 1.
#
# Layout under /opt/argo/docker/ (post-rename):
#   docker/s6-rc.d/dashboard/{run,finish,type,dependencies.d/base}
#   docker/s6-rc.d/main-argo/{run,type,dependencies.d/base}
#   docker/s6-rc.d/user/contents.d/{dashboard,main-argo}
#   docker/cont-init.d/015-supervise-perms
#   docker/cont-init.d/02-reconcile-profiles
#   docker/stage2-hook.sh   (root-level cont-init logic)
#   docker/main-wrapper.sh  (CMD wrapper — see ENTRYPOINT below)
#
# Permissions: the rename engine preserves modes via shutil.copy2, so the
# `run` / `finish` / `stage2-hook.sh` / `main-wrapper.sh` files are already
# 0755 on disk. The `--chmod=0755` on the cont-init.d COPYs is belt-and-
# braces (matches legacy's explicit chmod).
#
# Per-profile gateway services are registered DYNAMICALLY at runtime by
# the profile create/delete hooks (Phase 4 of legacy's s6 plan); they
# live under /run/service/ (tmpfs) and are reconciled on container
# restart by /etc/cont-init.d/02-reconcile-profiles.
USER root
# `cp -a` preserves modes (so the 0755 on run/finish/stage2-hook.sh survives)
# but also preserves ownership. The source files were COPY --chown=argo:argo'd
# in the slim stage, so we explicitly re-chown the installed copies to root
# so s6-overlay can supervise them with its standard expectations.
RUN cp -a /opt/argo/docker/s6-rc.d/. /etc/s6-overlay/s6-rc.d/ && \
    chown -R root:root /etc/s6-overlay/s6-rc.d/ && \
    mkdir -p /etc/cont-init.d && \
    printf '#!/command/with-contenv sh\nexec /opt/argo/docker/stage2-hook.sh\n' \
        > /etc/cont-init.d/01-argo-setup && \
    chmod 0755 /etc/cont-init.d/01-argo-setup && \
    cp /opt/argo/docker/cont-init.d/015-supervise-perms /etc/cont-init.d/015-supervise-perms && \
    cp /opt/argo/docker/cont-init.d/02-reconcile-profiles /etc/cont-init.d/02-reconcile-profiles && \
    chown root:root /etc/cont-init.d/015-supervise-perms /etc/cont-init.d/02-reconcile-profiles && \
    chmod 0755 /etc/cont-init.d/015-supervise-perms /etc/cont-init.d/02-reconcile-profiles

# /init must run as root so the stage2 cont-init hook can chown the
# volume + usermod/groupmod the argo user for ARGO_UID/ARGO_GID remap.
# Each supervised service then drops to the argo user via s6-setuidgid
# in its own `run` script. Legacy does the same (see legacy Dockerfile
# lines 155-158). We intentionally do NOT switch to `USER argo` here:
# the slim stage ends with `USER argo`, but for full /init must be root.
#
# main-wrapper.sh and each s6 `run` script do their own `cd /opt/data`
# before dropping privileges, so we don't need to reset WORKDIR from
# the slim stage's `/home/argo` — it's irrelevant to /init.

# ENTRYPOINT mirrors legacy ~/Code/argo-agent/Dockerfile:223. /init is
# PID 1 (s6-svscan); it sets up the supervision tree, runs
# /etc/cont-init.d/* (our stage2 hook + supervise-perms +
# reconcile-profiles), starts s6-rc services declared in
# /etc/s6-overlay/s6-rc.d/, then exec's its remaining argv as the
# container's "main program" with stdin/stdout/stderr inherited. When
# the main program exits, /init begins stage-3 shutdown and the container
# exits with the program's exit code.
#
# main-wrapper.sh is prepended to user-supplied args automatically:
#
#   docker run <image>                  → /init main-wrapper.sh    (CMD default)
#   docker run <image> chat -q "hi"     → /init main-wrapper.sh chat -q hi
#   docker run <image> sleep infinity   → /init main-wrapper.sh sleep infinity
#   docker run <image> --tui            → /init main-wrapper.sh --tui
#
# main-wrapper.sh handles arg routing (bare-exec vs argo subcommand vs
# no-args), drops to the argo user via s6-setuidgid, and exec's the
# final program so its exit code becomes the container exit code.
# Without the wrapper-as-ENTRYPOINT, leading-dash args like `--version`
# or `--tui` would be intercepted by /init's POSIX shell.
ENTRYPOINT [ "/init", "/opt/argo/docker/main-wrapper.sh" ]
CMD [ ]

# ---------- Stage 4: runtime-fde ------------------------------------------
#
# Forward Deployed Engineer customer baseline. Extends runtime-full with the
# same eager optional Python surface baked into native and VM deployments, plus
# the customer init command. This target is intentionally separate from
# runtime-full so the default customer image remains unchanged unless callers
# explicitly build/pull an FDE tag.
FROM runtime-full AS runtime-fde

USER root

COPY --chmod=0755 scripts/argo-customer-init /usr/local/bin/argo-customer-init

RUN /opt/argo/.venv/bin/python -m pip install --no-cache-dir -U \
        "honcho-ai==2.0.1" \
        "python-telegram-bot[webhooks]==22.6" \
        "edge-tts==7.2.7" \
        "ddgs" && \
    mkdir -p /opt/data && \
    cat > /opt/data/SOUL.md.template <<'EOF' && \
    cat > /opt/data/honcho.json.template <<'EOF2' && \
    chown -R argo:argo /opt/data
# Customer Operating Context

Profile: {{PROFILE}}
Honcho workspace: {{HONCHO_WORKSPACE}}
Honcho peer: {{HONCHO_PEER}}

Use this file for customer-specific operating context, preferences, boundaries,
and escalation notes. Do not put long-lived secrets here.
EOF
{
  "aiPeer": "argo",
  "contextCadence": 1,
  "dialecticCadence": 2,
  "dialecticDepth": 1,
  "environment": "production",
  "pinUserPeer": true,
  "recallMode": "hybrid",
  "writeFrequency": "async"
}
EOF2
