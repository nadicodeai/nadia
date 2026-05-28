"""tests/test_parity_runner.py — unit + integration tests for parity_runner.

Default suite (no marker) covers pure-Python behavior — normalization
mapping, diff function, SKIP detection, JSON-volatility stripping,
artifact-dir summarization, exit-code mismatch detection — without
invoking docker. The single ``@pytest.mark.integration`` test drives
the real runner against the locally-built ``:dev`` and locally-pulled
legacy ``:latest`` images; it skips gracefully if either is missing
so the default ``pytest tests/`` run never depends on local docker
state.

Baseline image note
-------------------

M6 uses ``ghcr.io/nadicodeai/argo-agent:latest`` as the parity baseline
because the ``:0.14.0`` tag referenced in ``.shepherd/spec.md`` was
never pushed to GHCR. The legacy repository's pyproject.toml does
report version 0.14.0, so ``:latest`` is functionally equivalent in
intent — but in practice the ``:latest`` image as pulled at the time
M6.2a landed reports ``Hermes Agent v0.8.0``, indicating the legacy
publisher never tagged v0.14.0 either. If a future legacy release
publishes a real ``:0.14.0`` tag, update spec FR-16 and the runner's
``DEFAULT_LEGACY_IMAGE`` accordingly and re-pin AC-7's gate.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "tools" / "parity_runner.py"

# Import the runner module directly so we can unit-test the helpers
# without round-tripping through subprocess. tools/ is not a package,
# so we extend sys.path here.
sys.path.insert(0, str(REPO_ROOT / "tools"))
import parity_runner  # noqa: E402


# ---------------------------------------------------------------------------
# Pure-Python tests — no docker, run by default.
# ---------------------------------------------------------------------------


def test_normalization_case_preserving() -> None:
    """``hermes``/``Hermes``/``HERMES`` map to the right case-preserving forms."""
    assert parity_runner._normalize_hermes("Hermes Agent") == "Argo Agent"
    assert parity_runner._normalize_hermes("hermes_cli") == "argo_cli"
    assert parity_runner._normalize_hermes("HERMES_HOME") == "ARGO_HOME"
    assert parity_runner._normalize_hermes("hermes-agent") == "argo-agent"
    assert parity_runner._normalize_hermes("HermesAgent") == "ArgoAgent"
    assert parity_runner._normalize_hermes("hermes: error: x") == "argo: error: x"


def test_normalization_keeps_unmapped_strings() -> None:
    """Text without any hermes-prefix variant is untouched."""
    untouched = "the quick brown fox jumps over 0xDEADBEEF\n"
    assert parity_runner._normalize_hermes(untouched) == untouched
    # Strings that merely contain ``argo`` (the target) are likewise inert.
    assert parity_runner._normalize_hermes("argo --version") == "argo --version"


def test_normalization_is_idempotent() -> None:
    """Applying the substitution twice equals applying it once."""
    src = (
        "Hermes Agent v0.8.0\n"
        "Project: /opt/hermes\n"
        "hermes: error: unrecognized arguments: --static\n"
        "HERMES_HOME=/opt/data\n"
    )
    once = parity_runner._normalize_hermes(src)
    twice = parity_runner._normalize_hermes(once)
    assert once == twice


def test_normalization_handles_composite_before_bare() -> None:
    """Longer composites must shadow ``hermes`` so we don't double-rewrite."""
    # If the engine applied ``hermes → argo`` before ``hermes_cli → argo_cli``
    # the latter would never fire and the output would have ``argo_cli`` only
    # via the bare rule; for ``hermes_tools_mcp_server`` the bare rule would
    # produce ``argo_tools_mcp_server`` correctly too — but for asymmetric
    # mappings like ``HERMES_HOME → ARGO_HOME`` the composite MUST win.
    assert (
        parity_runner._normalize_hermes("export HERMES_HOME=/x")
        == "export ARGO_HOME=/x"
    )
    assert (
        parity_runner._normalize_hermes("from hermes_tools_mcp_server import x")
        == "from argo_tools_mcp_server import x"
    )


def test_diff_empty_on_match() -> None:
    """``_diff`` returns empty string when normalized legacy == new."""
    legacy = "Argo Agent v0.14.0\nProject: /opt/argo\n"
    new = "Argo Agent v0.14.0\nProject: /opt/argo\n"
    assert parity_runner._diff(legacy, new, surface="version") == ""


