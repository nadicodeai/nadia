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
	@echo "  make test             pytest (M4.3)"
	@echo "  make parity           Parity suite vs legacy image (M6; XFAIL-aware)"
	@echo "  make parity-strict    Parity suite without expected-FAIL whitelist"
	@echo "  make check-legacy-untouched  Verify ~/Code/argo-agent untouched (M2.4a)"
	@echo "  make check-upstream-pristine Verify upstream/ matches last sync commit (M4.1)"
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

.PHONY: parity
# `--allow-expected` reclassifies surfaces listed in
# tests/parity-expected.yml as XFAIL (non-blocking) so the gate is
# strict-against-regressions without false-positiving on the documented
# v0.8.0-vs-v0.14.0 baseline gap. See AGENTS.md § Parity baseline and
# tests/parity-expected.yml for the lifecycle. Use `make parity-strict`
# (or invoke the runner directly without the flag) to see the full
# unmasked diff during development.
parity:
	python tools/parity_runner.py --allow-expected

.PHONY: parity-strict
parity-strict:
	python tools/parity_runner.py

.PHONY: check-legacy-untouched
check-legacy-untouched:
	@if [ -x tools/check_legacy_untouched.sh ]; then \
		tools/check_legacy_untouched.sh --verify; \
	else \
		echo "tools/check_legacy_untouched.sh not yet implemented (M2.4a)"; \
		exit 1; \
	fi

.PHONY: check-upstream-pristine
check-upstream-pristine:
	python tools/check_upstream_pristine.py

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
