"""CLI tests ensure replay is offline and live startup remains fail-closed."""

import socket
from io import StringIO
from decimal import Decimal

import pytest

from mydrak.live.guard import LiveGuardError
from scripts import run_telegram_bot


def test_replay_serves_registered_synthetic_case_with_sockets_blocked(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("replay must not use network sockets")
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    output = []
    result = run_telegram_bot.run(
        ["--replay", "synthetic-ask-01"], environ={}, output=output.append,
    )
    assert result == 0
    assert len(output) == 1
    assert "SYNTHETIC" in output[0] or "synthetic" in output[0]
    assert "provenance=synthetic-offline-demo" in output[0]


def test_allowlist_and_live_modes_fail_closed_without_startup_values():
    errors = StringIO()
    result = run_telegram_bot.run([], environ={}, output=lambda _: None, stderr=errors)
    assert result == 2
    assert "refused" in errors.getvalue()

    errors = StringIO()
    result = run_telegram_bot.run(
        ["--public-access"], environ={"MYDRAK_PUBLIC": "0"},
        output=lambda _: None, stderr=errors,
    )
    assert result == 2
    assert "refused" in errors.getvalue()


def test_public_mode_rejects_missing_limits_before_token_or_network(tmp_path):
    errors = StringIO()
    result = run_telegram_bot.run(
        ["--public-access", "--live-authorized", "--max-spend-usd", "1",
         "--bot-limits", str(tmp_path / "missing.yaml"), "--ledger", str(tmp_path / "ledger")],
        environ={"MYDRAK_PUBLIC": "1", "MYDRAK_LIVE": "1"},
        output=lambda _: None, stderr=errors,
    )
    assert result == 2
    assert "refused" in errors.getvalue()


def test_guard_error_output_never_contains_synthetic_bot_token(tmp_path):
    secret = "synthetic-telegram-token-do-not-output"
    errors = StringIO()
    result = run_telegram_bot.run(
        [], environ={"TELEGRAM_ALLOWED_CHAT_IDS": "1", "TELEGRAM_BOT_TOKEN": secret},
        output=lambda _: None, stderr=errors,
    )
    assert result == 2
    assert secret not in errors.getvalue(), "token leaked from startup error output"


@pytest.mark.parametrize("authorized,environ,cap,ledger", [
    (False, {"MYDRAK_LIVE": "1"}, "1", "exists"),
    (True, {}, "1", "exists"),
    (True, {"MYDRAK_LIVE": "1"}, None, "exists"),
    (True, {"MYDRAK_LIVE": "1"}, "0", "exists"),
    (True, {"MYDRAK_LIVE": "1"}, "1", "missing"),
])
def test_each_required_bot_live_gate_refuses(authorized, environ, cap, ledger, tmp_path):
    path = tmp_path / "ledger.sqlite3"
    if ledger == "exists":
        path.touch()
    with pytest.raises(LiveGuardError):
        run_telegram_bot._require_bot_live_gate(authorized, cap, environ, path)


def test_spend_ledger_read_gate_is_fail_closed_and_read_only(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    path.touch()
    assert run_telegram_bot._ledger_has_headroom(path, Decimal("1"))
    # An existing reservation at the configured cap blocks another case.
    import sqlite3
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE spend_ledger(singleton INTEGER PRIMARY KEY, reserved_usd TEXT NOT NULL)")
        db.execute("INSERT INTO spend_ledger VALUES(1,'1')")
    assert not run_telegram_bot._ledger_has_headroom(path, Decimal("1"))


def test_real_spark_factory_uses_runner_config_with_private_upload_flag(monkeypatch, tmp_path):
    """Regression: the factory must build SparkClient from the runner's config copy
    (which carries allow_private_upload), not the raw models.yaml dict."""
    from io import BytesIO
    from PIL import Image
    from mydrak.live.clients import SparkClient
    from mydrak.privacy.data_policy import (
        DataClass, DataPolicy, ProcessingEvidence, ProviderMode,
    )

    captured = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            captured["factory"] = kwargs["spark_provider_factory"]
            captured["raw_config"] = kwargs["spark_config"]
            self.spark_config = dict(kwargs["spark_config"])
            self.spark_config["allow_private_upload"] = kwargs["allow_private_upload"]
            captured["runner_config"] = self.spark_config

        def run_forever(self):
            return 0

    class Closable:
        def __init__(self, *a, **k):
            pass

        def close(self):
            pass

    monkeypatch.setattr(run_telegram_bot, "TelegramBotRunner", FakeRunner)
    monkeypatch.setattr(run_telegram_bot, "TraceStore", Closable)
    monkeypatch.setattr(run_telegram_bot, "PublicLimitStore", Closable)
    monkeypatch.setattr(run_telegram_bot.TelegramClient, "from_environment",
                        classmethod(lambda cls, environ=None: object()))
    ledger = tmp_path / "ledger.sqlite3"
    ledger.touch()
    environ = {
        "MYDRAK_LIVE": "1", "TELEGRAM_BOT_TOKEN": "fake-token",
        "TELEGRAM_ALLOWED_CHAT_IDS": "1", "META_API_KEY": "fake-key",
    }
    assert run_telegram_bot.run(
        ["--live-authorized", "--max-spend-usd", "5", "--ledger", str(ledger)],
        environ=environ, output=lambda _: None,
    ) == 0
    assert "allow_private_upload" not in captured["raw_config"]
    assert captured["runner_config"]["allow_private_upload"] is True

    buffer = BytesIO()
    Image.new("RGB", (8, 8)).save(buffer, "JPEG")
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.STANDARD, provider_mode_verified=True,
        rights_confirmed=True, user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    client = captured["factory"](
        config=captured["runner_config"], image_bytes=buffer.getvalue(),
        image_provenance="private", data_policy=DataPolicy.PRIVATE,
        data_class=DataClass.PRIVATE, evidence=evidence, use_contributor=False,
        trace_callback=lambda step: None,
    )
    assert type(client) is SparkClient