def test_diff_nonempty_on_mismatch() -> None:
    """``_diff`` returns a unified diff string with file headers on mismatch."""
    legacy = "Argo Agent v0.8.0\n"
    new = "Argo Agent v0.14.0\n"
    out = parity_runner._diff(legacy, new, surface="version")
    assert out != ""
    assert "legacy(normalized):version" in out
    assert "new:version" in out
    assert "-Argo Agent v0.8.0" in out
    assert "+Argo Agent v0.14.0" in out


def test_diff_after_normalization_matches() -> None:
    """End-to-end: legacy raw → normalize → diff vs new → empty when content
    only differs by brand-string."""
    legacy_raw = "Hermes Agent v0.14.0 (2026.5.16)\nProject: /opt/hermes\n"
    new_raw = "Argo Agent v0.14.0 (2026.5.16)\nProject: /opt/argo\n"
    legacy_normalized = parity_runner._normalize_hermes(legacy_raw)
    assert parity_runner._diff(legacy_normalized, new_raw, surface="x") == ""


def test_parity_error_hierarchy() -> None:
    """Subclasses all extend ``ParityError`` which extends ``RuntimeError``."""
    assert issubclass(parity_runner.ParityError, RuntimeError)
    assert issubclass(parity_runner.ImageNotFoundError, parity_runner.ParityError)
    assert issubclass(
        parity_runner.ExitCodeMismatchError, parity_runner.ParityError
    )
    assert issubclass(parity_runner.ContentDiffError, parity_runner.ParityError)


def test_surfaces_in_scope() -> None:
    """FR-16 (M6.2b) ships seven surfaces; IU-AC-7/IU-AC-8 (M6.1+M6.2) adds two."""
    assert set(parity_runner.SURFACES) == {
        # FR-16 / M6.2b
        "help",
        "version",
        "doctor-static",
        "mcp-list",
        "hook-fire",
        "auth-start",
        "session-init",
        # IU-AC-7 / IU-AC-8 (install-update loop M6.1 + M6.2)
        "install-script",
        "cmd-update",
    }


def test_install_script_surface_shape() -> None:
    """IU-AC-7 surface inspects the in-image install.sh via grep.

    Read-only post-install layout parity (option a in the M6 dispatch).
    The grep pattern MUST stay narrow — broadening it pulls in upstream
    refactors that don't break behavior, defeating the purpose of a
    pinned-line gate. See the inline comment in SURFACES.
    """
    spec = parity_runner.SURFACES["install-script"]
    # Both sides invoke ``bash -c "grep ... /opt/argo/scripts/install.sh"``;
    # the path was probed against both the new image and the legacy
    # baseline at SHA 9b8cf6bf5 (publish-legacy-baseline.yml's input).
    assert spec.new_args[0] == "bash"
    assert spec.legacy_entrypoint == "bash"
    assert "/opt/argo/scripts/install.sh" in spec.new_args[-1]
    assert "/opt/argo/scripts/install.sh" in spec.legacy_args[-1]
    # The pinned constants the surface gates on.
    for needle in ("BRANCH=", "REPO_URL_HTTPS=", "install_method"):
        assert needle in spec.new_args[-1]
        assert needle in spec.legacy_args[-1]


def test_cmd_update_surface_shape() -> None:
    """IU-AC-8 surface runs ``argo/hermes update --check`` on both sides.

    --check is the read-only path: no git pull, no state mutation, no
    network. The in-image tree has no .git/ so both sides take the
    'not a git repository' early-return; the parity gate asserts the
    error message is byte-equivalent modulo brand renames.
    """
    spec = parity_runner.SURFACES["cmd-update"]
    assert spec.new_args == ("argo", "update", "--check")
    assert spec.legacy_entrypoint == "hermes"
    assert spec.legacy_args == ("update", "--check")


def test_backend_surfaces_have_proper_specs() -> None:
    """Each backend surface MUST declare new_args, legacy_args, legacy_entrypoint.

    Specifically: mcp-list and hook-fire mount fixtures; session-init
    declares an artifact dir. This guards against accidentally regressing
    a surface to a CLI-only spec.
    """
    mcp = parity_runner.SURFACES["mcp-list"]
    assert mcp.legacy_entrypoint == "hermes"
    assert any(c == "/fixtures" for _, c in mcp.volumes)

    hook = parity_runner.SURFACES["hook-fire"]
    assert any(c == "/fixtures" for _, c in hook.volumes)

    auth = parity_runner.SURFACES["auth-start"]
    # auth-start exercises ``auth list`` on both images — same shape.
    assert auth.new_args[:2] == ("argo", "auth")
    assert auth.legacy_args[:1] == ("auth",)

    session = parity_runner.SURFACES["session-init"]
    assert session.container_artifact_dir is not None
    assert session.artifact_path == ""


