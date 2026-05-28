# update-cycle-smoke — Project Standards

Project rules, role-owned commands, and accepted waivers for the **update-cycle-smoke** Shepherd loop. Subagents MUST read this before editing.

Foundation rules in repo `AGENTS.md` and `.shepherd/standards.md` apply unmodified. The rules below are loop-specific additions.

## Code Quality

(Most rules carry forward from the foundation `.shepherd/standards.md` and `AGENTS.md`. Loop-specific tightenings:)

- **MUST prefer `argo-rename.yaml` > `overlay/` > `patches/` for every fix surfaced by the baseline run.** The cost hierarchy is: rename-yaml change = 1 line of YAML, zero sync cost; overlay file = additive, zero sync cost; patch = real sync-tax (forward-port on every upstream change to the same file). Choose the cheapest tool that does the job. See [[project-argo-rename-only]] and [[feedback-run-upstream-tests-on-dist]].
- **MUST give every XFAIL a written `reason:` field** in the manifest. Reason MUST cite either (a) a foundation-loop spec FR/IU-FR/IU-AC the test conflicts with intentionally, or (b) an upstream-test-that-asserts-on-hermes-specific-state where rename divergence is unavoidable. "Test is flaky" is NOT a valid reason for XFAIL — flaky tests go in the inherited-flake category and stay un-XFAIL'd until upstream fixes them.
- **SHOULD NOT add a new patch unless rename-yaml + overlay genuinely cannot solve the problem.** If a patch is needed, the patch's commit message MUST explain why neither lower-cost tool worked, and the patch MUST carry an `assertions:` entry per FR-14.
- **MUST NOT modify `upstream/` for any reason.** CI's `upstream-pristine` job (FR-15 / C3) blocks this. Same as foundation loop.

## Testing

| Surface | Command | Notes |
|---|---|---|
| Build the renamed tree | `make build` | Produces `dist/argo/`. Required before any test run. |
| Run upstream's test suite on `dist/argo/` (the headline command for this loop) | `cd dist/argo && .venv-test/bin/python scripts/run_tests_parallel.py` | Upstream's own runner, rebrand-renamed by the engine. Per-file isolation, default 6-slice parallelism via `os.cpu_count()`. **NEW dependency on local `[all,dev]` install in `dist/argo/.venv-test`** — first run installs; subsequent runs reuse. |
| Run a single test file (triage) | `cd dist/argo && .venv-test/bin/pytest tests/<file>.py -x -q --tb=short` | Use during triage to reproduce a single failure. |
| Lint | `ruff check .` (from repo root) | Inherited from foundation. |
| Type-check | `ty check overlay/ tools/` | Inherited from foundation. |
| Leakage scan | `make leakage-static` | Static scan that `dist/argo/` has no `hermes` leaks. Inherited from foundation. |
| Parity | `make parity` | CLI-surface diff vs legacy image. Inherited. **Reduces in importance once `dist-argo-tests` is green** — unit tests cover what parity was a stand-in for. |
| Upstream-pristine | `make check-upstream-pristine` | FR-15 gate. Inherited. |

- **Unit tests:** the 26,075 renamed upstream tests are the unit-test surface for this loop. Their pass-rate (post-fixes + XFAILs) is the loop's success measure.
- **Integration/e2e:** not configured by this loop. The original live-e2e scope was dropped per the Spec pivot decision (2026-05-28). Future loops may add e2e.
- **Hardening:** architect's prerogative at the end of Phase 2. Likely `ruff check`, `ty check`, `make leakage-static`, `make parity`, and a final clean `scripts/run_tests_parallel.py` run.

**Accepted limitations:**

- Tests requiring optional backends installed via `tools/lazy_deps.py` (anthropic, telegram-bot, voice/whisper, edge-tts, modal, daytona, …) will fail with `ImportError` unless the backend is `pip install`ed into `.venv-test`. **Accepted** for the baseline run; backend-specific tests get an XFAIL with reason "requires opt-in backend; lazy-loaded at runtime per upstream policy."
- The 3 collection-error tests (`test_cmd_argo_doctor`, `test_full_rename_config`, `test_sync_resume`) reference build-tool inputs (`argo-rename.yaml`) or unrenamed modules (`sync`) that don't ship in `dist/argo/`. **They're build-tool tests shipped into the customer tree by mistake.** Fix via `argo-rename.yaml` skip/exception rules, NOT by patching upstream.
- This loop does NOT promote the `dist-argo-tests` CI job to a required check on `main`. That's a follow-up after a green-streak — Vadim sign-off required (per `## Boundaries → Ask first` in `spec.md`).

