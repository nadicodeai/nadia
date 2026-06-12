---
date: 2026-06-12
topic: argo-portal-activation
---

# Argo Portal activation — fork-side requirements

## Summary

Argo deployments obtain managed model-access credentials from a NadicodeAI-operated portal at install time, through the OAuth device-authorization flow (RFC 8628). This document is the public, mechanism-only requirements for the fork side of that work — the installer/wizard changes, credential handling, and the box check-in — written so `ce-plan` can act on it within this repo. Commercial logic (pricing, channels, tenancy) is out of scope here and lives in the private company monorepo.

This is a deliberately separate requirements doc from the product brainstorm. The fork-side work is independently buildable in this repo, so it carries its own `ce-plan` origin; requirement IDs are FR-numbered to stay distinct from the monorepo's R-numbers and to make cross-references unambiguous.

## Requirements

**Activation (device flow)**

- FR1. The setup wizard (and a non-interactive installer flag) requests a device authorization from the portal and displays the short user code and verification URL.
- FR2. The wizard polls per RFC 8628 (honoring `authorization_pending` / `slow_down`) until approval, then receives the final credential — a base URL plus an API key — and optional initial settings (for example check-in interval and portal endpoint); the box proceeds immediately. Standard polling semantics make retries safe; no custom retry machinery.

**Credential handling**

- FR3. The credential is written into the agent's provider configuration as the default model-access path, with owner-only file permissions (0600); the box never embeds assumptions about what service stands behind the base URL.
- FR4. Provider defaults route model traffic to the credential's base URL; existing multi-provider configuration remains available for advanced users (traffic outside the managed credential is outside the managed posture).
- FR6. Credential rotation works without reinstalling: portal-issued replacement credentials ride the check-in response, and the box can also re-run the device-authorization flow on demand.

**Check-in (fleet control channel)**

- FR5. The box checks in with the portal every few minutes — a lightweight call from the always-running gateway process, authenticated with the deployment's runtime key, reporting agent version and health. The check-in response is the portal-to-box control channel. The check-in plays no role in usage enforcement (enforcement happens at the model-access endpoint on every request), and message content never leaves the box. Implementation (gateway loop vs cron, cadence default) decided in planning.

**Fork hygiene**

- FR7. All changes land through the sanctioned fork mechanisms — additive overlay modules for logic (including the device-flow polling module), build-time config defaults, and fail-loud `content_edits` entries as the wiring point into the wizard/installer. No patches against upstream's portal/auth stack (`hermes_cli/auth_commands.py`, `hermes_cli/nous_account.py`, and siblings stay untouched).
- FR8. Nothing in this repo's artifacts references commercial logic (plans, pricing, channel structure); mechanism only.

## Constraints

- Weekly upstream sync burden must be unchanged: prefer additive overlay modules and `content_edits` defaults over patches.
- The activation step must degrade cleanly when the portal is unreachable (retry guidance; the wizard's other steps complete).
- No new runtime dependencies beyond what upstream already ships.

## Dependencies and Assumptions

- The portal serves the device-authorization grant (RFC 8628); the box side is a polling client only.
- Enforcement is request-path at the model-access endpoint, so the check-in is never on the critical path for stopping a deployment.
- Product context, the full requirements, and all commercial decisions live in the private `nadicodeai/nadicodeai` monorepo; this doc must remain mechanism-only.