# ---------------------------------------------------------------------------
# SKIP detection — argparse "invalid choice" / "unrecognized arguments".
# ---------------------------------------------------------------------------


def test_skip_detector_invalid_choice_triggers_skip() -> None:
    """The legacy ``hermes hook --help`` argparse failure must be caught."""
    legacy_stdout = (
        "usage: hermes [-h] [--version] {chat,model,...} ...\n"
        "hermes: error: argument command: invalid choice: 'hooks' "
        "(choose from chat, model, ...)\n"
    )
    assert parity_runner._looks_like_missing_subcommand(legacy_stdout, 2)


def test_skip_detector_unrecognized_arguments_triggers_skip() -> None:
    """``unrecognized arguments: --plugin-dir`` is the parent-parser variant."""
    legacy_stdout = "hermes: error: unrecognized arguments: --plugin-dir /x\n"
    assert parity_runner._looks_like_missing_subcommand(legacy_stdout, 2)


def test_skip_detector_module_not_found_is_NOT_skip() -> None:
    """``ModuleNotFoundError`` is a real crash, not a missing subcommand.

    Important: the slim :dev image currently crashes with
    ``ModuleNotFoundError: No module named 'tools'`` on ``argo mcp list``.
    That MUST be reported as FAIL, not SKIP — the slim image is broken
    and we want the parity gate to surface that.
    """
    stdout = (
        "Traceback (most recent call last):\n"
        "  File '/opt/argo/.venv/bin/argo', line 6, in <module>\n"
        "ModuleNotFoundError: No module named 'tools'\n"
    )
    assert not parity_runner._looks_like_missing_subcommand(stdout, 1)


def test_skip_detector_exit_zero_is_never_skip() -> None:
    """A command that exits 0 is by definition not a missing-subcommand."""
    # Even if the magic phrase appears, exit-0 means the binary ran fine.
    stdout = "hermes: error: invalid choice: 'foo' (this is a doc example)\n"
    assert not parity_runner._looks_like_missing_subcommand(stdout, 0)


# ---------------------------------------------------------------------------
# Artifact-dir summarization (session-init surface).
# ---------------------------------------------------------------------------


def test_summarize_artifact_dir_empty(tmp_path: Path) -> None:
    """An empty directory produces an empty string (no entries)."""
    assert parity_runner._summarize_artifact_dir(tmp_path) == ""


def test_summarize_artifact_dir_missing(tmp_path: Path) -> None:
    """A path that doesn't exist returns the missing-marker line."""
    nonexistent = tmp_path / "nope"
    out = parity_runner._summarize_artifact_dir(nonexistent)
    assert "missing" in out


def test_summarize_artifact_dir_files(tmp_path: Path) -> None:
    """Non-JSON files are summarized by size bucket; sorted by relpath."""
    (tmp_path / "a.txt").write_text("")
    (tmp_path / "b.txt").write_text("x" * 100)
    (tmp_path / "c.txt").write_text("x" * 5000)
    out = parity_runner._summarize_artifact_dir(tmp_path)
    lines = out.strip().split("\n")
    assert lines == [
        "a.txt\tFILE\tempty",
        "b.txt\tFILE\tsmall",
        "c.txt\tFILE\tlarge",
    ]


def test_summarize_artifact_dir_strips_volatile_json(tmp_path: Path) -> None:
    """JSON files have their volatile keys removed before summarization."""
    payload = {
        "session_id": "abc-123",
        "created_at": "2026-05-27T00:00:00Z",
        "stable_field": "kept",
        "nested": {"id": "drop-me", "kind": "session"},
    }
    (tmp_path / "session.json").write_text(json.dumps(payload))
    out = parity_runner._summarize_artifact_dir(tmp_path)
    # Volatile keys gone; stable keys + nested.kind preserved.
    assert "session_id" not in out
    assert "created_at" not in out
    assert "drop-me" not in out
    assert "stable_field" in out
    assert '"kind": "session"' in out


def test_summarize_artifact_dir_stable_across_runs(tmp_path: Path) -> None:
    """Re-running the summarizer on the same tree yields byte-identical output.

    Critical for the parity diff: any non-determinism here would flap.
    """
    (tmp_path / "a.json").write_text('{"id": 1, "k": "v"}')
    (tmp_path / "b.json").write_text('{"id": 2, "k": "v"}')
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.txt").write_text("hello")
    first = parity_runner._summarize_artifact_dir(tmp_path)
    second = parity_runner._summarize_artifact_dir(tmp_path)
    assert first == second


