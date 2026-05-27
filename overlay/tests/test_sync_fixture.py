"""overlay/tests/test_sync_fixture.py — AC-2 zero-conflict pristine sync.

Exercises the M2.4 ``sync-fixture-200/`` fixture against ``tools/sync.py``
end-to-end:

1. Extract ``baseline-tree.tar.zst`` into a tmpdir simulating a hermes-agent
   worktree at ``BASELINE-SHA``.
2. ``git init`` + commit the baseline; apply ``upstream-200-files.patch``
   as a second commit → local replica has ``BASELINE → HEAD`` graph.
3. Clone the *current repo* into a sibling tmpdir, then rewind its
   ``upstream/`` subtree to the baseline tree (via ``git subtree add
   --squash`` against the local replica at ``BASELINE``).
4. Run ``tools/sync.py --upstream-url file:///<replica>/.git`` from
   inside the clone.
5. Assert: ``upstream/.commit`` advances to ``HEAD-SHA``; ``make build``
   exits 0; ``make leakage-static`` exits 0; sync commit on ``HEAD``.

Marked ``@pytest.mark.integration``; skipped by default. Re-enable with
``pytest -m integration``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sync-fixture-200"
BASELINE_TARBALL = FIXTURE_DIR / "baseline-tree.tar.zst"
FORWARD_PATCH = FIXTURE_DIR / "upstream-200-files.patch"
FIXTURE_README = FIXTURE_DIR / "README.md"


def _have_fixture() -> bool:
    return (
        BASELINE_TARBALL.is_file()
        and FORWARD_PATCH.is_file()
        and FIXTURE_README.is_file()
    )


def _read_sha_from_readme(label: str) -> str:
    r"""Extract a SHA from a ``**LABEL**: \`<sha>\``` line in the README."""
    text = FIXTURE_README.read_text(encoding="utf-8")
    needle = f"**{label}**:"
    for line in text.splitlines():
        if needle in line:
            # Format: `- **HEAD-SHA**: \`abc123...\``
            backticks = line.split("`")
            if len(backticks) >= 2:
                return backticks[1].strip()
    raise RuntimeError(f"could not find {label} in {FIXTURE_README}")


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\n"
            f"cwd: {cwd}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
    return result


def _git_env_no_signing() -> dict[str, str]:
    """Disable signing + GPG inside the test's git invocations."""
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "argo-test",
            "GIT_AUTHOR_EMAIL": "argo-test@example.invalid",
            "GIT_COMMITTER_NAME": "argo-test",
            "GIT_COMMITTER_EMAIL": "argo-test@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
        }
    )
    return env


def _extract_baseline_tree(dest: Path) -> None:
    """Extract the zstd-compressed baseline tarball into *dest*."""
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["tar", "--use-compress-program=unzstd", "-xf", str(BASELINE_TARBALL), "-C", str(dest)],
        check=True,
    )


def _build_local_upstream_replica(workdir: Path, env: dict[str, str]) -> Path:
    """Construct a 2-commit local git repo: BASELINE → HEAD.

    Returns the path to the .git directory of the replica.
    """
    replica = workdir / "upstream-replica"
    replica.mkdir(parents=True)
    _extract_baseline_tree(replica)

    _run(["git", "init", "--initial-branch=main", "-q"], cwd=replica, env=env)
    # Allow fetching arbitrary SHAs (some git versions need this for the
    # `git subtree add <sha>` form used below).
    _run(
        ["git", "config", "uploadpack.allowReachableSHA1InWant", "true"],
        cwd=replica,
        env=env,
    )
    _run(
        ["git", "config", "uploadpack.allowAnySHA1InWant", "true"],
        cwd=replica,
        env=env,
    )
    _run(["git", "add", "-A"], cwd=replica, env=env)
    _run(
        ["git", "commit", "-q", "--allow-empty", "-m", "baseline"],
        cwd=replica,
        env=env,
    )
    # Mark the baseline commit with a branch so `subtree add` can fetch it
    # by name (avoids any allowAnySHA1InWant issues across git versions).
    _run(["git", "branch", "baseline"], cwd=replica, env=env)
    # Apply forward delta as a second commit.
    apply_result = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", str(FORWARD_PATCH)],
        cwd=str(replica),
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if apply_result.returncode != 0:
        raise AssertionError(
            "git apply of forward delta failed:\n"
            f"stdout: {apply_result.stdout}\nstderr: {apply_result.stderr}"
        )
    _run(["git", "add", "-A"], cwd=replica, env=env)
    _run(["git", "commit", "-q", "-m", "forward delta"], cwd=replica, env=env)
    return replica / ".git"


