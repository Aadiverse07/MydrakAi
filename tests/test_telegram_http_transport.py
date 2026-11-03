"""Loopback-only contract tests for Telegram HTTP transport and runner polling."""

from contextlib import contextmanager, redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
import time
import traceback
from types import SimpleNamespace

import pytest

from mydrak.bot.adapter import OfflineTelegramAdapter
from mydrak.privacy.data_policy import DataClass, ProcessingEvidence, ProviderMode
from mydrak.replay import run_registered_cached_replay, seed_registered_demo_cache
from mydrak.telegram import http_transport
from mydrak.telegram.client import (
    TelegramApiError, TelegramClient, TelegramResponseError,
    TelegramTimeoutError,
)
from mydrak.telegram.config import AccessMode
from mydrak.telegram.runner import TelegramBotRunner
from mydrak.trace.store import TraceStore

SYNTHETIC_TOKEN = "synthetic-token-for-loopback-tests-only"
SYNTHETIC_IMAGE = b"synthetic-loopback-jpeg-bytes"


class ServerState:
    def __init__(self):
        self.requests = []
        self.get_updates = []
        self.get_updates_count = 0
        self.stop_path: Path | None = None
        self.delay_s = 0.0
        self.malformed = False
        self.error_description = "synthetic failure"
        self.error_method: str | None = None
        self.redirect = False


@contextmanager
def telegram_server(monkeypatch, state: ServerState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            # The request URL contains the synthetic token; never log it.
            return

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            parsed = _parse_request_body(content_type, body)
            state.requests.append((self.path, content_type, parsed, body))
            method = self.path.rsplit("/", 1)[-1]
            if state.delay_s:
                time.sleep(state.delay_s)
            if state.redirect:
                self.send_response(302)
                self.send_header("Location", "/collect")
                self.end_headers()
                return
            if method == state.error_method:
                self._json({"ok": False, "description": state.error_description,
                            "error_code": 400})
                return
            if state.malformed:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"not-json")
                return
            if method == "getUpdates":
                state.get_updates_count += 1
                if state.get_updates:
                    result = state.get_updates.pop(0)
                else:
                    result = []
                if state.stop_path and state.get_updates_count >= 2:
                    state.stop_path.write_text("", encoding="utf-8")
                self._json({"ok": True, "result": result})
            elif method == "getFile":
                self._json({"ok": True, "result": {
                    "file_id": "f1", "file_unique_id": "u1",
                    "file_size": len(SYNTHETIC_IMAGE), "file_path": "photos/test.jpg",
                }})
            elif method in {"sendMessage", "sendPhoto"}:
                self._json({"ok": True, "result": {"message_id": 1}})
            else:
                self._json({"ok": False, "description": state.error_description})

        def do_GET(self):
            state.requests.append((self.path, self.headers.get("Accept", ""), {}, b""))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(SYNTHETIC_IMAGE)

        def _json(self, payload):
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    prefix = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(http_transport, "API_URL_PREFIX", prefix + "/bot")
    monkeypatch.setattr(http_transport, "FILE_URL_PREFIX", prefix + "/file/bot")
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _parse_request_body(content_type, body):
    if content_type.startswith("application/json"):
        return json.loads(body.decode("utf-8"))
    boundary = content_type.split("boundary=", 1)[-1]
    return {"boundary": boundary, "contains_photo_part": b'name="photo"' in body}


def _raw_update(update_id=4, *, text="/start", photos=None):
    message = {"message_id": update_id, "date": 1,
               "chat": {"id": 101, "type": "private", "unknown": "ignored"},
               "from": {"id": 202, "is_bot": False, "first_name": "Synthetic"},
               "unknown_message_field": True}
    if photos is not None:
        message["photo"] = photos
    elif text is not None:
        message["text"] = text
    return {"update_id": update_id, "message": message, "unknown_update_field": 1}


def test_default_http_transport_encodes_json_multipart_and_file_download(monkeypatch):
    state = ServerState()
    with telegram_server(monkeypatch, state):
        client = TelegramClient(SYNTHETIC_TOKEN, timeout_s=2)
        assert client.get_updates(offset=9, limit=4, timeout=7) == []
        client.send_message(101, "hello")
        client.send_photo(101, SYNTHETIC_IMAGE, caption="synthetic")
        file = client.get_file("synthetic-file-id")
        assert file.file_path == "photos/test.jpg"
        assert file.file_size == len(SYNTHETIC_IMAGE)
        assert client.download_file(file.file_path, max_bytes=1024) == SYNTHETIC_IMAGE
    assert [request[0].rsplit("/", 1)[-1] for request in state.requests[:4]] == [
        "getUpdates", "sendMessage", "sendPhoto", "getFile"
    ]
    assert state.requests[0][1].startswith("application/json")
    assert state.requests[0][2] == {"limit": 4, "timeout": 7, "offset": 9}
    assert state.requests[1][2] == {"chat_id": 101, "text": "hello"}
    assert state.requests[2][1].startswith("multipart/form-data; boundary=")
    assert state.requests[2][2]["contains_photo_part"]
    assert SYNTHETIC_IMAGE in state.requests[2][3]
    assert state.requests[4][0].startswith("/file/bot")
    assert state.requests[4][0].endswith("/photos/test.jpg")


