"""Profile-local storage for NadicodeAI Portal activation.

Every piece of portal state — the profile-local stable identity, the staged and
active runtime credentials, the pending-poll handle, and the non-secret binding
metadata — lives under the ACTIVE profile home only, in
``get_nadia_home()/portal-activation/``. This module never reads the
global-root auth store or the shared cross-profile credential pool, so a portal
credential can never leak across profiles or be served through the global
fallback (contract "Client obligations"; requirements R5/R6/R8).

Two safety properties are enforced here rather than by callers:

* **Owner-only secrets.** Credential, token, nonce, and poll-handle files are
  written 0600 inside a 0700 directory, matching the ``auth.json`` protections.
* **Copy detection.** Every JSON payload records the resolved home path it was
  written under (``_home``). A profile directory copied or restored to a
  different location reads back as *foreign*, so its identity and credentials are
  ignored and quarantined and the profile must re-activate (contract clone/import
  obligation; requirements R9-R12).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

from nadia_constants import get_nadia_home

PORTAL_DIRNAME = "portal-activation"

IDENTITY_FILE = "identity.json"
PENDING_FILE = "pending.json"
STAGED_FILE = "staged.json"
CREDENTIAL_FILE = "credential.json"
BINDING_FILE = "binding.json"
LOCK_FILE = "connect.lock"
QUARANTINE_DIRNAME = "quarantine"

_LOCK_TIMEOUT_SECONDS = 10.0

# Fields that hold high-entropy bearer secrets. Never log or print their values.
SECRET_KEYS = frozenset(
    {"api_key", "activation_token", "poll_handle", "delivery_nonce"}
)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _home() -> Path:
    return get_nadia_home()


def _home_fingerprint() -> str:
    """Resolved home path string used to detect copied/restored profiles."""
    try:
        return str(_home().resolve(strict=False))
    except Exception:
        return str(_home())


def portal_root() -> Path:
    """Return the profile-local portal directory, creating it 0700 on demand.

    Seat belt (mirrors ``auth._auth_file_path``): under pytest, refuse to touch
    the real user's ``~/.nadia/portal-activation`` so a test that forgot to
    redirect ``NADIA_HOME`` cannot corrupt or leak real credentials.
    """
    root = _home() / PORTAL_DIRNAME
    if os.environ.get("PYTEST_CURRENT_TEST"):
        real = (Path.home() / ".nadia" / PORTAL_DIRNAME).resolve(strict=False)
        try:
            resolved = root.resolve(strict=False)
        except Exception:
            resolved = root
        if resolved == real:
            raise RuntimeError(
                f"Refusing to touch real user portal store during test run: {root}. "
                "Set NADIA_HOME to a tmp_path in your test fixture."
            )
    root.mkdir(parents=True, exist_ok=True)
    _chmod(root, 0o700)
    return root


def _chmod(path: Path, mode: int) -> None:
    if sys.platform == "win32":
        return
    try:
        os.chmod(path, mode)
    except (OSError, NotImplementedError):
        pass


def _atomic_write_secret(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically with owner-only (0600) perms."""
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".tmp-", suffix=".json")
    tmp_path = Path(tmp_name)
    try:
        _chmod(tmp_path, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        _chmod(path, 0o600)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _write_json(name: str, payload: Dict[str, Any]) -> None:
    data = dict(payload)
    data["_home"] = _home_fingerprint()
    _atomic_write_secret(portal_root() / name, json.dumps(data, indent=2, sort_keys=True))


def _read_json_raw(name: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Return ``(data, foreign)``.

    ``foreign`` is True when the payload was written under a different home path
    (a copied/restored profile). Missing/unparsable files return ``(None, False)``.
    """
    path = _home() / PORTAL_DIRNAME / name
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None, False
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None, False
    if not isinstance(data, dict):
        return None, False
    recorded = data.get("_home")
    foreign = recorded is not None and recorded != _home_fingerprint()
    return data, foreign


def _read_json(name: str) -> Optional[Dict[str, Any]]:
    data, foreign = _read_json_raw(name)
    if data is None or foreign:
        return None
    return data


def _unlink(name: str) -> None:
    try:
        (_home() / PORTAL_DIRNAME / name).unlink()
    except (FileNotFoundError, OSError):
        pass


# ---------------------------------------------------------------------------
# Profile-local stable identity
# ---------------------------------------------------------------------------

def load_or_create_stable_id() -> Tuple[str, bool]:
    """Return ``(stable_id, regenerated)`` for the active profile.

    Generates a fresh high-entropy id on first use. A foreign (copied) identity
    is quarantined and regenerated, and ``regenerated`` is True so the caller can
    tell the operator the profile must re-activate (R1-R4, R9-R12).
    """
    data, foreign = _read_json_raw(IDENTITY_FILE)
    if data is not None and not foreign and data.get("stable_id"):
        return str(data["stable_id"]), False

    regenerated = foreign
    if foreign:
        quarantine_all("copied-profile")
        _unlink(IDENTITY_FILE)

    stable_id = secrets.token_urlsafe(32)
    _write_json(IDENTITY_FILE, {"stable_id": stable_id, "created_at": _now_iso()})
    return stable_id, regenerated


def get_stable_id() -> Optional[str]:
    """Return the existing stable id without creating one (read-only callers)."""
    data = _read_json(IDENTITY_FILE)
    if data and data.get("stable_id"):
        return str(data["stable_id"])
    return None


def fingerprint(stable_id: str) -> str:
    """Short, non-secret identity fingerprint shown to the operator (R21)."""
    return hashlib.sha256(stable_id.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Pending poll handle (survives crashes during the approval wait)
# ---------------------------------------------------------------------------

def write_pending(state: Dict[str, Any]) -> None:
    _write_json(PENDING_FILE, state)


def read_pending() -> Optional[Dict[str, Any]]:
    return _read_json(PENDING_FILE)


def clear_pending() -> None:
    _unlink(PENDING_FILE)


# ---------------------------------------------------------------------------
# Staged credential (durably stored before ACK; ignored by runtime until active)
# ---------------------------------------------------------------------------

def write_staged(state: Dict[str, Any]) -> None:
    _write_json(STAGED_FILE, state)


def read_staged() -> Optional[Dict[str, Any]]:
    return _read_json(STAGED_FILE)


def clear_staged() -> None:
    _unlink(STAGED_FILE)


# ---------------------------------------------------------------------------
# Active credential + binding metadata (used for runtime resolution)
# ---------------------------------------------------------------------------

def write_active_credential(base_url: str, api_key: str) -> None:
    _write_json(
        CREDENTIAL_FILE,
        {"base_url": base_url, "api_key": api_key, "activated_at": _now_iso()},
    )


def read_active_credential() -> Optional[Dict[str, str]]:
    data = _read_json(CREDENTIAL_FILE)
    if not data:
        return None
    base_url = str(data.get("base_url") or "").strip()
    api_key = str(data.get("api_key") or "").strip()
    if not base_url or not api_key:
        return None
    return {"base_url": base_url, "api_key": api_key}


def clear_active() -> None:
    _unlink(CREDENTIAL_FILE)


def write_binding(meta: Dict[str, Any]) -> None:
    _write_json(BINDING_FILE, meta)


def read_binding() -> Optional[Dict[str, Any]]:
    return _read_json(BINDING_FILE)


def is_portal_managed() -> bool:
    """True when this profile completed a portal activation (binding present)."""
    binding = _read_json(BINDING_FILE)
    return bool(binding and binding.get("managed"))


# ---------------------------------------------------------------------------
# Quarantine — disable state that must never be used for inference
# ---------------------------------------------------------------------------

def quarantine_staged(reason: str) -> None:
    """Move the staged credential (and any active credential) out of use."""
    _quarantine_files([STAGED_FILE, CREDENTIAL_FILE], reason)


def quarantine_all(reason: str) -> None:
    """Move every credential/binding file out of use (copied-profile path)."""
    _quarantine_files([STAGED_FILE, CREDENTIAL_FILE, BINDING_FILE, PENDING_FILE], reason)


def _quarantine_files(names: list[str], reason: str) -> None:
    root = _home() / PORTAL_DIRNAME
    if not root.exists():
        return
    present = [name for name in names if (root / name).exists()]
    if not present:
        return
    dest = root / QUARANTINE_DIRNAME / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{reason}"
    dest.mkdir(parents=True, exist_ok=True)
    _chmod(root / QUARANTINE_DIRNAME, 0o700)
    _chmod(dest, 0o700)
    for name in present:
        try:
            os.replace(root / name, dest / name)
        except OSError:
            _unlink(name)


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def redact_secrets(text: str, values: Iterator[Any]) -> str:
    """Replace any secret substrings in ``text`` with a redaction marker."""
    result = text
    for value in values:
        token = str(value or "")
        if token:
            result = result.replace(token, "***redacted***")
    return result


# ---------------------------------------------------------------------------
# Activation lock — one connect per profile at a time (R23)
# ---------------------------------------------------------------------------

_lock_local = threading.local()


@contextmanager
def activation_lock(timeout_seconds: float = _LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Hold an advisory lock so concurrent ``portal connect`` runs can't race."""
    lock_path = portal_root() / LOCK_FILE
    try:
        import fcntl
    except ImportError:
        fcntl = None  # type: ignore[assignment]

    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    _chmod(lock_path, 0o600)
    acquired = False
    try:
        if fcntl is not None:
            deadline = time.monotonic() + timeout_seconds
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "Another `portal connect` is already running for this profile."
                        )
                    time.sleep(0.1)
        yield
    finally:
        if fcntl is not None and acquired:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        os.close(fd)
