# Progress

Living log of milestone progress. Append-only timeline; do not rewrite history. Each milestone's section starts pending, moves to in-progress on first task touch, and is marked complete only when its checkpoint passes (per `.shepherd/plan.md`).

**Plan tasks:** 39 across 8 milestones. See `.shepherd/plan.md` for the full task list with acceptance criteria.

---

## Status overview

| Milestone | Status | Tasks | Notes |
|---|---|---|---|
| M1 Bootstrap | complete | 9 / 9 | M1 closed @ 8ba174d (make build green, 2593 files renamed) |
| M2 Audit & validate baseline | complete | 5 / 5 | M2 closed @ 16cb79a (all gates green) |
| M3 Initial patch series | pending | 0 / 9 | next |
| M2 Audit & validate baseline | pending | 0 / 5 | — |
| M3 Initial patch series | pending | 0 / 9 | — |
| M4 CI gates | pending | 0 / 5 | — |
| M5 Docker pipeline | pending | 0 / 3 | — |
| M6 Parity suite | pending | 0 / 3 | — |
| M7 First real sync | pending | 0 / 2 | — |
| M8 Documentation freeze | pending | 0 / 3 | — |

Status values: `pending` · `in-progress` · `blocked` · `complete`.

---

## Milestone log

### M1 Bootstrap

**Goal:** Repo skeleton + upstream subtree + engine lift + minimal build orchestrator. `make build` against an empty patch series produces a clean `dist/argo/`.

**Tasks:**
- [x] M1.1 Create repo skeleton — commit `f3c39ea` 2026-05-27
- [x] M1.2 Add upstream subtree at pinned SHA `a890389b…` — commit `d6f27aa` 2026-05-27
- [x] M1.3 Lift rename engine via `tools/scripts/lift_engine.py` — commit `61bbfd1` 2026-05-27
- [x] M1.4 Lift argo-rename.yaml verbatim — bundled in `128eea2` 2026-05-27
- [x] M1.5 Lift overlay test assets + recorded_model fixtures — bundled in `128eea2` 2026-05-27
- [x] M1.6 doctor_leakage.py + new argo_update.py stub (OQ-6) — bundled in `128eea2` 2026-05-27
- [x] M1.7 tools/rebrand.py (sys.path injection avoids cold-start) — commit `8ba174d` 2026-05-27
- [x] M1.8 tools/build.py (full FR-4 pipeline; honors SOURCE_DATE_EPOCH) — commit `8ba174d` 2026-05-27
- [x] M1.9 Makefile (full surface; scaffolded in M1.1, wired in M1.8) — commit `f3c39ea` 2026-05-27

**Checkpoint:** `make build` produces `dist/argo/` ≈ upstream size ± 5%; `git status` clean; layout matches spec § Project Structure.

**Checkpoint status: PASSED 2026-05-27.**
- `dist/argo/` size: 86M (upstream/: 86M) — within ±5%.
- 2593 files renamed by engine; idempotent on second build (0 files touched).
- 17 overlay files added without collision.
- 103 residual `hermes` hits in `dist/argo/` — pending M2.2 verification against `argo-rename.yaml` exceptions/skip_contexts.
- Layout matches spec § Project Structure.

**Maps to spec:** AC-1 (bootstrap), AC-5 (rename idempotency — partial; full verification requires M5.3 + SOURCE_DATE_EPOCH).

**Notes:**
- M1.3 textual rewrite preserved lowercase `argo_sync` only; `ArgoSyncError` and other CamelCase class names retained as-is. The rename engine treats them as already-final TO-names at build time. Round-trip diff vs legacy is bit-identical.
- M1.8 initially set `--no-manifest` on the rebrand subprocess, which dropped the file-list. Fixed in-loop: build.py now reads the engine's sync-manifest.json to populate `files_touched_by_rename` in the build-manifest.
- M1.9 Makefile was written ahead of schedule in M1.1 to make the target surface visible from day one; `make build` no-op stubs print clear "not yet implemented" messages where targets aren't wired (sync, image, publish, lint, typecheck, parity).

---

### M2 Audit & validate baseline

**Goal:** Rename config audited for new layout; leakage scanner working; sync fixtures recorded; legacy baseline hash captured.

**Tasks:**
- [x] M2.1 Audit `argo-rename.yaml`: dropped 5 orphan exceptions, updated URL mapping → `nadicodeai/argo` — commit `65ef804` 2026-05-27
- [x] M2.2 `tools/verify_no_leakage.py` + leakage_positive/negative/stylized fixtures + 3 pytest tests pass — commit `3fd4fca` 2026-05-27
- [x] M2.3 mode preservation: 56 executables checked, 0 mismatches — commit `7935f01` 2026-05-27
- [x] M2.4a `tools/check_legacy_untouched.sh` + recorded baseline `b8e58957…` for legacy HEAD `9b8cf6bf5` — commit `9c93c1f` 2026-05-27
- [x] M2.4 `sync-fixture-200/` recorded: 25 MB tarball + 763 KB forward-delta patch + 157-file diff — commit `16cb79a` 2026-05-27