## Architecture

The fork architecture (pristine upstream subtree + quilt patches + overlay + build-time rebrand engine) is **good and externally-validated** (see `.shepherd/update-cycle-smoke/progress.md` § Decisions Log → "Foundation architecture review 2026-05-28"). Loop-specific architectural rules:

- **MUST exit `Phase 2` with NO new `patches/<NN>-*.patch` files unless explicitly justified** in the plan's per-milestone dispatch prompt. Default is zero new patches. The plan's exit table tracks any added.
- **MUST write the XFAIL manifest to `overlay/tests/argo-xfail.yml`** (path TBD by plan; same shape as `tests/parity-expected.yml`). Manifest MUST be loaded via a `conftest.py` hook or pytest plugin sitting in `overlay/tests/` — NOT in `dist/argo/tests/` directly (which would be lost on rebuild).
- **MUST register the new CI job as `dist-argo-tests` in `.github/workflows/ci.yml`**, NOT in a separate workflow file. Reasons: (a) discoverability for future maintainers, (b) shares the `argo-setup` composite action, (c) consistent with existing `install-smoke` / `update-smoke` jobs that live in `ci.yml`.
- **MUST NOT introduce a new test runner.** Use `dist/argo/scripts/run_tests_parallel.py` (upstream's runner, renamed). Per UCS-AC-6 in the spec.
- **MUST treat issue #12 as the loop's closing artifact.** Close it (with a comment linking the spec + baseline summary + bug-fix commits + XFAIL manifest) as part of the final architect pass. New tighter issue may replace it if any defer-from-here items remain — Vadim approval required for the new issue's contents.
- **Foundation invariants carry forward:** `upstream/` untouched, `dist/argo/` regenerated each build, `.sync-workdir/` and `dist/argo/` gitignored, reproducible builds (`SOURCE_DATE_EPOCH`) preserved, patches use `hermes`-named paths and the engine renames at build.

## Triage Categories (for Phase 2)

Every failing test from the baseline MUST be triaged into exactly one of:

| Category | Fix location | Example from baseline |
|---|---|---|
| **R — Real rebrand bug** | `overlay/` patch + tests, or `argo-rename.yaml` rename rule | A string the engine missed, an import path that points at a hermes-only module. |
| **X — XFAIL, rename-induced** | `overlay/tests/argo-xfail.yml` entry with `reason:` field | A test that asserts the install method is "pip" because upstream uses pip; argo uses git install via install.sh per IU-FR-13. Test asserts on dead code from argo's perspective. |
| **S — Skip-from-dist (build-tool test) ** | `argo-rename.yaml` skip rule (the file never ends up in `dist/argo/tests/`) | The 3 collection-error tests that reference `argo-rename.yaml` itself or the `sync` module. |
| **F — Inherited flake (already red on upstream)** | Document in `progress.md` triage table; do NOT XFAIL | Test that's red on upstream's own CI — not our problem to fix, but track. |
| **P — Patch-required behavioral change** | `patches/<NN>-*.patch` + `patches/asserts/<name>.txt` + entry in `patches/asserts/manifest.txt` | Only when none of the above work. Each P-category fix is a permanent sync-tax — minimize. |

Every entry in the triage table MUST identify category, fix location, and (for X / F) the written reason.

## Boundaries

- **Always:**
  - MUST run the full `scripts/run_tests_parallel.py` baseline before triage — no cherry-picking.
  - MUST commit the triage table to `progress.md` before opening any fix PR.
  - MUST run `make leakage-static` + `make parity` + `scripts/run_tests_parallel.py` post-fix to verify no regression.
- **Ask first:**
  - Adding any new `patches/<NN>-*.patch` (each one is a forever sync-tax).
  - Adding more than 5% of tests as XFAIL (~1,300+ tests) — likely indicates a deeper rebrand problem that needs its own loop.
  - Promoting `dist-argo-tests` to required-on-main.
  - Adding any new CI secret (e.g. LLM provider key) — this loop does not need one.
- **Never:**
  - MUST NOT edit `upstream/`.
  - MUST NOT skip a failing test without triage.
  - MUST NOT use a runner other than `scripts/run_tests_parallel.py`.
  - MUST NOT introduce FakeTelegramServer, `pexpect`, or any live-e2e infrastructure in this loop (deferred — see spec § Out of scope).
