#!/usr/bin/env bash
# nadia — tag + push the local builder image to ghcr.io/nadicodeai/nadia.
#
# Maps to spec FR-7 (image tagging conventions), FR-11 (Docker-only —
# no PyPI), plan M5.2, OQ-13 (GHCR token handling).
#
# SCOPE (issue #2). This script is the LOCAL MAINTAINER convenience for
# pushing the SLIM variant only (built by `make image` -> :dev). CI's
# `.github/workflows/docker-publish.yml` is the source of truth for the
# two-variant tag scheme (slim + full) and bypasses this script. A local
# maintainer pushing via `make publish` thus emits slim-variant images
# under the legacy bare-tag scheme (:<sha>, :latest); that is intentional
# for hot-fix flows where waiting on CI is not viable. Push the full
# variant by triggering the workflow (workflow_dispatch), not via this
# script.
#
# Tag-decision tree (FR-7).
#   :dev                Local builder. NEVER pushed (built by `make image`).
#   :<git-sha-short>    Pushed on every successful publish (main builds + releases).
#   :latest             Pushed when on `main` AND working tree clean.
#   :v<X.Y.Z>           Pushed when a `vX.Y.Z` git tag points at HEAD.
#
# Auth.
#   Requires $GHCR_TOKEN in the env. In CI this is `${{ secrets.GITHUB_TOKEN }}`
#   piped to `docker login ghcr.io` by the calling workflow before this script
#   runs. Locally, the maintainer exports a PAT scoped to write:packages
#   (spec OQ-13) and either:
#     (a) runs `echo "$GHCR_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin`
#         before invoking this script, or
#     (b) lets this script run `docker login` itself when $GHCR_USER is set.
#
# Refusals.
#   1. Working tree dirty (git status --porcelain non-empty) -> exit 2.
#   2. Source image `ghcr.io/nadicodeai/nadia:dev` missing -> exit 3
#      (run `make image` first).
#   3. $GHCR_TOKEN unset AND not already logged in to ghcr.io -> exit 4.
#
# Exit codes
#   0 success
#   1 generic / argparse
#   2 dirty tree
#   3 missing source image
#   4 missing auth
#
# Usage.
#   scripts/publish.sh             # main flow
#   scripts/publish.sh --help      # usage
#   scripts/publish.sh --dry-run   # print tags + push commands, do not push

set -euo pipefail

readonly IMAGE_REPO="ghcr.io/nadicodeai/nadia"
readonly SOURCE_TAG="${IMAGE_REPO}:dev"

