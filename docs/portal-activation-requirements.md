# Portal activation — fork-side requirements

Argo deployments obtain managed model-access credentials from a NadicodeAI-operated portal at install time. This doc captures only the fork-side mechanism; product context lives in the private company monorepo. Requirements are FR-numbered to stay distinct from the monorepo's R-numbers.

## Requirements

- FR1. The setup wizard (and a non-interactive installer flag) accepts a one-time activation code.
- FR2. The box exchanges the code at a single portal HTTPS endpoint and receives its final credential — a base URL plus an API key — and optional initial settings (for example heartbeat interval and portal endpoint); the box proceeds immediately on receipt.
- FR2a. The exchange sends a box-generated install nonce so a retry after a lost response safely returns the same credential.
- FR3. The credential is written into the agent's provider configuration as the default model-access path, with owner-only file permissions (0600); the box never embeds assumptions about what service stands behind the base URL.
- FR4. Provider defaults route model traffic to the credential's base URL; existing multi-provider configuration remains available for advanced users (traffic outside the managed credential is outside the managed posture).
- FR5. A periodic metadata-only heartbeat (agent version, health, numeric remaining credit) reports to the portal, authenticated with the deployment's runtime key; the heartbeat response is the portal-to-box control channel. Message content never leaves the box. Mechanism (cron vs gateway hook) decided in planning.
- FR6. Credential rotation works without reinstalling: the box can call a credential-refresh endpoint authenticated by its current key, and portal-triggered rotation rides the heartbeat response.
- FR7. All changes land through the sanctioned fork mechanisms — additive overlay modules for logic, build-time config defaults, and fail-loud `content_edits` entries as the wiring point into the wizard/installer. No patches against upstream's portal/auth stack (`hermes_cli/auth_commands.py`, `hermes_cli/nous_account.py`, and siblings stay untouched).
- FR8. Nothing in this repo's artifacts references commercial logic (plans, pricing, channel structure); mechanism only.

## Constraints

- Weekly upstream sync burden must be unchanged: prefer additive overlay modules and `content_edits` defaults over patches.
- The activation step must degrade cleanly when the portal is unreachable (retry guidance; the wizard's other steps complete).
- No new runtime dependencies beyond what upstream already ships.
