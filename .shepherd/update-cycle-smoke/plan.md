# Implementation Plan: update-cycle-smoke

Phase 2 + Phase 3 ordered work for the update-cycle-smoke Shepherd loop.

**Locked inputs:**
- Spec: `.shepherd/update-cycle-smoke/spec.md` (UCS-AC-1..8 are the exit gates).
- Standards: `.shepherd/update-cycle-smoke/standards.md` (triage categories R/X/S/F/P, fix-location hierarchy `argo-rename.yaml` > `overlay/` > `patches/`).
- Baseline data: `.shepherd/update-cycle-smoke/progress.md` § Baseline run summary (1,244 files, 26,075 tests, 7 files with 26 failing tests, 3 files with collection errors).

## Overview

Make the 26,075 renamed upstream tests in `dist/argo/tests/` go from "1,234 files green, 7 files red, 3 files broken" to "all files green or accepted-XFAIL'd", then wire that result into CI as a new `dist-argo-tests` job. The baseline already tells us the failures cluster in three groups — the plan tackles them cheapest-first.

Cheapest-leverage-first ordering rationale:

1. **S-category (skip-from-dist) goes first** — zero risk, single-config-file change, drops 3 collection errors + 1 deployment-smoke fixture failure with one `argo-rename.yaml` commit.
2. **XFAIL infrastructure (overlay conftest + manifest) second** — required scaffolding for all X-category work.
3. **X-category Cluster 1 (23 cmd_update pip-path tests)** — biggest single chunk of failures; all close at once via a single manifest commit.
4. **Cluster 2 one-offs (2 tests)** — needs failure-log reading; one-off triage.
5. **Clean baseline gate** — verify 0 failures before adding the CI job.
6. **CI job `dist-argo-tests`** — wires the now-green baseline into PR + push gates.
7. **Issue #12 closure + `install-update/progress.md` rewording** — paperwork; the actual product change is already done.

## Architecture Decisions