usage() {
    cat <<EOF
scripts/publish.sh — tag + push nadia image to ghcr.io

Usage:
  scripts/publish.sh [--dry-run] [--help|-h]

Preconditions:
  1. \`make image\` has run; ${SOURCE_TAG} exists locally.
  2. Working tree is clean (git status --porcelain empty).
  3. GHCR auth: either you have run \`docker login ghcr.io\` already, OR
     \$GHCR_TOKEN is set (with \$GHCR_USER, optional, defaulting to the
     current GitHub user resolved by \`gh api user --jq .login\`).

Tags applied (spec FR-7):
  :<git-sha-short>       always
  :latest                only when HEAD is on branch \`main\` and tree clean
  :v<X.Y.Z>              only when a vX.Y.Z git tag points at HEAD

Environment:
  GHCR_TOKEN   GitHub PAT scoped to write:packages (or GITHUB_TOKEN in CI)
  GHCR_USER    Username for docker login (default: \$GITHUB_ACTOR or gh user)
  GHCR_SKIP_LOGIN  Set to "1" to skip \`docker login\` (assume already logged in)

Exit codes: 0 ok | 2 dirty tree | 3 missing image | 4 missing auth | 1 other
EOF
}

# ------- argparse -----------------------------------------------------------

DRY_RUN=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --help|-h) usage; exit 0 ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo "publish.sh: unknown argument: $1" >&2; usage >&2; exit 1 ;;
    esac
done

# ------- preconditions ------------------------------------------------------

# 1. Tree must be clean. Dirty trees mean the image we built no longer
#    matches the SHA we'd be tagging it as. Catches: forgotten edits,
#    half-staged refresh, partial overlay touch-up.
if [ -n "$(git status --porcelain)" ]; then
    echo "publish.sh: refusing to push — working tree is dirty." >&2
    echo "Commit, stash, or clean before publishing. \`git status\` for details." >&2
    exit 2
fi

# 2. Source image must exist. We re-tag the local :dev image; we do NOT
#    rebuild here (that's `make image`'s job; this script is push-only).
if ! docker image inspect "${SOURCE_TAG}" >/dev/null 2>&1; then
    echo "publish.sh: ${SOURCE_TAG} not found locally." >&2
    echo "Run \`make image\` first." >&2
    exit 3
fi

# 3. Auth. Either we're already logged in (skip) or we have $GHCR_TOKEN.
#    GHCR_SKIP_LOGIN=1 short-circuits the check for callers (CI) that
#    handle login themselves via docker/login-action.
if [ "${GHCR_SKIP_LOGIN:-0}" != "1" ]; then
    if [ -z "${GHCR_TOKEN:-}" ]; then
        echo "publish.sh: \$GHCR_TOKEN is not set." >&2
        echo "" >&2
        echo "Either:" >&2
        echo "  (a) export GHCR_TOKEN=<PAT with write:packages> and re-run," >&2
        echo "  (b) docker login ghcr.io  (interactive)  and re-run with" >&2
        echo "      GHCR_SKIP_LOGIN=1 scripts/publish.sh, or" >&2
        echo "  (c) in CI, use docker/login-action@v3 before this script and" >&2
        echo "      set GHCR_SKIP_LOGIN=1." >&2
        echo "" >&2
        echo "Spec OQ-13: PAT MUST be scoped to write:packages only." >&2
        exit 4
    fi

    # Resolve username. In GH Actions, GITHUB_ACTOR is set. Locally we try
    # `gh api user`; fall back to the env's USER as a last resort.
    if [ -z "${GHCR_USER:-}" ]; then
        if [ -n "${GITHUB_ACTOR:-}" ]; then
            GHCR_USER="${GITHUB_ACTOR}"
        elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
            GHCR_USER="$(gh api user --jq .login 2>/dev/null || true)"
        fi
        GHCR_USER="${GHCR_USER:-${USER:-}}"
    fi

    if [ -z "${GHCR_USER:-}" ]; then
        echo "publish.sh: unable to determine GHCR username." >&2
        echo "Set GHCR_USER explicitly." >&2
        exit 4
    fi

    if [ "${DRY_RUN}" -eq 0 ]; then
        echo "publish.sh: logging into ghcr.io as ${GHCR_USER}"
        echo "${GHCR_TOKEN}" | docker login ghcr.io \
            --username "${GHCR_USER}" --password-stdin
    else
        echo "[dry-run] would docker login ghcr.io --username ${GHCR_USER}"
    fi
fi

# ------- tag computation ----------------------------------------------------

GIT_SHA_SHORT="$(git rev-parse --short HEAD)"
GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Release tag detection: does any `vX.Y.Z` git tag point at HEAD?
# `git tag --points-at HEAD` returns the tag names; we filter for the
# strict vMAJOR.MINOR.PATCH shape spec'd in FR-7. A repo may have
# unrelated tags pointed at the same commit; we only honor versioned ones.
VERSION_TAG="$(git tag --points-at HEAD | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -n1 || true)"

# Always: tag :<sha-short>.
TAGS_TO_PUSH=("${IMAGE_REPO}:${GIT_SHA_SHORT}")

# :latest only on main. Per FR-7 the customer-facing "latest" pointer is
# defined to track main; release tags update it explicitly via the
# workflow (see docker-publish.yml release branch).
if [ "${GIT_BRANCH}" = "main" ]; then
    TAGS_TO_PUSH+=("${IMAGE_REPO}:latest")
fi

# :v<X.Y.Z> when a version tag points at HEAD.
if [ -n "${VERSION_TAG}" ]; then
    TAGS_TO_PUSH+=("${IMAGE_REPO}:${VERSION_TAG}")
fi

# ------- tag + push ---------------------------------------------------------

echo "publish.sh: source = ${SOURCE_TAG}"
echo "publish.sh: SHA    = ${GIT_SHA_SHORT}  branch=${GIT_BRANCH}  vtag=${VERSION_TAG:-<none>}"
echo "publish.sh: tags   = ${TAGS_TO_PUSH[*]}"

for tag in "${TAGS_TO_PUSH[@]}"; do
    if [ "${DRY_RUN}" -eq 1 ]; then
        echo "[dry-run] docker tag ${SOURCE_TAG} ${tag}"
        echo "[dry-run] docker push ${tag}"
    else
        docker tag "${SOURCE_TAG}" "${tag}"
        docker push "${tag}"
    fi
done

echo "publish.sh: done."
