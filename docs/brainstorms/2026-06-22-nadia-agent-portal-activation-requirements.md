---
date: 2026-06-22
topic: nadia-agent-portal-activation
status: reviewed-draft
source: ce-brainstorm
---

# Nadia Agent Portal Activation Requirements

## Summary

Nadia needs the agent-side half of portal activation.

The target flow is simple: an Installer runs `nadia -p <profile> portal connect`, Nadia shows a portal activation URL and code, the Portal Admin approves it, Nadia claims a portal-managed runtime credential, stores it under that active Local Profile, ACKs durable storage, and then uses that credential for inference.

No manual OpenRouter key copy. No portal inference proxy. No billing UI in the agent. No generic provider marketplace.

## Problem Frame

The portal v0 product only works if the public Nadia agent can safely activate one Local Profile into one portal-managed Nadia Agent.

Current Nadia already has local profiles, profile-scoped `NADIA_HOME`, auth storage, portal CLI onboarding, device-code login machinery, status surfaces, and provider resolution. The missing work is the exact portal activation contract and safety rules:

- a Local Profile must bind to one portal Nadia Agent;
- a portal runtime credential must be profile-local;
- claim/ACK failure must not leave a usable orphan credential;
- clone, import, export, and replacement must not accidentally duplicate or switch an activated agent;
- the agent must use portal wrapper endpoints, not expose raw Better Auth device-registration internals;
- the user-facing noun is `Nadia Agent`, while the runtime container is `Local Profile`.

## Current Code Anchors

- `README.md:1` defines Nadia Agent as an installed AI agent.
- `README.md:33` says local configuration lives under `~/.nadia`.
- `README.md:36` says portal-managed model access is optional.
- `README.md:47` still uses older `Nadia Instance` language for activation. That must not become the new product vocabulary.
- `nadia_cli/portal_cli.py:1` defines the existing `nadia portal` command surface.
- `nadia_cli/portal_cli.py:191` dispatches current portal subcommands.
- `nadia_cli/portal_cli.py:211` registers the existing portal parser.
- `nadia_cli/portal_cli.py:226` registers current `login`, `info`, `status`, `open`, and `tools` subcommands.
- `nadia_cli/subcommands/backup.py:13` registers `nadia backup` for whole-home backups.
- `nadia_cli/subcommands/backup.py:27` defines `backup --quick` as critical state including auth.
- `nadia_cli/subcommands/import_cmd.py:13` registers `nadia import` for restoring backups.
- `nadia_cli/config.py:2385` documents pre-update backups that can be restored through `nadia import`.
- `nadia_cli/profiles.py:1` describes profile management for isolated Nadia runtimes.
- `nadia_cli/profiles.py:38` creates separate profile directories for memories, sessions, skills, logs, plans, workspace, cron, and home.
- `nadia_cli/profiles.py:55` allows profile cloning from an existing profile.
- `nadia_cli/profiles.py:198` excludes sensitive default-profile files such as `auth.json` and `.env` from export.
- `nadia_cli/main.py:330` preparses `--profile` / `-p` before heavy imports.
- `nadia_cli/main.py:490` sets `NADIA_HOME` for the selected profile.
- `nadia_cli/auth.py:855` stores auth state under the active Nadia home as `auth.json`.
- `nadia_cli/auth.py:877` can read a global-root auth store from profile mode.
- `nadia_cli/auth.py:1131` falls back to the global-root provider state when a profile lacks local state.
- `nadia_cli/auth.py:1215` falls back to the global-root credential pool when a profile lacks local credentials.
- `nadia_cli/auth.py:4394` implements the existing OAuth device-code request.
- `nadia_cli/auth.py:4421` polls the existing OAuth token endpoint with a raw `device_code`.
- `nadia_cli/auth.py:5261` persists existing Nous credentials and mirrors credential-pool state.
- `nadia_cli/auth.py:5330` resolves current Nous runtime credentials.
- `nadia_cli/auth.py:7564` implements the current Nous device-code login.
- `nadia_cli/status.py:199` reports whether an inference credential is present.
- `agent/credential_persistence.py:151` strips raw secrets for borrowed/reference credential sources.