def test_response_wrapper_errors_and_token_redaction(monkeypatch):
    state = ServerState()
    state.error_method = "sendMessage"
    state.error_description = f"private detail with {SYNTHETIC_TOKEN}"
    with telegram_server(monkeypatch, state):
        client = TelegramClient(SYNTHETIC_TOKEN)
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with pytest.raises(TelegramApiError) as caught:
                client.send_message(101, "x")
        formatted = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
        rendered = stdout.getvalue() + stderr.getvalue() + repr(client) + repr(client._transport) + formatted
        assert SYNTHETIC_TOKEN not in rendered, "token redaction failed"
        assert SYNTHETIC_TOKEN not in str(caught.value), "token appeared in exception text"
        assert "private detail" not in rendered, "provider error details escaped"


def test_malformed_json_wrapper_and_missing_result_fail_safely(monkeypatch):
    state = ServerState()
    state.malformed = True
    with telegram_server(monkeypatch, state):
        with pytest.raises(TelegramResponseError):
            TelegramClient(SYNTHETIC_TOKEN).get_updates()

    class InvalidTransport:
        def call(self, *_args, **_kwargs):
            return {"ok": True}
        def download(self, *_args, **_kwargs):
            return b""
    with pytest.raises(TelegramResponseError, match="result"):
        TelegramClient(SYNTHETIC_TOKEN, transport=InvalidTransport()).get_updates()


def test_timeout_is_sanitized_and_has_no_token_in_formatted_exception(monkeypatch):
    state = ServerState()
    state.delay_s = 0.15
    with telegram_server(monkeypatch, state):
        client = TelegramClient(SYNTHETIC_TOKEN, timeout_s=0.02)
        with pytest.raises(TelegramTimeoutError) as caught:
            client.get_updates()
        formatted = "".join(traceback.format_exception(caught.type, caught.value, caught.tb))
        assert SYNTHETIC_TOKEN not in formatted, "token appeared in formatted traceback"


def test_redirect_does_not_forward_token_bearing_request(monkeypatch):
    state = ServerState()
    state.redirect = True
    with telegram_server(monkeypatch, state):
        with pytest.raises(TelegramApiError):
            TelegramClient(SYNTHETIC_TOKEN).send_message(101, "safe")
    assert len(state.requests) == 1
    assert state.requests[0][0].endswith("/sendMessage")


def test_polling_retries_transient_http_failures_twice_and_advances_offset(monkeypatch, tmp_path):
    state = ServerState()
    state.get_updates = [[_raw_update(17)], []]
    state.stop_path = tmp_path / "STOP"
    # Return two HTTP failures before the queued successful responses.
    original_do_post = None
    with telegram_server(monkeypatch, state) as server:
        original_do_post = server.RequestHandlerClass.do_POST
        failure_count = {"left": 2}
        def do_post_with_transient_errors(handler):
            if handler.path.endswith("/getUpdates") and failure_count["left"]:
                failure_count["left"] -= 1
                state.requests.append((handler.path, "application/json", {}, b""))
                handler.send_response(500)
                handler.end_headers()
                return
            original_do_post(handler)
        server.RequestHandlerClass.do_POST = do_post_with_transient_errors
        client = TelegramClient(SYNTHETIC_TOKEN, timeout_s=2)
        trace = TraceStore(":memory:")
        runner = TelegramBotRunner(
            client=client, trace_store=trace, adapter=OfflineTelegramAdapter(),
            mode=AccessMode.ALLOWLIST, allowed_chat_ids=frozenset({"101"}),
            stop_path=state.stop_path, sleep=lambda _delay: None,
        )
        assert runner.run_forever() == 0
        updates_requests = [request for request in state.requests if request[0].endswith("/getUpdates")]
        offsets = [request[2].get("offset") for request in updates_requests if request[2]]
        assert len(updates_requests) == 4
        assert offsets == [None, 18]
        trace.close()


