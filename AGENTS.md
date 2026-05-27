# AGENTS.md

Instructions for AI agents (and humans) working on argo. Keep this short; deep references live in `.shepherd/`.

## What this repo is

`argo` is a rebranded fork of NousResearch's `hermes-agent`. Three rules describe the architecture:

1. **`upstream/` is pristine.** A `git subtree --squash` of `hermes-agent`'s `main`, pinned at the SHA recorded in `upstream/.commit`. Never edited directly.
2. **Fork changes live in `patches/` and `overlay/`.** `patches/` is a quilt-managed patch series. `overlay/` is additive files using **hermes-named** paths (e.g. `overlay/hermes_cli/argo_update.py`).
3. **The hermes→argo rebrand runs at build time.** The rename engine in `overlay/hermes_sync/` walks the post-patch tree and rewrites `hermes` → `argo` (per `argo-rename.yaml`). The renamed tree lands in `dist/argo/` and gets packaged into `ghcr.io/nadicodeai/argo:latest`. Tracked source is never renamed.

`tools/` holds the build-time Python (build.py, rebrand.py, sync.py, verify_no_leakage.py, parity_runner.py, run_assertions.py, check_upstream_pristine.py). It never ships in the image. `dist/` and `.sync-workdir/` are gitignored.

## Prerequisites

System tools (install once):

- `python >=3.11` (matches upstream).
- `quilt >=0.67` — `brew install quilt` on macOS, `apt install quilt` on Debian/Ubuntu, `pacman -S quilt` on Arch. Not on PyPI; required for every patch operation.
- `make`, `git`, `docker` (with buildx) — standard toolchain.

