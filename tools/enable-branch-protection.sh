#!/usr/bin/env bash
# Apply main-branch protection to nadicodeai/argo (issue #5).
#
# Prerequisite: the repository must be PUBLIC, on a GitHub Pro plan, or on
# a Team / Enterprise plan. GitHub Free does NOT expose branch-protection
# APIs on private repos (HTTP 403 on both the legacy
# `/repos/.../branches/main/protection` and the modern
# `/repos/.../rulesets` endpoints).
#
# Required CI checks below mirror ci.yml's job `name:` fields.
#
# Behavior: PUTs the protection ruleset and prints the resulting config.
# Idempotent — re-running just overwrites with the same payload.

set -euo pipefail

REPO="${REPO:-nadicodeai/argo}"
BRANCH="${BRANCH:-main}"

REQUIRED_CHECKS=(
  "lint (ruff)"
  "typecheck (ty)"
  "build (make build)"
  "leakage (static scan)"
  "test (pytest)"
  "upstream-pristine (FR-15)"
)

# Build the JSON checks array.
checks_json="["
for i in "${!REQUIRED_CHECKS[@]}"; do
  [ "$i" -gt 0 ] && checks_json+=","
  checks_json+="{\"context\":\"${REQUIRED_CHECKS[$i]}\"}"
done
checks_json+="]"

payload=$(cat <<JSON
{
  "required_status_checks": {
    "strict": true,
    "checks": $checks_json
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "required_linear_history": false
}
JSON
)

echo "Applying branch protection to $REPO@$BRANCH ..."
echo "$payload" | gh api -X PUT "/repos/$REPO/branches/$BRANCH/protection" --input -
echo "Done. Verify in Settings -> Branches."
