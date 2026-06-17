# Goal: Complete The Nadia Agent Product Migration

## Active Objective

Complete and verify the objective defined in `/home/vadim/Code/argo/docs/goals/nadia-migration-goal.md`.

## Outcome

Make this fork ship and present itself as **Nadia Agent** everywhere an end user, customer, installer, updater, desktop user, profile-builder user, contributor, or release consumer sees it.

The target state is:

- Product name: `Nadia Agent`.
- CLI command: `nadia`.
- Customer config and state: `~/.nadia`, `.nadia/`, `NADIA_*`.
- Public source/release repository coordinate, if GitHub remains the public coordinate: `nadicodeai/nadia`.
- Container/image coordinate, if container publishing remains supported: Nadia-named, for example `nadia` under the chosen registry.
- macOS and Windows app identity: `Nadia Agent`.
- Profile builder/onboarding identity: Nadia-branded.
- Install, update, download, docs, release, and support surfaces: Nadia-branded.
- `Argo` / `argo` / `ARGO`: removed from active product and distribution surfaces.
- `Hermes`: preserved only for upstream provenance, real external project names, real model identifiers, real parser/protocol names, and real Nous/Hermes wire identifiers.
- `Nous`: preserved when it is the real company, provider, Portal, model source, or backend protocol surface.

The user-facing success condition is simple: a customer can install the Nadia Agent CLI, download the Nadia Agent macOS or Windows app, use the Nadia profile builder/setup flow, update Nadia, and read Nadia docs without encountering Argo branding or fake renamed external Hermes names.

## Baseline

The repository has already moved many runtime surfaces from Argo to Nadia, and commit `6f716db` fixed the first wave of bad mechanical Hermes renames. Current known facts:

- The branch is `feature/nadia-migration`.
- `dist/nadia` is the built customer tree.
- The current repo path is still `/home/vadim/Code/argo`; local path names are not themselves customer proof.
- The public GitHub repository coordinate is `nadicodeai/nadia`; `nadicodeai/argo` is no longer the canonical repository.
- Current scans must continue to check for stale `nadicodeai/argo`, `ghcr.io/nadicodeai/argo`, `docs.nadicode.ai/argo`, old README policy, release tooling comments, and install/download surfaces that must be Nadia-branded. `hermes-agent.nousresearch.com` may remain only when it is upstream provenance, upstream docs attribution, or a protected external Hermes reference.
- There are unrelated untracked PNG files in the worktree: `create-controls.png`, `create-started.png`, `create.png`, `home.png`. Do not stage or delete them unless separately instructed.

## Required Architectural Understanding

This is not an in-place upstream rename.

The fork architecture remains:

1. `upstream/` is a pristine pinned subtree of NousResearch `hermes-agent`.
2. Fork changes that modify upstream files live in `patches/` as quilt patches.
3. Additive fork files live in `overlay/`, using upstream `hermes` paths and symbols where they target upstream files.
4. `tools/build.py` builds a distribution tree from upstream, patches, overlay, packaging rules, content edits, and the rename engine.
5. The built tree is what customers run and install.

Do not edit `upstream/` directly. Do not hand edit `dist/`. If an upstream-owned file must change, use the patch/content-edit mechanism already used by this repo. If a fork-owned mechanism or config must change, edit the fork-owned source and regenerate any generated defaults through the existing generator.

## Scope

Bring all fork-owned and customer-facing surfaces to Nadia Agent, including at minimum:

