# argo Standards

Coding, repository, and process standards for the `nadicodeai/argo` repo. These are derived from the upstream `hermes-agent` standards (inherited verbatim where they apply) plus fork-specific rules added by this repo's architecture (`upstream/` pristine + `patches/` + `overlay/` + build-time rename).

**Authoritative documents.** Read these as a triple:

1. **`.shepherd/spec.md`** — what we're building and why. Contracts and acceptance criteria.
2. **`.shepherd/plan.md`** — ordered, verified tasks (M1.x → M8.x). Each task has explicit acceptance criteria and verification commands.
3. **`.shepherd/standards.md`** — this file. How code looks, how the repo is laid out, what's allowed.

Conflicts: spec > plan > standards. If you find drift, fix the lower doc, not the higher one.

---

## Python

- Runtime: **`>=3.11`** (matches upstream `[project.requires-python]`).
- Type-check target: **`3.13`** (matches `[tool.ty.environment]`).
- `from __future__ import annotations` in every new module unless there's a specific reason not to.
- Type hints on every public function and class attribute. `ty check` runs in CI.
- Always pass `encoding="utf-8"` to `open()`, `read_text()`, `write_text()`, `Path.open()`. Enforced by `ruff PLW1514`.

## Dependencies

- Exact pins only (`==X.Y.Z`). No ranges, no `~=`, no `>=` upper-unbounded. Same rationale upstream uses.
- Regenerate `uv.lock` after every dep change. CI runs `uv lock --check`.
- **No new runtime dependencies** without explicit approval. The build-time tooling (`tools/build.py`, `tools/rebrand.py`, `tools/sync.py`, `tools/verify_no_leakage.py`, `tools/parity_runner.py`) uses stdlib + `pyyaml` (already a transitive upstream dep). Quilt and Make are system tools — not Python deps.
- Provider-specific / backend-specific deps stay in upstream's `[project.optional-dependencies]`. The fork does not add to either.

## Linting & Formatting

- **`ruff==0.15.10`** with the single rule upstream enforces: `PLW1514` (unspecified-encoding). Do not add new rules without coordinating with upstream's convention.
- `ruff format .` is the formatter. Don't argue with it.
- Per-file ignores match upstream: tests can use bare `open()`; skills/plugins are user-authored.

## Type Checker

- **`ty==0.0.21`** (Astral).
- `[tool.ty.rules]` matches upstream: `unknown-argument = "warn"`, `redundant-cast = "ignore"`.
- New strict rules require a separate review — drift here makes upstream sync noisy.

## Tests

- **`pytest==9.0.2`** with `pytest-asyncio==1.3.0`, `pytest-timeout==2.4.0`.
- Layout for **overlay-owned tests**: `overlay/tests/` mirrors the eventual `dist/argo/tests/` layout. Test files reference hermes-named symbols just like patches do; the rename engine produces argo-named tests in the built tree.
- **Build-tool tests** (for `tools/*.py`) live at top-level `tests/` (not under `overlay/`). They run against the pre-rename tree directly.
- Markers (inherited): `integration` (external services), `real_concurrent_gate` (opts out of an autouse stub).
- Default per-test timeout: 30s, signal method (`addopts = "-m 'not integration' --timeout=30 --timeout-method=signal"`).
- Slow / external-service tests MUST be `@pytest.mark.integration` so CI skips them by default.
- Coverage expectations: build pipeline (`tools/`) → high coverage; overlay-owned CLI shims → smoke + happy-path; parity suite (`tools/parity_runner.py`) → all FR-16 surfaces.

## File I/O

- Always `encoding="utf-8"` (PLW1514). Restating because it bites.
- JSON files we commit: deterministic key order (`json.dumps(..., sort_keys=True, indent=2)`). Build manifest is the canonical example.
- YAML: `ruamel.yaml` for round-trip-preserving edits, `pyyaml` for simple loads. Same as upstream.

---

## Repository Layout

**Always edit only these top-level paths:**

