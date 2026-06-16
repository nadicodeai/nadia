# Spec: Nadia default skin driven by the NadicodeAI Design System

> Status: reviewed 2026-06-06; decisions locked 2026-06-07 (DS via **private npm git dependency** — no publish; standards-first + documented in AGENTS.md/docs) · Owner: Vadim
> Downstream: feeds the `plan` skill, then implementation agents.

## Confirmed Intent

_Locked input from `interview-me` (2026-06-06). Do not edit here without re-running `interview-me`._

- **Outcome:** Ship an additive `nadia` skin (existing `default`/`ares`/`mono`/`slate`/`daylight`/`warm-lightmode` untouched) and make it the default in the published image. Its palette is **generated from the nadicodeai-design-system tokens**, mapped to the DS **ink/dark surface** (bg `#171717`, canvas text, green/cyan/state accents); it carries **fresh Nadia ASCII logo + hero derived from the DS logo-mark/wordmark** (caduceus retired) and a **neutralized minimal spinner** (no kawaii/war glyphs, plain verbs). In parallel, the **web dashboard** consumes the DS Tailwind-v4 theme (`@import "@nadicodeai/design-system/tailwind/theme.css"` in `upstream/web/src/index.css`), and **`ui-tui`** (Ink, no CSS) consumes the same DS **color tokens** as hex.
- **User:** Nadicode shipping `ghcr.io/nadicodeai/nadia`, and the North-Italy SMB end users who should see one coherent Nadia brand from first launch.
- **Why now:** `nadicodeai-design-system` just became the canonical brand source today; the shipped image still presents as Hermes (gold, kawaii, caduceus), so brand and product are out of sync.
- **Success:** Fresh image → `nadia` runs the `nadia` skin by default (DS ink colors, Nadia banner art, no caduceus, minimal spinner); `nadia dashboard` renders in the DS theme; a DS version bump re-flows into all surfaces on the next image build; **zero `upstream/` files edited directly**; all existing gates (build, leakage, pristine, packaging-contract, dist-test) stay green.
- **Constraint:** Live single source of truth = consume the **private** `@nadicodeai/design-system` → Docker build needs registry auth (GitHub Packages token); terminal/ui-tui colors are **generated** from DTCG tokens (no hand-forked hexes); the skin and all wiring ship via **overlay/patch + a build step**, never an upstream edit.
- **Out of scope:** Electron `apps/desktop` (never built in the image); modifying/removing existing skins; rename work the existing rename layer already handles; typography/layout beyond color on terminal surfaces (Ink/terminal can't take Geist/Tailwind).

## Scope & Phasing

_Added after the 2026-06-06 spec review. The Confirmed Intent's end-goal (all shipped surfaces present as Nadia via the DS) is unchanged; delivery is sequenced because the web surface is a larger migration than first assumed (see review finding below)._

- **Phase 1 (this spec):** the **terminal CLI skin** + **`ui-tui`** — both colored from the DS DTCG tokens, Nadia ASCII art replacing the caduceus, neutralized spinner, `nadia` made the default skin in the image. Self-contained and brand-faithful on its own.
- **Phase 2 (deferred — separate spec/plan):** the **web dashboard**. The dashboard is not bare Tailwind — it runs **`@nous-research/ui` 0.18.2 as its design system, imported by 38 files** (`grep -rln "@nous-research/ui" upstream/web/src` → 38), wired in `upstream/web/src/index.css` (its fonts + globals + JIT `@source`). Adopting the NadicodeAI DS there is a **component-library migration** (component-API gap, Geist-vs-Collapse/Mondwest font swap, utility-class reconciliation) and also removes a Nous-branded dependency from the shipped bundle. That is its own project; the Confirmed Intent's `nadia dashboard` success line moves to Phase 2.

> The "Constraint" bullet in Confirmed Intent says "registry auth (GitHub Packages token)" — superseded by the 2026-06-07 decision: the DS is consumed as a **private npm git dependency** (`github:nadicodeai/nadicodeai-design-system`; no registry, no `.npmrc`, no SHA-in-manifest; reproducible via the committed lockfile; npm uses existing org git auth). The locked Confirmed-Intent text is preserved as-written, but Assumption 4 + Open Q4 below govern implementation.

> **No publish prerequisite (revised 2026-06-07):** the DS stays private and is consumed as an npm **git dependency** (`github:nadicodeai/nadicodeai-design-system`), resolved via the maintainer's/CI's existing org git auth. Nothing needs publishing; `make gen-skin` runs outside Docker so the image never clones the DS. (One residual: if the regen-drift gate runs in CI, that job needs a cross-repo token/deploy-key for the private DS — local `make gen-skin` needs none.)

> **Standards-first (decided 2026-06-07):** the mechanisms this work establishes — how the DS is consumed (private npm git dep), how the token→skin generator runs, how the distribution default-skin switch is applied, and the patch/overlay/`content_edits` conventions used — MUST be defined as repo standards and documented "super clearly" in **AGENTS.md** and **docs/** as a written process, before/with the implementation that relies on them. See the dedicated section below.

## Standards & Documentation (required, decided 2026-06-07)

Do it the proper way; where the repo standard isn't clearly defined, define it first, then implement to it. These are first-class deliverables, not afterthoughts:

- **DS dependency standard:** consume `@nadicodeai/design-system` as a normal npm **git dependency** (`github:nadicodeai/nadicodeai-design-system`) resolved via existing org git auth, reproducibility via the committed `package-lock.json` (records the resolved commit). No `.npmrc`, no registry/publish, no auth token, no SHA-in-manifest, no vendoring. (A git URL is a normal npm `dependencies` entry — same discipline as `@nous-research/ui`, just sourced from the private repo instead of the public registry.)
- **Distribution default-skin-switch standard:** there must be ONE clearly-documented mechanism for "change a shipped default for the distribution" (the `display.skin: nadia` switch is the first use). If the existing `content_edits`/patch conventions don't already document this crisply, document them.
- **Token→skin generator standard:** one documented generator + `TOKEN_MAP`, how it runs in the build, where its output lives, and how a DS bump re-flows.
- **AGENTS.md:** a concise, unambiguous section an agent can act on — how the DS is consumed, how the generator runs, how a distribution default is changed, and the patch/overlay/`content_edits` rules for this work. Follow progressive-disclosure (link to docs/ for detail).
- **docs/:** a written process doc covering the same, for humans. Reference it from AGENTS.md.

A change is not "done" until these are documented and the docs match the implementation.

## Assumptions

→ Correct any of these now or implementation proceeds on them.

1. The `nadia` skin is registered as a **built-in** skin (so it is always available and selectable as the config default), introduced via a **quilt patch** to `upstream/hermes_cli/skin_engine.py`'s `_BUILTIN_SKINS` — not shipped as a drop-in `~/.nadia/skins/nadia.yaml` user file. Patching upstream via quilt is sanctioned; directly editing `upstream/` is not. _(Mechanism is an Open Question — see below; this is the working assumption.)_
2. The default-skin switch (`display.skin: nadia`) is applied **for the distribution only** (via the rename/overlay/config layer), not by changing upstream's config default. The fork is Docker-only, so "image default" == "product default". Verified safe: `cli.py:2884` hardcodes the Hermes banner only when `skin_name == "default"`; a non-`default` skin uses `agent_name` branding instead, so switching the default to `nadia` bypasses the hardcoded "⚕ NOUS HERMES" string.
3. "Generated from tokens" means a **build-time generator** that reads the DS DTCG export and emits **two** targets into `dist/nadia/` during the build: (a) the Python `nadia` skin color map, and (b) the `ui-tui` TypeScript theme override (`ThemeColors`). `ui-tui` themes itself independently of the Python skin engine via `upstream/ui-tui/src/theme.ts` (`DEFAULT_THEME`, currently Hermes gold `#FFD700`) and a `caduceus()` hero in `upstream/ui-tui/src/banner.ts` — both must be overridden/retired for Nadia. The generator reads the DTCG tokens from the **installed** DS package (`node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`). The generated values are what ship; a DS version bump (normal `npm` update) re-flows on the next build.
4. **DS consumption: private npm git dependency (decided 2026-06-07; revised from public-npm).** `@nadicodeai/design-system` is consumed as a **normal npm git dependency** — `"@nadicodeai/design-system": "github:nadicodeai/nadicodeai-design-system"` — and is **NOT published** to any registry (it stays private). npm clones the private repo using the maintainer's/CI's existing **git auth to the nadicodeai org** (no `.npmrc`, no registry token, no SHA in the manifest). Reproducibility comes from the committed `package-lock.json`, which records the resolved commit; `npm update` bumps it deliberately. The generator runs **outside** the hermetic Docker build (via `make gen-skin`) and reads tokens from the cloned package; the Docker image ships only the committed overlay and never clones the DS. **No publish prerequisite, no blocker.**
5. **DTCG structure (verified 2026-06-07 against upstream `master` `2dcbc1a` after `git pull`):** colors live at `nadicode.color.<name>.$value.hex` (the `nadicode` wrapper is present on current master). **The DS palette/schema is volatile** — an intermediate commit (`3b8bd32`) flattened it to top-level `color` and dropped `flag-red`; current master restores both. Therefore the generator MUST (a) **auto-detect** the container (`nadicode.color` else top-level `color`) and (b) **fail loud** if any mapped token is absent. We freeze a specific **published** DS version (T-PRE + lockfile) so the build target stops moving.
6. The Nadia ASCII `banner_logo` + `banner_hero` (Python) and the `ui-tui` banner art are **authored once** from `logo-mark.svg` / `logo-wordmark.svg` (rendered to Rich-markup ASCII / Ink lines), colored from DS tokens. The art is a static asset; only its colors track tokens.
7. The kawaii spinner faces/verbs and the caduceus appear only in `default`/`DEFAULT_THEME`; the `nadia` skin and the ui-tui theme override fully populate `branding`/`spinner`/`banner_*` so no Hermes value leaks through inheritance.
8. The DS is `0.1.0` / alpha and will churn — track it as a **git dependency + committed `package-lock.json`** (which records the resolved commit), bumped deliberately via `npm update`. The lockfile is the pin; no SHA in the manifest.

## Tech Stack

- **Terminal CLI skin engine** — Python 3.13. `upstream/hermes_cli/skin_engine.py`: `SkinConfig` dataclass + `_BUILTIN_SKINS` dict + YAML loader. Selected by config key `display.skin`. Consumed lazily across `upstream/agent/display.py` and `upstream/cli.py` via `get_active_skin()`.
- **TUI** — `upstream/ui-tui/`: **Ink** (`ink ^6.8.0`, React-to-terminal). Themed by `upstream/ui-tui/src/theme.ts` (`ThemeColors` interface, `DEFAULT_THEME` = Hermes gold; ANSI-downsamples on non-truecolor terminals so DS hex is approximated there) and `banner.ts` (`logo()` + `caduceus()`). **Independent of the Python skin engine** — a separate theming target. Built in the image (`npm run build`).
- **Design system** — `github.com/nadicodeai/nadicodeai-design-system`, npm name `@nadicodeai/design-system`, **consumed as a private npm git dependency (`github:nadicodeai/nadicodeai-design-system`; see Assumption 4)** — not published. The repo/tarball includes `dist/tokens/nadicode.dtcg.json` (DTCG 2025.10, nested), `dist/tailwind/nadicode.{theme.css,tailwind.json}`, `src/assets/{logo-mark,logo-wordmark,favicon}.svg`, Geist/Geist Mono. Exports incl. `./tokens/dtcg`, `./tailwind/theme.css`, `./assets/logo-mark`, `./assets/logo-wordmark`. Palette is light-canvas with a first-class **ink/dark surface** treatment.
- **Build/dist pipeline** — `tools/build.py` assembles `dist/nadia/` from: upstream → **quilt patches** (`patches/00NN-*.patch`) → **overlay copy** (`overlay/*` → `dist/nadia/`, fails on collision) → rename (`nadia-rename.yaml` → `overlay/hermes_cli/_rename_defaults.py`). Quilt workdir over `upstream/` with `QUILT_PATCHES`.
- **Image** — `Dockerfile` (slim + `image-full`), publishes to `ghcr.io/nadicodeai/nadia`.
- **Phase 2 only (deferred):** `upstream/web/` — Vite + React 19 + Tailwind v4 (`@tailwindcss/vite`, entry `src/index.css`), currently on **`@nous-research/ui` 0.18.2 across 38 files**. Not in scope for this spec.

## DS-token → terminal-skin color mapping (target)

> **Verified 2026-06-07 against upstream `master` `2dcbc1a`** (after `git pull`): the DS palette is volatile, but current master matches the table below — `flag-red #cd212a` present, `state-review #f5a623`, logo mark green `#007a5e` + **red `#cd212a`**. Don't hardcode hexes downstream: the generator's `TOKEN_MAP` + fail-loud are authoritative, and the committed lockfile pins the DS commit to stop the target moving.

The `nadia` skin maps the DS **ink surface** onto the skin's ~30 color keys; the same source tokens drive the `ui-tui` `ThemeColors`. Source values (from `nadicode.color.<name>.$value.hex`):
`primary/ink #171717`, `on-primary/canvas #ffffff`, `selection-fg #f2f2f2`, `body #4d4d4d`, `mute #888888`, `hairline #ebebeb`, `link #007a5e`, `link-deep #005d49`, `success #008c45`, `error #b80022`, `error-deep #820018`, `warning #f5a623`, `cyan #50e3c2`, `cyan-deep #29bc9b`, `flag-red #cd212a`, `selection-bg #171717`, `state-running #007a5e`, `state-review #f5a623`, `state-blocked #b80022`.

Intended mapping (the generator codifies this for both the Python skin keys and the ui-tui `ThemeColors`; values illustrative, final table fixed in the plan):

```
# dark/ink surface: dark background, canvas-tinted text, green/cyan accents
banner_border      → cyan-deep   #29bc9b
banner_title       → cyan        #50e3c2
banner_accent      → link        #007a5e
banner_dim         → mute        #888888
banner_text        → selection-fg #f2f2f2
ui_accent          → link        #007a5e
ui_label           → cyan-deep   #29bc9b
ui_ok / status_bar_good     → success #008c45
ui_error / status_bar_critical → flag-red #cd212a   (error #b80022 for non-critical)
ui_warn / status_bar_warn   → warning #f5a623
prompt             → selection-fg #f2f2f2
input_rule         → link-deep   #005d49
response_border    → cyan        #50e3c2
status_bar_bg / voice_status_bg / completion_menu_bg → ink #171717
status_bar_text    → mute        #888888
status_bar_strong  → cyan        #50e3c2
selection_bg / completion_menu_current_bg → a dark accent (e.g. link-deep on ink)
```

The ui-tui `ThemeColors` key set differs from the Python skin keys (e.g. `primary`, `accent`, `muted`, `sessionLabel`, `sessionBorder`) — the generator maps the same source tokens onto that second key set.

## Commands

```
Build dist:        make build            # upstream + patches + overlay + rename → dist/nadia/
Run tests:         make test
Lint:              make lint
Typecheck:         make typecheck
Leakage scan:      make leakage-static   # no residual hermes/caduceus/kawaii strings in dist
Pristine check:    make check-upstream-pristine
Packaging contract:make check-packaging-contract
Dist suite:        make dist-test        # REQUIRED before merging a dist-affecting change to main
Build image:       make image            # slim;  make image-full for full
Install hooks:     make install-hooks    # once per clone — pre-commit build/leakage gate
Patch workflow:    quilt workdir over upstream/ with QUILT_PATCHES (see memory/quilt-patch-editing-workflow)
DS dep:            npm git dependency github:nadicodeai/nadicodeai-design-system (private; org git auth; package-lock pins the commit; bump via npm update)
```

## Project Structure

```
upstream/                         → pristine Hermes fork — NEVER edit directly
  hermes_cli/skin_engine.py       → _BUILTIN_SKINS, SkinConfig (nadia skin added via PATCH)
  ui-tui/src/theme.ts             → DEFAULT_THEME override target (DS hex) — via PATCH/overlay
  ui-tui/src/banner.ts            → caduceus() hero → Nadia art (via PATCH)
patches/00NN-*.patch              → quilt patches (next: 0016+, e.g. nadia-skin, ui-tui-ds-theme)
patches/asserts/00NN-*.txt        → per-patch assertion contracts (banner/branding invariants)
overlay/                          → files copied verbatim into dist/nadia/ (no upstream collision)
  hermes_cli/                     → generated nadia-skin color data (build output target)
tools/                            → build.py + new DTCG→{skin,ui-tui theme} generator
  build.py                        → assembly pipeline (generator hooked in here or Docker stage)
nadia-rename.yaml                  → rename map (+ display.skin: nadia default override candidate)
packaging-overrides.yaml          → apt/extras deltas (DS git fetch / submodule wiring if needed)
Dockerfile                        → add pinned DS git fetch + git auth; run generator before build
specs/nadia-default-skin-design-system.md  → this spec (Phase 1)
plans/                            → implementation plan (produced by `plan` skill)
tests/ , upstream/tests/          → skin + ui-tui theme + dist + leakage tests
```

## Code Style

Match surrounding code. A built-in skin is **pure data** — a dict entry in `_BUILTIN_SKINS` following the documented schema; no logic. Example shape (final colors come from the generator, not hand-typed hexes):

```python
# upstream/hermes_cli/skin_engine.py — added to _BUILTIN_SKINS via quilt patch
"nadia": {
    "name": "nadia",
    "description": "NadicodeAI ink — dark surface, green/cyan accents (design-system driven)",
    "colors": { "banner_title": "#50e3c2", "banner_accent": "#007a5e",
                "banner_text": "#f2f2f2", ... },  # full ~30-key map per the mapping table
    "spinner": {                       # neutralized: minimal glyphs, plain verbs
        "thinking_verbs": ["thinking", "working", "reading", "editing"],
        "waiting_faces": ["( · )", "( ·· )", "( ··· )"],
        "thinking_faces": ["(/)", "(-)", "(\\)", "(|)"],
    },
    "branding": { "agent_name": "Nadia", "response_label": " Nadia ", ... },  # fully populated
    "tool_prefix": "┊",
    "banner_logo": "...",              # Rich-markup ASCII from DS logo-wordmark.svg
    "banner_hero": "...",              # Rich-markup ASCII from DS logo-mark.svg
},
```

ui-tui theme override (TypeScript — same source tokens, ui-tui's own key set):

```ts
// upstream/ui-tui/src/theme.ts — DEFAULT_THEME values overridden via patch/generator
const DEFAULT_THEME_COLORS: ThemeColors = {
  primary: '#50e3c2', accent: '#007a5e', muted: '#888888', /* …from DS tokens */
}
// banner.ts caduceus() hero replaced with Nadia mark art
```

Conventions: lowercase-hyphen skin name; lowercase hex; every `branding`/`spinner`/`banner_*` key explicit (no `default` inheritance → no Hermes leakage); generator output deterministic; DS pinned to an immutable ref.

## Testing Strategy

- **Framework:** pytest (Python: `upstream/tests/hermes_cli/test_skin_engine.py`, `upstream/tests/cli/test_cli_skin_integration.py`); vitest (ui-tui: `upstream/ui-tui/src/__tests__/theme.test.ts`).
- **Unit (skin engine):** `nadia` skin loads/validates/resolves all color keys; `set_active_skin("nadia")` succeeds; other skins' inheritance still works.
- **Default selection:** with the dist config, `get_active_skin().name == "nadia"`; branding resolves to "Nadia" with **no** "NOUS HERMES"/caduceus/kawaii fallback (covers the `skin_name == "default"` branch at `cli.py:2884`).
- **ui-tui theme:** `DEFAULT_THEME`/`ThemeColors` carry DS hex (golden test); caduceus replaced; ANSI-downsample path still produces readable colors on non-truecolor terminals.
- **Generator:** deterministic DTCG→{skin, ui-tui theme} output; given the committed DS token fixture, output matches expected maps (golden); a token change changes output (prove the test catches a wrong mapping).
- **Leakage / pristine:** `make leakage-static` finds no residual Hermes-only strings in the `nadia` skin / ui-tui theme / dist; `make check-upstream-pristine` confirms `upstream/` untouched; banner OSC-8 invariant + rename gates (`check_wire_identifiers`, `check_no_china_in_docs`) green.
- **Dist / image:** `make dist-test` passes; `make image` builds; the pinned DS git fetch resolves with auth and the generator runs.
- **Pre-commit gate:** `.githooks/pre-commit` runs `make build` + leakage on patch/overlay/tools/rename commits (`make install-hooks`).
- **No live-fire:** verify gates/destructive steps with automated tests in a throwaway repo, never by committing a known-broken artifact.

## Boundaries

- **Always:**
  - Run `make build`, `make leakage-static`, `make check-upstream-pristine`, and `make dist-test` before claiming done; full gate set before merging to `main`.
  - Add/modify upstream behavior only through quilt patches (`patches/`) or `overlay/` — never by editing `upstream/` directly.
  - Keep every existing skin and the rename layer intact; the `nadia` skin is purely additive.
  - Source colors from DS tokens via the generator; consume the DS as a **private npm git dependency** (lockfile-pinned to the resolved commit), bumped deliberately via `npm update`.
  - **Follow existing repo standards** (normal npm deps, no `.npmrc`/registry-auth, quilt/overlay/`content_edits` conventions); where a needed standard isn't clearly defined, **define and document it in AGENTS.md + docs/ first**, then implement to it. Keep docs in sync with the implementation.
- **Ask first:**
  - The skin-registration mechanism (built-in via patch vs. baked user-skin file) and where `display.skin: nadia` is set.
  - Cross-repo private-DS auth **in CI** (only if the regen-drift gate runs in CI it needs a token/deploy-key for the private DS repo; local `make gen-skin` uses the maintainer's existing org git auth and needs none).
  - Any change to `packaging-overrides.yaml` / `packaging-strip.yaml` or CI workflow.
  - The final Nadia ASCII art (logo/hero) before it ships.
  - **Starting Phase 2** (web `@nous-research/ui` → NadicodeAI DS migration) — separate spec/plan.
- **Never:**
  - Edit `upstream/` directly; remove or weaken failing gates/tests to go green; commit DS git credentials.
  - Hand-fork DS hex values into the repo as the source of truth; vendor the DS or introduce a private registry/`.npmrc`/auth/SHA-pin for it; change the `default` (Hermes) skin's appearance.

## Success Criteria

**Phase 1 (this spec):**
1. `docker run ghcr.io/nadicodeai/nadia` (fresh) → CLI banner shows **Nadia** art (no caduceus), **DS ink/dark** colors, **neutralized** spinner; `get_active_skin().name == "nadia"` by default.
2. `nadia --tui` (`ui-tui`) renders with DS hex colors (Ink) and Nadia banner art, consistent with the terminal skin.
3. Bumping the DS git dependency (`npm update @nadicodeai/design-system` re-resolves the commit, then `make gen-skin`) re-flows new token values into the skin **and** the ui-tui theme — no manual hex edits.
4. `make build`, `make test`, `make lint`, `make typecheck`, `make leakage-static`, `make check-upstream-pristine`, `make check-packaging-contract`, `make dist-test`, `make image` all pass; `git diff upstream/` empty (all changes in patches/overlay/tools/config).
5. No "NOUS HERMES", caduceus, or kawaii/war glyph leaks through the `nadia` skin or ui-tui theme on any Phase-1 surface.
6. **AGENTS.md + docs/** document, as a clear written process: how the DS is consumed (private npm git dep), how the token→skin generator runs, how a distribution default is changed (the default-skin switch mechanism), and the patch/overlay/`content_edits` conventions — and the docs match the implementation.

**Phase 2 (deferred — tracked, not delivered here):**
7. `nadia dashboard` renders in the NadicodeAI DS theme with `@nous-research/ui` removed from the shipped web bundle.

## Open Questions

1. **Skin registration mechanism:** built-in via quilt patch to `_BUILTIN_SKINS` (Assumption 1) vs. an overlay-shipped skin file vs. an overlay registration hook. Which best satisfies "always-available default" without an upstream edit?
2. **Default-skin switch location:** `nadia-rename.yaml`, a config-default patch, or `overlay`? (The `cli.py:2884` branch is already confirmed safe for a non-`default` name.)
3. **Generator placement & artifact:** does the DTCG→{skin, ui-tui theme} generator run in `make build` (committed output) or a Docker build stage (build-only)? The Python package and the ui-tui bundle must contain the values at runtime, so a build-only generator must emit into the image before the Python/npm builds.
4. **DS consumption — RESOLVED 2026-06-07 (revised):** consume `@nadicodeai/design-system` as a **private npm git dependency** (`github:nadicodeai/nadicodeai-design-system`) — no registry, no publish, no `.npmrc`, no SHA-in-manifest; npm uses existing org git auth; reproducibility via the committed `package-lock.json` (records the resolved commit). The generator runs outside Docker (`make gen-skin`) so the image never clones the DS. No publish blocker.
5. **ASCII art production:** tool/path to convert `logo-mark.svg`/`logo-wordmark.svg` → Rich-markup ASCII (Python) and Ink lines (ui-tui) at each banner's size budget; who signs off on the art.
6. **ui-tui generator target:** confirm the exact `ThemeColors` key set and how `DEFAULT_THEME` is overridden (patch the literal vs. read a generated JSON) without breaking the ANSI-downsample logic. _(Central module confirmed: `ui-tui/src/theme.ts`.)_
7. **DTCG dark-surface coverage:** confirm the nested export carries every value the ink-surface mapping needs, or define fallbacks for any missing dark-surface token.
8. **Native (non-Docker) installs:** the fork is Docker-only, but if any native install path exists, confirm whether it should also default to `nadia` or remain `default`.
9. **Phase 2 framing:** scope the web `@nous-research/ui` (0.18.2, 38 files) → NadicodeAI DS migration as its own spec — component-API mapping, font swap, utility reconciliation, Nous-dependency removal.
```
