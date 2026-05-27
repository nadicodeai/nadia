# Implementation Plan: argo — pristine-upstream fork of hermes-agent

**Spec:** `/home/vadim/Code/argo/.shepherd/spec.md` (v2, 558 lines, post opus review)
**Repo:** `/home/vadim/Code/argo` (greenfield; `git init -b main` done; otherwise empty)
**Legacy reference:** `/home/vadim/Code/argo-agent` (frozen, untouched — G5)
**Target:** Docker image `ghcr.io/nadicodeai/argo:latest`

---

## Overview

Build a new fork of `hermes-agent` that keeps tracked source pristine, expresses fork additions as a quilt patch series + an overlay directory, and rebrands at build time via the rename engine lifted from the legacy repo. The output is a Docker image published to GHCR; there is no PyPI artifact. Maintainer-facing upstream sync is `make sync` (≤2 min on a typical delta). The plan is sequenced bottom-up: dependencies (engine, rename config, build pipeline) before fork-specific content (patches, CI, parity), so each phase leaves a working artifact you can demo.

---

## Architecture Decisions (locked from spec v2)

- **Overlay paths mirror upstream** (overlay uses `hermes_*` directory names). The rename engine processes overlay and upstream uniformly when producing `dist/argo/`. (C1.)
- **Patch format is `diff -up --git`.** Captures binary files, mode bits, renames. Plain `diff -u` is insufficient. (M2.)
- **Sync conflict workdir is `.sync-workdir/`, not `dist/`.** `dist/` is regenerated on every build; would clobber manual edits. (M6.)
- **`tools/rebrand.py` imports the engine from `overlay/hermes_sync/`** via `sys.path.insert(0, "overlay")`. Not from `dist/`. Avoids the cold-start chicken-and-egg. (M1.)
- **Determinism gate is `dist/argo/` tree-hash + `argo --version --verbose`**, not Docker layer hashes. Docker reproducibility is best-effort. (C2.)
- **CI rejects any PR that touches `upstream/`** outside `make sync` automation. (C3.)
- **Per-patch grep assertions** in `patches/asserts/<patch>.txt` catch silent `quilt refresh` data loss. (M5/FR-14.)
- **Functional parity suite** (FR-16) is the customer-regression gate, not a single smoke chat.

---

## Dependency Graph

```
M1 Bootstrap (skeleton, subtree, engine lift, scaffolds)
    │
    └── M2 Audit & validate baseline (rename-config audit, leakage scan, fixtures incl. sync-fixture-200)
            │
            ├── M3 Initial patch series (extract 8 patches + assertions)
            │       │
            │       └── M5 Docker pipeline (Dockerfile, make image, GHCR push)
            │               │
            │               └── M6 Parity suite (M6.2a CLI surfaces, M6.2b backend surfaces)
            │
            ├── M4 CI gates (upstream-pristine, sync impl, ci.yml, sync.yml)
            │
            └── M7 First real sync (run against current upstream HEAD; tag)
                    │
                    └── M8 Docs freeze (AGENTS, README, standards, onboarding validation)
```

Phases M3 and M4 are partially independent (CI can scaffold before all patches exist); M5/M6 require M3. M4 includes the `tools/sync.py` implementation — `make sync` is a no-op stub from M1.9 until M4.2 makes it functional. M7 is sequenced after M4+M5 so the first real sync runs through the full pipeline. M8 last so docs reflect what was built.

---

## Phase M1 — Bootstrap (foundation)

### Task M1.1: Create repo skeleton

**Description:** Establish the top-level directory structure with empty/scaffold files for everything the build pipeline expects to find. No logic yet. Includes initial `.shepherd/standards.md` stub (finalized in M8.3) so the standards file the spec references exists from day one.

**Acceptance criteria:**
- [ ] Directories exist: `.shepherd/`, `patches/`, `patches/asserts/`, `overlay/`, `overlay/tests/`, `overlay/tests/fixtures/`, `tools/`, `scripts/`, `.github/workflows/`, `tests/fixtures/`.
- [ ] Files exist (empty or minimal): `patches/series`, `patches/asserts/manifest.txt`, `.gitignore`, `.gitattributes`, `Makefile`, `README.md`, `AGENTS.md`, `.shepherd/standards.md` (stub: heading + "Inherited from upstream. Finalized in M8.3.").
- [ ] `.gitignore` excludes `dist/`, `.sync-workdir/`, `.quilt/`, `*.rej`, `*.orig`, `__pycache__/`, `.venv/`, `*.pyc`.
- [ ] `.gitattributes` contains `upstream/* linguist-vendored=true` and `* text=auto eol=lf`.

**Verification:**
- [ ] `tree -L 2 -a /home/vadim/Code/argo` shows the layout from spec § Project Structure.
- [ ] `git status` is clean after `git add . && git commit -m "M1.1: skeleton"`.

**Dependencies:** None.

**Files likely touched:** `.gitignore`, `.gitattributes`, `Makefile`, `README.md`, `AGENTS.md`, `.shepherd/standards.md`, empty placeholder files.

**Scope:** S (1-2 files of content; rest are empty).

---

### Task M1.2: Add upstream subtree at pinned SHA

**Description:** Pull hermes-agent's `main` HEAD as a `git subtree --squash` into `upstream/`. Record the pinned SHA in `upstream/.commit`.

**Acceptance criteria:**
- [ ] `upstream/` directory contains pristine hermes-agent content (e.g., `upstream/hermes_agent/`, `upstream/hermes_cli/`, `upstream/pyproject.toml`).
- [ ] `upstream/.commit` is a single-line UTF-8 file containing the upstream `main` HEAD SHA (40 hex chars).
- [ ] The subtree squash commit message follows the form `M1.2: bootstrap upstream subtree at hermes-agent@<short-sha>`.

**Verification:**
- [ ] `git log --oneline -1 upstream/` shows the squash merge commit.
- [ ] `cat upstream/.commit | head -c 8` matches the short SHA in the commit message.
- [ ] `git ls-tree HEAD upstream/ | wc -l` ≥ 50 (sanity: enough top-level entries to indicate full content).

**Dependencies:** M1.1.

**Files likely touched:** `upstream/` (entire), `upstream/.commit`.

**Scope:** S (one git subtree command + one file write).

---

### Task M1.3: Lift rename engine to overlay

**Description:** Copy the rename engine from legacy `~/Code/argo-agent/argo_sync/` to `overlay/hermes_sync/`. The legacy engine's source code references its own package as `argo_sync` (in absolute imports, docstrings, dunders) — these MUST be rewritten to `hermes_sync` during lift so the engine is importable from the new overlay path BEFORE any build exists. The build-time rename pass then maps `hermes_sync → argo_sync` (via the bare `hermes → argo` mapping in `argo-rename.yaml`) when running against `dist/argo/`, restoring the engine's original `argo_sync` package name in the shipped tree.

This is a one-shot textual rewrite at lift time: `argo_sync` → `hermes_sync` across all `.py` files in the engine. Performed by `tools/scripts/lift_engine.py` (a one-off lift script committed alongside the engine). The engine is otherwise byte-for-byte identical to legacy.

**Acceptance criteria:**
- [ ] `overlay/hermes_sync/` exists with `__init__.py`, `config.py`, `engine.py`, `errors.py`, `manifest.py`, `passes/`.
- [ ] Every `argo_sync` token in the engine's source has been rewritten to `hermes_sync` (absolute imports, docstrings, sphinx cross-refs, exception class qualifiers). Verified: `grep -rn 'argo_sync' overlay/hermes_sync/` returns zero hits.
- [ ] `python -c "import sys; sys.path.insert(0, 'overlay'); from hermes_sync.engine import RenameEngine; print(RenameEngine)"` succeeds and prints the class repr.
- [ ] Aside from the `argo_sync → hermes_sync` rewrite, the engine code is byte-for-byte identical to legacy (verified by re-applying the inverse rewrite and `diff`-ing against legacy).
- [ ] `tools/scripts/lift_engine.py` is committed: takes a source dir + target dir, performs the textual rewrite, prints touched files.

**Verification:**
- [ ] Inverse-rewrite check: `python tools/scripts/lift_engine.py --reverse overlay/hermes_sync/ /tmp/engine-roundtrip/ && diff -r /tmp/engine-roundtrip/ /home/vadim/Code/argo-agent/argo_sync/` is empty.
- [ ] Import test above passes.
- [ ] After full M1.8 build: `grep -rn 'hermes_sync' dist/argo/argo_sync/` returns zero hits (engine package renamed back to `argo_sync` in built tree).

