"""Desktop-gateway adapter for the Nadia Agents Portal activation ceremony.

The desktop app signs a provider in through the local FastAPI gateway with a
device-code-shaped contract: ``POST /api/providers/oauth/nadia/start`` returns a
verification URL + user code, and the renderer polls
``GET /api/providers/oauth/nadia/poll/<session>`` until a background worker marks
the session ``approved``. Upstream's ``nous`` provider drove a Better Auth
device-code flow; NadicodeAI's ``nous`` provider instead runs the portal
activation ceremony (start → poll → complete → ack → promote) implemented in
:mod:`nadia_cli.portal_activation`.

This module adapts that ceremony onto the gateway's existing session model so
**no renderer or gateway response shape changes**:

* :func:`start_nous_portal_activation` runs the portal ``start`` synchronously
  (via :func:`portal_activation.begin_activation`) and returns the exact
  device-code start fields the renderer expects (``session_id``, ``flow``,
  ``user_code``, ``verification_url``, ``expires_in``, ``poll_interval``).
* A background worker then advances poll → complete → ack → promote, writing
  ``session["status"]`` — the field the shared, unchanged poll endpoint reports.
  ``approved`` on success; ``denied`` / ``expired`` / ``error`` on failure,
  mapped onto the renderer's existing terminal states.
* Cancellation (the renderer deleting the session) is honored cooperatively:
  the worker aborts its poll wait instead of promoting a credential the user no
  longer wants.

On success the worker also records a default model for the portal-managed
provider (resolved from the vended credential's ``/models`` list) so onboarding
lands on a concrete model without the portal needing to serve a
recommended-models route the control plane does not expose.

The gateway session registry and profile-scope primitives are **injected** by
the (content-edited) ``web_server`` call site rather than imported, so this
overlay stays decoupled from ``web_server`` internals and is unit-testable in
isolation. All identifiers are nadia-named and renamed to nadia at build time.
"""

from __future__ import annotations

import threading
import time
from contextlib import nullcontext
from typing import Any, Callable, Dict, Optional

from nadia_portal import portal_activation, portal_store

# Advisory poll cadence returned to the renderer (it polls on its own fixed
# interval; this only mirrors the legacy device-code start response).
_DEFAULT_POLL_INTERVAL = 5
# Fallback approval window (seconds) when the portal gives no expiry to echo.
_DEFAULT_APPROVAL_WINDOW = 15 * 60
# Short timeout for the best-effort vended-model discovery call.
_MODELS_FETCH_TIMEOUT = 8.0
# The provider the desktop persists post-activation; runtime resolution routes
# it to the portal credential (see portal_activation.maybe_resolve_portal_runtime).
_MANAGED_PROVIDER = "nous"


class _Cancelled(Exception):
    """Raised inside the worker when the renderer cancelled the session."""


def _noop(_msg: str) -> None:
    return None


# ---------------------------------------------------------------------------
# Public entrypoint (invoked from web_server's nadia branch via content_edit)
# ---------------------------------------------------------------------------

