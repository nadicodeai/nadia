"""``nadia portal connect`` — bind a Local Profile to a NadicodeAI Nadia Agent.

This is the agent-side client for the portal activation contract
(``portal/docs/nadia-agent-activation-contract.md``). It drives the four portal
routes — ``start`` -> ``poll`` -> ``complete`` -> ``ack`` — then promotes the
claimed runtime credential to active and records non-secret binding metadata.
Once a profile is activated, :func:`maybe_resolve_portal_runtime` routes managed
inference through the portal-issued ``base_url`` + ``api_key`` (requirements
R39-R60).

Design constraints honored here:

* Only portal wrapper endpoints are called; the raw Better Auth device-code flow
  is never touched, printed, or persisted (R24, R25).
* ``api_key``, ``activation_token``, ``poll_handle``, and ``delivery_nonce`` are
  bearer secrets — they never appear in stdout, logs, or exceptions (R35, R58).
* The credential is durably staged before ACK; ACK is idempotent and
  crash-recoverable; an expired claim quarantines the staged credential and
  fails closed (R40-R51).
* Runtime resolution reads only profile-local state and never falls back to the
  global-root/shared credential store (R8, R42, R60).

All identifiers are nadia-named and renamed to nadia at build time. Portal wire
field names (``profile_local_stable_id`` and friends) carry no brand token and
pass through the rename unchanged, matching the contract exactly.
"""

from __future__ import annotations

import logging
import os
import re
import socket
import time
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlsplit, urlunsplit

from nadia_cli import portal_store

logger = logging.getLogger(__name__)

# The REAL portal domain. Not portal.nadicodeai.com (a rebranded legacy default
# of the old flow). This literal domain has no rename token, so it survives the
DEFAULT_PORTAL_BASE_URL = "https://portal.nadicode.ai"

# Override env var, named consistently with the other portal env vars.
PORTAL_BASE_URL_ENV = "NADIA_PORTAL_BASE_URL"

_START_PATH = "/api/agent/activation/start"
_POLL_PATH = "/api/agent/activation/poll"
_COMPLETE_PATH = "/api/agent/activation/complete"
_ACK_PATH = "/api/agent/activation/ack"

_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 30.0
_DEFAULT_POLL_INTERVAL = 5
_MAX_APPROVAL_WAIT_SECONDS = 15 * 60
_MAX_CREDENTIAL_CREATING_WAIT = 2 * 60

# Runtime dict fields for an activated profile. provider="custom" +
# chat_completions matches the OpenAI-compatible endpoint the portal vends; the
# supplier behind base_url stays an implementation detail.
_RUNTIME_PROVIDER = "custom"
_RUNTIME_SOURCE = "nadicodeai-portal"

# Requested providers whose runtime resolves to the portal credential. ``auto``
# is the managed default path (FR4); ``nous`` is the explicitly-selected portal
# provider the desktop persists after activation (setModelAssignment provider
# "nous"). Any other explicit provider is advanced multi-provider use and opts
# out. An activated profile with a missing/quarantined credential still fails
# closed for both (never a silent global-root fallback; R60).
_PORTAL_RUNTIME_PROVIDERS = frozenset({"auto", "nous"})


class PortalActivationError(Exception):
    """User-facing activation failure. Its message is safe to print."""


# ---------------------------------------------------------------------------
# Portal base URL + TLS policy
# ---------------------------------------------------------------------------

def _is_local_host(hostname: str) -> bool:
    return (hostname or "").lower().rstrip(".") in {"localhost", "127.0.0.1", "::1"}


