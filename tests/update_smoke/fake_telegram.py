"""Fake Telegram Bot API server for the update smoke harness (M5.1).

Implements the minimum surface nadia's gateway exercises during the update
flow: ``getMe``, ``getUpdates``, ``sendMessage``. Binds to 127.0.0.1 on an
OS-assigned free port; never contacts api.telegram.org.

Spec: ``.shepherd/install-update/spec.md`` IU-NFR-2, IU-AC-6, Testing
Strategy ("end-to-end Telegram via a fake bot (no real Telegram API in
CI)"). Standards: ``.shepherd/install-update/standards.md`` § "Telegram
smoke tests use fake bots. Never the real Telegram API."

How the M5.3 smoke harness will wire nadia to this fake
-------------------------------------------------------

Nadia's gateway is python-telegram-bot (PTB) based. The Telegram platform
plugin honours ``config.extra.base_url`` and, when present, builds the
PTB ``Application`` with ``builder.base_url(custom_base_url)`` (see
``upstream/gateway/platforms/telegram.py`` around line 1481). PTB then
appends ``/bot<TOKEN>/<method>`` to that base URL, which is exactly the
shape this server serves. M5.3 will therefore configure the gateway
under test via the platform's ``extra.base_url`` config (and
``extra.base_file_url`` if file ops are added later), e.g.::

    platforms:
      telegram:
        token: "FAKE:fake_nadia_bot"
        extra:
          base_url: "http://127.0.0.1:<port>/bot"

Note the trailing ``/bot`` — PTB's ``base_url`` is the prefix to which
the library appends ``<TOKEN>/<method>``, so ``base_url`` ends in
``/bot`` (PTB default is ``https://api.telegram.org/bot``). The fake
serves paths under ``/bot<TOKEN>/<method>`` to mirror that contract.

Known limitation: the gateway's ``telegram_network.py`` (``_TELEGRAM_API_HOST
= "api.telegram.org"`` and the DoH fallback transport) is only activated
on direct HTTPS requests against the real host. Once ``extra.base_url``
points at the fake's plain-HTTP URL, the fallback transport is bypassed
(see PTB's own ``HTTPXRequest`` selection logic) and traffic goes
straight to 127.0.0.1. No env-var override is needed and none has been
patched into nadia by this task — that decision belongs to M5.3.

The fixture is stdlib-only (``http.server`` + ``threading``) so it adds
no runtime deps, in line with IU-NFR-7.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

__all__ = ["FakeTelegramServer"]

logger = logging.getLogger(__name__)


def _pick_free_port() -> int:
    """Bind to 127.0.0.1:0 to ask the OS for a free port, then release it.

    There is a small TOCTOU window between releasing and re-binding inside
    ``ThreadingHTTPServer`` but in practice the OS does not immediately
    recycle the port and this is the standard CPython recipe.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeTelegramServer:
    """A localhost HTTP server speaking just-enough Telegram Bot API.

    Usage::

        server = FakeTelegramServer()
        server.start()
        try:
            server.inject_message("/update")
            # ... point nadia's gateway at server.base_url ...
        finally:
            server.stop()

    All state mutation is guarded by an internal ``threading.Lock`` so
    the smoke harness can both inject incoming updates and inspect
    outbound ``sent_messages`` while the gateway is concurrently
    polling.
    """

    def __init__(
        self,
        *,
        bot_username: str = "fake_nadia_bot",
        bot_id: int = 42,
        bot_first_name: str = "Fake Nadia",
        host: str = "127.0.0.1",
        port: Optional[int] = None,
    ) -> None:
        if host not in ("127.0.0.1", "localhost"):
            # Hard refusal: a fake Telegram server must never be reachable
            # off-box. Spec IU-FR-13/standards "fake bots, never the real
            # API" implies "never accessible to anything but the test
            # process".
            raise ValueError(
                f"FakeTelegramServer must bind to localhost; got host={host!r}"
            )
        self._bot_username = bot_username
        self._bot_id = bot_id
        self._bot_first_name = bot_first_name
        self._host = host
        self._port = port if port is not None else _pick_free_port()

        # Shared state — every access takes self._lock.
        self._lock = threading.Lock()
        self._updates: List[Dict[str, Any]] = []
        self._next_update_id = 1
        self._sent_messages: List[Tuple[int, str]] = []
        self._next_message_id = 1
        self._next_user_message_id = 1000

        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """Root URL of the fake server, e.g. ``http://127.0.0.1:54321``.

        Append ``/bot<TOKEN>/<method>`` to form a request URL. PTB's
        ``Application.builder().base_url(...)`` argument should be
        ``f"{server.base_url}/bot"`` (note the trailing ``/bot``).
        """
        return f"http://{self._host}:{self._port}"

    @property
    def port(self) -> int:
        return self._port

    @property
    def bot_username(self) -> str:
        return self._bot_username

    @property
    def bot_id(self) -> int:
        return self._bot_id

    @property
    def sent_messages(self) -> List[Tuple[int, str]]:
        """A copy of the recorded ``(chat_id, text)`` tuples.

        Returns a copy so iteration is safe while the gateway is still
        sending.
        """
        with self._lock:
            return list(self._sent_messages)

    def inject_message(
        self,
        text: str,
        *,
        chat_id: int = 12345,
        user_id: int = 67890,
        username: str = "testuser",
        first_name: str = "Test",
    ) -> int:
        """Queue an incoming update for the next ``getUpdates`` poll.

        Returns the assigned ``update_id`` so tests can assert against
        ``getUpdates(offset=update_id+1)``.
        """
        with self._lock:
            update_id = self._next_update_id
            self._next_update_id += 1
            message_id = self._next_user_message_id
            self._next_user_message_id += 1
            update = {
                "update_id": update_id,
                "message": {
                    "message_id": message_id,
                    "from": {
                        "id": user_id,
                        "is_bot": False,
                        "first_name": first_name,
                        "username": username,
                    },
                    "chat": {
                        "id": chat_id,
                        "type": "private",
                        "first_name": first_name,
                        "username": username,
                    },
                    "date": int(time.time()),
                    "text": text,
                },
            }
            self._updates.append(update)
            return update_id

    def start(self) -> None:
        """Bind the port and spawn the serving thread. Idempotent — calling
        start twice on the same instance raises ``RuntimeError``."""
        if self._httpd is not None:
            raise RuntimeError("FakeTelegramServer.start() called twice")
        handler_cls = _make_handler(self)
        self._httpd = ThreadingHTTPServer((self._host, self._port), handler_cls)
        # Refresh port in case caller passed 0 explicitly.
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name=f"FakeTelegramServer-{self._port}",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Shut down the server and join the serving thread.

        Safe to call even if ``start()`` was never called or already
        stopped; in that case it is a no-op.
        """
        httpd = self._httpd
        thread = self._thread
        self._httpd = None
        self._thread = None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        if thread is not None:
            thread.join(timeout=timeout)

    # ------------------------------------------------------------------
    # Internals — invoked by the HTTP handler
    # ------------------------------------------------------------------

    def _handle_get_me(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "result": {
                "id": self._bot_id,
                "is_bot": True,
                "username": self._bot_username,
                "first_name": self._bot_first_name,
                "can_join_groups": True,
                "can_read_all_group_messages": False,
                "supports_inline_queries": False,
            },
        }

    def _handle_get_updates(self, params: Dict[str, List[str]]) -> Dict[str, Any]:
        offset_raw = params.get("offset", [None])[0] if params else None
        offset: Optional[int]
        try:
            offset = int(offset_raw) if offset_raw is not None else None
        except (TypeError, ValueError):
            offset = None
        with self._lock:
            if offset is None:
                result = list(self._updates)
            else:
                # Telegram semantics: returning updates with id >= offset
                # also confirms (drops) any update with id < offset.
                self._updates = [u for u in self._updates if u["update_id"] >= offset]
                result = list(self._updates)
        return {"ok": True, "result": result}

    def _handle_send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        chat_id_raw = payload.get("chat_id")
        text = payload.get("text", "")
        try:
            chat_id = int(chat_id_raw)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: chat_id is required and must be an integer",
            }
        with self._lock:
            message_id = self._next_message_id
            self._next_message_id += 1
            self._sent_messages.append((chat_id, str(text)))
        return {
            "ok": True,
            "result": {
                "message_id": message_id,
                "from": {
                    "id": self._bot_id,
                    "is_bot": True,
                    "username": self._bot_username,
                    "first_name": self._bot_first_name,
                },
                "chat": {"id": chat_id, "type": "private"},
                "date": int(time.time()),
                "text": str(text),
            },
        }


def _parse_path(path: str) -> Tuple[Optional[str], Optional[str], Dict[str, List[str]]]:
    """Split ``/bot<TOKEN>/<method>?<query>`` into ``(token, method, query)``.

    Returns ``(None, None, {})`` if the path does not match the
    Telegram Bot API shape.
    """
    parsed = urlparse(path)
    raw = parsed.path.lstrip("/")
    # PTB and curl-style clients both produce /bot<TOKEN>/<method>.
    if not raw.startswith("bot"):
        return None, None, {}
    rest = raw[len("bot"):]
    if "/" not in rest:
        return None, None, {}
    token, method = rest.split("/", 1)
    if not token or not method:
        return None, None, {}
    return token, method, parse_qs(parsed.query)


def _make_handler(server_instance: FakeTelegramServer):
    """Build a BaseHTTPRequestHandler subclass bound to ``server_instance``.

    BaseHTTPRequestHandler is instantiated per request by
    ``ThreadingHTTPServer``, so we close over the FakeTelegramServer
    instance via this factory rather than via globals.
    """

    class Handler(BaseHTTPRequestHandler):
        # Quiet by default — tests don't want log spam, and the smoke
        # harness logs at the gateway level.
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.debug("fake-telegram %s - %s", self.address_string(), format % args)

        # Telegram Bot API accepts both GET and POST for most methods.
        # We normalise both paths through ``_dispatch``.
        def do_GET(self) -> None:  # noqa: N802 — required by BaseHTTPRequestHandler
            self._dispatch(body=b"")

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
            self._dispatch(body=body)

        # ------------------------------------------------------------------

        def _dispatch(self, *, body: bytes) -> None:
            token, method, query = _parse_path(self.path)
            if token is None or method is None:
                self._send_json(
                    HTTPStatus.NOT_FOUND,
                    {"ok": False, "error_code": 404, "description": "Not Found"},
                )
                return

            if method == "getMe":
                self._send_json(HTTPStatus.OK, server_instance._handle_get_me())
                return

            if method == "getUpdates":
                # PTB sends getUpdates as POST with JSON body; honour offset
                # from query OR from JSON body.
                params = dict(query)
                if body:
                    parsed_body = _parse_body(body, self.headers.get("Content-Type", ""))
                    for key, value in parsed_body.items():
                        params[key] = [str(value)]
                self._send_json(
                    HTTPStatus.OK,
                    server_instance._handle_get_updates(params),
                )
                return

            if method == "sendMessage":
                payload = _parse_body(body, self.headers.get("Content-Type", ""))
                self._send_json(
                    HTTPStatus.OK,
                    server_instance._handle_send_message(payload),
                )
                return

            # Unknown method — Telegram's real server returns 404 with an
            # ok=False envelope. Match that so PTB's error path mirrors
            # production behaviour.
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {
                    "ok": False,
                    "error_code": 404,
                    "description": f"Not Found: method {method} not implemented by fake",
                },
            )

        def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _parse_body(body: bytes, content_type: str) -> Dict[str, Any]:
    """Parse a request body as JSON or form-encoded, returning a flat dict.

    Falls back to ``{}`` on any parse error; mirrors Telegram's lenient
    handling.
    """
    if not body:
        return {}
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    if ct == "application/json" or body.lstrip().startswith(b"{"):
        try:
            data = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
    # Default to form-encoded.
    try:
        parsed = parse_qs(body.decode("utf-8"))
    except UnicodeDecodeError:
        return {}
    # parse_qs returns lists; collapse single-value lists for ergonomics.
    return {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}


if __name__ == "__main__":
    # Smoke run: start, print URL, wait for Ctrl-C.
    server = FakeTelegramServer()
    server.start()
    print(server.base_url)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop()