- **XFAIL manifest format = YAML at `overlay/argo-xfail.yml`**, shaped like `tests/parity-expected.yml`. Each entry: `nodeid: <pytest nodeid>` + `reason: <one-line written reason>` + `category: X|S|F`. Loaded by `overlay/conftest.py` (added at overlay root, becomes `dist/argo/conftest.py` post-build — pytest's rootdir conftest, auto-discovered).

- **Hook mechanism = `pytest_collection_modifyitems` in `overlay/conftest.py`** — applies `pytest.mark.xfail(reason=...)` to matching nodeids at collection time. Pure additive — no patches against upstream's `tests/conftest.py`. Zero sync cost.

- **`argo-rename.yaml` skip rules** for the 4 build-tool tests that shouldn't have been shipped to `dist/argo/tests/`: extend the existing `skip_contexts:` or `exceptions:` (whichever the engine supports for "drop this file entirely"). If the engine doesn't currently support "drop this file," extend it in `tools/rebrand.py` — this is a tooling fix in `tools/`, not a patch against `upstream/`.

- **Patches added by this loop: zero (target).** Every fix this plan touches lives in `overlay/` or `argo-rename.yaml` or `tools/`. If any milestone discovers a fix that genuinely requires patching upstream, the dispatch prompt MUST escalate to Vadim before opening the patch.

- **CI job `dist-argo-tests`** added to `.github/workflows/ci.yml`, NOT a new workflow file. Uses the `argo-setup` composite action. 6-slice matrix matching upstream's `tests.yml`. Visible-but-non-blocking initially; promotion to required is a follow-up.

## Task List

### Phase 2

#### M1: Stop shipping the 4 overlay-owned build-tool tests into `dist/argo/tests/`

**Description (corrected from plan-editor round 1):** Four tests under `overlay/tests/` (`test_cmd_argo_doctor.py`, `test_full_rename_config.py`, `test_sync_resume.py`, `test_deployment_smoke.py`) exercise build-time tooling (`tools/rebrand.py`, `argo-rename.yaml`, `tools/sync.py`) that does not ship in the customer artifact. They were placed in `overlay/tests/` originally, which copies them verbatim into `dist/argo/tests/` via `tools/build.py:_copy_overlay()`. Per `.shepherd/standards.md` § Testing — *"Build-tool tests (for `tools/*.py`) live at top-level `tests/` (not under `overlay/`)"* — they were misplaced. Move them to repo-root `tests/` (next to existing build-tool tests like `tests/test_argo_release.py`, `tests/test_check_upstream_pristine.py`) and update their imports from `argo_sync.*` (post-rename names) to `hermes_sync.*` (pre-rename names matching the repo-root convention used by `tests/test_verify_no_leakage.py`). Verify they no longer land in `dist/argo/tests/` after `make build`. **No `argo-rename.yaml` change. No `tools/rebrand.py` change. No new skip primitive in the engine** — the engine has no "drop file" primitive and `exceptions:` only protects file contents, not file presence.

**Acceptance criteria:**
- [ ] All four files moved from `overlay/tests/` to `tests/`.
- [ ] Imports rewritten from `argo_sync.*` → `hermes_sync.*` and `argo_cli.*` → `hermes_cli.*` to match the pre-rename convention used by other repo-root tests; sys.path-injection pattern from `tools/rebrand.py` lines 34-40 is the reference.
- [ ] After `make build`, none of the 4 paths exist under `dist/argo/tests/`.
- [ ] `pytest tests/` from repo root passes for all four (build-tool surface still tested).
- [ ] Re-running `dist/argo/.venv-test/bin/python dist/argo/scripts/run_tests_parallel.py` shows 0 collection errors and the `test_deployment_smoke.py::test_help_and_version_smoke` failure is gone.

**Verification:**
- [ ] `make build && ls dist/argo/tests/test_cmd_argo_doctor.py 2>&1 | grep -q "No such"` exits 0 (and same for the other three).
- [ ] `pytest tests/test_cmd_argo_doctor.py tests/test_full_rename_config.py tests/test_sync_resume.py tests/test_deployment_smoke.py` exits 0 (build-tool tests still run; `test_deployment_smoke.py`'s `integration`-marked variants still skipped by default).
- [ ] `cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py` reports 0 collection errors; failures drop from 26+3 to 23+2.
- [ ] `make leakage-static` still passes (scanner targets `dist/argo/`, not `overlay/` — no expected change).

**Dependencies:** None. Truly parallel-eligible with M2.

**Files likely touched:**
- `overlay/tests/test_cmd_argo_doctor.py` → `tests/test_cmd_argo_doctor.py` (move + fix imports)
- `overlay/tests/test_full_rename_config.py` → `tests/test_full_rename_config.py` (move + fix imports)
- `overlay/tests/test_sync_resume.py` → `tests/test_sync_resume.py` (move + fix imports)
- `overlay/tests/test_deployment_smoke.py` → `tests/test_deployment_smoke.py` (move + fix imports)

**Estimated scope:** S (4 file moves + import edits; ~10-30 lines per file).

**Exit gates (UCS-AC-*):** Contributes to UCS-AC-3 (real bugs fixed via overlay/rename-yaml, here the bug is "test misplaced in overlay") and UCS-AC-2 (every failure triaged).

**Subagent roles:**
- Implementer: 1.
- Refactorer pass: skip (mechanical move + import edits).
- Architect pass: required — verify FR-15 upstream-pristine still passes, AC-8 determinism still holds, and `make leakage-static` still passes after the moves.

---

#### M2: XFAIL infrastructure — `overlay/argo-xfail.yml` + `overlay/conftest.py`

**Description:** Add the XFAIL manifest format and a pytest hook in overlay that reads it at collection time and marks matching nodeids as expected failures. This is the scaffolding M3 depends on. Empty manifest at end of this milestone — entries land in M3. **Path choice rationale:** Manifest at `overlay/argo-xfail.yml` (overlay root, not `overlay/tests/`) so the conftest hook at `overlay/conftest.py` (which becomes `dist/argo/conftest.py`, pytest's rootdir conftest) and the manifest are co-located and easier to discover; standards.md § Architecture line 44 marks the path as "TBD by plan." Pytest discovers `conftest.py` files top-down from rootdir before walking `testpaths`; `dist/argo/conftest.py` is loaded ahead of `dist/argo/tests/conftest.py`, which is exactly what we want (the manifest must be applied before per-test conftests assemble their fixtures). Verified during plan-editor round 1: `dist/argo/conftest.py` does not currently exist (only `dist/argo/tests/conftest.py`, ~31KB with autouse env-isolation fixtures), so the overlay file lands without collision.

**Acceptance criteria:**
- [ ] `overlay/argo-xfail.yml` exists with a documented schema header (commented) and an empty `xfails: []` list.
- [ ] `overlay/conftest.py` exists, gets renamed to `dist/argo/conftest.py` by the build, and at pytest collection time loads the manifest and applies `pytest.mark.xfail` to matching nodeids with the specified reason.
- [ ] An empty manifest is a no-op: `make build && cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py` reports the SAME failure count as the baseline (no new failures introduced by the conftest).
- [ ] A test inserting a deliberately-failing test + an XFAIL manifest entry for it shows pytest reports the test as `XFAIL` (expected failure), not `FAILED`.

**Verification:**
- [ ] Unit test for `overlay/conftest.py` (or its support module): `pytest tests/test_overlay_xfail_hook.py` exits 0. Test asserts manifest parsing, nodeid matching, and marker application against a small fixture pytest session.
- [ ] `make leakage-static` passes (the new files contain only `argo`-style names; no `hermes` strings).
- [ ] FR-15 upstream-pristine still passes.

**Dependencies:** None (parallel-eligible with M1).

**Files likely touched:**
- `overlay/argo-xfail.yml` (new)
- `overlay/conftest.py` (new, ~50 lines)
- `tests/test_overlay_xfail_hook.py` (new unit test for the hook, ~80 lines)

**Estimated scope:** S.

**Exit gates (UCS-AC-*):** Contributes to UCS-AC-4 (XFAILs gated by a manifest with `reason:` field) — provides the infrastructure UCS-AC-4 names.

**Subagent roles:**
- Implementer: 1 (parallel with M1's implementer in a separate worktree).
- Refactorer pass: required after merge (collapse any duplication, verify naming).
- Architect pass: required — verify the conftest's collection hook is idempotent and doesn't slow `make build` measurably.

---

#### Checkpoint after M1 + M2

- [ ] Baseline re-run shows 23 failures (Cluster 1 only — the cmd_update tests) and 2 one-off failures (Cluster 2). Collection errors and the S-category fixture failure are gone.
- [ ] All UCS-AC verifications that don't depend on later milestones still pass: UCS-AC-3, UCS-AC-4, UCS-AC-6 (no new runner, no new test infra), UCS-AC-8 (no fake servers / pexpect added).
- [ ] No new patches in `patches/`.

---

#### M3: X-category Cluster 1 — XFAIL the 23 `cmd_update` pip-path tests

**Description:** For each of the 23 failures in `tests/argo_cli/test_cmd_update.py`, `test_update_autostash.py`, `test_update_yes_flag.py`, `test_update_zip_symlink_reject.py`, add an entry to `overlay/argo-xfail.yml` with the reason: *"argo not published to PyPI per IU-FR-13; cmd_update's pip path is unused for properly-installed argo customers (install via public install.sh URL). Test asserts on pip-path branch-fallback / autostash / yes-flag / symlink behavior that argo's customer flow never exercises."* Per-test variation in the wording where the underlying assertion differs.

Also update `.shepherd/install-update/progress.md` § Phase 3 closure note: reconcile IU-FR-13's "_cmd_update_pip is unreachable" claim with reality — it IS reachable for pip-installed argo (e.g. dev installs); it's "unreachable for properly-installed customers." Wording fix only; no code change.

**Acceptance criteria:**
- [ ] 23 entries in `overlay/argo-xfail.yml`, each with a written `reason:` matching the standard above.
- [ ] `make build && cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py` shows 2 failures (Cluster 2 only) and 23 XFAILs.
- [ ] `.shepherd/install-update/progress.md` § Phase 3 closure has the wording fix applied.

**Verification:**
- [ ] `cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py 2>&1 | grep -c XFAIL` returns ≥ 23.
- [ ] Cluster-1 files show 0 FAILED entries.

**Dependencies:** M2 (XFAIL infrastructure must exist).

**Files likely touched:**
- `overlay/argo-xfail.yml` (+23 entries)
- `.shepherd/install-update/progress.md` (1 paragraph rewrite)

**Estimated scope:** S (mechanical content + one wording fix).

**Exit gates (UCS-AC-*):** Closes UCS-AC-2 for Cluster 1 (triage applied), UCS-AC-4 (manifest entries with `reason:` fields), part of UCS-AC-7 (issue-12 closure body cites this fix).

**Subagent roles:**
- Implementer: 1.
- Refactorer pass: required — collapse duplicated `reason:` strings into a shared constant if more than 3 tests share verbatim wording (manifest hygiene).
- Architect pass: required — verify the 23 entries collectively don't cross the 5% XFAIL threshold (~1,303 tests) that would trigger the "deeper rebrand problem" boundary in standards.md.

---

#### M4: Cluster 2 one-offs — fix `test_env_loader` real bug + triage `test_ntfy_plugin`

**Description (diagnosis pre-baked from plan-editor round 1; see below):**

***`test_env_loader.py::test_main_import_applies_user_env_over_shell_values` — R-category (real rebrand bug).*** The dist-rendered file (`dist/argo/tests/argo_cli/test_env_loader.py:94`) still contains the literal `HERMES_INFERENCE_PROVIDER=custom\n` inside a Python string fixture, while lines 100/106 correctly reference the renamed `ARGO_INFERENCE_PROVIDER`. The rebrand engine missed the fixture string because `argo-rename.yaml`'s URL `skip_contexts:` pattern `https?://(?!(?:...))[^\s]*` is greedy and consumes the entire `https://new.example/v1\nHERMES_INFERENCE_PROVIDER=custom\n` segment as one "URL" (the `\n` in the source is the two-char escape `\` + `n`, neither of which is a regex `\s` match). **Fix:** tighten the URL skip_contexts pattern in `argo-rename.yaml` to stop at the closing quote or escape: e.g. extend the negated character class from `[^\s]*` to `[^\s"'\\]*`. Then `make build` + re-run the failing test.

***`test_ntfy_plugin.py::TestStandaloneSend::test_posts_to_server` — F-category (inherited flake).*** The failure log shows `RuntimeWarning: coroutine 'BasePlatformAdapter._keep_typing' was never awaited` plus `Task was destroyed but it is pending` for tasks unrelated to ntfy itself; no `hermes`/`argo` token is involved. Confirm by running the file once on the un-renamed upstream tree (or against upstream's own CI logs if accessible); if the same failure reproduces upstream-shaped, it is an inherited flake. **Document in `progress.md` § Triage Table; do NOT XFAIL** (per standards.md § Triage Categories: F-category gets documented, not skip-marked).

**Acceptance criteria:**
- [ ] `argo-rename.yaml` URL `skip_contexts:` pattern tightened to stop at quote/escape boundaries.
- [ ] After `make build`, `grep -rn 'HERMES_INFERENCE_PROVIDER' dist/argo/tests/` returns no results.
- [ ] `cd dist/argo && .venv-test/bin/python -m pytest tests/argo_cli/test_env_loader.py -x` exits 0.
- [ ] `test_ntfy_plugin.py` failure documented as inherited flake in triage table (nodeid, category=F, evidence link).
- [ ] `cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py` shows 0 failures excluding XFAILs and the one F-category documented flake.

**Verification:**
- [ ] `cd dist/argo && grep -rn 'HERMES_INFERENCE_PROVIDER' tests/` returns nothing.
- [ ] Existing tests under `tests/test_verify_no_leakage.py` and (post-M1) `tests/test_full_rename_config.py` still pass.
- [ ] `make leakage-static` still exits 0 (regex tightening must not re-expose `hermes` tokens elsewhere — see Risk table).
- [ ] `make parity` still passes (no surface-diff regression).
- [ ] FR-15 upstream-pristine still passes.

**Dependencies:** M2 (manifest infrastructure exists in case `test_ntfy_plugin` triage flips to X-category on closer inspection).

**Files likely touched:**
- `argo-rename.yaml` (1-line regex tightening in URL `skip_contexts:`)
- `.shepherd/update-cycle-smoke/progress.md` (triage rows for both tests)

**Estimated scope:** S.

**Exit gates (UCS-AC-*):** Closes UCS-AC-2 for Cluster 2, contributes to UCS-AC-3 (real bug fixed via argo-rename.yaml).

**Subagent roles:**
- Implementer: 1.
- Refactorer pass: skip (config-only).
- Architect pass: required — verify no patches were introduced, that the regex change doesn't break leakage/parity, and that the chosen categories match the rationale in standards.md.

---

#### Checkpoint after M3 + M4: **Clean baseline gate (UCS-AC-1 met)**

- [ ] `make build && cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py` exits 0.
- [ ] All 26 originally-failing tests are now in one of: passing / XFAIL'd-with-reason / accepted-inherited-flake / skipped-from-dist.
- [ ] `make leakage-static` passes.
- [ ] `make parity` passes (unchanged from baseline).
- [ ] `make check-upstream-pristine` passes.
- [ ] No new files in `patches/`. (Hard gate per standards.md.)
- [ ] `.shepherd/update-cycle-smoke/progress.md` triage table is complete (one row per originally-failing test or cluster).

---

#### M5: CI job `dist-argo-tests` in `.github/workflows/ci.yml`

**Description:** Add a new job to `.github/workflows/ci.yml` that runs `make build` (producing `dist/argo/`), then creates a **dist-internal** venv at `dist/argo/.venv-test` with **Python 3.11** (matching upstream `tests.yml`, NOT argo's 3.13 used elsewhere — wheel-resolution surface must match upstream's CI), installs `[all,dev]` extras into it, and runs `dist/argo/scripts/run_tests_parallel.py --slice ${{ matrix.slice }}/6` from inside `dist/argo/` via a 6-slice matrix. Visible-but-non-blocking initially. Uses the existing `.github/actions/argo-setup` composite action with `pip-packages: ""` (composite provides `uv` + Python + apt only; the dist-internal venv is created and populated by a follow-on step). Adds test-durations cache restore/save (mirroring upstream `tests.yml` lines 35-40) keyed `argo-test-durations`. Argo's existing `lint`/`typecheck`/`test`/`parity` jobs continue on Python 3.13 unchanged.

**Acceptance criteria:**
- [ ] `.github/workflows/ci.yml` has a new `dist-argo-tests` job declared.
- [ ] Job runs on `pull_request` and `push: branches: [main]`.
- [ ] Job uses `strategy.matrix.slice: [1, 2, 3, 4, 5, 6]`.
- [ ] Each matrix shard, in order: (a) `uses: ./.github/actions/argo-setup` with `pip-packages: ""`, (b) `make build`, (c) `cd dist/argo && uv venv .venv-test --python 3.11 && uv pip install --python .venv-test/bin/python -e ".[all,dev]"`, (d) restore test-durations cache (key `argo-test-durations`), (e) `cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py --slice ${{ matrix.slice }}/6`.
- [ ] A companion `save-durations` job (or step) gated on `if: github.ref == 'refs/heads/main'` saves the updated durations cache after a green run.
- [ ] Job is declared visible-but-non-blocking (no branch-protection promotion in this loop — `## Boundaries → Ask first` gate).
- [ ] CI run on the PR introducing this job is green for all 6 shards on first non-draft run.
- [ ] uv HTTP cache restored across runs (key tied to `dist/argo/pyproject.toml` content hash) to keep `[all,dev]` install time within budget.

**Verification:**
- [ ] PR check: all 6 matrix shards exit 0 on the introducing PR's first non-draft run.
- [ ] Wall-clock per shard ≤ 25 min (if exceeded, reduce `-j` in the runner).
- [ ] No collision with the existing `legacy-image-${LEGACY_TAG}` cache key.

**Dependencies:** M3 + M4 + post-checkpoint clean baseline. (Cannot land before the baseline is green — would gate every PR red.)

**Files likely touched:**
- `.github/workflows/ci.yml` (+1 job; ~50-80 lines).
- `.shepherd/update-cycle-smoke/progress.md` (record CI green-run evidence).

**Estimated scope:** S-M.

**Exit gates (UCS-AC-*):** Closes UCS-AC-5 (CI job exists, runs on push + PR, exits 0), UCS-AC-6 (uses upstream's runner, not a new one).

**Subagent roles:**
- Implementer: 1.
- Refactorer pass: required — verify the new job shares the `argo-setup` composite action correctly without duplicating uv/python setup; verify caching strategy mirrors the existing `parity` job's `actions/cache@v4` pattern.
- Architect pass: required — verify the 6-shard matrix wall-clock + `[all,dev]` install size are within `ubuntu-latest` runner budgets (disk ≈ 14 GB free, minutes per-month under org quota); verify cache key namespacing doesn't collide with `legacy-image-${LEGACY_TAG}`.

---

#### M6: Issue #12 closure + final progress documentation

**Description:** Close GitHub issue #12 (nadicodeai/argo#12) with a comment linking: this loop's `spec.md`, the baseline-run.log path, the triage table, the M5 PR introducing `dist-argo-tests`. Verify `.shepherd/install-update/progress.md` § Phase 3 closure rewording from M3 is final and consistent with the new test job. Update `AGENTS.md` § "Reading order" to mention `.shepherd/update-cycle-smoke/` alongside the existing `.shepherd/install-update/`.

**Acceptance criteria:**
- [ ] `gh issue view 12 --repo nadicodeai/argo` shows state: CLOSED with a comment containing links to the four artifacts above.
- [ ] `AGENTS.md` § "Reading order" or equivalent section mentions update-cycle-smoke.
- [ ] Final `.shepherd/update-cycle-smoke/progress.md` records: closing date, issue-12 URL, M5 PR URL, summary line.

**Verification:**
- [ ] `gh issue view 12 --repo nadicodeai/argo --json state -q .state` returns `CLOSED`.
- [ ] `grep -q update-cycle-smoke AGENTS.md`.

**Dependencies:** M5 (CI job must exist + be green before closing the issue).

**Files likely touched:**
- (GitHub state — issue close + comment)
- `AGENTS.md` (1-line addition).
- `.shepherd/update-cycle-smoke/progress.md` (final closure section).

**Estimated scope:** XS.

**Exit gates (UCS-AC-*):** Closes UCS-AC-7 (issue #12 closed with linked artifacts), UCS-AC-8 (no fake servers / pexpect added — verifiable by diff inspection).

**Subagent roles:**
- Implementer: 1 (coordinator-level work; could be done directly).
- Refactorer pass: skip.
- Architect pass: required — final hardening pass (see Phase 3).

---

### Phase 3 — Completion

#### M7: Final architect hardening across the full diff

**Description:** Architect agent reviews the complete diff from Phase 2 (all M1-M6 commits), runs every standards-defined verification command, and produces a verdict + any final findings.

**Acceptance criteria:**
- [ ] Architect runs all of: `ruff check .`, `ty check overlay/ tools/`, `make build`, `make leakage-static`, `make parity`, `make check-upstream-pristine`, `cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py`. All exit 0.
- [ ] Architect produces a verdict in `.shepherd/update-cycle-smoke/progress.md` § Final Verdict.
- [ ] If architect requests changes, implementer repair cycle runs (max 3 iterations per Shepherd). After 3, present blocking findings to Vadim.

**Verification:**
- [ ] All verification commands exit 0 as above.
- [ ] Architect verdict = approved.

**Dependencies:** All of M1-M6.

**Files likely touched:**
- `.shepherd/update-cycle-smoke/progress.md` (final verdict section).
- Possibly small targeted fixes from architect findings (in `overlay/` / `argo-rename.yaml`).

**Estimated scope:** S to M depending on findings.

**Exit gates (UCS-AC-*):** Final verification of all UCS-AC-1..8.

---

#### M8: Cleanup + final report

**Description:** Remove non-main git worktrees used by Phase 2 dispatch. Delete merged feature branches. Produce final report covering: what shipped, milestone evidence, accepted limitations, deferred work (live-e2e for a future loop).

**Acceptance criteria:**
- [ ] `git worktree list` shows only `main`.
- [ ] All Phase-2 feature branches deleted (or kept open per Vadim's preference).
- [ ] Final report at `.shepherd/update-cycle-smoke/final-report.md` (or appended to `progress.md`) covers: shipped (M1-M6 summary), evidence (CI run URLs, log paths), limitations (XFAIL count + reasons), deferred (live-e2e moved to follow-up issue).

**Verification:**
- [ ] `git worktree list | wc -l` returns 1.
- [ ] Final report exists.

**Dependencies:** M7.

**Files likely touched:**
- `.shepherd/update-cycle-smoke/progress.md` or `.shepherd/update-cycle-smoke/final-report.md`.

**Estimated scope:** XS.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Moving the 4 build-tool tests to repo-root `tests/` (M1) exposes `from argo_sync.*` imports that worked only post-rename. | Medium — M1 implementer hits ImportError on first run. | Rewrite the imports to `hermes_sync.*` (consistent with `tests/test_verify_no_leakage.py` and the rest of repo-root `tests/`); sys.path-injection pattern from `tools/rebrand.py` lines 34-40 is the reference. Likely 1-2 lines per file. |
| URL `skip_contexts:` regex tightening in M4 inadvertently re-enables rename for tokens that previously needed protection (real upstream URLs). | Medium — could break `make parity` or `make leakage-static`. | After the regex change, re-run the full `make build && make leakage-static && make parity` triad. Pre-commit gate. |
| Cluster 2 `test_ntfy_plugin` turns out to be R-category (a real rebrand bug needing a patch). | Low — adds 1 patch, breaching "zero new patches" target. | Diagnosis already shows asyncio-flake symptoms unrelated to rename. If on closer reading the implementer reclassifies as R requiring a patch, escalate to Vadim per standards.md `Boundaries → Ask first`. |
| 5% XFAIL ceiling hit (~1,303 tests) | High — would invalidate the loop's assumption that 99.9% pass rate is real. | Architect pass after M3 explicitly checks the XFAIL count. If approaching 5%, loop is paused and a follow-up scoped to "the rebrand engine is missing X common patterns." |
| `[all,dev]` install in the new CI job pulls heavy optional backends (whisper, modal, daytona, anthropic, …) and inflates wall-clock or runner disk. | Medium — could exceed runner disk on `ubuntu-latest` (~14 GB free). | Cache the `uv` HTTP cache (`~/.cache/uv`) keyed on `dist/argo/pyproject.toml` content hash. If runner-disk pressure persists, switch the dist venv to `[dev]` only and add an opt-in `[all]` matrix dimension. |
| 6-shard CI matrix in M5 hits wall-clock limits per shard | Low — upstream uses the same shape successfully. | If a shard exceeds 25 min wall-clock, reduce parallelism in `run_tests_parallel.py` (`-j` flag) inside that shard. |
| `dist/argo/conftest.py` (added by M2 overlay) interacts unexpectedly with `dist/argo/tests/conftest.py` (the rebranded upstream conftest, ~31 KB with autouse fixtures for env-var unset / ARGO_HOME isolation). | Low — pytest layers conftests root-down so order is deterministic. | M2's unit test (`tests/test_overlay_xfail_hook.py`) exercises both conftests together against a fixture pytest session. |
| Issue-12 has new comments / discussion since spec was written | Low | M6 dispatch runs `gh issue view 12` and `gh issue list --repo nadicodeai/argo --state open` immediately before closing to confirm canonical location and latest context; if new context exists, surface to Vadim before closing. |

## Open Questions

(All resolved during Spec / Standards. Listed here so reviewers can confirm none are open.)

- LLM provider for live-e2e: **deferred** — live-e2e is now out-of-scope for this loop.
- TUI driver choice (`pexpect` vs `tui_gateway`): **deferred** — same.
- Promote `dist-argo-tests` to required-on-main: **deferred to follow-up** per standards.md `Boundaries → Ask first`.

## Verification (planning gate, not Phase 2)

- [x] Every task has acceptance criteria.
- [x] Every task has a verification step with commands runnable in this repo.
- [x] Task dependencies are identified and ordered correctly (M1, M2 parallel; M3 needs M2; M4 needs M2; M5 needs M3+M4; M6 needs M5; M7 needs M1-M6; M8 needs M7).
- [x] No task touches more than ~5 files (most touch 1-3).
- [x] Checkpoints exist between major phases (after M1+M2, after M3+M4).
- [x] Plan saved to `.shepherd/update-cycle-smoke/plan.md`.
- [x] Up-the-hill plan review round 1: REVISED → applied → READY. See § "Plan Editor Verdict" below.
- [ ] Vadim sign-off (final gate).

## Plan Editor Verdict

### Round 1 — 2026-05-28 — REVISED

Strategic problems found in plan draft #1 and the remediation applied:

1. **M1 architecture was wrong.** The 4 "build-tool" tests are overlay-owned files copied verbatim by `tools/build.py:_copy_overlay()`, NOT upstream files passing through the rename engine. The fix is a 4-file move (overlay/tests/ → tests/) + import rewrite (argo_sync → hermes_sync), not a `tools/rebrand.py` extension or an `argo-rename.yaml` skip primitive. The engine has no "drop file" primitive — `RenameConfig.exceptions:` only protects file contents, not file presence. **M1 rewritten accordingly.**

2. **M4 "Cluster 2 one-offs" was underspecified.** Read of the baseline log showed `test_env_loader` is a real R-category rebrand bug (engine missed a `HERMES_` token inside a multi-line fixture string because the URL `skip_contexts:` regex is too greedy), and `test_ntfy_plugin` presents as an asyncio inherited flake. **Diagnosis pre-baked into the M4 description** so the implementer does not re-do the read.

3. **M5 underspecified the dist-internal venv.** Must be `dist/argo/.venv-test`, not repo-root `.venv`. Must use Python 3.11 matching upstream `tests.yml` (wheel-resolution parity). M5 also missed the durations-cache restore/save jobs upstream uses for balanced slicing. **Both addressed in revised M5.**

4. **Risk table missing items:** `skip_contexts:` regex regression, `[all,dev]` install size on runner disk, overlay conftest interaction with the rebranded upstream conftest. **All three added.**

5. **Path & boilerplate fixes:** M2 manifest path rationale added (overlay root vs `overlay/tests/`); plan-editor verification removed reference to `actionlint` (not installed in this repo).

Verdict after round 1: **REVISED**. Plan now reflects ground-truth and is ready for Vadim sign-off.

### Round 2

Not run — round 1 produced a self-consistent plan with no open architecture/contract/sequencing problems. If Vadim requests refinement on review, round 2 can be dispatched. The 5-round ceiling per `plan` skill applies.

### Final verdict: READY (after round 1 revisions applied).
