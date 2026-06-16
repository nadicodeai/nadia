# Cutting a Nadia release

The single, reproducible procedure for shipping a release to customers. If you
follow the **TL;DR** you do not need to make any release-engineering decisions —
they are baked in below.

## TL;DR

From a **clean** `main` checkout, with `gh` authenticated (`gh auth status`):

```bash
# Pin __version__ to upstream's current value (see "Versioning" — never bump it
# independently); CalVer date defaults to today. One command does everything.
python tools/nadia_release.py --version "$(sed -nE 's/.*__version__ = "([^"]+)".*/\1/p' upstream/hermes_cli/__init__.py)"
```

This builds `dist/nadia/`, runs the gates, tags `main` HEAD, pushes the tag, and
creates the GitHub Release. The tag push fires `.github/workflows/release.yml`,
which rebuilds and **force-pushes the renamed tree to `origin/release`** — the
branch customers actually install from. Then watch CI:

```bash
gh run watch "$(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

When that is green, the release is live. A reinstall or `nadia update` on a
customer machine picks it up.

## Why there is a procedure at all (branch model)

- **`main` = workshop.** Holds `upstream/`, `patches/`, `overlay/`, `tools/`,
  `packaging-strip.yaml`, the rename engine. **Not** a runnable install. Merging
  here does **not** ship anything.
- **`release` = storefront.** The renamed, built `dist/nadia/` tree, force-pushed
  by CI. This is what `install.sh` clones and what `nadia update` (`git pull`)
  tracks. `dist/nadia/` is gitignored on `main`; the only way it reaches a tracked
  ref is the release-branch force-push.
- **A release happens only when a CalVer tag is pushed.** Nothing auto-promotes
  `main` → `release`. Merging a fix to `main` and never cutting a tag means
  customers never get it — that is the #1 "I thought it shipped" trap.

## Versioning (the rule that is easy to get wrong)

Two independent version numbers, by design (spec **IU-FR-12**, standards.md §
"Release tags"):

| Surface | Scheme | When it changes |
|---|---|---|
| CalVer tag `vYYYY.M.D` (same-day re-cut `vYYYY.M.D.2`) | per release | every cut = today |
| internal `nadia_cli/__init__.py:__version__` (semver) | tracks upstream | **only** when an upstream sync lands a new upstream version |

**Do not let the driver patch-bump the semver.** `nadia_release.py` defaults to
`--bump patch`, which would diverge from upstream — wrong. Always pass
`--version <upstream's current __version__>` (the TL;DR command reads it for
you). Past releases held at `0.14.1` across three CalVer tags; the `0.15.1` value
only appeared because a sync moved upstream there.

## Preconditions

- **Clean worktree** — the driver refuses if `git status --porcelain` is
  non-empty. Stash or remove scratch files first; don't pollute the tagged commit.
- **`gh` authenticated** with `repo` scope (`gh auth status`).
- The change you're shipping is already **merged to `main`** and green
  (`make dist-test` is the *merge-time* gate for dist-affecting changes; the
  release itself runs build + leakage + assertions — see below).

## What the driver does (and its gate ordering)

`tools/nadia_release.py`, in order: `make build` → rewrite version in
`dist/nadia/` → `make leakage-static` → `run_assertions.py` → `git tag -a` →
**`git push` the tag** → **`gh release create`** → print summary.

- All gates run **before** any outward action; a gate failure aborts with
  nothing pushed.
- Push happens **before** `gh release create` (gh refuses to create a release
  for an unpushed tag). This mirrors upstream `scripts/release.py` (push @1972 →
  create @2011). It is race-safe: `release.yml` doesn't read the release object
  until after its own build+leakage (minutes later).

CI (`release.yml`) then: rebuild → leakage → re-apply the bump (read from the
Release title) → deterministic tarball → sha256 → **force-push `dist/nadia/` →
`origin/release`** → upload assets.

## Same-day re-cut

The CalVer tag for today already exists? Pass an explicit suffix:

```bash
python tools/nadia_release.py --version <upstream-ver> --release-date 2026.6.3.2
```

To instead replace a failed cut cleanly (nothing consumed it yet):

```bash
gh release delete vYYYY.M.D --cleanup-tag --yes   # remote release + tag
git tag -d vYYYY.M.D                              # local tag
# fix the cause, then re-cut vYYYY.M.D at the new HEAD
```

## Storefront does NOT carry `.github/workflows/`

`release_branch_push.py` strips `.github/workflows/` from the pushed tree on
purpose (`_strip_release_workflows`). Two reasons:

1. **The Actions `GITHUB_TOKEN` cannot push workflow files** (create, update, or
   delete). The `workflow` OAuth scope cannot be granted to it, and `workflows`
   is not a valid key in a `permissions:` block — adding it breaks the workflow
   file's schema validation. So when an upstream sync adds a workflow file, a
   release tree that carried it would be rejected at the force-push.
2. Customers don't need our (renamed-upstream) CI, and those workflows could
   spuriously trigger on the `release` branch.

`dist/nadia/` itself (native install, tarball asset, Docker image) is untouched —
only the release-branch tree excludes them.

**One-time caveat:** if the `release` branch ever regains workflow files (e.g. an
older release left them), the first push that removes them must come from a
**workflow-capable credential** — a maintainer SSH push, not CI:

```bash
make build && python tools/apply_release_bump.py --version <ver> --release-date <date>
python tools/release_branch_push.py --dist-root dist/nadia \
  --remote-url git@github.com:nadicodeai/argo.git --branch release \
  --source-sha "$(git rev-parse HEAD)"
```

After that, every CI release pushes a workflow-free tree and `GITHUB_TOKEN`
never sees a workflow-file change.

## Verify a release landed

```bash
git fetch origin release
git show origin/release:nadia_cli/__init__.py | grep -E '__version__|__release_date__'
# spot-check the strip survived:
git ls-tree -r --name-only origin/release -- gateway/platforms/ | grep -iE 'feishu|wecom|weixin|dingtalk|qqbot|yuanbao'  # expect: nothing
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Driver aborts: "working tree has uncommitted changes" | dirty worktree | stash/remove scratch files |
| `gh release create` fails: "tag exists locally but has not been pushed" | running an old driver that created before pushing | already fixed — driver now pushes first |
| `release.yml` fails fast, 0 jobs, "workflow file issue" | invalid workflow YAML/schema (e.g. an invalid `permissions:` key like `workflows`) | fix the workflow file; never add `workflows:` to `permissions:` |
| Force-push step: "refusing to allow ... create or update workflow ... without `workflows` permission" | release tree carried a `.github/workflows/` file | the storefront strip handles this; if legacy files remain, do the one-time SSH push above |
| Customers still see old behavior after a merge | no tag was cut; `release` never rebuilt | cut a release (TL;DR) |
