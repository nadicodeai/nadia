# AGENTS.md

Instructions for AI agents (and humans) working on argo. Keep this short; deep references live in `.shepherd/`.

## What this repo is

`argo` is a rebranded fork of NousResearch's `hermes-agent`. Three rules describe the architecture:

1. **`upstream/` is pristine.** A `git subtree --squash` of `hermes-agent`'s `main`, pinned at the SHA recorded in `upstream/.commit`. Never edited directly.
2. **Fork changes live in `patches/` and `overlay/`.** `patches/` is a quilt-managed patch series. `overlay/` is additive files using **hermes-named** paths (e.g. `overlay/hermes_cli/argo_update.py`).
3. **The hermes→argo rebrand runs at build time.** The rename engine in `overlay/hermes_sync/` walks the post-patch tree and rewrites `hermes` → `argo` (per `argo-rename.yaml`). The renamed tree lands in `dist/argo/` and gets packaged into `ghcr.io/nadicodeai/argo:latest`. Tracked source is never renamed.

`tools/` holds the build-time Python (build.py, rebrand.py, sync.py, verify_no_leakage.py, run_assertions.py, check_upstream_pristine.py). It never ships in the image. `dist/` and `.sync-workdir/` are gitignored.

## Customer install path

Customers install argo directly on a Linux host (no Docker) with a single curl one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/nadicodeai/argo/release/scripts/install.sh | bash
```

Two optional flags are honoured: `--skip-setup` skips the interactive Telegram-pairing wizard at the end (useful for CI/headless bootstrap), and `--skip-browser` skips the Node/browser-tool provisioning step (useful for headless servers without `xz-utils`).

What the installer puts on disk: the venv at `~/.local/share/argo/`, config + state at `~/.argo/`, and a `~/.local/bin/argo` symlink (or `/usr/local/bin/argo` when run as root). After install, `argo --version` prints `Argo Agent v0.14.1 (2026.5.28)`; the customer then runs `argo setup` for the Telegram + provider wizard and `argo gateway install && argo gateway start` to bring the bot online.

Repo topology behind the URL: `main` is the workshop (this tree — upstream + patches + overlay + rename engine); `release` is the storefront (the renamed `dist/argo/` tree, force-pushed by CI). Both `install.sh` and `argo update` (`git pull`) target `origin/release`. Developers can override with `curl ... | bash -s -- --branch main` to install from the workshop instead.

Releases are cut by `tools/argo_release.py` from a clean workshop checkout (CalVer tags `v<YYYY>.<M>.<D>`, same-day suffix `.2`/`.3`); the tag push fires `.github/workflows/release.yml`, which rebuilds `dist/argo/`, force-pushes it to `release`, and uploads the tarball + standalone install scripts + SHA256 sums as GitHub Release assets. Argo does NOT publish to PyPI (IU-FR-13); the URL above is the only supported customer path and is stable forever (IU-FR-4). **Full step-by-step + the version-pinning rule (semver tracks upstream, never patch-bumped) + gotchas: [docs/RELEASE.md](docs/RELEASE.md).** Two load-bearing facts: pass `--version <upstream __version__>` (the default `--bump patch` wrongly diverges), and the `release` branch carries **no** `.github/workflows/` (the Actions `GITHUB_TOKEN` cannot push workflow files), so `release_branch_push.py` strips them.

Spec, plan, and standards for this work live in `.shepherd/install-update/`.

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

Sub-loops (same `{spec,plan,progress,standards}.md` shape, scoped to a sibling outcome):

- **`.shepherd/install-update/`** — IU-AC-1..15: customer install + `argo update` CLI surfaces (closed).
- **`.shepherd/update-cycle-smoke/`** — UCS-AC-1..8: run upstream's 26k renamed tests on `dist/argo/` in CI (closed; issue #12).

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
make dist-test                     # run dist/argo's renamed suite — the REAL gate for dist changes (mirrors CI dist-argo-tests)
make check-upstream-pristine       # FR-15 gate: upstream/ matches the last sync commit
make patch-new NAME=<slug>         # start a new patch
make patch-refresh                 # quilt refresh the current patch
make patch-list                    # cat patches/series
```

`make build` and `make leakage-static` MUST both exit 0 before any commit that touches `patches/`, `overlay/`, `tools/`, or `argo-rename.yaml`. This is **enforced**, not honour-system: `.githooks/pre-commit` runs the gate on exactly those paths and blocks the commit on failure. Enable it once per checkout with `make install-hooks` (sets `core.hooksPath`, which git does not clone). MUST NOT bypass with `git commit --no-verify`.

