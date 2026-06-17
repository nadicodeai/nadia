#!/usr/bin/env bash
# Update-smoke harness — Part B: Telegram /update mid-flight (IU-AC-6).
#
# Goal: boot nadia in a container, point its gateway at the localhost
# FakeTelegramServer, inject `/update`, observe the bot's reply, then
# (best-effort) verify the post-restart banner.
#
# STATUS: BLOCKED — exits 77 (autotools "skip"). See "Blocker" below.
# Part A (tests/update_smoke/run.sh) closes IU-AC-9 (full), IU-AC-10,
# IU-AC-11. Part B is deferred; promoting IU-AC-6 to M6 (parity surfaces)
# or a dedicated milestone is acceptable per the M5.3 dispatch note.
#
# Blocker
# -------
# A real end-to-end Telegram /update test needs five concurrent pieces:
#
#   1. The FakeTelegramServer running on the host on 127.0.0.1:<port>
#      with `extra.base_url` wired into the gateway's config — this part
#      is doable (M5.1 docstring lines 12-41 confirms PTB's
#      builder.base_url() honours custom HTTP endpoints; the rewrite
#      lands in upstream/gateway/platforms/telegram.py:1481-1490).
#
#   2. nadia running in a Docker container with `--network host` so it
#      can reach the host-bound fake on 127.0.0.1 — doable, but Docker
#      Desktop on macOS doesn't expose host networking; CI on linux is
#      OK. Tractable.
#
#   3. A configured TELEGRAM_BOT_TOKEN in `~/.nadia/.env` and a gateway
#      profile pointing at the fake's URL. The setup wizard is
#      interactive (upstream/hermes_cli/setup.py:_setup_telegram
#      line ~1831); bypassing it requires either driving the wizard
#      non-interactively or writing the config files directly. The
#      direct-write path is undocumented and brittle — a future
#      upstream refactor of the YAML schema would silently break the
#      harness without `parity_runner` catching it.
#
#   4. A running gateway. `nadia gateway run` runs in the foreground
#      (upstream/hermes_cli/main.py:11306) so we can background it
#      with `&` — fine. BUT cmd_update's restart path
#      (upstream/hermes_cli/main.py:9367-9383) ends with a systemd
#      `systemctl restart` call. Vanilla `ubuntu:22.04` has no
#      systemd; the restart is a no-op and the bot never reconnects
#      with the new code. The post-restart banner assertion that
#      IU-AC-6 demands therefore cannot fire on a non-systemd host
#      without re-engineering: either the test image needs to be
#      `jrei/systemd-ubuntu` (privileged container with /sys/fs/cgroup
#      bind-mount), OR cmd_update needs an "in-process restart" path
#      that nadia doesn't currently have (and adding one would be a
#      behavioural divergence from hermes — forbidden by IU-FR-8).
#
#   5. A working LLM provider key so the gateway doesn't crash on
#      startup when handling /update — actually safe: /update is a
#      built-in gateway command that short-circuits before the LLM
#      path, but a missing provider key still trips gateway config
#      validation in some code paths.
#
# Item 4 is the load-bearing blocker. Closing it cleanly requires
# either (a) switching the smoke image to a systemd-capable base
# (`jrei/systemd-ubuntu`) and running with `--privileged -v
# /sys/fs/cgroup:/sys/fs/cgroup:rw`, which has its own CI/security
# concerns, or (b) accepting that IU-AC-6 lives in a higher-fidelity
# integration tier (a real VPS-style runner) rather than a per-PR
# smoke test. Either choice is a scope expansion — coordinator's call.
#
# What this script DOES today
# ---------------------------
# Exits 77 (skipped) immediately, with the BLOCKED reason printed to
# stderr. Wired up to the M5.3 Makefile target so `make
# update-smoke-telegram` treats 77 as "skipped, not failed" (matches
# autotools convention).
#
# Spec:  .shepherd/install-update/spec.md § IU-AC-6, IU-AC-8 (partial)
# Plan:  .shepherd/install-update/plan.md § M5.3 Part B
# M5.1:  tests/update_smoke/fake_telegram.py docstring lines 12-41

set -euo pipefail

readonly EXIT_SKIP=77

cat >&2 <<'EOF'
=== M5.3 update-smoke (Part B: Telegram /update mid-flight) ===
BLOCKED: skipping IU-AC-6 end-to-end test (exit 77).

Reason: vanilla ubuntu:22.04 has no systemd, so cmd_update's
`systemctl restart` step is a no-op and the post-restart banner
assertion cannot fire. Closing this cleanly requires either a
systemd-capable container base (privileged) or a higher-fidelity
runner — both are scope expansions documented in this script's
header comment.

What IS exercised by Part A (tests/update_smoke/run.sh):
  - IU-AC-9  (full) : no "Updating from fork" warning on nadia update.
  - IU-AC-10        : NADIA_MANAGED=1 prints "is managed by" to stderr.
  - IU-AC-11        : pre_update_backup writes a zip; nadia import restores.

IU-AC-6 and IU-AC-8 (partial Telegram mid-flight) remain open.
Promote to M6 (parity surfaces, where the cmd-update surface diffs
the full update log against hermes) or to a dedicated milestone with
a systemd-capable runner.
EOF

exit "$EXIT_SKIP"
