# Argo Design-System Skin Process

This document is the maintenance process for the Argo terminal skin and the
Ink `ui-tui` theme generated from `@nadicodeai/design-system`.

## Standards

- MUST consume the design system as a private npm git dependency:
  `github:nadicodeai/nadicodeai-design-system`.
- MUST keep the dependency generator-only under `tools/skin-gen/`.
- MUST use `tools/skin-gen/package-lock.json` as the reproducibility pin.
  `package.json` stays on the package name, and the lockfile records the
  resolved git commit.
- MUST NOT add `.npmrc`, registry tokens, vendored design-system files, or a
  SHA-in-manifest pin for this dependency.
- MUST commit generated overlay output. `make build` consumes committed overlay
  files and does not run npm or require access to the private design-system
  repository.

## Files

- `tools/skin-gen/package.json` declares the private git dependency.
- `tools/skin-gen/package-lock.json` pins the resolved design-system commit.
- `tools/gen_argo_skin.py` maps DTCG tokens to both generated outputs.
- `overlay/hermes_cli/_argo_skin.py` is generated Python skin data.
- `overlay/ui-tui/src/argoTheme.generated.ts` is generated Ink theme data.
- `tests/test_gen_argo_skin.py` proves deterministic generation, full key
  coverage, token reflow, and loud failure when a mapped token disappears.

Generated overlay paths use hermes names because the repo's build-time rename
engine rewrites them into `dist/argo/`.

## Skin Reference Research

The official Hermes skin documentation is the source of truth for this work.
It defines a skin as CLI presentation only: `colors`, `spinner`, `branding`,
`tool_prefix`, `tool_emojis`, `banner_logo`, and `banner_hero`.

References checked:

- Official Hermes docs, "Skins & Themes": skins control banner colors, spinner
  faces and verbs, response labels, branding text, and the tool activity
  prefix. They are separate from personality and do not change agent behavior.
- Official built-ins listed in the docs:
  - `default`: warm gold, kawaii faces, caduceus banner.
  - `ares`: crimson/bronze with war-god spinner language and sword/shield art.
  - `mono`: grayscale, minimal, no custom spinner.
  - `slate`: cool blue, professional, no custom spinner.
  - `poseidon`, `sisyphus`, `charizard`: thematic art and spinner language.
- Community reference repo `joeynyc/hermes-skins`:
  - `netrunner`: strongest dark/cyan terminal structure, geometric spinner
    glyphs, and high-contrast wordmark.
  - `mother`: strong restraint and clear CRT terminal identity, but its amber
    palette is not close to NadicodeAI.
  - `lain` and `neonwave`: visually distinctive, but pink/purple palettes are
    not close to NadicodeAI.

Chosen base: `netrunner`.

Inherited from `netrunner`:

- Dark terminal surface with cyan/teal hierarchy.
- Geometric spinner faces: `(◎)`, `(◈)`, `(⬡)`, `(⌁)`, `(⊗)`.
- Geometric spinner wings: `⟨◎ ... ◎⟩`, etc.
- Tool prefix and activity language biased toward terse terminal operation.
- The large braille `banner_hero` composition. It is recolored from
  NadicodeAI tokens and stripped of third-party fictional captions.

Changed for Argo:

- Palette remaps to `@nadicodeai/design-system` tokens instead of hard-coded
  `netrunner` hex values.
- Branding strings become Argo strings as defined by the Hermes docs:
  `agent_name`, `welcome`, `goodbye`, `response_label`, `prompt_symbol`, and
  `help_header`.
- Third-party fictional labels from `netrunner` are removed. No "Jinteki",
  "Jack In", cyberpunk role text, or explanatory labels are shown.
- `banner_logo` is intentionally empty so Argo does not ship a fake terminal
  wordmark. Narrow `packaging-strip.yaml` content edits prevent non-default
  empty logo art from falling back to Hermes' wordmark in the shipped Argo tree.

Rejected approaches:

- Official `default`: keeps the caduceus/kawaii identity, wrong for Argo.
- Official `ares`, `poseidon`, `sisyphus`, `charizard`: too thematic.
- Official `mono`/`slate`: clean but too close to a recolor, with no distinctive
  Argo default identity.
- Community `mother`: beautiful, but amber/CRT identity fights the brand colors.
- Community `lain`/`neonwave`: visually strong, but pink/purple palettes fight
  the brand colors.

## Regenerate

Run:

```bash
make gen-skin
```

The target runs `npm --prefix tools/skin-gen ci --no-audit`, then
`python tools/gen_argo_skin.py`. It rewrites the generated overlay files from
the lockfile-pinned package.

After regeneration, verify at least:

```bash
pytest tests/test_gen_argo_skin.py -q
make gen-skin
git diff --exit-code overlay/hermes_cli/_argo_skin.py overlay/ui-tui/src/argoTheme.generated.ts
```

The final integration work must also run the repo gates documented in
`AGENTS.md`, including `make build`, `make leakage-static`,
`make check-upstream-pristine`, and `make dist-test` before merge.

## Bump The Design System

Run:

```bash
npm --prefix tools/skin-gen update @nadicodeai/design-system
make gen-skin
```

Then inspect:

```bash
git diff -- tools/skin-gen/package-lock.json overlay/
```

The generator intentionally fails when a mapped token is missing or malformed.
Fix the token map only after verifying the current design-system token export.
Do not add fallback hex values to hide a missing source token.

## Distribution Defaults

MUST change shipped distribution defaults through a documented
`content_edits` rule in the packaging/build config when the target file already
comes from upstream. The rule must include a `why:` and a narrow `find` anchor
so `tools/build.py` fails loudly if upstream changes the target text.

MUST NOT edit `dist/`, directly edit `upstream/`, or rely on post-build manual
rewrites. If the default switch needs upstream structure, add that structure via
a quilt patch and keep generated data in overlay.

## Patch And Overlay Split

- Patches carry structure that modifies upstream files.
- Overlay carries additive generated data and fork-owned modules.
- `content_edits` carries narrow distribution-default substitutions.
- The token map in `tools/gen_argo_skin.py` is the single source for generated
  skin colors; generated hex values are not hand-maintained.