- Repository coordinates and docs that currently reference `nadicodeai/argo`, where they are public product or support coordinates.
- Install scripts, install URLs, install docs, install smoke tests, and platform-specific install commands.
- Update logic, update docs, update smoke tests, release branch assumptions, and release manifest behavior.
- CLI command names, package metadata, script entry points, env vars, config paths, banners, logs, diagnostic messages, and help output.
- Public release metadata, release title parsing, release asset names, release workflow comments, release verification docs, and release driver references.
- Container image names, Docker labels, compose examples, docs, and GHCR or alternative-registry references.
- macOS desktop app name, product filename, app metadata, bundle identifiers, update metadata, download links, installer text, and tests.
- Windows desktop app name, installer metadata, app identity, update metadata, download links, setup text, and tests.
- Bootstrap/profile-builder/onboarding surfaces, including setup endpoints, profile-builder UI copy, generated config paths, docs, and tests.
- Generated website docs and root README docs so the product subject is Nadia Agent, with only a concise Hermes provenance section.
- Leak scanners and allowlists for old Argo branding and for over-renamed external Hermes identifiers.

Historical Argo references may remain only when they are explicitly about old migration history, prior release archaeology, or a temporary compatibility bridge approved by Vadim. Every retained Argo occurrence must be justified in a documented allowlist or a nearby comment.

## Non-Goals

- Do not edit `upstream/` directly.
- Do not commit `dist/`, `.sync-workdir/`, quilt backup state, generated caches, or local scratch artifacts.
- Do not create fake Nadia names for real external Hermes-named projects, models, parsers, packages, or protocols.
- Do not remove the existing Hermes/Nous wire-identifier protections.
- Do not publish to PyPI unless Vadim explicitly approves it.
- Do not implement a legacy `argo` compatibility alias, `~/.argo` migration, or `ARGO_*` compatibility layer unless Vadim explicitly approves it.
- Do not choose or invent a public artifact domain. Implement the code and docs in terms of the settled canonical coordinates or a clearly named configurable artifact base until Vadim chooses the public host.
- Do not perform DNS changes, release publication, image publication, privacy changes, or paid infrastructure setup without explicit approval. The public GitHub repository rename to `nadicodeai/nadia` was explicitly approved and performed during this migration.

## Approval Gates

Ask Vadim before any irreversible, public, shared, or costly action:

- Renaming the GitHub repository in GitHub settings. This was completed for `nadicodeai/argo` -> `nadicodeai/nadia`; any further repository rename still requires approval.
- Making the source repository private.
- Creating a new public release repository.
- Choosing or changing DNS or a public artifact host.
- Publishing or moving GHCR or other registry images.
- Force-pushing the release branch.
- Cutting, deleting, or moving release tags.
- Creating a GitHub Release.
- Publishing macOS or Windows artifacts publicly.
- Changing signed/notarized desktop identities in a way that affects existing update continuity.
- Publishing to PyPI.
- Adding old Argo compatibility aliases or migrations.

Local branches, local commits, local docs, local tests, generated local builds, and local dry-run release artifacts do not need separate approval.

## Primary Verifier

The goal is not complete until the Nadia Agent customer contract is proven by local commands and artifact inspection from a clean feature branch.

Required gates:

```bash
make build
make leakage-static
make test
make dist-test
make install-smoke
make update-smoke
```

If command names change, keep equivalent targets and document the equivalence. Do not delete or weaken gates to make this list pass.

## Required End-State Checks

The final verified state must prove:

- `nadia --version` exits 0 and prints `Nadia Agent v... (...)`.
- Fresh CLI install writes only Nadia paths, especially `~/.nadia` and the Nadia install root.
- `nadia update` updates from a Nadia-branded release/artifact coordinate or a configurable artifact base, not an Argo-branded coordinate.
- macOS desktop build metadata, app name, installer/download metadata, and tests identify the app as `Nadia Agent`.
- Windows desktop build metadata, app name, installer/download metadata, and tests identify the app as `Nadia Agent`.
- The profile builder/setup/onboarding flow is Nadia-branded and writes Nadia config.
- No unapproved `argo`, `Argo`, or `ARGO` remains in the built customer tree.
- No unapproved Argo filenames remain in fork-owned source.
- No customer docs instruct users to install, download, or update Argo.
- No customer docs present Hermes Agent as the product subject. Hermes may appear only in provenance, upstream links, real model IDs, real external project names, parser/protocol names, or protected wire identifiers.
- Existing protected Hermes external identifiers remain exact: Nous model IDs, OAuth client IDs, Portal tags, `--tool-call-parser hermes`, `HermesClaw`, `Hermes Mod`, `hermes-lcm`, `rtk-hermes`, and other documented external names.
- The renamed upstream test suite still runs against the built tree.
- Release/storefront dry-run or approved live verification shows Nadia assets, Nadia paths, and no workshop-only files in the customer artifact tree.

