# Langfuse Observability Plugin

This plugin ships bundled with Nadia but is **opt-in** — it only loads when
you explicitly enable it.

## Enable

Pick one:

```bash
# Interactive: walks you through credentials + SDK install + enable
nadia tools  # → Langfuse Observability

# Manual
pip install langfuse
nadia plugins enable observability/langfuse
```

## Required credentials

Set these in `~/.nadia/.env` (or via `nadia tools`):

```bash
NADIA_LANGFUSE_PUBLIC_KEY=pk-lf-...
NADIA_LANGFUSE_SECRET_KEY=sk-lf-...
NADIA_LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or your self-hosted URL
```

Without the SDK or credentials the hooks no-op silently — the plugin fails
open.

## Verify

```bash
nadia plugins list                 # observability/langfuse should show "enabled"
nadia chat -q "hello"              # then check Langfuse for a "Nadia turn" trace
```

## Optional tuning

```bash
NADIA_LANGFUSE_ENV=production       # environment tag
NADIA_LANGFUSE_RELEASE=v1.0.0       # release tag
NADIA_LANGFUSE_SAMPLE_RATE=0.5      # sample 50% of traces
NADIA_LANGFUSE_MAX_CHARS=12000      # max chars per field (default: 12000)
NADIA_LANGFUSE_DEBUG=true           # verbose plugin logging
```

## Disable

```bash
nadia plugins disable observability/langfuse
```
