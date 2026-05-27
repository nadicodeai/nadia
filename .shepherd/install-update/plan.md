# Implementation Plan: argo install + update parity with hermes

> **Inputs:** `.shepherd/install-update/spec.md` (v2, signed off 2026-05-28), `.shepherd/install-update/standards.md` (signed off 2026-05-28).
> **Status:** Draft v1, pre-editor.
> **Date:** 2026-05-28.

## Overview

Close the install + update UX gap surfaced after the M1–M8 foundation build. Most of the work is **distribution + verification**, not new code: the renamed `install.sh` and renamed `cmd_update` already exist in `dist/argo/` after `make build`; the orphaned `argo_update.py` stub is dead code; the rename engine handles most strings. What's missing is (a) a public URL serving the renamed artifacts, (b) a `release` branch on this repo carrying the runnable renamed tree, (c) verification that hidden landmines like `OFFICIAL_REPO_URLS` and `.install_method` work end-to-end, and (d) smoke + parity machinery that catches future divergence.

Seven milestones split into an **MVP cut** (M1–M4) that's customer-deployable and a **durable cut** (M5–M7) that hardens the loop for post-deploy sustainability.

## Round-5 plan-editor blockers — RESOLVED 2026-05-28

- **B1 — Banner regex mismatch:** RESOLVED via spec amendment (option b). `spec.md` § IU-AC-4 and § IU-AC-13 updated 2026-05-28 to expect the hermes-format banner `Argo Agent v\d+\.\d+\.\d+ \(\d{4}\.\d+\.\d+\)` verbatim (renamed brand only). No banner patch needed. The verbatim-from-hermes format is preserved; spec was incorrect originally and is now aligned with the actual upstream banner pattern.
- **B2 — `release.py` workshop incompatibility:** RESOLVED via custom argo release driver (option a). M4.3 below now consists of two sub-tasks: M4.3a (build `tools/argo_release.py` workshop-side wrapper that mirrors release.py's update-version + gh-release-create shape but works from the workshop layout) and M4.3b (run the wrapper to cut `v2026.5.28`).

## Architecture Decisions

See `spec.md` § Confirmed Intent + decisions logged in `progress.md`. Not restated here. Load-bearing constraints for this plan:

- `main` = workshop; `release` = storefront. CI force-pushes `dist/argo/` to `release` with `--force-with-lease`.
- CalVer tags `v<YYYY>.<M>.<D>`; same-day suffix `.2`/`.3`.
- No PyPI (IU-FR-13).
- `OFFICIAL_REPO_URLS` rebrand is load-bearing; regression = P0.
- Smoke tests use fake Telegram bot; never real API.

## Dependency Graph

```
M1 (stub removal)
  │
  └─ M2 (repo public + release branch bootstrap)
        │
        ├─ M3 (OFFICIAL_REPO_URLS + .install_method)
        │     │
        │     └─ M4 (install.sh default branch + release.yml + first tag)
        │           │
        │           ├─ M5 (smoke harness)
        │           ├─ M6 (parity surfaces)
        │           └─ M7 (architect + docs)
```

M5, M6, M7 can run in parallel after M4 closes.

## MVP Cut vs Durable Cut

| Milestone | Cut | Customer-blocking if missing? |
|---|---|---|
| M1 | MVP | No (hygiene), but cheap and unblocks dispatch |
| M2 | MVP | YES — no public URL = no customer install |
| M3 | MVP | YES — fork warning leaks rebrand on every `/update` |
| M4 | MVP | YES — without `$BRANCH=release` default, `curl|bash` clones `main` (workshop, not runnable) |
| M5 | Durable | No — manual smoke verifies for now |
| M6 | Durable | No — parity machinery catches future drift, not today's drift |
| M7 | Durable | No — docs polish + architect verdict |

**MVP cut (M1–M4): customer-deployable** with manual smoke verification. Vadim's manual checklist before sharing the curl URL with a customer:
1. `curl ... install.sh | bash -s -- --skip-setup` on a fresh Ubuntu 22.04 container; `~/.local/bin/argo --version` exits 0 and prints `Argo Agent v0.14.1 (2026.5.28)` (the renamed banner format `Argo Agent v{__version__} ({__release_date__})` after M4.3 runs `release.py --bump patch --first-release --publish`, which rewrites both `__version__` 0.14.0→0.14.1 AND `__release_date__` → 2026.5.28). Spec IU-AC-4 / IU-AC-13's `argo \d{4}\.\d+\.\d+` regex is satisfied via the parenthesised `__release_date__` token; per-stream check is `grep -E 'argo [0-9]{4}\.[0-9]+\.[0-9]+' <argo --version output>` exits 0.
2. `argo setup` completes the Telegram handoff (real or fake token).
3. `argo gateway install && argo gateway start` brings the bot online.
4. `argo update` stdout contains NO `"⚠ Updating from fork"` line (IU-AC-9 manual proof).
5. `ARGO_MANAGED=1 argo update` prints the renamed managed-mode error string to stderr (IU-AC-10 manual proof). Note: upstream's `cmd_update` returns after `managed_error()` without exiting non-zero, so assert the stderr substring (e.g., `"is managed by"`) rather than a non-zero exit code. Tightening to a non-zero exit is a behavioral divergence from hermes and would require an IU-FR + spec amendment.

If any of these fail, the MVP is not deployable — return to M3 / M4. **Durable cut (M5–M7): post-deploy hardening** so future syncs/changes don't silently regress (and automates steps 4 + 5 above so they survive the next upstream sync).

---

## M1 — Stub removal + workshop hygiene

**Goal.** Delete the orphaned `argo_update.py` stub. Closes IU-AC-1.

### Task M1.1: Delete `overlay/hermes_cli/argo_update.py`

**Description:** Remove the no-op stub file. Nothing imports it (confirmed by `grep -rn argo_update upstream/ overlay/ patches/`). The renamed `dist/argo/argo_cli/main.py:~8680` already dispatches to upstream's real `cmd_update`.

**Acceptance criteria:**
- [ ] File `overlay/hermes_cli/argo_update.py` does not exist.
- [ ] `git grep -n argo_update -- overlay/ patches/` returns nothing.
- [ ] `dist/argo/argo_cli/argo_update.py` does not exist after `make build`.

**Verification:**
- [ ] `make build` exits 0 with no missing-import errors.
- [ ] `make leakage-static` exits 0.
- [ ] `pytest overlay/tests/ -v` passes (no test references the stub).

**Dependencies:** None.

**Files touched:**
- `overlay/hermes_cli/argo_update.py` (delete)

**Scope:** XS.

**Owner role:** Implementer.

### Architect hardening checkpoint M1

Trivial — no architect needed. Coordinator verifies build + leakage.

### Exit gate M1

IU-AC-1.

---

## M2 — Repo public + `release` branch bootstrap

**Goal.** Make `nadicodeai/argo` public; bootstrap the `release` branch with the current `dist/argo/` tree. Closes IU-AC-2, IU-AC-3 (partial — full closure waits on M4 first release).

### Task M2.1: Make `nadicodeai/argo` public

**Description:** Flip the repo's visibility to public via `gh repo edit nadicodeai/argo --visibility public --accept-visibility-change-consequences`. Verify branch protection rules (from foundation issue #5) still apply.

**Acceptance criteria:**
- [ ] `gh repo view nadicodeai/argo --json visibility -q .visibility` returns `PUBLIC`.
- [ ] Branch protection on `main` still gates required CI checks.

**Verification:**
- [ ] `curl -fsSL -I https://raw.githubusercontent.com/nadicodeai/argo/main/README.md` returns 200.

**Dependencies:** None (parallel with M2.2).

**Files touched:** None (GitHub settings only).

**Scope:** XS.

**Owner role:** Coordinator (Vadim authorizes; agent executes via `gh`).

### Task M2.2: Bootstrap `release` branch with current `dist/argo/` tree

**Description:** Run `make build` to produce `dist/argo/`. Create a new orphan branch `release` containing only `dist/argo/`'s contents at the root. Push to `nadicodeai/argo`. This is a one-shot manual seed; M4 wires CI to maintain it going forward.

**Acceptance criteria:**
- [ ] `git ls-remote https://github.com/nadicodeai/argo.git refs/heads/release` returns a SHA.
- [ ] Workshop files NOT in release tree. Verification command (the v1 form `git archive --remote=origin release HEAD:` is malformed — `origin` is a local-clone alias not a URL, and the trailing `:` is invalid for `git archive --remote`): in a scratch clone run `git clone --depth 1 --branch release https://github.com/nadicodeai/argo.git /tmp/argo-release && (cd /tmp/argo-release && find . -type d \( -name patches -o -name .shepherd -o -name hermes_sync \) -o -name 'sync.py' -o -name 'parity_runner.py' -o -name 'argo-rename.yaml' | head)` — the listing MUST be empty.
- [ ] `curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/argo_cli/main.py | head -3` returns a docstring referencing "Argo" (not "Hermes").
- [ ] `curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh | head -10` returns the renamed installer header.

**Verification:**
- [ ] `make leakage-static` exits 0 against the local `dist/argo/` before bootstrap push.
- [ ] All AC URLs return 200 / expected content.

**Dependencies:** M2.1 (repo must be public for raw URLs to work).

**Files touched:**
- New: `tools/bootstrap_release_branch.sh` (one-shot helper; can also be a documented procedure in AGENTS.md).

**Scope:** S.

**Owner role:** Implementer.

### Architect hardening checkpoint M2

Verify the `release` branch tree contains NO workshop files. Verify the renamed install.sh's `REPO_URL_HTTPS` points at `nadicodeai/argo`. Verify `make leakage-static` is clean.

> **Note for coordinator:** The release branch is now reachable via the public curl URL, but the install.sh on it still defaults `BRANCH=main` (M4.1 not yet landed). Do NOT share the curl URL with customers between M2 and M4.3; a curious tester running `curl|bash` would clone `main` (workshop, broken). M3.2 tests must pass `--branch release` explicitly. The MVP-deployable moment is the M4 exit gate, not the M2 exit gate.

### Exit gate M2

IU-AC-2, IU-AC-3.

---

## M3 — `OFFICIAL_REPO_URLS` rebrand + `.install_method` verification

**Goal.** Verify the two hidden landmines (`OFFICIAL_REPO_URLS` causing fork-warning on every `/update`; `.install_method` stamp being wrong or missing). Closes IU-AC-5; partially closes IU-AC-9 (static-config check only — end-to-end "no warning on `argo update`" closes in M5.3 once a real install is automatable).

> **Pre-verified (2026-05-28 grep over `dist/argo/`):** rename engine already rewrites `OFFICIAL_REPO_URLS`, `OFFICIAL_REPO_URL`, `$HERMES_HOME` → `$ARGO_HOME`, and `REPO_URL_HTTPS`/`SSH` to `nadicodeai/argo`. Tasks below are "verify no regression and pin the assertion" rather than "do the rename."

### Task M3.1: Verify `OFFICIAL_REPO_URLS` rebrand in renamed tree

**Description:** Grep `dist/argo/argo_cli/main.py` for `OFFICIAL_REPO_URLS`. Check that the list contains `https://github.com/nadicodeai/argo` and the SSH form, and does NOT still contain `NousResearch/hermes-agent`. If the rename engine has handled it correctly: pass. If not: add a patch under `patches/00NN-official-repo-urls.patch` that rewrites the list.

**Acceptance criteria:**
- [ ] `grep -A20 'OFFICIAL_REPO_URLS' dist/argo/argo_cli/main.py` shows `nadicodeai/argo` and not `NousResearch/hermes-agent`.
- [ ] If a patch was needed: it has `patches/asserts/<name>.txt` per foundation FR-14.
- [ ] If a patch was needed: `make patch-list` shows it in `patches/series` between 0007 and 0008 (or appended).

**Verification:**
- [ ] `make build && python tools/run_assertions.py dist/argo/` exits 0.
- [ ] `make leakage-static` exits 0.

**Dependencies:** M1 (clean baseline).

**Files touched:**
- Possibly: `patches/00NN-official-repo-urls.patch`, `patches/series`, `patches/asserts/00NN-official-repo-urls.txt`, `patches/asserts/manifest.txt`.

**Scope:** XS if rename engine handles it; S if a patch is needed.

**Owner role:** Implementer.

### Task M3.2: Verify `.install_method` stamping end-to-end

**Description:** Run the renamed `install.sh` inside a clean Ubuntu 22.04 Docker container. Assert `~/.argo/.install_method` exists and reads `git`. If the rename engine missed the `$HERMES_HOME → $ARGO_HOME` rewrite somewhere in install.sh's stamping path, add a patch.

**Important sequencing note:** Until M4.1 lands the `BRANCH=release` default patch, the install.sh on the `release` branch still defaults `BRANCH=main` (M2.2 bootstraps from the un-patched `dist/argo/`). M3.2 MUST pass `--branch release` explicitly when invoking `curl|bash` to test the release-branch tree. After M4.3 the explicit override is unnecessary; smoke harness in M5.2 verifies the default.

**Acceptance criteria:**
- [ ] After `curl -fsSL .../scripts/install.sh | bash -s -- --skip-setup --branch release`, `~/.argo/.install_method` exists and contains exactly `git\n`.
- [ ] `~/.hermes/.install_method` does NOT exist.

**Verification:**
- [ ] Container-driven check; one-shot `docker run ubuntu:22.04 bash -c '...'` line that returns 0 + the expected file content.

**Dependencies:** M2 (release branch must exist before install.sh can pull from it). May run in parallel with M3.1.

**Files touched:**
- Possibly: a new patch under `patches/` rewriting any straggler `$HERMES_HOME` → `$ARGO_HOME` references in install.sh.
- New: `tests/install_smoke/test_install_method_stamp.sh` (small ad-hoc check; promoted into the M5 smoke harness later).

**Scope:** S.

**Owner role:** Implementer.

### Architect hardening checkpoint M3

Architect runs `tools/parity_runner.py --surface install-script` if M6 wired it; otherwise eyeballs the diff between hermes's and argo's install behavior on the same Docker base. Confirms `OFFICIAL_REPO_URLS` is correct via `grep`.

### Exit gate M3

IU-AC-5; IU-AC-9 partial (static-config asserted; full end-to-end closure in M5.3).

---

## Checkpoint: Pre-MVP

- [ ] M1, M2, M3 all green.
- [ ] `make build && make leakage-static && pytest overlay/tests/` clean.
- [ ] `release` branch exists, customer-clean, raw URLs return 200.

---

## M4 — install.sh default-branch + `release.yml` workflow + first release

**Goal.** Wire install.sh to default `$BRANCH=release` for argo customers; create the release workflow; cut the first CalVer tag `v2026.5.28`. Closes IU-AC-4, IU-AC-12, IU-AC-13.

### Task M4.1: Patch install.sh to default `$BRANCH=release`

**Description:** Upstream's `install.sh:73` declares `BRANCH="main"` (plain assignment, NOT the `${BRANCH:-main}` env-override form); the `--branch <X>` flag overrides via arg-parsing at line 102 (`BRANCH="$2"`). argo customers must clone the `release` branch instead. Either (a) add a patch under `patches/` that rewrites line 73 to `BRANCH="release"` in the renamed file, or (b) have `release.yml` post-process the install.sh asset before uploading. Prefer the in-repo patch because it's source-controlled and survives every `make build`. The patch target string is `BRANCH="main"`; the replacement is `BRANCH="release"`.

**Acceptance criteria:**
- [ ] Inside the renamed `dist/argo/scripts/install.sh`, line ~73 reads `BRANCH="release"` (plain default).
- [ ] Developer override `curl ... | bash -s -- --branch main` still clones `main` (the workshop) and works for developer setups — arg-parsing at line ~102 still wins over the default.

**Verification:**
- [ ] `grep -nE '^BRANCH="(main|release)"' dist/argo/scripts/install.sh` shows exactly one line, matching `BRANCH="release"`. The pre-patch baseline matches `BRANCH="main"`; the assertion file under `patches/asserts/` MUST pin the post-patch form so a future rename-engine regression flips it back to `main` silently.
- [ ] Smoke run: `curl ... | bash -s -- --skip-setup` in a Ubuntu container clones `release`, not `main`.

**Dependencies:** M2 (release branch must exist).

**Files touched:**
- `patches/00NN-install-default-branch.patch` (new).
- `patches/series`.
- `patches/asserts/00NN-install-default-branch.txt`.

**Scope:** S.

**Owner role:** Implementer.

### Task M4.2: Build `.github/workflows/release.yml`

**Description:** New workflow triggered on tag push matching `v20*` (CalVer prefix). Runs `make build`, runs `make leakage-static` (gate), tar-zips `dist/argo/` into `argo-vYYYY.M.D.tar.gz`, force-pushes `dist/argo/` to `origin/release` with `--force-with-lease`, uploads release assets (tarball + standalone `install.sh` + `install.ps1` + SHA256 sums) via `gh release upload` against the release that `release.py` already created on the developer machine in M4.3. Workflow uses `concurrency: { group: release, cancel-in-progress: false }` per standards.

> **Coordination with upstream's `release.py`:** Upstream's renamed `release.py --publish` already runs `gh release create <tag>` with the changelog and sdist/wheel artifacts before pushing the tag. M4.2 workflow MUST NOT call `gh release create` (would 422 — release exists). It uses `gh release upload <tag> ... --clobber` to add the argo-specific tarball + install scripts + sums to the existing release. Alternatively: pass `--skip-publish` to release.py and let the workflow own release creation. Pick one path explicitly in the implementer dispatch; the current text picks the `gh release upload` path because release.py is the authoritative source for changelog generation.

**Acceptance criteria:**
- [ ] Workflow file exists at `.github/workflows/release.yml`.
- [ ] On tag push, workflow: (a) builds, (b) gates on leakage, (c) tars deterministically (uses `--mtime=@$SOURCE_DATE_EPOCH --sort=name --owner=0 --group=0 --numeric-owner` per foundation AC-8), (d) force-pushes `release` with `--force-with-lease`, (e) uploads assets to the existing GitHub Release.
- [ ] Workflow YAML parses (`yaml.safe_load`).
- [ ] Workflow does NOT publish to PyPI (IU-FR-13).

**Verification:**
- [ ] `yamllint .github/workflows/release.yml` clean (or `python -c "import yaml; yaml.safe_load(open(...))"`).
- [ ] Workflow dry-run: trigger via `workflow_dispatch` against a test tag, observe steps run without error.

**Dependencies:** M2 (release branch must exist for force-push target).

**Files touched:**
- `.github/workflows/release.yml` (new).
- `tools/release_branch_push.py` (new; called by the workflow).

**Scope:** M.

**Owner role:** Implementer.

### Task M4.3: Build `tools/argo_release.py` and tag first CalVer release `v2026.5.28`

> **B1 and B2 resolved 2026-05-28.** Spec § IU-AC-4/AC-13 was amended (option b) to expect the hermes-format banner verbatim. `tools/argo_release.py` workshop-side wrapper (option a) builds + bumps + tags + publishes per the design below.

**Description:** Sub-step M4.3a (Implementer): build `tools/argo_release.py` — a workshop-side wrapper that (i) runs `make build`, (ii) edits `dist/argo/argo_cli/__init__.py` in-place to set `__version__` (`0.14.0 → 0.14.1`) and `__release_date__` (`2026.5.16 → 2026.5.28`), (iii) edits `dist/argo/pyproject.toml`'s `version` field to match, (iv) creates annotated tag `v2026.5.28` on workshop `main` HEAD (no version-bump commit — `main` does NOT carry the customer-visible version; that lives in `dist/argo/` and gets force-pushed to `release` by M4.2), (v) pushes the tag, (vi) builds the deterministic tarball (`--mtime=@$SOURCE_DATE_EPOCH --sort=name --owner=0 --group=0 --numeric-owner`), (vii) calls `gh release create v2026.5.28 --title 'Argo Agent v0.14.1 (2026.5.28)' --notes <changelog> argo-v2026.5.28.tar.gz dist/argo/scripts/install.sh dist/argo/scripts/install.ps1 sha256sums.txt`. The wrapper MUST cite `dist/argo/scripts/release.py:1412-1426` (the `update_version_files` shape it mirrors) and `release.py:1887-1918` (the `gh release create` shape it mirrors) per standards § "cite upstream file:line for any new code that mirrors hermes behavior." Sub-step M4.3b (Coordinator): run the wrapper. M4.2's workflow then fires on the tag push and (a) re-builds `dist/argo/` from scratch on CI, (b) force-pushes that `dist/argo/` to `release` branch (the tarball uploaded in step vii is the source of truth for assets; the CI re-build is the source of truth for the `release` branch contents — IU-NFR-3 determinism ensures the two match byte-for-byte).

**Acceptance criteria:**
- [ ] Tag `v2026.5.28` exists on `origin/main` and is visible in `gh release list`.
- [ ] Release page shows `argo-v2026.5.28.tar.gz`, `install.sh`, `install.ps1`, sha256 sums as downloadable assets (uploaded by `tools/argo_release.py` via `gh release create` in step vii).
- [ ] **Inside the tarball** (NOT on `main` — `dist/argo/` stays gitignored per standards § Architecture), `argo_cli/__init__.py` contains `__release_date__ = "2026.5.28"` and `__version__ = "0.14.1"`. Verification: `tar -xOf argo-v2026.5.28.tar.gz argo/argo_cli/__init__.py | grep -E '__version__|__release_date__'`.
- [ ] On the post-CI `release` branch, `curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/argo_cli/__init__.py | grep -E '__version__|__release_date__'` returns the bumped values.
- [ ] `git ls-remote https://github.com/nadicodeai/argo.git refs/heads/release` SHA differs from M2.2's bootstrap SHA (CI updated the branch).
- [ ] PyPI: `pip index versions argo-agent` returns no results (or 404). Confirms IU-FR-13.

**Verification:**
- [ ] `curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh | bash -s -- --skip-setup` in a fresh Ubuntu container exits 0; `~/.local/bin/argo --version` exits 0 and prints `Argo Agent v0.14.1 (2026.5.28)`. Rationale: `tools/argo_release.py` (created in M4.3a) directly rewrites both `__version__` and `__release_date__` in `dist/argo/argo_cli/__init__.py` before tagging — mirroring `release.py:1416-1425`. The bumped values flow into the tarball and into the post-CI `release` branch tree, which the curl-bash then clones. Without the rewrite, `__release_date__` stays `2026.5.16` and the banner CalVer is stale.
- [ ] **IU-AC-4 / IU-AC-13 banner assertion (B1-resolved, spec amendment):** Run `~/.local/bin/argo --version | grep -E 'Argo Agent v\d+\.\d+\.\d+ \(\d{4}\.\d+\.\d+\)'`. Expected exit 0. Spec § IU-AC-4 and § IU-AC-13 were amended 2026-05-28 to expect the hermes banner format verbatim (renamed brand only).
- [ ] **Determinism re-run for IU-AC-12:** re-run M4.2's tar step against the same SHA + `SOURCE_DATE_EPOCH` locally; sha256 of the two tarballs match.

**Dependencies:** M4.1, M4.2.

**Files touched:**
- Tag (`v2026.5.28`).
- `tools/argo_release.py` (new in M4.3a; tracked on `main`).
- `dist/argo/argo_cli/__init__.py` — `__version__` bumped to `0.14.1` and `__release_date__` rewritten to `2026.5.28` by `tools/argo_release.py`. **This file is gitignored on `main`** (per `.gitignore:2` `dist/`); the bumped values live only inside `dist/argo/`, the tarball, and the post-CI `release` branch tree. They do NOT land as a commit on `main`. Spec assumption 4 ("Internal `argo_cli/__init__.py:__version__` tracks upstream's exact value separately") is preserved at the `upstream/hermes_cli/__init__.py` source — that file stays at `0.14.0` until next sync. The `dist/argo/` bump is a per-release artifact-side rewrite, not a workshop-side commit.

**Scope:** S.

**Owner role:** Coordinator (Vadim authorizes; agent executes via `gh`).

### Architect hardening checkpoint M4

Architect runs the full IU-AC-4 from spec: container, curl, install, version-check. Confirms the install path is end-to-end working without `OFFICIAL_REPO_URLS` warnings.

### Exit gate M4

IU-AC-4, IU-AC-12, IU-AC-13, IU-AC-14 (leakage gate ran).

---

## Checkpoint: MVP COMPLETE — Customer Deployable

- [ ] Customer can run `curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh | bash` on a clean Ubuntu 22.04 VPS.
- [ ] Customer can run `argo setup` to pair their Telegram bot.
- [ ] Customer can run `argo gateway install && argo gateway start` to bring the bot online.
- [ ] Customer can DM `/update` and see hermes-equivalent progress + restart.
- [ ] ACs CI-green at this checkpoint: 1, 2, 3, 4, 5, 12, 13, 14.
- [ ] ACs Vadim-manually-verified before sharing the URL: 9, 10 (see "MVP cut" manual checklist).
- [ ] ACs deferred to M5: 6, 11 (automated end-to-end), 15 (CI time budgets).
- [ ] ACs deferred to M6: 7, 8 (parity surfaces).

**At this checkpoint, Vadim can deploy to the 3 customers** after completing the manual checklist above. M5–M7 land in the days after to automate the manual steps and make this sustainable.

---

## M5 — Smoke harness (install + update)

**Goal.** Automate what was manual at the MVP checkpoint. Closes IU-AC-6, IU-AC-15 partially.

### Task M5.1: Fake Telegram client fixture

**Description:** Create `tests/update_smoke/fake_telegram.py` — a minimal HTTP server that implements the Telegram bot API endpoints argo uses (`getUpdates`, `sendMessage`, `getMe`). Records messages sent to it; can inject incoming messages to argo. No real API; no auth required; localhost only.

**Acceptance criteria:**
- [ ] Module exists; running it on `localhost:PORT` exposes the endpoints argo's gateway calls.
- [ ] argo gateway can be configured to point at it via env var (e.g., `TELEGRAM_API_URL=http://localhost:PORT`).

**Verification:**
- [ ] Unit tests: `pytest tests/update_smoke/test_fake_telegram.py -v`.

**Dependencies:** M1.

**Files touched:**
- `tests/update_smoke/fake_telegram.py` (new).
- `tests/update_smoke/test_fake_telegram.py` (new).

**Scope:** M.

**Owner role:** Implementer.

### Task M5.2: `make install-smoke`

**Description:** New make target. Spins up an `ubuntu:22.04` container; runs `curl|bash` from `release` branch; asserts `argo --version` exit 0, `.install_method=git`, `OFFICIAL_REPO_URLS` warning absent on `argo update` (managed-mode block fine), three-stage handoff produces working `argo gateway` config.

**Acceptance criteria:**
- [ ] Target exists; running it in CI takes < 5 minutes.
- [ ] Asserts cover IU-AC-4, IU-AC-5, IU-AC-9.

**Verification:**
- [ ] `make install-smoke` exits 0 locally.
- [ ] CI integration: ci.yml runs it on every PR.

**Dependencies:** M4 (release branch must have current install.sh).

**Files touched:**
- `Makefile`.
- `tests/install_smoke/run.sh` (new).
- `.github/workflows/ci.yml` (add a job).

**Scope:** M.

**Owner role:** Implementer.

### Task M5.3: `make update-smoke`

**Description:** New make target. Boots argo at v(N-1) in a container; configures it to use the fake Telegram client; injects `/update`; asserts bot replies with expected progress messages; asserts service restarts; asserts `argo --version` reports v(N) post-restart. Also exercises three end-to-end ACs that have no static check: IU-AC-9 (no fork warning), IU-AC-10 (managed-mode block), IU-AC-11 (pre-update backup snapshot).

**Acceptance criteria:**
- [ ] Target exists; running it in CI takes < 5 minutes.
- [ ] Asserts cover IU-AC-6, IU-AC-8 partial, IU-AC-9 (full), IU-AC-10, IU-AC-11.
- [ ] **IU-AC-9 assertion:** stdout/stderr of `argo update` contains NO line matching `"⚠ Updating from fork"`.
- [ ] **IU-AC-10 assertion:** a separate container run with `ARGO_MANAGED=1` invokes `argo update`; STDERR contains the renamed managed-mode error string (substring match against `"is managed by"`). Do NOT assert non-zero exit code — upstream's `cmd_update` calls `managed_error()` (which only `print(..., file=sys.stderr)`s) and then returns; `main()` calls `args.func(args)` ignoring the return value, so process exits 0. Spec IU-AC-10 ("returns the managed-mode error string") is satisfied by the stderr substring; tightening to non-zero is a hermes-divergence and forbidden by the loop constraint without a spec amendment.
- [ ] **IU-AC-11 assertion:** before triggering the update, write `updates: { pre_update_backup: true }` to `~/.argo/config.yaml`; after update completes, assert `$ARGO_HOME/backups/<timestamp>/` exists with at least one file; run `argo import $ARGO_HOME/backups/<timestamp>` and assert it exits 0.

**Verification:**
- [ ] `make update-smoke` exits 0 locally.
- [ ] CI integration: ci.yml runs it on every PR.

**Dependencies:** M5.1, M4.

**Files touched:**
- `Makefile`.
- `tests/update_smoke/run.sh` (new).
- `.github/workflows/ci.yml` (add a job).

**Scope:** M.

**Owner role:** Implementer. (Parallel with M5.2 after M5.1.)

### Architect hardening checkpoint M5

Architect verifies the smoke harness is deterministic (no flakes on 10 re-runs in CI) and that it actually catches the failure modes it claims (intentionally break `.install_method` stamping; verify smoke fails loudly).

### Exit gate M5

IU-AC-6 (full), IU-AC-9 (full end-to-end), IU-AC-10, IU-AC-11 (full), IU-AC-15 partial (time budgets verified).

---

## M6 — Parity surfaces

**Goal.** Add `install-script` and `cmd-update` surfaces to the parity runner. Closes IU-AC-7, IU-AC-8 (full).

### Task M6.1: `install-script` parity surface

**Description:** New surface in `tools/parity_runner.py`. Runs upstream's `install.sh` in a hermes-baseline container + argo's `install.sh` in an argo container on the same base image. Diffs file trees, env vars, `--version` output, post-install symlinks. Tolerates renamed strings + URLs; flags anything else.

**Acceptance criteria:**
- [ ] Surface added to `tools/parity_runner.py` `SURFACES`.
- [ ] `tools/parity_runner.py --surface install-script` runs; exits 0 against today's baseline.

**Verification:**
- [ ] `python tools/parity_runner.py --surface install-script` exits 0.

**Dependencies:** M4, M5 (smoke harness fixtures reusable).

**Files touched:**
- `tools/parity_runner.py`.
- `tests/parity-expected.yml` (entries for any expected diffs — should be empty).

**Scope:** M.

**Owner role:** Implementer.

### Task M6.2: `cmd-update` parity surface

**Description:** Similar shape to M6.1. Both containers start at v(N-1); both run `cmd_update`; diff stdout/stderr; only-diff = renamed strings.

**Acceptance criteria:**
- [ ] Surface added.
- [ ] `tools/parity_runner.py --surface cmd-update` exits 0.

**Verification:**
- [ ] `python tools/parity_runner.py --surface cmd-update` exits 0.

**Dependencies:** M5.

**Files touched:**
- `tools/parity_runner.py`.

**Scope:** M.

**Owner role:** Implementer. (Parallel with M6.1.)

### Architect hardening checkpoint M6

Architect runs the full parity gate (`make parity`) against both surfaces. Confirms no false positives or missed divergences.

### Exit gate M6

IU-AC-7, IU-AC-8.

---

## M7 — Cross-loop hardening + docs

**Goal.** Architect pass over the full diff. Update customer-facing docs. Phase 3 closure. Closes IU-AC-15 (full); records architect-witnessed evidence for IU-AC-10 and IU-AC-11 already closed in M5.3.

### Task M7.1: Final architect verdict over the full diff

**Description:** Dispatch architect against `main..HEAD` for the loop. Run every hardening command in `.shepherd/install-update/standards.md`'s evidence schema. Verify all 15 ACs (IU-AC-1 through IU-AC-15) have empirical evidence in `progress.md`. Verdict: APPROVE / APPROVE-WITH-FOLLOW-UPS / REQUEST-CHANGES. Append "Phase 3 closure" section to `.shepherd/install-update/progress.md`.

**Acceptance criteria:**
- [ ] Phase 3 closure section exists in `progress.md`.
- [ ] Architect verdict = APPROVE or APPROVE-WITH-FOLLOW-UPS.

**Verification:**
- [ ] All commands in standards § Verification Evidence Schema have green output recorded.

**Dependencies:** M4, M5, M6 all closed.

**Files touched:**
- `.shepherd/install-update/progress.md`.

**Scope:** S.

**Owner role:** Architect.

### Task M7.2: Update AGENTS.md + README.md for new install/update UX

**Description:** AGENTS.md needs a § Customer install path section (curl URL, release branch, what the customer sees). README.md (the workshop one, on `main`) needs a "for customers" section pointing at the curl one-liner. The `release` branch's README.md is auto-renamed from upstream's; we don't touch it on `main` directly.

**Acceptance criteria:**
- [ ] AGENTS.md § Customer install path exists, includes the curl one-liner.
- [ ] README.md on `main` includes a customer install quickstart.

**Verification:**
- [ ] `grep -n "curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh" AGENTS.md README.md` returns both files.

**Dependencies:** M4 (URLs must be stable).

**Files touched:**
- `AGENTS.md`.
- `README.md`.

**Scope:** S.

**Owner role:** Implementer. (Parallel with M7.1.)

### Architect hardening checkpoint M7

Self — this milestone IS the architect pass.

### Exit gate M7

IU-AC-15 full (CI wall-clock measured); architect verdict APPROVE; all 15 ACs evidenced in progress.md. Loop complete.

---

## Checkpoint: DURABLE COMPLETE

- [ ] All 15 ACs green with evidence in `progress.md`.
- [ ] `make build && make leakage-static && make install-smoke && make update-smoke && make parity` all green.
- [ ] Customer-facing docs updated.
- [ ] Phase 3 architect verdict recorded.
- [ ] Loop closed; ready for next sync.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `OFFICIAL_REPO_URLS` rename-engine miss not caught until M3 — late in MVP cut | High (every `/update` warns) | M3 task M3.1 explicit check; promotes to a patch if needed |
| `release` branch force-push race | Low (workflow concurrency) | M4.2 uses `concurrency` + `--force-with-lease` |
| `make build` deterministic regression breaks release tarball reproducibility | Medium | Foundation AC-8 gate inherited; M4.2 leakage gate also catches large drift |
| Repo-public exposes patch series details | Low (Vadim accepted; hermes pattern) | Decision logged in `progress.md` |
| Telegram smoke flakiness in CI | Medium | M5.1 fake bot is localhost-only; no real API |
| Customer install times out on slow VPS | Low | NFR-1 = hermes + 10%; same dependency footprint |
| `release.py --publish` + M4.2 workflow both call `gh release create` → 422 | Medium | M4.2 uses `gh release upload --clobber` against the already-created release; documented inline at M4.2 |
| M4.2 tar step non-deterministic (timestamps/owner leak in) → IU-AC-12 fails | Medium | M4.2 AC mandates `--mtime=@$SOURCE_DATE_EPOCH --sort=name --owner=0 --group=0 --numeric-owner`; M4.3 verification re-runs and sha256-compares |
| Customer pulls curl URL between M2 and M4.3 → clones `main` (workshop) | Low (no public announcement yet) | Architect note at M2 checkpoint forbids URL sharing until M4.3 |
| IU-AC-10 (`is_managed`) never exercised end-to-end | Medium | M5.3 explicit assertion (stderr substring, not exit code — see M5.3 note); architect verifies on M7 |
| `argo --version` banner format (`Argo Agent v{__version__} ({__release_date__})`) means CalVer surfaces only via `__release_date__`, not as the primary version token | High (spec IU-AC-13 regex `argo \d{4}\.\d+\.\d+` fails without `--bump`) | M4.3 runs `release.py --bump patch --first-release --publish`; AC checks the rewritten `__release_date__`; trade-off documented at M4.3 Files-touched |
| `managed_error()` only prints to stderr and returns 0 (verified in dist/argo/argo_cli/config.py:376) | Medium (plan v1 wrongly required non-zero exit) | M5.3 assertion now substring-matches stderr; MVP checklist step 5 reworded |
| **B1 (banner regex) — RESOLVED 2026-05-28** | Closed | Spec § IU-AC-4 / IU-AC-13 amended to expect hermes banner format `Argo Agent v\d+\.\d+\.\d+ \(\d{4}\.\d+\.\d+\)` verbatim |
| **B2 (release.py workshop incompatibility) — RESOLVED 2026-05-28** | Closed | M4.3a builds `tools/argo_release.py` workshop wrapper; release.py never invoked directly from workshop layout |

## Open Questions

None — all spec-level OQs resolved at spec phase; both R5 blockers (B1, B2) resolved 2026-05-28.

## Verdict

`READY` — all five up-the-hill review rounds consumed; final 2 P0 blockers resolved by Vadim 2026-05-28 (B1: spec amendment; B2: `tools/argo_release.py` workshop wrapper). M1–M7 ready for dispatch.

---

## Notes for the Coordinator

- **MVP path (M1 → M4) is ~5–8 dispatch rounds**, fits in one focused session if Vadim authorizes the `gh repo edit` and tag-push moments.
- **Durable path (M5 → M7) is ~5–8 more rounds**, can run async after customer deploy.
- **M5.2 and M5.3 are parallelizable** after M5.1 lands; same for M6.1/M6.2; same for M7.1/M7.2.
- **All implementer dispatches** must record evidence per standards § Verification Evidence Schema in `progress.md`.
- **Foundation invariants** (upstream pristine, `make build` deterministic, `dist/` never on `main`) checked at every architect checkpoint.