**Landing a change on `main` REQUIRES the full dist suite green — not just build + leakage.** `ci.yml` runs on `pull_request` and push to `main` ONLY: a plain branch push runs **no CI at all**. And `make build` / `make leakage-static` / `make test` do **not** run `dist/argo/tests/` — `make test` runs the fork's *own* `tests/`. The dist suite (`make dist-test` locally; the `dist-argo-tests` matrix in CI) is the **only** gate that exercises what actually ships — it catches, e.g., a `packaging-strip.yaml` prune that breaks an upstream test which imports or enumerates a pruned module. Because `dist-argo-tests` is currently *non-blocking*, you MUST actively confirm it: **before merging any dist-affecting change to `main`, either open a PR and read the `dist-argo-tests` result, or run `make dist-test`.** Merging on the strength of local build + leakage alone shipped a red `main` once (the China strip) — do not repeat it.

## Upstream sync (the maintainer's main loop)

`make sync` is the ONLY sanctioned way to advance upstream. The tool owns the commit; you own only the conflict resolution inside `.sync-workdir/`. Hand-driving git or quilt around it is how a broken patch shipped once (2026-05-31) — don't.

A patch conflict on sync is NORMAL and healthy: one of the patches edits a line upstream also changed. It fails *safely and recoverably* — that is the architecture working, not breaking. The rename engine runs at build time and is never involved in a sync conflict.

A typical weekly sync:

