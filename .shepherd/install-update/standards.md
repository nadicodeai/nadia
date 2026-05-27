# install-update — Project Standards

Project rules, role-owned commands, and accepted waivers for THIS shepherd loop (install + update parity with hermes). Subagents read this before editing.

> **Foundation standards apply in full.** This file ADDS loop-specific rules on top of `.shepherd/standards.md`. Where the two conflict, the foundation wins; conflicts should be impossible — surface them as a blocker.

---

## Code Quality

- All loop-specific rules inherit from foundation `.shepherd/standards.md` (Python style, ruff PLW1514, ty type-check, file I/O encoding, patch authorship, overlay authorship, tools/ authorship, errors, logging, git discipline).
- One addition: **any code that touches `cmd_update` semantics, `install.sh` text, or release-cutting MUST be grounded in a file:line reference to upstream hermes.** Commits/PRs that change behavior here without citing the upstream pattern they're matching are REQUEST-CHANGES from review by default. Reason: the loop constraint is "byte-equivalent to hermes"; deviation needs explicit waiver, not silent invention.

## Testing

- Unit test command: `pytest overlay/tests/ -v` (existing).
- Smoke test commands (NEW; created during implementation):
  - `make install-smoke` — Docker-driven install.sh end-to-end.
  - `make update-smoke` — Docker-driven cmd_update end-to-end.
- Parity command: `tools/parity_runner.py --surface install-script --surface cmd-update` (existing runner; new surfaces added by this loop).
- Lint command: `ruff check . && ruff format --check .` (existing).
- Type-check command: `ty check` (existing).
- Hardening commands: `make leakage-static` (existing); `make check-upstream-pristine` (existing).
- Integration/e2e checks do not replace TDD unit coverage.
- **Telegram smoke tests use fake bots.** Never the real Telegram API. The fake client lives at `tests/update_smoke/fake_telegram.py` (NEW). Real-Telegram tests, if added later, run only on release tags, never on every PR.
- **Accepted limitations:**
  - PyPI distribution path (IU-FR-13). `_cmd_update_pip` is inherited unreachable code. No test exercises it. Documented in spec; acceptable.
  - macOS and Termux smoke coverage is best-effort (Ubuntu 22.04 is the primary smoke target). Inherited from upstream's CI shape.

## Architecture

- **`main` is the workshop. `release` is the storefront.** `main` contains `upstream/`, `patches/`, `overlay/`, `tools/`, `.shepherd/`, `argo-rename.yaml`. `release` contains the renamed `dist/argo/` tree only — no patch series, no shepherd notes, no rename engine source.
- **Never commit `dist/argo/` to `main`.** Force-push to `release` is the only way that tree reaches a tracked git ref.
- **Force-push to `release` uses `--force-with-lease`,** never `--force`. CI workflow MUST `concurrency: { group: release, cancel-in-progress: false }` to prevent races.
- **`make leakage-static` MUST gate every `release`-branch push.** A hermes string leaking into the customer-facing tree blocks the push.
- **`OFFICIAL_REPO_URLS` rebrand is load-bearing.** Every release MUST verify (via IU-AC-9 in CI) that running the renamed `argo update` against a fresh install does NOT print the `"⚠ Updating from fork"` warning. If this regresses, treat as P0.
- **PyPI uploads are prohibited for argo-agent.** Per IU-FR-13. No `upload_to_pypi.yml`-equivalent workflow exists in argo's `.github/workflows/`. Any PR adding one is REQUEST-CHANGES by default. Reverting this prohibition requires a spec amendment (`.shepherd/install-update/spec.md`'s IU-FR-13 deleted + signed off by Vadim).
- **Release tags follow CalVer.** Tag scheme: `v<YYYY>.<M>.<D>`, same-day suffix `.2`/`.3`. Internal `argo_cli/__init__.py:__version__` tracks upstream's exact value (`0.14.0`) and is bumped only on upstream sync that lands a new upstream version. The two never converge.
- **install.sh defaults to `$BRANCH=release` for argo customers.** Developers checking out the workshop pass `--branch main` explicitly.

## Role Ownership (Phase 2 milestone loop)

| Role | Owns in this loop | Does NOT own |
|---|---|---|
| Coordinator (me) | Phase 1 artifacts (this file, spec.md, plan.md, progress.md), sequencing dispatchers, merging implementer work, recording verification evidence, presenting architect verdicts. | Implementation. |
| Implementer | Assigned slice from `plan.md`. TDD unit tests where applicable. Running `make build`, the relevant smoke target, `make leakage-static`, ruff, ty. | Broad refactor outside their slice. New FR not in spec. |
| Refactorer | Post-implementer cleanup: names, duplication, weak tests, dead code (specifically: confirming `argo_update.py` stub is gone). | New behavior. |
| Architect | Cross-slice invariants (rename engine still produces deterministic output; OFFICIAL_REPO_URLS rewrite still works; `release` branch tree never contains workshop files). Final hardening pass before loop close. | New product behavior. Spec rewrites. |

## Always / Ask First / Never

### Always

- Run the full local verify before claiming a slice done: `make build && make leakage-static && pytest overlay/tests/ -v && (make install-smoke || true if not yet wired)`.
- Cite upstream file:line for any new code that mirrors hermes behavior.
- Pass `--force-with-lease` when force-pushing the `release` branch.
- Verify IU-AC-9 (no fork warning) before any release push.
- Use the fake Telegram client in smoke tests, never the real API.

### Ask First

- Reversing IU-FR-13 (publishing to PyPI). Requires spec amendment + Vadim sign-off.
- Modifying the foundation spec `.shepherd/spec.md` or foundation `.shepherd/standards.md`.
- Adding a new patch to `patches/series` that's not directly traceable to a spec FR.
- Renaming or restructuring the `release` branch.
- Changing what `install.sh`'s `$BRANCH` defaults to.

### Never

- Commit `dist/argo/` to `main`.
- Edit `upstream/`.
- Add features to argo that hermes doesn't have.
- Ship build-engine artifacts (`tools/`, `patches/`, `overlay/hermes_sync/`, `argo-rename.yaml`, `.shepherd/`) to the `release` branch tree.
- Publish argo-agent to PyPI (IU-FR-13).
- Force-push `release` without `--force-with-lease`.
- Skip smoke tests because parity tests passed.
- Use real Telegram API in CI.
- Carry behavioral divergence from hermes silently — divergence must be documented as an IU-FR with explicit rationale.

---

## Skill Notes (loop-relevant)

- **`tdd-mutation`** — applies to new `tools/release_branch_push.py` and the smoke harness. Mutation testing not required for inherited renamed code (already covered by upstream's tests, which run through the rename engine).
- **`systematic-debugging`** — applies when any AC fails. Required before proposing a fix.
- **`verification-before-completion`** — applies to every implementer slice. Evidence (command output, exit codes) MUST appear in `progress.md` before a task transitions to Done.
- **`spec`** and **`plan`** — owned by the coordinator (me) during Phase 1. Implementers do not edit `spec.md` or `plan.md` mid-loop without coordinator approval.

---

## Verification Evidence Schema

Each implementer slice records evidence in `progress.md`:

| Item | Required output |
|---|---|
| `make build` | exit 0 + last 5 lines of stdout |
| Smoke test (if wired) | exit 0 + the assertion line that proved the AC |
| Parity surface (if wired) | exit 0 + per-surface PASS/FAIL summary |
| `make leakage-static` | exit 0 + "no leakage detected" line |
| Unit tests | `pytest ... -v` summary |
| Upstream citation | file:line of hermes source if implementer code mirrors hermes |
