"""Unit tests for the fake Telegram server fixture (M5.1).

These tests cover the contracts that argo's gateway (via PTB) and the
M5.3 smoke harness will rely on. Every assertion runs against the
in-process server bound to 127.0.0.1; no real Telegram API contact
anywhere.

Spec/standards: ``.shepherd/install-update/standards.md`` § "Telegram
smoke tests use fake bots. Never the real Telegram API."
"""

from __future__ import annotations

import concurrent.futures
import json
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

import pytest

# argo's pyproject pins requests==2.33.0 in [project].dependencies, so
# using it here is consistent with the runtime; fall back to urllib if
# the test runs in a stripped-down environment.
try:
    import requests  # type: ignore[import-untyped]

    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover — argo always has requests
    _HAS_REQUESTS = False

from .fake_telegram import FakeTelegramServer

TOKEN = "TESTTOKEN:fake_argo_bot"


# ---------------------------------------------------------------------------
# HTTP helpers — single surface so the test bodies stay focused on behaviour.
# ---------------------------------------------------------------------------


def _post_json(url: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if _HAS_REQUESTS:
        resp = requests.post(url, json=payload or {}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310 — localhost only
        return json.loads(resp.read().decode("utf-8"))


def _get_json(url: str) -> Dict[str, Any]:
    if _HAS_REQUESTS:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json()
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 — localhost only
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def server():
    """A started fake server, torn down at end of test."""
    s = FakeTelegramServer()
    s.start()
    try:
        yield s
    finally:
        s.stop()


# ---------------------------------------------------------------------------
# Test cases (one per spec bullet in the M5.1 brief).
# ---------------------------------------------------------------------------


def test_get_me_returns_configured_identity():
    """getMe surfaces the bot id/username configured at construction time."""
    s = FakeTelegramServer(bot_username="custom_bot", bot_id=777)
    s.start()
    try:
        response = _post_json(f"{s.base_url}/bot{TOKEN}/getMe")
        assert response["ok"] is True
        result = response["result"]
        assert result["id"] == 777
        assert result["username"] == "custom_bot"
        assert result["is_bot"] is True
        assert result["first_name"]  # non-empty
    finally:
        s.stop()


def test_get_updates_returns_injected_messages_and_offset_drops_them(server):
    """inject_message → getUpdates returns it; calling again with offset
    past that id drops it from the queue and returns []."""
    update_id = server.inject_message("hello")
    assert isinstance(update_id, int) and update_id >= 1

    first = _post_json(f"{server.base_url}/bot{TOKEN}/getUpdates")
    assert first["ok"] is True
    assert len(first["result"]) == 1
    update = first["result"][0]
    assert update["update_id"] == update_id
    assert update["message"]["text"] == "hello"
    assert update["message"]["chat"]["id"] == 12345
    assert update["message"]["from"]["username"] == "testuser"

    # Confirm-and-drop: PTB sends offset=last_seen+1 to acknowledge.
    second = _post_json(
        f"{server.base_url}/bot{TOKEN}/getUpdates",
        {"offset": update_id + 1},
    )
    assert second["ok"] is True
    assert second["result"] == []


def test_send_message_records_chat_and_text_and_returns_envelope(server):
    """sendMessage returns ok=True with an int message_id and records the
    (chat_id, text) tuple in sent_messages."""
    response = _post_json(
        f"{server.base_url}/bot{TOKEN}/sendMessage",
        {"chat_id": 1, "text": "reply"},
    )
    assert response["ok"] is True
    result = response["result"]
    assert isinstance(result["message_id"], int)
    assert result["chat"]["id"] == 1
    assert result["text"] == "reply"

    assert server.sent_messages == [(1, "reply")]


def test_concurrent_send_messages_both_succeed(server):
    """Two parallel sendMessage requests both return ok=True and both are
    recorded — exercises the threading.Lock around sent_messages."""
    url = f"{server.base_url}/bot{TOKEN}/sendMessage"
    payloads = [
        {"chat_id": 100, "text": "alpha"},
        {"chat_id": 200, "text": "beta"},
    ]
    # Use a barrier so both requests are mid-flight simultaneously rather
    # than serialised by the thread-pool warmup.
    barrier = __import__("threading").Barrier(2)

    def send(payload: Dict[str, Any]) -> Dict[str, Any]:
        barrier.wait(timeout=5)
        return _post_json(url, payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, payloads))

    assert all(r["ok"] is True for r in results)
    # Order is non-deterministic under concurrency; assert as a set.
    assert set(server.sent_messages) == {(100, "alpha"), (200, "beta")}
    # And both message_ids are distinct integers.
    ids = [r["result"]["message_id"] for r in results]
    assert len(set(ids)) == 2
    assert all(isinstance(i, int) for i in ids)


def test_start_stop_lifecycle_refuses_connection_after_stop():
    """After stop(), the port is no longer accepting connections."""
    s = FakeTelegramServer()
    s.start()
    port = s.port
    # Sanity: it works while running.
    response = _post_json(f"{s.base_url}/bot{TOKEN}/getMe")
    assert response["ok"] is True
    s.stop()

    # Connection to the released port should now be refused. We probe
    # with a raw socket so we get ConnectionRefusedError fast — going
    # via requests/urllib would surface the same condition but wrapped
    # in their own error types, which is noisier.
    with pytest.raises((ConnectionRefusedError, OSError)):
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


# ---------------------------------------------------------------------------
# Defensive guard tests — small additions that protect the contract.
# ---------------------------------------------------------------------------


def test_rejects_non_localhost_bind():
    """Per standards, the fake must never be reachable off-box."""
    with pytest.raises(ValueError):
        FakeTelegramServer(host="0.0.0.0")  # noqa: S104 — intentional bad input
