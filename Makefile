# argo Makefile — stable user-facing entry point surface
#
# This file is the contract between maintainers and the build pipeline.
# Targets that are no-ops in M1 will be filled in by later plan milestones;
# they exist now so the contract is visible from day one.

.DEFAULT_GOAL := help

# -----------------------------------------------------------------------------
# Top-level workflow targets
# -----------------------------------------------------------------------------

.PHONY: help
help:
	@echo "argo — pristine-upstream fork of hermes-agent"
	@echo ""
	@echo "Setup:"
	@echo "  make bootstrap        Pull upstream subtree + lift overlay assets (M1)"
	@echo ""
	@echo "Build:"
	@echo "  make build            Produce dist/argo/ from upstream + patches + overlay (M1.8)"
	@echo "  make clean            Remove dist/ and .sync-workdir/"
	@echo "  make leakage-static   Static leakage scan over dist/argo/ (M2.2)"
	@echo ""
	@echo "Sync:"
	@echo "  make sync             Pull upstream, re-apply patches (M4.2)"
	@echo "  make sync-resume      Continue after manual conflict resolution (M4.2)"
	@echo "  make sync-reset       Wipe .sync-workdir/ (M4.2)"
	@echo ""
	@echo "Docker:"
	@echo "  make image            Build slim variant -> ghcr.io/nadicodeai/argo:dev (M5.1)"
	@echo "  make image-full       Build full variant -> ghcr.io/nadicodeai/argo:dev-full (issue #2)"
	@echo "  make publish          Push image to ghcr.io (M5.2)"
	@echo ""
	@echo "Quality gates:"
	@echo "  make lint             ruff check (M4.3)"
	@echo "  make typecheck        ty check (M4.3)"
	@echo "  make test             pytest the fork's own tests/ (NOT dist/argo's)"
	@echo "  make dist-test        Run dist/argo's renamed upstream suite (mirrors CI dist-argo-tests; the real gate for dist changes)"
	@echo "  make check-upstream-pristine Verify upstream/ matches last sync commit (M4.1)"
	@echo "  make check-packaging-contract Verify ./Dockerfile tracks upstream packaging (no drift)"
	@echo "  make install-smoke    Docker-driven install.sh smoke test (M5.2; IU-AC-4/5/9)"
	@echo "  make update-smoke     Docker update-smoke (IU-AC-9/10/11; M5.3 Part A)"
	@echo "  make update-smoke-telegram  Docker /update mid-flight (IU-AC-6; M5.3 Part B, currently SKIPPED)"
	@echo ""
	@echo "Patch ops:"
	@echo "  make patch-new NAME=<slug>   Start a new patch (M3.1)"
	@echo "  make patch-refresh           quilt refresh current patch (M3.1)"
	@echo "  make patch-list              List patches in series (M3.1)"

# -----------------------------------------------------------------------------
# Build (M1.8 wires the real implementation)
# -----------------------------------------------------------------------------

.PHONY: build
build:
	@if [ -x tools/build.py ]; then \
		python tools/build.py; \
	else \
		echo "tools/build.py not yet implemented (M1.8)"; \
		exit 1; \
	fi

.PHONY: clean
clean:
	rm -rf dist/ .sync-workdir/

.PHONY: leakage-static
leakage-static:
	@if [ -x tools/verify_no_leakage.py ]; then \
		python tools/verify_no_leakage.py dist/argo/; \
	else \
		echo "tools/verify_no_leakage.py not yet implemented (M2.2)"; \
		exit 1; \
	fi

# -----------------------------------------------------------------------------
# Sync workflow (M4.2 wires the real implementation)
# -----------------------------------------------------------------------------

.PHONY: sync sync-resume sync-reset
sync:
	python tools/sync.py

sync-resume:
	python tools/sync.py --resume

sync-reset:
	python tools/sync.py --reset

# -----------------------------------------------------------------------------
# Docker (M5 wires the real implementation)
# -----------------------------------------------------------------------------

# M5.1 + issue #2: build the runtime image via multi-stage Dockerfile.
#
# Two variants ship (NFR-3 resolution — see AGENTS.md § Image variants):
#   :slim / :dev       — runtime-slim target, ~371 MB CLI-only.
#   :latest / :dev-full — runtime-full target, ~4.5 GB customer-parity.
#
# Multi-arch (linux/arm64) is OQ-4 — deferred to release.yml. PR-time
# builds are linux/amd64 only for speed; CI release builds go multi-arch.
#
# SOURCE_DATE_EPOCH propagates the commit timestamp into the image for
# AC-8 determinism. Determinism is a gate ONLY for the slim variant
# (where the `dist/argo/` tree-hash is the artifact); the full variant
# fetches chromium + s6-overlay + npm tarballs at build time and is
# best-effort by design (spec § Build Reproducibility).
.PHONY: image
image:
	docker buildx build \
		--build-arg SOURCE_DATE_EPOCH=$$(git log -1 --format=%ct) \
		--platform linux/amd64 \
		--target runtime-slim \
		--load \
		-t ghcr.io/nadicodeai/argo:dev \
		.

.PHONY: image-full
image-full:
	docker buildx build \
		--build-arg SOURCE_DATE_EPOCH=$$(git log -1 --format=%ct) \
		--platform linux/amd64 \
		--target runtime-full \
		--load \
		-t ghcr.io/nadicodeai/argo:dev-full \
		.

.PHONY: publish
publish:
	scripts/publish.sh

