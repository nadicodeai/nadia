# Goal: Migrate Argo To Nadia

## Active Objective

Complete and verify the objective defined in `/home/vadim/Code/argo/docs/goals/nadia-migration-goal.md`.

## Outcome

Migrate this repository's fork brand from Argo to Nadia so every fork-owned and customer-facing surface that currently says `argo`, `Argo`, or `ARGO` becomes `nadia`, `Nadia`, or `NADIA`, while preserving the fork architecture:

- `upstream/` remains pristine and is never edited directly.
- Patches and overlay source remain authored against upstream `hermes` names.
- The build-time rename engine remains the mechanism that turns upstream `hermes` surfaces into the fork's customer-visible Nadia surfaces.
- The shipped agent is called `nadia`, not `argo`.

## Baseline

Today the fork target brand is Argo:

- Build output is rooted at `dist/argo/`.
- Customer command is `argo`.
- Python/package output includes names such as `argo_cli`, `argo_agent`, and `argo_sync`.
- Runtime config and state use `~/.argo`, `.argo/`, `ARGO_HOME`, and `ARGO_*`.
- Public surfaces point at `nadicodeai/argo`, `ghcr.io/nadicodeai/argo`, and `docs.nadicode.ai/argo`.
- Release tooling and tests use Argo names, including `tools/argo_release.py`, `argo-rename.yaml`, `scripts/argo-*`, smoke tests, docs, CI comments, Docker tags, release assets, and generated skin files.

There may be thousands of Argo tokens. Do not rely on a small manual list. Inventory text and filenames with `rg` before and after the migration.

## Required Architectural Understanding

This is not an in-source upstream rename.

The repository is a pristine-upstream fork:

1. `upstream/` is a pinned subtree of NousResearch `hermes-agent`.
2. Fork changes that modify upstream files live in `patches/` as quilt patches.
3. Additive fork files live in `overlay/`, using upstream `hermes` paths and symbols.
4. `tools/build.py` builds a temporary distribution tree from upstream, patches, and overlay.
5. The rename engine applies the fork brand at build time.
6. The built tree is what customers run and install.

Do not pre-rename patch or overlay source to `nadia_*` if it is supposed to target an upstream `hermes_*` surface. The authored side stays `hermes`; the built side becomes Nadia.

## Scope

Change all Argo fork-brand surfaces to Nadia, including at minimum:

- Rename config mappings, exceptions, comments, and generated defaults.
- Build output path decisions, such as whether `dist/argo/` becomes `dist/nadia/`.
- CLI command, package/module output, environment variables, home/config paths, metadata, banners, docs URLs, install URLs, update hints, GHCR image names, Docker labels/tags, and release asset names.
- Release tooling names and behavior, including the release driver and workflow parsing of release titles.
- Native install and update smoke harnesses.
- Tests and fixtures that currently assert Argo names.
- User-facing docs, README, AGENTS references, Shepherd loop docs that remain active, and goal/plan docs that future agents will read.
- Generated skin and preview surfaces currently carrying Argo names.
- File names that include `argo`, where they are fork-owned rather than upstream historical references.

Historical references may remain only when they are intentionally about old Argo history, attribution, prior releases, or migration context. Every retained Argo occurrence must be justified in a documented allowlist or in an inline comment near the verifier.

## Non-Goals

- Do not edit `upstream/`.
- Do not commit `dist/`, `.sync-workdir/`, quilt backup state, generated caches, or local scratch artifacts.
- Do not implement a legacy `argo` compatibility alias, `~/.argo` migration, or `ARGO_*` compatibility layer unless Vadim explicitly approves it.
- Do not publish to PyPI unless Vadim explicitly reverses the existing no-PyPI decision.
- Do not redesign install or update behavior. Preserve current behavior, renamed to Nadia.
- Do not rename the public GitHub repo, force-push `release`, publish GHCR images, change DNS/docs hosting, or cut a release without explicit approval.

## Approval Gates

Ask Vadim before any irreversible, public, shared, or costly action:

- Renaming the GitHub repository from `nadicodeai/argo` to `nadicodeai/nadia`.
- Creating or moving public GHCR images.
- Changing `docs.nadicode.ai/argo` to a Nadia URL or changing DNS.
- Force-pushing the `release` branch.
- Cutting or deleting release tags.
- Creating a GitHub Release.
- Adding backwards compatibility for old Argo commands, paths, or env vars.
- Publishing to PyPI.