## Portal V0 Contract Source

This brainstorm is anchored to the portal v0 decisions already made in the portal repo:

- Portal product noun: `Nadia Agent`.
- Local runtime noun: `Local Profile`.
- One host can run many local profiles.
- One activated local profile maps to one portal Nadia Agent.
- Portal creates and manages the supplier credential, currently OpenRouter-backed.
- The agent receives only the portal runtime credential needed for inference.
- Manual supplier-key copy is not part of the product flow.
- Raw Better Auth `device_code` stays server-side behind portal wrapper endpoints.
- Approval expiry and credential claim/ACK expiry are separate.
- The portal creates the supplier key during credential claim, not during approval.
- The agent must ACK durable credential storage before the portal marks the credential active.
- After ACK, the portal never returns the runtime API key again.
- Rotation and replacement create a new credential only after a Portal Admin-approved replacement flow.
- The portal does not proxy inference and does not collect prompts or outputs.

## Domain Vocabulary

`Customer`
: The tenant in the portal.

`Installer`
: The human at the machine running Nadia CLI commands for a Local Profile.

`Portal Admin`
: The human in the portal who approves, denies, revokes, or replaces a Nadia Agent activation for an authorized Customer.

`Nadia Agents Portal`
: The control plane where Portal Admins approve, replace, revoke, and inspect Nadia Agents.

`Nadia Agent`
: The portal product record for one activated Nadia runtime. This is what admins see, approve, revoke, and attribute cost to.

`Host`
: A physical or virtual machine that can run one or more Nadia Local Profiles.

`Host Label`
: A sanitized, portal-visible display label for the Host. It is for approval context, not identity, and not necessarily the raw hostname, path, or username.

`Local Profile`
: The Nadia runtime container selected by `nadia -p <profile>` or the active profile. It has its own `NADIA_HOME`.

`Profile Label`
: A sanitized, portal-visible display label for the Local Profile. It is for approval context, not identity, and not necessarily the raw profile name, path, or username.

`Profile-Local Identity`
: A stable, high-entropy local ID generated for one Local Profile. It is not the profile name, not the host name, and not a portal secret.

`Activation Request`
: The short-lived portal request created when a Local Profile starts `portal connect`.

`Activation Secret`
: A high-entropy bearer value used for activation polling, claim, or ACK. This includes request handles and claim/ACK tokens. It is not user-facing.

`Portal Runtime Credential`
: The credential returned once during activation so Nadia can call the inference provider path chosen by the portal.

`Portal Binding Metadata`
: Non-secret profile-local metadata that links the Local Profile to the portal Customer, Nadia Agent, credential version, portal environment, and activation/claim correlation IDs.

`Staged Credential`
: A claimed Portal Runtime Credential stored durably before ACK succeeds. Runtime resolution must ignore it until ACK succeeds.

`Credential ACK`
: The agent-side confirmation that the runtime credential was durably stored in the active Local Profile.

## Architecture Position

The implementation should extend Nadia's existing profile, portal CLI, and auth boundaries instead of creating a parallel runtime.

- Use the existing `--profile` / `NADIA_HOME` selection path.
- Add `connect` to the existing `nadia_cli/portal_cli.py` `nadia portal` command group.
- Preserve existing `nadia portal`, `nadia portal login`, `nadia portal info`, `nadia portal open`, and `nadia portal tools` behavior.
- Store profile identity and portal credential under the active `NADIA_HOME`.
- Add a portal-specific resolver path that does not silently read credentials from the global-root fallback.
- Keep Better Auth as a portal implementation detail, not a public agent protocol.
- Keep supplier management inside the portal. The agent should not expose "OpenRouter key management" as its product language.

## Key Decisions

