"""tools/check_packaging_contract.py — fork-vs-upstream packaging-drift gate.

Promotes ``dist/argo/Dockerfile`` — the rename of ``upstream/Dockerfile`` that
``make build`` already produces — to the authoritative packaging ORACLE, and
checks that the shipped ``./Dockerfile`` has not silently diverged from upstream's
toolchain decisions.

Motivation
----------
The fork's guardrails (FR-15 upstream-pristine, the rename engine, run_assertions,
verify_no_leakage) all guard the upstream->dist CONTENT pipeline. The shipped
``./Dockerfile`` is fork-native, sits OUTSIDE that pipeline, and was never
compared to upstream — so packaging drift was invisible by construction. That is
exactly how the runtime image ended up on Debian's Node 18 (apt default) while
upstream had deliberately pinned ``node:22`` for the Vite web build. This gate is
the missing forcing function.

What it enforces (against the oracle)
-------------------------------------
1. FROM digest parity — every digest-pinned oracle image must appear in the
   shipped Dockerfile with the SAME digest (catches a node/base bump), unless
   recorded in ``from_exceptions``.
2. Pinned-ARG parity — every oracle ARG whose value is a version or a sha256
   (e.g. the s6-overlay version + 4 checksums) must match the shipped value
   (catches a supply-chain bump), unless recorded in ``pinned_arg_exceptions``.
3. apt superset — every system dep upstream apt-installs must be reachable in
   the shipped image's apt closure (catches an upstream-ADDED dep), unless
   recorded in ``apt_exceptions``.
4. Install-extras coverage — every Python extra upstream installs must be
   installed in the shipped image, unless recorded in ``extras_exceptions``.
5. Stale-exception detection — every allowlisted exception must still correspond
   to a LIVE oracle facet; an exception whose upstream counterpart was removed or
   changed fails the gate so it is re-reviewed rather than masking new drift.

The oracle is consumed fresh (the caller runs ``make build`` first), so it is
trustworthy engine output — there is nothing to game without editing
``upstream/``/``patches/``/``overlay/``, which the existing gates already guard.

Exit codes
----------
- 0: shipped ./Dockerfile honors the contract (or every divergence is allowlisted).
- 1: contract violation(s); offending facets printed to stderr.
- 2: structural / usage error (oracle missing — run ``make build`` first;
  ./Dockerfile or packaging-overrides.yaml missing or unparseable).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from dockerfile_facets import Facets, parse_facets  # noqa: E402

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[0-9]+(\.[0-9]+)+")


class PackagingContractError(RuntimeError):
    """Structural failure (exit 2) — repo is not in a state we can check."""

    def __init__(self, message: str, *, step: str) -> None:
        super().__init__(f"[{step}] {message}")
        self.step = step


def _is_pinned_value(value: str | None) -> bool:
    """True if an ARG value looks like a version or sha256 pin worth tracking."""
    if value is None:
        return False
    return bool(_SHA256_RE.match(value) or _VERSION_RE.match(value))


def _read(path: Path, *, step: str, hint: str) -> str:
    if not path.exists():
        raise PackagingContractError(f"{path} missing — {hint}", step=step)
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - unusual IO failure
        raise PackagingContractError(f"cannot read {path}: {exc}", step=step) from exc


def _load_manifest(path: Path) -> dict:
    import yaml  # local import: pyyaml is a build/dev dep, not a runtime one

    text = _read(path, step="manifest", hint="the override manifest is required")
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise PackagingContractError(f"unparseable YAML in {path}: {exc}", step="manifest") from exc
    if not isinstance(data, dict):
        raise PackagingContractError(f"{path} must be a mapping at top level", step="manifest")
    return data


def _exception_keys(entries, key: str) -> set[str]:
    """Collect the values of ``key`` across a manifest exception list."""
    out: set[str] = set()
    for entry in entries or []:
        if isinstance(entry, dict) and key in entry:
            out.add(str(entry[key]))
    return out


# ---------------------------------------------------------------------------
# The five checks. Each appends human-readable violation strings.
# ---------------------------------------------------------------------------

def _check_from_digests(oracle: Facets, shipped: Facets, allow: set[str], violations: list[str]) -> None:
    shipped_by_name = {f.image.rsplit("/", 1)[-1]: f for f in shipped.froms}
    for ref in oracle.froms:
        if ref.digest is None:
            continue
        base = ref.image.rsplit("/", 1)[-1]
        if base in allow:
            continue
        ship = shipped_by_name.get(base)
        if ship is None:
            violations.append(
                f"FROM: upstream uses digest-pinned image '{ref.image}' "
                f"({ref.digest}) but the shipped Dockerfile has no '{base}' image "
                f"and it is not in from_exceptions"
            )
        elif ship.digest != ref.digest:
            violations.append(
                f"FROM: '{base}' digest drifted from upstream — oracle={ref.digest} "
                f"shipped={ship.digest}; mirror the bump or add a from_exceptions entry"
            )


def _check_pinned_args(oracle: Facets, shipped: Facets, allow: set[str], violations: list[str]) -> None:
    for name, value in oracle.args.items():
        if not _is_pinned_value(value) or name in allow:
            continue
        ship_value = shipped.args.get(name)
        if ship_value is None:
            violations.append(
                f"ARG: upstream pins {name}={value} but the shipped Dockerfile "
                f"does not define it (supply-chain pin not mirrored)"
            )
        elif ship_value != value:
            violations.append(
                f"ARG: {name} drifted from upstream — oracle={value} shipped={ship_value}"
            )


def _check_apt_superset(oracle: Facets, shipped: Facets, allow: set[str], violations: list[str]) -> None:
    missing = oracle.apt_packages - shipped.apt_packages - allow
    for pkg in sorted(missing):
        violations.append(
            f"apt: upstream installs system dep '{pkg}' but it is absent from the "
            f"shipped image's apt closure and from apt_exceptions"
        )


def _check_extras(oracle: Facets, shipped: Facets, allow: set[str], violations: list[str]) -> None:
    missing = oracle.install_extras - shipped.install_extras - allow
    for extra in sorted(missing):
        violations.append(
            f"extras: upstream installs the '{extra}' extra but the shipped image "
            f"neither installs it nor records it in extras_exceptions"
        )


def _check_stale_exceptions(oracle: Facets, manifest: dict, violations: list[str]) -> None:
    for img in _exception_keys(manifest.get("from_exceptions"), "image"):
        if oracle.image_by_name(img) is None:
            violations.append(
                f"stale from_exceptions: '{img}' is no longer a digest image in "
                f"upstream's Dockerfile — remove the exception"
            )
    for pkg in _exception_keys(manifest.get("apt_exceptions"), "package"):
        if pkg not in oracle.apt_packages:
            violations.append(
                f"stale apt_exceptions: upstream no longer apt-installs '{pkg}' — "
                f"remove the exception"
            )
    for extra in _exception_keys(manifest.get("extras_exceptions"), "extra"):
        if extra not in oracle.install_extras:
            violations.append(
                f"stale extras_exceptions: upstream no longer installs the '{extra}' "
                f"extra — remove the exception"
            )


def check_packaging_contract(repo_root: Path) -> list[str]:
    """Run all checks; return violation strings. Raise on structural errors."""
    oracle_path = repo_root / "dist" / "argo" / "Dockerfile"
    shipped_path = repo_root / "Dockerfile"
    manifest_path = repo_root / "packaging-overrides.yaml"

    oracle = parse_facets(
        _read(oracle_path, step="oracle", hint="run `make build` to produce the oracle first")
    )
    shipped = parse_facets(
        _read(shipped_path, step="shipped", hint="the shipped Dockerfile is required")
    )
    manifest = _load_manifest(manifest_path)

    violations: list[str] = []
    _check_from_digests(oracle, shipped, _exception_keys(manifest.get("from_exceptions"), "image"), violations)
    _check_pinned_args(oracle, shipped, _exception_keys(manifest.get("pinned_arg_exceptions"), "name"), violations)
    _check_apt_superset(oracle, shipped, _exception_keys(manifest.get("apt_exceptions"), "package"), violations)
    _check_extras(oracle, shipped, _exception_keys(manifest.get("extras_exceptions"), "extra"), violations)
    _check_stale_exceptions(oracle, manifest, violations)
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the shipped Dockerfile has not silently diverged from "
        "upstream's packaging (the renamed-upstream oracle dist/argo/Dockerfile)."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).parent.parent,
        help="repo root (default: the parent of tools/)",
    )
    args = parser.parse_args(argv)

    try:
        violations = check_packaging_contract(args.repo_root)
    except PackagingContractError as exc:
        print(f"packaging-contract: {exc}", file=sys.stderr)
        return 2

    if violations:
        print(
            "packaging-contract: shipped ./Dockerfile diverges from upstream "
            f"({len(violations)} issue(s)):",
            file=sys.stderr,
        )
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        print(
            "\nResolve by either mirroring upstream's decision into ./Dockerfile, "
            "or recording a reviewed divergence in packaging-overrides.yaml.",
            file=sys.stderr,
        )
        return 1

    print("packaging-contract: shipped ./Dockerfile tracks upstream (or all "
          "divergences are allowlisted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