Python deps come from `upstream/pyproject.toml` via `uv` (also upstream's convention). For most maintainer flows (`make sync`, `make build`, `make leakage-static`), the system `python` + stdlib + `pyyaml` is enough.

## Reading order

1. **`.shepherd/spec.md`** — what we're building, contracts, acceptance criteria.
2. **`.shepherd/plan.md`** — ordered tasks M1.x → M8.x.
3. **`.shepherd/progress.md`** — current milestone state.
4. **`.shepherd/standards.md`** — coding/repo/process rules.

## Workflow at a glance

```bash
make help                          # discover all targets
make build                         # produce dist/argo/ (upstream + patches + overlay + rename)
make sync                          # pull upstream, re-apply patches, run verification build
make sync-resume                   # continue after manual conflict resolution in .sync-workdir/
make sync-reset                    # wipe .sync-workdir/ and start the next sync clean
make image                         # docker build ghcr.io/nadicodeai/argo:dev
make publish                       # tag + push to GHCR
make leakage-static                # static scan: no "hermes" leaks in dist/argo/
make parity                        # surface-diff vs legacy image (XFAIL-aware; see § Parity)
make check-upstream-pristine       # FR-15 gate: upstream/ matches the last sync commit
make check-legacy-untouched        # G5 gate: ~/Code/argo-agent unchanged
make patch-new NAME=<slug>         # start a new patch
make patch-refresh                 # quilt refresh the current patch
make patch-list                    # cat patches/series
```

`make build` and `make leakage-static` MUST both exit 0 before any commit that touches `patches/`, `overlay/`, `tools/`, or `argo-rename.yaml`.

## Upstream sync (the maintainer's main loop)

A typical weekly sync:

1. `make sync` — pulls upstream, advances `upstream/.commit`, populates `.sync-workdir/`, runs `quilt push -a` there, then runs `make build` for verification. If clean, commits as `sync: upstream <short-sha> (<N> patches refreshed)`.
2. On `quilt push -a` failure, the script prints the failing patch + hunks, leaves `.sync-workdir/` half-applied, and exits non-zero. **Do not run `make build` in this state** — it would not invalidate `.sync-workdir/` (they're separate dirs, AC-11), but `make build` from the pre-sync tree is meaningless mid-sync.
3. Resolve conflicts inside `.sync-workdir/<conflicting-file>`, then `cd .sync-workdir && quilt refresh` to regenerate the patch.
4. `make sync-resume` — copies the refreshed patch back to `patches/`, replays the remainder of the series, runs `make build`, commits.
5. If a sync attempt is abandoned, `make sync-reset` wipes `.sync-workdir/`.

`.sync-workdir/` is gitignored and persistent across sync attempts; it is NOT `dist/argo/`, which is regenerated on every build.

## Quilt cheatsheet

Five commands cover ~99% of patch work:

```bash
quilt new <NN>-<slug>.patch        # 1. start a patch (auto-appended to series)
quilt add <file>                    # 2. mark file as touched by the current patch
# ... edit file(s) ...
quilt refresh                       # 3. regenerate the patch file from the current state
quilt push -a                       # 4. apply all patches (or up to first failure)
quilt pop -a                        # 5. remove all patches (clean slate)
```

Other useful queries: `quilt series` (list), `quilt top` (which patch is on top), `quilt diff` (preview the current patch).

`.quiltrc` at repo root pins `quilt refresh` output to `-p ab --no-timestamps --no-index` — without that flag, refreshed patches would hash-differ across regenerations and break AC-8 determinism. Do not override.

## Hard rules

- **Never edit `upstream/`.** Use a patch. CI's `upstream-pristine` job (FR-15) blocks PRs that touch it outside `make sync`.
- **Never commit `dist/` or `.sync-workdir/`.**
- **Patches and overlay files use `hermes` names.** The engine renames at build.
- **Patch format is `diff -up --git`** (handles binary, modes, renames). Enforced by `.quiltrc`.
- **Load-bearing patches need `patches/asserts/<name>.txt`** with grep patterns (FR-14). Catches `quilt refresh` silently dropping fork lines after conflict resolution. List the patch's basename in `patches/asserts/manifest.txt`.
- **Reproducible builds: `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)` before `make build`.** Required for AC-8 (`dist/argo/` byte-identity across machines). `make image` already sets it via `--build-arg`.
- **Don't touch `~/Code/argo-agent`.** Legacy in-tree-rename repo, frozen at HEAD `9b8cf6bf5`. `make check-legacy-untouched` verifies.
- **CI prelude lives in `.github/actions/argo-setup/`.** Composite action that installs uv + Python + apt + pip deps for every workflow job; edit it (not the workflow preludes) when bumping `setup-uv`, the Python pin, or the default apt package list.

## Parity baseline

`tools/parity_runner.py` (M6) drives the customer-parity gate (FR-16, AC-7). The spec names `ghcr.io/nadicodeai/argo-agent:0.14.0` as the legacy baseline. As of issue #1's resolution that tag is built + published by `.github/workflows/publish-legacy-baseline.yml` (one-shot, `workflow_dispatch`) from the maintainer's frozen `~/Code/argo-agent` tree at SHA `9b8cf6bf5` (whose `pyproject.toml` reports version 0.14.0). The runner's `DEFAULT_LEGACY_IMAGE` constant now points at `:0.14.0`.

**Pre-publish prerequisite.** The frozen legacy SHA `9b8cf6bf58e23723d4d021fda529f3f3f397646d` is local-only on the maintainer's workstation; `nadicode/main` is behind it. Before running the workflow the maintainer MUST push the frozen ref to the remote (this does NOT modify the legacy worktree, only adds a tag, so AGENTS.md § Hard rule "Don't touch `~/Code/argo-agent`" is preserved):

```bash
cd ~/Code/argo-agent
git push nadicode 9b8cf6bf58e23723d4d021fda529f3f3f397646d:refs/tags/baseline-v0.14.0
```

**Workflow lifecycle.** `tests/parity-expected.yml` still lists the three "version-gap" XFAILs (`help`, `version`, `session-init`) pending re-validation. After the workflow has published `:0.14.0` and a local `make parity` confirms they evaporate, a follow-up commit prunes them from the whitelist and (if no XFAILs remain) drops `--allow-expected` from `make parity`. Until then, CI's `docker pull ghcr.io/nadicodeai/argo-agent:0.14.0` step will 404 — that's the intended signal that the publish workflow has not yet been triggered.

To keep the gate useful while the baseline catches up, the runner accepts `--allow-expected` (default for `make parity` and for the CI parity job) which reclassifies surfaces named in `tests/parity-expected.yml` as `XFAIL` — they are reported but do NOT drive a non-zero exit. Any surface FAILing that is NOT on the whitelist still blocks the gate. To see the unmasked diff during development:

```bash
make parity-strict   # or: python tools/parity_runner.py
```

Per-surface status (pre-publish snapshot; expected to change after the `:0.14.0` baseline lands):

| Surface         | Status              | Reason                                              |
| --------------- | ------------------- | --------------------------------------------------- |
| `help`          | XFAIL (pending re-validation) | v0.14.0 subcommand superset over v0.8.0 baseline |
| `version`       | XFAIL (pending re-validation) | v0.14.0 banner vs v0.8.0 banner          |
| `doctor-static` | SKIPPED             | legacy v0.8.0 lacks the `--static` flag (M3 target) |
| `mcp-list`      | PASS                | Dockerfile fix landed (M6 follow-up)                |
| `hook-fire`     | SKIPPED             | legacy v0.8.0 has no `hooks` subcommand             |
| `auth-start`    | PASS                | proxied via `auth list`; both empty + identical     |
| `session-init`  | XFAIL (pending re-validation) | persistence layout drift v0.8.0 → v0.14.0 |

Anything still on the XFAIL list AFTER the `:0.14.0` baseline has been published and `make parity` has been re-run is a true semantic divergence and should be filed as a tracked issue, not silently accepted.

## Slim image (M5/M6 history)

M5 produced a 371 MB slim runtime image; M6's parity gate exposed two crashes (`mcp list`, `sessions list`) that traced to a missing `tools/` Python package in the runtime stage. Patch 0008 + the M6 Dockerfile regressions fix landed those import paths, so the slim image now handles all FR-16 surfaces 1-7. The image still does NOT match legacy's 4.71 GB surface (no node/npm/playwright/ffmpeg/s6-overlay yet) — that broader expansion is M7+ territory, contingent on real customer surface needs. NFR-3 (image size within 5% of legacy) is intentionally NOT a gate at this scope; track via a follow-up OQ if it becomes customer-blocking.

## Common tasks

- **Add a fork change.** Decide patch (modifies an upstream file) vs overlay (purely new file). Patches need assertions when load-bearing.
- **Investigate a leakage scan failure.** `make build && python tools/verify_no_leakage.py dist/argo/ --verbose` prints the offending paths. Either fix the source so it doesn't introduce `hermes`, or add an exception to `argo-rename.yaml` with a `why:` comment.
- **Investigate a parity FAIL.** `make parity-strict` shows the raw diff. If it's a known baseline-version gap, document in `tests/parity-expected.yml`. Otherwise it's a real regression — find the patch or overlay change that introduced it.
- **Bump upstream.** `make sync`. If conflicts: resolve in `.sync-workdir/`, `quilt refresh`, `make sync-resume`.

## Where to read more

- `.shepherd/spec.md` § Project Structure — directory layout details.
- `.shepherd/spec.md` § Functional Requirements — FR-1 through FR-16.
- `.shepherd/standards.md` § Patch Authorship — how to write a good patch.
- `.shepherd/standards.md` § Overlay Authorship — overlay conventions.
- `.shepherd/standards.md` § Build-Tool Authorship — `tools/` conventions (incl. `sys.path` rule for `rebrand.py`).
- `.shepherd/progress.md` — what shipped per milestone, with commit SHAs.
