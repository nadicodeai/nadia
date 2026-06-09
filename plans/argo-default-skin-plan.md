# Phase 1 Implementation Plan (REVISED 2026-06-07) — Argo default skin from the NadicodeAI Design System (private git-dependency model)

> Spec: `/home/vadim/Code/argo/specs/argo-default-skin-design-system.md` (decisions locked 2026-06-07). Source of truth.
> Supersedes the 2026-06-06 baseline of this file. The baseline's verified architecture is carried forward; the locked 2026-06-07 changes are applied: (a) DS = **private npm git dependency** (`github:nadicodeai/nadicodeai-design-system`; NO publish, NO registry, NO vendoring, NO SHA-in-manifest — drop the `tools/ds-tokens/`/`DS_PIN`/`refresh_ds_tokens.py` machinery; **PROVEN 2026-06-07** — `npm install github:…` resolves in ~11s via org git auth, lockfile pins commit `2dcbc1a`, no `.npmrc`); (b) **standards-first + documentation** is a first-class uphill foundation + Success Criterion #6; (c) determinism via committed lockfile (records the git commit) + committed generated overlay (`git diff --exit-code`).
> Scope: terminal CLI skin + `ui-tui` (Ink), both colored from the DS DTCG tokens; Argo ASCII art replacing the caduceus; neutralized minimal spinner; `argo` made the default skin (image AND native). **Web dashboard is Phase 2 — out of scope.**
> **Every path/line/value below was re-read from the tree on 2026-06-07.** Where the spec, baseline, or a draft was factually wrong, the correction is flagged inline and the verifying command is given.

---

## Overview

Phase 1 ships an additive built-in `argo` terminal skin (existing `default`/`ares`/`mono`/`slate`/`daylight`/`warm-lightmode`/`poseidon`/`sisyphus`/`charizard` untouched), generated from the **git-installed** NadicodeAI DS DTCG tokens, made the **distribution default**, with fresh Argo ASCII art (caduceus retired) and a neutralized spinner. The same palette re-flows onto the Ink `ui-tui`. Every change lands through quilt patches (`patches/0016+`), the `overlay/` copy mechanism, `tools/` generators, and the build-time `content_edits` layer — `upstream/` stays byte-pristine (`make check-upstream-pristine`).

### Three decisive verified facts that shape the whole design

