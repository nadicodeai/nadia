---
sidebar_position: 17
title: "Extending the Dashboard"
description: "Build plugins for the Nadia web dashboard — custom tabs, shell slots, page-scoped slots, and backend API routes"
---

# Extending the Dashboard

The Nadia web dashboard (`nadia dashboard`) is built to be extended without forking the codebase. Two plugin layers are exposed:

1. **UI plugins** — a directory with `manifest.json` + a JavaScript bundle that registers a tab, replaces a built-in page, augments one via page-scoped slots, or injects components into named shell slots.
2. **Backend plugins** — a Python file inside that plugin directory that exposes a FastAPI `router`; routes are mounted under `/api/plugins/<name>/` and called from the plugin's UI.

Both are **drop-in at runtime**: no repo clone, no `npm run build`, no patching the dashboard source. This page is the canonical reference for dashboard plugins.

If you just want to use the dashboard, see [Web Dashboard](./web-dashboard). If you want to reskin the terminal CLI (not the web dashboard), see [Skins & Themes](./skins) — the CLI skin system is unrelated to the web dashboard.

:::note Dashboard appearance
Nadia ships one NadicodeAI web dashboard skin with light, dark, and system modes. Runtime YAML dashboard themes and the old dashboard theme API were removed with the NadicodeAI design-system migration.
:::

---

## Table of contents

