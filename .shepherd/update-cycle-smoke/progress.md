# update-cycle-smoke — Project Progress

Shepherd loop for: closing the **dynamic update cycle** live-coverage gap surfaced post-install-update loop, per `nadicodeai/argo` issue #12.

Sibling to `.shepherd/install-update/` (which delivered IU-AC-1..15 with static + Phase-1-only dynamic coverage). This loop is scoped narrowly to **Fix 1** from the issue: a `runs-on: ubuntu-latest`-native job that exercises `install.sh → argo setup → argo gateway install → argo gateway start → argo update → restart` end-to-end on a real systemd-as-PID-1 host.

Foundation loop = `.shepherd/{spec,plan,progress,standards}.md` (M1..M8 fork architecture).
Install-update loop = `.shepherd/install-update/` (IU-AC-1..15).
This loop = `.shepherd/update-cycle-smoke/` (UCS-AC-1..N, TBD).

## Current Status
**Phase:** 2 — Milestone Loop.
**Current milestone:** M1 + M2 — implementers + M2 refactor merged; architect pass next.
**Current task:** Dispatch architect from merged main to harden M1+M2 slice. Then re-run baseline checkpoint.
**Last action:** M1 (`4a3c82ac6 feat(M1)...`), M1 merge (`00e488f50`), M2 (`a1edf1c8f feat(M2)...`), M2 merge (`040c29ca5`), M2 refactor (`c9866f363 refactor(M2)...`), M2 refactor merge (`a4f6c2711`) all landed on main. Verification on merged main: `make build` PASS, all 4 M1 files absent from `dist/argo/tests/`, `dist/argo/conftest.py` + `dist/argo/argo-xfail.yml` present, `make leakage-static` PASS, `make check-upstream-pristine` PASS, `pytest tests/` 133 passed 4 deselected 0 failures.

### M1 evidence
- 4 files moved from `overlay/tests/` to `tests/` via `git mv`.
- Imports rewired pre-rename (`hermes_sync.*`) for the pure-tooling tests; subprocess targets `dist/argo/argo_cli.main` for the two CLI-driving tests with module-level skipif guards on `dist/argo/` presence.
- Scope expansion flagged by M1 implementer: replaced 3 stale exception-membership assertions in `test_full_rename_config.py` with current-yaml assertions on `tests/test_full_rename_config.py`, `*/_rename_defaults.py`, `.argo/**`. → For architect review.
- Untracked artifact: `.shepherd/smoke-run-*.log` written by the help-version smoke harness; should likely be gitignored. → For architect review.

### M2 evidence
- `overlay/argo-xfail.yml` (empty manifest with documented schema header).
- `overlay/conftest.py` (~85 lines post-refactor; rootdir conftest with `pytest_collection_modifyitems` hook applying `pytest.mark.xfail(strict=False)` to matching nodeids).
- `tests/test_overlay_xfail_hook.py` (6 pytester-based tests covering: entry application, empty-list no-op, missing-manifest no-op, malformed-YAML no-op, stale-entry-silently-inert, non-match-leaves-others-alone).
- M2 refactor: deduped schema doc from conftest (manifest header is canonical); sharpened the non-match test to include a stale-entry case.

## Phase 1 Gate Tracker

| Step | Artifact | Gate | Status |
|---|---|---|---|
| 1. Intent | `spec.md` § Confirmed Intent | Vadim sign-off | ✅ 2026-05-28 ("yes this is what I want yes") |
| 2. Spec | `spec.md` body | Vadim sign-off | ✅ 2026-05-28 ("we are sound, we are good, we are there ... let's finish this up and go ahead"; spec pivoted mid-step from live-e2e to run-upstream-tests-on-dist) |
| 3. Standards | `standards.md` | Recorded | ✅ 2026-05-28 |
| 4. Plan | `plan.md` + plan-skill READY verdict (round 1 REVISED → applied → READY) | Vadim sign-off | ✅ 2026-05-28 ("the plan is ready Is everything ready? Can I start this in a new session?" — implicit sign-off; resume-handoff requested) |
| 5. Setup Close | This section | Recorded | ✅ 2026-05-28 — see § "Setup Close" below |

## Setup Close — 2026-05-28

**Phase 1 complete.** All five gates passed. Loop is parked here per Vadim's directive ("start this in a new session"). Phase 2 begins in a fresh session when Vadim chooses; this session does NOT enter Phase 2 autonomously.

### Verification state at setup close