1. **`make build` runs NO npm, and node_modules does not exist at make-build time on ANY host/CI/Docker path.** `make build` = `python tools/build.py` (`Makefile:73-74`); `grep -niE 'npm|node_modules' tools/build.py` → empty. The Docker **builder** stage is `FROM python:${PYTHON_VERSION}` (`Dockerfile:89`) and runs `RUN make build` at `Dockerfile:140` — no node there; npm only appears far later in `runtime-full` (`Dockerfile:394-405`). Therefore the token→skin generator (which reads the DS from `node_modules`) **cannot run inside `make build`**. It is a **separate `make gen-skin` step** whose deterministic output is **committed to `overlay/`**; `make build` consumes the committed overlay verbatim. (This corrects the baseline's "run the generator inside `make build`" wording — it would break every build.)

2. **The DS is a generator-only dependency — `ui-tui` imports nothing from it.** `grep -rn '@nadicodeai\|design-system' upstream/ui-tui/src` → empty. `ui-tui` ships generated hex literals, not the DS package. So the DS does NOT belong in the production image or in the pristine-gated `upstream/package-lock.json` (22,229 lines — verified `wc -l`). It is consumed in an isolated **generator-only tooling package** (`tools/skin-gen/`), a normal npm **git** `dependencies` entry (`github:nadicodeai/nadicodeai-design-system`), pinned by its own committed `tools/skin-gen/package-lock.json` (which records the resolved git commit) — honoring the standard (a normal `dependencies` entry, lockfile-pinned, no `.npmrc`/auth) without polluting the image or the workspace lockfile. (`@nous-research/ui` lives in `upstream/web/package.json:13`; a git URL is just as valid an npm dependency spec.)

3. **The DS stays PRIVATE (no publish) and is consumed as an npm git dependency; the palette/schema is VOLATILE.** The DS repo is `private:true`/`0.1.0`/unpublished — and it does NOT need publishing: `npm install github:nadicodeai/nadicodeai-design-system` resolves via the maintainer's/CI's org git auth (PROVEN 2026-06-07, ~11s, no `.npmrc`; lockfile pins commit `2dcbc1a`). No T-PRE blocker. The DTCG shape + palette oscillate across DS commits (intermediate `3b8bd32` flattened the schema and dropped `flag-red`; `master 2dcbc1a` restores both) — so the lockfile pins the commit and the generator is container-auto-detecting + fail-loud (see Finding F5).

### What changed vs the 2026-06-06 baseline (locked decisions applied)

| Area | Baseline (2026-06-06) | This revision (2026-06-07) |
|---|---|---|
| DS source | Vendor `dist/tokens/nadicode.dtcg.json` + SVGs into `tools/ds-tokens/` at a SHA; `DS_PIN`; `tools/refresh_ds_tokens.py` | **Public-npm normal dependency** in `tools/skin-gen/package.json`; generator reads `node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`; committed `tools/skin-gen/package-lock.json` |
| Generator placement | "Run in `make build`" | **Separate `make gen-skin` step**; output committed to `overlay/`; `make build` consumes it; CI drift gate (`make gen-skin && git diff --exit-code overlay/`) |
| Determinism | SHA file (`DS_PIN`) | Committed `package-lock.json` + committed generated overlay (`git diff --exit-code`) |
| Standards/docs | (not a deliverable) | **First-class uphill foundation** (T-DOCS) + **Success Criterion #6** |
| Prerequisite | (none) | **None blocking** — DS consumed as a private git dep (no publish); proven to install via org git auth |

### Load-bearing findings (all RE-verified 2026-06-07; corrections flagged)

**F1 — ui-tui themes via the gateway `fromSkin` AND a standalone `DEFAULT_THEME`; both must change.** `upstream/tui_gateway/server.py` `resolve_skin()` serializes the active Python skin to ui-tui, feeding `fromSkin()` (`upstream/ui-tui/src/theme.ts`). BUT `fromSkin`'s brand block hardcodes `icon: d.brand.icon` — it can NEVER override the `⚕` from `BRAND` (`theme.ts:239-247`, `icon: '⚕'` at :241). And `DEFAULT_THEME` (`theme.ts`, `DARK_THEME.color.primary = '#FFD700'`) is the pre-connection paint. So patch `BRAND` + `DARK_THEME`/`LIGHT_THEME` directly. **The icon-hardcode is in `fromSkin` (not the `BRAND` literal); the `BRAND` literal `icon: '⚕'` is at `theme.ts:241`.**

**F1a (CORRECTION — residue surface is LARGER than the baseline found).** The ui-tui residues `fromSkin`/the gateway cannot reach, all re-verified by exact line:
  - `upstream/ui-tui/src/components/appLayout.tsx:328` — `<Text color={ui.theme.color.muted}>⚕ {ui.status}</Text>` (baseline said `src/app/appLayout.tsx` — WRONG path; real dir is `src/components/`).
  - `upstream/ui-tui/src/components/appChrome.tsx:30` — `const EMOJI_FRAMES = ['⚕ ', '🌀', '🤔', '✨', '🍵', '🔮']`; `:54` — `?? '⚕ '` (baseline said `src/app/appChrome.tsx` — WRONG). `:81` derives `EMOJI_FRAME_WIDTH` from `EMOJI_FRAMES` via `stringWidth` — replacement frames must keep a sane width.
  - `upstream/ui-tui/src/app/uiStore.ts:28` — `status: 'summoning hermes…'` (this one IS caught by `make leakage-static` because it contains `hermes`).
  - **`upstream/ui-tui/src/components/branding.tsx:163` — `const heroLines = caduceus(t.color, t.bannerHero || undefined)`** — the hero FALLS BACK to the caduceus unless `bannerHero` is non-empty. The baseline OMITTED this. Setting `DARK_THEME`/`LIGHT_THEME` `bannerHero` to the Argo art defeats it.
  - **`upstream/ui-tui/src/content/fortunes.ts:26` — `return \`${rare ? '🌟' : '🔮'} ${bag[n % bag.length]}\`\`** — emits kawaii glyphs. The baseline OMITTED this.

**F2 — the rich CLI banner retires the caduceus purely via skin data (no `banner.py`/`cli.py` patch).** `upstream/cli.py:2884` hardcodes `"⚕ NOUS HERMES"` ONLY when `skin_name == "default"`; the `else` branch (`cli.py:2888-2890`) uses `agent_name`. A non-`default` skin (`argo`) bypasses it. `banner.py` picks `_bskin.banner_hero`/`banner_logo` when populated. A fully-populated `argo` skin + a non-`default` default switch needs no banner patch. (Re-verified `cli.py:2884-2890`.)

**F3 — SC-5 is NOT enforced by any existing gate.** `tools/verify_no_leakage.py` scans ONLY case-insensitive `hermes` (`:102,:129`) — blind to `caduceus`/`⚕`/`⚔`/kawaii/`#FFD700`. `tools/run_assertions.py` `check_assertion` (`:138-156`) is **positive-only** — it returns True iff a literal/regex is FOUND; there is **no absent/negative mode**, so the `patches/asserts/*.txt` contracts CANNOT do negative greps. SC-5 ("no caduceus/kawaii/⚕ leak") therefore needs a dedicated denylist scanner `tools/check_no_legacy_glyphs.py`. (Re-verified.)

**F4 — build order (drives generator placement).** `tools/build.py` `build()`: `_apply_patches(562) → _strip_quilt_state → _regenerate_rename_defaults(564) → _copy_overlay(565) → _copy_fde_scripts → _strip_excluded_paths → _apply_content_edits(568) → _run_rebrand(569) → _run_assertions`. Overlay copied (565) BEFORE content_edits (568) BEFORE rebrand (569). The rename is one-directional `hermes→argo`, so literal `argo` + lowercase hex + `@nadicodeai/design-system` are rename-invariant. `content_edits` fail loud on a stale anchor (`build.py:387`). (Re-verified `tools/build.py:562-569`.)

**F5 — DTCG structure + palette (RE-verified 2026-06-07 against upstream `master` `2dcbc1a` after `git pull`; the DS is VOLATILE).** A `git pull` showed the earlier read hit a **transient divergent commit** (`3b8bd32`, since superseded). On current master:
  - Top keys include **`nadicode`** — the wrapper IS present. Traverse **`d["nadicode"]["color"][<name>]["$value"]["hex"]`**. BUT `3b8bd32` had flattened it to top-level `color`, so the generator MUST **auto-detect** the container (`nadicode.color` else top-level `color`) and **fail loud** on a missing mapped token. Verified: `nadicode.color.cyan.$value.hex == "#50e3c2"`.
  - **`flag-red #cd212a` is PRESENT** (current master). The spec mapping `ui_error`/`status_bar_critical` → `flag-red #cd212a` is valid; `error #b80022` for non-critical, `error-deep #820018` for `status_bar_bad`.
  - **`state-review` is `#f5a623`** (current master), matching the spec table.
  - **The logo SVGs use `#007a5e` (green) + `#cd212a` (red)** (current master) — the approved **green-red node** direction is ON-token; no color reconciliation needed.
  - Verified-present (`$value.hex`): `primary #171717`, `cyan #50e3c2`, `cyan-deep #29bc9b`, `link #007a5e`, `link-deep #005d49`, `success #008c45`, `error #b80022`, `error-deep #820018`, `warning #f5a623`, `flag-red #cd212a`, `state-running #007a5e`, `state-review #f5a623`, `state-blocked #b80022`, `mute/muted #888888`, `selection-fg #f2f2f2`, etc. Because the palette oscillates across commits, **the committed `package-lock.json` pins the git commit** to freeze the target; the generator asserts each mapped token and FAILS LOUD on a drop — no silent fallback.

**F6 — skin color-key surface.** The `default` skin dict defines **16** color keys (`grep`-verified). The full superset consumed via `get_color("<key>")` across `upstream/` is **30** keys (verified union: `banner_×5, ui_×5, status_bar_×8 (bg/text/dim/good/warn/bad/critical/strong), prompt, input_rule, response_border, session_label, session_border, selection_bg, voice_status_bg, completion_menu_×4`). `_build_skin_config` (`skin_engine.py:692-704`) merges a skin's `colors` ON TOP of `default`, so any key the `argo` skin omits inherits the Hermes value. The generator MUST populate the full 30-key superset (+ `banner_logo`/`banner_hero`) so nothing inherits.

**F7 — packaging-contract is unaffected by an npm dependency add.** `tools/check_packaging_contract.py` checks FROM digests, apt superset, and Python extras only (verified docstring lines 20-29) — NOT npm deps and NOT the Dockerfile body. Adding `@nadicodeai/design-system` to `tools/skin-gen/package.json` does not trip it.

---

## Architecture Decisions

### AD1 — Skin registration: quilt patch 0016 into `_BUILTIN_SKINS` importing a generated overlay module (Open Q1)
`_BUILTIN_SKINS` opens at `skin_engine.py:164` and the dict closes `}` at **line 645** (verified `awk 'NR>=164 && /^}/'` → `645`; this corrects a draft that said 647). `load_skin` checks user `~/.<app>/skins/<name>.yaml` FIRST, so a built-in is the only always-available, non-shadowable config default. `patches/0016-argo-skin.patch` inserts before the close at line 645:
```python
    "argo": _ARGO_SKIN_DATA,
```
preceded by a guarded import in the dict region:
```python
try:
    from hermes_cli._argo_skin import ARGO_SKIN_DATA as _ARGO_SKIN_DATA
except Exception:  # pragma: no cover - keeps upstream/ importable standalone
    _ARGO_SKIN_DATA = {"name": "argo", "description": "NadicodeAI ink"}
```
The full 30-key color map + neutralized spinner + branding + `banner_logo`/`banner_hero` live in the **generated** `overlay/hermes_cli/_argo_skin.py` (renamed to `argo_cli/_argo_skin.py` by rebrand, mirroring `overlay/hermes_cli/_rename_defaults.py`). Patch carries STRUCTURE only (no hexes) → a DS bump regenerates only the overlay; the patch never refreshes on a sync. The patch also extends `upstream/tests/hermes_cli/test_skin_engine.py` so the new builtin passes the existing completeness test — that test edit ships inside patch 0016 (it lives under `upstream/`).
_Rejected:_ baked user-skin YAML (shadow-able, not always-available); import-time monkeypatch (invisible to `list_skins`); hexes in the patch (churns every DS bump).

### AD2 — Default-skin switch: build-time `content_edits` in `packaging-strip.yaml` (Open Q2) — the documented distribution-default standard
Upstream default `"skin": "default"` is at `cli.py:458` (verified). Flip to `"argo"` via a `content_edits` rule (`_apply_content_edits`, `build.py:356`; runs before rebrand on hermes-named content; anchor rename-invariant; **fails loud on a stale anchor** at `build.py:387`). `cli.py` is top-level `upstream/cli.py` → ships to `dist/argo/cli.py` (verify with `grep '"skin": "argo"' dist/argo/cli.py`; the post-rename module dir is `argo_cli/` for the skin engine, but the top-level entry stays `cli.py`). Per locked decision #4 this IS the documented distribution-default-switch standard; the user approved touching `packaging-strip.yaml` provided the mechanism is the documented standard (T-DOCS documents it). The rule shape mirrors existing `content_edits` (a `name`/`file`/`why`/`find`/`replace` block).
_Rejected:_ `argo-rename.yaml` (`"default"` is not a hermes token, can't be renamed); a dedicated quilt patch (keeps the switch in the series → refresh churn on a config-shape sync; `content_edits` keeps it out and is loud-on-drift).

### AD3 — Generator placement: a `make gen-skin` step that COMMITS output to `overlay/`; `make build` consumes the committed overlay; CI drift gate (Open Q3)
`tools/gen_argo_skin.py` reads the installed DS (`tools/skin-gen/node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`, overridable via `--ds-tokens`) and emits two deterministic committed artifacts: `overlay/hermes_cli/_argo_skin.py` and `overlay/ui-tui/src/argoTheme.generated.ts`. It is invoked by **`make gen-skin`** (= `npm --prefix tools/skin-gen ci` then `python tools/gen_argo_skin.py`), NOT inside `make build` (Fact #1: no node at make-build time). `make build` ships the committed overlay verbatim, so native installs, `make test`, `make dist-test`, and the Docker builder need NO DS/npm/git access. Freshness is proven by a CI job that runs `make gen-skin && git diff --exit-code overlay/` (the git-dep analogue of the baseline's stale-output gate).
Determinism: sorted keys, lowercase hex verbatim, no timestamps; header records the installed DS version. Keeps `tests/test_dist_determinism.py` (runs `make clean && make build` twice, compares the tree — no npm) green.
_Rejected:_ wiring the generator into `make build` against `node_modules` (breaks every CI/Docker `make build`); re-running it in the Docker builder against a fresh clone (re-introduces npm into the hermetic builder for zero benefit — F2: the image never imports the DS).

### AD4 — DS consumption: private npm git dependency in a generator-only `tools/skin-gen/` package (Open Q4, locked 2026-06-07)
`@nadicodeai/design-system` is consumed as a normal npm **git** `dependencies` entry — `"@nadicodeai/design-system": "github:nadicodeai/nadicodeai-design-system"` — no publish, no registry, no `.npmrc`/auth/SHA-in-manifest/vendoring (locked decision #1; verified `find . -name .npmrc` empty). **PROVEN 2026-06-07:** `npm install github:nadicodeai/nadicodeai-design-system` resolves in ~11s via the maintainer's org git auth; `package-lock.json` records `git+ssh://…#2dcbc1a7d75d…` (commit-pinned, reproducible); the DS has `prepublishOnly` (not `prepare`) so npm uses the committed `dist/` directly with no build step. Because the DS is **generator-only** (F2 — `ui-tui` imports nothing from it), it is declared in a dedicated `tools/skin-gen/package.json` with a committed `tools/skin-gen/package-lock.json`. This: (a) keeps the DS out of the production image; (b) keeps it OUT of the pristine-gated `upstream/package-lock.json` (22,229 lines) — workspace placement would force a quilt patch against that lockfile (fragile, churns every sync) and pull the DS into the image needlessly; (c) is still "a normal `dependencies` entry, lockfile-pinned, no auth" — honoring the standard. The generator reads `tools/skin-gen/node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`. A DS update = `npm --prefix tools/skin-gen update @nadicodeai/design-system` (re-resolves the git commit) + `make gen-skin` + commit.
**The placement (`tools/skin-gen/` vs the `upstream/` workspace) is a genuine USER decision** — the tooling-package placement satisfies the standard (normal dep, lockfile-pinned, no auth) while avoiding the image/lockfile costs; strict-workspace-parity is the alternative. See Decisions Requiring the User #1.
**No publish prerequisite.** The DS stays private; npm clones it via existing org git auth. The only residual auth question is the optional CI drift-gate (a CI job cloning the private DS needs a cross-repo token/deploy-key — local `make gen-skin` needs none; see Decisions #2).
_Rejected:_ vendoring / SHA-in-manifest / `.npmrc`/private-registry (explicitly rejected by the user); publishing to public npm (unnecessary — git dep works in-org and keeps the DS private).

### AD5 — ASCII art: hand-authored once, colored from tokens; USER sign-off at CP-A (Open Q5)
DS SVGs are glyph-based (`logo-mark.svg`: seam + green `#007a5e` / red `#cd212a` nodes; `logo-wordmark.svg`: text + seam), so auto-tracing yields garbage. `banner_logo` (block-letter "ARGO" in the `ares`/`poseidon` style) and `banner_hero` (compact seam + node mark) are **hand-authored Rich-markup templates** with COLOR placeholders the generator fills from DS tokens. Same templates feed ui-tui via `parseRichMarkup`. Approved DIRECTION per locked decision #5 (block-letter ARGO + compact seam/node hero, ares/poseidon style). The **green-red node** motif (green `#007a5e` + red `#cd212a`, both present on current DS master — F5) is on-token; FINAL glyphs need USER sign-off at CP-A. Art is a static template; only colors track tokens.

### AD6 — ui-tui: generate `DARK/LIGHT_THEME`/`BRAND` from the same TOKEN_MAP + patch the 5 residues; ANSI-downsample untouched (Open Q6)
`ThemeColors` is **28 keys** (`theme.ts:1-35`, verified: primary, accent, border, text, muted, 4×completion, label, ok, error, warn, prompt, sessionLabel, sessionBorder, 6×status, selectionBg, 4×diff, shellDollar). The generator emits dark+light literals from the SAME `TOKEN_MAP` as the Python skin. `patches/0017-ui-tui-argo.patch`:
1. import generated literals → replace inline `DARK_THEME.color` / `LIGHT_THEME.color` bodies;
2. patch `BRAND` (`theme.ts:239-247`) to Argo (`name:'Argo'`, drop `⚕` icon, neutral `goodbye`/`welcome`/`helpHeader`) — kills the `⚕` `fromSkin` can't reach (F1);
3. set `DARK_THEME`/`LIGHT_THEME` `bannerLogo`/`bannerHero` (currently `''`) to the generated Argo art — also defeats `branding.tsx:163`'s caduceus default (F1a);
4. patch the **5 verified residues**: `components/appLayout.tsx:328`, `components/appChrome.tsx:30,54` (keep `EMOJI_FRAME_WIDTH` at `:81` valid), `app/uiStore.ts:28`, **`content/fortunes.ts:26`**;
5. refresh `upstream/ui-tui/src/__tests__/theme.test.ts` — `:46` `'Hermes Agent'`→`'Argo'`, `:54` `DEFAULT_THEME.color.primary` `'#FFD700'`→the DS hex, `:55` `error '#ef5350'`→the DS error hex (these three break when the theme is patched; verified) + add a DS-hex golden.
Leave `normalizeThemeForAnsiLightTerminal` + `ANSI_NORMALIZED_FOREGROUNDS` UNTOUCHED. **CI gap (verified):** `make test` = `pytest -m 'not integration'`; ui-tui vitest runs in NO Argo CI gate; the image runs only `npm run build` (=`tsc`) at `Dockerfile:405`. Mitigation: refresh the assertions in-patch + add a Python-side golden in `make test` reading the generated `.ts`; `make image-full` exercises `tsc`.

### AD7 — Native (non-Docker) installs default to `argo` too (Open Q8, locked #5)
The `content_edits` switch (AD2) flips `display.skin` across the whole `dist/argo/` tree = the native-install artifact; no install-mode branch exists to make native differ. So native defaults to `argo`, matching locked decision #5. `default` (Hermes) stays opt-in via `/skin default`.

### AD8 — Spinner + branding fully populated to prevent Hermes inheritance (Assumption 7)
`_build_skin_config` (`skin_engine.py:692-704`) merges `colors`/`spinner`/`branding` ON TOP of `default`, so omitted keys inherit Hermes. The generator emits ALL spinner keys (plain verbs, minimal faces, no `wings`) and ALL branding keys (`agent_name:"Argo"`, neutral rest, no `⚕`). A unit test asserts no kawaii/`⚕`/`⚔` in the resolved `argo` skin.

### AD9 — Standards-first + documentation as a first-class deliverable (locked #3, SC-6)
Establish and document the four mechanisms BEFORE/WITH the implementation, in **AGENTS.md** (concise, progressive-disclosure — extends `## Common tasks` and `## Where to read more`, which already follow this convention) AND **`docs/argo-design-system.md`** (full written process) AND a small extension to **`.shepherd/standards.md`** (its `## Dependencies` + a new `## Distribution Defaults` subsection — the repo's existing standards layer):
  (a) **DS dependency standard** — private npm **git** dep (`github:nadicodeai/nadicodeai-design-system`), lockfile-pinned to the commit, no publish/`.npmrc`/auth/SHA-in-manifest/vendoring; declared in `tools/skin-gen/` (generator-only).
  (b) **token→skin generator standard** — one generator + one `TOKEN_MAP`, two emitters, runs via `make gen-skin` reading `node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`, output committed to `overlay/`, `make build` consumes the committed overlay, DS bump = `npm update` + `make gen-skin` + commit.
  (c) **distribution default-skin-switch standard** — ONE mechanism = a `content_edits` rule in `packaging-strip.yaml` with a `why:` + loud-on-drift anchor (`build.py:387`).
  (d) the patch/overlay/`content_edits` conventions for this work (patch carries structure, overlay carries generated data, no hand-typed hexes).
Where a standard isn't crisp today (the distribution-default-switch standard), define it here first, then implement to it. **Not "done" until AGENTS.md + docs exist AND match the implementation (SC-6).**

---

## Dependency Graph

```
(no publish/T-PRE blocker — DS is a private git dep, PROVEN to install via org git auth)

T-DOCS (standards + AGENTS.md + docs/ + .shepherd/ foundation, drafted)  ── UPHILL foundation
T0 (gate-verification throwaway harness)  ── independent
   │
   ▼
T1 (tools/skin-gen git DS dep + committed lockfile)  ── UPHILL: closes Q4 wiring
   │
   ▼
T2 (generator gen_argo_skin.py + TOKEN_MAP + golden tests; reads node_modules)  ── UPHILL: closes Q3/Q6/Q7 contract
   │
   ▼
T3 (ASCII art authoring + USER sign-off @ CP-A)  ── UPHILL: aesthetic unknown
   │
   ├──────► T4 (overlay/_argo_skin.py + patch 0016 register + skin tests)   (Q1)
   │             │
   │             ▼
   │        T5 (content_edits default-skin switch + cli integration test)   (Q2/Q8)
   │
   └──────► T6 (overlay/argoTheme.generated.ts + patch 0017 ui-tui: DARK/LIGHT/BRAND + 5 residues + theme.test)   (Q6)
                  │
T4,T5,T6 ──► T7 (SC-5 glyph denylist scanner + assert contracts + throwaway mutation proof)
                  │
                  ▼
            T8 (make gen-skin target + CI regen-drift gate; pre-commit hook)   (Q3 placement)
                  │
                  ▼
            T-DOCS2 (finalize AGENTS.md + docs/ to MATCH the implementation; SC-6 verification)
                  │
                  ▼
            T9 (full gate run: build/test/lint/typecheck/leakage/pristine/packaging/dist-test/image-full + PR)
                  │
                  ▼
            T10 (DS git-dep bump re-flow proof + finalize)
```

---

## Uphill — Resolve & De-risk

### T-PRE — Confirm the DS git-dependency installs (NO publish needed) [XS — PROVEN]
- **Description:** No publish, no registry, no maintainer npm action. The DS stays private and is consumed as `github:nadicodeai/nadicodeai-design-system`; npm clones it via existing org git auth. **Already PROVEN 2026-06-07:** a scratch `npm install github:nadicodeai/nadicodeai-design-system` resolved in ~11s, exposed `dist/tokens/nadicode.dtcg.json` (cyan `#50e3c2`, flag-red `#cd212a`), pinned `git+ssh://…#2dcbc1a` in the lockfile, needed no `.npmrc`. T1 formalizes this in `tools/skin-gen/`.
- **Acceptance:** a scratch `npm install github:nadicodeai/nadicodeai-design-system` yields `node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`.
- **Verification:** (done) `cd "$(mktemp -d)" && npm init -y && npm install github:nadicodeai/nadicodeai-design-system && test -f node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`
- **Dependencies:** none — NOT blocking.
- **Files:** none (cross-repo read-only check).
- **Scope:** XS (proven).
- **Owner:** done — no maintainer npm-publish action required.

### T-DOCS — Standards + AGENTS.md + docs/ foundation (drafted) [M]
- **Description:** Author the documented standards BEFORE/WITH the implementation (locked #3, AD9). New `docs/argo-design-system.md` (full written process for the four standards). Extend AGENTS.md `## Common tasks` with concise actionable entries ("Regenerate the Argo skin from the DS — `make gen-skin`", "Change a distribution default — add a `content_edits` rule", "Bump the design system — `npm --prefix tools/skin-gen update` + `make gen-skin`") and add the doc to `## Where to read more` (progressive disclosure; AGENTS.md additions kept tight). Extend `.shepherd/standards.md` (`## Dependencies` + a new `## Distribution Defaults` subsection). Draft now; finalize to match the as-built code at T-DOCS2.
- **Acceptance:** `docs/argo-design-system.md` exists covering all four standards; AGENTS.md links to it and has the new task entries; `.shepherd/standards.md` documents the content_edits default-switch + the DS-dep standard; no contradiction with existing "Hard rules"/standards (e.g. "no `.npmrc`").
- **Verification:** `test -f docs/argo-design-system.md && grep -q 'argo-design-system' AGENTS.md && grep -qE 'git dependency|package-lock|content_edits|gen-skin' docs/argo-design-system.md`
- **Dependencies:** none (DS git-dep is proven; T1 formalizes it).
- **Files:** `docs/argo-design-system.md` (new), `AGENTS.md` (extend `## Common tasks` + `## Where to read more`), `.shepherd/standards.md` (extend).
- **Scope:** M.
- **Decision recorded (#3):** standards-first; docs are a first-class deliverable; the distribution-default-switch standard is `content_edits` in `packaging-strip.yaml`.

### T0 — Stand up the gate-verification harness in a throwaway repo [S]
- **Description:** Extend `tests/test_precommit_gate.py` (fake-Makefile, throwaway git repo, `subprocess` — verified present, 4981 bytes) so the `.githooks/pre-commit` gate and the new SC-5 glyph scanner are proven WITHOUT live-firing a broken commit (memory: never-live-fire-destructive-tests). Reused by T7.
- **Acceptance:** A test asserts the pre-commit hook blocks a commit when the (future) glyph gate fails, in a throwaway repo; green.
- **Verification:** `pytest tests/test_precommit_gate.py -q`
- **Dependencies:** none.
- **Files:** `tests/test_precommit_gate.py` (extend) and/or `tests/test_check_no_legacy_glyphs.py` (new, harness portion).
- **Scope:** S.
- **Decision recorded:** SC-5 proven by an automated throwaway-repo test, never by committing a broken artifact.

### T1 — `tools/skin-gen/` DS git dependency + committed lockfile [S]
- **Description:** Create `tools/skin-gen/package.json` = `{"name":"argo-skin-gen","private":true,"dependencies":{"@nadicodeai/design-system":"github:nadicodeai/nadicodeai-design-system"}}` (no `.npmrc`). Run `npm install --prefix tools/skin-gen` — npm clones the private DS via the existing **org git auth** (PROVEN 2026-06-07) — and COMMIT `tools/skin-gen/package-lock.json` (it records the resolved git commit). `.gitignore` `tools/skin-gen/node_modules/`. This is the ONLY place the DS is consumed; read by the generator, never shipped in the runtime image (F2). _If the user chooses workspace placement (Decisions #1), this becomes a quilt patch to `upstream/package.json` + the workspace lockfile instead — but the tooling package is the recommended default._
- **Acceptance:** `npm install --prefix tools/skin-gen` resolves with NO `.npmrc`/token (org git auth only); `tools/skin-gen/node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json` exists and parses; `tools/skin-gen/package-lock.json` (committed) records `git+ssh://…#<commit>`; no `.npmrc` anywhere.
- **Verification:** `npm install --prefix tools/skin-gen --no-audit && python3 -c "import json; d=json.load(open('tools/skin-gen/node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json')); c=d.get('nadicode',{}).get('color',d.get('color',{})); assert c['cyan']['\$value']['hex']=='#50e3c2'" && test -z "$(find . -name .npmrc -not -path '*/node_modules/*')"`
- **Dependencies:** none (git-dep proven).
- **Files:** `tools/skin-gen/package.json` (new), `tools/skin-gen/package-lock.json` (new), `.gitignore` (add `tools/skin-gen/node_modules/`).
- **Scope:** S.
- **Decision recorded (Q4):** DS = private git dep (`github:…`), resolved in a generator-only `tools/skin-gen/`, lockfile-pinned to the commit; no publish, no vendoring, no SHA-in-manifest, no `.npmrc`.

### T2 — Generator `tools/gen_argo_skin.py` + `TOKEN_MAP` + golden tests [M]
- **Description:** Deterministic DTCG→{Python skin dict, ui-tui theme literals} generator. **Auto-detects the DTCG container (`nadicode.color` else top-level `color`) and traverses `…[<name>]["$value"]["hex"]`** (F5 — the DS oscillates between the two shapes). One `TOKEN_MAP` maps the spec table onto BOTH the 30 Python skin color keys (F6) AND the 28 `ThemeColors` keys (theme.ts:1-35), per the spec table: `ui_error`/`status_bar_critical` → `flag-red #cd212a` (present on current master), non-critical `error #b80022`, `status_bar_bad` → `error-deep #820018`, `state-review #f5a623`. Emits `overlay/hermes_cli/_argo_skin.py` (`ARGO_SKIN_DATA`: 30 colors + spinner + branding + tool_prefix + banner_logo/hero, full per AD8) and `overlay/ui-tui/src/argoTheme.generated.ts` (DARK/LIGHT `ThemeColors` + Argo `BRAND` + bannerLogo/Hero). Reads `--ds-tokens` (default `tools/skin-gen/node_modules/@nadicodeai/design-system/dist/tokens/nadicode.dtcg.json`). Header records the installed DS version. Asserts every MAPPED source token exists; FAILS LOUD on a drop (no silent fallback). Hand-authored art templates with token-color placeholders (T3). Tests use a committed fixture (copied from the git-installed DS package) so they need no npm/git. Golden tests: byte-identical on repeat; output contains DS hex (e.g. `banner_title:"#50e3c2"`); a perturbed token CHANGES output (mutation proof); full Python (30) + full `ThemeColors` (28) key coverage; loud-fail when a mapped token is removed from a fixture; no kawaii/`⚕`/`⚔` in resolved data.
- **Acceptance:** Two runs byte-identical; golden matches; perturbation test red on a wrong mapping; coverage test asserts both full key sets; loud-fail test green.
- **Verification:** `python tools/gen_argo_skin.py --ds-tokens tests/fixtures/nadicode.dtcg.sample.json && pytest tests/test_gen_argo_skin.py -q && python tools/gen_argo_skin.py --ds-tokens tests/fixtures/nadicode.dtcg.sample.json && git diff --exit-code overlay/hermes_cli/_argo_skin.py overlay/ui-tui/src/argoTheme.generated.ts`
- **Dependencies:** T1.
- **Files:** `tools/gen_argo_skin.py` (new), `tests/test_gen_argo_skin.py` (new), `tests/fixtures/nadicode.dtcg.sample.json` (new, copied from the git-installed DS package).
- **Scope:** M.
- **Decision recorded (Q3 contract, Q6, Q7):** one `TOKEN_MAP`, two emitters, deterministic, loud-on-drift; container-auto-detect (`nadicode.color`/`color`) `.$value.hex` traversal; `flag-red #cd212a` present, used for critical.

### T3 — Author Argo ASCII logo + hero + minimal spinner; USER sign-off @ CP-A [M]
- **Description:** Hand-author `banner_logo` (block-letter "ARGO", ares/poseidon style — see existing builtins + the rich banner width budget at `cli.py:2900-2902` for the tiny fallback), `banner_hero` (compact seam + node mark echoing `logo-mark.svg`), and the neutralized spinner glyphs, as templates with token-color placeholders the generator fills. Color the node motif from the DS logo tokens: green `#007a5e` + red `#cd212a` (both present on current DS master — F5), with cyan/link accents per the locked direction. Render a preview via Rich + the ui-tui `parseRichMarkup` path.
- **Acceptance:** Logo fits the rich-banner width budget; hero ~22-30 cols (poseidon/charizard budget); NO `⚕`/`⚔`/caduceus/kawaii; colors token-sourced; **Vadim approves the art at CP-A.**
- **Verification:** `python tools/gen_argo_skin.py --preview` (prints rendered art); visual review; glyph denylist (T7) passes.
- **Dependencies:** T2.
- **Files:** art templates in `tools/gen_argo_skin.py` (or `tools/argo_art.py`).
- **Scope:** M.
- **Decision recorded (Q5):** hand-authored, token-colored; node-color = DS green `#007a5e` + red `#cd212a` (on-token); **final art = USER sign-off @ CP-A** (Decisions #3).

---

## Downhill — Execution

### T4 — Commit `overlay/hermes_cli/_argo_skin.py`; patch 0016 register `argo` in `_BUILTIN_SKINS` [M]
- **Description:** Run `make gen-skin` to produce the committed overlay. Create `patches/0016-argo-skin.patch` via the quilt workdir over `upstream/` (memory: quilt-patch-editing-workflow, `QUILT_PATCHES`): guarded import + `"argo": _ARGO_SKIN_DATA` before the dict close at `skin_engine.py:645` (AD1), plus extend `upstream/tests/hermes_cli/test_skin_engine.py` (`test_argo_skin_loads`, `test_argo_has_complete_colors`, `test_set_active_skin_argo`, `test_argo_branding_no_hermes_glyph`). Add `patches/asserts/0016-argo-skin.txt` POSITIVE contract (`path:argo_cli/_argo_skin.py "argo"`, `path:argo_cli/skin_engine.py _ARGO_SKIN_DATA`, `path:argo_cli/_argo_skin.py "agent_name": "Argo"`). Add to `patches/series` + `patches/asserts/manifest.txt`.
- **Acceptance:** `make build` applies 0016; `dist/argo/argo_cli/_argo_skin.py` present; `load_skin("argo")` resolves all 30 color keys; `list_skins()` includes argo; `git diff upstream/` empty after build.
- **Verification:** `make build && make check-upstream-pristine && cd dist/argo && PYTHONPATH=. python -c "from argo_cli.skin_engine import load_skin; s=load_skin('argo'); assert s.name=='argo' and s.colors['banner_title']=='#50e3c2'" && cd - && make leakage-static`
- **Dependencies:** T2, T3.
- **Files:** `overlay/hermes_cli/_argo_skin.py` (generated, committed), `patches/0016-argo-skin.patch`, `patches/asserts/0016-argo-skin.txt`, `patches/series`, `patches/asserts/manifest.txt`. (Test edit carried inside patch 0016.)
- **Scope:** M.

### T5 — Default-skin switch via `packaging-strip.yaml` content_edit + CLI integration test [S]
- **Description:** Add a `content_edits` rule (AD2) flipping `"skin": "default"` → `"skin": "argo"` at `cli.py:458` (rename-invariant anchor; fails loud on drift at `build.py:387`), mirroring the existing rule shape (`name`/`file`/`why`/`find`/`replace`). Extend `upstream/tests/cli/test_cli_skin_integration.py`: under the dist config `get_active_skin().name == "argo"`, branding resolves to "Argo", the `cli.py:2884` branch yields no "NOUS HERMES". (Native inherits argo — AD7.)
- **Acceptance:** Fresh `dist/argo` resolves active skin = `argo`; banner takes the `agent_name` branch; `grep '"skin": "argo"' dist/argo/cli.py` hits (**top-level `dist/argo/cli.py`**).
- **Verification:** `make build && grep -q '"skin": "argo"' dist/argo/cli.py && make dist-test DIST_TEST_ARGS="--paths tests/cli/test_cli_skin_integration.py:tests/hermes_cli/test_skin_engine.py"`
- **Dependencies:** T4.
- **Files:** `packaging-strip.yaml` (content_edits rule), `upstream/tests/cli/test_cli_skin_integration.py` (via patch or as a dist test).
- **Scope:** S.
- **Note:** Touching `packaging-strip.yaml` is PRE-APPROVED by locked decision #4 provided the mechanism is the documented standard (T-DOCS does that). No fresh user ask.

### T6 — Commit `overlay/ui-tui/src/argoTheme.generated.ts`; patch 0017 ui-tui (DARK/LIGHT/BRAND + 5 residues + theme.test) [M]
- **Description:** Commit the generated `.ts`. Create `patches/0017-ui-tui-argo.patch` per AD6: (1) import generated literals → `DARK_THEME.color`/`LIGHT_THEME.color`; (2) patch `BRAND` (`theme.ts:239-247`) to Argo, drop `⚕`; (3) set `DARK_THEME`/`LIGHT_THEME` `bannerLogo`/`bannerHero` (defeats `branding.tsx:163` caduceus default); (4) patch the **5 residues** `components/appLayout.tsx:328`, `components/appChrome.tsx:30,54` (keep `EMOJI_FRAME_WIDTH` at `:81` valid), `app/uiStore.ts:28`, `content/fortunes.ts:26`; (5) refresh `upstream/ui-tui/src/__tests__/theme.test.ts` (`:46` name, `:54` primary, `:55` error) + add a DS-hex golden. Leave `normalizeThemeForAnsiLightTerminal`/`ANSI_NORMALIZED_FOREGROUNDS` untouched. Add `patches/asserts/0017-ui-tui-argo.txt` POSITIVE asserts (`path:ui-tui/src/argoTheme.generated.ts #50e3c2`, `path:ui-tui/src/theme.ts name: 'Argo'`). Add a Python-side golden in `make test` reading the generated `.ts` (vitest is in no CI gate).
- **Acceptance:** `DARK_THEME.color.primary` is DS hex (not `#FFD700`); `BRAND.name === 'Argo'`, no `⚕`; all 5 residues neutralized; `npm run type-check && npm run test` green in `dist/argo/ui-tui`; `git diff upstream/` empty after build.
- **Verification:** `make build && make check-upstream-pristine && cd dist/argo/ui-tui && npm install --prefer-offline --no-audit && npm run type-check && npm run test`
- **Dependencies:** T2, T3.
- **Files:** `overlay/ui-tui/src/argoTheme.generated.ts` (generated, committed), `patches/0017-ui-tui-argo.patch`, `patches/asserts/0017-ui-tui-argo.txt`, `patches/series`, `patches/asserts/manifest.txt`. (Test edit carried inside patch 0017.)
- **Scope:** M.

### T7 — SC-5 glyph denylist scanner + assertion contracts + throwaway mutation proof [S]
- **Description:** Add `tools/check_no_legacy_glyphs.py` — a denylist scan over `dist/argo/` for `caduceus`, `⚕`, `⚔`, the kawaii faces (`🌀🤔✨🍵🔮🌟`), and `#FFD700`/`#ffd700` on the **Argo-owned surfaces** (the `argo` skin data + ui-tui theme/banner). Wire into `make leakage-static` (`Makefile:81`) — it is the REAL SC-5 enforcement (`verify_no_leakage.py` is glyph-blind, F3; the assertion runner is positive-only). Add `tests/test_check_no_legacy_glyphs.py`. Prove the gate trips on a planted `⚕` in the T0 harness (never live-fire). **Scope the denylist to Argo surfaces so it does NOT flag the still-present `default` skin's legitimate `⚕`** (which MUST remain).
- **Acceptance:** `make leakage-static` fails on a planted banned glyph in an Argo surface, passes on the shipped art + the untouched `default` skin; mutation test green.
- **Verification:** `make build && make leakage-static && pytest tests/test_check_no_legacy_glyphs.py -q`
- **Dependencies:** T4, T5, T6.
- **Files:** `tools/check_no_legacy_glyphs.py` (new), `Makefile` (`leakage-static` wiring at :81), `tests/test_check_no_legacy_glyphs.py` (new).
- **Scope:** S.
- **Decision recorded:** SC-5 enforced by a dedicated denylist scanner + unit tests, scoped to Argo surfaces (preserves `default`'s `⚕`).

### T8 — `make gen-skin` target + CI regen-drift gate; pre-commit hook [S]
- **Description:** Add a `make gen-skin` target: `npm --prefix tools/skin-gen ci --no-audit --no-fund && python tools/gen_argo_skin.py`. Add a CI job (or extend an existing one) with `setup-node` + git auth to the private DS (cross-repo token/deploy-key — Decisions #2) + `make gen-skin` then `git diff --exit-code overlay/hermes_cli/_argo_skin.py overlay/ui-tui/src/argoTheme.generated.ts` (the git-dep analogue of the baseline stale-output gate — proves the committed overlay matches a fresh regen from the git-installed DS). `make build` is UNCHANGED (consumes committed overlay; runs no npm/git). Confirm `.githooks/pre-commit` (build+leakage on patch/overlay/tools commits) passes (`make install-hooks` once). Document `make gen-skin` in T-DOCS.
- **Acceptance:** `make gen-skin` regenerates identically (`git diff --exit-code overlay/`); the CI drift gate is green; `tests/test_dist_determinism.py` green; pre-commit hook green on a patch/overlay/tools commit.
- **Verification:** `make install-hooks && make gen-skin && git diff --exit-code overlay/hermes_cli/_argo_skin.py overlay/ui-tui/src/argoTheme.generated.ts && pytest -m integration tests/test_dist_determinism.py`
- **Dependencies:** T4, T6.
- **Files:** `Makefile` (`gen-skin` target), `.github/workflows/ci.yml` (regen-drift job: `setup-node` + `npm --prefix tools/skin-gen ci`), `docs/argo-design-system.md` (update).
- **Scope:** S.
- **Decision recorded (Q3 placement):** generator runs via `make gen-skin` (NOT `make build`); committed overlay; CI proves no drift.
- **Note:** The CI workflow change (`setup-node` in one job) is Ask-first per spec Boundaries — see Decisions Requiring the User #4.

### T-DOCS2 — Finalize AGENTS.md + docs/ to MATCH the implementation (SC-6) [S]
- **Description:** Reconcile the T-DOCS drafts with the as-built reality: final generator flags, the exact `content_edits` rule name, exact overlay paths, the `make gen-skin` command, the node-aware CI job. Ensure AGENTS.md is concise and links to `docs/argo-design-system.md`; ensure docs and `.shepherd/standards.md` match the code. This is the SC-6 gate.
- **Acceptance:** AGENTS.md + `docs/argo-design-system.md` describe the actual `make gen-skin` command, the actual `content_edits` rule, the git-dependency model, the overlay paths, and the patch conventions — verified against the code paths.
- **Verification:** Read-review against T1-T8 artifacts; `grep -qE 'gen-skin|content_edits|@nadicodeai/design-system' docs/argo-design-system.md`; confirm every command in the doc runs (`python tools/gen_argo_skin.py --help`, `npm view @nadicodeai/design-system version`, `make gen-skin`).
- **Dependencies:** T1-T8.
- **Files:** `AGENTS.md`, `docs/argo-design-system.md`, `.shepherd/standards.md`.
- **Scope:** S.
- **Decision recorded (#3, SC-6):** docs match the implementation; this is a release gate.

### T9 — Full gate run + PR [M]
- **Description:** Run the complete Phase-1 gate set and fix fallout (capture output to files — memory: no-fabricated-results). `make dist-test` is REQUIRED before merging a dist-affecting change (memory: argo-dist-test-gate; non-blocking in CI). `make image` = runtime-slim (no ui-tui); **`make image-full`** = runtime-full and exercises the ui-tui `npm run build`/`tsc` (`Dockerfile:405`) — run it. `check-packaging-contract` is unaffected by the npm dep (F7) but run it to confirm. Open a PR so CI `dist-argo-tests` + image build (no push) + the T8 regen-drift job run.
- **Acceptance:** All green: `make build`, `make test`, `make lint`, `make typecheck`, `make leakage-static`, `make check-upstream-pristine`, `make check-packaging-contract`, `make dist-test`, `make image-full`. `git diff --stat upstream/` empty.
- **Verification:** Run each target into a log file; `git diff --stat upstream/` empty; PR opened.
- **Dependencies:** T0-T8, T-DOCS2.
- **Files:** none (verification + targeted fixes).
- **Scope:** M.

### T10 — DS git-dep bump re-flow proof + finalize [XS]
- **Description:** Prove Success Criterion #3: a deliberate DS bump (`npm --prefix tools/skin-gen update @nadicodeai/design-system` re-resolving the git commit + updating `tools/skin-gen/package-lock.json`, in a scratch) re-runs `make gen-skin` and re-flows new token values into BOTH `overlay/hermes_cli/_argo_skin.py` and `overlay/ui-tui/src/argoTheme.generated.ts`, with no manual hex edit. Re-green gates after final art sign-off (T3).
- **Acceptance:** A scratch DS version bump changes the generated palette in both overlay artifacts; gates re-green; user art sign-off recorded.
- **Verification:** scratch `npm --prefix tools/skin-gen update @nadicodeai/design-system` + `make gen-skin` + `git diff overlay/` shows a palette change; `make leakage-static` green.
- **Dependencies:** T9.
- **Files:** regenerated overlay artifacts (only if art changed post sign-off).
- **Scope:** XS.

---

## Checkpoints

- **CP-0 — after T-DOCS + T0 + T1 (foundation):** the DS git dep resolves via org git auth (`npm --prefix tools/skin-gen install`); standards/docs drafted in AGENTS.md + `docs/argo-design-system.md` + `.shepherd/standards.md`; throwaway harness ready. System still builds (committed overlay path untouched).
- **CP-A — after T2 + T3 candidate (end of Uphill):** Review the `TOKEN_MAP` (verified against the lockfile-pinned DS commit — `flag-red #cd212a`, `state-review #f5a623`, green-red logo) and the ASCII art candidate WITH the user. **Final art needs explicit USER sign-off (locked #5).** Generator deterministic + golden-tested; DTCG coverage confirmed against the git-installed package. Also confirm the T1 DS-placement choice (tooling package vs workspace — Decisions #1).
- **CP-B — after T4 + T5:** Terminal CLI skin works and is the dist default; `make dist-test` skin tests green; no NOUS HERMES/caduceus/kawaii via the skin. Stop before ui-tui.
- **CP-C — after T6:** ui-tui themed from DS (live via gateway + standalone `DEFAULT_THEME`); `⚕` brand glyph + all 5 residues retired; `tsc` + vitest green.
- **CP-D — after T-DOCS2 + T9:** Full gate set green; AGENTS.md + docs match the implementation (SC-6); PR opened so CI dist-argo-tests + image build + regen-drift run; SC-5 glyph gate enforced. Merge-readiness.
- **CP-E — after T10:** DS npm-bump re-flow proven; art signed off. Ship-readiness.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CI cloning the private DS for the regen-drift gate needs cross-repo git auth (default `GITHUB_TOKEN` is repo-scoped) | Med | Low | Local `make gen-skin` + pre-commit need no CI auth; the CI drift job uses a PAT/deploy-key (Decisions #2/#4). Not a blocker for `make build` (ships committed overlay). |
| Generator wired into `make build` reading `node_modules` → breaks every CI/Docker `make build` (no node there — `Dockerfile:89` python builder, `build.py` runs no npm) | High (confirmed) | High | AD3/T8: generator is a SEPARATE `make gen-skin` step; `make build` consumes committed overlay; CI proves no drift via install+regen+`git diff`. |
| DTCG traversal wrong — spec said `nadicode.color.<name>.$value.hex`, a draft said `color.<name>.hex`; truth is `color.<name>.$value.hex` | High (confirmed) | High | F5: T2 traverses `d["color"][name]["$value"]["hex"]`; golden test against the real fixture catches it. |
| DS palette/schema VOLATILE — oscillates across commits (`3b8bd32` flattened the schema + dropped `flag-red`; `2dcbc1a` restores both, green-red logo) | High (confirmed) | High | The committed lockfile pins the git commit to freeze the target; generator auto-detects the container shape and FAILS LOUD on a missing mapped token; golden test against the pinned fixture. Re-verify the palette at CP-A against the pinned commit. |
| SC-5 silently unenforced (`verify_no_leakage.py` hermes-only; assertion runner positive-only) | High (confirmed F3) | High | T7 `tools/check_no_legacy_glyphs.py` wired into `make leakage-static` + unit tests; proven in T0 harness; scoped to Argo surfaces (preserves `default`'s `⚕`). Never rely on leakage-static or `.txt` negative greps. |
| Caduceus/kawaii survive via the OMITTED residues `branding.tsx:163` (empty-hero default) + `content/fortunes.ts:26` (baseline missed both) | High (confirmed F1a) | Med | T6 sets non-empty `bannerHero` and patches `fortunes.ts`; T7 denylist covers them. |
| Baseline residue paths stale (`src/app/` vs `src/components/`) → a patch hunk fails to apply | High (verified stale) | Med | Corrected: `components/appLayout.tsx:328`, `components/appChrome.tsx:30/54`, `app/uiStore.ts:28`. |
| `fromSkin` never overrides `brand.icon` → ui-tui keeps `⚕` | High (confirmed F1) | Med | T6 patches `BRAND` directly; golden asserts no `⚕`. |
| ui-tui vitest in NO Argo CI gate → a `DEFAULT_THEME`/`BRAND` patch silently breaks `theme.test.ts:46/54/55` | High (confirmed) | Med | T6 refreshes those assertions in-patch + Python-side golden in `make test`; `make image-full` exercises `tsc`. |
| Adding the DS to the pristine-gated `upstream/package-lock.json` (22,229 lines) via quilt → fragile, churns every sync, bloats the image | Med | Med | AD4/T1: isolate the DS to `tools/skin-gen/` (generator-only, out of image); committed lockfile. Workspace placement is the user fallback (Decisions #1). |
| Generated overlay hex/art mangled by `tools/rebrand.py` | Low | High | Rename one-directional hermes→argo; hex + literal `argo` + `@nadicodeai/design-system` rename-invariant; overlay copied before rebrand (build.py:565→569); T4/T6 asserts grep POST-rename `dist/argo`; check-upstream-pristine. |
| Generator output non-deterministic → breaks `test_dist_determinism.py` | Med | Med | Sorted keys, no timestamps; `git diff --exit-code overlay/` in T8; golden + stale tests. |
| `make dist-test` red on a dist change merged straight to main (non-blocking CI) | Med | High | T9 runs `make dist-test` locally OR via PR before merge (memory: argo-dist-test-gate, sync-pr-squash). |
| CI regen gate adds `setup-node` to CI (workflow change is Ask-first) | Med | Low | T8 scopes the change to one job; Decisions #4 surfaces the touch for a user nod. |
| `content_edits` anchor `"skin": "default"` drifts on a future sync | Low | Med | Build raises loud on a missing anchor (`build.py:387`). |
| Quilt patch to skin_engine.py / theme.ts drifts on next sync | Med | Med | Patches tiny + anchored; volatile data in regenerated overlay; sync conflicts per memory: argo-sync-conflict-protocol. |
| Quilt patch silently not staged into the commit (build green from working tree) | Med | Med | Verify `git status` shows the patch staged; rebuild from a clean checkout (memory: sync-subtree-conflict-and-unstaged-patch-trap). |
| Docs drift from implementation (SC-6 false-green) | Med | Med | T-DOCS drafted uphill; T-DOCS2 reconciles to the shipped impl + is a CP-D gate; commands in docs are run to verify. |
| Editing `upstream/` directly while authoring patches | Med | High | Quilt workdir + `QUILT_PATCHES`; `make check-upstream-pristine`. |

---

## Open Questions — resolutions

| # | Question | Resolution | Owner |
|---|---|---|---|
| 1 | Skin registration mechanism | Built-in via quilt patch 0016 into `_BUILTIN_SKINS` (close at `skin_engine.py:645`) importing generated `overlay/hermes_cli/_argo_skin.py` (AD1) | Architect |
| 2 | Default-skin switch location | `content_edits` in `packaging-strip.yaml`, `file: cli.py`, flipping `cli.py:458` → `dist/argo/cli.py` (AD2); documented as THE distribution-default standard (T-DOCS) | Architect (user pre-approved per locked #4) |
| 3 | Generator placement & artifact | Separate `make gen-skin` step reading installed DS tokens; COMMIT output to `overlay/`; `make build` consumes committed overlay; CI drift gate (AD3) | Architect |
| 4 | DS consumption | Private git dep (`github:…`) resolved in generator-only `tools/skin-gen/`, lockfile-pinned to the commit; NO publish/SHA-in-manifest/vendoring/`.npmrc`/auth (AD4, PROVEN) — LOCKED 2026-06-07 | User (locked); **placement = user nod (Decisions #1)** |
| 5 | ASCII art production | Hand-authored token-colored templates; node-color = DS green `#007a5e` + red `#cd212a` (on-token, current master) (AD5) | Architect mechanism; **final art = USER sign-off @ CP-A (Decisions #3)** |
| 6 | ui-tui generator target | Generate DARK/LIGHT/BRAND literals from the same `TOKEN_MAP`; patch them + the 5 residues (incl. `branding.tsx` hero default + `fortunes.ts`); ANSI-downsample untouched (AD6) | Architect |
| 7 | DTCG dark-surface coverage | container-auto-detect (`nadicode.color`/`color`) `.$value.hex` traversal; all mapped tokens present on current master (`flag-red #cd212a`, `state-review #f5a623`); generator fails loud on a mapped-token drop (F5) | Architect |
| 8 | Native (non-Docker) installs | Default to `argo` too (the dist-tree `content_edits` IS the native artifact) — confirmed by locked #5 (AD7) | Resolved (locked) |
| 9 | Standards/docs deliverable (NEW) | First-class uphill task T-DOCS: `docs/argo-design-system.md` + AGENTS.md section + `.shepherd/standards.md` extension; SC-6 gates it (AD9) | Architect |

---

## Decisions Requiring the User

Items with **no safe autonomous default** (or that the locked decisions / spec Boundaries reserve):

1. **DS dependency placement: generator-only `tools/skin-gen/` package vs the upstream npm workspace (Open Q4 wiring).**
   - *Why surfaced:* the locked text says "consume it as a normal `dependencies` entry, exactly like `@nous-research/ui`." `@nous-research/ui` lives in the `upstream/` workspace (`upstream/web/package.json:13`, pinned by the pristine-gated `upstream/package-lock.json`). But the DS is generator-only (verified: `ui-tui` imports nothing from it), so workspace placement would (a) need a quilt patch to `upstream/package.json` + the 22,229-line pristine-gated lockfile, and (b) pull the DS into the production image needlessly.
   - *Recommendation (autonomous default):* the `tools/skin-gen/` tooling package — still a normal `dependencies` entry (a git URL) with a committed lockfile (honors the standard), but isolated from the image and the pristine gate. Choose strict-workspace-parity only if you want the DS literally in `upstream/package.json`.
   - *Why no autonomous default:* it is a deviation from the literal "exactly like @nous-research/ui" wording, even though it satisfies the underlying standard. Needs a one-line nod.

2. **DS publish — NOT NEEDED (resolved 2026-06-07).**
   - The DS stays **private** and is consumed as a git dependency (`github:nadicodeai/nadicodeai-design-system`), PROVEN to install via existing org git auth. No npm-org credentials, no cross-repo publish, no blocker. Nothing for you to do here. (The only residual auth is the *optional* CI drift-gate — see #4.)

3. **Final Argo ASCII art (logo + hero) — aesthetic sign-off @ CP-A (locked #5, Boundaries).**
   - *Why no autonomous default:* the glyph layout is a brand aesthetic the spec reserves; the DIRECTION is approved, the FINAL glyphs are not.
   - *Recommendation:* approve a block-letter "ARGO" wordmark + a compact seam/node hero in the ares/poseidon style, node motif in the DS logo colors green `#007a5e` + red `#cd212a` (both present on current DS master — the green-red direction is on-token), plus cyan/link accents. Re-verify against the pinned DS commit at CP-A.

4. **Adding `setup-node` + the DS install to a CI job for the regen-drift gate (Open Q3 / Boundaries: CI workflow change is Ask-first).**
   - *Why surfaced:* spec Boundaries list "any change to CI workflow" as Ask-first; T8's drift gate needs `setup-node` + `npm --prefix tools/skin-gen ci` in one CI job.
   - *Recommendation:* approve the one-job CI addition (`setup-node` + cross-repo git auth to the private DS via a PAT/deploy-key + `make gen-skin` + `git diff --exit-code overlay/`) — it proves the committed overlay == a fresh regen from the git-installed DS. Alternative: local `make gen-skin` + pre-commit only, no CI job (weaker — drift could slip in, but avoids the cross-repo CI token).