def test_duplicate_update_id_is_not_processed_twice(monkeypatch, tmp_path):
    state = ServerState()
    state.get_updates = [[_raw_update(22), _raw_update(22)], []]
    state.stop_path = tmp_path / "STOP"
    with telegram_server(monkeypatch, state):
        trace = TraceStore(":memory:")
        runner = TelegramBotRunner(
            client=TelegramClient(SYNTHETIC_TOKEN), trace_store=trace,
            adapter=OfflineTelegramAdapter(), mode=AccessMode.ALLOWLIST,
            allowed_chat_ids=frozenset({"101"}), stop_path=state.stop_path,
            sleep=lambda _delay: None,
        )
        assert runner.run_forever() == 0
        assert sum(request[0].endswith("/sendMessage") for request in state.requests) == 1
        trace.close()


def test_photo_size_selection_uses_largest_eligible_area(monkeypatch):
    state = ServerState()
    state.get_updates = [[_raw_update(2, text=None, photos=[
        {"file_id": "small", "file_unique_id": "u1", "width": 100, "height": 100, "file_size": 1000},
        {"file_id": "too-large", "file_unique_id": "u2", "width": 900, "height": 900, "file_size": 20 * 1024 * 1024 + 1},
        {"file_id": "unknown-size", "file_unique_id": "u3", "width": 800, "height": 800},
        {"file_id": "largest-eligible", "file_unique_id": "u4", "width": 400, "height": 300, "file_size": 2000},
    ])]]
    with telegram_server(monkeypatch, state):
        updates = TelegramClient(SYNTHETIC_TOKEN).get_updates()
    assert len(updates) == 1
    assert updates[0].photo_file_id == "largest-eligible"
    assert updates[0].photo_size == 2000


def test_malformed_updates_are_skipped_with_safe_acknowledgement(monkeypatch):
    state = ServerState()
    missing_date = _raw_update(32, text="/help")
    missing_date["message"].pop("date")
    state.get_updates = [[{"update_id": 31}, {"update_id": "bad"}, missing_date,
                          _raw_update(33, text="/help")]]
    with telegram_server(monkeypatch, state):
        updates = TelegramClient(SYNTHETIC_TOKEN).get_updates()
    assert updates[0].update_id == 31
    assert updates[1].update_id is None
    assert updates[2].update_id == 32
    assert updates[3].update_id == 33 and updates[3].kind == "command"


def test_runner_exits_safely_when_malformed_update_has_no_acknowledgeable_id(monkeypatch, tmp_path):
    state = ServerState()
    state.get_updates = [[{"message": {"text": "/start"}}]]
    with telegram_server(monkeypatch, state):
        trace = TraceStore(":memory:")
        runner = TelegramBotRunner(
            client=TelegramClient(SYNTHETIC_TOKEN), trace_store=trace,
            adapter=OfflineTelegramAdapter(), mode=AccessMode.ALLOWLIST,
            allowed_chat_ids=frozenset({"101"}), sleep=lambda _delay: None,
        )
        assert runner.run_forever() == 2
        trace.close()


def test_loopback_photo_to_reply_uses_registered_replay_without_provider(monkeypatch, tmp_path):
    state = ServerState()
    state.get_updates = [[
        _raw_update(7, text="/start"),
        _raw_update(8, text=None, photos=[{
            "file_id": "synthetic-photo-id", "file_unique_id": "u1",
            "width": 320, "height": 240, "file_size": len(SYNTHETIC_IMAGE),
        }]),
    ], []]
    state.stop_path = tmp_path / "STOP"
    trace = TraceStore(":memory:")
    seed_registered_demo_cache(trace)
    calls = []
    def replay_workflow(mode, **kwargs):
        calls.append((mode, kwargs["photo_bytes"]))
        cached = run_registered_cached_replay(
            "synthetic-referral-01", trace_store=trace, demo_mode="replay",
        )
        return SimpleNamespace(action="refer", reply=cached.reply, overlay_bytes=None)
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
        rights_confirmed=True, user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    with telegram_server(monkeypatch, state):
        client = TelegramClient(SYNTHETIC_TOKEN, timeout_s=2)
        runner = TelegramBotRunner(
            client=client, trace_store=trace,
            adapter=OfflineTelegramAdapter(
                data_policy_value="private", data_class=DataClass.PRIVATE, evidence=evidence,
            ), mode=AccessMode.ALLOWLIST, allowed_chat_ids=frozenset({"101"}),
            stop_path=state.stop_path, spark_config={"allow_private_upload": True},
            processing_evidence=evidence, workflow=replay_workflow,
            spark_provider_factory=lambda **_kwargs: pytest.fail("replay must not call a provider"),
            sleep=lambda _delay: None,
        )
        assert runner.run_forever() == 0
    assert calls == [("spark_only", SYNTHETIC_IMAGE)]
    sent_text = [request[2].get("text") for request in state.requests
                 if request[0].endswith("/sendMessage")]
    assert len(sent_text) == 2 and "synthetic demo only" in sent_text[1]
    assert all(request[0].startswith(("/bot", "/file/bot")) for request in state.requests), "request used an unexpected local route"
    trace.close()