1. `Nadia Agent` is the product noun.
2. `Local Profile` is the runtime noun.
3. One activated Local Profile maps to one active Nadia Agent.
4. One Host can run many Local Profiles and therefore many Nadia Agents.
5. `nadia -p <profile> portal connect` is the main user flow.
6. The command extends the existing `nadia portal` parser.
7. The portal activation flow uses portal wrapper endpoints, not raw Better Auth device-code endpoints.
8. The raw Better Auth `device_code` must never be printed, stored, or passed through user-facing agent code.
9. The portal runtime credential is stored only in the selected Local Profile.
10. Portal runtime credentials must not use the existing global-root auth fallback.
11. Clone/import/export must not duplicate portal identity or portal runtime credentials.
12. The agent stages a claimed credential, ACKs durable storage, then promotes it to active.
13. A denied, expired, revoked, replaced, or rejected activation must be explicit to the Installer.

## Non-Goals

- Do not implement portal billing or cost charts in the agent.
- Do not let the agent create, view, or revoke supplier OpenRouter keys directly.
- Do not build a generic provider marketplace.
- Do not add background check-in, remote command execution, or remote config in this slice.
- Do not add a portal credential-status polling system in this slice.
- Do not send prompts, outputs, files, or session transcripts to the portal as part of activation.
- Do not support profile migration between hosts in v0.
- Do not support out-of-band filesystem copying of activated profiles in v0.

## Main Flow

1. Installer chooses or creates a Local Profile.
2. Installer runs `nadia -p <profile> portal connect`.
3. Nadia generates or loads the profile-local identity for that active profile.
4. Nadia shows the portal-visible metadata summary before starting activation.
5. Nadia asks the portal to start an activation request.
6. Portal returns a user code, verification URL, request handle, expiry, and polling interval.
7. Nadia prints the URL/code, expiry, and human-verifiable activation summary, then polls the portal wrapper endpoint.
8. Portal Admin authenticates in the portal, selects or confirms the Customer, then approves or denies the pending Nadia Agent request.
9. If approved, Nadia receives the bound Customer and Nadia Agent identity from the portal.
10. Nadia claims the runtime credential from the portal.
11. Nadia durably stores the runtime credential as a Staged Credential under the active profile.
12. Nadia ACKs storage to the portal.
13. After ACK succeeds, Nadia promotes the Staged Credential to active.
14. Portal marks the Nadia Agent credential active.
15. Nadia runtime uses the active portal credential for inference.

## Requirements

### Profile Identity And Storage

R1. Nadia must generate one profile-local stable identity for each Local Profile that starts portal activation.

R2. The profile-local identity must be high entropy and stable across normal restarts of the same Local Profile.

R3. The profile-local identity must not be the profile name, host label, username, path, or MAC address.

R4. The profile-local identity must be stored under the active `NADIA_HOME`.

R5. Portal runtime credentials must be stored under the active `NADIA_HOME`.

R6. Portal runtime credentials and Activation Secrets must be persisted with the same or stronger protection as existing auth secrets, including owner-only file permissions.

R7. Nadia must fail closed if safe local credential storage cannot be created.

R8. Portal runtime credentials must not be read from global-root auth fallback or shared credential-pool fallback.

R9. Supported data-movement flows must not duplicate an activated portal identity, Portal Binding Metadata, Staged Credential, or active Portal Runtime Credential.

R10. Profile clone, profile export, whole-home backup, and quick backup outputs must omit portal activation state; restore and `nadia import` must quarantine or invalidate any restored activation state before managed inference can use it.

R11. If a supported data-movement flow creates a new Local Profile or restores an old `NADIA_HOME`, that result must require fresh portal activation before managed inference can use a portal credential.

R12. Out-of-band filesystem copying of an activated `NADIA_HOME` is unsupported in v0. If Nadia can detect copied activation state, it must fail closed and require fresh activation.

### Activation CLI And Metadata

R13. Nadia must expose `nadia portal connect` by extending the existing `nadia_cli/portal_cli.py` portal command group.