def resolve_portal_base_url(cli_url: Optional[str] = None) -> str:
    """Resolve the portal base URL from flag, env, then the shipped default.

    Enforces HTTPS with certificate validation for every non-local host; plain
    HTTP is permitted only for localhost/127.0.0.1 test fixtures (R27).
    """
    raw = (cli_url or os.environ.get(PORTAL_BASE_URL_ENV, "") or DEFAULT_PORTAL_BASE_URL).strip()
    if not raw:
        raw = DEFAULT_PORTAL_BASE_URL
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        raise PortalActivationError(f"Invalid portal URL: {raw!r}")
    host = parts.hostname or ""
    if parts.scheme == "http" and not _is_local_host(host):
        raise PortalActivationError(
            "Refusing to use an insecure portal URL. Use https:// "
            "(plain http is allowed only for localhost)."
        )
    if parts.scheme not in {"http", "https"}:
        raise PortalActivationError(f"Unsupported portal URL scheme: {parts.scheme!r}")
    # Normalize: drop any path/query/fragment, keep scheme + authority.
    return urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")


def _verify_tls(base_url: str) -> bool:
    """Whether requests should verify TLS certs (always, except local http)."""
    parts = urlsplit(base_url)
    if parts.scheme == "http" and _is_local_host(parts.hostname or ""):
        return False
    return True


# ---------------------------------------------------------------------------
# Portal-visible, sanitized approval metadata
# ---------------------------------------------------------------------------

def _sanitize_label(value: str, *, fallback: str, max_len: int = 60) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ._-]", "", (value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned[:max_len] or fallback)


def default_host_label() -> str:
    try:
        name = socket.gethostname().split(".")[0]
    except Exception:
        name = ""
    return _sanitize_label(name, fallback="nadia-host")


def default_profile_label() -> str:
    from nadia_constants import get_nadia_home

    home = get_nadia_home()
    name = "default"
    try:
        if home.parent.name == "profiles":
            name = home.name
    except Exception:
        name = "default"
    return _sanitize_label(name, fallback="default")


def _agent_version() -> str:
    try:
        from nadia_cli import __version__

        return str(__version__)
    except Exception:
        return "0.0.0"


# ---------------------------------------------------------------------------
# HTTP helpers (redaction-safe; requests is an upstream dependency)
# ---------------------------------------------------------------------------

def _new_session() -> Any:
    import requests

    return requests.Session()