- `patches/` and `patches/asserts/` — fork's IP, as patch files + grep assertions.
- `overlay/` — fork-owned files added to the build (using **hermes**-named paths).
- `tools/` — build-time Python scripts. Never shipped in the runtime image.
- `scripts/` — shell entrypoints invoked from the Makefile.
- `Makefile`, `Dockerfile` — stable user-facing surface.
- `.github/workflows/` — CI. Shared setup (uv + Python + apt + pip) is factored into `.github/actions/argo-setup/action.yml`; edit the composite, not the per-job prelude.
- `.shepherd/` — spec, plan, standards, progress.
- `argo-rename.yaml` — declarative rename config.
- `README.md`, `AGENTS.md`, `.gitignore`, `.gitattributes`.

**Never edit:**

- `upstream/` — pristine. Use a patch instead.
- `dist/` — build output. Gitignored, regenerated on every build.
- `.sync-workdir/` — sync workdir. Gitignored, managed by `make sync`.

**Generated, must not be committed:**

- `dist/`, `.sync-workdir/`, `.quilt/`, `*.rej`, `*.orig`, `__pycache__/`, `.venv/`, `*.pyc`.

---

## Naming

Names in TRACKED source (i.e., what you write in patches and overlay) follow upstream:

- Modules: `lower_snake_case` (`hermes_cli`, `hermes_agent`, `hermes_sync`).
- Classes: `UpperCamelCase` (`HermesAgent`).
- Constants: `UPPER_SNAKE_CASE` (`HERMES_HOME`).
- Env vars: `HERMES_*` in source.
- CLI subcommands: `kebab-case`.

Names in the BUILT tree (`dist/argo/`, which gets packaged) — these are what customers see:

- Modules: `argo_cli`, `argo_agent`, `argo_sync`.
- Classes: `ArgoAgent`.
- Constants: `ARGO_HOME`.
- Env vars: `ARGO_*`.
- CLI: `argo` and its subcommands.

The rename engine handles this transformation at build time. Do not pre-rename in tracked source — it breaks the entire architecture (see spec § Why the legacy approach failed).

---

## Patch Authorship Rules

- **One patch = one logical fork change.** Never bundle. If a patch contains "add X and gate Y", split into `0007-add-x.patch` and `0008-gate-y.patch`.
- Patch `Subject:` line: imperative, ≤72 chars. References hermes names because the patch targets upstream's surface.
  - Good: `Subject: Wire --static and --live into hermes doctor`
  - Bad: `Subject: argo doctor flags`
- Patch body: explain the WHY. The diff shows the what.
- Patch format: `diff -up --git` (handles binary, modes, renames). Plain `diff -u` is insufficient.
- A patch larger than ~200 lines or touching >5 unrelated files MUST be split.
- **Load-bearing patches require a grep assertion file** at `patches/asserts/<patch-name>.txt`. Each non-comment line is a pattern (default fixed-string; `regex:` for regex; `path:` to restrict to a path glob).
  - Add the patch's basename to `patches/asserts/manifest.txt`.
  - Assertions catch the legacy failure mode: `quilt refresh` after conflict resolution silently dropping fork lines.

### Quilt commands you need

```bash
quilt new <name>.patch         # start a new patch (appends to series)
quilt add <file>                # mark file as touched by current patch
# ... edit files ...
quilt refresh                   # regenerate current patch from current state
quilt push -a                   # apply entire series (or up to first failure)
quilt pop -a                    # remove entire series
quilt series                    # show ordered series
quilt top                       # show currently-top patch
```

Workflow for a new fork change (authored against `.sync-workdir/`, NOT `dist/`):

