"""NadicodeAI Portal activation / licensing — pip plugin package.

Extracted from the in-tree overlay (``nadia_cli/portal_activation*.py`` +
``portal_store.py``) into a self-contained entry-point plugin discovered by the
upstream loader via the ``nadia_agent.plugins`` group (rewritten to
``nadia_agent.plugins`` in the shipped product). ``register(ctx)`` wires the
activation ceremony onto the generic loader hooks added upstream:

* ``resolve_runtime_provider`` — route an activated profile's managed inference
  through the portal-issued ``base_url`` + ``api_key`` (fail-closed on a
  missing/quarantined credential; never a global-root fallback).
* ``profile_clone_exclusions`` / ``profile_export_exclusions`` — keep the
  per-profile portal identity + credentials out of clones and export archives.
* ``oauth_provider_dispatch`` — run the portal activation ceremony for the
  desktop gateway's ``nous`` provider instead of the legacy device-code flow.
* nested ``portal connect`` CLI subcommand via
  ``register_cli_command(..., parent="portal")``.

All identifiers are nadia-named in source and renamed to nadia at build time,
so the shipped module runs as ``nadia_portal`` importing ``nadia_cli.*`` /
``nadia_constants``.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from nadia_portal import portal_activation, portal_activation_gateway

# The provider slug the desktop persists after portal activation; its OAuth
# "start" runs the activation ceremony rather than the legacy device-code flow.
_MANAGED_OAUTH_PROVIDER = "nous"
# Per-profile portal state directory (identity + credentials) — never cloned
# or exported. Matches portal_store.PORTAL_DIRNAME.
_PORTAL_STATE_DIR = "portal-activation"


def _resolve_runtime_provider(
    *,
    requested_provider: str,
    explicit_api_key: Optional[str] = None,
    explicit_base_url: Optional[str] = None,
    **_: Any,
) -> Optional[Dict[str, Any]]:
    """resolve_runtime_provider hook: portal credential or None/fail-closed."""
    return portal_activation.maybe_resolve_portal_runtime(
        requested_provider=requested_provider,
        explicit_api_key=explicit_api_key,
        explicit_base_url=explicit_base_url,
    )


def _oauth_provider_dispatch(
    *,
    provider_id: str,
    profile: Optional[str],
    new_session: Any,
    sessions: Any,
    sessions_lock: Any,
    config_profile_scope: Any,
    **_: Any,
) -> Optional[Dict[str, Any]]:
    """oauth_provider_dispatch hook: portal ceremony for the ``nous`` provider."""
    if provider_id != _MANAGED_OAUTH_PROVIDER:
        return None
    return portal_activation_gateway.start_nous_portal_activation(
        profile=profile,
        new_session=new_session,
        sessions=sessions,
        sessions_lock=sessions_lock,
        config_profile_scope=config_profile_scope,
    )


def register(ctx: Any) -> None:
    """Entry point called by the plugin loader with a PluginContext."""
    ctx.register_hook("resolve_runtime_provider", _resolve_runtime_provider)
    ctx.register_hook(
        "profile_clone_exclusions", lambda **_: (_PORTAL_STATE_DIR,)
    )
    ctx.register_hook(
        "profile_export_exclusions", lambda **_: (_PORTAL_STATE_DIR,)
    )
    ctx.register_hook("oauth_provider_dispatch", _oauth_provider_dispatch)
    ctx.register_cli_command(
        "connect",
        help=portal_activation.CONNECT_HELP,
        description=portal_activation.CONNECT_DESCRIPTION,
        setup_fn=portal_activation.add_connect_arguments,
        handler_fn=portal_activation.portal_connect_command,
        parent="portal",
    )
