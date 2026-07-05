---
sidebar_position: 1
title: "Run Nadia Agent with the NadicodeAI Portal"
description: "Start-to-finish walkthrough: subscribe, activate, switch models, enable gateway tools, and verify routing."
---

# Run Nadia Agent with the NadicodeAI Portal

This guide walks you through running Nadia Agent on a [NadicodeAI Portal](https://portal.nadicode.ai) subscription end to end — from signing up to verifying that every tool routes correctly. If you just want the overview of what the Portal is and what's in the subscription, see the [NadicodeAI Portal integration page](/integrations/nadia-portal). This page is the task script.

## Prerequisites

- Nadia Agent installed ([Quickstart](/getting-started/quickstart))
- A device with a browser to approve activation (the browser does **not** have to be on the machine you're setting up — see [OAuth over SSH](/guides/oauth-over-ssh))
- About 5 minutes

You do **not** need a separate model key, search account, image account, browser account, or TTS key. That's the whole point.

## 1. Get a subscription

Open [portal.nadicode.ai](https://portal.nadicode.ai), sign up, and pick a plan.

Already subscribed? Skip to step 2.

## 2. Run the one-shot setup

```bash
nadia setup --portal
```

This single command does five things:

1. Runs Portal activation — prints a short user code and waits while you approve it at [portal.nadicode.ai/device](https://portal.nadicode.ai/device)
2. Stores the refresh token at `~/.nadia/auth.json`
3. Sets `model.provider: nous` in `~/.nadia/config.yaml`
4. Picks a default agentic model from the curated catalog
5. Turns on the Tool Gateway for web search, image generation, TTS, and browser automation

When it finishes, you're back at your terminal ready to chat.

### What if I'm SSH'd into a server?

Activation confirms a short code in a browser, so it works even when the Nadia host has no browser: run the command on the remote, then approve the printed code from any device.

```bash
nadia setup --portal            # on the remote — approve the printed code from your laptop browser
```

See [OAuth over SSH / Remote Hosts](/guides/oauth-over-ssh) for the full walkthrough including ProxyJump chains, mosh/tmux, and browser-only environments like Cloud Shell / Codespaces.

## 3. Verify it worked

```bash
nadia portal info
```

You should see:

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
```

If any line shows something other than "via NadicodeAI Portal" or the auth line says "not activated", jump to [Troubleshooting](#troubleshooting) below.

## 4. Run your first conversation

```bash
nadia chat
```

Try something that exercises both the model and the Tool Gateway:

```
Hey, search the web for "Nadia Agent release notes" and summarize the top 3 hits.
```

You should see Nadia call `web_search` (through the gateway) and respond with a summary. If the search runs and the response makes sense, you're done — the Portal is wired up end to end.

## 5. Pick the model you actually want

`nadia setup --portal` lets you pick a model during setup, but the whole point of the subscription is access to the curated catalog — switch any time with `/model` mid-session:

```bash
/model anthropic/claude-sonnet-4.6     # best general-purpose agentic
/model openai/gpt-5.4                  # strong reasoning + tool calling
/model google/gemini-2.5-pro           # huge context window
/model deepseek/deepseek-v3.2          # cost-effective coder
```

Or pop the picker to browse the curated catalog:

```bash
/model
```

Pick a different default permanently:

```bash
# in your terminal, outside any session
nadia config set model.default anthropic/claude-sonnet-4.6
```

### Don't pick Hermes-4 for agent work

Hermes-4-70B and Hermes-4-405B are available on the Portal at deep discounts, but they're **chat/reasoning models**, not tool-call-tuned. They will struggle with multi-step agent loops. Use them for hosted chat through the NadicodeAI Portal, for research workflows, or through the [subscription proxy](/user-guide/features/subscription-proxy) from non-agent tools. For Nadia Agent itself, stick to the frontier agentic models above.

The Portal's own info page carries this warning too — it's the official Portal guidance, not just a Nadia-side opinion.

## 6. (Optional) Customize Tool Gateway routing

The gateway is opt-in per tool, not all-or-nothing. If you already have your own browser account and want to keep using it while routing web search and image generation through the Portal, that's supported:

```bash
nadia tools
# → Web search       → "NadicodeAI Subscription"   (recommended)
# → Image generation → "NadicodeAI Subscription"   (recommended)
# → Browser          → your own key
# → TTS              → "NadicodeAI Subscription"   (recommended)
```

These rows appear in `nadia tools` even before you've activated — if you pick "NadicodeAI Subscription" without an active session, Nadia runs Portal activation inline (without changing your inference provider or your other tools).

Verify your mix with:

```bash
nadia portal tools
```

You'll see per-tool routing — `via NadicodeAI Portal` for the ones routed through the subscription, and the backend name for the ones using your own keys.

## 7. (Optional) Enable voice mode

Because the Tool Gateway includes TTS, [voice mode](/user-guide/features/voice-mode) works without a separate key:

```bash
nadia setup voice
# → pick "NadicodeAI Subscription" for TTS
# → pick a speech-to-text backend (local faster-whisper is free, no setup)
```

Then in any messaging-platform session (Telegram, Discord, Signal, etc.), send a voice message and Nadia will transcribe it, respond, and reply with synthesized voice — all on your Portal subscription.

## 8. (Optional) Cron + always-on workflows

The Portal subscription works for [cron jobs](/user-guide/features/cron) and [batch processing](/user-guide/features/batch-processing) the same way it works for interactive chat — the refresh token is reused automatically. No additional setup; just schedule cron jobs and they'll bill against your subscription.

```bash
nadia cron create "every day at 9am" \
  "Search the web for top AI news and summarize the 5 most important stories" \
  --name "Daily AI news"
```

The cron job runs unattended, calling the model + web search + summarization all through your Portal subscription.

## Profiles and multi-user setups

If you use [Nadia profiles](/user-guide/profiles) (e.g. a separate config per project), the Portal refresh token is automatically shared across all profiles via a shared token store. Activate once on any profile, and the rest pick it up automatically.

For team setups where multiple humans share a machine, each human has their own Portal account → each home directory holds its own `~/.nadia/auth.json` → no token sharing across users. This is the right boundary.

## Troubleshooting

### `nadia portal info` shows "not activated" after `nadia setup --portal`

Activation didn't complete. Re-run it:

```bash
nadia portal
```

If you can't approve the code, you're likely on a remote/headless host — see [OAuth over SSH](/guides/oauth-over-ssh) for the remote patterns.

### "Model: currently openrouter" (or some other provider) instead of "using NadicodeAI Portal as inference provider"

Your local config drifted. Activation worked but `model.provider` is still pointing at a different provider. Fix:

```bash
nadia config set model.provider nadia
```

Or interactively:

```bash
nadia model
# pick the NadicodeAI Portal
```

Re-verify with `nadia portal info`.

### Tool Gateway tools showing backend names instead of "via NadicodeAI Portal"

Per-tool config is overriding the gateway. Run:

```bash
nadia tools
# pick "NadicodeAI Subscription" for any tool you want gateway-routed
```

Some users intentionally mix — e.g. routing web through the Portal but using their own browser key. If that's intentional, leave it alone. If not, this command fixes it.

### "Re-activation required" mid-session

Your Portal refresh token was invalidated (password change, manual revoke, session expiry). The token is now quarantined locally so Nadia doesn't replay it endlessly. Just activate again:

```bash
nadia portal
```

The quarantine clears automatically on successful re-activation.

### A model I want isn't in the `/model` picker

The picker shows the curated catalog — the manifest intersected with what the Portal can currently serve, minus experimental models. If a model you expect is missing, it may be experimental (stripped by design) or temporarily unavailable. If a model is genuinely unavailable, [open an issue](https://github.com/nadicodeai/nadia/issues) — most gaps are catalog config we can update.

### Billing not appearing on my account

`nadia portal info` will tell you whether you're actually routing through the Portal or some other provider. Common causes:

- `model.provider` set to `openrouter`/`anthropic`/etc. instead of `nous`
- Multiple Nadia profiles where you're using the wrong one (check `nadia profile list`)

An activation failure is never the cause: when activation or a token refresh fails, Nadia surfaces a plain-language error and asks you to retry (`nadia portal`) — it never silently switches you to a different configured provider.

### Want to revoke and start clean

```bash
nadia auth logout nadia       # wipes the local refresh token
# Then re-run setup or remove the subscription from the Portal web UI
```

## What this gets you, in plain numbers

| Without the Portal | With the Portal |
|--------------------|-----------------|
| 1× model provider key in `.env` | 1× activation refresh token, no `.env` keys |
| 1× search key for web | Web routed through gateway |
| 1× image key for image gen | Image gen routed through gateway |
| 1× browser key for browser | Browser routed through gateway |
| 1× TTS key for voice mode | TTS routed through gateway |
| Several separate dashboards, top-ups, invoices | 1 subscription, 1 invoice |
| Cross-machine: replicate every key | Cross-machine: re-activate once |

That's the deal. If you're using more than two of those backends anyway, the subscription pays for itself.

## See also

- **[NadicodeAI Portal integration page](/integrations/nadia-portal)** — Overview of what's in the subscription
- **[Tool Gateway](/user-guide/features/tool-gateway)** — Full details on every gateway-routed tool
- **[Subscription proxy](/user-guide/features/subscription-proxy)** — Use your Portal subscription from non-Nadia tools
- **[Voice mode](/user-guide/features/voice-mode)** — Set up voice conversations on the Portal subscription
- **[OAuth over SSH](/guides/oauth-over-ssh)** — Remote / headless activation patterns
- **[Profiles](/user-guide/profiles)** — Share one Portal activation across multiple Nadia configurations