Local branches, local commits, tests, and local documentation edits do not need separate approval.

## Primary Verifier

The migration is not complete until the updated equivalents of these commands pass from a clean feature branch:

```bash
make build
make leakage-static
make test
make dist-test
make install-smoke
make update-smoke
```

If target names change, update the Makefile and tests so the commands still represent the same gates for Nadia. Do not delete or weaken a gate to make this list pass.

## Required End-State Checks

The final verified state must prove:

- `nadia --version` exits 0 and prints `Nadia Agent v... (...)`.
- A fresh install writes `~/.nadia/.install_method` containing `git`.
- The update path runs as Nadia and does not print the fork warning.
- No unapproved `argo`, `Argo`, or `ARGO` remains in the built customer tree.
- No unapproved Argo filenames remain in fork-owned source.
- Existing protected Hermes external identifiers remain protected. Do not break Nous model IDs, OAuth client IDs, attribution strings, or other wire-protocol identifiers that must stay Hermes.
- The renamed upstream test suite still runs against the built tree.
- Release/storefront dry-run or approved live verification shows Nadia assets and Nadia paths, with no workshop files in the storefront tree.

## Supporting Verifiers

Add or update focused checks as needed:

- A config-aware Argo-leakage scanner, analogous to the current Hermes leakage scanner, with positive and negative fixtures.
- Tests proving rename mappings now produce Nadia outputs from Hermes inputs.
- Tests proving install URLs point at the correct Nadia release branch surface.
- Tests proving smoke harnesses assert `nadia`, `~/.nadia`, and `NADIA_*`.
- Tests proving release title parsing accepts `Nadia Agent v... (...)`.
- File-name inventory checks for old Argo paths.

Keep the existing Hermes leakage and wire-identifier checks. The goal is not to remove all Hermes strings blindly; Hermes remains upstream, attribution, model, and protocol identity where the current repo says it must.

## Iteration Loop

1. Create or find the GitHub issue for this migration and reference this goal file.
2. Work on a feature branch, never directly on `main`.
3. Record a baseline inventory:
   - `rg -n "argo|Argo|ARGO" --glob '!dist/**' --glob '!.sync-workdir/**'`
   - `rg --files --glob '!dist/**' --glob '!.sync-workdir/**' | rg '(^|/)(argo|Argo|ARGO)'`
4. Change one meaningful surface group at a time.
5. After each surface group, run the focused tests for that group plus `make build` and `make leakage-static`.
6. Commit small green slices.
7. Run the full primary verifier before requesting merge or public release action.
8. Preserve a short worklog in the GitHub issue or a sibling result file if the run spans multiple sessions.

## Anti-Cheating Rules

- Do not edit `upstream/`.
- Do not edit generated `dist/` files.
- Do not bypass quilt patch rules.
- Do not remove tests, xfail tests, or narrow scanners without explaining why and preserving equivalent coverage.
- Do not treat a clean Hermes leakage scan as proof that no Argo branding remains.
- Do not hide retained Argo strings under broad binary or directory skips.
- Do not create mocks for install/update proof when an existing smoke harness exercises the real artifact.
- Do not report "done" after source grep only. The built tree and install/update paths are the product.

## Blocker Standard

Mark the goal blocked only after the same external blocker repeats across the required goal turns and no meaningful local progress remains. Valid blockers include missing approval for a public rename, missing credentials for a public release action, or an external service outage that prevents the required approved verification.

Build failures, test failures, stale docs, or a large number of Argo occurrences are not blockers. They are the work.

## Completion Proof

Before marking complete, provide:

- Tracking issue URL.
- Branch name and final commit SHA or PR URL.
- Exact commands run and their exit status.
- Sample `nadia --version` output.
- Install-smoke proof showing `~/.nadia/.install_method = git`.
- Update-smoke proof showing no fork warning.
- Argo-leakage scan result and any allowlist of retained Argo references.
- Dist-test result.
- Release/storefront verification result, either dry-run or approved live result.
- List of public actions not taken because they require separate approval.

## Compact Objective For Goal Runners

Use this when activating a persistent goal:

```text
Complete and verify the objective defined in /home/vadim/Code/argo/docs/goals/nadia-migration-goal.md.
```
