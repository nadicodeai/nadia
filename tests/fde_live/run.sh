#!/usr/bin/env bash
# Live acceptance for provided Telegram and Honcho credentials.

set -euo pipefail

PROFILE="${FDE_PROFILE:-fde-live-smoke}"
HONCHO_WORKSPACE="${FDE_HONCHO_WORKSPACE:-nadia-fde-live}"
HONCHO_PEER="${FDE_HONCHO_PEER:-fde-smoke}"
HONCHO_API_KEY="${FDE_HONCHO_API_KEY:-}"
HONCHO_BASE_URL="${FDE_HONCHO_BASE_URL:-}"
TELEGRAM_TOKEN="${FDE_TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_ALLOWED_USERS="${FDE_TELEGRAM_ALLOWED_USERS:-}"
TELEGRAM_HOME_CHANNEL="${FDE_TELEGRAM_HOME_CHANNEL:-}"

missing=()
[ -n "${HONCHO_API_KEY}" ] || missing+=(FDE_HONCHO_API_KEY)
[ -n "${TELEGRAM_TOKEN}" ] || missing+=(FDE_TELEGRAM_BOT_TOKEN)
[ -n "${TELEGRAM_ALLOWED_USERS}" ] || missing+=(FDE_TELEGRAM_ALLOWED_USERS)
if [ "${#missing[@]}" -gt 0 ]; then
    printf 'fde-live: missing required env: %s\n' "${missing[*]}" >&2
    exit 77
fi

args=(
    --profile "${PROFILE}"
    --honcho-workspace "${HONCHO_WORKSPACE}"
    --honcho-peer "${HONCHO_PEER}"
    --honcho-api-key "${HONCHO_API_KEY}"
    --telegram-token "${TELEGRAM_TOKEN}"
    --telegram-allowed-users "${TELEGRAM_ALLOWED_USERS}"
    --yes
)
[ -z "${HONCHO_BASE_URL}" ] || args+=(--honcho-base-url "${HONCHO_BASE_URL}")
[ -z "${TELEGRAM_HOME_CHANNEL}" ] || args+=(--telegram-home-channel "${TELEGRAM_HOME_CHANNEL}")

nadia-customer-init "${args[@]}"

nadia -p "${PROFILE}" --version
nadia -p "${PROFILE}" honcho status
nadia -p "${PROFILE}" gateway status

printf 'fde-live: PASSED profile=%s\n' "${PROFILE}"