**Dependencies:** M1.1.

**Files likely touched:** `overlay/hermes_sync/**`, `tools/scripts/lift_engine.py`.

**Scope:** S (mechanical rewrite + tiny lift script).

**Why this approach:** The legacy engine uses absolute imports `from argo_sync.config import RenameConfig`. If those imports are left as `argo_sync.*` while the package directory is renamed to `hermes_sync/`, the engine cannot be imported under the new path — `argo_sync` doesn't exist on `sys.path`. Symmetric approach: lift rewrites `argo_sync → hermes_sync` once at bootstrap; the build-time rename pass undoes it (`hermes_sync → argo_sync`) when producing `dist/argo/`. The lift is reproducible (one-off script) and the round-trip is verifiable.

---

### Task M1.4: Lift argo-rename.yaml verbatim

**Description:** Copy `argo-rename.yaml` from legacy. Do NOT edit yet — audit happens in M2.1.

**Acceptance criteria:**
- [ ] `argo-rename.yaml` at repo root, byte-identical to `~/Code/argo-agent/argo-rename.yaml`.
- [ ] `python -c "import yaml; yaml.safe_load(open('argo-rename.yaml', encoding='utf-8'))"` parses without error.

**Verification:**
- [ ] `diff argo-rename.yaml /home/vadim/Code/argo-agent/argo-rename.yaml` is empty.

**Dependencies:** M1.1.

**Files likely touched:** `argo-rename.yaml`.

**Scope:** XS.

---

### Task M1.5: Lift overlay test assets and fixtures

**Description:** Copy test files and fixtures from legacy into `overlay/tests/`, preserving hermes-named paths where they exist. Specifically: `test_full_rename_config.py`, `test_deployment_smoke.py`, `test_cmd_argo_doctor.py`, and the `recorded_model/` fixtures.

**Acceptance criteria:**
- [ ] `overlay/tests/test_full_rename_config.py` exists.
- [ ] `overlay/tests/test_deployment_smoke.py` exists.
- [ ] `overlay/tests/test_cmd_argo_doctor.py` exists.
- [ ] `overlay/tests/fixtures/recorded_model/server.py` exists.
- [ ] Each file is byte-identical to its legacy counterpart.

**Verification:**
- [ ] `diff overlay/tests/test_full_rename_config.py /home/vadim/Code/argo-agent/tests/test_full_rename_config.py` empty.
- [ ] Same for the other 3 files + 1 fixture.

**Dependencies:** M1.1.

**Files likely touched:** `overlay/tests/**`.

**Scope:** S.

---

### Task M1.6: Lift overlay CLI shims

**Description:** Copy `argo_cli/doctor_leakage.py` (legacy) → `overlay/hermes_cli/doctor_leakage.py`. Write a fresh `overlay/hermes_cli/argo_update.py` as a no-op stub that prints the docker-pull instruction (OQ-6 resolution).

**Acceptance criteria:**
- [ ] `overlay/hermes_cli/doctor_leakage.py` byte-identical to legacy `argo_cli/doctor_leakage.py`.
- [ ] `overlay/hermes_cli/argo_update.py` exists; running it prints `Use docker pull ghcr.io/nadicodeai/argo:latest` and exits 0.
- [ ] Both files use `from __future__ import annotations` and `encoding="utf-8"` on any I/O.

**Verification:**
- [ ] `python overlay/hermes_cli/argo_update.py` prints expected output, exits 0.
- [ ] `diff overlay/hermes_cli/doctor_leakage.py /home/vadim/Code/argo-agent/argo_cli/doctor_leakage.py` empty.

**Dependencies:** M1.1.

**Files likely touched:** `overlay/hermes_cli/doctor_leakage.py`, `overlay/hermes_cli/argo_update.py`.

**Scope:** S.

---

### Task M1.7: Write `tools/rebrand.py`

**Description:** Build the entrypoint script that imports the engine from `overlay/hermes_sync/` and runs it against a target directory. Pure-Python, single CLI: `python tools/rebrand.py <target-dir>`.

**Acceptance criteria:**
- [ ] `tools/rebrand.py` parses `argv[1]` as a target directory.
- [ ] Inserts `overlay/` into `sys.path` BEFORE importing the engine (M1 fix).
- [ ] Loads `argo-rename.yaml` from the script's repo root.
- [ ] Runs the engine's full pass sequence (content → filenames → directories).
- [ ] Exits 0 on success, non-zero on any engine error.
- [ ] Re-running against an already-renamed directory produces zero diffs (idempotency check).

**Verification:**
- [ ] Manual: `cp -r upstream/ /tmp/test-rebrand/ && python tools/rebrand.py /tmp/test-rebrand/` exits 0 and `grep -ri hermes /tmp/test-rebrand/ | wc -l` is dramatically lower than `grep -ri hermes upstream/ | wc -l`.
- [ ] Idempotency: re-run yields no diffs.
- [ ] `rm -rf /tmp/test-rebrand/` (cleanup).

**Dependencies:** M1.3, M1.4.

**Files likely touched:** `tools/rebrand.py`.

**Scope:** S.

---

### Task M1.8: Write `tools/build.py`

**Description:** The build orchestrator per spec FR-4. Pure-Python script: clean `dist/argo/`, copy `upstream/*`, `quilt push -a`, copy `overlay/*` (fail on collision), run `tools/rebrand.py`, run FR-14 assertions, write build manifest.

**Acceptance criteria:**
- [ ] `python tools/build.py` runs end-to-end on an empty patch series and produces `dist/argo/` containing renamed upstream + overlay content.
- [ ] On overlay path collision with upstream (post-patch), exits non-zero with the colliding path.
- [ ] `dist/argo/.argo/build-manifest.json` exists with keys: `upstream_sha`, `patches_applied`, `overlay_files_added`, `files_touched_by_rename`, `assertions_checked`, `ran_at`. JSON is `sort_keys=True, indent=2`.
- [ ] Preserves file modes (executable bits on scripts; verified by a fixture file).
- [ ] All file I/O uses `encoding="utf-8"`.

