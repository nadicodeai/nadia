# Spec: argo — pristine-upstream fork of hermes-agent (v2)

> **Status:** Draft v2 (post opus review). Awaiting human approval.
> **Supersedes:** none. Greenfield repo. Legacy in-tree-rename implementation lives at `~/Code/argo-agent` (frozen, untouched).
> **Date:** 2026-05-27.
> **Reviewer findings incorporated:** C1 (overlay naming) · C2 (Docker reproducibility scope) · C3 (CI gate on upstream/) · M1 (bootstrap import path) · M2 (patch format) · M3 (parity suite) · M4 (exception audit) · M5 (patch assertions) · M6 (sync workdir).

---

## Confirmed Intent

- **Outcome.** A new GitHub repo `nadicodeai/argo` (private at start) that produces a Docker image `ghcr.io/nadicodeai/argo:latest` containing a fully-rebranded fork of NousResearch's hermes-agent. Customer-visible brand is `argo` (same as today's `argo-agent`). Internal architecture: tracked source is **pristine upstream**, fork additions live as a **quilt patch series** and an **overlay directory**, hermes→argo rebrand runs as a **build-time transform** producing the published Docker image. The renamed tree is **never committed**.

- **User.** Vadim, operating nadicodeai — a B2B business deploying this agent under the "argo" brand into customer companies. Customers see only "argo" everywhere.

- **Why now.** The legacy `~/Code/argo-agent` in-tree rename strategy has structurally failed. The 2026-05-26 sync produced 163 merge conflicts (130+ rename-collision noise) and silently dropped two fork features (`argo update` dispatch swap, `argo doctor --static/--live` wiring) before they were caught. Continuing to extend that approach burns engineering time on every sync indefinitely. Research on successful rebranded forks (Brave/Chromium, Rocky Linux/srpmproc, Debian quilt, MariaDB/MySQL, Forgejo) converged on: don't rename in tracked source.

- **Success.** Six concrete gates (G1–G6) defined under § Success Criteria. The headline three: (a) sync produces zero rename-collision conflicts; (b) `dist/argo/` is bit-identical across two engineers' machines on the same SHA; (c) customer-side parity suite (M3-expanded) passes against the new image with only brand-string diffs vs. legacy v0.14.0.

- **Constraint.** Maintainer experience is paramount. A weekly upstream sync MUST be performable in under 15 minutes by a single engineer. >30 min of conflict resolution = a defect against this spec; investigate the root cause (split a patch, upstream a feature) rather than normalizing the cost.

- **Out of scope.**
  - Migrating any deployment running legacy `argo-agent` to the new image (operator concern).
  - Publishing to PyPI (explicitly excluded — Docker-image-only).
  - Public-fork status on GitHub (private at start; visibility deferred).
  - Upstreaming a `BRAND_NAME` config to hermes-agent (would shrink our patch set but is a separate workstream).
  - Customer-specific branding overlays (single `argo` brand; per-customer is v2).
  - `argo doctor --live` (deferred until G1–G3 are met).
  - Reusing the legacy `argo-agent` repo as a starting point. **This repo starts empty.**
  - Docker layer-hash reproducibility (best-effort via `SOURCE_DATE_EPOCH`; not a gate — see AC-8 rationale).

---

## Tech Stack

Inherited from upstream `hermes-agent`. Divergence costs us on every sync; deviate only with written justification.

| Layer | Choice | Source / version |
|---|---|---|
| Runtime | Python `>=3.11`, type-check target `3.13` | upstream `pyproject.toml` |
| Build backend | `setuptools>=61.0` | upstream |
| Dependency manager | `uv` (exact-pinned, lockfile) | upstream convention |
| Linter | `ruff==0.15.10` (`PLW1514` only) | upstream |
| Type checker | `ty==0.0.21` (Astral) | upstream |
| Test framework | `pytest==9.0.2`, `pytest-asyncio==1.3.0`, `pytest-timeout==2.4.0` | upstream |

**Fork-only tooling** (added by this spec):

| Layer | Choice | Rationale |
|---|---|---|
| Upstream incorporation | `git subtree` (single-repo, in-tree directory) | One `git clone` is enough. No `--recurse-submodules`. CI doesn't deal with submodule refs. The Brave / Debian model. |
| Patch series manager | `quilt==0.67+` | Mature, text-format, language-agnostic, Debian-standard. Avoids the StGit learning curve. |
| Patch format | `diff -up --git` | Handles binary files, mode changes, renames. Plain `diff -u` cannot. (M2 fix.) |
| Build orchestrator | `make` plus Python helpers under `tools/` | Universal; engine is Python. |
| Container build | `docker buildx` (multi-platform) | Matches legacy repo's M5 workflow. |
| Registry | `ghcr.io/nadicodeai/argo` | Same model as legacy; no PyPI. |

**No new runtime dependencies.** Build-time rename engine uses stdlib + `pyyaml` (already an upstream dep). `quilt` and `make` are dev-time only — never shipped in the runtime image.

---

## Commands

Run from `~/Code/argo` repo root. All paths POSIX.

| Purpose | Command |
|---|---|
| One-time setup | `make bootstrap` |
| Sync from upstream | `make sync` |
| Resume after sync conflict | `make sync-resume` |
| Reset the sync workdir | `make sync-reset` |
| Build the renamed tree | `make build` → `dist/argo/` |
| Build the Docker image | `make image` → `ghcr.io/nadicodeai/argo:dev` |
| Push image to ghcr | `make publish` |
| Lint | `make lint` |
| Type-check | `make typecheck` |
| Run tests | `make test` |
| Static leakage scan | `make leakage-static` |
| Parity test suite (vs legacy) | `make parity` |
| Create a new patch | `make patch-new NAME=<slug>` |
| Refresh the current patch | `make patch-refresh` |
| List patches | `make patch-list` |

