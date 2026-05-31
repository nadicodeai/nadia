# Argo for North-Italy SMB — Enablement Plan

*Audience: the maintainer editing Argo's packaging. Scope: turn upstream Hermes into a small, Italian-first, GDPR-credible default surface that a non-technical owner-operator can run on a €5 VPS with voice working out of the box.*

---

## 1. Executive summary

**What Argo-for-Italy is.** A re-packaged Hermes build (NadicodeAI's *Argo* fork) deliberately reduced to a small, opinionated default surface aimed at micro/small North-Italy firms — industrial-district manufacturers, Made-in-Italy/design, fashion/leather, food&wine, tourism, and the artisans and professional studios around them. The buyer is the 2-3 people who carry the company, with no IT staff and (per Istat) low AI literacy. The product's job is to **give time back on customer communication, marketing copy, document/admin work, and voice-note handling** — operational support in Italian, not "AI transformation".

**Positioning (one paragraph).** Argo is one competent, supervised assistant around one real workflow, that works in Italian out of the box, keeps the company's knowledge and corrections on the company's own box, never sends without a human pressing send, and is not locked to a single US model vendor. It ships ready to talk on Telegram, listen to and reply with Italian voice, read PDFs/photos/emails, draft and route messages, and remember corrections — with everything heavier kept one opt-in away.

**Headline default-on / strip stance.** Default surface is **small and curated**: keyless web search, terminal/file/vision/code/delegate/cron core tools, **local Italian voice (TTS + STT)**, local "Company Brain" memory, a trimmed productivity+email+github skill set, two calm hook plugins, and **Telegram as the only enabled channel**. Everything credential-heavy or sector-specific (WhatsApp Business, email/PEC, SMS, Slack, finance/Shopify/telephony skills, n8n/Linear MCPs, EU/local providers, redact_pii, tirith) is **kept in-image but off**. **Stripped entirely**: all China platforms + their tools/skills, China LLM providers, the joke personalities, red-teaming, gaming, mlops, health/BCI, OpenClaw migration, datagen, the demo/achievements plugins, and the Nous-Portal `dashboard_auth` lock-in. **macOS-only features (Apple Notes/Reminders/iMessage/FindMy, `computer_use`) and the cross-platform camofox browser are NOT stripped — they are kept in-tree but platform-gated/dormant, self-disabling on the Linux fleet and lighting up on a Mac laptop at ~zero cost.**

**Deployment model.** Argo runs *inside the customer's own perimeter*, not as SaaS — most often a **headless Linux VM** in the customer's virtual infrastructure, sometimes a Docker/K8s workload, sometimes a **laptop on-site** (Windows, occasionally a Mac), rarely a remote VPS. Ship **one adaptive build**, not per-OS SKUs; platform-gating decides what surfaces where. This shape is itself the headline GDPR pitch — *the agent and its data live on the customer's own machine and never leave the premises* — and it reinforces every local-first default (local voice, local memory, EU/local providers). On headless VMs, voice runs through the **messaging gateway** (transcribe inbound voice notes → TTS reply), which needs no mic/PortAudio; CLI push-to-talk is the laptop-only bonus.

> **Two release-blockers identified by the critique and confirmed against the live code.** Both undercut the core "works OOB, Italian-first" promise and **must** be fixed before the claims are made:
> 1. **Keyless web search is not actually in the image.** `ddgs` is in no extra and no `lazy_deps` entry — it is import-guarded only (`tools/web_tools.py:234`), exactly the failure mode this plan uses to strip NeuTTS/Piper. The eager-install fix must bake it in, or `web_search` must be demoted from "zero-config default".
> 2. **"Italian-first" via `config.personalities` does not fire.** `personalities` (`cli-config.yaml.example:599`) is only the manual `/personality` picker. A fresh agent defaults to **English**. Italian-by-default must come from the **auto-injected context file** path (`AGENTS.md`/`.hermes.md`/`SOUL.md`), which the agent loads into the system prompt at start.

---

## 2. Market snapshot (North-Italy SMB) — and the "so what" for defaults

- **Sectors:** mechanics/mechatronics, Made-in-Italy/design/arredo, textile-fashion-leather-footwear, agroalimentare & food/wine, tourism/hospitality, professional studios (commercialisti), artisans, retail, construction. → *So what:* defaults must be **Italian-language and sector-light** (drafting, translating, summarizing, admin), not enterprise process orchestration.
- **Firm shape:** overwhelmingly micro/small, family-owned, owner wears every hat, **no IT staff**, low digital floor (only 22.5% of small firms "highly digital"). → *So what:* **near-zero config**; must accept low-tech inputs — PDFs, emails, **photos**, **voice notes**, spreadsheets. Drives `vision_analyze` + local STT + file ops as core.
- **Channels (ranked):** **WhatsApp** (~97% reach, ~54% PMI use, 85-98% open) > **phone/voice** (77% of contact uses) > **email** (~29-34%) > **PEC** (legally mandatory formal lane) > **SMS** (OTP/notifications) > **Telegram** (minor, mostly broadcast). → *So what:* WhatsApp is the **flagship channel** but is **heavy** (Node bridge, QR-linked account, no official Cloud-API adapter in-tree), so it cannot be the zero-config default. **Telegram** (bot token only) is the only default-enabled channel — fastest first win — while WhatsApp is the first-class opt-in. Voice being a top channel makes the voice guarantee non-negotiable.
- **Language:** Italian UI/voice **non-negotiable** (Italy 59th/123, "Moderate" English); German co-official and majority in Alto Adige/Südtirol (68.6% German mother tongue). → *So what:* ship a **default Italian persona** plus a **bilingual IT/DE variant**; English is a fallback, not a default.
- **Compliance/GDPR:** e-invoicing via **SdI/FatturaPA** mandatory for all VAT holders since 2024; **PEC** mandatory; the **Garante** is the EU's most aggressive AI enforcer (banned ChatGPT, fined OpenAI €15M); **Legge 132/2025** mandates meaningful human oversight; **NIS2** now reaches SMB supply chains; data-residency a real buying criterion (US CLOUD Act anxiety). → *So what:* **local-by-default** (memory, STT, file ops, search backend with no paid-vendor egress), **draft-and-pause human-in-the-loop**, **EU/local providers foregrounded**, and **redact_pii/tirith** documented as one-flag hardening.
- **Adoption barriers:** **skills (58.6%) — not cost** — is #1; ~76% of PMI not investing; privacy 43.2%, regulatory uncertainty 47.3%. → *So what:* the product must be usable with **zero AI literacy** — opinionated defaults, guided "show me how", one Italian workflow as the front door, **not a product menu or a chatbot**.

---

## 3. Brand constraints (the principles that shaped the choices)

1. **Human direction and accountability** → draft-and-pause; sensitive/outbound actions pause for approval; the human presses send.
2. **Small, curated, opinionated surface** → ship one narrow workflow, not a catalog; advanced behind progressive disclosure.
3. **Customer-owned intelligence (Company Brain)** → local memory; corrections and context stay on the customer's box, exportable.
4. **Multi-provider, no lock-in** → `provider:auto`; EU/local options foregrounded; refuse vendor-coupled components (Nous Portal).
5. **Calm security, not fear-led** → least-privilege, sandboxed higher-risk execution, non-blocking self-correct hooks; GDPR/NIS2 posture stated plainly.
6. **No AI theater** → no gamification/achievements, no demo dashboards, no joke avatars; traces/timeline are proof-of-work, never the headline; Arianna only with real work context.
7. **Promise only what agents can keep** → never advertise a capability that isn't baked into the image (the standard that strips NeuTTS/Piper — and, per the critique, must also be applied to `ddgs`, SdI, and the aux-model provider).
8. **Final test:** *would a pragmatic manufacturing founder in northern Italy trust this?* — the basis for stripping the joke personalities.

---

## 4. THE LIST

> Config-mechanism columns name a real Argo file/key. Rows tagged **⚠ verify** need a code check before implementing (flagged again in §6). Line numbers are from the current tree and should be re-confirmed at edit time.

### ✅ Enable by default

| Feature | Group | Why | Config mechanism |
|---|---|---|---|
| `web_search` + `web_extract` (keyless `ddgs` backend) | tool | #1 SMB use is text/doc analysis (70.8%) + research for marketing; keyless = no API key, no paid-vendor egress (privacy 43.2%) | Already core in `toolsets.py _HERMES_CORE_TOOLS`. **`ddgs` is NOT in any extra/`lazy_deps` — must be force-installed in the Dockerfile (see §6 fix #1). ⚠ release-blocker.** Ship no paid-backend keys |
| `terminal` + `process` (local backend, dangerous-cmd approval) | tool | Execution substrate for every workflow; local = no egress; approval = human-in-the-loop | `_HERMES_CORE_TOOLS`; cli-config `terminal.backend: local`, `docker_mount_cwd_to_workspace: false` |
| `read_file` / `write_file` / `patch` / `search_files` | tool | Baseline for summarize/draft/admin on low-tech PDF/email/photo/spreadsheet inputs; works with no gestionale API | `_HERMES_CORE_TOOLS` (already core) |
| `vision_analyze` | tool | Owners photograph documents/receipts/labels; photos-in is how low-literacy owners interact; uses configured LLM, no extra key | `_HERMES_CORE_TOOLS` (already core). **Note: vision routes through the aux/compression model — see §6 fix #5 (US Nous default).** |
| `text_to_speech` (Edge TTS, Italian voice) | voice | Voice hard-constraint; free zero-key default; Italian voice for an Italian product | `text_to_speech` in core + messaging presets; cli-config `tts` voice `it-IT-ElsaNeural`. **Bake `edge-tts` extra into runtime-full (§5/§6).** |
| STT (faster-whisper local) + auto-transcription of inbound voice notes | voice | Voice hard-constraint; phone/voice is the most-used channel (77%); STT is top-3 SMB technique (41.3%); local = GDPR-safe, audio never leaves the box | cli-config `stt.enabled: true`, `provider: local`, `model: base`. **Bake `voice` extra into runtime-full (§5/§6).** |
| `todo` + `clarify` | tool | Task tracking + clarifying questions = brand "flag uncertainty instead of inventing" + guided onboarding (skills barrier 58.6%) | `_HERMES_CORE_TOOLS` (already core) |
| `memory` (built-in, local holographic backend) | tool | Company Brain; corrections/context persist and belong to the customer; local SQLite/FTS5 = no third-party egress | `memory` in core; plugin `group:memory` provider `holographic` (local); cli-config `memory_enabled` + `user_profile_enabled: true` |
| `session_search` | tool | Recall past customer conversations/quotes; local state DB, no egress | `_HERMES_CORE_TOOLS` (already core) |
| `skills_list` / `skill_view` / `skill_manage` | tool | Reusable instruction packs = brand "reusable skills under human guidance"; capture the firm's own Italian templates | `_HERMES_CORE_TOOLS` (already core) |
| `execute_code` (sandbox) | tool | Fewer LLM round-trips for admin/reporting (parse invoice PDFs, build a sheet); sandbox call/time limits = brand controlled autonomy | core; cli-config `code_execution` 300s/50-calls. **Note (critique fix #7a): not strictly POSIX-only — uses local sockets, Windows falls back to loopback TCP; Linux image unaffected.** |
| `delegate_task` (subagents) | tool | Isolated-context subtasks keep one workflow focused; bounded depth/parallelism = controlled autonomy | core; cli-config delegation 3-parallel/depth-1 |
| `cronjob` (scheduled tasks) | tool | Follow-ups, reminders, daily report (admin 25.7%); internal scheduler, no external dep | core (gated on gateway running) |
| `send_message` (cross-platform, China targets removed) | tool | Draft+route customer messages; draft-and-pause keeps the human pressing send | core. **China strip also touches `tools/send_message_tool.py`, not just the gateway list — see §6 fix #4.** |
| `browser_*` (local Chromium / agent-browser) | tool | High SMB value (research, supplier forms, portal quotes); Chromium ships in `:latest`; local accessibility-tree mode needs no cloud key; approval governs sensitive sites | `browser_*` already core; chromium baked (Dockerfile ~L360). Local backend default; cloud backends available-off |
| `image_generate` (key-gated) | tool | Generative image is a top technique (59.1%); marketing/social is the #1 AI function (33.1%); self-gates off when no backend key — safe default capability | `image_generate` stays in core; plugin `group:image_gen` activates when FAL/OpenAI key set |
| **Telegram** platform | messaging-platform | Lowest-friction conversational channel (bot token only; no QR/Node/Business verification); fastest first win while WhatsApp is configured | **The ONLY default-enabled platform** in the `config.yaml` template; `python-telegram-bot` via `messaging` extra |
| productivity skills (Office/PDF/OCR/maps + Notion/Airtable/Linear) — curated subset | skill | Highest-relevance bundle: documents/quotes/email/sheets/PPT/OCR are the proven admin (25.7%) + marketing/sales (33.1%) jobs; reads low-tech inputs | skills bundle — keep `skills/productivity` seeded; trim to office/PDF/OCR/maps/Notion-Airtable-Linear; per-tool CLIs gated on credentials |
| email/himalaya skill | skill | Email is the strong secondary written channel (~29-34%); provider-agnostic IMAP/SMTP works with any Italian mailbox/PEC | keep `skills/email` seeded; document PEC (IMAP/SMTP) as the formal/legal lane |
| github skill | skill | Supports the technical-person persona + the agent's own dogfood loop; keyless-friendly via `gh` | keep `skills/github` seeded |
| security-guidance plugin | plugin | "Security as a calm trust layer" + GDPR/NIS2 posture; non-blocking self-correct on dangerous patterns | add to default-enabled set (`cli-config plugins.enabled`) |
| disk-cleanup plugin | plugin | Auto-cleans ephemeral session files; supports €5-VPS posture; zero config | add to default-enabled `plugins.enabled` |
| model default + `provider:auto` (claude-opus-4.6) | provider | Capable default that auto-detects whatever key the customer pays for (no lock-in); EU/local surfaced for residency | cli-config `model.default anthropic/claude-opus-4.6`, `provider: auto`; EU/local in setup picker. **⚠ verify the exact model id is valid in this build before shipping.** |
| compression (auto context compression) | config | Keeps cost/latency down (affordability) via a cheap aux model; invisible reliability | cli-config `compression.enabled: true`. **⚠ the aux model defaults to US Nous — see §6 fix #5.** |
| memory `MEMORY.md`/`USER.md` + `session_reset` + per-user group context | config | Customer-owned bounded memory + `group_sessions_per_user: true` prevents cross-customer context bleed in group chats (GDPR-aligned) | cli-config `memory_enabled`/`user_profile_enabled: true`, `session_reset` mode `both`, `group_sessions_per_user: true` |
| prompt_caching + OpenRouter `response_cache` | config | Cost/latency savings = affordability; response_cache is free edge caching on OpenRouter | cli-config `prompt_caching: 5m`; `response_cache` documented-on when OpenRouter selected |
| tool_loop_guardrails (soft warnings) | config | Soft warnings on stalled/looping tools = controlled autonomy + reliability for unattended cron; hard-stop opt-in | cli-config `tool_loop_guardrails` soft-on, hard-stop off |
| `:latest` / runtime-full image (TUI + voice + browser, ffmpeg, s6) | config | Default image must carry voice (hard-constraint) + the show-work dashboard surface; ffmpeg already present | packaging — `:latest` = runtime-full (`make image-full`); **must add voice/edge-tts/ddgs to its install (§6).** |

### 🟡 Keep available, off by default

| Feature | Group | Why | Config mechanism |
|---|---|---|---|
| **WhatsApp** (Business) | messaging-platform | Market #1 channel and the flagship onboarding step — but heavy (Node bridge subprocess, QR-linked account; no official Business Cloud API adapter in-tree), so it can't be zero-config | gateway list — present, `enabled: false`; Node bridge in runtime-full; documented primary opt-in. **Roadmap: official WhatsApp Business Cloud API adapter** |
| email platform (IMAP/SMTP + PEC) | messaging-platform | Strong secondary written channel; PEC is the legal lane; needs the customer's mailbox creds | gateway list — `enabled: false`; stdlib IMAP/SMTP; document PEC as the legal lane, not marketing |
| SMS platform (Twilio) | messaging-platform | Complementary OTP/notifications/reminders lane; needs a Twilio account | gateway list — `enabled: false`; HTTP API, no heavy dep |
| Slack platform | messaging-platform | Used by some team buyers internally; not customer-facing Italian comms | gateway list — `enabled: false`; `slack-bolt` via `messaging` extra |
| Discord platform + discord/discord_admin tools | messaging-platform | Community/team use, not core Italian customer comms; already default-off upstream | `_DEFAULT_OFF_TOOLSETS` already has discord/discord_admin; `enabled: false` |
| Signal / Matrix / Mattermost / Webhook / BlueBubbles(iMessage) / Home Assistant | messaging-platform | Niche/self-hosted/privacy-power-user/hardware-bound channels; keep surface small | gateway list — all `enabled: false`; heavy external deps documented as power-user |
| finance skills (DCF/LBO/comps + excel/pptx-author + Yahoo quotes) | skill | High relevance (Excel models, preventivo modelling) but a specialized opt-in; light deps | `optional-skills/finance` — `argo skills install finance`; feature in catalog |
| optional productivity: Shopify + telephony (Twilio/Bland/Vapi) + Canvas/SiYuan | skill | E-commerce (retail ~19% online) + AI-call are high-value for tourism/retail but credential-heavy/sector-specific | `optional-skills/productivity` — opt-in; telephony gated on Twilio/Bland/Vapi keys |
| n8n MCP | mcp | Very popular EU automation tool; bridges the firm's existing automations; manifest only | `optional-mcps/n8n` — `argo mcp install official/n8n`; feature in catalog |
| Linear MCP | mcp | Issue/project tracking for the technical persona; remote OAuth, nothing local | `optional-mcps/linear` — `argo mcp install official/linear` |
| creative skills (SVG/Excalidraw/p5/infographics) — light subset | skill | Marketing/social visuals have value, but heavy members (ComfyUI/Manim/TouchDesigner) MUST NOT bundle on a €5-VPS | move `skills/creative` to opt-in (or seed only the pure-HTML subset); **exclude comfyui/manim/touchdesigner from the image** |
| media skills (YouTube→summary, GIF, audio) — light subset | skill | YouTube transcript→summary/blog is a real marketing use (keyless); ML-audio members are heavy | keep `youtube-content` (needs `youtube` extra); move ML-audio members to opt-in |
| note-taking/obsidian + smart-home/openhue + social-media/xurl + research skills | skill | Useful to some owners but niche/credential-bound; not the proven core jobs | move `skills/{note-taking,smart-home,social-media,research}` out of default seed to optional |
| software-development + autonomous-ai-agents + devops(kanban/webhook) skills | skill | Dev-methodology / external-agent delegation / multi-agent kanban are power-user, not the owner's first workflow | move to `optional-skills`; `kanban_*` tools stay gated (worker/orchestrator only) |
| optional skills: communication(1-3-1), security(1Password/Sherlock), devops(Docker/Pinggy), web-dev(page-agent), email(agentmail), research(OSINT) | skill | Credible power-user upsells but credential/infra-heavy | `optional-skills/*` opt-in via `argo skills install`; surface 1Password + communication in catalog |
| blockchain skills (read-only EVM/Solana/Hyperliquid) | skill | No SMB justification, but keyless read-only and already opt-in/never-seeded — leaving it dormant costs zero default surface and is lower-effort than excising | `optional-skills/blockchain` — leave as-is (opt-in, NOT seeded, NOT featured). No packaging action |
| `video_analyze` / `video_generate` / heavy image_gen plugins / `x_search` / `mixture_of_agents` | tool | Video low SMB relevance and expensive; x_search/MoA need xAI/OpenRouter keys; already default-off | `_DEFAULT_OFF_TOOLSETS` already has video/video_gen/x_search/moa; plugin groups key-gated |
| premium TTS + cloud STT (ElevenLabs/OpenAI/Groq/Gemini/xAI) | voice | Quality upgrades, but US data-residency or paid; keep behind keys | `tts-premium` extra (elevenlabs) installable; cloud STT/TTS auto-detect only when key present |
| `voice_mode` (CLI push-to-talk) + transcription helper | voice | CLI mic needs PortAudio + desktop session — inert on headless VMs, but a real bonus on a laptop install; harmless either way | runtime mode stays available; **no PortAudio in the VM/container** (messaging path needs no mic); installs locally on a laptop |
| Apple skills (Notes/Reminders/iMessage/FindMy) | skill | **Platform-gated** (`platforms: [macos]`; loader maps macos→darwin and skips off-platform, `skills_tool.py:34,97-100`): auto-skipped on the Linux fleet, auto-loaded on a Mac laptop where they're genuinely useful to an owner. Cost on Linux ≈ a few KB | keep `skills/apple` seeded; the loader gates by OS — no Linux cost, lights up on macOS |
| `computer_use` (macOS desktop control, cua-driver) | tool | **Self-gating**: `check_computer_use_requirements()` returns False unless `sys.platform=='darwin'` + cua-driver present (`tools/computer_use/tool.py:741`). Inert on Linux; on a Mac laptop it's the headline "agent operates my desktop" capability | keep in `_HERMES_CORE_TOOLS`; on macOS gate behind **approval** (matches human-in-the-loop). Do not strip |
| camofox anti-detection browser backend | tool | Cross-platform and **already opt-in** — only active when `CAMOFOX_URL` is set (`tools/browser_camofox.py`). Not a platform issue; the only real cost is the ~300MB Camoufox binary | keep the code path (dormant); **don't bundle the Camoufox binary**. Default browser stays agent-browser/Chromium |
| EU/local + secondary model providers (Mistral-FR, Azure-EU, LM Studio, Ollama/vLLM/llamacpp, OpenAI, Gemini, Nous, Copilot, HuggingFace) | provider | Data-residency is a real buying criterion; Mistral(FR)/Azure-EU/local LM Studio/Ollama give "data stays in EU/on-box" | plugin `group: model-providers` — keep these; **foreground Mistral/azure-foundry/lmstudio/ollama** in setup picker |
| observability/langfuse plugin | plugin | Useful for the technical person to debug cost/latency; needs Langfuse keys | not in default allow-list; documented opt-in |
| teams_pipeline + google_meet plugins | plugin | Meeting-summary intelligence is high-value but credential/infra-heavy (MS Graph; Meet needs Chrome+audio bridge) | off by default; catalog upsell |
| spotify plugin/tool | plugin | Office-music novelty, low business value; already off | `_DEFAULT_OFF_TOOLSETS` has spotify; plugin off |
| kanban plugin + browser cloud backends (Browserbase/browser_use/Firecrawl) | plugin | Kanban is multi-agent power-user; cloud browser backends need keys and send page data to a 3rd party (privacy) | off by default; browser falls back to local Chromium |
| config toggles: security(tirith), worktree isolation, gateway streaming, `privacy.redact_pii` | config | tirith (pre-exec scanning) + redact_pii are valuable GDPR/security levers but need a binary / change behavior | keep commented/off; **DOCUMENT `redact_pii: true` and tirith as recommended privacy/security hardening** in the SMB guide |
| `:slim` / runtime-slim image | config | Headless CLI/server deployments (CI, batch); ~371MB; not the customer default | packaging — `:slim` = runtime-slim (`make image`); a build variant |
| FORK extras-parity (bedrock/azure-identity eager-install) | config | The voice/messaging/anthropic eager-install is mandatory; bedrock/azure are less SMB-relevant → stay documented opt-in extras (keep image lean) | `packaging-overrides.yaml` — keep bedrock/azure-identity as documented opt-in extras with their `why`; resolve voice+edge-tts+messaging+anthropic+ddgs separately |

### ❌ Strip out

| Feature | Group | Why | Config mechanism |
|---|---|---|---|
| China platforms: feishu, dingtalk, wecom, wecom_callback, weixin, qqbot, yuanbao | messaging-platform | Explicit constraint + zero North-Italy relevance; China-specific native SDKs; `wecom_callback` parses untrusted XML (attack surface) | remove `Platform.*` branches in `gateway/run.py` (~L6298-6376 + QQ/YUANBAO env ~L3994-4010); drop dingtalk/feishu extras; delete `gateway/platforms/{feishu,dingtalk,wecom,wecom_callback,weixin,qqbot,yuanbao}.py` |
| China companion tools: `feishu_doc_read`, `feishu_drive_*`, `yb_*` (yuanbao) | tool | Companion tools for stripped platforms; dead weight + China SDK deps | remove registrations from `toolsets.py`/`tools/*` (overlay strip) |
| China send_message targets/branches | tool | **Critique fix #4:** China targets are hardcoded in `tools/send_message_tool.py`, not only the gateway list | remove yuanbao/feishu/weixin examples from the `description` string (L138) and delete the feishu (L349)/weixin (L226,L376)/yuanbao (L380) special-case branches + `_send_weixin`/`_send_yuanbao`/`_send_feishu` |
| yuanbao skill category | skill | Tencent Yuanbao group ops (China platform); pairs with stripped yuanbao platform | delete `skills/yuanbao` from the seed |
| **Joke personalities** (kawaii, catgirl, uwu, pirate, surfer, noir, shakespeare, hype, philosopher, …) | config | **Critique fix #3 (confirmed: 12+ entries in `cli-config.yaml.example:599+`).** "desu~ ヽ(>∀<☆)ノ", "Neko-chan nya~", "hewwo *nuzzles your code* OwO" directly violate serious-business / no-AI-theater / Arianna-never-infantilized and fail the "manufacturing founder trust" test | strip from `agent.personalities` in the Argo default config; ship only business-appropriate Italian + IT/DE bilingual personas |
| red-teaming/godmode skill | skill | Jailbreak/safety-bypass prompts are a direct legal + brand liability for a GDPR/EU-AI-Act/Legge-132 market | delete `skills/red-teaming` from the seed; ensure absent from every image |
| gaming skill (Minecraft/Pokemon) | skill | Explicit constraint + no business use; undermines the serious brand | delete `skills/gaming` from the seed |
| mlops skills (lm-eval, vLLM, FSDP, abliteration, SAM, DSPy) | skill | Explicit constraint — GPU/PyTorch/CUDA research tooling, too heavy for €5-VPS; abliteration is a safety-bypass liability | delete `skills/mlops`; keep OUT of image and OUT of catalog |
| health skills (fitness/nutrition + neuroskill-BCI) | skill | Personal wellness / BCI hardware; zero SMB relevance; health is a Legge-132 sensitive sector the brand avoids | `optional-skills/health` — remove from catalog/build |
| migration (openclaw) skill | skill | One-shot import of a competitor footprint; a fork should not carry a competitor-migration artifact | `optional-skills/migration` — remove from build |
| datagen / dev-only research scaffolding | config | Explicit constraint + dev-only eval scaffolding with no customer value | exclude `datagen-config-examples` + dev-only runners from the customer image |
| example-dashboard + hermes-achievements plugins | plugin | Demo dashboard + gamification; no business value, "achievements" clashes with no-AI-theater | remove `plugins/{example-dashboard,hermes-achievements}`; never in `plugins.enabled` |
| dashboard_auth/nous plugin | plugin | Couples dashboard OAuth to Nous's US-hosted Portal — vendor lock-in + non-EU dependency; violates no-lock-in/EU-residency | remove `plugins/dashboard_auth`; dashboard auth must be self-hosted/local (**replacement = separate task**) |
| China LLM provider profiles: zai(ZhipuAI), kimi/moonshot, minimax/minimax-cn, xiaomi | provider | China model vendors carry data-residency/geopolitical risk toxic to a GDPR-first pitch; EU/local/US-major cover all needs | drop these profiles from the `model-providers` setup/discovery; generic custom/OpenAI-compatible path stays for advanced users |
| NeuTTS / KittenTTS / Piper advertised as "out-of-the-box" local TTS | voice | NO pyproject extra and NO `lazy_deps` entry (import-guarded only) + large models → CANNOT work in either image without manual pip install; advertising as default = false capability claim | docs/cli-config — do NOT list as default/auto-available; document only as an advanced manual recipe. **Edge TTS stays the shipped free default** |

---

## 5. Voice service — works out of the box

**Plain statement: voice works out of the box, with zero API keys — *after* the one mandatory packaging fix in §6.** The fix bakes the voice deps into `:latest`; without it, the deps try to lazy-install from PyPI at first use and fail in a PyPI-blocked container. The voice guarantee itself is **verified accurate** against the live code: Edge is the real TTS default (`tools/tts_tool.py` `DEFAULT_PROVIDER='edge'`), it passes the configured voice through with no allowlist, and **`it-IT-ElsaNeural` / `it-IT-DiegoNeural` are real edge-tts 7.2.7 voices**; faster-whisper local is the real STT default and auto-detects Italian.

**Guaranteed default config (no keys):**
- **TTS** = Edge TTS (`provider: edge`), voice **`it-IT-ElsaNeural`** (free, no key; MP3 out → ffmpeg transcodes to OGG/Opus for voice bubbles).
- **STT** = **faster-whisper local** (`provider: local`, `model: base`, ~150MB auto-downloaded on first use; free, offline; CUDA→CPU int8 fallback; Whisper silence-hallucination filter). Italian is handled by **auto-detect** (critique fix #7c) — no `language` key required; *optionally* set `stt.local.language: it` to force it for short/noisy clips.
- Gateway **auto-transcribes inbound voice notes** (Telegram/WhatsApp/Slack/Signal) and can **reply with TTS** (auto-TTS-reply opt-in per chat, preserving draft-and-pause).

**Requirements:**
1. **MANDATORY PACKAGING FIX** — runtime-full installs Python deps via bare `pip install -e .` (Dockerfile **L190**, confirmed; L189 is the pip-upgrade) and the `[all]` extra **deliberately excludes** voice + edge-tts (pulled 2026-05-12 so a quarantined PyPI release can't break installs), so faster-whisper and edge-tts are **not baked in**. Change the install to include `voice,edge-tts` (full line in §6).
2. **ffmpeg** — already present in runtime-full (Dockerfile ~L285); required for Opus bubbles and STT on non-WAV audio. No change.
3. **Deps baked by the fix:** `faster-whisper==1.2.1` + `sounddevice==0.5.5` + `numpy==2.4.3` (`voice` extra) and `edge-tts==7.2.7` (`edge-tts` extra).
4. **Network:** Edge TTS is cloud-free but **not offline** — needs outbound HTTPS to the Microsoft Edge TTS endpoint. A PyPI-blocked-*and*-internet-restricted container will still fail TTS at runtime even with the package baked in (critique fix #8). For air-gapped/EU-only posture, document Piper/Kitten as a **manual** local-TTS swap.
5. **No PortAudio in the container** — only CLI push-to-talk needs it; the messaging path doesn't.
6. **Smoke test** — assert `import faster_whisper, edge_tts, telegram`, `from tools import tts_tool`, **and `import ddgs`** (critique fix #1/#8) so a future extras regression fails loudly.

**Premium upgrade path (opt-in, keys required):** ElevenLabs (US, multilingual + cloning, `tts-premium` extra) · OpenAI TTS gpt-4o-mini-tts + OpenAI/Groq Whisper STT (US) · Gemini / xAI Grok voice (US) · **Mistral Voxtral (EU/France — the privacy-friendly choice, but currently DEAD: `mistralai` PyPI quarantined 2026-05-12; re-enable when a verified-clean release returns)** · any local CLI (Kokoro/VoxCPM/Piper/Kitten) wired as a `type: command` provider with no Python changes — best for an EU-only/offline posture.

---

## 6. Concrete packaging changes (ordered checklist)

1. **[BLOCKER — Dockerfile L190] Eager-install the customer-relevant extras + ddgs into runtime-full.** Change `.venv/bin/pip install --no-cache-dir -e .` to:
   `.venv/bin/pip install --no-cache-dir -e .[voice,edge-tts,messaging,anthropic] ddgs`
   This bakes in: local STT + Edge TTS (voice guarantee), Telegram/Slack adapters, the Anthropic provider, **and the keyless search backend**. `ddgs` is a bare pip package — it is in **no extra** (confirmed: `pyproject.toml` `web = [fastapi, uvicorn]` only) and **no `lazy_deps` entry** (`tools/web_tools.py:234`, import-guarded), so it must be added explicitly. *(If you instead choose to demote web_search, see Open Question Q1.)*

2. **[BLOCKER — Italian-first persona] Ship a default Italian system prompt via the auto-injected context-file path, NOT `config.personalities`.** Confirmed: `personalities` (`cli-config.yaml.example:599`) is only the `/personality` picker; there is **no `system_prompt`/`instructions`/`default_personality`/`language` key**. The agent **does** auto-inject `AGENTS.md`/`.hermes.md`/`SOUL.md`/`.cursorrules` into the system prompt at start (`agent/prompt_builder.py`, `hermes_cli/_parser.py`). **Seed an Italian-language instructions file on that path** in the customer image (plus a German/bilingual variant for Alto Adige). **⚠ verify** the exact filename/precedence the gateway honours for a non-CWD server deploy before relying on it; if none applies cleanly to the gateway runtime, this is a code gap (add a configurable default system prompt) — **do not claim Italian-first until a fresh agent demonstrably replies in Italian with zero user action.**

3. **[Smoke test] Add a built-image test** asserting `import faster_whisper, edge_tts, telegram`, `import ddgs`, `from tools import tts_tool`. Document that Edge TTS needs outbound HTTPS to Microsoft.

4. **[packaging-overrides.yaml] Mark voice/edge-tts/messaging/anthropic (and ddgs) as RESOLVED** (now eagerly installed) rather than FLAGGED; keep bedrock/azure-identity as documented opt-in extras with their `why`/issue.

5. **[cli-config.yaml default] Italian-first defaults + strip joke personalities:**
   - `tts` voice = `it-IT-ElsaNeural` (or `it-IT-DiegoNeural`); `stt.enabled: true`, `provider: local`, `model: base`.
   - `plugins.enabled` = `{security-guidance, disk-cleanup}`.
   - Keep: `memory_enabled`/`user_profile_enabled: true`, `group_sessions_per_user: true`, `session_reset: both`, `compression.enabled: true`, `prompt_caching: 5m`, `tool_loop_guardrails` soft-on, `code_execution`/`delegation` bounded defaults, `mcp_servers` examples commented.
   - **Strip the joke personalities** (kawaii/catgirl/uwu/pirate/surfer/noir/shakespeare/hype/philosopher and the rest — 12+ at `:599+`); keep only serious Italian + IT/DE personas.
   - **⚠ verify** `model.default anthropic/claude-opus-4.6` resolves in this build.
   - **[Aux-model / data-residency — critique fix #5] ⚠ verify and address the auxiliary (compression + vision) model default.** The aux default is reported as Nous (US). For a GDPR/EU pitch this silently routes compression+vision of customer content to a US endpoint. Classify it explicitly: **document it, and default/allow it to follow the customer's chosen EU/local provider** (Mistral/Azure-EU/local). Fold into the redact_pii/data-residency guidance.

6. **[gateway `config.yaml` template] Enable ONLY Telegram.** Ship WhatsApp/email/SMS/Slack present-but-`enabled: false` with first-class setup docs (WhatsApp Business as the flagship opt-in).

7. **[China strip — gateway] Remove every China `Platform.*` branch** from `gateway/run.py` (~L6298-6376) **and** the QQ/YUANBAO env handling (~L3994-4010), and delete `gateway/platforms/{feishu,dingtalk,wecom,wecom_callback,weixin,qqbot,yuanbao}.py` via the overlay/rename pipeline.

8. **[China strip — send_message, critique fix #4] Add `tools/send_message_tool.py` to the overlay** (confirmed China refs): remove the yuanbao/feishu/weixin examples from the tool `description` (L138) and delete the `weixin` (L226,L376), `feishu` (L349), `yuanbao` (L380) special-case branches plus `_send_weixin`/`_send_yuanbao`/`_send_feishu`. Otherwise the model still sees yuanbao routing examples in the schema.

9. **[toolsets.py] Trim `_HERMES_CORE_TOOLS`** in the customer build: remove **only** the China companion tools (`feishu_doc_read`/`feishu_drive_*`/`yb_*`). **KEEP `computer_use`** — it self-gates to macOS (`tools/computer_use/tool.py:741` returns False off-`darwin`) so it is inert on the Linux fleet and there is no reason to excise it; on a Mac laptop it is a differentiator. Keep upstream `_DEFAULT_OFF_TOOLSETS` `{moa, homeassistant, spotify, discord, discord_admin, video, video_gen, x_search}` off.

10. **[skills bundle — `setup-hermes.sh` ~L399-412 `cp -rn skills/*`]** KEEP `productivity`, `email`, `github` (+ light creative/media subset). **KEEP `apple` seeded** — it is platform-gated (`platforms: [macos]`) so it is invisible on the Linux fleet and only surfaces on a Mac laptop. **DELETE** `gaming`, `red-teaming`, `mlops`, `yuanbao` so they never seed. **MOVE** `note-taking`, `smart-home`, `social-media`, `research`, `software-development`, `autonomous-ai-agents`, `devops`, and heavy creative/media members to `optional-skills`. **Exclude** comfyui/manim/touchdesigner and all mlops/Blender heavy native installs from the image. **⚠ verify** the exact seed copy line/path in the current `setup-hermes.sh`.

11. **[plugins] DELETE** `plugins/example-dashboard`, `plugins/hermes-achievements`, `plugins/dashboard_auth` (Nous lock-in) from the customer build. The dashboard needs a **self-hosted/local auth replacement (separate task).**

12. **[model-providers picker] Drop** China vendor profiles (zai, kimi-coding, minimax, minimax-cn, xiaomi); **FOREGROUND** EU/local (Mistral-FR, azure-foundry EU-region, lmstudio, custom/ollama/vllm/llamacpp); keep `provider:auto` + claude-opus-4.6 as the capable default.

13. **[image strip] Strip dev/niche artifacts:** `datagen-config-examples`, mlops, red-teaming, OpenClaw migration, health/BCI. **Don't bundle the ~300MB Camoufox binary** but keep camofox's opt-in `CAMOFOX_URL` code path. Do not feature blockchain/health/mlops in the catalog (blockchain stays a dormant opt-in, never seeded).

14. **[image identity] `:latest` = runtime-full (`make image-full`); `:slim` = runtime-slim (`make image`)** — a build variant, not the customer default. **⚠ verify** the exact Make target names in the current Makefile.

15. **[Documentation/UX — brand, not code]** Default to draft-and-pause (auto-TTS-reply opt-in per chat) and human-in-the-loop approval on sensitive/outbound actions; surface `redact_pii: true` and tirith as recommended GDPR/security hardening; lead onboarding with **one Italian workflow** (not a product menu, not a chatbot front door); keep the run-timeline/traces dashboard as proof-of-work, never the headline.

---

## 7. Open questions / risks

- **Q1 — web_search OOB (critique #1, high).** Decision needed: bake `ddgs` into the Dockerfile (preferred — keeps the "zero-config keyless search" headline true and applies the NeuTTS/Piper standard consistently), **or** demote `web_search` to "available, requires post-setup install" and stop describing it as zero-config. The named alternative `searxng` needs a self-hosted `SEARXNG_URL` the customer won't have, so it is **not** a substitute. **Resolved in this plan as: bake it in (§6 #1).**
- **Q2 — Italian-first delivery (critique #2, high).** The seeded-context-file approach (§6 #2) is the right vehicle, but the exact filename and **whether the gateway server runtime (not just CWD-based CLI) injects it** must be verified. If it does not, this is a **code gap**: add a configurable default system prompt. The Italian-first claim is **not** earned until a fresh agent replies in Italian with zero user action.
- **Q3 — Auxiliary/compression/vision provider defaults to US Nous (critique #5, medium).** Verify the current aux default and make it follow the customer's EU/local provider (or at minimum document the US routing). Until then, "data stays in the EU" is only partly true — compression and `vision_analyze` may egress to a US endpoint.
- **Q4 — SdI/FatturaPA + gestionale blind spot (critique #6, medium).** There is **no SdI/FatturaPA XML or TeamSystem/Zucchetti/Danea capability in-tree**, yet e-invoicing is the universal North-Italy admin baseline (mandatory for all VAT holders since 2024) and the commercialista is the key channel. **State the limit honestly:** Argo *reads* PDFs/emails/photos of invoices via vision+OCR; it does **not** speak SdI XML. Put a native FatturaPA/SdI + TeamSystem/Zucchetti **read** integration on the roadmap — it is the universal admin entry point and the most defensible expansion wedge.
- **Q5 — WhatsApp is opt-in, not default.** The #1 market channel is not the default channel because no official Business Cloud API adapter exists in-tree (only the heavy Node/QR bridge). First-win lands on Telegram. **Roadmap: an official WhatsApp Business Cloud API adapter** is the single highest-leverage channel investment.
- **Q6 — Mistral voice is dead.** The EU/privacy-friendly premium voice option (Voxtral) is unavailable while `mistralai` is PyPI-quarantined. The EU-only voice story currently rests on the **manual** Piper/Kitten command-provider swap, not a supported default.
- **Q7 — Dashboard auth replacement is unscoped.** Removing `dashboard_auth` (Nous) leaves the dashboard without an auth path; a **self-hosted/local replacement is a separate task** and a gap until done.
- **Q8 — Air-gapped customers.** Edge TTS needs live Microsoft egress; a fully air-gapped deploy has **no supported zero-config voice** — only the documented manual Piper/Kitten swap.
- **Critique items accepted with low-priority handling (none rejected):** #7a `execute_code` is not strictly POSIX-only (loopback-TCP fallback on Windows; Linux unaffected) — corrected in §4. #7b install fix is **L190**, not L189-190 — corrected. #7c faster-whisper auto-detects Italian; `stt.local.language: it` is the optional force — noted in §5. #8 smoke test extended to `import ddgs` + Edge egress note — folded into §5. **No high/medium critique issue is rejected.** The only deliberate non-removal is **blockchain skills** (kept dormant/opt-in/never-seeded because excising costs more than leaving them inert), which is a *retention* call the matrix already made, not a rejected fix.
