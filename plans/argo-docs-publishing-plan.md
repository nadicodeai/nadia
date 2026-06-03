# Integrated Implementation Plan: Publish ARGO docs at https://docs.nadicode.ai/argo/

## Goal

Publish the ARGO-branded documentation site at `https://docs.nadicode.ai/argo/` (host `docs.nadicode.ai`, Docusaurus `baseUrl: /argo/`), mirroring how upstream Hermes ships its docs at `hermes-agent.nousresearch.com/docs/`. The site MUST be built from the **renamed** tree (`dist/argo/website/`, produced by `make build`) — never from raw `upstream/website/`, which would publish un-rebranded "hermes" docs — and deployed **into the already-provisioned Vercel project** by uploading a prebuilt static bundle via the Vercel CLI (Vercel itself performs zero build, so it cannot pick up the wrong source). The change-set is three coordinated mechanisms: (A) `packaging-strip.yaml` `content_edits` that make the Docusaurus `url`/`baseUrl`/Home env-overridable + a `sidebars.ts` fix; (B) a `deploy-docs.yml` workflow on `main`; (C) an `argo-rename.yaml` mapping that rewrites every self-referential `/docs` URL to `docs.nadicode.ai/argo` while preserving all MIT-attribution surfaces.

---

## 0. Reconciliation decisions (read first — resolves all cross-component conflicts)

The three design components overlapped on *which mechanism rewrites which URL*. The single coherent split below avoids any double-rewrite and keeps every gate green. All file:line evidence below was re-verified against the live repo and a real `make build` dist.

| URL class | Example | Owner mechanism (ONE) | Why |
|---|---|---|---|
| Docusaurus **`url` + `baseUrl`** | `url: 'https://hermes-agent.nousresearch.com'` / `baseUrl: '/docs/'` (`upstream/website/docusaurus.config.ts:10-11`) | **Component A — `content_edits`** → `process.env.DOCS_URL ?? <upstream>` / `process.env.DOCS_BASE_URL ?? <upstream>` | `baseUrl: '/docs/'` is a standalone token with **no host prefix**, so Component C's `hermes-agent.nousresearch.com/docs` key cannot match it; the rebrand leaves `url`/`baseUrl` untouched (verified: `dist/argo/website/docusaurus.config.ts:10-11` still upstream). Env-override keeps the upstream literal as the leakage-safe default. |
| Navbar **"Home" href** | `href: 'https://hermes-agent.nousresearch.com'` (`:126`) | **Component A — `content_edits`** → `https://docs.nadicode.ai/argo` | Bare host (no `/docs` path) → Component C never matches it. Self-referential brand surface, not attribution. |
| **`/docs`-path URLs in prose + generators + runtime code** | `SITE_BASE` (`generate-llms-txt.py:34`), the 5 llms-txt literals (`:12,13,34,251,252`), `UNIFIED_INDEX_URL` (`prebuild.mjs:36-37`), `acp_registry/agent.json:7` `website`, `agent/prompt_builder.py`, `argo_cli/model_catalog.py`, ~34 dist files + ~150 prose links | **Component C — rename mapping + lookahead amendment** | `hermes-agent.nousresearch.com/docs → docs.nadicode.ai/argo` collapses host+baseUrl in one pass and auto-covers every `/docs` occurrence repo-wide (verified: `grep -rln "nousresearch.com/docs" dist/argo/` = 34 files). **This makes the original Component-A `content_edits` for `generate-llms-txt.py`/`prebuild.mjs` REDUNDANT — they are DROPPED.** |
| **Attribution — MUST stay upstream** | footer copyright `Built by Nous Research` + nousresearch.com link (`:167,:171`), Discord (`:136,:157`), bare-host HTTP-Referer header, `/install.sh`, `/llms.txt` bare-host paths, `pypi.org/p/hermes-agent`, `img.shields.io/badge/Docs-hermes`, the "Based on Hermes Agent by Nous Research" credit (`argo-rename.yaml:160`), README fork-notice/badges, `NousResearch/hermes-agent` slug, all Nous model-ids | **UNTOUCHED by any component** | Different host (`nousresearch.com`, bare), a bare-host PyPI/Discord/badge, or an explicit attribution phrase. The amended lookahead releases ONLY `hermes-agent.nousresearch.com/docs`; none of these flip. Empirically confirmed the amended regex preserves them. |

**Net effect on Component A:** keep the config `url`/`baseUrl`/`organizationName`/Home `content_edits` and the build+Vercel wiring; ADD a `sidebars.ts` fix (see §0.1). DROP the `generate-llms-txt.py` and `prebuild.mjs` `content_edits` — Component C owns those literals. One mechanism owns each literal: `content_edits` run **before** rebrand (`tools/build.py:519` then `:520`, verified), so an A-side edit would change the literal first and leave the C-side mapping with nothing to match.

**Invariant verified:** Component C's `docs.nadicode.ai/argo` target is byte-identical to Component A's `DOCS_URL=https://docs.nadicode.ai` + `DOCS_BASE_URL=/argo/` (host `docs.nadicode.ai`, base path `/argo/`). The workflow builds exactly `dist/argo/website/build/` — the artifact A's build command produces. No host/path mismatch.

### 0.1 The two blockers the prior plan missed (now fixed in this change-set)

1. **`make dist-test` failure — ACP registry manifest test (FIXED here).** `dist/argo/acp_registry/agent.json:7` `website` = `https://hermes-agent.nousresearch.com/docs/user-guide/features/acp` — a `/docs` URL, **not** engine-excepted, so Component C's mapping flips it to `https://docs.nadicode.ai/argo/...`. But `dist/argo/tests/acp/test_registry_manifest.py:36` asserts `data["website"].startswith("https://hermes-agent.nousresearch.com/")` (the assertion literal is a **bare host**, preserved by the lookahead, so the engine does NOT rewrite it). Manifest flips, assertion does not → **fail**. **Fix:** update `upstream/tests/acp/test_registry_manifest.py:36` to assert the rebranded host (the ACP `website` is the agent's own docs page — self-referential, correctly migrated to the live Argo docs site). This is the **only** dist test that asserts a bare-host `/docs`-derived value (audited: `test_model_catalog.py:183` self-heals because its `PRIMARY` literal is itself rewritten identically; the three bare-host HTTP-Referer assertions in `test_provider_attribution_headers.py`/`test_openrouter_response_cache.py` stay green because the lookahead preserves the bare host).