def _clone_repo_under_test(workdir: Path, env: dict[str, str]) -> Path:
    """Clone the current argo-agent repo into a fresh tmpdir.

    We need a real ``.git`` directory because ``git subtree pull`` mutates
    refs/commits. The clone shares no state with the source.

    Because the test may run inside a feature-branch worktree that has
    *uncommitted* changes (e.g. the M4.2 branch adding ``tools/sync.py``
    itself), we also overlay-copy tracked-or-untracked working-tree
    files via ``git ls-files -co --exclude-standard`` so the test sees
    the same files the developer is exercising.
    """
    clone = workdir / "argo-clone"
    _run(
        ["git", "clone", "--quiet", "--no-local", str(REPO_ROOT), str(clone)],
        cwd=workdir,
        env=env,
    )
    # Overlay any uncommitted-but-tracked or untracked files from the
    # source worktree onto the clone. This makes the test work on a
    # feature branch where tools/sync.py hasn't landed yet.
    ls = subprocess.run(
        ["git", "ls-files", "--others", "--modified", "--exclude-standard"],
        cwd=str(REPO_ROOT),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    skip_prefixes = ("dist/", ".sync-workdir/", "__pycache__/", ".pytest_cache/")
    for rel in ls.stdout.splitlines():
        rel = rel.strip()
        if not rel or rel.startswith(skip_prefixes):
            continue
        src = REPO_ROOT / rel
        if not src.is_file():
            continue
        dst = clone / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    # Stage + commit the overlay so the clone's working tree stays clean
    # (sync.py refuses to operate on a dirty tree).
    _run(["git", "add", "-A"], cwd=clone, env=env)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(clone),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        check=True,
    ).stdout.strip()
    if status:
        _run(
            ["git", "commit", "-q", "-m", "test: overlay uncommitted feature files"],
            cwd=clone,
            env=env,
        )
    return clone


def _rewind_upstream_to_baseline(
    clone: Path, replica_git: Path, baseline_sha: str, env: dict[str, str]
) -> None:
    """Rewind the clone's upstream/ subtree to point at BASELINE.

    Strategy: remove upstream/ in the clone, then `git subtree add
    --prefix=upstream <replica> baseline-ref --squash` to seed it at
    the baseline tree. Also rewrite upstream/.commit to BASELINE-SHA.
    """
    # Remove existing upstream/.
    upstream_dir = clone / "upstream"
    if upstream_dir.exists():
        _run(["git", "rm", "-r", "-q", "upstream"], cwd=clone, env=env)
        _run(
            ["git", "commit", "-q", "-m", "test: drop upstream/ to seed at baseline"],
            cwd=clone,
            env=env,
        )

    # Re-add upstream/ at baseline (use the `baseline` branch we tagged
    # on the replica so upload-pack will serve the ref).
    _run(
        [
            "git",
            "subtree",
            "add",
            "--prefix=upstream",
            f"file://{replica_git}",
            "baseline",
            "--squash",
        ],
        cwd=clone,
        env=env,
    )

    # Reset upstream/.commit to BASELINE-SHA (subtree add doesn't touch it).
    commit_file = upstream_dir / ".commit"
    commit_file.write_text(baseline_sha + "\n", encoding="utf-8")
    _run(["git", "add", "upstream/.commit"], cwd=clone, env=env)
    _run(
        ["git", "commit", "-q", "-m", "test: rewind upstream/.commit to baseline"],
        cwd=clone,
        env=env,
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not BASELINE_TARBALL.is_file(),
    reason=f"fixture missing: {BASELINE_TARBALL}",
)
def test_sync_against_fixture_200_advances_pin_and_builds_clean(tmp_path: Path) -> None:
    """AC-2: zero-conflict pristine sync produces a clean dist/argo/."""

    if not _have_fixture():
        pytest.skip("sync-fixture-200 incomplete")

    head_sha = _read_sha_from_readme("HEAD-SHA")
    baseline_sha = _read_sha_from_readme("BASELINE-SHA")
    assert head_sha != baseline_sha

    env = _git_env_no_signing()

    replica_git = _build_local_upstream_replica(tmp_path, env)
    clone = _clone_repo_under_test(tmp_path, env)
    _rewind_upstream_to_baseline(clone, replica_git, baseline_sha, env)

    # Pre-condition checks.
    pin_before = (clone / "upstream" / ".commit").read_text(encoding="utf-8").strip()
    assert pin_before == baseline_sha

    # Run the sync.
    head_before = _run(
        ["git", "rev-parse", "HEAD"], cwd=clone, env=env
    ).stdout.strip()
    sync_result = _run(
        [
            sys.executable,
            str(clone / "tools" / "sync.py"),
            "--upstream-url",
            f"file://{replica_git}",
        ],
        cwd=clone,
        env=env,
        check=False,
    )
    assert sync_result.returncode == 0, (
        f"sync failed:\nstdout: {sync_result.stdout}\nstderr: {sync_result.stderr}"
    )

    # Post-conditions.
    pin_after = (clone / "upstream" / ".commit").read_text(encoding="utf-8").strip()
    assert pin_after != baseline_sha
    # NOTE: pin_after is the SHA from the upstream subtree pull's
    # git-subtree-split trailer; it MUST match the replica HEAD.
    replica_head = _run(
        ["git", "rev-parse", "HEAD"], cwd=replica_git.parent, env=env
    ).stdout.strip()
    assert pin_after == replica_head, (
        f"upstream/.commit ({pin_after}) does not match replica HEAD ({replica_head})"
    )

    # Sync produced a new HEAD commit.
    head_after = _run(
        ["git", "rev-parse", "HEAD"], cwd=clone, env=env
    ).stdout.strip()
    assert head_after != head_before, "sync produced no new commit"

    # Commit message follows `sync: upstream <short-sha> (<n> patches refreshed)`.
    commit_msg = _run(
        ["git", "log", "-1", "--pretty=%s"], cwd=clone, env=env
    ).stdout.strip()
    assert commit_msg.startswith("sync: upstream "), (
        f"unexpected commit subject: {commit_msg!r}"
    )

    # Verification: make build + leakage already ran inside sync.py, but
    # re-run from the clone explicitly to mirror the AC-2 spec language.
    _run(["make", "build"], cwd=clone, env=env)
    _run(["make", "leakage-static"], cwd=clone, env=env)

    # .sync-workdir/ cleared on success.
    assert not (clone / ".sync-workdir").exists()