R14. `nadia -p <profile> portal connect` must activate the selected profile, using the existing profile preparse and `NADIA_HOME` selection path.

R15. The command must preserve current behavior for existing portal subcommands.

R16. The command must not accept a CLI-supplied Customer identifier as authority for Customer binding.

R17. If the portal approval result lacks exactly one authorized Customer and Nadia Agent binding, the command must fail with clear guidance and must not claim a runtime credential.

R18. The command must show the active Local Profile, portal verification URL, user code, expiry, and clear pending status.

R19. The command must send at least the profile-local identity, Profile Label, Host Label, and Nadia version to the portal start endpoint.

R20. Profile Label, Host Label, and Nadia version must be treated as portal-visible metadata: minimized to what Portal Admins need for approval, sanitized to avoid paths/usernames/secrets by default, and shown before submission.

R21. The CLI must print the same human-verifiable activation summary that the portal approval surface receives: user code, Profile Label, Host Label, Nadia version, and a short non-secret profile identity fingerprint.

R22. After portal approval, the CLI must show the bound Customer and Nadia Agent returned by the portal before claiming the runtime credential.

R23. The command must hold a local activation/replacement lock for the active Local Profile so concurrent `portal connect` processes cannot create competing local activation attempts.

R24. The command must call portal-owned activation endpoints. It must not call the raw Better Auth device-code endpoint directly.

R25. The command must not print, log, or persist raw Better Auth `device_code`.

R26. The command must handle pending, denied, expired, approved, network failure, and retryable server failure states.

R27. Non-test portal activation, polling, claim, ACK, and verification URLs must use HTTPS with certificate validation. Plain HTTP is allowed only for the local test-server fixture.

### Portal Contract Assumptions And Trust Boundary

R28. Nadia must not send a CLI-supplied Customer identifier as authority for Customer binding.

R29. Nadia must treat Customer binding as portal-owned and accept only the Customer and Nadia Agent binding returned by portal wrapper endpoints.

R30. Nadia may claim a runtime credential only when the portal response identifies exactly one bound Customer, one Nadia Agent, and the matching profile-local identity.

R31. If the portal response reports missing, ambiguous, or unauthorized Customer context, Nadia must fail closed before credential claim.

R32. Before approval, duplicate handling keys on the request handle and profile-local identity. After approval, or during replacement, duplicate handling keys on Customer, Nadia Agent, profile-local identity, and lifecycle correlation data. Nadia must resume only the same request handle or fail without claiming another credential.

R33. A repeated local activation attempt for the same pending tuple must attach to the existing pending request or fail without claiming another credential.

R34. Nadia must treat approval, denial, revocation, and replacement as portal-owned decisions and must not expose local commands that bypass Portal Admin authorization.

R35. Nadia must handle Activation Secrets as high-entropy bearer secrets: redact them from logs, persist only what recovery needs, and stop using them after expiry or successful ACK.

R36. Nadia must accept a Portal Runtime Credential only when portal metadata uniquely matches one Customer, one Nadia Agent, one profile-local identity, and one activation lifecycle.

R37. Nadia must treat each Portal Runtime Credential as limited to portal-managed inference and independently revocable or replaceable by the portal.

R38. Nadia must never expect the portal to return the raw runtime credential after successful ACK; if such a response appears, Nadia must reject it and redact it from logs.

### Credential Claim And ACK

R39. After approval, Nadia must claim the portal runtime credential using the activation request handle and profile-local identity.

R40. The claimed portal runtime credential must be written durably as a Staged Credential before Nadia ACKs.

R41. Staged state must include the activation request, claim, ACK, credential identifier, and profile-local correlation data needed for idempotent recovery.

R42. Runtime resolution must ignore Staged Credentials until ACK succeeds.

R43. If durable staged storage fails, Nadia must not ACK.

R44. ACK must be idempotent and restart-safe across lost responses or crashes after the portal accepts ACK but before local promotion.

