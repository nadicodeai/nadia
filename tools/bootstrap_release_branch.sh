#!/usr/bin/env bash
# tools/bootstrap_release_branch.sh
#
# One-shot helper: seed the long-lived `release` branch on `nadicodeai/argo`
# with the renamed `dist/argo/` tree. Closes M2.2 (IU-FR-3, IU-AC-2, IU-AC-3).
#
# Architecture (see .shepherd/install-update/standards.md):
#   - `main` is the workshop (upstream/, patches/, overlay/, tools/, .shepherd/).
#   - `release` is the storefront (renamed dist/argo/ contents only).
#   - dist/argo/ is gitignored; force-push to release is the only way it lands
#     on a tracked git ref.
#   - Force-push uses --force-with-lease, never --force.
#
# Usage:
#   tools/bootstrap_release_branch.sh                  # do it for real
#   tools/bootstrap_release_branch.sh --dry-run        # build + stage, skip push
#   tools/bootstrap_release_branch.sh --remote upstream-fork
#   tools/bootstrap_release_branch.sh --branch release-test
#
# Hard constraints:
#   - Refuses to run if `dist/argo/` is missing after `make build`.
#   - Reads commit author identity from existing global git config; NEVER
#     writes `git config --global` (that would mutate the operator's env).
#   - Pushes using the *origin repo's* remote URL (resolved via
#     `git remote get-url <remote>` in the original repo), NOT the scratch
#     clone's remote.

set -euo pipefail

# ----------------------------------------------------------------------------
# Defaults / argument parsing
# ----------------------------------------------------------------------------
DRY_RUN=0
REMOTE="origin"
BRANCH="release"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run] [--remote <name>] [--branch <name>]

Options:
  --dry-run         Build + stage the scratch dir; print state; skip push.
  --remote <name>   Git remote in the workshop repo whose URL we push to
                    (default: origin).
  --branch <name>   Target branch name on the remote (default: release).
  -h, --help        Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --remote)
      REMOTE="${2:?--remote requires an argument}"
      shift 2
      ;;
    --branch)
      BRANCH="${2:?--branch requires an argument}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# ----------------------------------------------------------------------------
# Locate repo root
# ----------------------------------------------------------------------------
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

echo "==> bootstrap_release_branch.sh"
echo "    repo root: $REPO_ROOT"
echo "    remote:    $REMOTE"
echo "    branch:    $BRANCH"
echo "    dry-run:   $DRY_RUN"
echo

# ----------------------------------------------------------------------------
# Resolve remote URL from the workshop repo (NOT the scratch dir)
# ----------------------------------------------------------------------------
REMOTE_URL="$(git remote get-url "$REMOTE")"
echo "==> resolved remote URL: $REMOTE_URL"
echo

# ----------------------------------------------------------------------------
# Resolve commit author identity from EXISTING git config (no writes)
# ----------------------------------------------------------------------------
AUTHOR_NAME="$(git config --get user.name || true)"
AUTHOR_EMAIL="$(git config --get user.email || true)"
if [[ -z "$AUTHOR_NAME" || -z "$AUTHOR_EMAIL" ]]; then
  echo "error: git user.name and user.email must be set globally (or in repo)" >&2
  echo "       refusing to fabricate identity." >&2
  exit 3
fi
echo "==> commit author: $AUTHOR_NAME <$AUTHOR_EMAIL>"
echo

# ----------------------------------------------------------------------------
# Build (loud failure if either step exits non-zero)
# ----------------------------------------------------------------------------
echo "==> make build"
make build
echo

echo "==> make leakage-static"
make leakage-static
echo

# ----------------------------------------------------------------------------
# Sanity: dist/argo/ must exist after build
# ----------------------------------------------------------------------------
DIST_DIR="$REPO_ROOT/dist/argo"
if [[ ! -d "$DIST_DIR" ]]; then
  echo "error: $DIST_DIR is missing after make build; aborting" >&2
  exit 4
fi
echo "==> dist/argo/ present"
echo

# Capture the main SHA for the commit message
MAIN_SHA="$(git rev-parse HEAD)"
echo "==> workshop HEAD SHA: $MAIN_SHA"
echo

# ----------------------------------------------------------------------------
# Scratch dir setup
# ----------------------------------------------------------------------------
SCRATCH_PARENT="$REPO_ROOT/.sync-workdir/release-bootstrap"
SCRATCH="$SCRATCH_PARENT/repo"

echo "==> preparing scratch dir at $SCRATCH"
rm -rf "$SCRATCH_PARENT"
mkdir -p "$SCRATCH"

# `cp -a dist/argo/. <scratch>/` copies contents (including dotfiles) WITHOUT
# nesting dist/argo/ inside scratch — the renamed tree becomes the repo root.
cp -a "$DIST_DIR/." "$SCRATCH/"
echo "==> copied $(find "$SCRATCH" -mindepth 1 -maxdepth 1 | wc -l) top-level entries"
echo

# ----------------------------------------------------------------------------
# Initialise an orphan branch inside the scratch dir
# ----------------------------------------------------------------------------
(
  cd "$SCRATCH"
  git init -q
  # Set local identity on the scratch repo only (NOT --global). This way the
  # commit is authored correctly without mutating the operator's env.
  git config user.name "$AUTHOR_NAME"
  git config user.email "$AUTHOR_EMAIL"
  git checkout --orphan "$BRANCH" -q
  git add -A
  git commit -q -m "release: initial bootstrap from dist/argo/ at $MAIN_SHA"
)

SCRATCH_SHA="$(git -C "$SCRATCH" rev-parse HEAD)"
echo "==> scratch commit SHA: $SCRATCH_SHA"
echo

# ----------------------------------------------------------------------------
# Dry-run short-circuit
# ----------------------------------------------------------------------------
if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "==> [DRY RUN] scratch dir state:"
  echo "    path:     $SCRATCH"
  echo "    branch:   $BRANCH"
  echo "    commit:   $SCRATCH_SHA"
  echo "    files:"
  (cd "$SCRATCH" && git ls-files | head -30 | sed 's/^/      /')
  TOTAL="$(cd "$SCRATCH" && git ls-files | wc -l)"
  echo "    (total tracked files: $TOTAL)"
  echo
  echo "==> [DRY RUN] skipping push to $REMOTE_URL"
  exit 0
fi

# ----------------------------------------------------------------------------
# Force-push (with-lease) the orphan branch to the workshop repo's remote URL
# ----------------------------------------------------------------------------
echo "==> pushing $BRANCH to $REMOTE_URL (--force-with-lease)"
git -C "$SCRATCH" push --force-with-lease "$REMOTE_URL" "$BRANCH:$BRANCH"
echo
echo "==> done. release branch SHA = $SCRATCH_SHA"