# -----------------------------------------------------------------------------
# Quality gates (M4.3 wires real implementations)
# -----------------------------------------------------------------------------

.PHONY: lint
lint:
	@echo "make lint: not yet implemented (M4.3)"

.PHONY: typecheck
typecheck:
	@echo "make typecheck: not yet implemented (M4.3)"

.PHONY: test
test:
	@if command -v pytest > /dev/null && [ -d tests ]; then \
		pytest -m 'not integration'; \
	else \
		echo "make test: pytest not available or no tests dir (M4.3)"; \
	fi

# The renamed upstream test suite run against dist/argo/, EXACTLY as CI's
# `dist-argo-tests` job does. This is the ONLY gate that exercises dist/argo
# content changes (packaging-strip.yaml prunes, content_edits, patches, rebrand)
# against the full suite. `make build`, `leakage-static`, and `test` (which runs
# the fork's OWN tests/, not dist/argo's) do NOT cover it.
#
# CI runs this on `pull_request` + push to `main` only, and it is currently
# *non-blocking* — so a branch pushed and merged straight to `main` (no PR)
# bypasses it entirely. That gap shipped a red main once (China-strip: two
# general tests that import/enumerate the pruned platforms). RUN THIS — or open
# a PR and read the dist-argo-tests result — BEFORE merging any dist-affecting
# change to main.
#
#   make dist-test                                              # full suite (heavy; provisions a 3.11 venv with [all,dev])
#   make dist-test DIST_TEST_ARGS="--slice 1/6"                 # one CI-equivalent slice
#   make dist-test DIST_TEST_ARGS="--paths tests/a.py:tests/b.py"  # only these files (colon-separated; fast iteration)
.PHONY: dist-test
dist-test: build
	cd dist/argo && uv venv .venv-test --python 3.11
	cd dist/argo && uv pip install --quiet --python .venv-test/bin/python -e ".[all,dev]"
	cd dist/argo && OPENROUTER_API_KEY="" OPENAI_API_KEY="" NOUS_API_KEY="" \
		.venv-test/bin/python scripts/run_tests_parallel.py $(DIST_TEST_ARGS)

.PHONY: check-upstream-pristine
check-upstream-pristine:
	python tools/check_upstream_pristine.py

# Verify the shipped ./Dockerfile has not silently diverged from upstream's
# packaging (the renamed-upstream oracle dist/argo/Dockerfile). Operates on an
# existing dist/argo/ tree, like leakage-static — run `make build` first
# (the checker exits 2 with that hint if the oracle is absent).
.PHONY: check-packaging-contract
check-packaging-contract:
	python tools/check_packaging_contract.py

# M5.2: Docker-driven install.sh smoke harness.
#
# Pulls the renamed install.sh from the live release branch
# (https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh),
# runs it in a clean ubuntu:22.04 container, and asserts five invariants
# (.install_method=git, argo --version exits 0, banner matches hermes regex,
# no "Updating from fork" warning, no ~/.hermes/ leakage). Closes IU-AC-4,
# IU-AC-5, IU-AC-9 (static portion). See tests/install_smoke/run.sh.
.PHONY: install-smoke
install-smoke:
	bash tests/install_smoke/run.sh

# -----------------------------------------------------------------------------
# Patch operations (M3.1 wires the real implementations)
# -----------------------------------------------------------------------------

.PHONY: patch-new patch-refresh patch-list

patch-new:
	@echo "make patch-new NAME=<slug>: not yet implemented (M3.1)"
	@exit 1

patch-refresh:
	@echo "make patch-refresh: not yet implemented (M3.1)"
	@exit 1

patch-list:
	@if [ -f patches/series ]; then \
		cat patches/series; \
	else \
		echo "patches/series does not exist"; \
		exit 1; \
	fi

# -----------------------------------------------------------------------------
# Update-smoke harness (M5.3)
# -----------------------------------------------------------------------------
# Part A — IU-AC-9 (full), IU-AC-10, IU-AC-11. Boots ubuntu:22.04, installs
# argo from the public `release` branch, asserts:
#   - no "Updating from fork" warning on `argo update` (IU-AC-9 full)
#   - `ARGO_MANAGED=1 argo update` prints "is managed by" on stderr (IU-AC-10;
#     exit code NOT asserted per plan § M5.3 stderr-substring note)
#   - pre_update_backup writes a zip; `argo import` restores it (IU-AC-11)
# Wall-clock budget < 5 min (spec IU-AC-15).
#
# Part B — IU-AC-6 Telegram /update mid-flight. Currently exits 77 (skipped)
# because the assertion needs systemd (cmd_update's restart path), which a
# vanilla ubuntu:22.04 container doesn't provide. The Makefile target treats
# 77 as "skipped, not failed" (autotools convention).
.PHONY: update-smoke update-smoke-telegram
update-smoke:
	bash tests/update_smoke/run.sh

update-smoke-telegram:
	@bash tests/update_smoke/run_telegram.sh; rc=$$?; \
	if [ $$rc -eq 77 ]; then \
		echo "update-smoke-telegram: SKIPPED (exit 77)"; \
		exit 0; \
	else \
		exit $$rc; \
	fi

# -----------------------------------------------------------------------------
# Bootstrap (M1)
# -----------------------------------------------------------------------------

.PHONY: bootstrap
bootstrap:
	@if [ -d upstream ]; then \
		echo "upstream/ already exists; refusing to re-bootstrap"; \
		exit 1; \
	fi
	@echo "make bootstrap: see plan M1.2 — git subtree add --prefix=upstream …"
