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

`tools/parity_runner.py` (M6) drives the customer-parity gate (FR-16,
AC-7). The spec names `ghcr.io/nadicodeai/argo-agent:0.14.0` as the
legacy baseline, but **that tag was never pushed to GHCR**. The
runner defaults to `ghcr.io/nadicodeai/argo-agent:latest`, which as
pulled today reports `Hermes Agent v0.8.0` (an OLDER version than the
spec-named 0.14.0). The diff vs the new image is therefore a feature
superset (additive), not a regression.

To keep the gate useful in this in-between state, the runner accepts
`--allow-expected` (default for `make parity` and for the CI parity
job) which reclassifies surfaces named in `tests/parity-expected.yml`
as `XFAIL` — they are reported but do NOT drive a non-zero exit.
Any surface FAILing that is NOT on the whitelist still blocks the
gate. To see the unmasked diff during development:

```bash
make parity-strict   # or: python tools/parity_runner.py
```

Current per-surface status against the locally-built images:

| Surface         | Status              | Reason                                              |
| --------------- | ------------------- | --------------------------------------------------- |
| `help`          | XFAIL (was FAIL)    | v0.14.0 subcommand superset over v0.8.0             |
| `version`       | XFAIL (was FAIL)    | v0.14.0 banner vs v0.8.0 banner                     |
| `doctor-static` | SKIPPED             | legacy v0.8.0 lacks the `--static` flag (M3 target) |
| `mcp-list`      | PASS                | Dockerfile fix landed (M6 follow-up)                |
| `hook-fire`     | SKIPPED             | legacy v0.8.0 has no `hooks` subcommand             |
| `auth-start`    | PASS                | proxied via `auth list`; both empty + identical     |
| `session-init`  | XFAIL (was FAIL)    | persistence layout drift v0.8.0 → v0.14.0           |

Lifecycle: when a real v0.14.0 legacy image is published (M7 first
real sync), DROP entries from `tests/parity-expected.yml` that no
longer FAIL and re-tighten the gate. Anything still on the list at
that point is a true semantic divergence and should be filed as a
tracked issue, not silently accepted.

## Slim image (M5/M6 history)

M5 produced a 371MB slim runtime image; M6's parity gate exposed two
crashes (`mcp list`, `sessions list`) that traced to a missing
`tools/` Python package in the runtime stage. Patches 0008 + the M6
Dockerfile regressions fix landed those import paths, so the slim
image now handles all FR-16 surfaces 1-7. The image still does NOT
match legacy's 4.71GB surface (no node/npm/playwright/ffmpeg/
s6-overlay yet) — that broader expansion is M7+ territory, contingent
on real customer surface needs. NFR-3 (image size within 5% of legacy)
is intentionally NOT a gate at this scope; track via OQ-21 if it ever
becomes a customer-blocking concern.

## Where to read more

- `.shepherd/spec.md` § Project Structure — directory layout details.
- `.shepherd/standards.md` § Patch Authorship — how to write a good patch.
- `.shepherd/standards.md` § Overlay Authorship — overlay conventions.
- `.shepherd/spec.md` § Functional Requirements — FR-1 through FR-16.