R45. If a retried ACK receives already-ACKed or already-active from the portal for the same correlation data, Nadia must treat it as success and promote the existing Staged Credential.

R46. If ACK succeeds, Nadia must promote the Staged Credential to active.

R47. After promotion, Nadia must persist Portal Binding Metadata under the active `NADIA_HOME`.

R48. Portal Binding Metadata must include portal base URL/environment, Customer identifier, Nadia Agent identifier, credential identifier/version, profile identity fingerprint, and activation/claim correlation IDs needed for status, replacement, and ACK recovery.

R49. If ACK fails after staged storage succeeds, Nadia must retry ACK without requesting a different runtime credential unless the portal says the claim expired.

R50. If Nadia crashes or restarts after claim but before ACK, it must either resume ACK using persisted activation state or quarantine/delete the Staged Credential on startup.

R51. If the claim expires before ACK, Nadia must fail closed, quarantine/delete the Staged Credential, and require a new activation.

R52. Nadia must not expose the raw runtime credential after successful activation.

### Runtime Behavior

R53. An activated profile must use the active portal runtime credential for managed inference.

R54. Runtime status must identify the active Local Profile and source as `Nadia Agents Portal`.

R55. Runtime status must show the bound Customer and Nadia Agent from Portal Binding Metadata.

R56. Managed inference with a portal runtime credential must not send prompts, outputs, files, memory, sessions, or workspace payloads through the Nadia Agents Portal.

R57. The portal runtime credential must resolve to the provider path selected by the portal without making the Nadia Agents Portal an inference proxy.

R58. Runtime logs must redact runtime credentials and Activation Secrets.

R59. Revocation detection is foreground-only in v0: when managed inference with a portal credential fails with an authentication or authorization error, Nadia must show a clear portal credential rejected/reconnect message.

R60. Revoked, rejected, missing, or inactive portal credentials must not silently fall back to global-root credentials.

R61. Activation code must not send prompts, outputs, memory, sessions, or workspace files to the portal.

### Reconnect And Replacement

R62. Running `nadia portal connect` on an already activated profile must not mint a new runtime credential by default.

R63. Already activated profiles must show current portal connection state, active Local Profile, and the exact replacement/reconnect command.

R64. Replacement must require an explicit local replacement action, such as `nadia portal connect --replace`.

R65. Replacement must require a new Portal Admin-approved activation request.

R66. Replacement activation must bind the local command, portal-approved request, existing Nadia Agent, and current profile-local identity.

R67. Nadia must reject stale, mismatched, or wrong-profile replacement handles.

R68. Replacement must not switch the active runtime credential until the new credential is durably stored, ACKed, and promoted to active.

R69. Failed replacement before credential delivery must leave the previous working credential active unless the portal has revoked it.

R70. Failed replacement after the portal returns a replacement credential must retry the same pending replacement and warn that the previous portal credential may already be retired; after successful replacement ACK, Nadia must mark the old local credential replaced or quarantined and must not keep using it.

### Multi-Profile Host Behavior

R71. Two Local Profiles on the same Host must be able to activate independently.

R72. Two Local Profiles on the same Host must have different profile-local identities.

R73. Two Local Profiles on the same Host must not share portal runtime credentials.

R74. Status and diagnostics must make the active Local Profile clear enough to avoid Installer confusion.

### Testing And Verification

R75. Tests must use temporary `NADIA_HOME` directories to prove profile-local behavior.

R76. Tests must prove `connect` extends the existing portal command group without breaking existing portal subcommands.

R77. Tests must cover Customer binding: missing, ambiguous, unauthorized, and valid Customer context.

R78. Tests must cover the happy path: start, pending, approve, claim, staged store, ACK, promote active, persist Portal Binding Metadata, runtime resolve.

R79. Tests must cover two profiles on one host activating to two different Nadia Agents.

R80. Tests must cover concurrent `portal connect` attempts for one Local Profile without duplicate credential minting.

