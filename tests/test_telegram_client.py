"""Offline tests for documented Telegram method parameters only."""

import socket

import pytest

from mydrak.telegram.client import (
    TelegramClient, TelegramClientError, TelegramContractUnverified, TelegramFile,
)


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.downloaded = []
        self.result = []
        self.failure = None

    def call(self, method, parameters, *, timeout_s):
        self.calls.append((method, dict(parameters), timeout_s))
        if self.failure:
            raise self.failure
        if method == "getFile":
            return TelegramFile("synthetic/file.jpg", 5)
        return self.result

    def download(self, file_path, *, max_bytes, timeout_s):
        self.downloaded.append((file_path, max_bytes, timeout_s))
        return b"image"


def test_methods_build_only_documented_parameter_names_and_use_timeout():
    transport = FakeTransport()
    client = TelegramClient("synthetic-token-never-output", transport=transport, timeout_s=7)
    assert client.get_updates(offset=5, limit=10, timeout=25) == []
    client.send_message("chat", "safe")
    client.send_photo("chat", b"image", caption="safe caption")
    assert client.get_file("synthetic-file-id").file_path == "synthetic/file.jpg"
    assert client.download_file("synthetic/file.jpg", max_bytes=100) == b"image"
    assert [call[0] for call in transport.calls] == ["getUpdates", "sendMessage", "sendPhoto", "getFile"]
    assert transport.calls[0][1] == {"limit": 10, "timeout": 25, "offset": 5}
    assert transport.calls[1][1] == {"chat_id": "chat", "text": "safe"}
    assert transport.calls[2][1] == {"chat_id": "chat", "photo": b"image", "caption": "safe caption"}
    assert transport.calls[3][1] == {"file_id": "synthetic-file-id"}
    assert all(call[2] == 7 for call in transport.calls)
    assert transport.downloaded == [("synthetic/file.jpg", 100, 7)]


@pytest.mark.parametrize("kwargs", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"timeout": -1},
    {"allowed_updates": "message"},
])
def test_poll_parameters_are_validated_before_transport(kwargs):
    transport = FakeTransport()
    with pytest.raises(TelegramClientError):
        TelegramClient("synthetic-token", transport=transport).get_updates(**kwargs)
    assert transport.calls == []


def test_send_file_and_message_boundaries_are_validated_before_transport():
    transport = FakeTransport()
    client = TelegramClient("synthetic-token", transport=transport)
    with pytest.raises(TelegramClientError):
        client.send_message("chat", "")
    with pytest.raises(TelegramClientError):
        client.send_photo("chat", b"x" * (10 * 1024 * 1024 + 1))
    with pytest.raises(TelegramClientError):
        client.download_file("path", max_bytes=20 * 1024 * 1024 + 1)
    assert transport.calls == []
    assert transport.downloaded == []


def test_environment_token_is_not_retained_in_repr_or_sanitized_error():
    secret = "synthetic-token-do-not-print"
    client = TelegramClient.from_environment(environ={"TELEGRAM_BOT_TOKEN": secret})
    assert secret not in repr(client)
    with pytest.raises(TelegramContractUnverified) as error:
        client.get_updates()
    assert secret not in str(error.value)
    assert secret not in repr(error.value)


def test_default_transport_refuses_before_any_socket(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("offline Telegram client must not open a socket")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    client = TelegramClient("synthetic-token")
    with pytest.raises(TelegramContractUnverified, match=r"TODO\(verify\)"):
        client.get_updates()


def test_method_and_download_transport_errors_are_sanitized():
    secret = "synthetic-token-in-error"
    transport = FakeTransport()
    transport.failure = RuntimeError(f"request failed at bot{secret}/sendMessage")
    client = TelegramClient(secret, transport=transport)
    with pytest.raises(TelegramClientError) as error:
        client.send_message(1, "safe")
    assert secret not in str(error.value)
    assert secret not in repr(error.value)