1. `make build` first to confirm clean baseline.
2. Populate `.sync-workdir/` if not already (`make sync` does this; or `cp -r upstream/* .sync-workdir/ && cd .sync-workdir && quilt push -a`).
3. `cd .sync-workdir`.
4. `quilt new 00NN-short-slug.patch` (writes to `.sync-workdir/patches/`, since `.quiltrc` sets `QUILT_PATCHES=patches` relative to cwd).
5. `quilt add <files-you'll-edit>`.
6. Edit the files inside `.sync-workdir/`.
7. `quilt refresh` (`.quiltrc` ensures `-p ab --no-timestamps --no-index` output for AC-8 determinism).
8. Copy `.sync-workdir/patches/00NN-*.patch` back to repo-root `patches/`; append the filename to `patches/series`.
9. Write `patches/asserts/00NN-short-slug.txt` (if load-bearing) and add its basename to `patches/asserts/manifest.txt`.
10. `make build` from repo root to verify the patch applies cleanly and assertions pass.
11. `make leakage-static`; both must exit 0.
12. Commit.

**Do NOT author patches inside `dist/argo/`** — that directory is regenerated on every `make build` and would clobber un-copied-back patch files. `.sync-workdir/` is gitignored and persistent across sync attempts (AC-11), which is why it's the right workdir.

---

## Overlay Authorship Rules

**C1 resolution (spec v2):** overlay uses **hermes-named** paths and identifiers. The rename engine processes overlay AND upstream uniformly in the same pass when producing `dist/argo/`. There is no separate "overlay is already argo-named" path.

- Overlay files use **hermes-named** paths and reference upstream symbols by their hermes names. Example: `overlay/hermes_cli/doctor_leakage.py` imports `from hermes_sync.config import RenameConfig`. The build-time rename engine rewrites these to `argo_cli/doctor_leakage.py` and `from argo_sync.config import RenameConfig` in `dist/argo/`.
- All file I/O uses `encoding="utf-8"` (PLW1514).
- `from __future__ import annotations` at top.
- Overlay's `hermes_sync/` (the rename engine) is load-bearing infra. Changes there carry the same care as upstream contracts.
- Overlay files MUST NOT collide with paths in the patched upstream tree. The build fails loudly on collision. Overlay is purely **additive** — it adds files upstream doesn't have.

---

## Build-Tool Authorship (`tools/`)

- Pure Python where possible; `make` orchestrates, doesn't do logic.
- `tools/rebrand.py` MUST import the rename engine from `overlay/hermes_sync/` via:
  ```python
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).parent.parent / "overlay"))
  from hermes_sync.engine import RenameEngine
  ```
  NOT from `dist/argo/argo_sync/`. Avoids the cold-start chicken-and-egg.
- `tools/*.py` files run from the **repo root** (not as installed packages). Use `Path(__file__)` carefully.
- Errors carry context — never `raise Exception("bad")`. Define a typed subclass:
  ```python
  class UpstreamSyncError(RuntimeError):
      def __init__(self, message: str, *, step: str):
          super().__init__(f"[{step}] {message}")
          self.step = step
  ```

---

## Errors and Logging

- Domain errors are typed subclasses with context, never bare `Exception`.
- CLI surfaces user-facing errors with `rich` (an upstream transitive dep) — color, traceback only with `--debug`.
- Build-tool errors print the offending path/patch/file in stderr before exiting non-zero.

---

## Git Discipline

- Commits on `main`: imperative subject ≤72 chars. Body explains the WHY when non-obvious.
- **Sync commits** use the fixed format: `sync: upstream <short-sha> (<N> patches refreshed)`. Mechanical — produced by `make sync` itself.
- **Bootstrap commit** (one-time): `bootstrap: pristine fork at hermes-agent@<sha>`.
- **Patch-add commits** (during M3.x and beyond): `add patch 00NN: <subject>`.
- Never force-push `main`.
- Never `git push upstream` — `upstream` is read-only.
- Branch names: feature branches off `main`, named `argo/<topic>`.
- The CI gate `upstream-pristine` (FR-15) MUST stay green. If a PR touches `upstream/`, that's a `make sync` job's commit, not a human's.

---

## Architecture Boundaries