def _retry_after_seconds(response: Any) -> Optional[int]:
    raw = response.headers.get("Retry-After") if getattr(response, "headers", None) else None
    if not raw:
        return None
    try:
        return max(0, int(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def _error_code(response: Any) -> str:
    try:
        body = response.json()
    except Exception:
        return ""
    if isinstance(body, dict):
        for key in ("error", "code", "status"):
            value = body.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _json_body(response: Any) -> Dict[str, Any]:
    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001 - normalize to a safe message
        raise PortalActivationError("Portal returned a non-JSON response.") from None
    if not isinstance(body, dict):
        raise PortalActivationError("Portal returned an unexpected response shape.")
    return body


def _request(
    session: Any,
    method: str,
    url: str,
    *,
    verify: bool,
    json_body: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    bearer: Optional[str] = None,
) -> Any:
    import requests

    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        return session.request(
            method,
            url,
            json=json_body,
            params=params,
            headers=headers,
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
            verify=verify,
        )
    except requests.exceptions.SSLError as exc:  # never echo secrets/URLs verbatim
        raise PortalActivationError(
            "Could not verify the portal's TLS certificate. Check the portal URL."
        ) from None
    except requests.exceptions.RequestException:
        raise PortalActivationError(
            "Could not reach the portal. Check your connection and try again."
        ) from None


# ---------------------------------------------------------------------------
# Contract calls
# ---------------------------------------------------------------------------

def start_activation(
    session: Any,
    base_url: str,
    *,
    host_label: str,
    local_profile_name: str,
    stable_id: str,
    agent_version: str,
) -> Dict[str, Any]:
    """POST /start. Returns the start payload, or a sentinel for reconnect states.

    Sentinels: ``{"already_connected": True}`` and ``{"pending_exists": True}``.
    """
    verify = _verify_tls(base_url)
    response = _request(
        session,
        "POST",
        base_url + _START_PATH,
        verify=verify,
        json_body={
            "host_label": host_label,
            "local_profile_name": local_profile_name,
            "profile_local_stable_id": stable_id,
            "agent_version": agent_version,
        },
    )
    if response.status_code == 200:
        return _json_body(response)
    if response.status_code == 409:
        code = _error_code(response)
        if code == "already_connected":
            return {"already_connected": True}
        if code == "pending_request_exists":
            return {"pending_exists": True}
        raise PortalActivationError("Portal rejected the activation request (conflict).")
    if response.status_code == 400 and _error_code(response) == "invalid_stable_id":
        raise PortalActivationError(
            "The portal rejected this profile's identity. Re-run activation to regenerate it."
        )
    if response.status_code == 429:
        wait = _retry_after_seconds(response)
        hint = f" Retry in {wait}s." if wait else ""
        raise PortalActivationError(f"Portal is rate limiting activation.{hint}")
    raise PortalActivationError(f"Portal start failed (HTTP {response.status_code}).")


def poll_activation(
    session: Any,
    poll_url: str,
    poll_handle: str,
    *,
    verify: bool,
    interval: int,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """GET /poll until a terminal state. Returns the ``approved`` payload.

    ``pending`` and ``approval_sync_failed`` are retryable waits; ``denied`` and
    ``expired`` raise; ``429`` backs off on ``Retry-After`` (R26).
    """
    wait = max(1, int(interval or _DEFAULT_POLL_INTERVAL))
    while True:
        if deadline is not None and monotonic() >= deadline:
            raise PortalActivationError(
                "Activation timed out waiting for approval. Run `nadia portal connect` again."
            )
        response = _request(
            session, "GET", poll_url, verify=verify, params={"handle": poll_handle}
        )
        status_code = response.status_code
        if status_code == 429:
            sleep(_retry_after_seconds(response) or wait)
            continue
        if status_code == 404:
            raise PortalActivationError("Portal did not recognize the activation handle.")
        if status_code == 409:
            raise PortalActivationError(
                "This activation was already claimed. Run `nadia portal connect` again."
            )
        if status_code != 200:
            raise PortalActivationError(f"Portal poll failed (HTTP {status_code}).")

        body = _json_body(response)
        status = str(body.get("status") or "")
        if status in {"pending", "approval_sync_failed"}:
            wait = max(1, int(body.get("poll_interval_seconds") or wait))
            sleep(wait)
            continue
        if status == "approved":
            return body
        if status == "denied":
            reason = str(body.get("reason") or "").strip()
            suffix = f" ({reason})" if reason else ""
            raise PortalActivationError(f"Activation was denied by the operator{suffix}.")
        if status == "expired":
            raise PortalActivationError(
                "Activation expired before approval. Run `nadia portal connect` again."
            )
        raise PortalActivationError(f"Portal returned an unknown poll status: {status!r}")


def complete_activation(
    session: Any,
    base_url: str,
    *,
    activation_token: str,
    activation_request_id: str,
    stable_id: str,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> Dict[str, Any]:
    """POST /complete. Claims the credential, retrying ``credential_creating``.

    The same token is reused across retries so the portal never mints a second
    supplier key (contract idempotency; R39).
    """
    verify = _verify_tls(base_url)
    deadline = monotonic() + _MAX_CREDENTIAL_CREATING_WAIT
    while True:
        response = _request(
            session,
            "POST",
            base_url + _COMPLETE_PATH,
            verify=verify,
            bearer=activation_token,
            json_body={
                "activation_request_id": activation_request_id,
                "profile_local_stable_id": stable_id,
            },
        )
        if response.status_code == 200:
            body = _json_body(response)
            credential = body.get("credential")
            if not isinstance(credential, dict):
                raise PortalActivationError("Portal did not return a credential.")
            base = str(credential.get("base_url") or "").strip()
            key = str(credential.get("api_key") or "").strip()
            nonce = str(body.get("delivery_nonce") or "").strip()
            if not base or not key or not nonce:
                raise PortalActivationError("Portal returned an incomplete credential.")
            return {
                "base_url": base,
                "api_key": key,
                "delivery_nonce": nonce,
                "ack_expires_at": body.get("ack_expires_at"),
            }
        if response.status_code == 409 and _error_code(response) == "credential_creating":
            if monotonic() >= deadline:
                raise PortalActivationError(
                    "Portal is still preparing the credential. Run `nadia portal connect` again."
                )
            sleep(_retry_after_seconds(response) or _DEFAULT_POLL_INTERVAL)
            continue
        if response.status_code == 401:
            raise PortalActivationError(
                "The portal rejected the activation token. Run `nadia portal connect` again."
            )
        if response.status_code == 429:
            sleep(_retry_after_seconds(response) or _DEFAULT_POLL_INTERVAL)
            continue
        raise PortalActivationError(f"Portal complete failed (HTTP {response.status_code}).")


def ack_activation(
    session: Any,
    base_url: str,
    *,
    activation_token: str,
    activation_request_id: str,
    stable_id: str,
    delivery_nonce: str,
) -> str:
    """POST /ack. Returns the terminal status; ``410`` raises ack_expired.

    Idempotent: an already-ACKed/active response is treated as success (R44,
    R45). ``410 ack_expired`` is a fail-closed signal for the caller to
    quarantine the staged credential (R51).
    """
    verify = _verify_tls(base_url)
    response = _request(
        session,
        "POST",
        base_url + _ACK_PATH,
        verify=verify,
        bearer=activation_token,
        json_body={
            "activation_request_id": activation_request_id,
            "profile_local_stable_id": stable_id,
            "delivery_nonce": delivery_nonce,
        },
    )
    if response.status_code == 200:
        return str(_json_body(response).get("status") or "active")
    if response.status_code == 410:
        raise PortalActivationError("ack_expired")
    if response.status_code == 409 and _error_code(response) in {
        "already_active",
        "already_acked",
    }:
        return "active"
    if response.status_code == 400 and _error_code(response) == "invalid_nonce":
        raise PortalActivationError("The portal rejected the delivery confirmation.")
    if response.status_code == 401:
        raise PortalActivationError("The portal rejected the activation token during confirmation.")
    raise PortalActivationError(f"Portal ack failed (HTTP {response.status_code}).")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _timestamp_passed(value: Any) -> bool:
    """True when an ISO-8601 UTC timestamp is in the past (or unparseable)."""
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        from datetime import datetime, timezone

        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp() <= time.time()
    except Exception:
        return False


def _promote(base_url: str, api_key: str, binding: Dict[str, Any]) -> None:
    """Write active credential, record binding, and clear staged/pending state."""
    portal_store.write_active_credential(base_url, api_key)
    portal_store.write_binding({**binding, "managed": True})
    portal_store.clear_staged()
    portal_store.clear_pending()


def finish_from_staged(
    session: Any,
    staged: Dict[str, Any],
    stable_id: str,
    out: Callable[[str], None],
    *,
    resumed: bool,
) -> int:
    """ACK a staged credential and promote it (phase 2b of activation).

    Shared by the CLI ``run_connect`` and the desktop gateway worker: both stage
    a credential (fresh claim or crash-recovery adoption) and then confirm it
    here.

    ``resumed`` distinguishes the two callers that reach ACK: a fresh activation
    that just staged its credential this run (``resumed=False``) versus a
    crash-recovery run that adopted a credential staged by an earlier,
    interrupted run (``resumed=True``). Only the crash-recovery path reports
    "Reconnected"; a first activation reports "Connected".
    """
    portal_base = str(staged.get("portal_base_url") or "")
    if _timestamp_passed(staged.get("ack_expires_at")):
        portal_store.quarantine_staged("ack-expired")
        raise PortalActivationError(
            "The previous activation's confirmation window expired. Run "
            "`nadia portal connect` again to re-activate."
        )
    try:
        status = ack_activation(
            session,
            portal_base,
            activation_token=str(staged.get("activation_token") or ""),
            activation_request_id=str(staged.get("activation_request_id") or ""),
            stable_id=stable_id,
            delivery_nonce=str(staged.get("delivery_nonce") or ""),
        )
    except PortalActivationError as exc:
        if str(exc) == "ack_expired":
            portal_store.quarantine_staged("ack-expired")
            raise PortalActivationError(
                "The activation credential expired before confirmation. Run "
                "`nadia portal connect` again to re-activate."
            ) from None
        raise
    if status not in {"active", "already_active", "already_acked"}:
        raise PortalActivationError(f"Portal reported an unexpected ack status: {status!r}")
    _promote(
        str(staged.get("base_url") or ""),
        str(staged.get("api_key") or ""),
        _binding_from_staged(staged, portal_base),
    )
    if resumed:
        out("Reconnected: durable credential confirmed and now active.")
    else:
        out("Connected: durable credential confirmed and now active.")
    return 0


def _binding_from_staged(staged: Dict[str, Any], portal_base: str) -> Dict[str, Any]:
    binding: Dict[str, Any] = {
        "portal_base_url": portal_base,
        "activation_request_id": staged.get("activation_request_id"),
        "connected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    # Bound customer/agent identity and credential correlation are not part of
    # the current portal contract, so the staged state never carries them. Write
    # a key only when a value is actually present rather than persisting
    # always-null placeholders; a future contract version can populate them.
    for key in ("credential_correlation", "customer", "agent"):
        value = staged.get(key)
        if value is not None:
            binding[key] = value
    return binding


def run_connect(
    *,
    portal_url: Optional[str] = None,
    replace: bool = False,
    host_label: Optional[str] = None,
    profile_label: Optional[str] = None,
    out: Callable[[str], None] = print,
    session: Optional[Any] = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> int:
    """Drive activation end-to-end for the active profile. Returns an exit code."""
    base_url = resolve_portal_base_url(portal_url)
    verify = _verify_tls(base_url)
    owns_session = session is None
    session = session or _new_session()
    try:
        with portal_store.activation_lock():
            return _run_connect_locked(
                base_url=base_url,
                verify=verify,
                replace=replace,
                host_label=host_label,
                profile_label=profile_label,
                out=out,
                session=session,
                sleep=sleep,
                monotonic=monotonic,
            )
    except TimeoutError as exc:
        raise PortalActivationError(str(exc)) from None
    finally:
        if owns_session:
            try:
                session.close()
            except Exception:
                pass


def _display_from_pending(pending: Dict[str, Any]) -> Dict[str, Any]:
    """Operator-facing prompt fields carried alongside a persisted pending.

    ``user_code`` and ``verification_url`` are display fields (not bearer
    secrets), persisted so a resumed pending can re-show the same prompt.
    """
    return {
        "user_code": str(pending.get("user_code") or ""),
        "verification_url": str(pending.get("verification_url") or ""),
        "approval_expires_at": pending.get("approval_expires_at"),
        "poll_interval_seconds": int(
            pending.get("poll_interval_seconds") or _DEFAULT_POLL_INTERVAL
        ),
    }


def begin_activation(
    session: Any,
    base_url: str,
    *,
    replace: bool = False,
    host_label: Optional[str] = None,
    profile_label: Optional[str] = None,
    agent_version: Optional[str] = None,
    out: Callable[[str], None] = lambda _msg: None,
) -> Dict[str, Any]:
    """Phase 1 of activation: resolve identity and decide the next step.

    Reuses the exact reconnect / crash-recovery / start decision ``run_connect``
    makes, but returns a structured outcome instead of driving the rest inline,
    so the CLI and the desktop gateway share one code path. Persists the pending
    poll handle (with display fields) or leaves a staged credential in place;
    never ACKs or promotes here.

    Returns a dict whose ``kind`` is one of:

    * ``already_active`` — a managed profile already holds an active credential.
    * ``resume_staged`` — an interrupted run left a staged credential to ACK.
    * ``pending`` — an approval is in flight (freshly started or resumed);
      ``pending`` carries the poll state, ``display`` the operator prompt, and
      (fresh only) ``start_result`` the raw start payload for CLI printing.
    * ``already_connected_remote`` — the portal reports this identity already
      maps to an active agent, but no local credential exists; re-activation
      needs an operator-initiated replacement.
    """
    stable_id, regenerated = portal_store.load_or_create_stable_id()
    if regenerated:
        out(
            "This profile looks copied or restored — generated a fresh identity. "
            "You must complete a new activation."
        )

    host = (
        _sanitize_label(host_label or "", fallback=default_host_label())
        if host_label
        else default_host_label()
    )
    profile = (
        _sanitize_label(profile_label or "", fallback=default_profile_label())
        if profile_label
        else default_profile_label()
    )
    version = agent_version or _agent_version()
    common = {"stable_id": stable_id, "host_label": host, "profile_label": profile}

    # Reconnect no-op: an already-active profile does not mint a new credential.
    if not replace and portal_store.is_portal_managed() and portal_store.read_active_credential():
        return {
            **common,
            "kind": "already_active",
            "binding": portal_store.read_binding() or {},
        }

    # Crash recovery: a staged (claimed-but-unACKed) credential resumes at ACK,
    # regardless of --replace (an interrupted replacement resumes its own claim).
    staged = portal_store.read_staged()
    if staged:
        return {**common, "kind": "resume_staged", "staged": staged}

    # Resume an unexpired pending approval wait from a stored handle.
    pending = portal_store.read_pending()
    if pending and not replace and not _timestamp_passed(pending.get("approval_expires_at")):
        return {
            **common,
            "kind": "pending",
            "pending": pending,
            "display": _display_from_pending(pending),
            "resumed": True,
        }
    if pending:
        portal_store.clear_pending()

    result = start_activation(
        session,
        base_url,
        host_label=host,
        local_profile_name=profile,
        stable_id=stable_id,
        agent_version=version,
    )
    if result.get("already_connected"):
        return {**common, "kind": "already_connected_remote"}
    if result.get("pending_exists"):
        raise PortalActivationError(
            "A pending activation already exists for this profile in the portal. "
            "Approve or let it expire, then run `nadia portal connect` again."
        )

    pending = {
        "activation_request_id": result.get("activation_request_id"),
        "poll_handle": result.get("poll_handle"),
        "poll_url": result.get("poll_url") or (base_url + _POLL_PATH),
        "poll_interval_seconds": result.get("poll_interval_seconds") or _DEFAULT_POLL_INTERVAL,
        "approval_expires_at": result.get("approval_expires_at"),
        "portal_base_url": base_url,
        # Display fields (non-secret) so a resumed pending re-shows the prompt.
        "user_code": str(result.get("user_code") or ""),
        "verification_url": str(result.get("verification_url") or ""),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    portal_store.write_pending(pending)
    return {
        **common,
        "kind": "pending",
        "pending": pending,
        "display": _display_from_pending(pending),
        "resumed": False,
        "start_result": result,
    }


def drive_pending(
    session: Any,
    base_url: str,
    *,
    verify: bool,
    pending: Dict[str, Any],
    stable_id: str,
    replace: bool = False,
    out: Callable[[str], None] = lambda _msg: None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    deadline: Optional[float] = None,
) -> Dict[str, Any]:
    """Phase 2a: poll for approval, claim the credential, and stage it durably.

    Returns the staged state (already written to profile-local storage). The
    caller then confirms it via :func:`finish_from_staged`. Injected ``sleep``
    lets a caller (e.g. the desktop worker) interrupt the poll wait to honor a
    cancellation.
    """
    poll_url = str(pending.get("poll_url") or (base_url + _POLL_PATH))
    interval = int(pending.get("poll_interval_seconds") or _DEFAULT_POLL_INTERVAL)
    if deadline is None:
        deadline = monotonic() + _MAX_APPROVAL_WAIT_SECONDS
    approved = poll_activation(
        session,
        poll_url,
        str(pending.get("poll_handle") or ""),
        verify=verify,
        interval=interval,
        sleep=sleep,
        monotonic=monotonic,
        deadline=deadline,
    )
    activation_request_id = str(pending.get("activation_request_id") or "")
    activation_token = str(approved.get("activation_token") or "")
    if not activation_token:
        raise PortalActivationError("Portal approved the request but returned no token.")
    out("Approved. Claiming the runtime credential…")

    # Complete → stage durably BEFORE ack.
    claimed = complete_activation(
        session,
        base_url,
        activation_token=activation_token,
        activation_request_id=activation_request_id,
        stable_id=stable_id,
        sleep=sleep,
        monotonic=monotonic,
    )
    staged_state = {
        "portal_base_url": base_url,
        "activation_request_id": activation_request_id,
        "activation_token": activation_token,
        "delivery_nonce": claimed["delivery_nonce"],
        "base_url": claimed["base_url"],
        "api_key": claimed["api_key"],
        "ack_expires_at": claimed.get("ack_expires_at"),
        "replace": replace,
        "staged_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    portal_store.write_staged(staged_state)
    return staged_state


def _run_connect_locked(
    *,
    base_url: str,
    verify: bool,
    replace: bool,
    host_label: Optional[str],
    profile_label: Optional[str],
    out: Callable[[str], None],
    session: Any,
    sleep: Callable[[float], None],
    monotonic: Callable[[], float],
) -> int:
    outcome = begin_activation(
        session,
        base_url,
        replace=replace,
        host_label=host_label,
        profile_label=profile_label,
        out=out,
    )
    kind = outcome["kind"]
    stable_id = outcome["stable_id"]

    if kind == "already_active":
        out("This profile is already connected to the Nadia Agents Portal.")
        _print_binding(outcome["binding"], outcome["profile_label"], out)
        out("To bind a replacement credential, run: nadia portal connect --replace")
        return 0

    if kind == "already_connected_remote":
        out(
            "This profile's identity is already connected to a Nadia Agent in the portal. "
            "To bind a replacement credential, run: nadia portal connect --replace"
        )
        return 0

    if kind == "resume_staged":
        if replace:
            # An interrupted replacement resumes its own pending claim (R70).
            out("Resuming an interrupted replacement…")
        else:
            out("Resuming a previous activation that was interrupted before confirmation…")
        return finish_from_staged(session, outcome["staged"], stable_id, out, resumed=True)

    # kind == "pending": either a resumed approval wait or a fresh start.
    if outcome.get("resumed"):
        out("Resuming the pending activation approval…")
    else:
        _print_activation_prompt(
            outcome["start_result"],
            outcome["profile_label"],
            outcome["host_label"],
            _agent_version(),
            stable_id,
            out,
        )

    # Poll → complete → stage, then ack → promote. This is the fresh activation
    # path (credential staged this run), so it reports "Connected".
    staged_state = drive_pending(
        session,
        base_url,
        verify=verify,
        pending=outcome["pending"],
        stable_id=stable_id,
        replace=replace,
        out=out,
        sleep=sleep,
        monotonic=monotonic,
    )
    return finish_from_staged(session, staged_state, stable_id, out, resumed=False)


def _print_activation_prompt(
    result: Dict[str, Any],
    profile_label: str,
    host_label: str,
    agent_version: str,
    stable_id: str,
    out: Callable[[str], None],
) -> None:
    user_code = str(result.get("user_code") or "")
    verification_url = str(result.get("verification_url") or "")
    expires = str(result.get("approval_expires_at") or "")
    out("")
    out("  Nadia Agents Portal — activation")
    out("  --------------------------------")
    out(f"  Open:         {verification_url}")
    out(f"  Enter code:   {user_code}")
    if expires:
        out(f"  Expires:      {expires}")
    out("")
    out("  Approve this Nadia Agent in the portal:")
    out(f"    Profile:    {profile_label}")
    out(f"    Host:       {host_label}")
    out(f"    Version:    {agent_version}")
    out(f"    Identity:   {portal_store.fingerprint(stable_id)}")
    out("")
    out("  Waiting for operator approval…")


def _print_binding(binding: Dict[str, Any], profile_label: str, out: Callable[[str], None]) -> None:
    out(f"  Profile:  {profile_label}")
    customer = binding.get("customer")
    agent = binding.get("agent")
    if customer:
        out(f"  Customer: {customer}")
    if agent:
        out(f"  Agent:    {agent}")


# ---------------------------------------------------------------------------
# Runtime resolution hook (called from runtime_provider.resolve_runtime_provider)
# ---------------------------------------------------------------------------

def maybe_resolve_portal_runtime(
    *,
    requested_provider: str,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return a runtime dict when the active profile should use the portal.

    Fires for the managed default path (``auto`` request) and for an explicitly
    selected ``nous`` provider — the provider the desktop persists after portal
    activation — as long as no explicit credentials are passed, so advanced
    multi-provider configs still work (FR4). With an active portal credential
    both resolve to the portal-issued ``base_url`` + ``api_key``; with no
    binding at all (never activated) both return ``None`` so ``nous`` falls back
    to its legacy OAuth state and ``auto`` continues down the normal chain. An
    activated profile whose active credential is missing/quarantined fails
    closed rather than silently falling back to the global-root store (R60);
    a staged-but-unACKed credential is never used (R42).
    """
    if explicit_api_key or explicit_base_url:
        return None
    if (requested_provider or "").strip().lower() not in _PORTAL_RUNTIME_PROVIDERS:
        return None

    try:
        credential = portal_store.read_active_credential()
        managed = portal_store.is_portal_managed()
    except Exception:
        return None

    if credential:
        return {
            "provider": _RUNTIME_PROVIDER,
            "api_mode": "chat_completions",
            "base_url": credential["base_url"].rstrip("/"),
            "api_key": credential["api_key"],
            "source": _RUNTIME_SOURCE,
            "requested_provider": requested_provider,
        }

    if managed:
        from nadia_cli.auth import AuthError

        raise AuthError(
            "This profile is connected to the Nadia Agents Portal, but its "
            "credential is missing or was quarantined. Run `nadia portal "
            "connect` to re-activate.",
            code="portal_credential_unavailable",
        )
    return None


# ---------------------------------------------------------------------------
# CLI wiring (invoked from portal_cli via fail-loud content_edits)
# ---------------------------------------------------------------------------

def add_connect_parser(portal_sub: Any) -> None:
    """Register ``connect`` on the existing ``nadia portal`` subparser group."""
    connect_parser = portal_sub.add_parser(
        "connect",
        help="Connect this Local Profile to a Nadia Agent in the NadicodeAI portal",
        description=(
            "Bind the active Local Profile to a Nadia Agent: request activation, "
            "wait for operator approval, claim the managed runtime credential, and "
            "store it under this profile. Use --replace to bind a new credential to "
            "an already-connected profile."
        ),
    )
    connect_parser.add_argument(
        "--replace",
        action="store_true",
        help="Bind a replacement credential to an already-connected profile",
    )
    connect_parser.add_argument(
        "--portal-url",
        dest="portal_url",
        help="Override the portal base URL (default: the shipped NadicodeAI portal)",
    )
    connect_parser.add_argument(
        "--host-label",
        dest="host_label",
        help="Override the sanitized host label shown to the operator",
    )
    connect_parser.add_argument(
        "--profile-label",
        dest="profile_label",
        help="Override the sanitized profile label shown to the operator",
    )


def portal_connect_command(args: Any) -> int:
    """Handler for ``nadia portal connect``. Prints only redaction-safe output."""
    try:
        return run_connect(
            portal_url=getattr(args, "portal_url", None),
            replace=bool(getattr(args, "replace", False)),
            host_label=getattr(args, "host_label", None),
            profile_label=getattr(args, "profile_label", None),
        )
    except PortalActivationError as exc:
        print(str(exc))
        return 1
    except KeyboardInterrupt:
        print()
        print("Activation cancelled.")
        return 1