R81. Tests must cover data-movement safety: profile clone/export, whole-home backup, quick backup, restore, and `nadia import` cannot reuse the source portal identity or credential.

R82. Tests must cover global-root fallback safety: an activated portal profile never reads another profile's credential through fallback.

R83. Tests must cover safe-storage failure before ACK.

R84. Tests must cover ACK retry, already-ACKed recovery, and crash/restart recovery after successful staged storage.

R85. Tests must cover expired claim cleanup or quarantine.

R86. Tests must cover portal credential rejected/reconnect behavior with no silent fallback.

R87. Tests must cover no-proxy runtime behavior: prompts, outputs, files, memory, sessions, and workspace payloads do not pass through the Nadia Agents Portal.

R88. Tests must cover replacement correlation: wrong profile, stale handle, successful ACK, and failed ACK.

R89. Tests must cover redaction for runtime credentials, Activation Secrets, and raw Better Auth device codes.

R90. Tests must use a real local HTTP test server for the portal contract. Use mocks only for narrow failure injection that cannot be expressed through the server.

R91. Verification evidence for the implementation plan must include real CLI transcripts with secrets redacted.

R92. Any release exposing `nadia portal connect` must update public activation docs to use `Nadia Agent` and `Local Profile` consistently and remove stale `Nadia Instance` activation/check-in wording.

## Acceptance Examples

### AE1: New Activation

Given a fresh Local Profile, when the Installer runs `nadia -p sales portal connect`, the CLI shows the active profile, portal URL, user code, expiry, and activation summary. After the Portal Admin approves and binds the request to a Customer, Nadia shows the bound Customer and Nadia Agent, stores the returned runtime credential as staged, ACKs storage, promotes it to active, persists Portal Binding Metadata, and `nadia -p sales status` reports `Nadia Agents Portal` inference ready.

### AE2: Many Profiles On One Host

Given `sales` and `support` profiles on the same laptop, when both run portal activation, the portal sees two separate Nadia Agents. Each profile has its own local identity and its own runtime credential. Deleting or revoking one does not affect the other.

### AE3: Clone Safety

Given an activated `sales` profile, when the Installer clones it to `sales-demo` through supported Nadia commands, the cloned profile does not inherit the source portal identity or portal runtime credential. `sales-demo` must run a fresh portal activation.

### AE4: Replacement

Given an activated profile, when the Installer runs the explicit replacement command and the Portal Admin approves the new request, Nadia stages and ACKs the new credential before switching. If failure happens before credential delivery, the previous local credential remains active unless already revoked by the portal. If failure happens after replacement credential delivery, Nadia retries the same pending replacement and does not silently fall back.

### AE5: Credential Rejected

Given an activated profile, when managed inference using the portal credential returns an authentication or authorization failure, Nadia shows a portal credential rejected/reconnect message. Nadia does not use any fallback global credential.

### AE6: Redaction

Given activation succeeds or fails, command output, logs, status, and test artifacts never include raw runtime credentials, Activation Secrets, or raw Better Auth device codes.

## Open Planning Questions

These must be decided during the agent implementation plan, not hidden inside code:

1. Should portal identity and credential live inside `auth.json`, a new profile-local portal file, or both?
2. What exact portal endpoint names and JSON shapes will the agent consume?
3. What is the exact local test-server fixture shape for portal activation contract tests?
4. How should the portal resolver integrate with existing Nous runtime credential resolution without reusing global fallback?

## Success Criteria

- A future implementation plan can be written from this document without inventing the portal activation model.
- The agent-side flow never requires copying an OpenRouter key manually.
- The active Local Profile is the only local boundary for portal identity and runtime credential storage.
- ACK failure, crash, and expired claim cannot leave a usable orphan credential.
- Clone/import/export cannot accidentally duplicate an activated portal agent.
- Replacement cannot switch the wrong Local Profile or wrong Nadia Agent.
- The implementation can be tested with real local HTTP flows and temporary Nadia homes.