- **`upstream/` is sacred.** Never edited in tracked source. The only writers are `make bootstrap` and `make sync`, both producing commits in dedicated automation.
- **`overlay/hermes_sync/` is the rename engine.** It MUST NOT import from `overlay/hermes_cli/` or any other overlay package. The engine is a standalone library; the CLI shims and tests import the engine, never the reverse.
- **`tools/` is build-time only.** `tools/*.py` MUST NOT be importable from the runtime image. The final Docker stage does not copy `tools/`.
- **`dist/argo/` is regenerated.** Never commit it. Never resume manual edits from it (use `.sync-workdir/`).
- **`.sync-workdir/` is persistent across sync attempts.** Cleared only by `make sync-reset`. Separate from `dist/` so manual conflict edits survive a `make build` invocation.

---

## Documentation

- Module docstrings on every public module under `overlay/` and `tools/`.
- One-line summaries on public functions; richer docstrings only when the why is non-obvious.
- No `TODO:` in committed code without a tracking entry in `.shepherd/progress.md`.
- `README.md` is end-user-facing: `docker pull` quickstart + fork-notice + license. Mentions of patch series mechanics belong in `AGENTS.md`.
- `AGENTS.md` is ≤200 lines, points at `.shepherd/spec.md` and this file, plus the quilt cheatsheet.

---

## Performance

- `make sync` budget: ≤2 minutes wall-clock on a typical upstream delta (≤200 changed files, no patch refreshes). Spec NFR-1.
- `make build` budget: ≤5 minutes (rename + Docker build). Spec NFR-1.
- Rename engine traversal: `pathlib.Path.rglob` is fine; avoid spawning subprocesses per file. (Same as upstream.)

---

## Security

- No secrets in code, fixtures, or patch bodies.
- `.env` files always in `.gitignore`.
- Model API keys come from env vars at runtime; never persisted to disk by argo itself.
- `argo-rename.yaml` `exceptions:` entries MUST include a one-line `why:` justification. Reviewer rejects unjustified entries.
- GHCR push uses a PAT scoped to `write:packages` only. Rotate annually. (Spec OQ-13.)
- `.gitleaks.toml` allowlist entries (Patch 0006) MUST be justified per entry.

---

## Build Reproducibility

- `make build` MUST be deterministic given the same `upstream/.commit`, `patches/`, `overlay/`, and `argo-rename.yaml`. Verified by spec AC-5 (rename idempotency) + AC-8 (`dist/argo/` bit-identity across two builds with `SOURCE_DATE_EPOCH` set).
- Full Docker layer-hash reproducibility is best-effort and explicitly NOT a gate.
- Tooling that introduces non-determinism (uuid generators, time.time()) MUST honor `SOURCE_DATE_EPOCH` if set.

---

## Always / Ask First / Never

### Always
- Edit only the paths listed in § Repository Layout under "Always edit only these".
- Pass `encoding="utf-8"` on every file I/O.
- Use **hermes**-named identifiers in patches AND overlay. The engine renames at build.
- Patch files in `diff -up --git` format.
- After any patch/overlay edit, run `make build` locally before committing.
- Run `make leakage-static` after `make build` — both pass before commit.
- Add a `patches/asserts/<patch>.txt` for every load-bearing patch.

### Ask First
- Adding any new top-level Python runtime dependency to upstream.
- Adding a patch >200 lines or touching >5 unrelated files. Default: split it.
- Changing the rename engine's pass order (content → filenames → directories).
- Bumping `upstream/.commit` to an older SHA (downgrade).
- Adding an entry to `argo-rename.yaml` `exceptions:` (MUST include `why:`).
- Inlining a git submodule that upstream adds.

### Never
- Edit files under `upstream/` directly.
- Edit files under `dist/` or `.sync-workdir/`.
- Commit `dist/`, `.sync-workdir/`, `.quilt/`, `*.rej`, `*.orig`.
- Force-push `main`.
- `git push upstream` — upstream is read-only.
- Publish to PyPI. Docker-only.
- Touch `~/Code/argo-agent` from this repo's workflows. The legacy repo is frozen (spec G5).
- Add a fork-feature commit on `main` outside the `patches/` / `overlay/` system.
- Skip `make leakage-static`, `make parity`, or the upstream-pristine job in CI.
- Run `make build` while `.sync-workdir/` has unresolved conflicts.
- Past 20 patches: add new patches before the audit-and-reduce cycle completes (spec NFR-2).