`argo update` from the legacy repo does **not** exist as a maintainer command in this repo. Maintainers use `make sync`. Customers update with `docker pull ghcr.io/nadicodeai/argo:latest`. (The in-container `argo update` subcommand is preserved as a no-op stub that prints the docker-pull instruction — see OQ-6, resolved.)

---

## Project Structure

```
~/Code/argo/
├── .shepherd/
│   ├── spec.md                   # ← this file
│   ├── plan.md                   # Written by the plan skill after spec approval
│   ├── standards.md              # Inherited + fork-specific style rules
│   └── progress.md               # Per-milestone progress log
│
├── upstream/                     # git subtree at a pinned hermes-agent SHA.
│   ├── hermes_agent/             # ← still "hermes". DO NOT EDIT IN TRACKED SOURCE.
│   ├── hermes_cli/               # ← still "hermes". DO NOT EDIT.
│   ├── tests/                    # Upstream tests. DO NOT EDIT.
│   ├── pyproject.toml            # Upstream's. DO NOT EDIT.
│   └── .commit                   # ← single-line text file; pinned SHA. Committed.
│                                 # CI gate (FR-15) rejects any PR that diffs
│                                 # upstream/ outside `make sync` automation.
│
├── overlay/                      # Files this fork adds. Layout MIRRORS upstream
│   │                             # paths so the rename engine processes overlay
│   │                             # uniformly. C1 resolution: overlay uses HERMES
│   │                             # names; engine renames overlay AND upstream
│   │                             # together in the same pass against dist/.
│   ├── hermes_cli/               # NOTE: overlay dirs are "hermes_*" — engine
│   │   │                         # renames them to "argo_*" in dist/.
│   │   ├── argo_update.py        # No-op stub: prints `docker pull …` instruction.
│   │   ├── doctor_leakage.py     # The --static scan logic.
│   │   └── overlay_init.py       # Wires overlay imports into the CLI.
│   ├── hermes_sync/              # The rename engine (renamed at build to argo_sync).
│   │   ├── config.py
│   │   ├── engine.py
│   │   ├── errors.py
│   │   ├── manifest.py
│   │   └── passes/
│   └── tests/
│       ├── test_deployment_smoke.py
│       ├── test_cmd_argo_doctor.py
│       ├── test_full_rename_config.py     # Exempted from rename (matches hermes
│       │                                  # literals as FROM keys).
│       ├── test_parity.py                 # vs ghcr.io/nadicodeai/argo-agent:0.14.0
│       └── fixtures/recorded_model/
│
├── patches/                      # quilt-managed patch series. The fork's IP.
│   ├── series                    # Ordered patch filenames. `#` comments out.
│   ├── 0001-fork-notice-readme.patch
│   ├── 0002-rebrand-urls-preserve-upstream.patch    # may be moot if argo-rename.yaml covers it; audit M2
│   ├── 0003-ci-gate-pypi-publish.patch
│   ├── 0004-ci-gate-vercel-deploy.patch
│   ├── 0005-docker-publish-ghcr.patch
│   ├── 0006-gitleaks-allowlist.patch
│   ├── 0007-browser-test-skip-gate.patch
│   └── …
│
├── patches/asserts/              # Per-patch grep-pattern assertions (FR-14).
│   ├── 0001-fork-notice-readme.txt
│   ├── 0005-docker-publish-ghcr.txt
│   └── …                          # Optional per patch; load-bearing patches MUST.
│
├── tools/                        # Build-time tooling. Never shipped in the image.
│   ├── build.py                  # Orchestrates copy → patches → overlay → rename.
│   ├── rebrand.py                # Entrypoint that imports overlay/hermes_sync/
│   │                             # directly (M1 fix), runs against dist/argo/.
│   ├── verify_no_leakage.py      # Build-gate check (FR-12). Honors skip_contexts.
│   ├── sync.py                   # Maintainer-facing sync workflow.
│   └── parity_runner.py          # Builds parity diffs vs ghcr.io/nadicodeai/argo-agent:0.14.0
│
├── scripts/
│   ├── sync.sh                   # `make sync` entrypoint (wraps tools/sync.py).
│   ├── bootstrap.sh              # `make bootstrap` entrypoint.
│   └── publish.sh                # `make publish`: tag + push.
│
├── argo-rename.yaml              # Declarative rename + exceptions. Inherited
│                                 # from legacy, audited for new layout (M4 fix).
│
├── Dockerfile                    # Multi-stage. Build stage runs rename engine.
│                                 # Final stage copies ONLY dist/argo/ + deps.
│                                 # upstream/, patches/, overlay/, tools/ never
│                                 # appear in the final image.
│
├── .sync-workdir/                # GITIGNORED. Persistent quilt working tree for
│                                 # `make sync` conflict resolution. Separate from
│                                 # dist/ which is regenerated on every build (M6).
│
├── .github/
│   └── workflows/
│       ├── ci.yml                # PR gate: lint, build, test, leakage, parity,
│       │                          # plus upstream/-diff check (FR-15).
│       ├── sync.yml              # Weekly cron: `make sync` + open PR.
│       ├── docker-publish.yml    # On main merge: image + push.
│       └── release.yml           # On tag: image + push with version tag.
│
├── Makefile                      # Stable user-facing entrypoint surface.
├── .gitignore                    # dist/, .sync-workdir/, .quilt/, *.rej, *.orig
├── .gitattributes                # upstream/* linguist-vendored=true; text=auto eol=lf
├── AGENTS.md                     # ≤200 lines; points at .shepherd/ and patch ops.
└── README.md                     # `docker pull` quickstart + fork notice.
```

**Strict layout invariants** (CI-enforced):

- **I-1.** `git diff $(cat upstream/.commit) HEAD -- upstream/` MUST be empty. Verified by `tools/check_upstream_pristine.py`. (FR-15.)
- **I-2.** Every file in `patches/` MUST appear in `patches/series` (orphan check).
- **I-3.** Every patch in `patches/` MUST apply cleanly via `quilt push -a` (verified by `make build`).
- **I-4.** `dist/` and `.sync-workdir/` MUST be in `.gitignore`. Never committed.
- **I-5.** Every patch whose name appears in `patches/asserts/manifest.txt` MUST have its assertion file present and its assertions satisfy `dist/argo/` after build (FR-14).

---

## Code Style

Inherits from `.shepherd/standards.md`. Fork-specific rules below.

### Overlay authorship: use HERMES names

Per C1 resolution: overlay code uses upstream's hermes-named identifiers, paths, and imports. The build-time rename engine processes overlay and upstream uniformly when producing `dist/argo/`.

```python
# overlay/hermes_cli/doctor_leakage.py — overlay code as authored.
# After `make build`, this file ends up at dist/argo/argo_cli/doctor_leakage.py
# with all "hermes" tokens rewritten to "argo".