1. `make sync` — pulls upstream, advances `upstream/.commit`, populates `.sync-workdir/`, runs `quilt push -a` there, then runs `make build` for verification. If clean, commits as `sync: upstream <short-sha> (<N> patches refreshed)`.
2. On `quilt push -a` failure it names the **failing patch** (the one that stopped, not the last applied) and prints the recovery recipe, leaving `.sync-workdir/` half-applied. **Do not run `make build` at the repo root in this state** — it is meaningless mid-sync.
3. **Resolve a rejected hunk with EXACTLY this recipe — nothing more:**
   1. `cd .sync-workdir`
   2. `quilt push -f` — force-apply the failing patch; the rejected hunk lands in a `.rej`. (Editing the file *before* this does nothing — the patch isn't applied yet, so `quilt refresh` would capture nothing.)
   3. Edit the conflicting file to apply what the `.rej` wanted; delete the `.rej`.
   4. `quilt refresh` — regenerate the patch **from the resolved file**.
   5. `cd .. && make sync-resume`.
4. `make sync-resume` — `quilt refresh`, detects the refreshed patches (it diffs `patches/` against HEAD — quilt rewrites `patches/NNNN.patch` in place via `QUILT_PATCHES`, there is no copy-back), replays the series, runs the `make build` gate, and **commits**, staging all of `patches/` so every refreshed/new patch lands. The commit is the tool's job, not yours.
5. If a sync attempt is abandoned, `make sync-reset` wipes `.sync-workdir/`.

A conflict can also surface one stage **earlier — in `git subtree pull` itself** (upstream rewrote a file the old pin carried; e.g. a renamed test). `make sync` then stops with a `[subtree-pull]` error and leaves `upstream/` half-merged (a `UU` path). Resolve it by taking **upstream's** version (`git checkout --theirs <path>`; we never legitimately edit `upstream/`), `git add` it, `git commit` to finish the merge (this preserves the `git-subtree-split:` trailer the tool re-reads), then re-run `make sync`. Committing *that merge* is the tool's own printed instruction — it is NOT the forbidden hand-commit below, which is about the final `sync:` commit that `sync-resume` still owns and gates on `make build`.

**MUST NOT, during a sync:**
- `quilt refresh` while the conflicting file is pristine/unresolved — it silently **drops the hunk** from the patch (the exact bug that shipped a broken `deploy-site.yml` gate).
- copy pristine files over the workdir, or run pop/push loops beyond the recipe above.
- `git commit` / `git commit --amend` a sync by hand — `sync-resume` runs `make build` *before* committing; hand-committing skips that gate. The pre-commit hook is the backstop, but follow the recipe rather than leaning on it.
- If you've thrashed the workdir: `make sync-reset` and start clean. Never paper over it.

`.sync-workdir/` is gitignored and persistent across sync attempts; it is NOT `dist/argo/`, which is regenerated on every build.

### Sync bot token setup

The weekly `sync.yml` workflow opens its PR with `secrets.SYNC_BOT_TOKEN` (a fine-grained PAT), not the default `GITHUB_TOKEN`. This is REQUIRED so the PR fires downstream `pull_request` workflows (i.e. `ci.yml`) — GitHub intentionally suppresses those events for PRs opened by `GITHUB_TOKEN` (issue #6). Provision once via GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens; scope the token to the `nadicodeai/argo` repository with `Pull requests: write` + `Contents: write`, then save it under repo settings → Secrets and variables → Actions as `SYNC_BOT_TOKEN`. The workflow's "Verify sync bot token" step fails fast with a pointer to this section if the secret is missing.

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
- **Merge sync PRs preserving the `sync:` subject** — a merge commit, or `gh pr merge --squash --subject "sync: …"`. A *plain* squash rewrites the subject to `Squashed 'upstream/' changes …`, which FR-15 doesn't recognise as a sync anchor, so it reddens `main` against the just-synced `upstream/`. Recover by amending HEAD back to `sync: …` (the gate's failure message says exactly this).
- **Never commit `dist/` or `.sync-workdir/`.**
- **Patches and overlay files use `hermes` names.** The engine renames at build.
- **Patch format is `diff -up --git`** (handles binary, modes, renames). Enforced by `.quiltrc`.
- **Load-bearing patches need `patches/asserts/<name>.txt`** with grep patterns (FR-14). Catches `quilt refresh` silently dropping fork lines after conflict resolution. List the patch's basename in `patches/asserts/manifest.txt`.
- **Reproducible builds: `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)` before `make build`.** Required for AC-8 (`dist/argo/` byte-identity across machines). `make image` already sets it via `--build-arg`.
- **CI prelude lives in `.github/actions/argo-setup/`.** Composite action that installs uv + Python + apt + pip deps for every workflow job; edit it (not the workflow preludes) when bumping `setup-uv`, the Python pin, or the default apt package list.

## Image variants

Issue #2 split the image into TWO variants so customers pick by deployment shape, not by NFR-3 compromise:

| Tag pointers (customer-facing)         | Variant       | Target        | Size    | When to use                                                                              |
| -------------------------------------- | ------------- | ------------- | ------- | ---------------------------------------------------------------------------------------- |
| `:latest`, `:v<X.Y.Z>`, `:<sha-short>` | full          | `runtime-full`| ~4.5 GB | Default. TUI dashboard, voice, browser-tool MCP, s6-supervised gateway — full customer surface. |
| `:slim`, `:latest-slim`, `:v<X.Y.Z>-slim`, `:<sha-short>-slim` | slim | `runtime-slim`| ~371 MB | CLI-only deployments (CI runners, batch agents, server-side automation). |

A bare `docker pull ghcr.io/nadicodeai/argo` resolves to `:latest` = full variant. CLI-only callers MUST explicitly opt into `:slim`.

**Local builds.**
- `make image` → builds `runtime-slim` and tags `:dev` (preserved name for backward compat with `scripts/publish.sh`).
- `make image-full` → builds `runtime-full` and tags `:dev-full`.

**Determinism.** AC-8 byte-determinism is a gate only for the slim variant (where the `dist/argo/` tree-hash is the artifact). The full variant fetches chromium + s6-overlay tarballs + npm packages at build time; its reproducibility is best-effort by design (spec § Build Reproducibility).

## Common tasks

- **Add a fork change.** Decide patch (modifies an upstream file) vs overlay (purely new file). Patches need assertions when load-bearing.
- **Investigate a leakage scan failure.** `make build && python tools/verify_no_leakage.py dist/argo/ --verbose` prints the offending paths. Either fix the source so it doesn't introduce `hermes`, or add an exception to `argo-rename.yaml` with a `why:` comment.
- **Bump upstream.** `make sync`. If conflicts: resolve in `.sync-workdir/`, `quilt refresh`, `make sync-resume`.

## Where to read more

- `.shepherd/spec.md` § Project Structure — directory layout details.
- `.shepherd/spec.md` § Functional Requirements — FR-1 through FR-15.
- `.shepherd/standards.md` § Patch Authorship — how to write a good patch.
- `.shepherd/standards.md` § Overlay Authorship — overlay conventions.
- `.shepherd/standards.md` § Build-Tool Authorship — `tools/` conventions (incl. `sys.path` rule for `rebrand.py`).
- `.shepherd/progress.md` — what shipped per milestone, with commit SHAs.
