"""tools/dockerfile_facets.py — extract toolchain-relevant facets from a Dockerfile.

This is the parsing half of the packaging-contract gate (see
``tools/check_packaging_contract.py``). It turns Dockerfile text into a small,
comparable ``Facets`` record so the gate can diff what our shipped
``./Dockerfile`` pins against the renamed-upstream oracle (``dist/nadia/Dockerfile``,
produced verbatim from ``upstream/Dockerfile`` by ``make build``).

Why a real parser and not a regex grab-bag: the things that silently drift away
from upstream are *pinned external toolchains* (the ``node:22`` base digest, the
s6-overlay version + checksums) and *additive* changes (a new apt system dep, a
new install extra). Each needs to be extracted structurally — joining backslash
continuations, ignoring comments, and isolating the ``apt-get install`` argument
list from the surrounding shell — so a comment token or a flag is never mistaken
for a package.

stdlib only (no pyyaml here — the gate owns config loading). Pure functions; no
filesystem or process side effects.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImageRef:
    """One ``FROM`` image reference, split into its comparable parts.

    ``raw`` is the full ``image[:tag][@digest]`` token as written, so the gate
    can show the exact string on a mismatch. ``stage`` is the ``AS <name>``
    alias (or None). A bare stage reference (``FROM runtime-slim``) has the
    prior stage name as ``image`` and no tag/digest.
    """

    raw: str
    image: str
    tag: str | None
    digest: str | None
    stage: str | None


@dataclass(frozen=True)
class Facets:
    """The toolchain-relevant surface of a Dockerfile, ready to diff."""

    froms: tuple[ImageRef, ...] = ()
    args: dict[str, str | None] = field(default_factory=dict)
    apt_packages: frozenset[str] = frozenset()
    env: dict[str, str] = field(default_factory=dict)
    entrypoint: tuple[str, ...] | None = None
    cmd: tuple[str, ...] | None = None
    install_extras: frozenset[str] = frozenset()

    def image_by_name(self, name: str) -> ImageRef | None:
        """Return the LAST ``FROM`` whose image basename is ``name``.

        Used to locate the node-source stage (image ``node``) regardless of
        which stage alias it carries. Last-wins matches Docker's own
        "later instruction shadows earlier" semantics.
        """
        found = None
        for ref in self.froms:
            if ref.image == name or ref.image.rsplit("/", 1)[-1] == name:
                found = ref
        return found


# ---------------------------------------------------------------------------
# Instruction tokenizer
# ---------------------------------------------------------------------------

_CONT_RE = re.compile(r"\\\s*\n")


def _logical_lines(text: str) -> list[str]:
    """Yield logical Dockerfile instructions with continuations joined.

    Full-line comments are dropped first (a ``#`` at the start of a physical
    line, including inside a continued RUN block — Dockerfile treats those as
    comments). Backslash-newline continuations are then collapsed so each
    instruction is one string.
    """
    # Drop full-line comments (leading whitespace allowed). Trailing inline
    # ``#`` is NOT stripped — it is not a comment in Dockerfile shell form.
    decommented = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    joined = _CONT_RE.sub(" ", decommented)
    return [ln.strip() for ln in joined.splitlines() if ln.strip()]


def _instruction(line: str) -> tuple[str, str]:
    """Split a logical line into (UPPERCASE keyword, remainder)."""
    parts = line.split(None, 1)
    if not parts:
        return "", ""
    return parts[0].upper(), (parts[1] if len(parts) > 1 else "")


# ---------------------------------------------------------------------------
# Per-instruction extractors
# ---------------------------------------------------------------------------

def _parse_from(rest: str) -> ImageRef:
    """Parse the argument of a ``FROM`` instruction into an :class:`ImageRef`."""
    toks = rest.split()
    # Drop a leading --platform=... flag if present.
    toks = [t for t in toks if not t.startswith("--")]
    image_token = toks[0] if toks else ""
    stage = None
    if len(toks) >= 3 and toks[1].upper() == "AS":
        stage = toks[2]

    digest = None
    tag = None
    ref = image_token
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    # A tag colon is only a tag if it appears after the last '/' (host:port
    # would contain a colon before the path).
    if ":" in ref.rsplit("/", 1)[-1]:
        ref, tag = ref.rsplit(":", 1)
    return ImageRef(raw=image_token, image=ref, tag=tag, digest=digest, stage=stage)


def _parse_arg(rest: str) -> tuple[str, str | None]:
    """Parse ``ARG NAME[=value]`` into (name, value-or-None)."""
    if "=" in rest:
        name, value = rest.split("=", 1)
        return name.strip(), value.strip()
    return rest.strip(), None


def _parse_env(rest: str) -> dict[str, str]:
    """Parse an ``ENV`` instruction.

    Supports both ``ENV key=value [key2=value2 ...]`` and the legacy
    ``ENV key value`` single-pair form. Values may be quoted.
    """
    rest = rest.strip()
    out: dict[str, str] = {}
    first_token = rest.split(None, 1)[0] if rest.split() else ""
    if "=" in first_token:
        # key=value form (possibly several). Split on top-level whitespace,
        # honoring quotes.
        for tok in _split_env_pairs(rest):
            if "=" in tok:
                k, v = tok.split("=", 1)
                out[k.strip()] = _unquote(v.strip())
    else:
        # Legacy ``ENV key value`` single-pair form.
        parts = rest.split(None, 1)
        if len(parts) == 2:
            out[parts[0].strip()] = _unquote(parts[1].strip())
    return out


def _split_env_pairs(rest: str) -> list[str]:
    """Whitespace-split ``key=value`` pairs while respecting quoted values."""
    return re.findall(r'(?:[^\s"\']+|"[^"]*"|\'[^\']*\')+', rest)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_exec_vector(rest: str) -> tuple[str, ...] | None:
    """Parse the exec (JSON-array) form of ENTRYPOINT/CMD, e.g. ``[ "a", "b" ]``.

    Returns a tuple of args, ``()`` for an empty vector, or None for the shell
    (non-JSON) form (which we do not currently model).
    """
    rest = rest.strip()
    if not rest.startswith("["):
        return None
    try:
        parsed = json.loads(rest)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list):
        return tuple(str(x) for x in parsed)
    return None


_APT_INSTALL_RE = re.compile(r"apt-get\s+install\b(.*?)(?:&&|;|$)", re.DOTALL)
_FLAG_RE = re.compile(r"^-")


def _extract_apt(run_body: str) -> set[str]:
    """Extract installed package names from a (joined) RUN instruction body.

    Isolates each ``apt-get install ...`` argument list (up to the next ``&&``
    or ``;``), drops flags (``-y``, ``--no-install-recommends``), and keeps
    package-shaped tokens. Multiple install invocations in one RUN are unioned.
    """
    pkgs: set[str] = set()
    for match in _APT_INSTALL_RE.finditer(run_body):
        for tok in match.group(1).split():
            if _FLAG_RE.match(tok):
                continue
            # Package names: letters/digits and -+._ (covers libffi-dev,
            # python3-dev, g++, ca-certificates). Anything with shell syntax
            # ($, /, quotes) is not a package.
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", tok):
                pkgs.add(tok)
    return pkgs


_EXTRA_RE = re.compile(r"--extra\s+([A-Za-z0-9][A-Za-z0-9._-]*)")
_PIP_EXTRAS_RE = re.compile(r"-e\s+[\"']?\.\[([^\]]+)\]")


def _extract_extras(run_body: str) -> set[str]:
    """Extract Python install extras from ``uv sync --extra X`` / ``pip ... .[x,y]``."""
    extras = set(_EXTRA_RE.findall(run_body))
    for grp in _PIP_EXTRAS_RE.findall(run_body):
        extras.update(p.strip() for p in grp.split(",") if p.strip())
    return extras


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_facets(text: str) -> Facets:
    """Extract :class:`Facets` from Dockerfile ``text``.

    ENTRYPOINT/CMD use last-wins (final stage shadows earlier ones), matching
    Docker. apt packages and install extras are unioned across all stages,
    because the gate compares the WHOLE shipped image's reachable surface
    against the single-stage oracle.
    """
    froms: list[ImageRef] = []
    args: dict[str, str | None] = {}
    env: dict[str, str] = {}
    apt: set[str] = set()
    extras: set[str] = set()
    entrypoint: tuple[str, ...] | None = None
    cmd: tuple[str, ...] | None = None

    for line in _logical_lines(text):
        kw, rest = _instruction(line)
        if kw == "FROM":
            froms.append(_parse_from(rest))
        elif kw == "ARG":
            name, value = _parse_arg(rest)
            # First definition wins for a default; later bare re-decls in other
            # stages don't erase it.
            if name not in args or value is not None:
                args[name] = value
        elif kw == "ENV":
            env.update(_parse_env(rest))
        elif kw == "RUN":
            apt |= _extract_apt(rest)
            extras |= _extract_extras(rest)
        elif kw == "ENTRYPOINT":
            vec = _parse_exec_vector(rest)
            if vec is not None:
                entrypoint = vec
        elif kw == "CMD":
            vec = _parse_exec_vector(rest)
            if vec is not None:
                cmd = vec

    return Facets(
        froms=tuple(froms),
        args=args,
        apt_packages=frozenset(apt),
        env=env,
        entrypoint=entrypoint,
        cmd=cmd,
        install_extras=frozenset(extras),
    )