2. **Docusaurus build failure — `sidebars.ts` references stripped China docs (FIXED here).** Independent of any URL change: the `china-docs` strip (`packaging-strip.yaml:106-122`) deletes `website/docs/user-guide/messaging/{dingtalk,feishu,qqbot,wecom,wecom-callback,weixin,yuanbao}.md`, but `dist/argo/website/sidebars.ts:644-652` ("Chinese platforms" category) still references those 7 doc IDs. Docusaurus validates sidebar doc IDs strictly (NOT governed by `onBrokenLinks: 'warn'`), so `npm run build` dies: `Invalid sidebar file … These sidebar document ids do not exist: user-guide/messaging/dingtalk …`. This is invisible to `make build`, `make leakage-static`, and `make dist-test` (the last runs only pytest, never `npm run build`). **Fix:** a `packaging-strip.yaml` `content_edit` that deletes the entire "Chinese platforms" category block from `website/sidebars.ts`.

### 0.2 Whole-file-excepted markdown is NOT reached by Component C (explicit, accepted)

The `/docs` mapping is **not** repo-wide: six whole-file engine exceptions short-circuit before `skip_contexts`, so their `/docs` links stay on the upstream host:

- `README.md`, `README.zh-CN.md` (`argo-rename.yaml:76-79`) — keep `hermes-agent.nousresearch.com/docs/...` (verified `dist/argo/README.md:8,55,82,127-145,181`). **This is correct attribution** and matches patch `0014`'s explicit header: *"It deliberately leaves attribution intact: the `NousResearch/hermes-agent` repo URLs, the `hermes-agent.nousresearch.com` docs links … are untouched."* Patch 0014 rebrands ONLY command examples + config paths, never URLs. `tests/test_readme_commands_rebranded.py` (`assert "hermes-agent.nousresearch.com" in text`) therefore stays green.
- `CONTRIBUTING.md` (`:80`) — keeps `hermes-agent.nousresearch.com/docs` and a bare-host parenthetical (`dist/argo/CONTRIBUTING.md:197`).
- `argo-already-has-routines.md` (`:84`) — keeps `hermes-agent.nousresearch.com/docs/guides/automation-templates` (`dist/argo/argo-already-has-routines.md:152`).
- `AGENTS.md` (`:82`), the two `website/docs/.../*.md` plugin-example exceptions (`:90,:92`) — no `/docs`-site links of concern.