def start_nous_portal_activation(
    *,
    profile: Optional[str],
    new_session: Callable[..., Any],
    sessions: Dict[str, Dict[str, Any]],
    sessions_lock: Any,
    config_profile_scope: Callable[[Optional[str]], Any],
    portal_url: Optional[str] = None,
    http_session_factory: Optional[Callable[[], Any]] = None,
    thread_launcher: Optional[Callable[..., None]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Begin the portal ceremony for the desktop ``nous`` provider.

    Runs synchronously (the caller offloads it to a worker thread), returning
    the device-code start response the renderer expects. A background worker
    then advances the ceremony and updates ``session["status"]``.

    Injected dependencies (from ``web_server``):

    * ``new_session(provider_id, flow, profile)`` → ``(session_id, session)``.
    * ``sessions`` / ``sessions_lock`` — the shared OAuth session registry the
      poll and cancel endpoints already read.
    * ``config_profile_scope(profile)`` — an await-safe scope that redirects
      ``get_nadia_home()`` so profile-local credential/config writes land in
      the right profile home.
    """
    sid, sess = new_session(_MANAGED_PROVIDER, "device_code", profile)
    factory = http_session_factory or portal_activation._new_session

    http = factory()
    try:
        with config_profile_scope(profile):
            base_url = portal_activation.resolve_portal_base_url(portal_url)
            outcome = portal_activation.begin_activation(
                http,
                base_url,
                replace=False,
                out=_noop,
            )
    except portal_activation.PortalActivationError as exc:
        _set_status(sessions, sessions_lock, sid, "error", str(exc))
        _close(http)
        return _start_response(sid, "https://portal.nadicode.ai", display=None)
    except Exception as exc:  # normalize any unexpected failure to a session error
        _set_status(sessions, sessions_lock, sid, "error", str(exc))
        _close(http)
        return _start_response(sid, "https://portal.nadicode.ai", display=None)

    kind = outcome["kind"]

    if kind == "already_active":
        # Already connected: report success so the renderer proceeds straight to
        # its model-confirm step. No verification page is opened for real; the
        # fallback device URL is harmless if the renderer opens it.
        _set_status(sessions, sessions_lock, sid, "approved")
        _close(http)
        return _start_response(sid, base_url, display=None)

    if kind == "already_connected_remote":
        _set_status(
            sessions,
            sessions_lock,
            sid,
            "error",
            "This profile is already connected to a Nadia Agent. Ask an operator "
            "to start a replacement to bind a new credential to it.",
        )
        _close(http)
        return _start_response(sid, base_url, display=None)

    # kind in {"pending", "resume_staged"}: advance the ceremony in a worker.
    display = outcome.get("display")
    sess["expires_at"] = _approval_epoch(display)
    launcher = thread_launcher or _default_thread_launcher
    launcher(
        _run_worker,
        sid,
        sessions,
        sessions_lock,
        config_profile_scope,
        profile,
        base_url,
        outcome,
        http,
        sleep,
    )
    return _start_response(sid, base_url, display=display)


# ---------------------------------------------------------------------------
# Background worker: poll → complete → ack → promote → default model
# ---------------------------------------------------------------------------

def _run_worker(
    sid: str,
    sessions: Dict[str, Dict[str, Any]],
    sessions_lock: Any,
    config_profile_scope: Callable[[Optional[str]], Any],
    profile: Optional[str],
    base_url: str,
    outcome: Dict[str, Any],
    http: Any,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Advance the ceremony to completion and report through ``session[status]``."""
    stable_id = outcome["stable_id"]
    try:
        with config_profile_scope(profile):
            verify = portal_activation._verify_tls(base_url)

            def _cancellable_sleep(seconds: float) -> None:
                # Break the poll wait promptly if the renderer cancelled (the
                # session is popped from the registry on DELETE).
                if not _session_alive(sessions, sessions_lock, sid):
                    raise _Cancelled()
                sleep(seconds)

            if outcome["kind"] == "resume_staged":
                portal_activation.finish_from_staged(
                    http, outcome["staged"], stable_id, _noop, resumed=True
                )
            else:
                staged = portal_activation.drive_pending(
                    http,
                    base_url,
                    verify=verify,
                    pending=outcome["pending"],
                    stable_id=stable_id,
                    out=_noop,
                    sleep=_cancellable_sleep,
                )
                if not _session_alive(sessions, sessions_lock, sid):
                    raise _Cancelled()
                portal_activation.finish_from_staged(
                    http, staged, stable_id, _noop, resumed=False
                )

            # Credential is now active for this profile. Record a default model
            # so onboarding lands on a concrete model (best-effort; below).
            _record_default_model()

        _set_status(sessions, sessions_lock, sid, "approved")
    except _Cancelled:
        # Session already removed by the cancel endpoint; nothing to report.
        return
    except portal_activation.PortalActivationError as exc:
        status, message = _map_error(str(exc))
        _set_status(sessions, sessions_lock, sid, status, message)
    except Exception as exc:  # never let a worker crash silently swallow status
        _set_status(sessions, sessions_lock, sid, "error", str(exc))
    finally:
        _close(http)


# ---------------------------------------------------------------------------
# Default-model resolution (part D: the control plane serves no model catalog)
# ---------------------------------------------------------------------------

def _record_default_model(
    http_session_factory: Optional[Callable[[], Any]] = None,
) -> None:
    """Persist a sensible default model for the freshly-activated profile.

    The portal is a control plane and does not serve a recommended-models route,
    so the renderer's opportunistic model list can come back empty. We resolve a
    concrete default from the vended credential's own ``/models`` endpoint (the
    supplier's public list — fetching it with the vended key is allowed) and
    persist ``model.provider=nadia`` + ``model.default`` so chat has a real model
    without the control plane advertising one. Entirely best-effort: on any
    failure runtime resolution still routes ``nous``/``auto`` to the portal
    credential and the user can pick a model in the UI.
    """
    try:
        cred = portal_store.read_active_credential()
    except Exception:
        cred = None
    if not cred:
        return
    model_id = _discover_default_model(
        cred["base_url"], cred["api_key"], http_session_factory
    )
    if not model_id:
        return
    _persist_default_model(model_id)


def _discover_default_model(
    base_url: str,
    api_key: str,
    http_session_factory: Optional[Callable[[], Any]] = None,
) -> str:
    """Return the first model id advertised at ``<base_url>/models``, or ``""``.

    Never raises and never logs the vended key; the key is sent only to the
    credential's own base URL, exactly as inference traffic is.
    """
    factory = http_session_factory or portal_activation._new_session
    url = base_url.rstrip("/") + "/models"
    session = factory()
    try:
        response = session.request(
            "GET",
            url,
            headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"},
            timeout=_MODELS_FETCH_TIMEOUT,
        )
        if getattr(response, "status_code", 0) != 200:
            return ""
        body = response.json()
    except Exception:
        return ""
    finally:
        _close(session)

    if isinstance(body, dict):
        entries = body.get("data")
    else:
        entries = body
    if not isinstance(entries, list):
        return ""
    for entry in entries:
        if isinstance(entry, dict):
            model_id = str(entry.get("id") or "").strip()
            if model_id:
                return model_id
        elif isinstance(entry, str) and entry.strip():
            return entry.strip()
    return ""


def _persist_default_model(model_id: str) -> None:
    """Write ``model.provider=nadia`` + ``model.default`` to the profile config.

    Runs inside the worker's ``config_profile_scope`` so it lands in the active
    profile. Clears stale endpoint credentials when switching provider (the old
    ``base_url``/``api_key`` belonged to a different provider); the portal
    credential itself lives in profile-local storage, not in config.
    """
    try:
        from nadia_cli.config import load_config, save_config

        cfg = load_config()
        model_cfg = dict(cfg.get("model") or {})
        previous = str(model_cfg.get("provider") or "").strip().lower()
        model_cfg["provider"] = _MANAGED_PROVIDER
        model_cfg["default"] = model_id
        if previous != _MANAGED_PROVIDER:
            for stale in ("base_url", "api_key", "api", "api_mode", "context_length"):
                model_cfg.pop(stale, None)
        else:
            model_cfg.pop("context_length", None)
        cfg["model"] = model_cfg
        save_config(cfg)
    except Exception:
        # Best-effort only: provider still resolves via maybe_resolve_portal_runtime.
        pass


# ---------------------------------------------------------------------------
# Session-registry + response helpers
# ---------------------------------------------------------------------------

def _start_response(sid: str, base_url: str, *, display: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the device-code start response shape the renderer expects."""
    fallback_url = base_url.rstrip("/") + "/device"
    if display:
        user_code = str(display.get("user_code") or "")
        verification_url = str(display.get("verification_url") or "") or fallback_url
        expires_in = _seconds_until(display.get("approval_expires_at")) or _DEFAULT_APPROVAL_WINDOW
        poll_interval = int(display.get("poll_interval_seconds") or _DEFAULT_POLL_INTERVAL)
    else:
        user_code = ""
        verification_url = fallback_url
        expires_in = _DEFAULT_APPROVAL_WINDOW
        poll_interval = _DEFAULT_POLL_INTERVAL
    return {
        "session_id": sid,
        "flow": "device_code",
        "user_code": user_code,
        "verification_url": verification_url,
        "expires_in": int(expires_in),
        "poll_interval": int(poll_interval),
    }


def _set_status(
    sessions: Dict[str, Dict[str, Any]],
    sessions_lock: Any,
    sid: str,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    with (sessions_lock or nullcontext()):
        sess = sessions.get(sid)
        if sess is not None:
            sess["status"] = status
            if error_message is not None:
                sess["error_message"] = error_message


def _session_alive(sessions: Dict[str, Dict[str, Any]], sessions_lock: Any, sid: str) -> bool:
    with (sessions_lock or nullcontext()):
        return sid in sessions


def _map_error(message: str) -> tuple[str, str]:
    """Map a PortalActivationError message onto a renderer terminal status."""
    low = message.lower()
    if "denied" in low:
        return "denied", message
    if "expired" in low or "timed out" in low or "confirmation window" in low:
        return "expired", message
    return "error", message


def _seconds_until(iso_value: Any) -> Optional[int]:
    """Whole seconds until an ISO-8601 UTC timestamp, or ``None`` if unparsable."""
    if not isinstance(iso_value, str) or not iso_value.strip():
        return None
    text = iso_value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        from datetime import datetime, timezone

        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int(parsed.timestamp() - time.time()))
    except Exception:
        return None


def _approval_epoch(display: Optional[Dict[str, Any]]) -> Optional[float]:
    if not display:
        return None
    seconds = _seconds_until(display.get("approval_expires_at"))
    return time.time() + seconds if seconds is not None else None


def _default_thread_launcher(target: Callable[..., None], *args: Any) -> None:
    threading.Thread(target=target, args=args, daemon=True, name="portal-activation").start()


def _close(session: Any) -> None:
    try:
        session.close()
    except Exception:
        pass
