# nadia Makefile — stable user-facing entry point surface
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
	@echo "nadia — pristine-upstream fork of hermes-agent"
	@echo ""
	@echo "Setup:"
	@echo "  make bootstrap        Pull upstream subtree + lift overlay assets (M1)"
	@echo ""
	@echo "Setup (run once per clone):"
	@echo "  make install-hooks    Enable the pre-commit build gate (sets core.hooksPath)"
	@echo ""
	@echo "Build:"
	@echo "  make build            Produce dist/nadia/ from upstream + patches + overlay (M1.8)"
	@echo "  make gen-skin         Regenerate the committed Nadia skin overlay from the design system"
	@echo "  make clean            Remove dist/ and .sync-workdir/"
	@echo "  make leakage-static   Static leakage scan over dist/nadia/ (M2.2)"
	@echo ""
	@echo "Sync:"
	@echo "  make sync             Pull upstream, re-apply patches (M4.2)"
	@echo "  make sync-resume      Continue after manual conflict resolution (M4.2)"
	@echo "  make sync-reset       Wipe .sync-workdir/ (M4.2)"
	@echo ""
	@echo "Docker:"
	@echo "  make image            Build slim variant -> ghcr.io/nadicodeai/nadia:dev (M5.1)"
	@echo "  make image-full       Build full variant -> ghcr.io/nadicodeai/nadia:dev-full (issue #2)"
	@echo "  make fde-container    Build FDE customer image -> ghcr.io/nadicodeai/nadia:fde-dev"
	@echo "  make publish          Push image to ghcr.io (M5.2)"
	@echo ""
	@echo "Quality gates:"
	@echo "  make lint             ruff check (M4.3)"
	@echo "  make typecheck        ty check (M4.3)"
	@echo "  make test             pytest the fork's own tests/ (NOT dist/nadia's)"
	@echo "  make dist-test        Run dist/nadia's renamed upstream suite (mirrors CI dist-nadia-tests; the real gate for dist changes)"
	@echo "  make check-upstream-pristine Verify upstream/ matches last sync commit (M4.1)"
	@echo "  make check-packaging-contract Verify ./Dockerfile tracks upstream packaging (no drift)"
	@echo "  make install-smoke    Docker-driven install.sh smoke test (M5.2; IU-AC-4/5/9)"
	@echo "  make fde-container-smoke  Build and validate FDE customer container"
	@echo "  make fde-live-smoke  Validate live Telegram/Honcho credentials from FDE_* env"
	@echo "  make golden-vm-smoke  Docker-backed Ubuntu smoke for golden VM bake/init"
	@echo "  make golden-vm-qemu-smoke Real QEMU/KVM Ubuntu VM smoke for golden image clone/init"
	@echo "  make fde-vm-image     Produce dist/images/nadia-fde-ubuntu-22.04.qcow2"
	@echo "  make update-smoke     Docker update-smoke (IU-AC-9/10/11; M5.3 Part A)"
	@echo "  make update-smoke-telegram  Docker /update mid-flight (IU-AC-6; M5.3 Part B, currently SKIPPED)"
	@echo ""
	@echo "Patch ops:"
	@echo "  make patch-list              List the applied patch series (author/edit with quilt — see AGENTS.md)"

# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------