**Verification:**
- [ ] `python tools/build.py && ls dist/argo/.argo/build-manifest.json` exits 0.
- [ ] `grep -ri hermes dist/argo/ | grep -v argo-rename.yaml` returns nothing outside the documented exception set (validated by M2.2 leakage scan).
- [ ] `python tools/build.py && python tools/build.py` (twice in a row) produces the same `dist/argo/` tree (manifest's `ran_at` differs but `files_touched_by_rename` is stable).

**Dependencies:** M1.7. (Audit M2.1 runs AGAINST the first build's output, so M1.8 ships before M2.1.)

**Files likely touched:** `tools/build.py`.

**Scope:** M (3-5 logical steps; ~150-250 LOC).

**Note on assertion runner:** FR-4 step 6 (per-patch assertions) is implemented in M3.1's `tools/run_assertions.py`. M1.8 ships `tools/build.py` WITHOUT the assertion step; M3.1 wires it in. Until then `dist/argo/.argo/build-manifest.json` records `"assertions_checked": []`.

---

### Task M1.9: Write minimal `Makefile`

**Description:** Initial Makefile with bootstrap, build, clean targets. Other targets (sync, image, publish, parity, etc.) are scaffolded as `@echo "not yet implemented"` and filled in later phases.

**Acceptance criteria:**
- [ ] `make bootstrap` is documented but not required to be runnable until M1 is complete (chicken-and-egg).
- [ ] `make build` invokes `python tools/build.py`.
- [ ] `make clean` removes `dist/` and `.sync-workdir/`.
- [ ] `make leakage-static`, `make sync`, `make sync-resume`, `make sync-reset`, `make image`, `make publish`, `make lint`, `make typecheck`, `make test`, `make parity`, `make patch-new`, `make patch-refresh`, `make patch-list` all exist as targets (some as no-op stubs for now).
- [ ] `make help` prints a summary of available targets.

**Verification:**
- [ ] `make build` exits 0 and produces `dist/argo/`.
- [ ] `make clean && ls dist 2>&1 | grep -q "No such"` confirms cleanup.
- [ ] `make help` shows all targets listed above.

**Dependencies:** M1.8.

**Files likely touched:** `Makefile`.

**Scope:** S.

---

### Checkpoint: M1 complete

- [ ] `make build` produces a `dist/argo/` whose tree size is ≈ `upstream/` size ± 5%.
- [ ] `grep -i hermes dist/argo/ -r | wc -l` is dramatically lower than upstream (a smoke check; M2 makes it formal).
- [ ] `git status` is clean; the bootstrap commit (M1.2) and follow-up commits (M1.3–M1.9) are on `main`.
- [ ] Human review: confirm the engine ran end-to-end and the layout matches spec § Project Structure.

**Maps to spec AC-1** (bootstrap), AC-5 (rename idempotency — partial verification).

---

## Phase M2 — Audit & validate baseline

### Task M2.1: Audit `argo-rename.yaml` for new layout

**Description:** Three concurrent edits to the lifted `argo-rename.yaml`:

1. **Update URL/repo mappings for the new fork name.** The legacy mapping is `NousResearch/hermes-agent → nadicodeai/argo-agent` (legacy repo was `argo-agent`). The new fork is `nadicodeai/argo`. Change the mapping accordingly. Also reconfirm `hermes-agent → argo-agent` vs `hermes-agent → argo`: the legacy collapsed the package name to `argo-agent` to match its repo; the new repo's customer-visible Docker image name is `argo`, but the renamed pyproject project name MAY remain `argo-agent` (verify against legacy `pyproject.toml`). Document the chosen mapping inline.
2. **Audit exceptions.** Walk `exceptions:` entries; remove orphans whose paths no longer match anything under `dist/argo/`; add overlay-internal entries (e.g. `overlay/hermes_sync/passes/_constants.py` may legitimately contain hermes literals as engine constants — but ALSO confirm whether the engine actually walks `passes/_constants.py`: looking at the constants file shows it's `SKIP_DIRS = frozenset({...})` and `apply_mappings` — does it contain `hermes` literals? Verify; if it does, add an exception).
3. **Audit skip_contexts.** Confirm the URL skip regex still excludes our owned domain (none) and includes upstream's docs site host (NousResearch's).

**Acceptance criteria:**
- [ ] URL mapping points at `nadicodeai/argo` (or whatever the M3.6/M5.2 image-name decision lands on); document the decision in a YAML comment.
- [ ] Every `exceptions:` path glob matches at least one file in `dist/argo/` after `make build`. Orphan entries removed.
- [ ] Every removed/added entry has a one-line `why:` comment per spec standards.
- [ ] `python -c "import yaml; yaml.safe_load(open('argo-rename.yaml', encoding='utf-8'))"` still parses.

**Verification:**
- [ ] `tools/audit_rename_config.py` (write this as a one-off) reports zero orphans and zero unjustified additions.
- [ ] `make build` produces `dist/argo/`; `make leakage-static` (once M2.2 lands) reports zero residual leakage hits.

**Dependencies:** M1.8 (need a working build to count files).

**Files likely touched:** `argo-rename.yaml`, `tools/audit_rename_config.py` (new).

**Scope:** S–M (audit can balloon if many orphans exist).

---

### Task M2.2: Write `tools/verify_no_leakage.py` and its fixtures

**Description:** The static leakage scanner per FR-12. Recursively scans `dist/argo/` for case-insensitive `hermes` occurrences; honors `exceptions:` (path globs) and `skip_contexts:` (regex patterns). Naive `grep -i hermes` is forbidden — the scanner MUST be config-aware. This task **also creates the fixture trees** the scanner is tested against (positive, negative, stylized).

**Acceptance criteria:**
- [ ] `python tools/verify_no_leakage.py dist/argo/` exits 0 on a clean build.
- [ ] **Create** `tests/fixtures/leakage_positive/file.py` containing `hermes_thing` outside any exception. Create a tiny per-fixture `rename.yaml` that the scanner can be pointed at. Scanner detects the leak and exits 1.
- [ ] **Create** `tests/fixtures/leakage_negative/argo-rename.yaml` containing `hermes` as a FROM key inside a `skip_contexts:` regex; scanner ignores it and exits 0.
- [ ] **Create** `tests/fixtures/leakage_stylized/file.py` containing `HeRmEs`, `HERMES`, `Hermes` (OQ-16). Scanner detects all three.
- [ ] All I/O uses `encoding="utf-8"`.

**Verification:**
- [ ] All three fixtures exercise the scanner; each passes its expected exit code.
- [ ] `make leakage-static` invokes the scanner and is now functional (not a stub).
- [ ] Run against current `dist/argo/`: zero leakage hits.

**Dependencies:** M1.8, M2.1.

**Files likely touched:** `tools/verify_no_leakage.py`, `tests/fixtures/leakage_positive/**`, `tests/fixtures/leakage_negative/**`, `tests/fixtures/leakage_stylized/**`, `Makefile` (wire leakage-static).

**Scope:** M.

---

### Task M2.3: Test mode preservation across build

**Description:** Verify FR-4 step 2 promise that `cp -r upstream/* dist/argo/` preserves file modes (executable bit). Catch the OQ-17 risk early.

**Acceptance criteria:**
- [ ] Identify an executable file in `upstream/` (e.g., `upstream/scripts/install.sh` or similar; if none exist, add a test fixture under `overlay/tests/fixtures/exec_mode/test.sh` with `0755`).
- [ ] After `make build`, the same file in `dist/argo/` has the executable bit set.
- [ ] Add a one-line CI assertion script `tools/check_modes.sh` for inclusion in CI later.

**Verification:**
- [ ] `stat -c '%a' dist/argo/path/to/exec.sh` reports `755` (or other expected mode).
- [ ] If `tools/build.py` does NOT preserve modes (e.g., `shutil.copy2` was used incorrectly), fix it.

**Dependencies:** M1.8.

**Files likely touched:** `tools/build.py` (maybe), `tools/check_modes.sh`, fixture file.

**Scope:** XS-S.

---

### Task M2.4a: Record legacy-repo baseline hash (AC-10 anchor)

**Description:** Spec AC-10 requires verifying that `~/Code/argo-agent` is untouched throughout development by hashing its tree at session start and end. This task records the start hash NOW and writes it to a versioned file the final-acceptance sweep can compare against.

**Acceptance criteria:**
- [ ] `tools/check_legacy_untouched.sh` exists. Hashes `~/Code/argo-agent` recursively (excluding `.git/`, `__pycache__/`, `.venv/`, build artefacts) via `find … -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum`.
- [ ] `.shepherd/legacy-baseline.sha256` is committed: contains exactly one line — the baseline hash + the legacy repo's current `git log -1 --format=%H` for cross-reference.
- [ ] Running `tools/check_legacy_untouched.sh --verify` reads `.shepherd/legacy-baseline.sha256`, recomputes the current hash, and exits 0 iff they match.
- [ ] `make check-legacy-untouched` wraps the verify mode.

**Verification:**
- [ ] `tools/check_legacy_untouched.sh --verify` exits 0 immediately after recording (sanity round-trip).
- [ ] If a single file under `~/Code/argo-agent` is touched (`touch ~/Code/argo-agent/<some-file>` then revert via `git checkout`), the script catches the touched-mtime-but-same-content case correctly (the hash is content-based, so a mtime-only touch should NOT flip the hash — confirm).

**Dependencies:** None.

**Files likely touched:** `tools/check_legacy_untouched.sh`, `.shepherd/legacy-baseline.sha256`, `Makefile` (target).

**Scope:** XS-S.

**Why now (M2 not M8):** The baseline MUST be recorded before any task that could plausibly touch the legacy repo. M2 is the earliest stable point post-bootstrap.

---

### Task M2.4: Build the `sync-fixture-200/` reproducibility fixture

**Description:** Spec AC-2 requires a pre-recorded sync fixture under `tests/fixtures/sync-fixture-200/` (~200 changed files constructed by replaying upstream's last 20 commits as one patch). Without this fixture AC-2 is unverifiable. Build it as a one-off recording.

**Fixture design (corrected — the patch is forward-direction; the *starting state* is the baseline, NOT current upstream).** `upstream/.commit` is currently at `HEAD-SHA`. The fixture represents a counterfactual prior state SO THAT M4.2's sync test can start at the older baseline and "sync forward" to current `HEAD-SHA`. Concretely:

1. Clone hermes-agent at `HEAD-SHA`; walk back ~20 commits to find a `BASELINE-SHA` whose diff vs. `HEAD-SHA` touches ≥100 files (target ~200).
2. Record two artifacts:
   - **`tests/fixtures/sync-fixture-200/baseline-tree.tar.zst`** — a compressed tarball of the hermes-agent worktree AT `BASELINE-SHA` (so M4.2 can seed `.sync-workdir/`-or-upstream-replica from it). Track via Git LFS if size >10 MB; otherwise commit directly.
   - **`tests/fixtures/sync-fixture-200/upstream-200-files.patch`** — a `git format-patch` style patch (or `git diff BASELINE-SHA HEAD-SHA --` capture) representing the forward delta. Applies cleanly to `baseline-tree/`, not to current `upstream/`.
3. Document both SHAs and the file count in `tests/fixtures/sync-fixture-200/README.md`: `Constructed from hermes-agent BASELINE-SHA..HEAD-SHA on YYYY-MM-DD; <N> files changed (≥100 required).`

**Acceptance criteria:**
- [ ] `tests/fixtures/sync-fixture-200/baseline-tree.tar.zst` exists (or `baseline-tree/` directory, if size permits direct commit).
- [ ] `tests/fixtures/sync-fixture-200/upstream-200-files.patch` exists.
- [ ] `tests/fixtures/sync-fixture-200/README.md` documents both SHAs and the file count; file count is `≥100` (the spec's ≥100-file-delta threshold for G1).
- [ ] Counting `^diff --git` lines in the patch yields the file count documented in README (NOT a hard 200 — record the actual count).
- [ ] Smoke check: extract baseline tarball to `/tmp/u/`, then `git apply --check tests/fixtures/sync-fixture-200/upstream-200-files.patch -p1` (run from `/tmp/u/`) succeeds.

**Verification:**
- [ ] `tar -xf tests/fixtures/sync-fixture-200/baseline-tree.tar.zst -C /tmp/u/ && (cd /tmp/u && git apply --check ../path/to/upstream-200-files.patch)` succeeds (exact path forms in the README).
- [ ] File count assertion: `grep -c '^diff --git' tests/fixtures/sync-fixture-200/upstream-200-files.patch` ≥ 100.

**Dependencies:** M1.2 (need `upstream/.commit` pinned so the HEAD-SHA is known).

**Files likely touched:** `tests/fixtures/sync-fixture-200/**` (baseline tree + patch + README).

**Scope:** S–M (one-time recording; mechanical, but tarball + patch require coordination).

**Why baseline-tree is required:** A patch from `BASELINE→HEAD` cannot apply against `upstream/` (which is already at HEAD). The fixture MUST provide the older starting tree so M4.2's `test_sync_fixture.py` can place the simulated upstream replica at `BASELINE-SHA` before running `make sync`. Without the baseline tree, AC-2 cannot be exercised.

---

### Checkpoint: M2 complete

- [ ] `make build && make leakage-static` exits 0 with empty patch series.
- [ ] Stylized brand-string fixture proves case-insensitive detection works.
- [ ] File modes preserved end-to-end.
- [ ] `argo-rename.yaml` audited; orphans removed; new overlay-specific entries documented; URL mapping updated for new fork.
- [ ] Legacy-untouched baseline recorded (M2.4a) so AC-10 is verifiable at the end.
- [ ] `tests/fixtures/sync-fixture-200/` recorded with baseline-tree + forward-delta patch (M2.4) so AC-2 is testable in M4.2.

**Maps to spec AC-1, AC-5, AC-6, AC-10 (baseline anchor).** (AC-2 testable from M4.2 once `make sync` is implemented and the sync-fixture test wires the fixture into the pipeline.)

---

## Phase M3 — Initial patch series

> **Pattern for every patch in M3.x:** (a) create the patch via `quilt new <name>.patch`; (b) `quilt add` the upstream file(s); (c) make the edit; (d) `quilt refresh`; (e) write `patches/asserts/<name>.txt` with grep patterns proving the patch landed; (f) run `make build` and confirm it passes including FR-14 assertions; (g) commit the patch + assertion file.

### Task M3.1: Write `tools/run_assertions.py` (FR-14 enforcer)

**Description:** The per-patch assertion runner. Reads `patches/asserts/<patch-name>.txt` files; each non-comment line is a grep pattern (default: fixed string; `regex:` prefix for regex; `path:` prefix to restrict to a path glob). Runs against `dist/argo/` after rename. Fails the build if any pattern is unsatisfied.

**Acceptance criteria:**
- [ ] Pattern syntax matches spec FR-14 (`path:`, `regex:`, fixed-string default, `#` comments).
- [ ] Returns non-zero on any failed assertion, with the failing patch + pattern named in stderr.
- [ ] Skips patches whose assertion file doesn't exist (assertion is optional per-patch).
- [ ] `tools/build.py` (M1.8) is updated to call `tools/run_assertions.py` as step 6.
- [ ] Positive fixture: an assertion that's satisfied → exit 0. Negative fixture: an assertion deliberately broken → exit 1 with helpful output.

**Verification:**
- [ ] `python tools/run_assertions.py dist/argo/` exits 0 on the current build (no assertions defined yet).
- [ ] Negative fixture passes.

**Dependencies:** M1.8.

**Files likely touched:** `tools/run_assertions.py`, `tools/build.py` (wire in).

**Scope:** S.

---

### Task M3.2: Patch 0001 — fork-notice README

**Description:** Add fork-notice block + attribution badges to `upstream/README.md` per legacy commit `3effed6b7` + `782a7f15b`. Use `quilt new` + `quilt edit` + `quilt refresh`.

**Acceptance criteria:**
- [ ] `patches/0001-fork-notice-readme.patch` exists, format `diff -up --git`.
- [ ] `patches/series` has `0001-fork-notice-readme.patch` as the first (and only) entry.
- [ ] `patches/asserts/0001-fork-notice-readme.txt` contains at least: `Fork of NousResearch/hermes-agent`, `nadicodeai/argo`.
- [ ] `patches/asserts/manifest.txt` lists `0001-fork-notice-readme.patch`.
- [ ] `make build` succeeds; assertions pass; leakage scan passes (the fork-notice URLs are upstream-referencing and covered by `argo-rename.yaml` skip_contexts).

**Verification:**
- [ ] `quilt push -a` from `.sync-workdir/` (or `dist/argo/`) applies the patch cleanly.
- [ ] `make build` exits 0.
- [ ] `grep "Fork of NousResearch" dist/argo/README.md` succeeds.

**Dependencies:** M3.1.

**Files likely touched:** `patches/0001-fork-notice-readme.patch`, `patches/asserts/0001-fork-notice-readme.txt`, `patches/asserts/manifest.txt`, `patches/series`.

**Scope:** S.

---

### Task M3.3: Patch 0002 — rebrand URLs (audit first)

**Description:** Before writing this patch, AUDIT whether it's still needed. The legacy `argo-rename.yaml` (M1.4) now encodes the URL mappings (`NousResearch/hermes-agent → nadicodeai/argo`, etc.). If those mappings cover the URLs in upstream's source, the patch is redundant — skip.

**Acceptance criteria:**
- [ ] Verify by running `make build` and `make leakage-static` after M3.2. If leakage scan reports zero hits and the published URLs in `dist/argo/` already point to `nadicodeai/argo`, this patch is NOT needed → write a note in `patches/series` (commented-out line: `# 0002 SKIPPED: covered by argo-rename.yaml URL mappings (audited 2026-MM-DD)`).
- [ ] If leakage scan finds residual URL issues OR the URLs in `dist/argo/` are wrong (e.g. still `NousResearch/argo-agent` instead of `nadicodeai/argo`), write the patch with assertions verifying the corrected URLs.

**Verification:**
- [ ] Document the audit result inline in `patches/series`.
- [ ] Either the patch is written and `make build` passes, OR the patch is documented as not-needed.

**Dependencies:** M3.2.

**Files likely touched:** `patches/series` (comment), possibly `patches/0002-rebrand-urls-preserve-upstream.patch` and asserts.

**Scope:** S (audit-driven; could be a no-op).

---

### Task M3.4: Patch 0003 — gate PyPI publish workflow

**Description:** Disable the upstream `upload_to_pypi.yml` workflow per legacy commits `8bceb51de` + `8fda451aa` + `b8e6e76a2`. Strategy: gate every job with `if: false` and remove the auto-trigger. (Or: delete the workflow file entirely via patch — simpler and matches FR-11. Prefer delete.)

**Acceptance criteria:**
- [ ] `patches/0003-ci-gate-pypi-publish.patch` exists.
- [ ] After apply, `dist/argo/.github/workflows/upload_to_pypi.yml` either does not exist OR has all jobs gated `if: false` with explanatory comment.
- [ ] Assertion: `path:.github/workflows/`, `regex:^# Nadicode fork:` OR file deletion (assertion: file absent).

**Verification:**
- [ ] `make build` passes; assertions pass.

**Dependencies:** M3.3.

**Files likely touched:** `patches/0003-ci-gate-pypi-publish.patch`, asserts, series.

**Scope:** S.

---

### Task M3.5: Patch 0004 — gate Vercel/docs deploy

**Description:** Disable `deploy-site.yml`, `skills-index.yml`, and any other upstream-Vercel/docs workflows that publish to `hermes-agent.nousresearch.com`. Per legacy commit `ff5ca129c`.

**Acceptance criteria:**
- [ ] `patches/0004-ci-gate-vercel-deploy.patch` deletes or gates the deploy-site and skills-index workflows.
- [ ] Assertions verify the workflows are absent OR `if: false`-gated.

**Verification:**
- [ ] `make build` passes.

**Dependencies:** M3.4.

**Files likely touched:** patch, asserts, series.

**Scope:** S.

---

### Task M3.6: Patch 0005 — Docker publish to ghcr.io/nadicodeai/argo

**Description:** Replace upstream's Docker Hub publish workflow with a ghcr.io publish. The image NAME changes vs the legacy repo: `nadicodeai/argo-agent` → `nadicodeai/argo`. Update the workflow's IMAGE_NAME env var accordingly.

**Acceptance criteria:**
- [ ] `patches/0005-docker-publish-ghcr.patch` modifies `.github/workflows/docker-publish.yml` to use `ghcr.io/nadicodeai/argo` and `secrets.GITHUB_TOKEN` auth.
- [ ] All jobs that pushed to Docker Hub now push to ghcr only.
- [ ] Assertions: `path:.github/workflows/docker-publish.yml`, `ghcr.io/nadicodeai/argo`, NOT `dockerhub`.

**Verification:**
- [ ] `make build` passes; assertions pass.

**Dependencies:** M3.5.

**Files likely touched:** patch, asserts, series.

**Scope:** S–M.

---

### Task M3.7: Patch 0006 — gitleaks allowlist

**Description:** Allowlist OAuth-public-client paths in `.gitleaks.toml` per legacy `fea0bf210`. Verbatim port.

**Acceptance criteria:**
- [ ] `patches/0006-gitleaks-allowlist.patch` adds the allowlist entries.
- [ ] No assertion needed (low-risk patch; pure config addition).

**Verification:**
- [ ] `make build` passes.

**Dependencies:** M3.6.

**Files likely touched:** patch, series.

**Scope:** XS.

---

### Task M3.8: Patch 0007 — browser-test skip gate

**Description:** Add `ARGO_E2E_BROWSER` env check to `tests/tools/test_browser_supervisor.py` per legacy `deb150128`. Skip the suite in CI unless explicitly set.

**Acceptance criteria:**
- [ ] `patches/0007-browser-test-skip-gate.patch` adds the skip condition.
- [ ] Assertion: `regex:ARGO_E2E_BROWSER`.

**Verification:**
- [ ] `make build` passes; assertion satisfied.

**Dependencies:** M3.7.

**Files likely touched:** patch, asserts, series.

**Scope:** XS.

---

### Task M3.9: Patch 0008 — pyproject.toml rename targets (defer if not needed)

**Description:** Add hints/entries the rename engine needs to find pyproject.toml rename targets correctly. May be a no-op if the lifted rename engine already handles pyproject.toml well — verify before writing.

**Acceptance criteria:**
- [ ] Either the patch is written (with assertions) OR documented as not-needed (comment in `series`).
- [ ] If written: build passes; `dist/argo/pyproject.toml` has `name = "argo-agent"` (or `name = "argo"` per OQ resolution — verify legacy convention).

**Verification:**
- [ ] `make build && grep "^name" dist/argo/pyproject.toml` shows the renamed package name.

**Dependencies:** M3.8.

**Files likely touched:** patch (maybe), series.

**Scope:** S.

---

### Checkpoint: M3 complete

- [ ] Patch series 0001–0008 applied (or documented as skipped).
- [ ] `make build` exits 0; all assertions pass; leakage scan exits 0.
- [ ] `patches/series` has each entry; `patches/asserts/manifest.txt` lists load-bearing patches.
- [ ] Manual review of each patch by author: does it represent ONE logical change, is it ≤200 lines, ≤5 unrelated files?
- [ ] Commit each M3.x as a separate commit on `main` for reviewability.

**Maps to spec AC-6** (leakage), **AC-12** (assertion failure mode — tested via M3.1 negative fixture). (AC-3's formal verification lives in M4.2a, not here — M3 only confirms patches apply against the static current upstream pin, not the upstream-refactor scenario AC-3 specifies.)

---

## Phase M4 — CI gates

### Task M4.1: Write `tools/check_upstream_pristine.py`

**Description:** The FR-15 / C3 enforcer. Verifies that `upstream/` in the current working tree matches the upstream tree exactly as it was at the last `make sync` / `make bootstrap` commit. Any drift fails. CI runs this on every PR.

**Strategy.** Upstream's SHA (`cat upstream/.commit`) is NOT a ref in our repo — `git subtree --squash` records the tree but does NOT preserve upstream's commit objects in our object DB. So we cannot `git show upstream-sha:upstream/...`. Two viable approaches; pick (A):

- **(A) Sync-commit anchored diff.** Every `make sync` / `make bootstrap` commit touches `upstream/` (and only `upstream/` + `upstream/.commit`). Find the most recent commit whose tree under `upstream/` differs from its parent's. Verify `git diff <that-commit> HEAD -- upstream/` is empty. Encoded as: `tools/check_upstream_pristine.py` walks `git log --pretty=%H -- upstream/`, picks the newest commit, and runs `git diff <sha> HEAD -- upstream/`. Any non-empty diff is a drift.
- **(B) Fetch upstream as a read-only remote** and compare blob hashes. Adds a remote, fragile in CI sandbox.

Implement (A). Reject any PR whose `upstream/` tree differs from the last-sync-commit's `upstream/` tree.

**Acceptance criteria:**
- [ ] `python tools/check_upstream_pristine.py` exits 0 if `upstream/` matches the last-sync-commit's `upstream/` tree.
- [ ] Exits non-zero with the list of drifted paths if any edit exists.
- [ ] Bootstrap edge case: if there is only one commit affecting `upstream/` (the bootstrap commit itself), the gate exits 0 (no drift possible by definition — the working tree IS the bootstrap state, unless someone uncommitted-edited `upstream/`).
- [ ] Working-tree edge case: also rejects uncommitted edits — `git diff HEAD -- upstream/` MUST be empty.

**Verification:**
- [ ] Default state: exits 0.
- [ ] Manually edit one file under `upstream/` (don't commit): exits 1 naming the file. Revert.
- [ ] Commit an edit to `upstream/` in a feature branch: exits 1 naming the file. Reset.

**Dependencies:** M1.2.

**Files likely touched:** `tools/check_upstream_pristine.py`.

**Scope:** M.

---

### Task M4.2: Implement `tools/sync.py` + wire `make sync` / `make sync-resume` / `make sync-reset`

**Description:** Make the sync workflow real per spec FR-8 / FR-9. M1.9 left `make sync` / `make sync-resume` / `make sync-reset` as no-op stubs. This task implements them.

`tools/sync.py` per FR-8:

1. Verify working tree is clean (`git status --porcelain` empty); refuse otherwise.
2. `git subtree pull --prefix=upstream <hermes-upstream-url> main --squash`. On merge conflict in `upstream/`, exit non-zero with instructions.
3. Update `upstream/.commit` with the new pinned SHA.
4. Populate `.sync-workdir/` (clear if it already exists from a prior failed attempt — but offer `make sync-reset` first; refuse if `.sync-workdir/` has uncommitted edits unless `--force`).
5. `cd .sync-workdir && quilt push -a`. On failure, print failing patch + conflicting hunks, leave `.sync-workdir/` half-applied, print `make sync-resume` instructions, exit non-zero.
6. On success, run `make build` as verification (includes FR-12 leakage + FR-14 assertions).
7. Copy any refreshed patches from `.sync-workdir/patches/` back to `patches/`.
8. Stage `upstream/`, `upstream/.commit`, modified patches; commit with `sync: upstream <short-sha> (<n> patches refreshed)`.

`tools/sync_resume.py` per FR-9: verify `.sync-workdir/` exists, runs `quilt refresh`, copies patches back, re-runs `quilt push -a` for remainder, then `make build`, then commit.

`tools/sync_reset.py`: wipe `.sync-workdir/`.

`Makefile` targets (replacing the M1.9 stubs): `sync`, `sync-resume`, `sync-reset` call the three scripts respectively.

**Acceptance criteria:**
- [ ] `tools/sync.py`, `tools/sync_resume.py`, `tools/sync_reset.py` exist, each pure-Python, each with `encoding="utf-8"` on all I/O.
- [ ] `tools/sync.py` accepts a `--upstream-url <url>` flag (or honours `ARGO_SYNC_UPSTREAM_URL`) that overrides the default hermes-agent upstream URL. Required for the M4.2 fixture test (and for any future air-gapped sync rehearsal); production runs use the default.
- [ ] `make sync` (against a clean tree where `upstream/.commit` already equals the upstream HEAD) is a no-op that exits 0 with a "no changes" message.
- [ ] `make sync` against the `sync-fixture-200/` fixture runs end-to-end with zero conflicts, produces a clean `dist/argo/`, leakage scan passes — this is the AC-2 verification path. Implemented as a unit test `overlay/tests/test_sync_fixture.py` that:
   1. Extracts `tests/fixtures/sync-fixture-200/baseline-tree.tar.zst` to a tmpdir (simulating "upstream at the older baseline SHA").
   2. Initializes a local bare git repo from that tree at `BASELINE-SHA`, applies the fixture patch as a commit at `HEAD-SHA`, so the bare repo has the two-commit graph `BASELINE → HEAD`.
   3. Constructs a sibling worktree where `upstream/` is reset to match `BASELINE-SHA` and `upstream/.commit` records `BASELINE-SHA` (so `make sync` sees an outdated pin).
   4. Runs `tools/sync.py` with the subtree URL pointed at the local bare repo (e.g. via a `--upstream-url` flag the script supports, or by environment var `ARGO_SYNC_UPSTREAM_URL` honoured by the script).
   5. Asserts: zero quilt conflicts, `dist/argo/` clean, leakage passes, `upstream/.commit` advanced to `HEAD-SHA`.
- [ ] `make sync-resume` against a half-applied `.sync-workdir/` (constructed by deliberately introducing a conflict in a test) recovers and commits.
- [ ] `make sync-reset` wipes `.sync-workdir/` cleanly; subsequent `make sync` works.
- [ ] All three commands refuse to operate if working tree has uncommitted changes (except for `.sync-workdir/` which is gitignored).

**Verification:**
- [ ] No-op `make sync` against current pin exits 0 with no commit produced.
- [ ] Sync-fixture-200 test passes (AC-2 met for the first time).
- [ ] Manually inject a conflict, run `make sync`, observe failure with helpful output; run `make sync-resume` after manual fix, observe success.

**Dependencies:** M2.4 (fixture must exist), M3.1 (assertions runner must exist so `make build` enforces FR-14 in the verification step).

**Files likely touched:** `tools/sync.py`, `tools/sync_resume.py`, `tools/sync_reset.py`, `Makefile`, `overlay/tests/test_sync_fixture.py`.

**Scope:** L (3 scripts + a non-trivial fixture-driven test; ~400-600 LOC total).

**Maps to spec AC-2** (zero-conflict pristine sync — first time it's actually tested), **AC-4** (overlap-fail-loud — exercised by the conflict-injection test), **AC-11** (sync workdir isolation — confirmed when `make build` mid-sync doesn't clobber `.sync-workdir/`).

---

### Task M4.2a: AC-3 single non-overlapping patch sync test

**Description:** Spec AC-3 specifies a scenario distinct from AC-2: `patches/series` contains one patch that adds a `--static` flag to `hermes_cli/main.py`; upstream refactors that same file AWAY from the patch's insertion lines; `quilt push -a` MUST succeed without manual intervention. M4.2's sync-fixture-200 test covers AC-2 (empty patch series), not AC-3. This task adds the AC-3 fixture and assertion.

**Fixture design.** Under `tests/fixtures/sync-fixture-ac3/`:
- `baseline-main.py` — a minimal `hermes_cli/main.py` stand-in (or use the real one at baseline).
- `patches/add-static-flag.patch` — adds a `--static` flag at lines that exist in `baseline-main.py`.
- `upstream-refactor.patch` — a refactor that moves the surrounding code blocks but does NOT touch the lines the `--static` flag patch inserts (e.g. renames a helper used elsewhere in the file).

The test starts at baseline, places `add-static-flag.patch` in `patches/series`, simulates a sync that applies `upstream-refactor.patch` to upstream, runs `make sync`, and asserts `quilt push -a` succeeds with zero user prompts AND the patch's `--static` flag survives.

**Acceptance criteria:**
- [ ] `tests/fixtures/sync-fixture-ac3/` exists with the three files above.
- [ ] `overlay/tests/test_sync_fixture.py` (or a sibling `test_sync_ac3.py`) exercises the AC-3 scenario.
- [ ] The test asserts: `quilt push -a` exit 0; `dist/argo/argo_cli/main.py` contains both the refactor AND `--static` (verified via assertion file pattern).
- [ ] An assertion file `tests/fixtures/sync-fixture-ac3/asserts.txt` lists the patterns that must remain.

**Verification:**
- [ ] Test passes in CI.
- [ ] If the patch is deliberately constructed to overlap (e.g. inserts on a refactored line), the test variant for AC-4 fails loudly — already covered by M4.2's conflict-injection test, this confirms the inverse path.

**Dependencies:** M4.2.

**Files likely touched:** `tests/fixtures/sync-fixture-ac3/**`, `overlay/tests/test_sync_ac3.py`.

**Scope:** S–M.

**Maps to spec AC-3.**

---

### Task M4.3: Write `.github/workflows/ci.yml`

**Description:** Per-PR CI workflow. Jobs: `lint`, `typecheck`, `build`, `leakage`, `upstream-pristine`, `test`, `parity` (placeholder until M6). Runs on `pull_request` and `push to main`. The `test` job includes the M4.2 sync-fixture test (AC-2), the M4.2a AC-3 fixture test, and the M2.4a legacy-untouched verify (`make check-legacy-untouched`) so all three ACs are enforced on every PR.

**Acceptance criteria:**
- [ ] Each job runs the corresponding Make target.
- [ ] `upstream-pristine` job calls `tools/check_upstream_pristine.py`.
- [ ] `test` job includes `overlay/tests/test_sync_fixture.py` (the AC-2 gate).
- [ ] Workflow uses uv for Python setup and quilt installed via apt.
- [ ] PR mergeability gated on all jobs passing (branch protection — separate manual config).
- [ ] Workflow is idempotent — re-running on the same SHA gives the same result.

**Verification:**
- [ ] Push to a feature branch, open a draft PR, observe all jobs run and pass on a clean repo.
- [ ] Deliberately introduce an `upstream/` edit, confirm `upstream-pristine` fails.
- [ ] Deliberately drop a fork line, confirm a patch assertion fails.

**Dependencies:** M2.2 (leakage), M2.4a (legacy-untouched check), M3.1 (assertions), M4.1 (upstream-pristine), M4.2 (sync impl + sync-fixture test), M4.2a (AC-3 test). Some jobs are no-ops until later phases (parity); spec the placeholders explicitly.

**Files likely touched:** `.github/workflows/ci.yml`.

**Scope:** M.

---

### Task M4.4: Write `.github/workflows/sync.yml` (weekly cron)

**Description:** Cron-triggered workflow that runs `make sync` and opens a PR with the result. Manual `workflow_dispatch` trigger also.

**Acceptance criteria:**
- [ ] Cron schedule: weekly (e.g., Mondays at 06:00 UTC).
- [ ] Job runs `make sync`; on success, commits and opens a PR titled `sync: upstream <short-sha>`.
- [ ] On any failure (conflict, build, leakage, assertion), opens an issue with the failure details.
- [ ] Uses a bot token with PR-create + issue-create permissions.

**Verification:**
- [ ] Manual `workflow_dispatch` trigger on the workflow runs through without errors against the current upstream pin (= no-op sync).
- [ ] Force a conflict via a test branch and verify the failure-issue path.

**Dependencies:** M4.2 (sync impl), M4.3 (CI workflow). M5.x is NOT required (sync is independent of image push).

**Files likely touched:** `.github/workflows/sync.yml`.

**Scope:** M.

---

### Checkpoint: M4 complete

- [ ] All CI jobs run on PRs and pass on a clean repo.
- [ ] `upstream-pristine` job catches an injected drift.
- [ ] Per-patch assertions catch an injected fork-line drop.
- [ ] `make sync` / `make sync-resume` / `make sync-reset` are functional (no longer no-op stubs from M1.9).
- [ ] Sync-fixture-200 test passes (AC-2 verified for the first time).
- [ ] AC-3 single non-overlapping patch test passes (M4.2a).
- [ ] Weekly sync workflow runs manually with no-op result.

**Maps to spec AC-2** (zero-conflict pristine sync via fixture), **AC-3** (single non-overlapping patch sync via M4.2a), **AC-4** (overlap-fail-loud), **AC-9** (CI gate), **AC-11** (sync workdir isolation).

---

## Phase M5 — Docker pipeline

### Task M5.1: Write multi-stage `Dockerfile`

**Description:** Per FR-7. Stage 1 (`builder`): copies `upstream/`, `patches/`, `overlay/`, `tools/`, `argo-rename.yaml`, runs `tools/build.py`, produces `dist/argo/`. Stage 2 (`runtime`): `FROM python:3.13-slim`, copies ONLY `dist/argo/`, runs `pip install -e /opt/argo`, sets `CMD ["argo"]`, `ENV ARGO_HOME=/home/argo/.argo`.

**Acceptance criteria:**
- [ ] Dockerfile builds locally via `docker buildx build -t argo:dev .`.
- [ ] Final image does NOT contain `upstream/`, `patches/`, `overlay/`, `tools/`, `.shepherd/`, `scripts/`. Verify via `docker run --rm argo:dev sh -c 'ls /' | grep -E "upstream|patches|overlay|tools"` returns nothing.
- [ ] Final image does NOT contain `argo_sync/` (OQ-10 — strip rename engine from runtime).
- [ ] `docker run --rm argo:dev argo --version` prints version + build manifest.
- [ ] `docker run --rm argo:dev argo doctor --static` exits 0.
- [ ] Image size within 5% of legacy `argo-agent:0.14.0` (NFR-3).

**Verification:**
- [ ] All four "exits 0" / "doesn't contain" checks pass.
- [ ] `docker image ls argo:dev` reports size; compare to legacy.

**Dependencies:** M2 complete.

**Files likely touched:** `Dockerfile`.

**Scope:** M.

---

### Task M5.2: Write `scripts/publish.sh` and `make publish`

**Description:** Tag and push to ghcr.io. Tags: `:dev` (local), `:<git-sha-short>` (CI on main), `:latest` (on main merge), `:v<X.Y.Z>` (on release tags).

**Acceptance criteria:**
- [ ] `make publish` requires GHCR auth (uses `secrets.GHCR_TOKEN` in CI, `gh auth login` locally).
- [ ] Pushes both `:<sha>` and `:latest` on `main`.
- [ ] Refuses to push if working tree is dirty.
- [ ] `.github/workflows/docker-publish.yml` invokes `make image && make publish` on `push to main`.

**Verification:**
- [ ] Manually run `make publish` (with GHCR auth) and verify the image appears at `ghcr.io/nadicodeai/argo:dev`.
- [ ] PR-merge into main triggers the workflow and produces `:<sha>` + `:latest`.

**Dependencies:** M5.1.

**Files likely touched:** `scripts/publish.sh`, `Makefile`, `.github/workflows/docker-publish.yml`.

**Scope:** S–M.

---

### Task M5.3: Verify dist/ determinism (AC-8)

**Description:** Prove `dist/argo/` is bit-identical across two builds on the same SHA with `SOURCE_DATE_EPOCH` set.

**Acceptance criteria:**
- [ ] Run `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) make build` twice; hash the trees.
- [ ] `find dist/argo -type f -exec sha256sum {} \; | sort | sha256sum` is identical across runs.
- [ ] `docker run --rm argo:dev argo --version --verbose` is byte-identical across two `make image` builds on the same SHA.
- [ ] Document in `AGENTS.md` that `SOURCE_DATE_EPOCH` MUST be set for reproducible builds.

**Verification:**
- [ ] Two-build hash comparison succeeds.

**Dependencies:** M5.1.

**Files likely touched:** `tools/build.py` (set SOURCE_DATE_EPOCH-aware mtimes if needed), `AGENTS.md`.

**Scope:** S.

---

### Checkpoint: M5 complete

- [ ] Docker image builds locally and via CI.
- [ ] Image published to GHCR at `:dev` from a local run.
- [ ] `dist/argo/` is deterministic across two builds.
- [ ] Image size within 5% of legacy.

**Maps to spec AC-8** (dist determinism), parts of **G2**, **G3** (image surface).

---

## Phase M6 — Parity suite

### Task M6.1: Pull legacy baseline image

**Description:** Pull `ghcr.io/nadicodeai/argo-agent:0.14.0` (or whichever tag is the current production baseline) and verify it runs.

**Acceptance criteria:**
- [ ] `docker pull ghcr.io/nadicodeai/argo-agent:0.14.0` succeeds.
- [ ] `docker run --rm ghcr.io/nadicodeai/argo-agent:0.14.0 argo --help` works.

**Verification:**
- [ ] Both commands above exit 0.

**Dependencies:** None (independent of M5).

**Files likely touched:** None (verification-only).

**Scope:** XS.

---

### Task M6.2a: Parity runner skeleton + CLI surfaces (1-2)

**Description:** Build the parity runner framework and implement the easy CLI surfaces. Splits the original M6.2 in half because the 7 surfaces collectively are XL (not L) — particularly surfaces 3-7 require stub backends, fixture plugin dirs, and stub OAuth providers. M6.2a establishes the harness against the two zero-fixture surfaces.

**Surfaces in scope:**
1. `argo --help`, `argo --version` (no inputs; just compare stdout).
2. `argo doctor --static` (against a tmpdir tree containing one leakage hit).

**Acceptance criteria:**
- [ ] `tools/parity_runner.py` parses `--surface <name>` and `--image <image>` flags; runs a single surface against a single image; returns stdout + exit code.
- [ ] Normalizes legacy output via `s/hermes/argo/g`, `s/Hermes/Argo/g`, `s/HERMES/ARGO/g`, `s/hermes-agent/argo/g` (surface decides which subset applies — `argo --version` should NOT have its commit SHA rewritten if it's a 40-hex token).
- [ ] `make parity` invokes the runner across the in-scope surfaces.
- [ ] Each surface is a `surfaces/<name>.py` plugin so adding more in M6.2b is mechanical.
- [ ] Runs in CI as part of `make test` IF both images are pullable (skipped with warning otherwise).

**Verification:**
- [ ] Surfaces 1-2 against legacy `:0.14.0` and `:dev`: zero non-brand diffs.

**Dependencies:** M5.1, M6.1.

**Files likely touched:** `tools/parity_runner.py`, `tools/parity_surfaces/help_version.py`, `tools/parity_surfaces/doctor_static.py`, `overlay/tests/test_parity.py`.

**Scope:** M.

---

### Task M6.2b: Parity surfaces (3-7) with fixtures

**Description:** Implement the remaining FR-16 surfaces, each behind its own fixture/stub. These are the surfaces that catch real customer regressions (vs surface 1-2 which only catch wholesale breakage).

**Surfaces in scope:**
3. API server: `GET /health`, `GET /v1/models` (stub model backend fixture).
4. MCP plugin discovery: `argo mcp list` against `tests/fixtures/parity_mcp_plugins/`.
5. Hook dispatch: `argo hook fire <event>` against `tests/fixtures/parity_hooks/`.
6. OAuth flow init: `argo auth start --provider stub` returning expected URL (`tests/fixtures/parity_oauth_stub/`).
7. Session persistence: `argo chat --once` with `ARGO_HOME=/tmp/x`; compare JSON keys of resulting session file.

**Acceptance criteria:**
- [ ] Each surface has a dedicated fixture under `tests/fixtures/parity_<surface>/` checked into the repo.
- [ ] Each surface's normalized output diffs to zero against legacy.
- [ ] If a surface CANNOT be implemented (e.g., a real OAuth provider would be required and stubbing is infeasible), document with `# DEFERRED: <reason>` and a follow-up milestone reference. Be explicit — AC-7 doesn't pass with deferred surfaces but the plan acknowledges scope.

**Verification:**
- [ ] All 5 surfaces have at least one assertion.
- [ ] `make parity` reports per-surface pass/fail/deferred.

**Dependencies:** M6.2a.

**Files likely touched:** `tools/parity_surfaces/*.py`, `tests/fixtures/parity_*/`, `overlay/tests/test_parity.py`.

**Scope:** L.

**Risk:** Some surfaces may need real model/provider backends that don't have viable stubs. M6.2b SHOULD bias toward deferring with clear documentation rather than building elaborate fakes that drift from production behavior. The Customer-Parity gate G3 requires all 7 to land eventually — track deferred surfaces explicitly.

---

### Checkpoint: M6 complete

- [ ] `make parity` runs end-to-end against `:dev` vs `:0.14.0`.
- [ ] All 7 surfaces (2 from M6.2a + 5 from M6.2b) pass with zero non-brand diffs, OR deferred surfaces are explicitly listed with rationale and follow-up tracked.
- [ ] G3 (customer parity) is green only when ALL 7 surfaces pass; partial M6 means G3 is BLOCKED.

**Maps to spec AC-7** (functional parity), **G3** (customer parity).

---

## Phase M7 — First real sync

### Task M7.1: Run `make sync` against current upstream HEAD

**Description:** Execute the full sync workflow end-to-end against real upstream. This is the production validation of G1.

**Acceptance criteria:**
- [ ] `make sync` runs; reports the upstream delta size; reports patch refresh count.
- [ ] **Delta-size precondition for G1 measurement:** the real upstream HEAD must differ from `upstream/.commit` by ≥100 changed files. If the natural delta is smaller, intentionally delay this milestone until ≥100 files accumulate upstream (track with a one-line check: `git diff --name-only $(cat upstream/.commit) <upstream-head> | wc -l`). G1's measurement requires the ≥100-file threshold — anything less and it's a smoke test, not a gate.
- [ ] If conflicts arise: resolve via `make sync-resume` per FR-9; verify the workflow doesn't lose data.
- [ ] Final commit on `main` is `sync: upstream <short-sha> (<n> patches refreshed)`.
- [ ] `make build && make leakage-static && make parity` all pass post-sync.
- [ ] **Timing recorded.** `time make sync` wall-clock is captured in the commit message body (e.g. `Sync wall-clock: 3m42s; delta 173 files; 1 patch refreshed.`). G1's ≤5 min budget is asserted against this number.

**Verification:**
- [ ] Sync completes ≤5 min wall-clock on a delta ≥100 files (G1 — measured, not declared).
- [ ] Non-conflict path ≤2 min (NFR-1).
- [ ] No fork features lost (verified by assertions + parity).

**Dependencies:** M4.2 (sync impl), M4.3 (ci.yml), M5.1, M6.2a (M6.2b not required for first sync — sync gate is leakage + assertions; parity is a post-sync check).

**Files likely touched:** `upstream/`, `upstream/.commit`, possibly `patches/<one or more>.patch`.

**Scope:** M (mostly mechanical; investigation if conflicts).

---

### Task M7.2: Tag a first release

**Description:** After the sync passes all gates, tag a `v0.1.0` release. Triggers `release.yml` (if scaffolded) to publish `ghcr.io/nadicodeai/argo:v0.1.0` + `:latest`.

**Acceptance criteria:**
- [ ] `git tag -a v0.1.0 -m "First pristine-fork release"` + `git push --tags`.
- [ ] CI publishes the image with correct tags.

**Verification:**
- [ ] `docker pull ghcr.io/nadicodeai/argo:v0.1.0` works.

**Dependencies:** M7.1.

**Files likely touched:** None (tag + workflow).

**Scope:** XS.

---

### Checkpoint: M7 complete

- [ ] First real sync against upstream HEAD succeeded.
- [ ] First release tagged and image published.
- [ ] All G1, G2, G3, G4 gates green.

**Maps to G1** (sync sanity).

---

## Phase M8 — Documentation freeze

### Task M8.1: Finalize `AGENTS.md`

**Description:** ≤200 lines per FR-13. Points at `.shepherd/spec.md`, `.shepherd/standards.md`. Includes the 5-command quilt cheatsheet. Documents the maintainer sync workflow + conflict resolution playbook.

**Acceptance criteria:**
- [ ] `wc -l AGENTS.md` ≤200.
- [ ] Has sections: Overview, Architecture (one paragraph), Workflow (sync + patch ops + build), Common Tasks (cheatsheet), Where to find more (links).
- [ ] Mentions `SOURCE_DATE_EPOCH` requirement for reproducibility.

**Verification:**
- [ ] A new engineer reading only `AGENTS.md` + `.shepherd/spec.md` can complete `make sync` within 30 minutes (G6 — self-audit by re-reading cold).

**Dependencies:** M7 complete.

**Files likely touched:** `AGENTS.md`.

**Scope:** M.

---

### Task M8.2: Finalize `README.md`

**Description:** User-facing. `docker pull ghcr.io/nadicodeai/argo:latest` quickstart, fork-notice, license, link to upstream credit.

**Acceptance criteria:**
- [ ] Has: title, one-paragraph description, quickstart (3 commands), fork-notice block, license, contributing pointer.
- [ ] Does NOT mention internal patch-series mechanics (that's `AGENTS.md`).

**Verification:**
- [ ] Manual read-through; user-perspective sanity.

**Dependencies:** None.

**Files likely touched:** `README.md`.

**Scope:** S.

---

### Task M8.3: Finalize `.shepherd/standards.md`

**Description:** Restate inherited standards + the fork-specific additions (patch authorship, overlay authorship, assertion format).

**Acceptance criteria:**
- [ ] All rules from spec § Code Style captured.
- [ ] Includes the C1 resolution clearly: "overlay uses hermes names; engine renames at build."

**Verification:**
- [ ] Cross-reference each "always/never/ask-first" item in spec Boundaries — every one appears in `standards.md`.

**Dependencies:** None.

**Files likely touched:** `.shepherd/standards.md`.

**Scope:** S.

---

### Checkpoint: M8 complete

- [ ] All docs finalized.
- [ ] G6 onboarding gate validated (self-audit or peer walkthrough).

**Maps to G6** (docs onboarding).

---

## Final Acceptance Sweep

Before declaring "done":

- [ ] G1 — `make sync` completes ≤5 min on ≥100-file delta (measured by M7.1; delta gated by acceptance criterion).
- [ ] G2 — Two-engineer determinism check on `dist/argo/` tree-hash (or self-audit by running on two machines / containers).
- [ ] G3 — `make parity` passes with zero non-brand diffs (M6.2a + M6.2b).
- [ ] G4 — Branch protection on `main` enforces all CI jobs; recent runs green (M4.3 + manual config).
- [ ] G5 — `make check-legacy-untouched` exits 0 (uses the M2.4a baseline; this is the AC-10 verification path — not just a commit-log spot-check).
- [ ] G6 — Docs onboarding validated (M8.1).

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Engine self-renaming `argo_sync` → confused mapping | Medium | Medium | M1.3 risk note; verify in M2.1 audit. |
| Subtree blob-compare in `tools/check_upstream_pristine.py` is fragile | Medium | Medium | M4.1 risk note; consider fetching upstream as a separate remote for the diff. |
| Parity surface 3–7 fixtures balloon scope | Medium | High | Split into M6.2a (1-2) + M6.2b (3-7); defer surfaces in 6.2b explicitly if they grow >2 days, but flag — AC-7 needs all 7. |
| `quilt` not available on macOS dev machines without `brew install quilt` | Low | Low | AGENTS.md documents the install. |
| First real sync (M7.1) surfaces a conflict the spec didn't anticipate | Medium | Medium | The whole pipeline (FR-9, assertions, parity) is designed to fail-loud; investigate root cause and adjust spec/plan. |
| `SOURCE_DATE_EPOCH` ignored by some `pip install` invocations inside Docker | Medium | Low | Document the workaround in AGENTS.md; accept best-effort for now. |
| Lifted assets diverge from legacy due to active development on legacy | N/A | None | G5 enforces legacy is frozen; if it diverges, the spec is violated. |

---

## Open Items (deferred to during-build decisions)

- The exact set of fixture surfaces for `make parity` may need refinement during M6.2 — if a surface (e.g. OAuth flow init) requires a real provider, replace with a stub and document the deferred-to-integration-test.
- Whether to enable multi-arch (linux/arm64) builds on every PR or only on release tags (OQ-4) — decide during M5.1.
- Whether `.github/workflows/release.yml` is built in M5 or M7 — currently in M5 (publish.sh handles tags) but could split.

---

## Parallelization Notes

If multiple agents / sessions are available:

- **Safe to parallelize:** M2.2 (leakage scanner + its fixtures), M2.3 (mode preservation test), M2.4a (legacy-baseline hash recorder), M2.4 (sync-fixture-200 recording), M3.1 (assertion runner). All independent of each other.
- **Must be sequential:** M1.x (bootstrap order matters), each M3.x patch (depends on prior `patches/series`).
- **Coordination needed:** M4.3 (CI workflow) references M2.2, M3.1, M4.1, M4.2 — define the job names + Makefile contract before parallelizing.
