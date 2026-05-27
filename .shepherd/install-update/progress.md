# install-update — Project Progress

Shepherd loop for: native install path + working `/update` UX for `nadicodeai/argo`.

Foundation loop (the M1–M8 build of the patch+overlay fork architecture) lives in `.shepherd/{spec,plan,progress,standards}.md`. This loop is scoped narrowly to the install/update gap that surfaced post-foundation.

## Current Status
**Phase:** Setup — CLOSED 2026-05-28. Ready to enter Phase 2 (Milestone Loop) on Vadim's go-ahead.
**Last action:** All Phase 1 gates passed. Setup Close gate (Step 5) executed; this entry records it. Loop is parked here per Vadim's directive ("you stop before phase 2 please"). Phase 2 begins on explicit Vadim signal.

## Phase 1 Gate Summary

| Step | Artifact | Gate | Status |
|---|---|---|---|
| 1. Intent | `spec.md` § Confirmed Intent | Vadim sign-off | ✅ 2026-05-27 ("yes") |
| 2. Spec | `spec.md` body (v2) | Vadim sign-off | ✅ 2026-05-28 ("1. ok.") |
| 3. Standards | `standards.md` | Vadim sign-off | ✅ 2026-05-28 ("we are good lets go") |
| 4. Plan | `plan.md` + 5-round up-the-hill review | Plan returns READY + Vadim sign-off | ✅ 2026-05-28 (R5 blockers resolved; plan verdict = READY) |
| 5. Setup Close | This section in `progress.md` | Recorded | ✅ 2026-05-28 |

## Architecture decisions (locked)

- **Single repo, single brand surface.** `nadicodeai/argo` made public; `main` is workshop (upstream/, patches/, overlay/, tools/, .shepherd/); long-lived `release` branch on same repo carries the runnable renamed `dist/argo/` tree, force-pushed by CI with `--force-with-lease`.
- **install.sh and cmd_update target `origin/release`** via the renamed installer at `https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh`.
- **CalVer release tags** `v<YYYY>.<M>.<D>` (same-day suffix `.2`/`.3`); `__version__` bumped per-release inside `dist/argo/argo_cli/__init__.py` (gitignored on main; lives only in tarballs + release branch); `upstream/hermes_cli/__init__.py` source stays at upstream's value until next sync.
- **Banner format inherited verbatim.** `Argo Agent v<semver> (<calver>)` — same shape as hermes. Spec amended 2026-05-28 to match.
- **No PyPI.** IU-FR-13 codifies the divergence; `_cmd_update_pip` inherited as unreachable code for properly-installed argo customers.
- **`tools/argo_release.py` workshop-side release driver.** Mirrors upstream `release.py` shape but operates from workshop layout; tags HEAD without committing gitignored files; calls `gh release create`.
- **Telegram smoke tests use a fake bot fixture, never the real API.**
- **`OFFICIAL_REPO_URLS` rebrand is load-bearing.** P0 gate via IU-AC-9.

## Verification state at setup close

| Item | Status | Evidence |
|---|---|---|
| Foundation `make build` deterministic | passed | Foundation `.shepherd/progress.md` § Phase 3 closure |
| Foundation `make leakage-static` | passed | Foundation `.shepherd/progress.md` |
| Foundation tests (`pytest tests/`) | passed | Foundation `.shepherd/progress.md` (56/56) |
| Foundation upstream-pristine | passed | Foundation `.shepherd/progress.md` |
| Spec internally consistent post-amendment | passed | This spec amendment 2026-05-28 (B1 resolved) only changes IU-AC-4 + IU-AC-13 regex; no other ACs reference the old regex |
| Plan covers all 15 ACs | passed | Plan exit gates table closes IU-AC-1..15 across M1-M7 |
| Plan returns READY | passed | Plan § Verdict |
| No new dependencies that need approval | passed | All commands are existing or noted as new-in-this-loop |
| `tools/argo_release.py` design fits existing tools/ patterns | accepted | Wrapper mirrors `tools/build.py`, `tools/sync.py` shape (typed errors, UTF-8 explicit, no bare Exception) |

## Phase 2 dispatch order (pre-loaded for resumption)

When Vadim signals to start Phase 2:

1. **M1** (stub removal) — 1 round, Implementer.
2. **M2.1 + M2.2** (repo public + release branch bootstrap) — 1 round, parallel.
3. **M3.1 + M3.2** (OFFICIAL_REPO_URLS + .install_method) — 1 round, parallel after M2.
4. **M4.1** (install.sh default-branch patch) — 1 round, Implementer.
5. **M4.2** (release.yml workflow + tools/release_branch_push.py) — 1 round, Implementer (parallel with M4.1).
6. **M4.3a** (build tools/argo_release.py) — 1 round, Implementer.
7. **M4.3b** (Coordinator runs argo_release.py to tag v2026.5.28) — Coordinator, after M4.1+M4.2+M4.3a.
8. **Checkpoint: MVP COMPLETE.** Coordinator runs manual checklist; presents to Vadim.
9. **M5–M7** (durable cut) — parallel after MVP, ~3 dispatch rounds.