- [Dashboard appearance](#dashboard-appearance)
- [Plugins](#plugins)
  - [Quick start — your first plugin](#quick-start--your-first-plugin)
  - [Directory layout](#directory-layout)
  - [Manifest reference](#manifest-reference)
  - [The Plugin SDK](#the-plugin-sdk)
  - [Shell slots](#shell-slots)
  - [Replacing built-in pages (`tab.override`)](#replacing-built-in-pages-taboverride)
  - [Augmenting built-in pages (page-scoped slots)](#augmenting-built-in-pages-page-scoped-slots)
  - [Slot-only plugins (`tab.hidden`)](#slot-only-plugins-tabhidden)
  - [Backend API routes](#backend-api-routes)
  - [Custom CSS per plugin](#custom-css-per-plugin)
  - [Plugin discovery & reload](#plugin-discovery--reload)
- [API reference](#api-reference)
- [Troubleshooting](#troubleshooting)

---

## Dashboard appearance

The Nadia dashboard now uses the NadicodeAI design system directly. Runtime YAML dashboard themes and the dashboard theme picker have been retired. Light, dark, and system mode are handled client-side by the shared NadicodeAI UI theme-mode contract.

Use plugins to extend dashboard behavior, pages, slots, and backend routes. Use the CLI skin system only for terminal appearance; it does not reskin the web dashboard.

## Plugins

A dashboard plugin is a directory with a `manifest.json`, a pre-built JS bundle, and optionally a CSS file and a Python file with FastAPI routes. Plugins live next to other Nadia plugins in `~/.nadia/plugins/<name>/` — the dashboard extension is a `dashboard/` subfolder inside that plugin directory, so one plugin can extend both the CLI/gateway and the dashboard from a single install.

Plugins don't bundle React or UI components. They use the **Plugin SDK** exposed on `window.__NADIA_PLUGIN_SDK__`. This keeps plugin bundles tiny (typically a few KB) and avoids version conflicts.

### Quick start — your first plugin

Create the directory structure:

```bash
mkdir -p ~/.nadia/plugins/my-plugin/dashboard/dist
```

Write the manifest:

```json
// ~/.nadia/plugins/my-plugin/dashboard/manifest.json
{
  "name": "my-plugin",
  "label": "My Plugin",
  "icon": "Sparkles",
  "version": "1.0.0",
  "tab": {
    "path": "/my-plugin",
    "position": "after:skills"
  },
  "entry": "dist/index.js"
}
```

Write the JS bundle (a plain IIFE — no build step needed):

```javascript
// ~/.nadia/plugins/my-plugin/dashboard/dist/index.js
(function () {
  "use strict";

  const SDK = window.__NADIA_PLUGIN_SDK__;
  const { React } = SDK;
  const { Card, CardHeader, CardTitle, CardContent } = SDK.components;

  function MyPage() {
    return React.createElement(Card, null,
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, null, "My Plugin"),
      ),
      React.createElement(CardContent, null,
        React.createElement("p", { className: "text-sm text-muted-foreground" },
          "Hello from my custom dashboard tab.",
        ),
      ),
    );
  }

  window.__NADIA_PLUGINS__.register("my-plugin", MyPage);
})();
```

Refresh the dashboard — your tab appears in the nav bar, after **Skills**.

:::tip Skip React.createElement
If you prefer JSX, use any bundler (esbuild, Vite, rollup) with React as an external and IIFE output. The only hard requirement is that the final file is a single JS file loadable via `<script>`. React is never bundled; it comes from `SDK.React`.
:::

### Directory layout

```
~/.nadia/plugins/my-plugin/
├── plugin.yaml              # optional — existing CLI/gateway plugin manifest
├── __init__.py              # optional — existing CLI/gateway hooks
└── dashboard/               # dashboard extension
    ├── manifest.json        # required — tab config, icon, entry point
    ├── dist/
    │   ├── index.js         # required — pre-built JS bundle (IIFE)
    │   └── style.css        # optional — custom CSS
    └── plugin_api.py        # optional — backend API routes (FastAPI)
```

A single plugin directory can carry three orthogonal extensions:

- `plugin.yaml` + `__init__.py` — CLI/gateway plugin ([see plugins page](./plugins)).
- `dashboard/manifest.json` + `dashboard/dist/index.js` — dashboard UI plugin.
- `dashboard/plugin_api.py` — dashboard backend routes.

None of them are required; include only the layers you need.

### Manifest reference

```json
{
  "name": "my-plugin",
  "label": "My Plugin",
  "description": "What this plugin does",
  "icon": "Sparkles",
  "version": "1.0.0",
  "tab": {
    "path": "/my-plugin",
    "position": "after:skills",
    "override": "/",
    "hidden": false
  },
  "slots": ["sidebar", "header-left"],
  "entry": "dist/index.js",
  "css": "dist/style.css",
  "api": "plugin_api.py"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique plugin identifier. Lowercase, hyphens ok. Used in URLs and registration. |
| `label` | Yes | Display name shown in the nav tab. |
| `description` | No | Short description (shown in dashboard admin surfaces). |
| `icon` | No | Lucide icon name. Defaults to `Puzzle`. Unknown names fall back to `Puzzle`. |
| `version` | No | Semver string. Defaults to `0.0.0`. |
| `tab.path` | Yes | URL path for the tab (e.g. `/my-plugin`). |
| `tab.position` | No | Where to insert the tab. `"end"` (default), `"after:<path>"`, or `"before:<path>"` — value after the colon is the **path segment** of the target tab (no leading slash). Examples: `"after:skills"`, `"before:config"`. |
| `tab.override` | No | Set to a built-in route path (`"/"`, `"/sessions"`, `"/config"`, ...) to **replace** that page instead of adding a new tab. See [Replacing built-in pages](#replacing-built-in-pages-taboverride). |
| `tab.hidden` | No | When true, register the component and any slots without adding a tab to the nav. Used by slot-only plugins. See [Slot-only plugins](#slot-only-plugins-tabhidden). |
| `slots` | No | Named shell slots this plugin populates. **Documentation aid only** — actual registration happens from the JS bundle via `registerSlot()`. Listing slots here makes discovery surfaces more informative. |
| `entry` | Yes | Path to the JS bundle relative to `dashboard/`. Defaults to `dist/index.js`. |
| `css` | No | Path to a CSS file to inject as a `<link>` tag. |
| `api` | No | Path to a Python file with FastAPI routes. Mounted at `/api/plugins/<name>/`. |

#### Available icons

Plugins use Lucide icon names. The dashboard maps these by name — unknown names silently fall back to `Puzzle`.

Currently mapped: `Activity`, `BarChart3`, `Clock`, `Code`, `Database`, `Eye`, `FileText`, `Globe`, `Heart`, `KeyRound`, `MessageSquare`, `Package`, `Puzzle`, `Settings`, `Shield`, `Sparkles`, `Star`, `Terminal`, `Wrench`, `Zap`.

Need a different icon? Open a PR to `web/src/App.tsx`'s `ICON_MAP` — pure additive change.

### The Plugin SDK

Everything a plugin needs is on `window.__NADIA_PLUGIN_SDK__`. Plugins should never import React directly.

```javascript
const SDK = window.__NADIA_PLUGIN_SDK__;

// React + hooks
SDK.React                    // the React instance
SDK.hooks.useState
SDK.hooks.useEffect
SDK.hooks.useCallback
SDK.hooks.useMemo
SDK.hooks.useRef
SDK.hooks.useContext
SDK.hooks.createContext

// UI components (shadcn/ui primitives)
SDK.components.Card
SDK.components.CardHeader
SDK.components.CardTitle
SDK.components.CardContent
SDK.components.Badge
SDK.components.Button
SDK.components.Input
SDK.components.Label
SDK.components.Select
SDK.components.SelectOption
SDK.components.Separator
SDK.components.Tabs
SDK.components.TabsList
SDK.components.TabsTrigger
SDK.components.PluginSlot    // render a named slot (useful for nested plugin UIs)

// Nadia API client + raw fetcher
SDK.api                      // typed client — getStatus, getSessions, getConfig, ...
SDK.fetchJSON                // raw fetch for custom endpoints (plugin-registered routes)

// Utilities
SDK.utils.cn                 // Tailwind class merger (clsx + twMerge)
SDK.utils.timeAgo            // "5m ago" from unix timestamp
SDK.utils.isoTimeAgo         // "5m ago" from ISO string

// Hooks
SDK.useI18n                  // i18n hook for multi-language plugins
```

#### Calling your plugin's backend

```javascript
SDK.fetchJSON("/api/plugins/my-plugin/data")
  .then((data) => console.log(data))
  .catch((err) => console.error("API call failed:", err));
```

`fetchJSON` injects the session auth token, surfaces errors as thrown exceptions, and parses JSON automatically.

#### Calling built-in Nadia endpoints

```javascript
// Agent status
SDK.api.getStatus().then((s) => console.log("Version:", s.version));

// Recent sessions
SDK.api.getSessions(10).then((resp) => console.log(resp.sessions.length));
```

See [Web Dashboard → REST API](./web-dashboard#rest-api) for the full list.

### Shell slots

Slots let a plugin inject components into named locations of the app shell — the header, the footer, an overlay layer, or page-specific content areas — without claiming a whole tab. Multiple plugins can populate the same slot; they render stacked in registration order.

Register from inside the plugin bundle:

```javascript
window.__NADIA_PLUGINS__.registerSlot("my-plugin", "sidebar", MySidebar);
window.__NADIA_PLUGINS__.registerSlot("my-plugin", "header-left", MyCrest);
```

#### Slot catalogue

**Shell-wide slots** (render anywhere in the app chrome):

| Slot | Location |
|------|----------|
| `backdrop` | Inside the `<Backdrop />` layer stack, above the noise layer. |
| `header-left` | Before the Nadia brand in the top bar. |
| `header-right` | Before the language and mode controls in the top bar. |
| `header-banner` | Full-width strip below the nav. |
| `sidebar` | Reserved legacy slot. The cockpit layout variant and YAML theme activation are retired. |
| `pre-main` | Above the route outlet (inside `<main>`). |
| `post-main` | Below the route outlet (inside `<main>`). |
| `footer-left` | Footer cell content (replaces default). |
| `footer-right` | Footer cell content (replaces default). |
| `overlay` | Fixed-position layer above everything else. Useful for chrome (scanlines, vignettes) `customCSS` can't achieve alone. |

**Page-scoped slots** (render only on the named built-in page — use these to inject widgets, cards, or toolbars into an existing page without overriding the whole route):

| Slot | Where it renders |
|------|------------------|
| `sessions:top` / `sessions:bottom` | Top / bottom of the `/sessions` page. |
| `analytics:top` / `analytics:bottom` | Top / bottom of the `/analytics` page. |
| `logs:top` / `logs:bottom` | Top (above filter toolbar) / bottom (below log viewer) of `/logs`. |
| `cron:top` / `cron:bottom` | Top / bottom of the `/cron` page. |
| `skills:top` / `skills:bottom` | Top / bottom of the `/skills` page. |
| `config:top` / `config:bottom` | Top / bottom of the `/config` page. |
| `env:top` / `env:bottom` | Top / bottom of the `/env` (Keys) page. |
| `docs:top` / `docs:bottom` | Top (above the iframe) / bottom of the embedded Docs page. |
| `chat:top` / `chat:bottom` | Top / bottom of `/chat` (only active when embedded chat is enabled). |

Example — add a banner card to the top of the Sessions page:

```javascript
function PinnedSessionsBanner() {
  return React.createElement(Card, null,
    React.createElement(CardContent, { className: "py-2 text-xs" },
      "Pinned note injected by my-plugin"),
  );
}

window.__NADIA_PLUGINS__.registerSlot("my-plugin", "sessions:top", PinnedSessionsBanner);
```

Combine page-scoped slots with `tab.hidden: true` if your plugin only augments existing pages and doesn't need a sidebar tab of its own.

The shell only renders `<PluginSlot name="..." />` for the slots above. Additional names are accepted by the registry for nested plugin UIs — a plugin can expose its own slots via `SDK.components.PluginSlot`.

#### Re-registration and HMR

If the same `(plugin, slot)` pair is registered twice, the later call replaces the earlier one — this matches how React HMR expects plugin re-mounts to behave.

### Replacing built-in pages (`tab.override`)

Setting `tab.override` to a built-in route path makes the plugin's component replace that page instead of adding a new tab. Useful when a plugin wants a custom home page (`/`) but wants to keep the rest of the dashboard intact.

```json
{
  "name": "my-home",
  "label": "Home",
  "tab": {
    "path": "/my-home",
    "override": "/",
    "position": "end"
  },
  "entry": "dist/index.js"
}
```

With `override` set:

- The original page component at `/` is removed from the router.
- Your plugin renders at `/` instead.
- No nav tab is added for `tab.path` (the override is the point).

Only one plugin can override a given path. If two plugins claim the same override, the first wins and the second is ignored with a dev-mode warning.

If you only need to add a card or toolbar to an existing page without taking it over, use [page-scoped slots](#augmenting-built-in-pages-page-scoped-slots) instead.

### Augmenting built-in pages (page-scoped slots)

Full replacement via `tab.override` is heavy — your plugin now owns the entire page, including any future updates we ship to it. Most of the time you just want to add a banner, card, or toolbar to an existing page. That's what **page-scoped slots** are for.

Every built-in page exposes `<page>:top` and `<page>:bottom` slots rendered at the top and bottom of its content area. Your plugin populates one by calling `registerSlot()` — the built-in page keeps working normally, and your component renders alongside it.

Available slots: `sessions:*`, `analytics:*`, `logs:*`, `cron:*`, `skills:*`, `config:*`, `env:*`, `docs:*`, `chat:*` (each with `:top` and `:bottom`). See the full catalogue in [Shell slots → Slot catalogue](#slot-catalogue).

Minimal example — pin a banner to the top of the Sessions page:

```json
// ~/.nadia/plugins/session-notes/dashboard/manifest.json
{
  "name": "session-notes",
  "label": "Session Notes",
  "tab": { "path": "/session-notes", "hidden": true },
  "slots": ["sessions:top"],
  "entry": "dist/index.js"
}
```

```javascript
// ~/.nadia/plugins/session-notes/dashboard/dist/index.js
(function () {
  const SDK = window.__NADIA_PLUGIN_SDK__;
  const { React } = SDK;
  const { Card, CardContent } = SDK.components;

  function Banner() {
    return React.createElement(Card, null,
      React.createElement(CardContent, { className: "py-2 text-xs" },
        "Remember to label important sessions before archiving."),
    );
  }

  // Placeholder for the hidden tab.
  window.__NADIA_PLUGINS__.register("session-notes", function () { return null; });

  // The real work.
  window.__NADIA_PLUGINS__.registerSlot("session-notes", "sessions:top", Banner);
})();
```

Key points:

- `tab.hidden: true` keeps the plugin out of the sidebar — it has no standalone page.
- The `slots` manifest field is documentation only. The actual binding happens in the JS bundle via `registerSlot()`.
- Multiple plugins can claim the same page-scoped slot. They render stacked in registration order.
- Zero footprint when no plugin registers: the built-in page renders exactly as before.

A reference plugin (`example-dashboard` in the `nadia-example-plugins` companion repo — wire reference: `github.com/NadicodeAI/nadia-example-plugins/tree/main/example-dashboard`) ships a live demo that injects a banner into `sessions:top` — install it to see the pattern end-to-end.

### Slot-only plugins (`tab.hidden`)

When `tab.hidden: true`, the plugin registers its component (for direct URL visits) and any slots, but never adds a tab to the navigation. Used by plugins that only exist to inject into slots — a header crest, a sidebar HUD, an overlay.

```json
{
  "name": "header-crest",
  "label": "Header Crest",
  "tab": {
    "path": "/header-crest",
    "position": "end",
    "hidden": true
  },
  "slots": ["header-left"],
  "entry": "dist/index.js"
}
```

The bundle still calls `register()` with a placeholder component (good practice in case someone hits the URL directly) and then `registerSlot()` to do the real work.

### Backend API routes

Plugins can register FastAPI routes by setting `api` in the manifest. Create the file and export a `router`:

```python
# ~/.nadia/plugins/my-plugin/dashboard/plugin_api.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/data")
async def get_data():
    return {"items": ["one", "two", "three"]}

@router.post("/action")
async def do_action(body: dict):
    return {"ok": True, "received": body}
```

Routes are mounted under `/api/plugins/<name>/`, so the above becomes:

- `GET  /api/plugins/my-plugin/data`
- `POST /api/plugins/my-plugin/action`

Plugin API routes bypass session-token authentication since the dashboard server binds to localhost by default. **Don't expose the dashboard on a public interface with `--host 0.0.0.0` if you run untrusted plugins** — their routes become reachable too.

#### Accessing Nadia internals

Backend routes run inside the dashboard process, so they can import from the nadia-agent codebase directly:

```python
from fastapi import APIRouter
from nadia_state import SessionDB
from nadia_cli.config import load_config

router = APIRouter()

@router.get("/session-count")
async def session_count():
    db = SessionDB()
    try:
        count = len(db.list_sessions(limit=9999))
        return {"count": count}
    finally:
        db.close()

@router.get("/config-snapshot")
async def config_snapshot():
    cfg = load_config()
    return {"model": cfg.get("model", {})}
```

### Custom CSS per plugin

If your plugin needs styles beyond Tailwind classes and inline `style=`, add a CSS file and reference it in the manifest:

```json
{
  "css": "dist/style.css"
}
```

The file is injected as a `<link>` tag on plugin load. Use specific class names to avoid conflicts with the dashboard's styles, and reference the dashboard's CSS vars to stay compatible with light/dark mode:

```css
/* dist/style.css */
.my-plugin-chart {
  border: 1px solid var(--color-border);
  background: var(--color-card);
  color: var(--color-card-foreground);
  padding: 1rem;
}
.my-plugin-chart:hover {
  border-color: var(--color-ring);
}
```

The dashboard exposes shadcn-compatible tokens as `--color-*` plus layout primitives such as `--radius` and `--spacing-mul`. Reference those and your plugin follows the active light/dark mode.

### Plugin discovery & reload

The dashboard scans three directories for `dashboard/manifest.json`:

| Priority | Directory | Source label |
|----------|-----------|--------------|
| 1 (wins on conflict) | `~/.nadia/plugins/<name>/dashboard/` | `user` |
| 2 | `<repo>/plugins/memory/<name>/dashboard/` | `bundled` |
| 2 | `<repo>/plugins/<name>/dashboard/` | `bundled` |
| 3 | `./.nadia/plugins/<name>/dashboard/` | `project` — only when `NADIA_ENABLE_PROJECT_PLUGINS` is set |

Discovery results are cached per dashboard process. After adding a new plugin, either:

```bash
# Force a rescan without restart
curl http://127.0.0.1:9119/api/dashboard/plugins/rescan
```

…or restart `nadia dashboard`.

#### Plugin load lifecycle

1. Dashboard loads. `main.tsx` exposes the SDK on `window.__NADIA_PLUGIN_SDK__` and the registry on `window.__NADIA_PLUGINS__`.
2. `App.tsx` calls `usePlugins()` → fetches `GET /api/dashboard/plugins`.
3. For each manifest: CSS `<link>` is injected (if declared), then a `<script>` tag loads the JS bundle.
4. The plugin's IIFE runs and calls `window.__NADIA_PLUGINS__.register(name, Component)` — and optionally `.registerSlot(name, slot, Component)` for each slot.
5. The dashboard resolves the registered component against the manifest, adds the tab to navigation (unless `hidden`), and mounts the component as a route.

Plugins have up to **2 seconds** after their script loads to call `register()`. After that the dashboard stops waiting and finishes initial render. If a plugin later registers, it still appears — the nav is reactive.

If a plugin's script fails to load (404, syntax error, exception during IIFE), the dashboard logs a warning to the browser console and continues without it.

---

## API reference

### Plugin endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/plugins` | GET | List discovered plugins (with manifests, minus internal fields). |
| `/api/dashboard/plugins/rescan` | GET | Force re-scan the plugin directories without restarting. |
| `/dashboard-plugins/<name>/<path>` | GET | Serve static assets from a plugin's `dashboard/` directory. Path traversal is blocked. |
| `/api/plugins/<name>/*` | * | Plugin-registered backend routes. |

### SDK on `window`

| Global | Type | Provider |
|--------|------|----------|
| `window.__NADIA_PLUGIN_SDK__` | object | `registry.ts` — React, hooks, UI components, API client, utils. |
| `window.__NADIA_PLUGINS__.register(name, Component)` | function | Register a plugin's main component. |
| `window.__NADIA_PLUGINS__.registerSlot(name, slot, Component)` | function | Register into a named shell slot. |

---

## Troubleshooting

**My plugin's tab doesn't show up.**
1. Check the manifest is at `~/.nadia/plugins/<name>/dashboard/manifest.json` (note the `dashboard/` subdirectory).
2. `curl http://127.0.0.1:9119/api/dashboard/plugins/rescan` to force re-discovery.
3. Open browser dev tools → Network — confirm `manifest.json`, `index.js`, and any CSS loaded without 404s.
4. Open browser dev tools → Console — look for errors during the IIFE or `window.__NADIA_PLUGINS__ is undefined` (indicates the SDK didn't initialize, usually a React render crash earlier).
5. Verify your bundle calls `window.__NADIA_PLUGINS__.register(...)` with the **same name** as `manifest.json:name`.

**Slot-registered components don't render.**
The `sidebar` slot is legacy-reserved; use page-scoped slots, header slots, footer slots, or overlays for new plugins. If you're registering into a slot with no hits, add `console.log` inside `registerSlot` to confirm the plugin bundle ran at all.

**Plugin backend routes return 404.**
1. Confirm the manifest has `"api": "plugin_api.py"` pointing to an existing file inside `dashboard/`.
2. Restart `nadia dashboard` — plugin API routes are mounted once at startup, **not** on rescan.
3. Check that `plugin_api.py` exports a module-level `router = APIRouter()`. Other export names are not picked up.
4. Tail `~/.nadia/logs/errors.log` for `Failed to load plugin <name> API routes` — import errors are logged there.

**Plugin CSS overrides do not apply.**
Plugin CSS files are loaded as normal stylesheets through the plugin manifest `css` field. Keep selectors scoped to your plugin root and prefer dashboard tokens over hard-coded colors.

**I want to ship a plugin on PyPI.**
Dashboard plugins are installed by directory layout, not by pip entry point. The cleanest distribution path today is a git repo the user clones into `~/.nadia/plugins/`. A pip-based installer for dashboard plugins is not currently wired up.
