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
	@echo "  make image            Build ghcr.io/nadicodeai/argo:dev (M5.1)"
	@echo "  make publish          Push image to ghcr.io (M5.2)"
	@echo ""
	@echo "Quality gates:"
	@echo "  make lint             ruff check (M4.3)"
	@echo "  make typecheck        ty check (M4.3)"
	@echo "  make test             pytest (M4.3)"
	@echo "  make parity           Parity suite vs legacy image (M6)"
	@echo "  make check-legacy-untouched  Verify ~/Code/argo-agent untouched (M2.4a)"
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

.PHONY: sync
sync:
	@echo "make sync: not yet implemented (M4.2)"
	@exit 1

.PHONY: sync-resume
sync-resume:
	@echo "make sync-resume: not yet implemented (M4.2)"
	@exit 1

.PHONY: sync-reset
sync-reset:
	rm -rf .sync-workdir/

# -----------------------------------------------------------------------------
# Docker (M5 wires the real implementation)
# -----------------------------------------------------------------------------

.PHONY: image
image:
	@echo "make image: not yet implemented (M5.1)"
	@exit 1

.PHONY: publish
publish:
	@echo "make publish: not yet implemented (M5.2)"
	@exit 1

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
parity:
	@echo "make parity: not yet implemented (M6.2)"
	@exit 1

.PHONY: check-legacy-untouched
check-legacy-untouched:
	@if [ -x tools/check_legacy_untouched.sh ]; then \
		tools/check_legacy_untouched.sh; \
	else \
		echo "tools/check_legacy_untouched.sh not yet implemented (M2.4a)"; \
		exit 1; \
	fi

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
# Bootstrap (M1)
# -----------------------------------------------------------------------------

.PHONY: bootstrap
bootstrap:
	@if [ -d upstream ]; then \
		echo "upstream/ already exists; refusing to re-bootstrap"; \
		exit 1; \
	fi
	@echo "make bootstrap: see plan M1.2 — git subtree add --prefix=upstream …"
