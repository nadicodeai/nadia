# sync-fixture-200/

Reproducibility fixture for spec AC-2 (zero-conflict pristine sync) and
M4.2's `test_sync_fixture.py`. Records a baseline upstream tree + the
forward delta to a target HEAD, so the sync workflow can be exercised
deterministically without depending on the live upstream remote.

## Contents

- **`baseline-tree.tar.zst`** — zstd-compressed tarball of the
  hermes-agent worktree at `BASELINE-SHA` (below). Excludes `.git/`.
  Compressed with `zstd --ultra -22 --sort=name --mtime='2020-01-01' --owner=0 --group=0 --numeric-owner`
  for deterministic bytes.
- **`upstream-200-files.patch`** — `git diff --binary BASELINE-SHA HEAD-SHA`.
  Applies cleanly to the extracted baseline tree (verified by smoke check).
- **`README.md`** — this file.

## SHAs

- **HEAD-SHA**: `a890389b69575916dfaf3980556f31f7f25c9871`
  (matches `upstream/.commit` at the time of fixture creation).
- **BASELINE-SHA**: `b6ca56f651505d6a8ec2489f1048da3d2c07d12e`
  (50 commits behind HEAD-SHA in hermes-agent `main`).
- **File count**: **157 files changed** in the BASELINE→HEAD delta
  (≥100 required for the G1 sync-sanity gate).
- **Recorded**: 2026-05-27.

## Usage

`overlay/tests/test_sync_fixture.py` (M4.2) consumes this fixture by:

1. Creating a temporary scratch directory.
2. Extracting `baseline-tree.tar.zst` into it.
3. `git init` + initial commit of the baseline tree to create a
   tag-able anchor.
4. Optionally registering it as a local "upstream" remote for
   `tools/sync.py --upstream-url file:///tmp/scratch/.git`.
5. Running `make sync` to apply `upstream-200-files.patch` as the
   forward delta.
6. Asserting the resulting tree's `make build && make leakage-static`
   exits 0 and produces a clean `dist/nadia/`.

## Smoke check (manual)

```bash
mkdir -p /tmp/smoke && cd /tmp/smoke
tar -xf /path/to/baseline-tree.tar.zst --use-compress-program=unzstd
git init -q && git add -A && git commit -q -m baseline
git apply --check /path/to/upstream-200-files.patch
echo $?  # 0 if patch applies cleanly
```

## Size

The tarball is ~25 MB compressed (≈80 MB uncompressed). This is large
but acceptable for a one-time fixture. If it becomes painful (CI clone
times, etc.), migrate to Git LFS in a follow-up commit. Re-recording
the fixture requires updating BASELINE-SHA + HEAD-SHA together (and
re-running the smoke check).

## Why baseline-tree is required

A `git diff BASELINE→HEAD` patch CANNOT apply against `upstream/`
(which is already at HEAD). The fixture MUST provide the older starting
tree so M4.2's test can place the simulated upstream replica at the
baseline before running `make sync` forward to HEAD.