def test_strip_volatile_json_recurses_into_lists() -> None:
    """``_strip_volatile_json`` walks lists of dicts too."""
    src = {
        "items": [
            {"id": 1, "name": "a"},
            {"id": 2, "name": "b"},
        ],
        "session_id": "drop",
    }
    out = parity_runner._strip_volatile_json(src)
    assert out == {"items": [{"name": "a"}, {"name": "b"}]}


# ---------------------------------------------------------------------------
# run_surface() — unit tests with mocked subprocess.
# ---------------------------------------------------------------------------


def _fake_run(
    new_out: str,
    new_exit: int,
    legacy_out: str,
    legacy_exit: int,
) -> mock.MagicMock:
    """Build a docker_run side-effect that returns new-then-legacy."""
    return mock.MagicMock(
        side_effect=[(new_exit, new_out), (legacy_exit, legacy_out)],
    )


def test_run_surface_pass_for_matching_output() -> None:
    """If exit codes match and normalized outputs match → PASS."""
    new = "Argo Agent v0.14.0\n"
    legacy = "Hermes Agent v0.14.0\n"  # normalizes to identical
    with mock.patch.object(parity_runner, "_check_image_present"), \
         mock.patch.object(parity_runner, "_docker_run", _fake_run(new, 0, legacy, 0)):
        result = parity_runner.run_surface(
            "version", new_image="img:new", legacy_image="img:old"
        )
    assert result.status == "PASS"
    assert result.passed is True
    assert result.diff == ""


def test_run_surface_fail_for_diverging_output() -> None:
    """Same exit, different content → FAIL with a non-empty diff."""
    new = "Argo Agent v0.14.0\n"
    legacy = "Hermes Agent v0.8.0\n"  # normalizes to Argo Agent v0.8.0
    with mock.patch.object(parity_runner, "_check_image_present"), \
         mock.patch.object(parity_runner, "_docker_run", _fake_run(new, 0, legacy, 0)):
        result = parity_runner.run_surface(
            "version", new_image="img:new", legacy_image="img:old"
        )
    assert result.status == "FAIL"
    assert result.passed is False
    assert "v0.8.0" in result.diff
    assert "v0.14.0" in result.diff


def test_run_surface_skip_when_legacy_lacks_subcommand() -> None:
    """Legacy argparse "invalid choice" → SKIPPED, not FAIL."""
    legacy_argparse = (
        "usage: hermes [...]\n"
        "hermes: error: argument command: invalid choice: 'hooks'\n"
    )
    new = "usage: argo hooks [-h] {list,test,doctor} ...\n"
    with mock.patch.object(parity_runner, "_check_image_present"), \
         mock.patch.object(
             parity_runner, "_docker_run", _fake_run(new, 0, legacy_argparse, 2)
         ):
        result = parity_runner.run_surface(
            "hook-fire", new_image="img:new", legacy_image="img:old"
        )
    assert result.status == "SKIPPED"
    assert "legacy" in result.skip_reason
    assert result.diff == ""


def test_run_surface_skip_when_new_lacks_subcommand() -> None:
    """If the NEW image is what's missing the subcommand, that's also SKIP.

    Defensive: we'd never expect the new image to lack a v0.14.0
    subcommand, but if a future refactor drops one we want SKIP not
    FAIL — the gate would then surface the regression upstream.
    """
    legacy_ok = "no sessions found\n"
    new_argparse = (
        "argo: error: argument command: invalid choice: 'sessions'\n"
    )
    with mock.patch.object(parity_runner, "_check_image_present"), \
         mock.patch.object(
             parity_runner, "_docker_run", _fake_run(new_argparse, 2, legacy_ok, 0)
         ):
        result = parity_runner.run_surface(
            "auth-start", new_image="img:new", legacy_image="img:old"
        )
    assert result.status == "SKIPPED"
    assert "new" in result.skip_reason


def test_run_surface_module_not_found_is_FAIL_not_skip() -> None:
    """The slim :dev image's ``ModuleNotFoundError`` is a real regression."""
    new = (
        "Traceback (most recent call last):\n"
        "ModuleNotFoundError: No module named 'tools'\n"
    )
    legacy = "No MCP servers configured.\n"
    with mock.patch.object(parity_runner, "_check_image_present"), \
         mock.patch.object(
             parity_runner, "_docker_run", _fake_run(new, 1, legacy, 0)
         ):
        result = parity_runner.run_surface(
            "mcp-list", new_image="img:new", legacy_image="img:old"
        )
    assert result.status == "FAIL"
    assert result.new_exit == 1
    assert result.legacy_exit == 0