| Item | Status | Evidence |
|---|---|---|
| Spec is sign-off-complete | ✅ | Vadim 2026-05-28; spec.md § Confirmed Intent locked; UCS-AC-1..8 defined |
| Standards recorded | ✅ | standards.md exists; triage categories R/X/S/F/P defined; fix-location hierarchy locked |
| Plan returns READY | ✅ | plan-editor round 1 verdict in plan.md § Plan Editor Verdict |
| Baseline numbers captured | ✅ | progress.md § Baseline run summary; baseline-run.log @ `.shepherd/update-cycle-smoke/baseline-run.log` |
| Foundation architecture reviewed | ✅ | progress.md § Foundation architecture review 2026-05-28 (Debian/Iceweasel/git-subtree external grounding) |
| No new dependencies that need approval | ✅ | `[all,dev]` install in `dist/argo/.venv-test` already used in baseline; no new deps for Phase 2 |
| All upstream tests run locally (one-shot baseline) | ✅ | 1,234 of 1,244 files green; 7 files with 26 failing tests + 3 collection errors all triaged into cluster table |

## Phase 2 dispatch order (handoff to next session)

When the next session starts and Vadim signals to enter Phase 2:

1. **First action: re-read** `.shepherd/update-cycle-smoke/{spec,standards,plan,progress}.md` and `AGENTS.md`. Then read `~/.claude/projects/-home-vadim-Code-argo/memory/MEMORY.md` for foundational rules ([[project-argo-rename-only]], [[feedback-run-upstream-tests-on-dist]]).
2. **Round 1 (parallel-eligible):** Dispatch **M1** (move 4 build-tool tests) and **M2** (XFAIL infrastructure) in separate worktrees. Both are S-sized, independent, no shared file contention.
3. **Verify + merge M1 and M2** per Shepherd milestone loop (implementer verification → refactorer if file-touching → architect pass).
4. **Checkpoint after M1+M2:** Re-run baseline. Expect 23 failures (Cluster 1) + 2 failures (Cluster 2), 0 collection errors.
5. **Round 2:** Dispatch **M3** (XFAIL Cluster 1) — single implementer.
6. **Round 3:** Dispatch **M4** (Cluster 2 fix + triage) — single implementer.
7. **Checkpoint Clean baseline gate (UCS-AC-1 met):** Re-run baseline, exit 0.
8. **Round 4:** Dispatch **M5** (CI job `dist-argo-tests` in ci.yml).
9. **Round 5:** Dispatch **M6** (close issue #12 + final docs).
10. **Phase 3:** Architect final hardening (M7) → cleanup (M8) → final report.

Estimated Phase 2 wall-clock: 4-6 dispatch rounds; ~6-10 hours subagent time given S-sized milestones and pre-baked diagnoses.

### How a new session resumes

In a fresh Claude Code session at `/home/vadim/Code/argo`, the simplest resume prompt is:

> *"Resume the update-cycle-smoke shepherd loop from `.shepherd/update-cycle-smoke/`. Phase 1 is closed; enter Phase 2 starting with the milestone loop. Dispatch M1 and M2 in parallel worktrees per the plan. The shepherd skill knows the protocol."*

The new session will:
- Invoke the `shepherd` skill.
- Read the four state files.
- Begin Phase 2 dispatching M1 + M2.
- Stop only when Phase 3 architect approves OR a blocker requires Vadim input.

### Open punch list (deferred from this loop)

| Item | Where it goes | Why deferred |
|---|---|---|
| Live e2e against real LLM provider + `/update` from TUI + real systemd respawn | Future loop (separate `.shepherd/<new-name>/`) | Cheapest answer to "does argo work" turned out to be "run the 26k tests upstream wrote." Live e2e is the SECOND line of defense and only worth doing once those tests are green. Spec.md § Out of scope tracks. |
| Promote `dist-argo-tests` to required check on `main` | Follow-up issue after green streak | Standards.md `Boundaries → Ask first`; Vadim's call once stability observed. |
| Sync-regression CI (does `make sync` produce a still-working tree?) | Future loop | Maintainer-facing; could chain off the new `dist-argo-tests` job once it's green. Beyond this loop. |
| Cross-platform installs (macOS, Windows) | Future loop | Linux-first; same as upstream. |

## Baseline run summary (captured during Spec step)

| Metric | Value |
|---|---|
| Test files in `dist/argo/tests/` | 1,244 |
| Test cases collected | 26,075 |
| Files with failures | 7 (26 individual tests) |
| Files with collection errors | 3 |
| Files passing completely | 1,234 |
| Implied test-case pass rate | ~99.9% (~25,974 of 26,075) |
| Wall-clock | ~6 minutes (16:33–16:40 on Vadim's machine, 2026-05-28) |
| Log | `.shepherd/update-cycle-smoke/baseline-run.log` |
| Runner | `dist/argo/scripts/run_tests_parallel.py` (upstream's runner, rebrand-renamed) |

Cluster summary of the 26 individual failures:

| Cluster | Files | Failures | Likely category |
|---|---|---|---|
| 1. `cmd_update` pip-vs-git path | `tests/argo_cli/test_cmd_update.py`, `test_update_autostash.py`, `test_update_yes_flag.py`, `test_update_zip_symlink_reject.py` | 23 | X — XFAIL (argo not on PyPI per IU-FR-13; pip path is dead code for properly-installed argo customers) |
| 2. one-offs | `tests/argo_cli/test_env_loader.py`, `tests/gateway/test_ntfy_plugin.py` | 2 | TBD — read failures during triage |
| 3. Build-tool tests shipped to dist by mistake | `tests/test_deployment_smoke.py` (FileNotFoundError on `argo-rename.yaml`); collection errors on `tests/test_cmd_argo_doctor.py`, `tests/test_full_rename_config.py`, `tests/test_sync_resume.py` | 1 + 3 collection errors | S — Skip-from-dist via `argo-rename.yaml` skip rule |

## Foundation architecture review 2026-05-28

Recorded during Spec step. External grounding (Debian quilt, Iceweasel post-mortem, git-subtree docs) confirms the fork architecture (pristine `upstream/` subtree + quilt `patches/` + additive `overlay/` + build-time `argo-rename.yaml` engine + reproducible builds) is **industry-best-practice** for a long-lived rename-only fork. Build-time rebrand engine is **better than Iceweasel's patch-on-every-string-rename model** because it limits patch-conflict surface on sync to behavioral patches only (~9 today) rather than every string-rename patch.

Sources reviewed:
- [UsingQuilt — Debian Wiki](https://wiki.debian.org/UsingQuilt)
- [The end of the Iceweasel Age — LWN](https://lwn.net/Articles/676799/)
- [Git Subtree: Alternative to Submodule — Atlassian](https://www.atlassian.com/git/tutorials/git-subtree)
- [Friendly fork management — GitHub Blog](https://github.blog/2022-05-02-friend-zone-strategies-friendly-fork-management/)

Gaps identified during review (operational, NOT architectural):
1. The 26k upstream tests are renamed by the engine but not run by CI. **This loop closes it.**
2. `make parity` covers ~7 CLI surfaces — was meant to complement, not replace, running upstream tests. Returns to complementary role once `dist-argo-tests` job lands.
3. No CI for sync regressions (`make sync` is local-only). Beyond this loop.
4. `_cmd_update_pip` documented as unreachable per IU-FR-13; baseline run proves it IS reachable when argo is pip-installed. Doc drift; will be reconciled during Phase 2 triage.

## Decisions Log

### Decision: Argo = Hermes + rename only — no behavioral divergence
- Recorded: 2026-05-28 during the Intent interview.
- Vadim's words: "I'm just trying to have my agent which is called Argo, she's exactly like Hermes, behaves like Hermes, updates like Hermes, everything happens like Hermes, but it's just called Argo."
- Rationale: The fork's value proposition is "Hermes but called argo, on our daily release cadence, at our public URL." Anything beyond that is scope creep and divergence-by-accident.
- Trade-off accepted: Argo cannot have argo-specific testing infrastructure unless it's directly verifying a rename-specific risk.
- See memory: `project-argo-rename-only`.

### Decision: Issue #12 is suspect, not load-bearing
- Recorded: 2026-05-28 during the Intent interview.
- Vadim's words: "the previous session that had the misunderstanding probably wrote the issue so we might as well review the issue I'm not saying that the issue is correct."
- Rationale: The same drift this interview surfaced (argo-specific CI infrastructure beyond what Hermes has) also produced issue #12's "Fix 1" proposal. Treat the issue as a hypothesis to validate against the confirmed intent, not a fixed input.
- Trade-off accepted: This loop's Phase 2 milestones include a "review issue #12 + close or rewrite" step. The spec/plan are NOT constrained to match issue #12's acceptance criteria verbatim.

### Decision: Slash-command transport for the update test = TUI/CLI, NOT Telegram fake
- Recorded: 2026-05-28 during the Intent interview.
- Vadim's words: "you can use the clee on this machine because it would be easier obviously than just hook up every single telegram stuff because we know that when we invoke a slash command we can invoke it from the tui like locally or like from telegram it's the same thing but the behavior is what really matters."
- Rationale: The rename-only rule + the "no fakes" rule together imply: the test must exercise a REAL transport, but the Telegram transport itself is upstream's responsibility. TUI/CLI invokes the same slash-command handler via the same in-process code path; argo's rebranded `/update` behavior is verified identically.
- Trade-off accepted: This test will NOT exercise the Telegram-network surface (PTB long-poll, conflict recovery, base_url config). That surface is upstream's; argo inherits it via the rename engine. Any rebrand bug specific to Telegram message-text rendering would not be caught here — accepted because the rename engine treats slash-command response text identically regardless of transport.

### Decision: Drop the FakeTelegramServer from this loop's design
- Recorded: 2026-05-28.
- Derived from the previous two decisions. Vadim's words: "no fakes."
- The `tests/update_smoke/fake_telegram.py` fixture remains in the repo for any future loop that wants it; this loop does not consume it.

### Decision: PIVOT — drop the entire live-e2e scope; this loop is now "run upstream's tests on dist/argo + fix what breaks"
- Recorded: 2026-05-28 (mid-Spec step, after Vadim asked "can you run the tests locally?").
- Vadim's framing: *"I just wanted an Argo agent, man. I rebranded Hermes, which is called Argo instead of Hermes, and it just works, and it builds, and it runs tests."* Followed by *"Yeah, run the tests and fix the tests."*
- Rationale: A live audit during this loop's own Spec step revealed that `dist/argo/tests/` contains 26,075 renamed upstream tests and zero of them are run by CI. The first non-trivial test we executed surfaced a real bug. The original live-e2e framing was solving a smaller problem (a single restart-cycle gap) while ignoring a much bigger problem (24k+ untested tests on disk).
- Trade-off accepted: The original "test on Telegram-style slash command, real LLM call" e2e is deferred entirely. Once the renamed unit test suite is green in CI, that may become the right *next* loop. For now, the loop's success criterion is: argo's pytest suite runs and is green, same as Hermes's does.
- See: [[feedback-run-upstream-tests-on-dist]] memory.

### Decision: Issue #12 was scope-creep dressed up as a CI gap report
- Recorded: 2026-05-28.
- The issue (written by the misunderstood previous session) proposed a `FakeTelegramServer`-based CI job to close the dynamic-restart-cycle gap. The deeper problem — that 26k renamed unit tests sit unused on disk — was invisible to that framing.
- Disposition: Close issue #12 at this loop's completion. Replace (if needed) with a tighter issue that points at the new "run-upstream-tests-on-dist" job and any defer-from-this-loop items.

## Verification Evidence

| Item | Status | Evidence |
|------|--------|----------|
| Unit tests | n/a (no unit-test surface — this loop ships a CI job + shell harness) | will record once M-level harness ships |
| Integration/e2e checks | n/a yet | this loop IS the integration check; success = job exit 0 on `runs-on: ubuntu-latest` |
| Lint/type checks | n/a (shell + YAML only) | `actionlint` / `shellcheck` if added (TBD in standards) |
| Hardening checks | n/a yet | architect pass at completion |

## Inputs

- **Issue:** https://github.com/nadicodeai/argo/issues/12 (open as of 2026-05-28).
- **Released artifact under test:** https://github.com/nadicodeai/argo/releases/tag/v2026.5.28.
- **Sibling-loop closure framing:** `.shepherd/install-update/progress.md` § Phase 3 closure (IU-AC-6 currently mis-framed as "needs systemd in container" — this loop also reworks that note).
- **Existing harnesses we extend, not replace:**
  - `tests/install_smoke/run.sh` (Docker, ubuntu:22.04, --skip-setup).
  - `tests/update_smoke/run.sh` (Docker, ubuntu:22.04, --skip-setup, asserts IU-AC-9/10/11 statically).
  - `tests/update_smoke/run_telegram.sh` (currently exits 77 — skipped).
  - `tests/update_smoke/fake_telegram.py` (stdlib `http.server` FakeTelegramServer fixture).

## Decisions Log
_(populated during the Setup phase as gates are passed)_

## Architecture State
_(populated post-Setup)_