**Checkpoint status: PASSED 2026-05-27.**
- `make build && make leakage-static` both exit 0.
- Positive/negative/stylized fixtures all classified correctly.
- Mode preservation: 56/56 OK.
- argo-rename.yaml audited: 0 orphan exceptions; URL mapping = `nadicodeai/argo`.
- Legacy baseline recorded; `make check-legacy-untouched` exits 0 (== expected HEAD `9b8cf6bf5`).
- sync-fixture-200 baseline + forward delta recorded; 157 ≥ 100 (G1 threshold satisfied).

**Maps to spec:** AC-1 (bootstrap), AC-5 (rename idempotency), AC-6 (zero-leakage), G5 (legacy baseline anchor); AC-2 testable from M4.2 once `tools/sync.py` consumes the fixture.

**Notes:**
- M2.2 negative-fixture initially failed because docstring lines outside URL context legitimately contained `hermes` and the scanner correctly flagged them. Fixed by ensuring every fixture `hermes` is inside a URL or 40-hex sha (scanner discipline reinforced — no escape hatch for "comments are fine").
- M2.4 baseline=`b6ca56f6` is HEAD~50 from our pin `a890389b…`. 157-file delta hits the G1 ≥100 threshold without going overboard (200-commit walk produces 940-file diffs — unnecessarily large).
- 25 MB tarball is direct-committed (not Git LFS) — defensible at this scale; revisit if it causes CI clone-time pain.

---

### M3 Initial patch series

**Goal:** Extract 8 fork patches from legacy as quilt patches against pristine upstream. Each patch has assertions where load-bearing.

**Tasks:**
- [ ] M3.1 Write `tools/run_assertions.py` (FR-14 enforcer) + wire into `tools/build.py`
- [ ] M3.2 Patch 0001 — fork-notice README
- [ ] M3.3 Patch 0002 — rebrand URLs (audit first; may be skipped)
- [ ] M3.4 Patch 0003 — gate PyPI publish workflow
- [ ] M3.5 Patch 0004 — gate Vercel/docs deploy
- [ ] M3.6 Patch 0005 — Docker publish to `ghcr.io/nadicodeai/argo` (new image name)
- [ ] M3.7 Patch 0006 — gitleaks allowlist
- [ ] M3.8 Patch 0007 — browser-test skip gate
- [ ] M3.9 Patch 0008 — pyproject.toml rename targets (defer if not needed)

**Checkpoint:** Patches applied (or skipped with documented rationale). `make build && make leakage-static` exit 0. All FR-14 assertions pass.

**Maps to spec:** AC-12 (assertion failure mode — tested via M3.1 negative fixture).

**Notes:**
- (none yet)

---

### M4 CI gates

**Goal:** All CI jobs in place — lint, typecheck, build, test, leakage, parity (placeholder), upstream-pristine. Sync implementation + fixture-driven tests.

**Tasks:**
- [ ] M4.1 Write `tools/check_upstream_pristine.py`
- [ ] M4.2 Implement `tools/sync.py` + wire `make sync` / `make sync-resume` / `make sync-reset` (uses `--upstream-url` flag for fixture-driven tests)
- [ ] M4.2a Add `tests/fixtures/sync-fixture-ac3/` + AC-3 test (non-overlapping upstream refactor)
- [ ] M4.3 Write `.github/workflows/ci.yml`
- [ ] M4.4 Write `.github/workflows/sync.yml` (weekly cron + PR creation)

**Checkpoint:** All CI jobs pass on a clean repo; `upstream-pristine` catches injected drift; per-patch assertions catch injected fork-line drop; sync fixture test passes; weekly sync workflow runs manually with no-op result.

**Maps to spec:** AC-2, AC-3, AC-4, AC-9, AC-10, AC-11.

**Notes:**
- (none yet)

---

### M5 Docker pipeline

**Goal:** Multi-stage Dockerfile; `make image` builds locally; `make publish` pushes to ghcr; `dist/argo/` is deterministic.

**Tasks:**
- [ ] M5.1 Write multi-stage `Dockerfile` (strip `argo_sync/` from final image per OQ-10)
- [ ] M5.2 Write `scripts/publish.sh` and `make publish` + `.github/workflows/docker-publish.yml`
- [ ] M5.3 Verify `dist/` determinism (AC-8)

**Checkpoint:** Docker image builds locally + in CI; image published to ghcr at `:dev` from local run; `dist/argo/` bit-identical across two builds with `SOURCE_DATE_EPOCH` set; image size within 5% of legacy.

**Maps to spec:** AC-8; G2; G3 (partial — image surface).

**Notes:**
- (none yet)

---

### M6 Parity suite

**Goal:** `make parity` drives the new image and legacy `ghcr.io/nadicodeai/argo-agent:0.14.0` through 7 surfaces; diffs are empty modulo brand-string substitution.

