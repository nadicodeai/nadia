# update-cycle-smoke — Spec

Make argo's tests run, like Hermes's do. That's it.

GitHub issue: https://github.com/nadicodeai/issues/12 (was about live e2e + FakeTelegramServer — superseded by this spec; will be closed in favor of a follow-up issue once Phase 2 lands).

## Confirmed Intent

Locked input. Confirmed by Vadim 2026-05-28 ("yes this is what I want yes") and re-affirmed in the same session after a deep interview-me pass exposed that the whole loop had been scoped wrong. Vadim's words at the inflection point:

> *"I just wanted an Argo agent, man. I rebranded Hermes, which is called Argo instead of Hermes, and it just works, and it builds, and it runs tests. I don't know what else to ask for, man."*

Translated:

- **Outcome:** The 26,075 upstream unit tests that the rebrand engine produces under `dist/argo/tests/` actually RUN and PASS, in CI, on every push. Just like Hermes runs them on every push for its own tree. No new test infrastructure. Same runner upstream uses (`scripts/run_tests_parallel.py`), pointed at the renamed tree.
- **User:** Argo CI / the project itself. Not Vadim.
- **Why now:** Audit during the loop revealed: tests get RENAMED by the rebrand engine, end up in `dist/argo/tests/`, and **nobody runs them anywhere**. The foundation loop chose `make parity` (surface diff against the legacy image, ~7 CLI surfaces) as the proxy for "rebrand survived." That covers ~0.04% of the test surface. The first test we ran out of 26,075 found a real bug (`_cmd_update_pip` is reachable when argo is pip-installed, but argo isn't published to PyPI — install would 404).
- **Success:** `pytest dist/argo/tests/` (or upstream's `scripts/run_tests_parallel.py` driving it) is green in CI on every push and PR. Failures we found during baseline are either fixed (real bugs / rebrand bugs) or XFAIL'd with a written reason (legitimately-differs-from-upstream-because-rename).
- **Constraint:** Argo behaves exactly like Hermes. Use the same test runner upstream uses. Don't invent argo-specific test infrastructure. If a test would have caught a rebrand bug on Hermes, it should catch it on argo too.
- **Out of scope (this loop):** Live e2e against a real LLM provider. FakeTelegramServer. New harnesses. `pexpect`-driving the TUI. Any test infrastructure beyond what upstream already wrote. These were all the previous (misunderstood) scope; deferred or dropped.

## Pre-locked decisions

(See `.shepherd/update-cycle-smoke/progress.md` § Decisions Log for full context.)

1. **Argo = Hermes + rename only.** No behavioral or testing-posture divergence beyond what the rename forces.
2. **Use upstream's test runner.** `dist/argo/scripts/run_tests_parallel.py` already exists (rebrand-renamed from `upstream/scripts/run_tests_parallel.py`). It does 6-slice per-file parallelism with ~250ms per file. Argo CI uses this, against `dist/argo/`, NOT a new runner.
3. **Failure triage policy:**
   - **Real bug** (rebrand engine missed a string, customer-visible breakage) → fix in `overlay/` or extend `argo-rename.yaml` / patches; re-run.
   - **Legitimately-differs test** (test asserts on a hermes-specific path/env-var/banner that the rename engine MUST change) → XFAIL with a written reason; track in a manifest analogous to `tests/parity-expected.yml`.
   - **Test broken pre-rename** (upstream test was already flaky / red on upstream's own CI) → mark as inherited-flake; do NOT try to fix; document.
4. **No FakeTelegramServer, no `pexpect`, no live-e2e infrastructure in this loop.** Those were the previous misunderstanding. Drop them. If a real live-e2e becomes warranted later, it gets its own loop.
5. **Issue #12 closes at the end of this loop.** A new issue (cleaner, matching this spec) replaces it if anything's still open.

## What the loop does

In Phase 2:

1. **Baseline run (Vadim's machine, kicked off 2026-05-28).** Install `dist/argo/` with `[all,dev]` extras into `.venv-test`; run `scripts/run_tests_parallel.py` over the full `dist/argo/tests/` tree; capture every pass/fail/error to `.shepherd/update-cycle-smoke/baseline-run.log`. Produce baseline counts.
2. **Triage.** Group failures by category. Decide for each: fix (real bug), XFAIL (rename-induced), or inherited-flake.
3. **Fix.** Either land overlay/patch changes that close the rebrand bugs the tests caught, or wire an XFAIL list (manifest file + a `conftest.py` hook in `overlay/tests/conftest.py`, or a pytest plugin reading the manifest at collection time).
4. **CI job.** Add `dist-argo-tests` job to `.github/workflows/ci.yml`: builds `dist/argo/`, installs `[all,dev]` extras, runs `scripts/run_tests_parallel.py`. Runs on `push` + `pull_request`.
5. **Lock the green state.** Once the job is green, promote to required check on `main` (follow-up; not gating this loop's close).
6. **Issue #12.** Close in favor of a new issue if any defer-from-here items remain.

## Acceptance criteria

| ID | Criterion | How verified |
|---|---|---|
| UCS-AC-1 | Baseline run completes locally on `dist/argo/` with `[all,dev]` deps; counts are captured. | Output at `.shepherd/update-cycle-smoke/baseline-run.log` shows passed / failed / errored / skipped totals. |
| UCS-AC-2 | Every failing test from the baseline is triaged into exactly one of: {real-bug-to-fix, XFAIL-with-reason, inherited-flake-documented}. No silent skips. | A triage table in `.shepherd/update-cycle-smoke/progress.md`; one row per failing test file (or per failure cluster). |
| UCS-AC-3 | Real bugs surfaced by the baseline are fixed via `overlay/` or `argo-rename.yaml` changes (no edits to `upstream/`). | `make build && pytest dist/argo/tests/<file>` exits 0 for each previously-failing test after the fix. |
| UCS-AC-4 | XFAIL-warranted tests are gated by a manifest at `overlay/tests/argo-xfail.yml` (or similar; final path TBD in plan). Each entry has a written reason. | Manifest file exists, loaded by `dist/argo/tests/conftest.py` (or a `conftest_argo.py` overlay), each entry has `reason:` field. |
| UCS-AC-5 | A CI job `dist-argo-tests` exists in `.github/workflows/ci.yml`, runs on `push` to `main` + `pull_request`, and exits 0 with the baseline+fixes+XFAILs in place. | CI run artifact green; job visible in PR checks. |
| UCS-AC-6 | The CI job uses `dist/argo/scripts/run_tests_parallel.py` (upstream's own runner, renamed) — NOT a new argo-specific runner. | Workflow file inspection. |
| UCS-AC-7 | Issue #12 is closed; the loop's outcomes are linked from the closure comment (this spec, baseline run summary, list of bugs fixed, manifest of XFAILs). | `gh issue view 12` shows closed-state with linked artifacts. |
| UCS-AC-8 | No new fake servers, no `pexpect`, no live-e2e harness lands in this loop. | Diff inspection; the only files added are XFAIL manifest, CI job, and overlay/patch fixes for real bugs. |

## Tech stack

Same as the rest of argo (see `AGENTS.md`):

- Python 3.11+, uv, pytest, the test runner upstream already wrote.
- CI: GitHub Actions, `ubuntu-latest`.
- No new deps beyond what `dist/argo/.[all,dev]` already pulls in.

## Boundaries

- **Always:**
  - MUST use `dist/argo/scripts/run_tests_parallel.py` (upstream's runner, renamed) — not a new runner.
  - MUST fix real bugs via `overlay/` or `argo-rename.yaml` — never by editing `upstream/`.
  - MUST give every XFAIL a written reason in the manifest.
  - MUST run the baseline numbers honestly — no cherry-picking, no `-k 'pattern'` filtering.

- **Ask first:**
  - Adding any new CI secret (e.g. LLM provider key for a test that needs one).
  - Promoting the new job to a required check on `main`.
  - Marking more than 5% of tests as XFAIL (suggests a deeper rebrand problem that needs its own loop, not silent skipping).

- **Never:**
  - MUST NOT add FakeTelegramServer, `pexpect`, or any other test infrastructure that upstream doesn't have.
  - MUST NOT skip a failing test without triage; every red goes into the triage table.
  - MUST NOT modify `upstream/`.
  - MUST NOT use mocks beyond what upstream's own tests already use.

## Out of scope (this loop)

| Item | Why deferred |
|---|---|
| Live e2e test against a real LLM provider, real systemd respawn, real `/update` cycle. | Was the previous (misunderstood) scope of this loop. Worth doing eventually, but only AFTER the 26k unit tests are running — anything else is premature optimization. Gets its own loop. |
| Cross-platform installs (macOS, Windows). | Linux-first; same as upstream. |
| Sync-with-upstream verification (does `make sync` produce a still-working tree?). | Separate concern — that's a maintainer-facing flow. Could chain off the new CI job once it's green. |

## Open questions (for the plan step)

1. Where the XFAIL manifest lives — `overlay/tests/argo-xfail.yml` vs alongside `tests/parity-expected.yml`. Plan picks.
2. How the manifest is loaded — pytest plugin vs conftest hook. Plan picks the cheapest.
3. Whether `dist-argo-tests` job runs all 6 slices in matrix or single-slice. Match upstream (matrix 6) unless cost is prohibitive; plan decides.
4. Wall-clock budget if needed for branch-protection promotion. Plan can defer to a follow-up.