from __future__ import annotations

from pathlib import Path

from hermes_sync.config import RenameConfig       # ← hermes_sync, not argo_sync
from hermes_sync.errors import LeakageDetected


def run_static(repo: Path, rename_yaml: Path, *, verbose: bool = False) -> list[Path]:
    """Scan *repo* for case-insensitive ``hermes`` hits outside exceptions list."""
    cfg = RenameConfig.load(rename_yaml)
    hits: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or cfg.matches_exception(path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "hermes" in text.lower():
            hits.append(path)
            if verbose:
                print(f"  LEAK: {path}")
    return hits
```

### Patch authorship

- One patch = one logical fork change. Never bundle.
- `Subject:` is imperative, ≤72 chars: `Subject: Wire --static and --live into hermes doctor`.
- Patches reference **hermes** symbols (upstream surface).
- Body explains WHY, not what.
- Patch >200 lines or touching >5 unrelated files → split it.
- **Load-bearing patches MUST have a `patches/asserts/<patch>.txt` file** containing one grep pattern per line that MUST appear in `dist/argo/` after build (FR-14). Comments allowed via leading `#`.

### Build-tool authorship

- Pure-Python where possible; `make` orchestrates, doesn't do logic.
- `tools/rebrand.py` MUST import the rename engine from `overlay/hermes_sync/` via `sys.path.insert(0, "overlay")`, NOT from `dist/argo/`. (M1 fix.)

---

## Functional Requirements

**FR-1. Pristine upstream subtree.** `upstream/` populated via `git subtree add --prefix=upstream <hermes-agent-url> <sha> --squash` and updated via `git subtree pull --prefix=upstream <hermes-agent-url> main --squash`. Pinned SHA recorded in `upstream/.commit` (single-line UTF-8 text file).

**FR-2. Quilt patch series.** All patch files live in `patches/`. `patches/series` lists them in apply order, one filename per line. Comment lines (`# ...`) are allowed and disable the patch. **Patch files use `diff -up --git` format** so binary patches, file renames, and mode-bit changes are representable. (M2 fix.) Build fails if `quilt push -a` fails.

**FR-3. Overlay directory.** `overlay/` contains files the fork adds. Layout mirrors upstream's path conventions: an overlay file destined for `dist/argo/argo_cli/foo.py` lives at `overlay/hermes_cli/foo.py`. The rename engine processes overlay and upstream uniformly. (C1 resolution.) `make build` copies overlay last, before rename; if an overlay path collides with the post-patch upstream tree, the build fails loudly with the colliding path.

**FR-4. Build orchestrator.** `tools/build.py` is a pure-Python script that:

1. `rm -rf dist/argo/` (clean slate).
2. `cp -r upstream/* dist/argo/` (preserving file modes).
3. `cd dist/argo && quilt push -a` (applies the patch series in order).
4. `cp -r overlay/* dist/argo/` (overlay copy; fails on collision).
5. `python tools/rebrand.py dist/argo/` (rename engine in-place). The rebrand script imports the engine from `overlay/hermes_sync/` via `sys.path.insert(0, "overlay")` (M1 fix), so the engine is available before any prior build exists.
6. Run `patches/asserts/*.txt` assertions against `dist/argo/` (FR-14). Fail on any unsatisfied assertion.
7. Write `dist/argo/.argo/build-manifest.json` deterministically (sort_keys, indent=2) with: `upstream_sha`, `patches_applied`, `overlay_files_added`, `files_touched_by_rename`, `assertions_checked`, `ran_at` (ISO-8601 UTC).
8. Exit non-zero on any failure with the offending file/patch printed.

**FR-5. Rename engine.** Lifted from the legacy `~/Code/argo-agent/argo_sync/` verbatim, with the package path changed from `argo_sync/` to `overlay/hermes_sync/` (so the engine itself renames to `argo_sync` in `dist/argo/`). Idempotent: `tools/rebrand.py` against an already-rebranded `dist/argo/` produces zero diffs (legacy AC-3).

**FR-6. Build manifest.** `dist/argo/.argo/build-manifest.json` is deterministic JSON containing the keys listed in FR-4 step 7. Committed into the Docker image (not into the source repo). Surfaced via `argo --version --verbose`.

**FR-7. Docker image.** Built FROM a multi-stage Dockerfile. Final stage contains ONLY `dist/argo/` and its runtime dependencies. `upstream/`, `patches/`, `overlay/`, `tools/`, `.shepherd/`, `scripts/` never appear in the final image. Tagged as `:dev` for local, `:<git-sha-short>` for `main` builds, `:latest` + `:v<X.Y.Z>` on release tags. Runtime surface (CMD, ENV ARGO_HOME, volumes, ports) matches legacy `argo-agent` v0.14.0.

**FR-8. Sync workflow.** `make sync` runs `tools/sync.py` which:

1. Verify working tree is clean (`git status --porcelain` empty).
2. `git subtree pull --prefix=upstream <upstream-url> main --squash`. On conflict, exit non-zero with instructions.
3. Update `upstream/.commit` with the new pinned SHA.
4. **Conflict-resolution workdir:** populate `.sync-workdir/` with `cp -r upstream/* .sync-workdir/` then `cd .sync-workdir && quilt push -a`. **`.sync-workdir/` is gitignored and persistent across sync attempts.** It is NOT `dist/argo/` — that is regenerated on every build and would clobber manual conflict edits (M6 fix).
5. If `quilt push -a` fails: print the failing patch, the conflicting hunks; leave `.sync-workdir/` in the half-applied state; print `make sync-resume` instructions; exit non-zero.
6. If `quilt push -a` succeeds: run the **verification build** via `make build`. If the build (including FR-14 assertions and FR-12 leakage scan) passes, the sync is good.
7. Stage `upstream/` + `upstream/.commit` + any patches refreshed via `quilt refresh` (copied from `.sync-workdir/patches/` back to `patches/`). Commit with `sync: upstream <short-sha> (<n> patches refreshed)`.

**FR-9. Sync resume.** `make sync-resume` runs after manual conflict resolution in `.sync-workdir/`:

1. Verify `.sync-workdir/` exists and has at least one resolved `.rej` file or recent edits.
2. `cd .sync-workdir && quilt refresh` (regenerates the conflicted patch).
3. Copy refreshed patches from `.sync-workdir/patches/` back to `patches/`.
4. Re-run `quilt push -a` to verify the rest of the series still applies.
5. Run `make build` to verify end-to-end. Fail on FR-14 assertion or FR-12 leakage failure.
6. Stage + commit per FR-8 step 7.

`make sync-reset` wipes `.sync-workdir/` and starts the next sync clean. Use after abandoning a sync attempt.

**FR-10. Bootstrap workflow.** `make bootstrap` runs ONCE on an empty `~/Code/argo` (just `git init`-ed):

1. Verify `upstream/` doesn't exist (refuse to overwrite).
2. `git subtree add --prefix=upstream https://github.com/NousResearch/hermes-agent main --squash`.
3. Record SHA in `upstream/.commit`.
4. Create `patches/series` (empty file).
5. Create `patches/asserts/manifest.txt` (empty file).
6. Copy `argo_sync/` from legacy → `overlay/hermes_sync/` (one-time lift).
7. Copy `argo-rename.yaml` from legacy → repo root; audit/strip dead exception entries for the new layout (M4 — semi-automated: run a script that warns about entries with no matching files in the new structure).
8. Copy `tests/test_full_rename_config.py`, `tests/test_deployment_smoke.py`, `tests/fixtures/recorded_model/` from legacy → `overlay/tests/`. (Lifted with hermes names; engine renames them.)
9. Write minimal `Dockerfile`, `Makefile`, `.gitignore`, `.gitattributes`, `.github/workflows/ci.yml`, `AGENTS.md`, `README.md` from spec scaffolds in `tools/scaffolds/`.
10. Stage everything and PREPARE a commit message `bootstrap: pristine fork at hermes-agent@<sha>`. User commits.

**FR-11. No PyPI publishing.** No `upload_to_pypi.yml` workflow exists. The Docker image is the only published artifact. (Inside the image, the renamed package IS pip-installable via `pip install -e /opt/argo`, but it's never uploaded.)

**FR-12. Static leakage gate.** `tools/verify_no_leakage.py` (called by `make leakage-static`):

1. Runs after `make build`.
2. Loads `argo-rename.yaml` to get `exceptions:` (glob paths) and `skip_contexts:` (regex patterns that exempt matched substrings).
3. Recursively scans `dist/argo/` for case-insensitive `hermes` occurrences.
4. Exits 0 iff every hit is covered by exceptions OR skip_contexts. Otherwise prints the uncovered hits and exits 1.

A naive `grep -i hermes` is insufficient and explicitly forbidden — `argo-rename.yaml` itself contains `hermes` literals as FROM keys, and the engine's pass code legitimately contains `hermes` constants.

**FR-13. AGENTS.md + README.** `AGENTS.md` ≤200 lines, points at `.shepherd/spec.md`, `.shepherd/standards.md`, and patch ops. `README.md` contains a `docker pull ghcr.io/nadicodeai/argo:latest` quickstart + a fork-notice block crediting upstream (NousResearch/hermes-agent).

**FR-14. Per-patch assertions.** (NEW — M5 fix.) Load-bearing patches MUST have an assertion file at `patches/asserts/<patch-name>.txt`. Format:

```
# Each non-comment line is a grep pattern that MUST appear in dist/argo/
# Pattern is fixed-string by default; prefix with `regex:` for regex.
# Prefix with `path:` to restrict to a specific path glob.

# Example for 0005-docker-publish-ghcr.patch:
path:argo_cli/main.py
regex:cmd_argo_update
ghcr.io/nadicodeai/argo
```

`tools/build.py` step 6 runs these assertions after rename. Fails the build if any assertion is unsatisfied. This catches the failure mode where `quilt refresh` after conflict resolution silently drops a fork line — the assertion fires.

`patches/asserts/manifest.txt` lists which patches REQUIRE assertions (one filename per line). Adding a load-bearing patch without an entry is a review gate, not a CI gate (judgment call).

**FR-15. Upstream-pristine CI gate.** (NEW — C3 fix.) `.github/workflows/ci.yml` includes a job `upstream-pristine` that runs:

```
diff <(git ls-tree -r HEAD upstream/) <(git ls-tree -r $(cat upstream/.commit):upstream/)
```

(or equivalent via `tools/check_upstream_pristine.py`). Any non-empty diff fails the job. The only paths that may edit `upstream/` are `make sync` and `make bootstrap`; both produce commits in dedicated automation, never user-driven.

**FR-16. Parity test suite.** (NEW — M3 fix.) `overlay/tests/test_parity.py` + `tools/parity_runner.py` exercise both images side-by-side and diff outputs:

- Both images: `ghcr.io/nadicodeai/argo-agent:0.14.0` (legacy baseline) and the under-test image.
- Surfaces tested (per AC-7-sharpened):
  1. `argo --help`, `argo --version`
  2. `argo doctor --static`
  3. API server: `GET /health`, `GET /v1/models` (with stub model backend)
  4. MCP plugin discovery: `argo mcp list` against a fixture plugin dir
  5. Hook dispatch: `argo hook fire <event>` with a fixture hook
  6. OAuth flow init: `argo auth start --provider stub` returns expected URL
  7. Session persistence: `argo chat --once` with `ARGO_HOME=/tmp/x` writes same JSON keys
- Each output is normalized by substituting `hermes→argo`, `Hermes→Argo`, `HERMES→ARGO`, `hermes-agent→argo` in the legacy output. The diff vs the new image's output MUST be empty.
- Any non-brand-string diff is a regression; CI fails.
- Parity suite is `make parity`; runs as part of `make test` only when both images are pullable (skipped otherwise, with a warning).

---

## Behavioral Acceptance Criteria

**AC-1 (bootstrap).** Given empty `~/Code/argo` with `git init`, when `make bootstrap` runs, then within 60 seconds the repo has: populated `upstream/`, recorded `upstream/.commit`, empty `patches/series`, scaffolded `overlay/hermes_sync/`, copied `argo-rename.yaml` (with dead exceptions stripped), scaffolded Dockerfile/Makefile/CI/AGENTS/README. `make build` against this state succeeds; `make leakage-static` exits 0. `git status` is clean (no `.rej`, no untracked `.quilt/`, no backup files).

**AC-2 (zero-conflict pristine sync).** Given a pre-recorded sync-fixture under `tests/fixtures/sync-fixture-200/` (200 changed files constructed by replaying upstream's last 20 commits as one patch), when `make sync` runs against an empty patch series, then sync completes with zero merge conflicts; build produces a clean `dist/argo/`; leakage scan passes. The fixture is real upstream content recorded once and committed for reproducibility.

**AC-3 (single non-overlapping patch sync).** Given `patches/series` contains one patch that adds a `--static` flag to `hermes_cli/main.py`, and upstream refactors `hermes_cli/main.py` away from the patch's insertion lines, when `make sync` runs, then `quilt push -a` succeeds without manual intervention; `dist/argo/` contains both upstream's refactor and our flag; FR-14 assertion for the patch passes.

**AC-4 (overlapping-patch sync — must fail loudly).** Given a patch that edits line N of `hermes_cli/main.py` and upstream changes that same line, when `make sync` runs, then `quilt push -a` fails with output naming **the patch file AND the line in the patch where the conflict occurred** (not just the upstream file). `.sync-workdir/` is left in a recoverable state; FR-9 recovery does NOT lose data even if the user runs `make build` in the middle (because `.sync-workdir/` is separate from `dist/`).

**AC-5 (rename idempotency).** Given a built `dist/argo/`, when `tools/rebrand.py` re-runs against `dist/argo/`, then zero diffs are produced. (Inherited from legacy.)

**AC-6 (zero-leakage build artifact).** Given a clean build, when `make leakage-static` runs against `dist/argo/`, then it exits 0. The scan honors `argo-rename.yaml`'s `skip_contexts` AND `exceptions`. Tested with a positive case (file with `hermes` outside both lists → scan fails) AND a negative case (file with `hermes` inside `skip_contexts` → scan passes), both as fixtures.

**AC-7 (functional parity vs legacy).** (M3 sharpened.) Given `ghcr.io/nadicodeai/argo:latest` is built, when `make parity` runs against both the new image and `ghcr.io/nadicodeai/argo-agent:0.14.0`, then for every surface listed in FR-16 the **parity diff is empty modulo brand-string substitution**. Any non-brand diff is a regression; CI fails. Parity suite is the gate for the customer-parity G3.

**AC-8 (dist/ determinism — not Docker layers).** (C2 sharpened.) Given two engineers run `make build` on the same `main` SHA with `SOURCE_DATE_EPOCH=<commit-timestamp>` and identical `argo-rename.yaml`, then the **`dist/argo/` directory tree is bit-identical** (verified by recursive content hash). Additionally, `argo --version --verbose` output from the built tree is byte-identical. Full Docker layer-hash reproducibility is best-effort (timestamps, uid/gid, base image drift) and explicitly NOT a gate.

**AC-9 (CI gate).** When a PR is opened against `main`, CI runs and ALL of `make lint`, `make typecheck`, `make build`, `make test`, `make leakage-static`, `make parity`, and the **upstream-pristine job** (FR-15) MUST pass before merge. Branch protection enforces.

**AC-10 (legacy repo untouched).** Throughout the development of this repo, `~/Code/argo-agent` MUST remain unmodified. Verified by hashing the recursive tree of `~/Code/argo-agent` at session start and end; hashes match.

**AC-11 (sync workdir isolation).** (M6.) Given `make sync` fails at the quilt step and leaves `.sync-workdir/` populated, when the user runs `make build` (without resuming sync), then `make build` succeeds against the CURRENT (pre-sync) tree using a separate temp directory; `.sync-workdir/` is untouched. The user can then `make sync-resume` and pick up where they left off.

**AC-12 (patch assertion fail).** (FR-14.) Given a patch with assertion file containing pattern `cmd_argo_update`, when a `quilt refresh` after manual conflict resolution accidentally drops that line, when `make build` next runs, then it fails at step 6 (FR-4) with `Assertion failed: 0005-docker-publish-ghcr — pattern 'cmd_argo_update' not found in dist/argo/argo_cli/main.py`.

---

## Non-Functional Requirements

- **NFR-1. Sync time.** Typical `make sync` (no patch conflicts) completes in ≤2 min wall-clock. Build (rename + Docker) in ≤5 min.
- **NFR-2. Patch set size.** Target ≤20 patches; 21–30 triggers audit pressure; 31+ requires patch-count freeze (no new patches until audit reduces).
- **NFR-3. Image size.** Final image MUST NOT exceed legacy image by >5%.
- **NFR-4. dist/ determinism.** As AC-8.
- **NFR-5. Maintainer onboarding.** A new engineer completes their first successful `make sync` within 30 minutes given access + `AGENTS.md` + `.shepherd/spec.md`.

---

## Boundaries

**Always:**
- Edit only `patches/`, `overlay/`, `tools/`, `scripts/`, `Makefile`, `.github/`, `.shepherd/`, `Dockerfile`, `README.md`, `AGENTS.md`, `argo-rename.yaml`, `.gitignore`, `.gitattributes`.
- Pass `encoding="utf-8"` to every file I/O (PLW1514).
- Use **hermes** names in patches AND overlay code. Engine does the rename at build time.
- Patch files in `diff -up --git` format.
- After any patch/overlay edit, run `make build` locally before committing.
- Treat `argo-rename.yaml` as load-bearing — every change passes `make leakage-static`.
- Add a `patches/asserts/<patch>.txt` for every load-bearing patch (FR-14).

**Ask first:**
- Adding any new top-level Python runtime dependency to upstream (consider overlay-only instead).
- Adding a patch >200 lines or touching >5 unrelated files. Split it.
- Changing the rename engine's pass order (content → filenames → directories).
- Bumping `upstream/.commit` to a SHA older than current (downgrade).
- Adding an entry to `argo-rename.yaml`'s `exceptions:` list (MUST include `why:`).
- Inlining a git submodule that upstream adds (vs nesting it as a separate subtree).

**Never:**
- Edit files under `upstream/` directly. Use a patch.
- Edit files under `dist/` or `.sync-workdir/`. Both are regenerated/managed.
- Commit `dist/`, `.sync-workdir/`, `.quilt/`, `*.rej`, `*.orig`.
- Force-push `main` without explicit user approval.
- `git push upstream` — upstream is read-only.
- Publish to PyPI. Docker-image-only.
- Touch `~/Code/argo-agent` from this repo's workflows.
- Add a fork-feature commit on `main` outside the `patches/` / `overlay/` system.
- Skip `make leakage-static`, `make parity`, or the upstream-pristine job in CI.
- Run `make build` while `.sync-workdir/` has unresolved conflicts (would invalidate verification).
- Past 20 patches, add new patches before completing the audit-and-reduce cycle (NFR-2).

---

## Migration from Legacy Repo

This repo does NOT import git history from `~/Code/argo-agent`. We start fresh. Specific assets lifted (one-time copy at bootstrap):

1. `argo-rename.yaml` — verbatim, then audit/strip dead exceptions in M2 (M4 fix).
2. `argo_sync/` → `overlay/hermes_sync/` — the rename engine. Package path renamed once.
3. `tests/test_full_rename_config.py` → `overlay/tests/test_full_rename_config.py`.
4. `tests/test_deployment_smoke.py` → `overlay/tests/test_deployment_smoke.py`.
5. `tests/test_cmd_argo_doctor.py` → `overlay/tests/`.
6. `tests/fixtures/recorded_model/` → `overlay/tests/fixtures/recorded_model/`.
7. `argo_cli/argo_update.py` — heavily simplified to a no-op stub in `overlay/hermes_cli/argo_update.py` (prints docker-pull instruction).
8. `argo_cli/doctor_leakage.py` → `overlay/hermes_cli/doctor_leakage.py`.

**Initial patch set** (recast from legacy fork commits as patches against pristine upstream):

| Patch | Source legacy commit(s) | Likely scope | Assert needed? |
|---|---|---|---|
| `0001-fork-notice-readme.patch` | `3effed6b7` + `782a7f15b` | README fork-notice + attribution | YES |
| `0002-rebrand-urls-preserve-upstream.patch` | part of `3effed6b7` | URL corrections — may be redundant with rename config; audit in M2 | MAYBE |
| `0003-ci-gate-pypi-publish.patch` | `8bceb51de` + `8fda451aa` + `b8e6e76a2` | gate upload_to_pypi.yml off | YES |
| `0004-ci-gate-vercel-deploy.patch` | `ff5ca129c` | gate deploy-site / skills-index workflows | YES |
| `0005-docker-publish-ghcr.patch` | `5c5dd471a` | publish ghcr.io/nadicodeai/argo (note: image name `argo` not `argo-agent`) | YES |
| `0006-gitleaks-allowlist.patch` | `fea0bf210` | gitleaks false positives | NO |
| `0007-browser-test-skip-gate.patch` | part of `deb150128` | `ARGO_E2E_BROWSER` skip condition | YES |
| `0008-pyproject-rename-targets.patch` | (new) | entries the rename engine needs to find pyproject.toml targets | MAYBE |

Some may collapse or expand during the actual migration. The plan skill enumerates the M-numbered tasks.

---

## Implementation Order (overview)

The plan skill writes the detailed milestones. For navigability:

1. **M1 — Bootstrap.** `make bootstrap`, verify `make build` produces clean `dist/argo/` with empty patches. AC-1.
2. **M2 — Audit + lift assets.** Audit `argo-rename.yaml` exceptions for new layout. Lift overlay assets. Run leakage scan; iterate.
3. **M3 — Initial patch series.** Extract the 8 patches one by one; each followed by `make build` + leakage + assertions.
4. **M4 — CI gates.** `ci.yml` with all jobs (FR-15 upstream-pristine, leakage, parity).
5. **M5 — Docker pipeline.** Dockerfile multi-stage; `make image`; `make publish`. Reproducible `dist/argo/` (AC-8).
6. **M6 — Parity suite.** Build the parity runner against legacy v0.14.0 image. AC-7.
7. **M7 — First real sync.** Run `make sync` against current upstream HEAD; resolve any conflicts; tag the result.
8. **M8 — Documentation freeze.** Finalize AGENTS.md, README.md, .shepherd/standards.md. Validate G6 onboarding.

---

## Open Questions

- **OQ-1. Subtree squash vs no-squash.** Squash (proposed) = small repo, no `git blame` into upstream. No-squash = blame works but adds GBs of history. **Decision: `--squash`.** Confirmed during M1.
- **OQ-2. Quilt vs Stacked Git.** Quilt (proposed) is text-format and portable; StGit is git-native. Spec assumes quilt. Reconsider if maintainer experience suffers in M3.
- **OQ-3. CI sync cadence.** Weekly cron (proposed) that opens a PR. Daily is too noisy; monthly is too lagged.
- **OQ-4. Multi-arch Docker.** linux/amd64 + linux/arm64 (proposed, matches legacy). Cross-compile arm64 via buildx + QEMU — adds ~10 min to image builds in CI; consider amd64-only on PRs and full multi-arch only on release tags.
- **OQ-5. Patch versioning.** Purely sequence-numbered (proposed): `0001-…`, `0002-…`. Renumber when inserting mid-series via `quilt new --at <pos>`.
- **OQ-6. In-container `argo update` UX.** **Decision: no-op stub** that prints `Use docker pull ghcr.io/nadicodeai/argo:latest`. Preserves muscle memory; doesn't mislead. Implemented in `overlay/hermes_cli/argo_update.py`.
- **OQ-7. Initial patch extraction fidelity.** **Decision: functional equivalence** (achieves the same end state) over commit-fidelity (textual reproduction). Each patch flagged for opus during M3 if it deviates substantively from its source commit.
- **OQ-8. Patch format.** (Reviewer-added.) **Decision: `diff -up --git`.** Captured in FR-2.
- **OQ-9. Build-time vs install-time rename.** Build-time (proposed); image ships pre-renamed. Install-time = customer container runs rename at boot; bigger image, slower startup, but more flexibility. **Decision: build-time.**
- **OQ-10. Rename engine in the final image.** After build, `argo_sync/` (renamed from `overlay/hermes_sync/`) is in the image. Customers could theoretically re-run it. **Decision: STRIP from final image stage** — engine is a build-time tool, not a runtime API. Removes a small attack surface. Verified by an AC-13 (add): "no `argo_sync/` in the final image."
- **OQ-11. Upstream tag tracking.** Track upstream `main` HEAD (proposed) or a release tag? Hermes-agent releases on tags; `main` is the rolling tip. **Decision: `main` HEAD with weekly cadence.** Allows quick security pickups. Revisit if upstream's `main` becomes unstable.
- **OQ-12. CI minutes budget.** Multi-arch + weekly auto-sync + per-PR full pipeline: estimate ~3000 minutes/month. Fits inside GitHub Actions paid plan; verify nadicodeai has one. (Flag for human confirmation.)
- **OQ-13. Secret handling for GHCR push.** Use a `secrets.GHCR_TOKEN` PAT scoped to `write:packages` only. Rotate annually. CI emits a warning when token age >330 days.
- **OQ-14. Overlay rename mode.** **Resolved by C1: overlay uses hermes names, engine processes overlay.** Captured in FR-3 and § Code Style.
- **OQ-15. Patch-set scaling endgame.** Hard thresholds: ≤20 patches healthy; 21–30 audit pressure; 31+ patch-count freeze. (Captured in Boundaries.)
- **OQ-16. Stylized brand strings.** Marketing copy with `HeRmEs`-style mixed-case slips through case-insensitive grep but is still leakage. Add a stylized-grep test fixture in M2.
- **OQ-17. File mode preservation across upstream → dist → image.** `cp -r` and `shutil.copytree` preserve modes by default; spec explicitly relies on this (FR-4 step 2). Verify in M1 with an executable test fixture.
- **OQ-18. Submodules inside upstream.** Hermes-agent has none today. If upstream adds one, `make sync` MUST fail loudly with: "upstream introduced a git submodule at <path>; decide between inlining vs nested subtree." Not silently ignored.
- **OQ-19. Line-ending normalization.** `.gitattributes` sets `text=auto eol=lf`. macOS contributors who run `quilt` may produce CRLF in patches if their editor is sloppy; `quilt push` may then mis-apply. CI gate: `git diff --check` on PRs.

---

## Success Criteria (G1–G6)

Migration is **done** when ALL hold simultaneously:

1. **G1 — Sync sanity.** `make sync` against a real fresh upstream HEAD (delta ≥100 changed files since the previous `upstream/.commit`) completes in ≤5 min with zero quilt failures OR ≤3 patches needing `quilt refresh`. Measured on a real sync, not a fixture.
2. **G2 — Build determinism.** Two engineers on different laptops, same `main` SHA, same `SOURCE_DATE_EPOCH`: their `dist/argo/` tree-hashes match. Their built `argo --version --verbose` outputs are byte-identical.
3. **G3 — Customer parity.** `make parity` against `ghcr.io/nadicodeai/argo:latest` vs `ghcr.io/nadicodeai/argo-agent:0.14.0` produces zero non-brand diffs across all surfaces in FR-16.
4. **G4 — CI green.** Branch protection on `main` enforces all CI jobs. Recent CI runs green.
5. **G5 — Legacy untouched.** Tree-hash of `~/Code/argo-agent` unchanged. `git -C ~/Code/argo-agent log --oneline -1` returns `9b8cf6bf5`.
6. **G6 — Docs onboarding.** A new engineer (or self-audit, re-reading docs cold) completes a successful `make sync` within 30 min using only AGENTS.md + spec.md.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `quilt refresh` silently drops fork-feature lines during conflict resolution | High | High | FR-14 per-patch assertions catch it at build time. |
| Upstream adds binary files (icons, fonts, model weights) inside hermes_agent/ | Medium | High | `diff -up --git` format handles binary patches (FR-2). |
| Upstream adds a git submodule | Low | High | `make sync` detects and fails loudly (OQ-18). |
| Rename engine misses a new identifier (`HermesXyz`) | Medium | Medium | The catch-all `Hermes → Argo` / `hermes → argo` covers most. Static leakage scan catches the rest. Stylized brand strings (OQ-16) need a fixture. |
| GHCR token rotation / auth rot | Medium | Medium | Annual rotation, CI warns at 330 days (OQ-13). |
| Multi-arch CI minutes exceed budget | Medium | Low | amd64 on PRs; multi-arch only on release tags (OQ-4). |
| `dist/` collision with quilt workdir destroys conflict edits | (mitigated) | High | `.sync-workdir/` is separate from `dist/` (FR-8, M6 fix). |
| Patch count grows past 30 | Medium | Medium | NFR-2 + Boundaries freeze rule. Quarterly audit. |
| Customer regression in a code path AC-7 didn't exercise | (mitigated) | High | Expanded parity suite (FR-16, AC-7 sharpened). |
| Quilt learning curve for maintainers | Medium | Medium | `make patch-new/refresh/list` Makefile shortcuts; 5-command cheatsheet in AGENTS.md. |
| `git subtree pull` slower than expected on large pulls | Low | Low | Acceptable (maintainer-only). |
| Upstream introduces a vulnerability that the patch set can't ride over | Low | High | Track upstream `main` weekly; security fixes propagate within 7 days (OQ-11). |
| Maintainer forgets to commit a refreshed patch | (mitigated) | Medium | CI gate: `git status` after `make build` MUST be empty. |
| Build stage in Docker multi-arch (QEMU emulation) is slow | Medium | Low | Cap multi-arch to release builds (OQ-4). |
| Customer muscle-memory: typing `argo update` inside container | Low | Low | No-op stub prints docker pull instruction (OQ-6). |

---

## Glossary

- **Subtree.** Directory imported from external git repo via `git subtree`. Tracked as normal files. Used for `upstream/`.
- **Quilt.** Patch-stack manager. Maintains an ordered series of textual patches that apply on top of an unmodified upstream tree.
- **Overlay.** Files this fork adds with no upstream counterpart. Live in `overlay/` using **hermes-named** paths. Engine renames them at build time alongside upstream.
- **Rename engine / rebrand.** Python code (`overlay/hermes_sync/`, renamed to `argo_sync` in `dist/`) that rewrites `hermes` → `argo`. Runs at build time against `dist/`, never against tracked source.
- **`dist/`.** Build output. Gitignored, regenerated on every `make build`.
- **`.sync-workdir/`.** Persistent workdir for conflict resolution during `make sync`. Gitignored. Separate from `dist/`. Cleared by `make sync-reset`.
- **Patch series.** Ordered patches in `patches/series`. Applied by `quilt push -a`. `#` at line start disables.
- **Pristine upstream.** `upstream/` contents = exact bytes of the commit pinned in `upstream/.commit`. Never edited directly.
- **Assertion.** A grep pattern in `patches/asserts/<patch>.txt` that MUST appear in `dist/argo/` after build (FR-14). Catches `quilt refresh` data loss.

---

## Provenance

- Informed by 2026-05-26 failed merge in `~/Code/argo-agent` (163 conflicts, 2 silent feature losses).
- Strategy: Brave/Chromium patches, Rocky Linux `srpmproc`, Debian `quilt`/`gbp`, Forgejo's failed soft-fork, MariaDB selective merge, OpenSearch hard-fork.
- Key insight: **never rename in tracked source.** Renamed tree is a build artifact.
- v2 incorporates opus review (2026-05-27): C1 (overlay naming), C2 (Docker reproducibility scope), C3 (CI gate on upstream/), M1–M6 fixes.