**Tasks:**
- [ ] M6.1 Pull legacy baseline image and verify it runs
- [ ] M6.2a Write `tools/parity_runner.py` for CLI surfaces (`--help`, `--version`, `argo doctor --static`)
- [ ] M6.2b Extend parity runner for backend surfaces (API server, MCP, hooks, OAuth, session persistence) with fixtures/stubs

**Checkpoint:** All 7 parity surfaces pass with zero non-brand diffs. Any deferred surfaces explicitly listed with rationale.

**Maps to spec:** AC-7; G3.

**Notes:**
- (none yet)

---

### M7 First real sync

**Goal:** Run `make sync` against current upstream HEAD on a real ≥100-file delta. Tag a v0.1.0 release.

**Tasks:**
- [ ] M7.1 Run `make sync` against current upstream HEAD (record wall-clock; ≥100-file delta precondition; assert ≤5 min)
- [ ] M7.2 Tag a first release (v0.1.0)

**Checkpoint:** First real sync against upstream HEAD succeeded with measured ≤5 min wall-clock; first release tagged and image published; G1, G2, G3, G4 gates all green.

**Maps to spec:** G1; G2 (re-verified); G3 (re-verified); G4 (re-verified).

**Notes:**
- (none yet)

---

### M8 Documentation freeze

**Goal:** Finalize `AGENTS.md`, `README.md`, `.shepherd/standards.md` (this file). Validate G6 onboarding.

**Tasks:**
- [ ] M8.1 Finalize `AGENTS.md` (≤200 lines)
- [ ] M8.2 Finalize `README.md`
- [ ] M8.3 Finalize `.shepherd/standards.md`

**Checkpoint:** All docs finalized. G6 onboarding gate validated (self-audit or peer walkthrough — a fresh engineer or fresh re-read completes `make sync` within 30 min using only AGENTS.md + spec.md).

**Maps to spec:** G6.

**Notes:**
- (none yet)

---

## Decision log

Append entries here whenever a non-obvious decision is made during execution. Keep entries brief; link back to the task that produced them.

| Date | Task | Decision | Rationale |
|---|---|---|---|
| 2026-05-27 | (spec) | Use `git subtree --squash` for upstream | OQ-1 resolved; small repo, no blame into upstream |
| 2026-05-27 | (spec) | Use `quilt` (not StGit) | OQ-2 resolved; text-format, portable |
| 2026-05-27 | (spec) | Image name `argo` (not `argo-agent`) | User confirmed |
| 2026-05-27 | (spec) | Distribution: Docker only, no PyPI | FR-11; user confirmed |
| 2026-05-27 | (spec) | Patch format: `diff -up --git` | OQ-8; M2 reviewer fix |
| 2026-05-27 | (spec) | Determinism gate is `dist/argo/` tree, not Docker layers | C2 reviewer fix |
| 2026-05-27 | (spec) | Overlay uses **hermes**-named paths; engine renames overlay too | C1 reviewer fix |
| 2026-05-27 | (spec) | `argo update` in container is a no-op stub | OQ-6 resolved |
| 2026-05-27 | (spec) | Strip `argo_sync/` from final image | OQ-10 resolved |
| 2026-05-27 | (plan) | `tools/rebrand.py` imports engine from `overlay/` via `sys.path.insert` | M1 reviewer fix; avoids cold-start chicken-and-egg |
| 2026-05-27 | (plan) | Lift engine with `argo_sync → hermes_sync` textual rewrite at lift time | Plan editor round 1 |
| 2026-05-27 | (plan) | Implement `tools/sync.py` as M4.2 (had been missing) | Plan editor round 2 |
| 2026-05-27 | (plan) | Sync fixture is baseline-tree + forward-delta patch | Plan editor round 3 |
| 2026-05-27 | (plan) | Record `.shepherd/legacy-baseline.sha256` in M2.4a | Plan editor round 3 |
| 2026-05-27 | (plan) | G1 measurement: ≥100-file delta precondition + record wall-clock | Plan editor round 3 |

---

## Blockers

(none yet)

---

## Risks materialized

(none yet — risk realization log; reference spec § Risks for the pre-execution risk table)

---

## Cold-pickup checklist (for autonomous phase 2)

A new session picking up this work should, in order:

1. Read `.shepherd/spec.md` (what we're building).
2. Read `.shepherd/plan.md` (next ordered task).
3. Read this file (`.shepherd/progress.md`) for the current state.
4. Read `.shepherd/standards.md` (conventions).
5. Identify the next unchecked `[ ]` task in this file's Milestone log; that's the work to do.
6. Honor the dependency declarations on each plan task before starting.
7. After completing a task: mark `[x]` here, append a Notes bullet with relevant verification output, and append a Decision-log row only if a non-obvious choice was made.
8. After completing a milestone's checkpoint: change its Status to `complete` in the status overview table.
9. Never proceed past a failing acceptance gate — record the failure in Blockers and stop.

This file IS the autonomous loop's progress contract. Keep it accurate.
