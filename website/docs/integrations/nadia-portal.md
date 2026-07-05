---
sidebar_position: 1
title: "NadicodeAI Portal"
description: "Activation, the curated model catalog, and the Tool Gateway — the way to run Nadia Agent."
---

# NadicodeAI Portal

The [NadicodeAI Portal](https://portal.nadicode.ai) is where your identity, billing, and models live, and **the way to run Nadia Agent**. One activation replaces the juggling act of separate accounts, API keys, and billing relationships across every model lab, search API, image generator, and browser provider you'd otherwise wire up by hand.

If you only set up one thing, set up this. The fastest path:

```bash
nadia setup --portal
```

That single command runs Portal activation, lets you pick a model from the curated catalog, sets the Portal as your inference provider in `config.yaml`, and turns on the Tool Gateway. You're ready to `nadia chat` immediately after.

Don't have a subscription yet? Open [portal.nadicode.ai](https://portal.nadicode.ai), sign up, then come back and run the command above.

## Activation — how you sign in

The Portal uses a device-flow activation ceremony rather than a password prompt or a redirect through a third party. When you run `nadia setup --portal` (or `nadia portal`), Nadia:

1. Requests a short **user code** from the Portal and prints it in your terminal.
2. Opens (or tells you to open) the Portal device page at [portal.nadicode.ai/device](https://portal.nadicode.ai/device).
3. Waits while you confirm the code from any browser and **approve** the activation.
4. Stores the resulting refresh token at `~/.nadia/auth.json` and continues setup.

The activation resolves as **approved**, **denied**, **expired** (the code timed out — rerun the command for a fresh one), or **unreachable** (the Portal could not be reached — check your connection and retry). Because the code is confirmed in a browser you already trust, activation works the same on a headless host: run the command over SSH, then approve the code from your laptop.

## What the subscription covers

### The curated model catalog

The Portal proxies a **curated catalog** of agentic models: the published manifest intersected with the live Portal catalog, with the tool-support filter retained and experimental (alpha/preview) models stripped out. Entries whose live price is zero are labeled **free**. It is the only model list the picker shows — no dead entries, no models the Portal can't actually serve.

Billing is one balance: model usage is charged in credits against your NadicodeAI subscription instead of one balance per lab. Switch between a strong coding model and a long-context model with `/model` mid-session — no new credentials, no per-provider top-ups, no surprise zero-balance errors.

```bash
/model            # open the curated-catalog picker
/model <slug>     # switch directly to a catalog model mid-session
```

### The Tool Gateway

The same subscription unlocks the [Tool Gateway](/user-guide/features/tool-gateway), which routes Nadia Agent's tool calls through NadicodeAI-managed infrastructure. One activation, several backends:

| Tool | What it does |
|------|--------------|
| **Web search & extract** | Agent-grade search and full-page extraction. No separate search API key. |
| **Image generation** | Multiple image models under one endpoint. No separate image-provider account. |
| **Text-to-speech** | High-quality TTS without a separate key. Enables [voice mode](/user-guide/features/voice-mode) across messaging platforms. |
| **Cloud browser automation** | Headless browser sessions for `browser_navigate`, `browser_click`, `browser_type`, `browser_vision`. No separate browser account. |
| **Cloud terminal sandbox** | Serverless terminal sandboxes for code execution (optional add-on). |

Without the gateway, hooking each of those up means a separate account, dashboard, and top-up flow per backend. With the gateway, all of it routes through one subscription. You can also enable just specific gateway tools — see [Mixing the gateway with your own backends](#mixing-the-gateway-with-your-own-backends).

### No credentials in your dotfiles

Because everything routes through one activated Portal session, you don't accumulate a `.env` file full of long-lived API keys. The refresh token at `~/.nadia/auth.json` is the only credential on disk, and Nadia mints short-lived JWTs from it per request — see [Token handling](#token-handling).

### Cross-platform parity

[Native Windows](/user-guide/windows-native) makes per-tool API key setup its rough edge — installing a search account, an image account, a browser account, and a TTS key from Windows is the highest-friction part of getting a useful agent. Portal activation smooths that out: one activation covers the model and every gateway tool, so Windows users get the same experience as macOS/Linux without configuring backends by hand.

## Setup

### Fresh install — one command

```bash
nadia setup --portal
```

This runs the full setup in one shot:

1. Runs Portal activation (short user code confirmed at [portal.nadicode.ai/device](https://portal.nadicode.ai/device))
2. Stores the refresh token at `~/.nadia/auth.json`
3. Lets you pick a model from the curated catalog (or skip to keep your current one)
4. Sets the Portal as your inference provider in `~/.nadia/config.yaml` (when you pick a model)
5. Turns on the Tool Gateway (web, image, TTS, browser routing)
6. Returns you to your terminal ready to `nadia chat`

If you don't have a subscription yet, sign up at [portal.nadicode.ai](https://portal.nadicode.ai) first.

### Add the Portal to an existing install

```bash
nadia portal
```

`nadia portal` (with no subcommand) is the human-readable alias for `nadia auth add nous --type oauth` — it runs activation, lets you pick a catalog model, sets the Portal as your inference provider, and offers the Tool Gateway opt-in (identical to `nadia setup --portal`, and the same Portal flow as the first-time quick setup).

### Headless / SSH / remote setup

Activation confirms a short code in a browser, so it works without a browser on the Nadia host: run `nadia portal` over SSH, then approve the printed code from any device. For deeper remote patterns (port forwarding, browser-only environments like Cloud Shell / Codespaces), see [OAuth over SSH / Remote Hosts](/guides/oauth-over-ssh).

### Profile setup

If you use [Nadia profiles](/user-guide/profiles), the Portal refresh token is automatically shared across all profiles via a shared token store. Activate once on any profile, and the rest pick it up automatically — no need to repeat activation per profile.

## Using the Portal day-to-day

### Inspecting what's wired up

```bash
nadia portal            # activate + set up the Portal (one-shot onboarding)
nadia portal info       # activation status, subscription info, model + gateway routing
nadia portal status     # alias for `portal info`
nadia portal tools      # detailed Tool Gateway catalog with per-tool routing
nadia portal open       # open the subscription management page in your browser
```

`nadia portal info` gives you the high-level overview:

```
  NadicodeAI Portal
  ─────────────────
  Auth:    ✓ activated
  Portal:  https://portal.nadicode.ai
  Model:   ✓ using NadicodeAI Portal as inference provider

  Tool Gateway
  ────────────
  Web search & extract  via NadicodeAI Portal
  Image generation      via NadicodeAI Portal
  Text-to-speech        via NadicodeAI Portal
  Browser automation    via NadicodeAI Portal
  Cloud terminal        not configured
```

### Switching models

Inside a session, switch to any model in the curated catalog:

```bash
/model                 # arrow keys, enter to select
/model <catalog-slug>  # switch directly
```

Outside a session (the full setup wizard):

```bash
nadia model
```

### Mixing the gateway with your own backends

If you already have your own browser or search account and want to keep using it while routing the rest through the Portal, that's supported. Use `nadia tools` to pick a backend per tool:

```bash
nadia tools
# → Web search       → "NadicodeAI Subscription"
# → Image generation → "NadicodeAI Subscription"
# → Browser          → your own key
# → TTS              → "NadicodeAI Subscription"
```

The Tool Gateway is opt-in per tool, not all-or-nothing. The managed backends show up in `nadia tools` whether or not you've activated — if you pick "NadicodeAI Subscription" before activating, Nadia runs Portal activation inline (it won't change your inference provider or touch your other tools). See the [Tool Gateway docs](/user-guide/features/tool-gateway) for the full per-tool configuration matrix.

### Subscription management

Manage your plan, view usage and credits, or upgrade/cancel at any time:

- **Web:** [portal.nadicode.ai](https://portal.nadicode.ai)
- **CLI shortcut:** `nadia portal open` (opens the same page in your default browser)

## Configuration reference

After `nadia setup --portal`, `~/.nadia/config.yaml` will look like:

```yaml
model:
  provider: nous
  default: anthropic/claude-sonnet-4.6     # or whatever catalog model you picked
  # base_url is managed automatically by the NadicodeAI Portal
```

The Tool Gateway settings live under their respective tool sections:

```yaml
web:
  backend: nous       # web search/extract routes through the Tool Gateway

image_gen:
  provider: nous

tts:
  provider: nous

browser:
  backend: nous
```

The provider wire id stays `nous`. The refresh token is stored separately at `~/.nadia/auth.json` (not in `config.yaml` — credentials and configuration are kept separate by design).

## Token handling

Nadia mints a short-lived JWT from your stored Portal refresh token on each inference call rather than reusing a long-lived API key. The token lifecycle is fully automatic — refresh, mint, retry on transient 401 — and you never see it.

If the Portal invalidates the refresh token (password change, manual revoke, session expiry), the invalid refresh token is **quarantined locally** so Nadia stops replaying it and you don't see a stream of identical 401s. The next call surfaces a clear "re-activation required" message. Run `nadia portal` to activate again; the quarantine clears on the next successful activation.

## Non-interactive configuration (escape hatch)

Interactive setup is the supported path, and the Portal is the only provider the picker offers. For non-interactive contexts — CI, containers, config-managed fleets — you can point Nadia at a specific inference endpoint by setting the provider `base_url` in `config.yaml` (or the corresponding environment variable) directly, instead of running activation. This is a documented escape hatch for automation, not an interactive provider choice; day-to-day, activate the Portal and let it manage routing.

## Troubleshooting

### `nadia portal info` shows "not activated"

You haven't completed activation, or your refresh token was wiped. Run:

```bash
nadia portal
```

or use `nadia model` and re-select the NadicodeAI Portal.

### Got a "re-activation required" message mid-session

Your Portal refresh token was invalidated (password change, manual revoke, or session expiry). Run `nadia portal`, approve the new code, and your next request will use the fresh credentials. Any quarantine on the old token clears automatically on successful re-activation.

### A model I want isn't in the picker

The picker shows the curated catalog only — the manifest intersected with what the Portal can currently serve, minus experimental models. If a model you expect is missing, it may be experimental (stripped by design) or temporarily unavailable in the live catalog. Check `nadia portal info` for catalog status.

### Bills not appearing on my account

Check `nadia portal info` first — if it shows you're using a different provider instead of "using NadicodeAI Portal as inference provider", your local config has drifted. Run `nadia model`, pick the NadicodeAI Portal, and the next request will route through your subscription.

## See also

- **[Tool Gateway](/user-guide/features/tool-gateway)** — Every gateway tool, per-tool config, and pricing
- **[Subscription proxy](/user-guide/features/subscription-proxy)** — Use your Portal subscription from non-Nadia tools
- **[Voice mode](/user-guide/features/voice-mode)** — Voice conversations using the Portal's TTS
- **[AI Providers](/integrations/providers)** — How the Portal fits as your provider
- **[OAuth over SSH](/guides/oauth-over-ssh)** — Activate from remote hosts or browser-only environments
- **[Profiles](/user-guide/profiles)** — Multiple Nadia configurations sharing one Portal activation