Estimated Phase 2 wall-clock: ~5-8 dispatch rounds for MVP (M1-M4); ~3-5 more for durable (M5-M7). Total ~8-13 rounds, ~4-7 hours subagent time.

## Verification Evidence

| Item | Status | Evidence |
|------|--------|----------|
| Unit tests | pending | overlay/tests/ via pytest (project default) |
| Integration/e2e checks | pending | TBD — likely a clean-VM smoke test |
| Lint/type checks | pending | ruff + ty (project default) |
| Hardening checks | pending | leakage-static + run_assertions (project default) |

## Completed Milestones

(none yet — Phase 1 in progress)

## Decisions Log

- **2026-05-27 — Intent locked.** Customer-facing install and update UX must be byte-equivalent to upstream hermes-agent. Renames only; no redesign. Rationale: the entire foundation architecture exists to keep argo ≡ hermes modulo brand strings; the no-op `argo_update.py` stub and the missing public install URL silently broke that invariant. Interviewer (interview-me) initially proposed install/update redesigns; Vadim corrected sharply: "if there is something different as update experience is wrong. Devastating. You need to understand that im renaming from hermes to argo - im not downgrading the fucking agent." Spec scope is therefore: serve the already-renamed `install.sh` at a public URL; undo the `argo_update.py` stub so the real hermes `cmd_update` flows through the rename engine; verify equivalence via parity checks.

- **2026-05-28 — Architecture: single-repo + `release` branch.** Vadim's words: "i accept the 1 sided repo one. i do cause my repo is argo overlay right?" Adopts the Opus-reviewer's recommendation: no `argo-dist` mirror; `nadicodeai/argo` becomes public; `main` stays as workshop (upstream/ + patches/ + overlay/); a long-lived `release` branch on the same repo carries the runnable `dist/argo/` tree, force-pushed by CI on every release. `install.sh` and `cmd_update` both target `origin/release`. Foundation rule "tracked source on main is pristine upstream + patches; renamed tree never committed to main" survives unchanged.

- **2026-05-28 — Setup wizard: inherit + rename.** Vadim: "we want the setup wizar dof course but its for argo our name doing the same thing exactly like hermes." `upstream/hermes_cli/setup.py` and `upstream/scripts/install.sh`'s setup-wizard branches are inherited via the rename engine; renamed strings, identical behavior.

- **2026-05-28 — Release: inherit `upstream/scripts/release.py`, rename, run.** Vadim: "release - es we inherit, rename and run according to our patternns." `release.py` runs through the rename engine; tags follow hermes's CalVer scheme (`v<YYYY>.<M>.<D>`, same-day suffix `.2`/`.3`); internal semver in `argo_cli/__init__.py` tracks upstream's exact value separately so customer-visible version never leaks the rebrand.

- **2026-05-28 — PyPI: option 2 (no PyPI, document divergence) — CONFIRMED.** Vadim: "ok no pypi. lets go." Codified as IU-FR-13 in spec.md and as a Never-rule in standards.md. Reversing requires a spec amendment.

- **2026-05-28 — Spec v2 signed off.** Vadim: "1. ok." Locks the spec body. Standards drafted next.

- **2026-05-28 — Standards signed off.** Vadim: "we are good lets go." Locks the loop standards. `plan` skill invocation next.

- **2026-05-28 — Plan up-the-hill review, 5 rounds.** R1: 5 fixes (AC-closure claims, IU-AC-12 verification, release.py/release.yml collision, M3.2 sequencing, pre-verified rename-engine findings). R2: 2 material fixes (banner format wrong in checklist step 1, managed_error() exit-code wrong) + ~5 follow-ups. R3: 2 internal-consistency fixes from R2 edits. R4: 1 material fix (M4.1 grep pattern wrong — install.sh uses `BRANCH="main"` not env-override syntax). R5: 2 P0 blockers (B1, B2) — escalated to Vadim. Each round provided material value; no cosmetic-only rounds. Protocol's 5-round max consumed; coordinator presents plan + blockers per the plan skill's stop rule.

- **2026-05-28 — B1 + B2 resolved.** Vadim: "b1 b. b2 yes." (a) B1: spec.md § IU-AC-4 and § IU-AC-13 amended — regex `argo \d{4}\.\d+\.\d+` → `Argo Agent v\d+\.\d+\.\d+ \(\d{4}\.\d+\.\d+\)` (matches the inherited hermes banner verbatim, brand-renamed). (b) B2: M4.3 now builds `tools/argo_release.py` (workshop-side wrapper that mirrors upstream release.py's update-version + gh-release-create flow but operates from the workshop layout) as sub-step M4.3a before invoking it in M4.3b. Plan verdict moved from REVISED to READY.

- **2026-05-28 — Phase 1 closed.** Setup Close (Step 5) recorded. Loop parked per Vadim's directive ("you stop before phase 2 please") awaiting explicit go-ahead before Phase 2 milestone-loop dispatch.

## Open Questions

(populated by `spec` skill in Step 2)
