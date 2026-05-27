# AGENTS.md

Instructions for AI agents (and humans) working on argo. Keep this file short; deep references live in `.shepherd/`.

## What this repo is

`argo` is a fork of NousResearch's `hermes-agent`. Architecturally:

- `upstream/` — pristine hermes-agent subtree. Do NOT edit directly.
- `patches/` — quilt-managed patch series. The fork's IP.
- `overlay/` — files this fork adds (using hermes-named paths; renamed at build).
- `tools/` — build-time Python tooling. Never ships in the image.
- `dist/` — gitignored build output.

The hermes→argo rebrand runs at **build time** via the rename engine in `overlay/hermes_sync/`. Source-of-truth code in `upstream/` and `overlay/` uses **hermes** names. The renamed tree lands in `dist/argo/` and gets packaged into the Docker image.

## Reading order

Start here, then deepen:

1. **`.shepherd/spec.md`** — what we're building, contracts, acceptance criteria.
2. **`.shepherd/plan.md`** — ordered tasks M1.x → M8.x.
3. **`.shepherd/progress.md`** — current milestone state.
4. **`.shepherd/standards.md`** — coding/repo/process rules.

## Common tasks

```bash
make help                    # discover targets
make build                   # produce dist/argo/
make sync                    # pull upstream and re-apply patches
make sync-resume             # continue after manual conflict resolution
make patch-new NAME=<slug>   # start a new patch
make leakage-static          # verify no "hermes" leaks in dist/argo/
make parity                  # diff vs legacy image (catches regressions)
```

## Quilt cheatsheet

```bash
quilt new <name>.patch       # start a new patch (appended to series)
quilt add <file>             # mark file as touched by current patch
# ... edit ...
quilt refresh                # regenerate the patch from current state
quilt push -a                # apply the whole series
quilt pop -a                 # remove the whole series
quilt series                 # list patches
quilt top                    # show currently-top patch
```

## Hard rules

- **Never edit `upstream/`.** Use a patch.
- **Never commit `dist/` or `.sync-workdir/`.**
- **Patches and overlay files use `hermes` names.** The engine renames at build.
- **Patch format is `diff -up --git`** (handles binary, modes, renames).
- **Load-bearing patches need `patches/asserts/<name>.txt`** with grep patterns.
- **Reproducible builds need `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)`** before `make build`.
- **Don't touch `~/Code/argo-agent`.** That's the legacy in-tree-rename repo, frozen.

## Parity baseline

`tools/parity_runner.py` (M6.2a) drives the customer-parity gate
(FR-16, AC-7). The spec names `ghcr.io/nadicodeai/argo-agent:0.14.0`
as the legacy baseline, but **that tag was never pushed to GHCR**.
The runner defaults to `ghcr.io/nadicodeai/argo-agent:latest` instead.
The legacy repo's `pyproject.toml` does report version 0.14.0, so
`:latest` is intended to be functionally equivalent — but in practice
the `:latest` image as pulled at the time M6.2a landed reports
`Hermes Agent v0.8.0`, which is OLDER than v0.14.0. As a result the
strict `make parity` diff is currently non-empty (the new image ships
a feature superset; the diff is a version gap, not a regression).
If a future legacy release publishes a real `:0.14.0` tag, update the
spec's FR-16 reference and the runner's `DEFAULT_LEGACY_IMAGE`, then
re-pin the AC-7 gate.

## Where to read more

- `.shepherd/spec.md` § Project Structure — directory layout details.
- `.shepherd/standards.md` § Patch Authorship — how to write a good patch.
- `.shepherd/standards.md` § Overlay Authorship — overlay conventions.
- `.shepherd/spec.md` § Functional Requirements — FR-1 through FR-16.