**Decision: accept these as-is for this PR.** The READMEs/CONTRIBUTING staying on the upstream docs host is defensible attribution, and they are patch-0014-owned. The product inconsistency (published site + agent prompt + CLI cite `docs.nadicode.ai/argo`, but README still cites `hermes-agent.nousresearch.com/docs`) is a **fast-follow** (see Open Decision OD-3), not a blocker. The `argo-rename.yaml` `why`-comment edits in §2.1 are written to state this truth — they do NOT claim patch 0014 rebrands the docs links (the prior plan's comments lied about that; corrected here).

---

## 1. Ordered implementation checklist (copy-pasteable)

```bash
# 1. Branch off main (never edit main directly)
git switch -c docs-nadicode-publish

# 2. Edit argo-rename.yaml          (Component C: mapping + lookahead + truthful comments — §2.1)
# 3. Edit packaging-strip.yaml      (Component A: 3 docusaurus content_edits + sidebars China-strip — §2.2)
# 4. Add  .github/workflows/deploy-docs.yml   (Component B: on main — §2.3)
# 5. Edit upstream/tests/acp/test_registry_manifest.py:36  (dist-test fix — §2.4)
# 6. (optional) extend tests/test_full_rename_config.py     (§2.5)

# 7. Regenerate rename defaults (also runs inside make build; standalone is a convenience)
python3 tools/generate_rename_defaults.py

# 8. Build the renamed dist (regen + content_edits + rebrand -> dist/argo/)
make build

# 9. Verify the URLs/strips landed (greps in §3.2)

# 10. Leakage gate (hermes-only; stays green)
make leakage-static

# 11. Dist-test (REQUIRED gate for this dist-affecting change)
make dist-test
#     or fast slice:  make dist-test DIST_TEST_ARGS="--slice 1/6"
#     and explicitly: make dist-test DIST_TEST_ARGS="--paths tests/acp/test_registry_manifest.py"

# 12. Local Docusaurus smoke build from the RENAMED tree with env injected (§3.5)

# 13. Commit (pre-commit hook re-runs make build + make leakage-static — argo-rename.yaml is gated)
make install-hooks   # once per clone, if not already
git add argo-rename.yaml packaging-strip.yaml overlay/hermes_cli/_rename_defaults.py \
        .github/workflows/deploy-docs.yml upstream/tests/acp/test_registry_manifest.py \
        tests/test_full_rename_config.py   # last only if §2.5 applied
git commit -m "feat(docs): publish renamed docs to docs.nadicode.ai/argo (mapping + deploy workflow)"

# 14. Push + PR (CI runs ci.yml gates)
git push -u origin docs-nadicode-publish
gh pr create

# 15. AFTER merge to main: add the 3 Vercel repo secrets + disable Vercel git auto-build (§4)
```

**Ordering notes:**
- `_rename_defaults.py` is **regenerated, never hand-edited** (engine-excepted, `argo-rename.yaml:74-75`). `make build` regenerates it first (`tools/build.py:515` → `_regenerate_rename_defaults()`); step 7 standalone is only convenience. Commit the regenerated diff.
- The pre-commit hook (`.githooks/pre-commit`) fires `make build` + `make leakage-static` because the staged set matches `argo-rename\.yaml$` (and `overlay/`). The workflow YAML and the test file are NOT gated by the hook (paths don't match `^(patches/|overlay/|tools/|argo-rename\.yaml$)`), but the workflow MUST live on `main` because the release/storefront branch strips all workflows (`tools/release_branch_push.py:220-276` `_strip_release_workflows()`).

---

## 2. Every file change (final, ready-to-apply)

### 2.1 `argo-rename.yaml` (Component C — the structural fix)

**Edit C-1 — insert the docs mapping after line 22** (after the `.../main/scripts/install` mapping, before the bare-host keys, so the engine's longest-first sort consumes the whole `/docs` URL cleanly):

```diff
   - {from: "NousResearch/hermes-agent/main/scripts/install", to: "nadicodeai/argo/release/scripts/install"}
+  # --- Self-referential Argo docs site (host + baseUrl swap) ---
+  # Upstream Docusaurus is host `hermes-agent.nousresearch.com` + baseUrl
+  # '/docs/'. The Argo fork publishes the RENAMED docs (built from
+  # dist/argo/website/) at host `docs.nadicode.ai` + baseUrl '/argo/'. Rewrite
+  # host AND the /docs prefix together so e.g.
+  #   .../docs/user-guide/cli -> docs.nadicode.ai/argo/user-guide/cli
+  # (a naive host-only swap would wrongly yield docs.nadicode.ai/docs/...).
+  # This 34-char key sorts ahead of the bare org slug + bare hermes-agent keys
+  # (engine sorts longest-first), so it fires first and the tail is clean. The
+  # skip_contexts URL guard below was amended (third lookahead alternative) to
+  # RELEASE this /docs path from preservation so this mapping can fire. The BARE
+  # host (the OpenRouter HTTP-Referer attribution header), /install.sh,
+  # /llms.txt, and the img.shields.io Docs badge label remain preserved (they
+  # are not /docs paths / are a different host). Docusaurus url/baseUrl are NOT
+  # rewritten here — they are not /docs URLs; they are flipped via env-override
+  # in packaging-strip.yaml content_edits. Whole-file-excepted markdown
+  # (README*.md, CONTRIBUTING.md, argo-already-has-routines.md) is NOT reached by
+  # this mapping (the exception short-circuits before skip_contexts), so their
+  # /docs links stay on the upstream host as MIT attribution — intentional.
+  - {from: "hermes-agent.nousresearch.com/docs", to: "docs.nadicode.ai/argo"}
   # The Windows-native docs invoke install.ps1 with `-Branch main`, which would
```

**Edit C-2 — amend the negative-lookahead (replace line 115)** so the `/docs` path is released from preservation (the inner lookahead matches → the OUTER preservation lookahead fails → the URL is left unprotected so the mapping fires):

```diff
+  # The third lookahead alternative `hermes-agent\.nousresearch\.com/docs\b`
+  # makes the self-referential DOCS path REWRITABLE (inner lookahead matches ->
+  # OUTER preservation lookahead FAILS -> the host+/docs -> docs.nadicode.ai/argo
+  # mapping above fires). The BARE host (HTTP-Referer), /install.sh, /llms.txt,
+  # github.com/NousResearch/hermes-agent and pypi.org/p/hermes-agent do NOT match
+  # /docs, so they stay preserved.
-  - 'https?://(?!(?:(?:raw\.)?github(?:usercontent)?\.com/(?i:NousResearch/hermes-agent)\b|hermes-agent\.local))[^\s"''\\]*'
+  - 'https?://(?!(?:(?:raw\.)?github(?:usercontent)?\.com/(?i:NousResearch/hermes-agent)\b|hermes-agent\.local|hermes-agent\.nousresearch\.com/docs\b))[^\s"''\\]*'
```

**Edit C-3 — comment/`why` hygiene (TRUTHFUL; the prior plan's versions lied about patch 0014).** Non-functional, but comments MUST NOT lie. The READMEs/CONTRIBUTING keep their upstream `/docs` links — say exactly that.

Mapping-block header comment (lines 9-11):
```diff
   # GitHub URLs for the upstream Hermes repo map to this fork's GitHub repo
-  # (nadicodeai/argo). nadicode does not own nousresearch.com, so no
-  # docs/pypi domains are rewritten.
+  # (nadicodeai/argo). nadicode does not own nousresearch.com, so the upstream
+  # PyPI package (pypi.org/p/hermes-agent) and the bare upstream host are NOT
+  # rewritten. The ONE nousresearch.com exception is the self-referential DOCS
+  # path (hermes-agent.nousresearch.com/docs/...), which the fork now mirrors at
+  # its own live site docs.nadicode.ai/argo/ — see the docs mapping below and the
+  # amended skip_contexts URL guard. Whole-file-excepted markdown keeps its
+  # upstream /docs links (the exception short-circuits the mapping).
```

`*.egg-info/**` exception (`:67`):
```diff
-    why: "setuptools-generated metadata produced by `pip install -e .` inside the runtime Docker stage (issue #4 surfaced this). PKG-INFO embeds README.md / README.zh-CN.md verbatim, which are themselves excepted (fork-notice block, attribution badges, upstream docs links — MIT attribution requirement, no nadicode-hosted docs site). The egg-info is regenerated on every install and is never tracked in source. Excluding it here keeps `argo doctor --static` exit-zero clean for runtime users."
+    why: "setuptools-generated metadata produced by `pip install -e .` inside the runtime Docker stage (issue #4 surfaced this). PKG-INFO embeds README.md / README.zh-CN.md verbatim, which are themselves whole-file engine-excepted (fork-notice block, attribution badges, and the upstream docs links — README docs links intentionally stay on hermes-agent.nousresearch.com/docs as MIT attribution; patch 0014 rebrands only command examples + config paths, NOT URLs). The egg-info is regenerated on every install and is never tracked in source. Excluding it here keeps `argo doctor --static` exit-zero clean for runtime users."
```

`README.md` exception (`:77`):
```diff
-    why: "Fork-notice block, attribution badges, and docs links intentionally reference upstream (NousResearch/hermes-agent, hermes-agent.nousresearch.com). MIT license requires attribution and there is no Nadicode-hosted docs site."
+    why: "Whole-file engine exception. Attribution (fork-notice block, License + Fork-of badges, the NousResearch/hermes-agent repo slug) AND the docs links (hermes-agent.nousresearch.com/docs/...) intentionally reference upstream — MIT license requires attribution and the README is part of that attribution surface. Patch 0014 rebrands ONLY the copy-paste command examples (`hermes`->`argo`) and config paths (~/.hermes->~/.argo); it deliberately leaves the docs URLs upstream (see patch 0014 header + tests/test_readme_commands_rebranded.py). The /docs rename mapping does NOT reach this file (exception short-circuits)."
```

`CONTRIBUTING.md` exception (`:81`):
```diff
-    why: "Points contributors at upstream docs site (hermes-agent.nousresearch.com) which is where the documentation actually lives."
+    why: "Whole-file engine exception. The docs links (hermes-agent.nousresearch.com/docs) and the bare-host 'Documentation site' note stay on the upstream host — the /docs rename mapping does NOT reach this file (exception short-circuits). The upstream clone URL (NousResearch/hermes-agent.git), Issues links, and discord.gg/NousResearch stay upstream per MIT attribution."
```

`argo-already-has-routines.md` exception (`:85`):
```diff
-    why: "Planning/comparison document that references upstream docs URLs for context."
+    why: "Whole-file engine exception. Planning/comparison document referencing the upstream docs URL (hermes-agent.nousresearch.com/docs/guides/automation-templates) for context; the /docs rename mapping does NOT reach this file (exception short-circuits), so the link stays on the upstream host — intentional, not a deploy surface."
```

`skip_contexts` header comment (`:95-103`):
```diff
 skip_contexts:
   # Preserve every URL whose host/path is NOT something nadicode controls.
   # We only rewrite GitHub URLs for the upstream hermes-agent repo (handled by
-  # the NousResearch/hermes-agent → nadicodeai/argo mapping above) and
-  # the hermes-agent.local devhost. Everything else — hermes-agent.nousresearch.com
-  # (real upstream docs site, owned by NousResearch), pypi.org/p/hermes-agent
-  # (real upstream PyPI package), img.shields.io/badge/Docs-hermes (badge label
-  # that should mirror upstream), and NousResearch/hermes-example-plugins
-  # (no nadicode fork exists) — is preserved as-is.
+  # the NousResearch/hermes-agent → nadicodeai/argo mapping above), the
+  # hermes-agent.local devhost, AND the self-referential DOCS path
+  # hermes-agent.nousresearch.com/docs (rewritten to docs.nadicode.ai/argo by the
+  # docs mapping above — the fork now hosts its own docs site, so that path is
+  # RELEASED from preservation via the third lookahead alternative below).
+  # Everything else is preserved as-is: the BARE host
+  # hermes-agent.nousresearch.com (the OpenRouter HTTP-Referer attribution header)
+  # and its /install.sh + /llms.txt paths, pypi.org/p/hermes-agent (real upstream
+  # PyPI package), img.shields.io/badge/Docs-hermes (badge label that mirrors
+  # upstream), and NousResearch/hermes-example-plugins (no nadicode fork exists).
```

> The exception **entries themselves stay** — only their `why` prose changes. Do NOT delete any exception.

### 2.2 `packaging-strip.yaml` (Component A — config env-override + sidebar fix; generators dropped)

Append four `content_edits` at the end of the `content_edits:` list (after `setup-menu-hide-china-platforms`). Anchors match the **pre-rename** upstream text (`content_edits` runs before rebrand — `tools/build.py:519` before `:520`). A stale anchor fails `make build` loudly (`tools/build.py:373-380`) — the desired loud-on-drift contract.

```yaml
  # ---- Docs-site host/baseUrl + navbar Home (docs.nadicode.ai/argo) ----
  # The rebrand pass does NOT rewrite url/baseUrl/Home-href (bare-host or a
  # standalone /docs/ baseUrl token, preserved by argo-rename.yaml's URL guard).
  # These content_edits flip them. SITE_BASE / the llms.txt headers / prebuild
  # UNIFIED_INDEX_URL / acp_registry website are NOT handled here — they are
  # /docs-path URLs flipped by the argo-rename.yaml docs mapping instead.
  - name: docs-url-env-overridable
    file: website/docusaurus.config.ts
    why: >-
      Make the published docs host/baseUrl injectable at build time so CI can
      target docs.nadicode.ai + /argo/ while the upstream literal stays the
      default (preserved by argo-rename.yaml skip_contexts -> leakage-safe). The
      rebrand pass does NOT rewrite url/baseUrl. Anchor matches the exact
      upstream pre-rename two-line block (both lines indented 2 spaces).
    find: |2
        url: 'https://hermes-agent.nousresearch.com',
        baseUrl: '/docs/',
    replace: |2
        url: process.env.DOCS_URL ?? 'https://hermes-agent.nousresearch.com',
        baseUrl: process.env.DOCS_BASE_URL ?? '/docs/',
  - name: docs-organization-name-argo
    file: website/docusaurus.config.ts
    why: >-
      organizationName is a gh-pages-deploy-only field the rebrand leaves as
      'NousResearch' (projectName is already flipped to argo-agent). Build-inert
      for Vercel, corrected for consistency. Anchor is the exact pre-rename line.
    find: "organizationName: 'NousResearch',"
    replace: "organizationName: 'nadicodeai',"
  - name: docs-navbar-home-link
    file: website/docusaurus.config.ts
    why: >-
      The navbar "Home" href is a BARE host (no /docs path) so the docs mapping
      in argo-rename.yaml does NOT touch it, and the rebrand preserves it. It is
      a self-referential brand surface (the docs site's own Home), not MIT
      attribution, so it points at the Argo docs site. Anchor is the exact
      pre-rename href line (10 leading spaces); the footer copyright + "Nous
      Research" link use a different host (nousresearch.com) and stay upstream.
    find: "          href: 'https://hermes-agent.nousresearch.com',"
    replace: "          href: 'https://docs.nadicode.ai/argo',"
  # ---- Remove the "Chinese platforms" sidebar category (matches china-docs strip) ----
  - name: sidebars-drop-chinese-platforms
    file: website/sidebars.ts
    why: >-
      The china-docs strip above deletes website/docs/user-guide/messaging/
      {dingtalk,feishu,wecom,wecom-callback,weixin,qqbot,yuanbao}.md, but
      sidebars.ts still references those 7 doc IDs in a "Chinese platforms"
      category. Docusaurus validates sidebar doc IDs strictly (NOT governed by
      onBrokenLinks:'warn'), so `npm run build` fails with "Invalid sidebar
      file … these sidebar document ids do not exist". Remove the whole category
      block. Anchor is the exact upstream block (sidebars.ts is rename-invariant
      here — no hermes tokens inside). Verified: removing this block makes
      `npm run build` exit 0 for both en and zh-Hans.
    find: |2
            {
              type: 'category',
              label: 'Chinese platforms',
              items: [
                'user-guide/messaging/dingtalk',
                'user-guide/messaging/feishu',
                'user-guide/messaging/wecom',
                'user-guide/messaging/wecom-callback',
                'user-guide/messaging/weixin',
                'user-guide/messaging/qqbot',
                'user-guide/messaging/yuanbao',
              ],
            },
    replace: ""
```

> **Indentation is load-bearing.** The `url`/`baseUrl` block uses YAML block scalar `|2` (keep-trailing) so the two emitted lines are exactly `  url: '...'` and `  baseUrl: '...'` — **both indented 2 spaces** (verified via `cat -A` on `upstream/website/docusaurus.config.ts:10-11`; the prior plan's `|2-` with a 0-indent `baseUrl` line FAILED `make build` with a stale-anchor error). The Home-href anchor carries its **10 leading spaces** (`:126`). The sidebars block uses the exact upstream indentation from `upstream/website/sidebars.ts:642-654` (category nested under `items:` — 8-space `{`, 10-space fields). If `make build` reports a stale anchor, re-copy the exact bytes via `cat -A`.

**Optional cleanup (warn-level, non-blocking):** `dist/argo/website/docs/user-guide/messaging/index.md:566-573` still link to the stripped pages (`[DingTalk Setup](dingtalk.md)` … `[Yuanbao Setup](yuanbao.md)`). With `onBrokenLinks: 'warn'` these ship as dead links but do NOT fail the build. RECOMMENDED follow-up `content_edit` to drop those 7 list lines (or accept the warnings). Not a blocker; see OD-4.

**Not edited (already correct in dist, verified):** `editUrl` (`:76` → `nadicodeai/argo` via mapping), `themeConfig.image` (→ `img/argo-agent-banner.png`, asset present after a clean `make build`), `projectName` (`:14` → `argo-agent`). `trailingSlash` stays absent (Docusaurus default is correct for Vercel static hosting). Footer copyright + "Nous Research" link (`:167,:171`) and Discord (`:136,:157`) stay upstream (attribution / different host). `locales: ['en','zh-Hans']` (`:25-27`) — see OD-5.

### 2.3 `.github/workflows/deploy-docs.yml` (Component B — new file on `main`)

```yaml
# argo — docs-site deploy to docs.nadicode.ai/argo/ (mirrors upstream deploy-site.yml).
#
# LIVES ON main (NOT release/storefront): tools/release_branch_push.py
# ::_strip_release_workflows() deletes .github/workflows/ from the storefront
# tree because GITHUB_TOKEN lacks the `workflow` scope. A workflow on `release`
# is silently dropped on the next release push and never runs. (.github/workflows
# lives at the repo root on main, NOT inside dist/argo/, so the strip never sees
# this file — verified release_branch_push.py:220-276.)
#
# BUILDS FROM dist/argo/website (NOT upstream/website): the Argo-branded docs
# prose only exists AFTER the hermes->argo rename, under dist/argo/website/,
# produced by `make build`. dist/argo/ is gitignored on main, so this job MUST
# run `make build` first, then build Docusaurus from the renamed tree.
#
# DEPLOY MODEL: Actions builds the renamed static site and pushes the PREBUILT
# output INTO the already-provisioned Vercel project via the Vercel CLI
# (`vercel deploy --prebuilt --prod`). Vercel never builds anything, so it cannot
# pick up the wrong (un-renamed) source. The provisioned project's git auto-build
# MUST be disabled (one-time human step — see §4).

name: deploy-docs

on:
  release:
    types: [published]
  push:
    branches: [main]
    paths:
      - 'upstream/website/**'
      - 'upstream/skills/**'
      - 'upstream/optional-skills/**'
      - 'upstream/scripts/build_skills_index.py'
      - 'patches/**'
      - 'overlay/**'
      - 'tools/**'
      - 'argo-rename.yaml'
      - 'packaging-strip.yaml'
      - '.github/workflows/deploy-docs.yml'
      - '.github/actions/argo-setup/**'
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: deploy-docs
  cancel-in-progress: false

jobs:
  deploy-docs:
    name: build (renamed) + deploy to Vercel
    if: github.repository == 'nadicodeai/argo'
    runs-on: ubuntu-latest
    env:
      DOCS_URL: https://docs.nadicode.ai
      DOCS_BASE_URL: /argo/
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd  # v6.0.2
        with:
          fetch-depth: 0

      - name: Install fork toolchain (uv + Python + quilt/zstd + pip deps)
        uses: ./.github/actions/argo-setup
        with:
          with-uv: "true"
          python-version: "3.13"
          apt-packages: "quilt zstd"
          pip-packages: "pyyaml httpx"

      # 1) RENAME FIRST — produce dist/argo/ (gitignored on main; absent in a
      #    fresh checkout). Without this, dist/argo/website is missing.
      - name: Build renamed dist (make build)
        run: |
          . .venv/bin/activate
          make build

      # 2) SAFETY GATE — same hermes-leak scan release.yml uses. nadicode URLs
      #    are invisible to it; an un-rebranded `hermes` leak fails the deploy.
      - name: Leakage gate (static)
        run: |
          . .venv/bin/activate
          make leakage-static

      # 3) Node — AFTER make build so cache-dependency-path resolves to the
      #    now-generated lockfile. argo-setup installs NO Node (verified).
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020  # v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: dist/argo/website/package-lock.json

      # 4) SKILLS PIPELINE — same scripts + ordering as upstream deploy-site.yml,
      #    against the RENAMED dist tree. build_skills_index lives at dist repo
      #    root (dist/argo/scripts/); extract + generate live under
      #    dist/argo/website/scripts/. prebuild.mjs re-runs extract + llms.txt but
      #    NOT generate-skill-docs, so it is invoked explicitly here.
      - name: Build skills index (non-fatal — falls back to on-disk cache)
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python3 scripts/build_skills_index.py || echo "Skills index build failed (non-fatal)"
        working-directory: dist/argo

      - name: Extract skill metadata for dashboard
        run: python3 website/scripts/extract-skills.py
        working-directory: dist/argo

      - name: Regenerate per-skill docs pages + catalogs
        run: python3 website/scripts/generate-skill-docs.py
        working-directory: dist/argo

      # 5) DOCUSAURUS BUILD from the renamed tree. `npm run build` runs the
      #    `prebuild` hook (extract-skills + generate-llms-txt) then docusaurus
      #    build. url/baseUrl come from DOCS_URL/DOCS_BASE_URL (Component A reads).
      - name: Install website deps
        run: npm ci
        working-directory: dist/argo/website

      - name: Build Docusaurus (renamed)
        run: npm run build
        working-directory: dist/argo/website

      # 6) DEPLOY prebuilt static output INTO the provisioned Vercel project,
      #    wrapped in Build Output API v3 so Vercel performs ZERO build.
      - name: Install Vercel CLI
        run: npm i --global vercel@latest

      - name: Deploy prebuilt site to Vercel (production)
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}
        run: |
          set -euo pipefail
          DEPLOY_ROOT="$(mktemp -d)"
          mkdir -p "$DEPLOY_ROOT/.vercel/output/static"
          cp -r dist/argo/website/build/* "$DEPLOY_ROOT/.vercel/output/static/"
          printf '{"version":3}\n' > "$DEPLOY_ROOT/.vercel/output/config.json"
          cd "$DEPLOY_ROOT"
          # `vercel pull` writes .vercel/project.json (NOT .vercel/output/), so it
          # must run AFTER the output staging above (ordering is load-bearing).
          vercel pull --yes --environment=production --token "$VERCEL_TOKEN"
          vercel deploy --prebuilt --prod --token "$VERCEL_TOKEN"
```

> **Verified:** `.github/actions/argo-setup/action.yml` exposes inputs `with-uv`, `python-version`, `apt-packages`, `pip-packages` (`:21-31`) and installs NO Node (`setup-node` is added separately). Pinned SHAs reuse the exact ones vetted in `upstream/.github/workflows/deploy-site.yml`. `build_skills_index.py` lives at `dist/argo/scripts/`; `extract-skills.py`/`generate-skill-docs.py` at `dist/argo/website/scripts/` (verified). `release.published` is a real firing trigger — `tools/argo_release.py` runs `gh release create` with no `--draft`; same trigger already in production in `docker-publish.yml`.

### 2.4 `upstream/tests/acp/test_registry_manifest.py` (dist-test BLOCKER fix — REQUIRED)

The ACP registry `website` is the agent's own docs page — a self-referential link the fork now hosts at the live Argo docs site. Update the assertion to the rebranded host:

```diff
-    assert data["website"].startswith("https://hermes-agent.nousresearch.com/")
+    assert data["website"].startswith("https://docs.nadicode.ai/argo/")
```

> The manifest `dist/argo/acp_registry/agent.json:7` `website` is flipped to `https://docs.nadicode.ai/argo/user-guide/features/acp` by Component C's mapping (verified: `/docs` URL, not engine-excepted, released by the amended lookahead). This is the ONLY dist test that asserts a bare-host `/docs`-derived value; all others stay green (audited in §0.1). Edit `upstream/...` — `dist/argo/tests/...` is regenerated by `make build`.

### 2.5 (Optional) `tests/test_full_rename_config.py` — coverage for the new mapping

Engine-excepted (`argo-rename.yaml:70-71`); stays green unchanged (new key isn't in its required-key set; mapping count still ≥15). **Recommended** addition: assert `"hermes-agent.nousresearch.com/docs"` → `"docs.nadicode.ai/argo"` exists and that the bare host / `pypi.org/p/hermes-agent` / shields-badge remain preserved. Read the file before editing to match its assertion style.

---

## 3. Gate / verification command sequence (exact, with expected green result)

Run from repo root. All MUST pass before merge (dist-test-gate + pre-commit-build-gate memories).

### 3.1 Regenerate rename defaults (also inside `make build`)
```bash
python3 tools/generate_rename_defaults.py        # writes overlay/hermes_cli/_rename_defaults.py
```

### 3.2 Build + verify the URLs/strips landed
```bash
make build        # EXPECT: exit 0. Stale anchor would fail loudly here.

# url/baseUrl env-override + Home flipped:
grep -n "DOCS_URL\|DOCS_BASE_URL\|docs.nadicode.ai/argo" dist/argo/website/docusaurus.config.ts
# generate-llms-txt fully flipped (EXPECT ZERO hits — all 5 /docs literals gone, :12,13,34,251,252):
grep -n "hermes-agent.nousresearch.com" dist/argo/website/scripts/generate-llms-txt.py   # EXPECT: (no output)
# prebuild UNIFIED_INDEX_URL flipped:
grep -n "UNIFIED_INDEX_URL\|docs.nadicode.ai/argo" dist/argo/website/scripts/prebuild.mjs
# ACP manifest flipped:
grep -n "website" dist/argo/acp_registry/agent.json                                      # EXPECT: docs.nadicode.ai/argo
# Chinese-platforms category gone from sidebar:
grep -n "Chinese platforms" dist/argo/website/sidebars.ts                                 # EXPECT: (no output)
# Attribution MUST SURVIVE upstream:
grep -n "nousresearch.com\|Based on Hermes\|NousResearch/hermes-agent" dist/argo/website/docusaurus.config.ts
```

### 3.3 Leakage gate (hermes-only; stays green)
```bash
make leakage-static     # == python tools/verify_no_leakage.py dist/argo/  (Makefile:81-82)
```
EXPECT: `no leakage detected`, exit 0. The scanner only flags lines containing `hermes` (`tools/verify_no_leakage.py:129` — `if "hermes" not in line.lower()`); the new `docs.nadicode.ai/argo` URLs are invisible to it. This change **removes** `hermes-agent.nousresearch.com/docs` occurrences → strictly leakage-reducing. (The brief's parenthetical "may fail if new nadicode URLs appear" is FALSE — there is no nadicode/forbidden-URL rule.)

### 3.4 Dist-test (REQUIRED gate for this dist-affecting change)
```bash
make dist-test                                                          # full suite (heavy)
# fast iteration alternatives:
make dist-test DIST_TEST_ARGS="--slice 1/6"
make dist-test DIST_TEST_ARGS="--paths tests/acp/test_registry_manifest.py"   # confirm the §2.4 fix is green
```
EXPECT: all pass. `dist-test` runs `scripts/run_tests_parallel.py` (pytest only — `Makefile:184-188`); it does NOT run `npm run build`, so the docusaurus/sidebar break is invisible to it (hence §3.5 is mandatory). The `test_registry_manifest.py` fix (§2.4) is what keeps `tests/acp/` green.

### 3.5 Local Docusaurus smoke build (the ONLY check that validates published URLs + sidebar + strips)
```bash
cd dist/argo/website
npm ci
python3 scripts/build_skills_index.py || echo "skills-index crawl non-fatal"
python3 scripts/generate-skill-docs.py
DOCS_URL="https://docs.nadicode.ai" DOCS_BASE_URL="/argo/" npm run build
# EXPECT: build/ produced for both en and zh-Hans, exit 0 (sidebar fix is what unblocks this).
grep -rl "docs.nadicode.ai/argo" build/sitemap.xml build/index.html | head
grep -o 'og:image[^>]*docs.nadicode.ai/argo[^"]*' build/index.html | head   # og:image absolute = url+baseUrl+image
grep -c "docs.nadicode.ai/argo" build/llms.txt                              # per-page links via SITE_BASE
grep -c "hermes" build/index.html                                          # EXPECT: 0 (or attribution-only)
```
EXPECT: `build/` produced, sitemap `<loc>` and og:image rooted at `https://docs.nadicode.ai/argo`, `llms.txt` links at `docs.nadicode.ai/argo`. `onBrokenLinks: 'warn'` means broken internal links (e.g. the messaging `index.md` cross-links to stripped pages) warn but don't fail — eyeball the log.

### 3.6 Pre-commit (fires automatically on the `argo-rename.yaml`/`overlay/` commit)
```bash
make install-hooks      # once per clone, if not already
git commit ...          # hook re-runs make build + make leakage-static
```

---

## 4. Required secrets + manual Vercel-dashboard steps

**Repo secrets** (GitHub → Settings → Secrets → Actions, or `gh secret set <NAME> --repo nadicodeai/argo`). Verified `gh secret list --repo nadicodeai/argo` is **empty** — all three Vercel secrets MUST be added before the first deploy.

| Secret | Required | Source | Used by |
|---|---|---|---|
| `VERCEL_TOKEN` | **Yes** | Vercel → Account Settings → Tokens → Create (scope to the team owning the provisioned project) | `vercel pull` / `vercel deploy` auth |
| `VERCEL_ORG_ID` | **Yes** | `.vercel/project.json` (`orgId`) after a one-time local `vercel link`, or Vercel → Team Settings → Team ID | targets the existing project |
| `VERCEL_PROJECT_ID` | **Yes** | `.vercel/project.json` (`projectId`) after `vercel link`, or Vercel → Project → Settings → Project ID | targets the existing project |
| `GITHUB_TOKEN` | No (auto) | GitHub-provided (read scope sufficient for the non-fatal crawl) | `build_skills_index.py` |

**Not needed** (vs. upstream): `VERCEL_DEPLOY_HOOK` (we push prebuilt, not a Vercel-side git build) and `pages: write`/`id-token: write` (no GitHub Pages).

**Manual Vercel-dashboard steps (one-time, human):**
1. **Disable the provisioned project's Git auto-build** (Project → Settings → Git → disconnect/pause). If it stays connected, Vercel builds `upstream/website/` (a fresh clone has no `dist/argo/`) and publishes **un-renamed "hermes" docs** alongside the correct prebuilt deploy — the single most likely way to leak hermes content despite a correct workflow. **Invisible to every repo gate.** This is a release-checklist blocker for the human operator.
2. **Confirm the custom domain + base-path mapping:** the project must serve `docs.nadicode.ai` and the static bundle under the `/argo/` path. Docusaurus bakes `baseUrl: '/argo/'` into the HTML (the site self-references `/argo/...`), so the project must route the bundle under `/argo/` — if it serves at root, every asset 404s. Verify the domain config + any path/rewrite.
3. The workflow **file** is pushed to `main` by a normal maintainer push (carries `workflow` scope); `GITHUB_TOKEN` never pushes it. No scope problem once on `main`.

---

## 5. Open Decisions

- **OD-1 — path-baseUrl (`/argo/`) vs subdomain.** This plan implements **path-baseUrl** (`docs.nadicode.ai` + `baseUrl: /argo/`), per the target. If the team later prefers a dedicated subdomain (e.g. `argo-docs.nadicode.ai` at root), flip `DOCS_BASE_URL=/` and adjust the Vercel domain — the env-override mechanism (§2.2) makes this a one-line change. **Decision needed before first deploy:** confirm `/argo/` path-routing is configured on the Vercel project (§4 step 2).
- **OD-2 — first-deploy chicken-and-egg on `UNIFIED_INDEX_URL` / `/docs/api/*.json`.** Component C points `prebuild.mjs`'s fetch (and `skills-index.json`/`model-catalog.json` consumers) at `docs.nadicode.ai/argo/api/...`, which 404s on the very first build before the site exists. **Non-fatal** (falls back to on-disk copy, `prebuild.mjs:84-118`), but the first Skills Hub may be sparse. **Decide:** accept a sparse first deploy + one `workflow_dispatch` re-run after first publish, OR confirm the Docusaurus `static/api/*.json` files publish under `/argo/api/` (else runtime fetches 404 permanently).
- **OD-3 — README/CONTRIBUTING docs-host fast-follow.** The published site + agent prompt + CLI cite `docs.nadicode.ai/argo`, but `README.md`/`README.zh-CN.md`/`CONTRIBUTING.md` (whole-file-excepted, patch-0014-owned) still cite `hermes-agent.nousresearch.com/docs`. **Decide:** keep them on the upstream docs host as attribution (current behavior, defensible), OR a follow-up patch (0014 amendment / new 0016) repoints the README docs URLs to `docs.nadicode.ai/argo` — which would require re-scoping `tests/test_readme_commands_rebranded.py:55` (`assert "hermes-agent.nousresearch.com" in text`) to assert the genuine attribution URLs (`NousResearch/hermes-agent`, badges) while permitting `docs.nadicode.ai`. **Out of scope for this PR.**
- **OD-4 — messaging `index.md` dead cross-links.** `dist/argo/website/docs/user-guide/messaging/index.md:566-573` link to the 7 stripped China pages (`onBrokenLinks: 'warn'` → ship as dead links, build still passes). **Decide:** add a `content_edit` to drop those 7 list lines now, OR accept the warnings and clean in a follow-up. RECOMMENDED: clean now (same change-set as the sidebar strip).
- **OD-5 — `zh-Hans` locale builds with English-fallback content.** `docusaurus.config.ts:25-27` keeps `locales: ['en','zh-Hans']` while `i18n/zh-Hans` is stripped (verified absent in dist). `npm run build` emits a `build/zh-Hans/` tree that falls back to English source — wasted build time + a half-broken localized site under `/argo/zh-Hans/`. **Decide:** drop `'zh-Hans'` from `locales` via a `content_edit`, OR build only `en` (`docusaurus build --locale en` in the workflow). Not a blocker (build succeeds); recommend dropping the locale for a clean product.

---

## 6. Risks & Rollback

### Risks
1. **Vercel git auto-build trap (HIGHEST, invisible to all gates).** A still-connected Vercel git integration builds `upstream/website/` → publishes hermes docs alongside the correct deploy. **Mitigation:** disable git auto-build (§4 step 1). No repo gate catches it.
2. **`sidebars.ts` / docusaurus build break — FIXED in §2.2.** Without the sidebar strip, `npm run build` fails on stripped China doc IDs. Invisible to `make build`/`leakage`/`dist-test`. The §3.5 smoke build is the only repo-side check that exercises it; the workflow's `npm run build` step is the deploy-side check. **Mitigation:** the §2.2 `sidebars-drop-chinese-platforms` content_edit + the §3.5 smoke build are both mandatory.
3. **`make dist-test` failure — FIXED in §2.4.** ACP registry manifest test. **Mitigation:** the §2.4 assertion update + run `make dist-test` (not assume).
4. **First-deploy 404 on `UNIFIED_INDEX_URL` (OD-2).** Non-fatal; falls back to on-disk copy. One `workflow_dispatch` re-run after first publish repopulates.
5. **Stale `content_edits` anchor on upstream sync.** If `make sync` rewrites the `url`/`baseUrl` block, the Home href, or the China sidebar block, the matching rule fails `make build` loudly (`tools/build.py:373-380`) — by design. Re-anchor against the new upstream text. The `argo-rename.yaml` `/docs` mapping is more sync-robust (substring, not line-anchored).
6. **Leakage gate gives no correctness protection.** Hermes-only; won't warn if `DOCS_URL`/`DOCS_BASE_URL` aren't injected (site silently ships upstream defaults), the baseUrl is wrong, or a link breaks. **Mitigation:** the §3.5 smoke build with grep assertions on `sitemap.xml`/`index.html`/`llms.txt` is the real check; the workflow always sets both env vars.
7. **Component A is a hard prerequisite for B.** If the workflow runs before the env-override lands, the site self-reports the upstream host/baseUrl (wrong canonical URLs, broken `/argo/` asset paths). Both ship in this one PR — land them together; don't enable a production deploy until `make build` shows the env-override in `dist/argo/website/docusaurus.config.ts`.
8. **`onBrokenLinks: 'warn'`** — a bad rebrand link (or the messaging index dead links, OD-4) ships silently. **Mitigation/follow-up:** a non-deploy CI `npm run build` check against `dist/argo/website` (mirroring upstream `docs-site-checks`) to catch future dangling links.
9. **Pre-existing preserved leak (out of scope).** `dist/argo/website/docs/user-guide/features/skills.md:27` keeps `curl …hermes-agent.nousresearch.com/install.sh` (bare-host `/install.sh`, correctly preserved by the lookahead, leakage-gate-clean). The published docs tell users to curl upstream's installer. Flag as a separate pre-existing issue, not a blocker here.

### Rollback
- **Pre-merge:** `git switch main && git branch -D docs-nadicode-publish`. Nothing reaches `main`, no deploy fires.
- **Post-merge, config/rename only (no deploy yet):** revert the merge commit. `make build` regenerates `dist/argo/` from the reverted source; `make leakage-static` + `make dist-test` confirm green. No Vercel state to undo (secrets not yet added / auto-build still disabled).
- **Post-deploy (bad site live):** the deploy is a prebuilt static upload → rollback is a **Vercel-side promote-previous-deployment** (Dashboard → Deployments → promote last-good production), independent of git. Then revert the offending commit on `main` and re-deploy via `workflow_dispatch`. Because Vercel git auto-build is disabled, no un-renamed source can sneak back in during rollback.
- **Secret rotation:** if a `VERCEL_*` secret is compromised, rotate the token in Vercel and `gh secret set VERCEL_TOKEN` again; `ORG_ID`/`PROJECT_ID` are non-secret identifiers.

---

## 7. Why each invariant stays green

- **Leakage (`make leakage-static`):** the scanner only flags lines containing `hermes` (`tools/verify_no_leakage.py:129`); `docs.nadicode.ai/argo` contains no `hermes`, and the change **removes** `hermes-agent.nousresearch.com/docs` occurrences → strictly leakage-reducing. Every surviving bare-host `hermes` (HTTP-Referer, `/install.sh`, `/llms.txt`, excepted READMEs, homebrew formula) remains `skip_contexts`-covered.
- **Attribution:** the amended lookahead releases ONLY `hermes-agent.nousresearch.com/docs`. Empirically preserved: bare-host HTTP-Referer, `/install.sh`, `/llms.txt`, `github.com/NousResearch/hermes-agent`, `pypi.org/p/hermes-agent`, the shields Docs badge, footer copyright + "Nous Research" link + Discord, the "Based on Hermes Agent by Nous Research" credit (`argo-rename.yaml:160`), all Nous model-ids, and the whole-file-excepted READMEs/CONTRIBUTING docs links. Only the agent's OWN `/docs` self-references move.
- **Release-branch:** the workflow lives at the repo root on `main` (NOT inside `dist/argo/`), so `_strip_release_workflows()` (`tools/release_branch_push.py:220-276`, which operates only on the dist-derived scratch tree) never sees it. Triggers on `release.published` (verified-firing, same as `docker-publish.yml`) + `push.main` + `workflow_dispatch`. Least-privilege `permissions: contents: read`; no GitHub-write scope needed for a prebuilt Vercel push.
- **Dist-test:** the one test that would break (`test_registry_manifest.py`) is fixed in §2.4; the audit (§0.1) confirms it's the only bare-host `/docs`-derived assertion (others self-heal or are bare-host-preserved). `make dist-test` MUST be run, not assumed — pre-commit fires build+leakage but CI `dist-argo-tests` is non-blocking and a direct push to `main` bypasses it.

---

### Files changed by this plan (absolute paths)
- `/home/vadim/Code/argo/argo-rename.yaml` — Component C (mapping + lookahead + truthful comments)
- `/home/vadim/Code/argo/packaging-strip.yaml` — Component A (3 docusaurus `content_edits` + sidebars China-strip; generator edits dropped)
- `/home/vadim/Code/argo/overlay/hermes_cli/_rename_defaults.py` — regenerated by `make build` (do not hand-edit; commit the regenerated diff)
- `/home/vadim/Code/argo/.github/workflows/deploy-docs.yml` — Component B (new, on `main`)
- `/home/vadim/Code/argo/upstream/tests/acp/test_registry_manifest.py` — dist-test fix (assert rebranded host)
- `/home/vadim/Code/argo/tests/test_full_rename_config.py` — optional coverage for the new mapping

**Untouched on purpose (attribution / must-not-flip):** root `README.md` "Upstream docs" line, `dist/argo/README*.md` + `CONTRIBUTING.md` + `argo-already-has-routines.md` docs links (whole-file-excepted, patch-0014-owned), the docusaurus footer copyright + "Nous Research" link + Discord, `pypi.org/p/hermes-agent`, the shields.io Docs badge label, the "Based on Hermes Agent by Nous Research" credit (`argo-rename.yaml:160`), all Nous model-ids, the HTTP-Referer bare-host header, `/install.sh` and `/llms.txt` bare-host paths, and patch 0014/0015.