# Wire the tracked .githooks/ as the repo's hook dir. The pre-commit hook
# enforces "make build + leakage-static before any patches/overlay/tools/rename
# commit" — the executable form of the AGENTS.md build gate. core.hooksPath is
# local git config (not cloned), so this must be run once per checkout.
.PHONY: install-hooks
install-hooks:
	@git config core.hooksPath .githooks
	@chmod +x .githooks/* 2>/dev/null || true
	@echo "✓ pre-commit gate enabled (core.hooksPath=.githooks)"

.PHONY: build
build:
	python tools/build.py

.PHONY: gen-skin
gen-skin:
	npm --prefix tools/skin-gen ci --no-audit
	python tools/gen_nadia_skin.py

.PHONY: clean
clean:
	rm -rf dist/ .sync-workdir/

.PHONY: leakage-static
leakage-static:
	python tools/verify_no_leakage.py dist/nadia/
	# Old fork-brand companion: the Hermes leakage scanner does not know that
	# this fork used to ship as Argo. Keep built Nadia artifacts free of old
	# command names, env vars, paths, and user-facing brand text.
	python tools/verify_no_old_brand.py dist/nadia/
	# Over-rename companion: leakage above catches a stray `hermes` (under-rename);
	# this catches the OPPOSITE failure leakage is blind to — a Nous wire identifier
	# (OAuth client_id, Portal tags, catalog User-Agent) clobbered to nadia-* by the
	# rename, which the Nous backend rejects. A clobbered value leaves no `hermes`
	# to flag, so only this positive gate catches it. Wired here so every caller of
	# `make leakage-static` (ci/release/deploy-docs/pre-commit/release script) gets it.
	python tools/check_wire_identifiers.py dist/nadia/
	# China-in-docs companion: the strip removes China platform CODE + leaf doc pages,
	# but shared docs (landing, messaging hub, env/tool/toolset tables, mermaid, setup
	# links) used to keep enumerating/dead-linking them. This gate fails the build if a
	# stripped China messaging platform is still referenced in the shipped docs, so
	# docs.nadicode.ai/nadia can never again ship features the product does not have.
	python tools/check_no_china_in_docs.py dist/nadia/website/

# -----------------------------------------------------------------------------
# Sync workflow
# -----------------------------------------------------------------------------

.PHONY: sync sync-resume sync-reset
sync:
	python tools/sync.py

sync-resume:
	python tools/sync.py --resume

sync-reset:
	python tools/sync.py --reset

# -----------------------------------------------------------------------------
# Docker
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
# (where the `dist/nadia/` tree-hash is the artifact); the full variant
# fetches chromium + s6-overlay + npm tarballs at build time and is
# best-effort by design (spec § Build Reproducibility).
.PHONY: image
image:
	docker buildx build \
		--build-arg SOURCE_DATE_EPOCH=$$(git log -1 --format=%ct) \
		--platform linux/amd64 \
		--target runtime-slim \
		--load \
		-t ghcr.io/nadicodeai/nadia:dev \
		.

.PHONY: image-full
image-full:
	docker buildx build \
		--build-arg SOURCE_DATE_EPOCH=$$(git log -1 --format=%ct) \
		--platform linux/amd64 \
		--target runtime-full \
		--load \
		-t ghcr.io/nadicodeai/nadia:dev-full \
		.

.PHONY: fde-container
fde-container:
	docker buildx build \
		--build-arg SOURCE_DATE_EPOCH=$$(git log -1 --format=%ct) \
		--platform linux/amd64 \
		--target runtime-fde \
		--load \
		-t ghcr.io/nadicodeai/nadia:fde-dev \
		.

.PHONY: publish
publish:
	scripts/publish.sh

# -----------------------------------------------------------------------------
# Quality gates — mirror the `lint (ruff)` and `typecheck (ty)` CI jobs exactly,
# so local `make lint` / `make typecheck` give the same verdict CI does.
# -----------------------------------------------------------------------------

.PHONY: lint
lint:
	ruff check .

.PHONY: typecheck
typecheck:
	ty check overlay/ tools/

.PHONY: test
test:
	pytest -m 'not integration'

# The renamed upstream test suite run against dist/nadia/, EXACTLY as CI's
# `dist-nadia-tests` job does. This is the ONLY gate that exercises dist/nadia
# content changes (packaging-strip.yaml prunes, content_edits, patches, rebrand)
# against the full suite. `make build`, `leakage-static`, and `test` (which runs
# the fork's OWN tests/, not dist/nadia's) do NOT cover it.
#
# CI runs this on `pull_request` + push to `main` only, and it is currently
# *non-blocking* — so a branch pushed and merged straight to `main` (no PR)
# bypasses it entirely. That gap shipped a red main once (China-strip: two
# general tests that import/enumerate the pruned platforms). RUN THIS — or open
# a PR and read the dist-nadia-tests result — BEFORE merging any dist-affecting
# change to main.
#
#   make dist-test                                              # full suite (heavy; provisions a 3.11 venv with [all,dev])
#   make dist-test DIST_TEST_ARGS="--slice 1/6"                 # one CI-equivalent slice
#   make dist-test DIST_TEST_ARGS="--paths tests/a.py:tests/b.py"  # only these files (colon-separated; fast iteration)
.PHONY: dist-test
dist-test: build
	cd dist/nadia && uv venv .venv-test --python 3.11
	cd dist/nadia && uv pip install --quiet --python .venv-test/bin/python -e ".[all,dev]"
	cd dist/nadia && OPENROUTER_API_KEY="" OPENAI_API_KEY="" NOUS_API_KEY="" \
		.venv-test/bin/python scripts/run_tests_parallel.py $(DIST_TEST_ARGS)

.PHONY: check-upstream-pristine
check-upstream-pristine:
	python tools/check_upstream_pristine.py

# Verify the shipped ./Dockerfile has not silently diverged from upstream's
# packaging (the renamed-upstream oracle dist/nadia/Dockerfile). Operates on an
# existing dist/nadia/ tree, like leakage-static — run `make build` first
# (the checker exits 2 with that hint if the oracle is absent).
.PHONY: check-packaging-contract
check-packaging-contract:
	python tools/check_packaging_contract.py

# M5.2: Docker-driven install.sh smoke harness.
#
# Pulls the renamed install.sh from a local release-branch dry run by default
# (use tests/install_smoke/run.sh --live after the public release branch updates),
# runs it in a clean ubuntu:22.04 container, and asserts five invariants
# (.install_method=git, nadia --version exits 0, banner matches hermes regex,
# no "Updating from fork" warning, no ~/.hermes/ leakage). Closes IU-AC-4,
# IU-AC-5, IU-AC-9 (static portion). See tests/install_smoke/run.sh.
.PHONY: install-smoke
install-smoke:
	bash tests/install_smoke/run.sh

.PHONY: golden-vm-smoke
golden-vm-smoke:
	bash tests/golden_vm/run.sh

.PHONY: golden-vm-qemu-smoke
golden-vm-qemu-smoke:
	bash tests/golden_vm/run_qemu.sh

.PHONY: fde-container-smoke
fde-container-smoke:
	bash tests/fde_container/run.sh

.PHONY: fde-live-smoke
fde-live-smoke:
	bash tests/fde_live/run.sh

.PHONY: fde-vm-image
fde-vm-image:
	bash scripts/fde-vm-image.sh

# -----------------------------------------------------------------------------
# Patch operations — author/edit patches with quilt directly (see AGENTS.md
# "Quilt cheatsheet"); make patch-list shows the applied series.
# -----------------------------------------------------------------------------

.PHONY: patch-list

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
# nadia from the public `release` branch, asserts:
#   - no "Updating from fork" warning on `nadia update` (IU-AC-9 full)
#   - `NADIA_MANAGED=1 nadia update` prints "is managed by" on stderr (IU-AC-10;
#     exit code NOT asserted per plan § M5.3 stderr-substring note)
#   - pre_update_backup writes a zip; `nadia import` restores it (IU-AC-11)
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
