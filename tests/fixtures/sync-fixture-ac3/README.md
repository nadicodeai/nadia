# sync-fixture-ac3/

Reproducibility fixture for spec **AC-3** (single non-overlapping patch
sync). Distinct from `sync-fixture-200/` (which exercises AC-2, the
zero-conflict pristine sync with an empty patch series).

**Scenario:** `patches/series` contains one fork patch that adds a
`cmd_new_flag` function at the tail of `baseline.py`; upstream refactors
`cmd_existing` near the head of the same file. Because the two edits
target disjoint line ranges, `quilt push -a` against the refactored
upstream tree MUST succeed without manual intervention.

## Why synthetic

The fixture is intentionally a synthetic 3-file tree (single Python
module, minimal `pyproject.toml`, minimal `README.md`) rather than a
slice of real `hermes-agent`. Spec AC-3 is a property of the
patch-vs-refactor *geometry*, not of any specific upstream file — the
synthetic baseline lets us pin the exact line ranges of the two edits
and verify non-overlap by inspection. The fixture is also tiny
(<1 KB compressed) so it never grows into a Git LFS candidate.

## Contents

- **`baseline-tree.tar.zst`** — deterministic zstd-compressed tarball of
  a 3-file synthetic upstream worktree (`baseline.py`, `pyproject.toml`,
  `README.md`). Built with
  `tar --sort=name --mtime='2020-01-01' --owner=0 --group=0 --numeric-owner`
  piped through `zstd --ultra -22` so two engineers re-recording the
  fixture get byte-identical bytes.
- **`upstream-refactor.patch`** — `diff -up --git` patch (no `index`
  line, no timestamps) that simulates an upstream-side refactor of
  `baseline.py`. Touches lines 3–10 of the baseline only.
- **`fork-flag.patch`** — quilt-style `diff -up --git` patch (no
  `index`, no timestamps) that adds a `cmd_new_flag` function after
  `main()`. Authored against the baseline; its hunk context spans
  lines 14–18 of the baseline.
- **`asserts.txt`** — grep patterns that MUST appear in the final
  baseline.py after both patches are applied. Mirrors the
  `patches/asserts/<patch>.txt` convention from FR-14.
- **`README.md`** — this file.

## Line geometry (proves non-overlap)

`baseline.py` is 18 lines. The two edits target disjoint ranges:

| Patch                    | Hunk header   | Baseline lines touched | Region of file        |
|--------------------------|---------------|------------------------|-----------------------|
| `upstream-refactor.patch`| `@@ -3,8 +3,14 @@` | lines 3–10            | head: `cmd_existing`  |
| `fork-flag.patch`        | `@@ -14,5 +14,11 @@` | lines 14–18           | tail: after `main()`  |

Lines 11–13 (the `main()` definition and body) are context for the fork
patch but unchanged by both. There is no overlap between the two hunks'
target line ranges, which is exactly the AC-3 hypothesis.

## Smoke check (manual)

```bash
# Extract baseline into a scratch tree
SCRATCH=$(mktemp -d)
cd "$SCRATCH"
tar --use-compress-program=unzstd \
    -xf /path/to/tests/fixtures/sync-fixture-ac3/baseline-tree.tar.zst
git init -q && git add -A && git commit -q -m baseline

# Apply the upstream refactor (simulates a future upstream HEAD)
git apply --check /path/to/tests/fixtures/sync-fixture-ac3/upstream-refactor.patch
git apply        /path/to/tests/fixtures/sync-fixture-ac3/upstream-refactor.patch
git add -A && git commit -q -m "upstream refactor"

# Now try applying the fork patch via quilt — should succeed cleanly,
# even though the patch was authored against the pre-refactor file.
mkdir patches
cp /path/to/tests/fixtures/sync-fixture-ac3/fork-flag.patch patches/
echo fork-flag.patch > patches/series
QUILT_PATCHES=patches quilt push -a
echo "exit=$?"  # 0
test -z "$(find . -name '*.rej' -o -name '*.orig')"  # no rejects
```

Expected: `quilt push -a` prints `Hunk #1 succeeded at <line> (offset N
lines).` and exits 0. The hunk shifts because the refactor added lines
above its context, but the *context* lines themselves are unchanged so
quilt finds them and applies cleanly.

## Test consumer

`overlay/tests/test_sync_fixture_ac3.py` (M4.2a) exercises this fixture
end-to-end and asserts:

- `quilt push -a` exit code 0.
- No `.rej` or `.orig` files left behind.
- The final `baseline.py` contains BOTH the refactor markers
  (`_existing_message`, `verbose=False`) AND the fork addition
  (`cmd_new_flag`, the fork's print string).
- Patterns in `asserts.txt` all appear in the final file.

Marked `@pytest.mark.integration`; default `pytest` runs skip it.