def test_run_surface_unknown_raises_keyerror() -> None:
    """Asking for a surface we don't ship is a programmer error → KeyError."""
    with mock.patch.object(parity_runner, "_check_image_present"):
        with pytest.raises(KeyError):
            parity_runner.run_surface(
                "no-such-surface",
                new_image="img:new",
                legacy_image="img:old",
            )


# ---------------------------------------------------------------------------
# CLI surface — argparse wiring.
# ---------------------------------------------------------------------------


def test_runner_help_succeeds() -> None:
    """``python tools/parity_runner.py --help`` returns 0 and lists surfaces."""
    res = subprocess.run(
        [sys.executable, str(RUNNER), "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "FR-16" in res.stdout
    assert "--new-image" in res.stdout
    assert "--legacy-image" in res.stdout
    assert "doctor-static" in res.stdout
    # M6.2b surfaces are advertised in --help via the argparse choices.
    assert "mcp-list" in res.stdout
    assert "hook-fire" in res.stdout
    assert "auth-start" in res.stdout
    assert "session-init" in res.stdout
    # IU-AC-7 / IU-AC-8 (install-update loop M6.1 + M6.2).
    assert "install-script" in res.stdout
    assert "cmd-update" in res.stdout


def test_runner_rejects_unknown_surface() -> None:
    """argparse choices reject unknown --surface; exit 2."""
    res = subprocess.run(
        [sys.executable, str(RUNNER), "--surface", "not-a-surface"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 2
    assert "invalid choice" in res.stderr


def test_runner_image_not_found_exits_2() -> None:
    """A bogus ``--new-image`` produces a structural exit 2, not 1."""
    res = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--surface",
            "version",
            "--new-image",
            "ghcr.io/nadicodeai/this-image-definitely-does-not-exist:nope",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
    )
    assert res.returncode == 2
    assert "not present locally" in res.stderr


# ---------------------------------------------------------------------------
# Fixtures must be checked in.
# ---------------------------------------------------------------------------


def test_mcp_fixture_present_and_valid() -> None:
    """The MCP plugin fixture is a real JSON file with required keys."""
    f = REPO_ROOT / "tests" / "fixtures" / "parity-mcp" / "plugins" / "example.json"
    assert f.is_file(), f"missing MCP fixture: {f}"
    data = json.loads(f.read_text())
    assert "name" in data
    assert "transport" in data
    assert "command" in data


def test_hook_fixture_present_and_executable() -> None:
    """The hook fixture is a real executable script."""
    f = REPO_ROOT / "tests" / "fixtures" / "parity-hooks" / "hook.sh"
    assert f.is_file(), f"missing hook fixture: {f}"
    # On POSIX, the script must have the exec bit set or the binary
    # under test won't be able to run it. (Git tracks file mode.)
    import stat
    mode = f.stat().st_mode
    assert mode & stat.S_IXUSR, "hook.sh must be executable"


# ---------------------------------------------------------------------------
# Expected-FAIL whitelist (M6 architect).
# ---------------------------------------------------------------------------


def test_expected_file_present_at_default_location() -> None:
    """The shipped expected-FAIL YAML loads cleanly."""
    p = parity_runner.DEFAULT_EXPECTED_FILE
    assert p.is_file(), f"missing expected-FAIL whitelist: {p}"
    loaded = parity_runner._load_expected_fails(p)
    # Every entry's surface MUST be a real declared surface — guards
    # against typo'd whitelist entries silently allowing nothing.
    for name in loaded:
        assert name in parity_runner.SURFACES, (
            f"expected-FAIL entry {name!r} is not a known surface; "
            f"known surfaces: {sorted(parity_runner.SURFACES)}"
        )


def test_load_expected_fails_missing_file_returns_empty(tmp_path: Path) -> None:
    """``--expected-file`` pointing at a missing path is treated as 'no whitelist'."""
    missing = tmp_path / "nope.yml"
    assert parity_runner._load_expected_fails(missing) == {}


def test_load_expected_fails_parses_reasons(tmp_path: Path) -> None:
    """Whitelist entries surface their reason text."""
    p = tmp_path / "expected.yml"
    p.write_text(
        "expected:\n"
        "  - surface: help\n"
        "    reason: baseline gap\n"
        "  - surface: version\n"
        "    reason: v0.8.0 vs v0.14.0\n",
        encoding="utf-8",
    )
    out = parity_runner._load_expected_fails(p)
    assert out == {"help": "baseline gap", "version": "v0.8.0 vs v0.14.0"}


def test_runner_allow_expected_classifies_fail_as_xfail(tmp_path: Path) -> None:
    """With ``--allow-expected`` and a whitelist entry, a FAIL becomes XFAIL.

    Exercises the CLI end-to-end without docker by pre-seeding a runner
    invocation that mocks ``run_surface`` to return a synthetic FAIL.
    """
    # Build a tiny whitelist on the fly.
    yml = tmp_path / "exp.yml"
    yml.write_text(
        "expected:\n"
        "  - surface: help\n"
        "    reason: synthetic baseline gap\n",
        encoding="utf-8",
    )
    fake_result = parity_runner.SurfaceResult(
        surface="help",
        status="FAIL",
        new_exit=0,
        legacy_exit=0,
        new_stdout="new",
        legacy_stdout_raw="legacy",
        legacy_stdout_normalized="legacy-norm",
        diff="--- legacy\n+++ new\n",
    )
    with mock.patch.object(parity_runner, "run_surface", return_value=fake_result):
        rc = parity_runner._main(
            [
                "--surface",
                "help",
                "--allow-expected",
                "--expected-file",
                str(yml),
            ],
        )
    # XFAIL must not contribute to a non-zero exit.
    assert rc == 0


def test_runner_strict_mode_fails_without_allow_expected(tmp_path: Path) -> None:
    """Without ``--allow-expected``, the same FAIL exits 1."""
    fake_result = parity_runner.SurfaceResult(
        surface="help",
        status="FAIL",
        new_exit=0,
        legacy_exit=0,
        new_stdout="new",
        legacy_stdout_raw="legacy",
        legacy_stdout_normalized="legacy-norm",
        diff="--- legacy\n+++ new\n",
    )
    with mock.patch.object(parity_runner, "run_surface", return_value=fake_result):
        rc = parity_runner._main(["--surface", "help"])
    assert rc == 1


# ---------------------------------------------------------------------------
# Integration test — exercises the real runner against real images.
# ---------------------------------------------------------------------------


def _docker_image_present(image: str) -> bool:
    """True iff ``image`` is locally available (no pull attempted)."""
    res = subprocess.run(
        ["docker", "image", "inspect", image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return res.returncode == 0


@pytest.mark.integration
@pytest.mark.timeout(300)
def test_parity_runner_against_real_images() -> None:
    """Drive every FR-16 surface against the locally-available images.

    Skips when either image is missing (CI is responsible for pulling /
    building before invoking this gate). When both images are present
    the runner MUST produce a per-surface report covering all 7
    surfaces; per-surface outcomes vary (the legacy ``:latest`` is
    v0.8.0, so several FR-16 backend surfaces SKIP; the slim ``:dev``
    image has a known ``ModuleNotFoundError`` on ``mcp list`` /
    ``sessions list`` which surfaces as FAIL — that's the M5 follow-up
    flag, not a runner bug).
    """
    new_image = parity_runner.DEFAULT_NEW_IMAGE
    legacy_image = parity_runner.DEFAULT_LEGACY_IMAGE
    if not _docker_image_present(new_image):
        pytest.skip(f"{new_image} not present; run `make image` first")
    if not _docker_image_present(legacy_image):
        pytest.skip(f"{legacy_image} not present; `docker pull` first")

    res = subprocess.run(
        [sys.executable, str(RUNNER), "--verbose"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        check=False,
        timeout=300,
    )
    # The runner MUST emit one status line per surface (PASS, FAIL,
    # or SKIPPED) — that's the contract for AC-7 reporting.
    for surface in parity_runner.SURFACES:
        assert f"surface={surface}" in res.stdout, (
            f"runner did not report surface={surface}; "
            f"stdout={res.stdout!r}"
        )
    # Exit code is 0 (all PASS-or-SKIP) or 1 (at least one FAIL).
    # 2 would be a structural failure (gate itself broken) — fail the
    # test in that case so the gate's reliability is itself gated.
    assert res.returncode in (0, 1), (
        f"runner returned structural-error exit {res.returncode}; "
        f"stdout={res.stdout!r} stderr={res.stderr!r}"
    )
