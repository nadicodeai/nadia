# Spec: argo install + update parity with hermes-agent

> **Status:** Draft v2 (post Opus-reviewer + Vadim architecture decisions). Awaiting final sign-off.
> **Loop scope:** Closing the install + update UX gap that surfaced after the M1–M8 foundation build. Narrow, contained, ~3 days of work.
> **Foundation spec:** `.shepherd/spec.md` (NOT modified by this loop).
> **Date:** 2026-05-28.
> **Supersedes:** Draft v1 (2026-05-27). v1 proposed a separate `nadicodeai/argo-dist` mirror repo and a `v<upstream>-fork.<N>` version scheme; both are deleted in v2 after grounding in upstream hermes-agent's actual patterns.

## Confirmed Intent

- **Outcome:** argo's customer install and update UX is byte-equivalent to hermes-agent's today. Brand strings (`hermes`→`argo`) and distribution URLs (`NousResearch/hermes-agent`→`nadicodeai/argo`) change; nothing else changes.
- **User:** customers running argo as a Telegram-fronted daemon, plus Vadim himself on his own systems (Wolf pattern). No TUI in the install or update flow.
- **Why now:** 3 customer deployments imminent from 2026-05-27. Current state — `overlay/hermes_cli/argo_update.py` is a no-op stub that intentionally replaced hermes's real `cmd_update`, and no public URL serves the renamed `install.sh` — silently breaks parity. Cannot deploy.
- **Success:** (a) `curl -fsSL <public-argo-url> | bash` lands a working argo install indistinguishable from how hermes installs today. (b) Sending `/update` over Telegram triggers the exact same smooth mid-flight restart hermes performs today. (c) Whatever hermes does in install + update, argo does — verified by parity-runner-style equivalence checks that catch future divergence.
- **Constraint:** Zero behavioral divergence from hermes install/update. **One knowing exception:** argo does not publish to PyPI (Vadim's prior signoff preserved). The renamed `_cmd_update_pip` branch is inherited but unreachable for properly-installed argo customers; see IU-FR-13. If Vadim flips this to "publish to PyPI as argo-agent", IU-FR-13 is deleted and the constraint becomes fully unconditional.
- **Out of scope:** Redesigning install or update. Changing rollback semantics. Simplifying or removing upstream's update branches (git pull / pip / zip / node / managed). Adding features argo has that hermes doesn't.

Signed off by Vadim (interview-me) on 2026-05-27; architecture decisions logged in `progress.md` on 2026-05-28.

---

## Assumptions

Five remaining after the v1 → v2 reduction. Most v1 assumptions are now resolved decisions in `progress.md`.

1. **`nadicodeai/argo` becomes public.** Same single repo; no second repo. Workshop visible on `main`; that's the hermes pattern (their repo is fully public including plans/, RFC docs, internal CI).
2. **Customer install dir layout matches hermes.** Verbatim upstream's `install.sh` layout (`$INSTALL_DIR=$HOME/.local/share/argo`, venv at `$INSTALL_DIR/.venv`, `~/.local/bin/argo` symlink). No deviation.
3. **A long-lived `release` branch on `nadicodeai/argo` carries the runnable renamed tree.** CI force-pushes `dist/argo/` (the rename-engine output) to `release` after every successful release build. Both `install.sh` (curl URL) and `cmd_update` (`git pull`) target `origin/release`. Customer never touches `main`.
4. **CalVer for customer-visible tags; semver for internal `__version__`.** Tags: `v2026.5.28`, same-day suffix `v2026.5.28.2`. Internal `argo_cli/__init__.py:__version__` tracks upstream's exact value (`0.14.0` today). Customer sees `argo 2026.5.28`; the fork suffix never surfaces.
5. **No new build-time deps.** Everything reuses existing tooling (`tools/build.py`, the rename engine, `upstream/scripts/release.py` via the rename engine, `gh` CLI). Anything new must justify itself.

---

## Architectural reality check (grounded findings, v2)

Read before evaluating FRs/ACs.

- **The orphaned `overlay/hermes_cli/argo_update.py` stub is dead code.** Nothing imports it. The renamed `dist/argo/argo_cli/main.py:~8680` already dispatches to upstream's real `cmd_update`. Stub removal is hygiene; no behavior change.
- **`upstream/scripts/install.sh:46-47`** hardcodes `REPO_URL_HTTPS="https://github.com/NousResearch/hermes-agent.git"`; line 970 does `git clone --branch "$BRANCH"` of that URL. The rename engine already rewrites this to `nadicodeai/argo`. We add: install.sh defaults to `$BRANCH=release` for argo (not `main`), so the clone targets the release branch (which has a runnable tree), not `main` (which is the workshop).
- **`upstream/hermes_cli/main.py:~8736`** (`_cmd_update_impl`) does `git pull` against whatever `origin` points to. The rename engine doesn't need to touch this — but the install.sh's `--branch release` default propagates: customer's local clone tracks `origin/release`, so `git pull` updates from there.
- **`upstream/hermes_cli/main.py:7319-7332`** (`_is_fork`) compares `origin` against a list `OFFICIAL_REPO_URLS`; if fork, line 8812-8815 prints `"⚠ Updating from fork: <url>"` and proceeds. For argo customers to NOT see this warning on every update, the rename engine must rewrite `OFFICIAL_REPO_URLS` to include `https://github.com/nadicodeai/argo`. Verify whether existing patches handle this; add a patch if not.
- **`upstream/scripts/install.sh:2062`** writes `echo "git" > "$HERMES_HOME/.install_method"`. The renamed version writes to `$ARGO_HOME/.install_method`. `upstream/hermes_cli/config.py:282-309` reads this and dispatches `cmd_update` accordingly. For argo's `install.sh` to lead to a working `cmd_update`, this stamp MUST exist and read `git`.
- **`upstream/scripts/install.sh:1695-1727`** (`run_setup_wizard`) shells out to `python -m hermes_cli.main setup < /dev/tty` and is skippable with `--skip-setup`. `upstream/hermes_cli/setup.py:_setup_telegram` (line ~1831) collects `TELEGRAM_BOT_TOKEN`. Three-stage handoff: bootstrap → setup → gateway install. All three exist in renamed form; verify end-to-end.
- **`upstream/scripts/install.sh:1729-1824`** (`maybe_start_gateway`) detects messaging tokens in `$HERMES_HOME/.env`, prompts "Install gateway as background service?", runs `hermes gateway install && hermes gateway start`. Renamed: `argo gateway install && argo gateway start`. This is the moment the customer's bot comes online.
- **`upstream/scripts/release.py:1364-1426`** owns tag cutting, CalVer, same-day suffix, atomic semver bump. Renamed and reused; no rewrite.
- **`upstream/.github/workflows/upload_to_pypi.yml`** publishes hermes to PyPI on tag push. Argo's release workflow does NOT do this (IU-FR-13). Tag pushes still trigger build + `release` branch update + GitHub Release with assets — just not PyPI.

---

## Tech Stack

Inherited verbatim from foundation spec § Tech Stack. New this loop: `gh` CLI for release creation (already used by `publish-legacy-baseline.yml`).

---

## Commands

Existing (foundation):
- `make build` — produces `dist/argo/` including renamed `scripts/install.sh` and `argo_cli/main.py`.
- `make image` / `make image-full` — Docker variants.

New (this loop):
- `make release` — runs `dist/argo/scripts/release.py` (the renamed upstream release.py) to bump CalVer tag, runs `make build`, force-pushes `dist/argo/` to `origin/release`, creates a GitHub Release via `gh release create` with `argo-vYYYY.M.D.tar.gz` + the standalone renamed `install.sh` as assets.
- `make install-smoke` — runs the renamed `install.sh` inside a Docker container (Ubuntu 22.04), asserts `argo --version` succeeds, asserts `~/.argo/.install_method` equals `git`.
- `make update-smoke` — boots an argo install at version N-1, triggers `cmd_update`, asserts it reaches version N with the same intermediate log output upstream produces (parity-runner pattern).

---

## Project Structure

Additions to the foundation layout:

```
.github/workflows/
  release.yml                # new: tag + build + release-branch force-push + gh release create
tools/
  release_branch_push.py     # new: force-push dist/argo/ to origin/release with --force-with-lease
overlay/
  hermes_cli/
    argo_update.py           # REMOVED (orphaned stub)
patches/
  00NN-official-repo-urls.patch  # new IF the rename engine doesn't catch OFFICIAL_REPO_URLS; verify first
tests/
  install_smoke/             # new: install.sh smoke tests (Docker-driven)
  update_smoke/              # new: cmd_update smoke tests (Docker-driven)
  parity-install.yml         # new: parity surface for install.sh equivalence
  parity-update.yml          # new: parity surface for cmd_update equivalence
```

The `release` branch on this same repo is a long-lived CI-maintained branch; it has no entries here because it is not committed to from human-driven work.

---

## Code Style

Inherited from `.shepherd/standards.md`. No changes.

---

## Testing Strategy

- **Unit:** `pytest overlay/tests/test_release_branch_push.py`, smoke-test fixtures. Fast, mocked subprocess/git.
- **Smoke (CI):** `make install-smoke` and `make update-smoke` run in Docker. Real `git clone`, real `uv` provisioning, real install. Includes end-to-end Telegram via a fake bot (no real Telegram API in CI).
- **Parity (CI):** Two new surfaces in `tools/parity_runner.py`:
  - `install-script`: runs upstream `install.sh` + argo `install.sh` in parallel containers; diffs result trees. Only-diff = renamed strings + URLs.
  - `cmd-update`: starts both at version N-1, triggers update in both, diffs log stream + final `--version`.
- **Hardening:** `make leakage-static` runs over the `release`-branch tree before force-push. Blocks the push if a hermes string leaks into the customer-facing tree.

---

## Functional Requirements

**IU-FR-1. Stub removal.** Delete `overlay/hermes_cli/argo_update.py`. No code references it; `dist/argo/argo_cli/main.py` already dispatches to upstream's real `cmd_update`.

**IU-FR-2. Repo public.** `nadicodeai/argo` is made public. Single repo; no separate mirror.

**IU-FR-3. `release` branch on `nadicodeai/argo`.** A long-lived `release` branch carries the runnable renamed tree (`dist/argo/`). CI force-pushes after every successful `make release` build. The branch tree contains NO `patches/`, `.shepherd/`, `tools/sync.py`, `tools/parity_runner.py`, `overlay/hermes_sync/`, or `argo-rename.yaml` — those are build-engine inputs, not outputs. Force-push is acceptable because `release` is a build artifact, not a source-of-truth.

**IU-FR-4. Public install URL.** `https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh` returns the renamed installer. Stable URL, never changes.

**IU-FR-5. install.sh behavior parity.** The renamed `install.sh` exhibits byte-equivalent behavior to upstream's, modulo renamed strings. Same supported platforms (Linux, macOS, Termux, WSL2, Windows via `install.ps1`); same install dir layout; same flags (`--no-venv`, `--skip-setup`, `--branch`, `--postinstall`); same symlink target; same `uv` and Node.js provisioning; same systemd integration; same `.install_method` stamping.

**IU-FR-6. install.sh default branch override.** Argo's renamed `install.sh` defaults `$BRANCH` to `release` (not `main`). The override lives in the rename engine — `argo-rename.yaml` adds a mapping or a small patch sets `DEFAULT_BRANCH="release"` for argo. Customer running `curl ... | bash` clones `release`; runs `--branch main` explicitly only if they want to track the workshop (developer use).

**IU-FR-7. `OFFICIAL_REPO_URLS` rebrand.** The renamed `argo_cli/main.py:7319-7332` (`_is_fork`) list includes `https://github.com/nadicodeai/argo` (and the SSH form). Customers do NOT see `"⚠ Updating from fork: ..."` on `/update`. Verify rename engine catches the list; add patch if not.

**IU-FR-8. cmd_update behavior parity.** The renamed `cmd_update` exhibits byte-equivalent behavior to upstream's. All update paths (git pull, zip, node, managed) work identically. `_run_pre_update_backup`, `_install_hangup_protection`, exit-code-42 → TUI/wrapper relaunch — all preserved by rename engine.

**IU-FR-9. Three-stage install handoff parity.** install.sh ends with: (a) bootstrap (binary on PATH, `.install_method=git` stamped); (b) optional `argo setup` wizard (skippable with `--skip-setup`) that prompts for Telegram bot token + model provider + writes `~/.argo/.env`; (c) optional `maybe_start_gateway` that runs `argo gateway install && argo gateway start` after detecting the token. End state: bot online, customer can DM it.

**IU-FR-10. Setup wizard parity.** The renamed `argo_cli/setup.py` collects `TELEGRAM_BOT_TOKEN`, model provider, etc. Same prompts as hermes, with brand strings renamed.

**IU-FR-11. Telegram `/update` parity.** Customer DMs `/update` → bot replies with the same progress messages hermes does today (e.g., "Checking for updates...", "Found vYYYY.M.D, downloading...", "Restarting...") → service restarts via systemd → bot reconnects → bot replies with hermes's equivalent "Updated to vYYYY.M.D" line. No new code; this FR asserts non-regression via IU-AC-6.

**IU-FR-12. CalVer release tags.** Releases tagged `v<YYYY>.<M>.<D>`. Same-day re-releases: `v<YYYY>.<M>.<D>.2`, `.3`, etc. (matches hermes `release.py:1376-1380` pattern). Internal `argo_cli/__init__.py:__version__` tracks upstream's exact value separately; never carries the CalVer.

**IU-FR-13. PyPI divergence — DOCUMENTED.** argo does NOT publish to PyPI. The renamed `_cmd_update_pip` branch remains in `argo_cli/main.py` (inherited via rename engine) but is unreachable for properly-installed argo customers because `install.sh` always stamps `.install_method=git`. Any customer who somehow has a pip install of `argo-agent` (custom wheel, internal mirror) and triggers `cmd_update` will see a PyPI 404 error — acceptable failure mode because no such customer exists under supported install paths. Foundation FR-11 ("Docker image is the only published artifact") is narrowed within this loop's scope to "no PyPI uploads of argo-agent"; GitHub Releases + `release` branch are NOT PyPI uploads and ARE explicitly allowed.

**IU-FR-14. `is_managed()` parity.** Foundation note: `upstream/hermes_cli/config.py` supports `is_managed()` blocking `cmd_update`. Inherited via rename engine; no new code.

**IU-FR-15. Pre-update backup parity.** `_run_pre_update_backup` runs unconditionally at the top of `_cmd_update_impl`, gated by `updates.pre_update_backup` in `~/.argo/config.yaml` (default per upstream). Renamed; no new code.

**IU-FR-16. Release artifacts on every tag.** Each `vYYYY.M.D` tag produces a GitHub Release with:
  - `argo-vYYYY.M.D.tar.gz` — the renamed `dist/argo/` tree.
  - `install.sh` — the renamed installer (byte-identical to what's at `dist/argo/scripts/install.sh` for that tag).
  - `install.ps1` — Windows equivalent.
  - SHA256 sums.

---

## Non-Functional Requirements

**IU-NFR-1. Install time ≤ hermes install time + 10%.** Clean Ubuntu 22.04 container, no caches, `time curl ... | bash`. Hermes baseline measured first.

**IU-NFR-2. Update time ≤ hermes update time + 10%.** Same methodology, on `cmd_update`.

**IU-NFR-3. Release artifact determinism.** `argo-vYYYY.M.D.tar.gz` built twice on the same SHA + same `SOURCE_DATE_EPOCH` produces byte-identical tarballs. Inherits foundation AC-8.

**IU-NFR-4. `release` branch size bounded.** Force-push (not append) keeps `.git` small. CI rejects a release if `release` branch checkout exceeds 500 MB.

**IU-NFR-5. Customer install needs no auth.** No PAT, no SSH key, no `gh login`. Just `curl | bash` on a clean machine.

**IU-NFR-6. Telegram update progress UX matches hermes.** Mid-flight: "Updating...", "Restarting...", "Connected." Messages byte-identical to hermes modulo "argo" replacing "hermes" / "Hermes".

**IU-NFR-7. No new runtime deps.** Mirror tooling (`release_branch_push.py`) is build-time only.

---

## Acceptance Criteria

**IU-AC-1. Stub removed.** `git grep -n argo_update overlay/ patches/` returns nothing. `make build` succeeds. `dist/argo/argo_cli/argo_update.py` does not exist.

**IU-AC-2. Repo public.** `gh repo view nadicodeai/argo --json visibility -q .visibility` returns `PUBLIC`.

**IU-AC-3. `release` branch exists and is customer-grade.** `git ls-remote https://github.com/nadicodeai/argo.git refs/heads/release` returns a SHA. `git archive --remote=origin release HEAD: | tar -tf - | grep -E '^(patches/|\.shepherd/|tools/sync\.py|tools/parity_runner\.py|overlay/hermes_sync/|argo-rename\.yaml)'` returns nothing. `curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/argo_cli/main.py | head -3` returns Python docstring containing "Argo" (not "Hermes").

**IU-AC-4. Customer install one-liner works on Ubuntu 22.04.**
```bash
docker run --rm -it ubuntu:22.04 bash -c "
  apt-get update -qq && apt-get install -y -qq curl
  curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh | bash -s -- --skip-setup
  ~/.local/bin/argo --version
"
```
Exit 0. Last line matches `Argo Agent v\d+\.\d+\.\d+ \(\d{4}\.\d+\.\d+\)` (hermes banner format inherited verbatim, brand renamed; verified against `dist/argo/argo_cli/main.py:106`).

**IU-AC-5. `.install_method` stamped correctly.** After IU-AC-4 runs, `~/.argo/.install_method` exists and contains `git` (no trailing newline beyond what upstream writes).

**IU-AC-6. End-to-end install + Telegram + update.** In a single Docker run: install argo at vN-1; complete setup wizard with fake Telegram token; start gateway; have a fake Telegram client DM `/update`; assert bot replies with hermes's expected progress messages; assert service restarts; assert bot reconnects; assert bot replies with the post-update "Updated" line; assert `argo --version` reports vN.

**IU-AC-7. Install parity.** `tools/parity_runner.py --surface install-script` exits 0. Renamed install end-state is byte-equivalent to hermes install end-state on the same base image; only diff = renamed strings + URLs + `.install_method` content.

**IU-AC-8. cmd_update parity.** `tools/parity_runner.py --surface cmd-update` exits 0. Argo update logs byte-equivalent to hermes update logs.

**IU-AC-9. Fork warning suppressed.** Running `argo update` against a fresh `release`-branch install produces no `"⚠ Updating from fork: ..."` line. Verified via stdout grep in IU-AC-8.

**IU-AC-10. is_managed() blocks update.** With `ARGO_MANAGED=1`, `argo update` returns the managed-mode error string (renamed from upstream's verbatim string).

**IU-AC-11. Pre-update backup writes a snapshot.** With `updates.pre_update_backup: true` in `~/.argo/config.yaml`, `argo update` creates `$ARGO_HOME/backups/<timestamp>/`. `argo import <path>` restores.

**IU-AC-12. Release tarball is deterministic.** `make release` twice on the same SHA + same `SOURCE_DATE_EPOCH` produces byte-identical `argo-vYYYY.M.D.tar.gz`.

**IU-AC-13. CalVer tags + banner format parity.** `git tag -l 'v20*'` shows CalVer tags. `argo --version` output matches the hermes banner format renamed: `Argo Agent v\d+\.\d+\.\d+ \(\d{4}\.\d+\.\d+\)` — semver from `argo_cli/__init__.py:__version__` + CalVer release-date in parentheses (verified at `dist/argo/argo_cli/main.py:6250`). The CalVer in parens is what surfaces customer-side as the human-readable release identifier; the semver inside `v...` is the internal version tracking upstream's value. Spec amended on 2026-05-28 from a CalVer-only regex (which would have required a banner patch and diverged from hermes); the parenthesised hermes form preserves byte-equivalence-to-hermes.

**IU-AC-14. No new hermes leakage.** `make leakage-static` over the `release` branch checkout is clean.

**IU-AC-15. Time budget.** `make release` in CI ≤ 10 min. `make install-smoke` ≤ 5 min. `make update-smoke` ≤ 5 min.

---

## Boundaries

- **Always:**
  - Run `make build && make leakage-static && make install-smoke && make update-smoke` before any release tag is pushed.
  - `release` branch force-push uses `--force-with-lease`.
  - Every new file in `tools/` follows the typed-error + UTF-8 + no-bare-Exception pattern from foundation standards.
- **Ask first:**
  - Reversing IU-FR-13 (publishing to PyPI).
  - Diverging in any way from upstream's install or update behavior beyond IU-FR-13.
  - Modifying the foundation spec `.shepherd/spec.md`.
- **Never:**
  - Commit `dist/argo/` to `main`.
  - Edit `upstream/`.
  - Add features to argo that hermes doesn't have.
  - Ship `tools/`, `patches/`, `overlay/hermes_sync/` to the `release` branch tree.
  - Skip the smoke tests because "the parity tests passed."

---

## Success Criteria

- **(a) Public install works.** IU-AC-3 + IU-AC-4 + IU-AC-5 + IU-AC-7 pass.
- **(b) Telegram /update mid-flight restart works.** IU-AC-6 + IU-AC-8 + IU-AC-9 + IU-AC-11 pass.
- **(c) Parity machinery catches future divergence.** `tools/parity_runner.py` includes `install-script` and `cmd-update` as required surfaces. ci.yml's parity job blocks merge on regression.

---

## Risks

1. **`release` branch force-push race.** Two CI jobs racing → one push lost. Mitigation: workflow-level `concurrency: { group: release, cancel-in-progress: false }` + `--force-with-lease`.
2. **Upstream changes install or update.** Next sync may land a hermes refactor that breaks argo parity. This IS the design intent — parity tests catch it. They're the gate, not a nice-to-have.
3. **`OFFICIAL_REPO_URLS` rename engine miss.** If the rename engine misses this list, every customer's `/update` prints "⚠ Updating from fork: ...". Demo killer. Mitigation: IU-AC-9 in CI; verify-or-patch as part of IU-FR-7.
4. **PyPI divergence bites a customer.** A customer who somehow pip-installed argo-agent hits a 404 on update. Mitigation: IU-FR-13 documents the divergence; bounded blast radius because no supported install path produces a pip-install state.
5. **Workshop on public main.** `.shepherd/`, patches/, parity-expected.yml, this very spec are now world-readable. Hermes pattern says this is fine (their workshop is public too). Vadim accepted.

---

## Dependencies

- Foundation architecture stays stable: `upstream/` pristine, patches/ + overlay/ unchanged, rename engine unchanged, `make build` deterministic.
- `gh` CLI authenticated with `releases: write` permissions in CI (already true).
- A CI token authorized to force-push to `nadicodeai/argo`'s `release` branch (the workflow's default `GITHUB_TOKEN` suffices since this is the same repo).
- The rename engine correctly rewrites `OFFICIAL_REPO_URLS`. (Verify; patch if not.)

---

## Open Questions

Only one remains. The rest are resolved decisions in `progress.md`.

**OQ-IU-1. PyPI confirmation.** Spec encodes IU-FR-13 (no PyPI, documented divergence) based on Vadim's prior signoff. Confirm or flip to "publish argo-agent to PyPI on every release" (deletes IU-FR-13, adds a `pyproject.toml` rename in the engine, adds an `upload_to_pypi.yml` workflow).

---

## Glossary (loop-specific)

- **`release` branch.** Long-lived branch on `nadicodeai/argo`. Force-pushed by CI from `dist/argo/` on every release. Contains the runnable renamed tree only; no build-engine inputs.
- **CalVer.** `v<YYYY>.<M>.<D>` versioning (e.g., `v2026.5.28`). Same-day re-releases append `.2`/`.3`.
- **`.install_method`.** Stamp file at `$ARGO_HOME/.install_method` written by `install.sh`. Read by `cmd_update` to dispatch the right update path.
- **`OFFICIAL_REPO_URLS`.** Constant list in `argo_cli/main.py` used by `_is_fork` to decide whether to print the fork warning.
- **Three-stage handoff.** install.sh → `argo setup` (Telegram + provider) → `argo gateway install && argo gateway start`. End state: bot online.
- **Customer-managed.** Customer environment where IT controls upgrades; gated by `is_managed()` returning True.