## Supporting Verifiers

Add or update focused checks as needed:

- Config-aware Argo leakage scanner with positive and negative fixtures.
- File-name inventory check for old Argo paths.
- Tests proving install URLs and update URLs use Nadia coordinates or a configurable artifact base.
- Tests proving smoke harnesses assert `nadia`, `~/.nadia`, and `NADIA_*`.
- Tests proving release title parsing accepts `Nadia Agent v... (...)`.
- Tests proving desktop bundle/app metadata says Nadia Agent.
- Tests proving profile builder/setup surfaces say Nadia and write Nadia config.
- Tests proving external Hermes identifiers remain preserved exactly.

Keep the existing Hermes leakage and wire-identifier checks. A clean Hermes leakage scan is not proof that Argo is gone.

## Iteration Loop

1. Work on a feature branch, never directly on `main`.
2. Record and refresh baseline inventories:
   - `rg -n "argo|Argo|ARGO" --glob '!dist/**' --glob '!.sync-workdir/**'`
   - `rg --files --glob '!dist/**' --glob '!.sync-workdir/**' | rg '(^|/)(argo|Argo|ARGO)'`
   - `rg -n "nadicodeai/argo|ghcr.io/nadicodeai/argo|docs.nadicode.ai/argo|hermes-agent.nousresearch.com|setup.hermes-agent.nousresearch.com" --glob '!dist/**' --glob '!.sync-workdir/**'`
3. Change one meaningful surface group at a time.
4. After each surface group, run focused tests plus `make build` and `make leakage-static`.
5. Commit small green slices.
6. Run the full primary verifier before requesting merge or any public action.
7. Preserve a short worklog in this goal file or a sibling result file if the run spans multiple sessions.

## Anti-Cheating Rules

- Do not edit `upstream/`.
- Do not edit generated `dist/` files.
- Do not bypass quilt patch rules.
- Do not remove tests, xfail tests, or narrow scanners without explaining why and preserving equivalent coverage.
- Do not hide retained Argo strings under broad binary or directory skips.
- Do not pretend a public hosting/domain decision has been made when it has not.
- Do not replace a real external Hermes identifier with an invented Nadia identifier.
- Do not report done after source grep only. The built tree, install/update paths, desktop artifacts, and profile-builder path are the product.

## Blocker Standard

Mark blocked only after the same external blocker repeats across the required goal turns and no meaningful local progress remains. Valid blockers include missing approval for a public repo rename, source privacy change, DNS/artifact-host decision, release publication, image publication, desktop signing/notarization identity change, or unavailable credentials for an approved public action.

Build failures, test failures, stale docs, many old-brand occurrences, and unclear implementation details are not blockers. They are the work.

## Completion Proof

Before marking complete, provide:

- Branch name and final commit SHA or PR URL.
- Exact commands run and their exit status.
- Sample `nadia --version` output.
- Install-smoke proof showing Nadia paths and no Argo branding.
- Update-smoke proof showing Nadia update coordinates and no Argo branding.
- Desktop artifact or metadata proof for macOS and Windows Nadia Agent identity.
- Profile builder/setup proof showing Nadia branding and Nadia config output.
- Old-brand scan result and allowlist of any retained Argo references.
- Hermes external-identifier preservation scan result.
- Full `make dist-test` result.
- Release/storefront verification result, either dry-run or approved live result.
- List of public actions not taken because they require separate approval.

## Compact Objective For Goal Runners

Use this when activating a persistent goal:

```text
Complete and verify the objective defined in /home/vadim/Code/argo/docs/goals/nadia-migration-goal.md.
```
