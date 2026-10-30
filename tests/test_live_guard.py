"""Offline tests for the future live-call gate; no credential or network use."""

from decimal import Decimal
import argparse

import pytest

from mydrak.live.guard import LiveGuardError, add_live_arguments, reserve_live_call
from mydrak.live.retry import call_with_retries
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, DataPolicyError, ProcessingEvidence, ProviderMode,
    require_external_processing_allowed,
)
from mydrak.sam.transport import FakeSamTransport, default_transport, request_live_transport
from mydrak.sam.transport import SamTransportError


GOOD_CONFIG = {
    "model_id": "test-model",
    "endpoint": "https://api.example.test/v1/call",
    "timeout_s": 10,
    "max_input_tokens": 1000,
    "max_output_tokens": 1000,
    "price_input_per_1m": "2.00",
    "price_output_per_1m": "4.00",
}
GOOD_ENV = {"MYDRAK_LIVE": "1", "META_API_KEY": "synthetic-test-key"}


def reserve(tmp_path, **overrides):
    args = {
        "config": GOOD_CONFIG,
        "cli_authorized": True,
        "environ": GOOD_ENV,
        "max_spend_usd": "0.01",
        "ledger_path": tmp_path / ".mydrak-spend-ledger.sqlite3",
    }
    args.update(overrides)
    return reserve_live_call(**args)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"cli_authorized": False}, "--live-authorized"),
        ({"environ": {"META_API_KEY": "synthetic-test-key"}}, "MYDRAK_LIVE"),
        ({"environ": {"MYDRAK_LIVE": "1"}}, "credential"),
        ({"max_spend_usd": None}, "spend-usd"),
        ({"max_spend_usd": 0}, "greater than zero"),
        ({"max_spend_usd": -1}, "invalid"),
        ({"config": GOOD_CONFIG | {"max_input_tokens": None}}, "input tokens"),
        ({"config": GOOD_CONFIG | {"max_output_tokens": None}}, "output tokens"),
        ({"config": GOOD_CONFIG | {"max_tokens": 1000} | {"max_input_tokens": None}}, "input tokens"),
        ({"config": GOOD_CONFIG | {"model_id": "TODO(verify)"}}, "unresolved"),
        ({"config": GOOD_CONFIG | {"endpoint": "http://api.example.test"}}, "endpoint"),
        ({"config": GOOD_CONFIG | {"timeout_s": "TODO(verify)"}}, "timeout"),
        ({"config": GOOD_CONFIG | {"price_input_per_1m": "TODO(verify)"}}, "input price"),
        ({"config": GOOD_CONFIG | {"price_output_per_1m": None}}, "output price"),
    ],
)
def test_guard_rejects_each_missing_or_unresolved_gate(tmp_path, overrides, message):
    with pytest.raises(LiveGuardError, match=message):
        reserve(tmp_path, **overrides)


def test_spend_cap_refuses_before_reserving_excess(tmp_path):
    with pytest.raises(LiveGuardError, match="exceeds spend cap"):
        reserve(tmp_path, max_spend_usd="0.0001")
    assert not (tmp_path / ".mydrak-spend-ledger.sqlite3").exists()


def test_worst_case_reservations_accumulate_in_persistent_ledger(tmp_path):
    first = reserve(tmp_path, max_spend_usd="0.02")
    second = reserve(tmp_path, max_spend_usd="0.02")
    assert first.estimated_usd == Decimal("0.006")
    assert first.cumulative_reserved_usd == Decimal("0.006")
    assert second.cumulative_reserved_usd == Decimal("0.012")
    with pytest.raises(LiveGuardError, match="exceeds spend cap"):
        reserve(tmp_path, max_spend_usd="0.013")


def test_guard_does_not_echo_or_retain_synthetic_credential(tmp_path):
    synthetic_secret = "SYNTHETIC-KEY-9X"
    with pytest.raises(LiveGuardError) as exc:
        reserve(
            tmp_path,
            environ={"MYDRAK_LIVE": "1", "META_API_KEY": synthetic_secret},
            config=GOOD_CONFIG | {"price_input_per_1m": "TODO"},
        )
    assert synthetic_secret not in str(exc.value)
    assert synthetic_secret not in repr(exc.value)


def test_private_photo_is_rejected_for_contributor_variant():
    evidence = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
        user_authorization_confirmed=True,
        privacy_notice_present=True,
    )
    with pytest.raises(DataPolicyError, match="private data"):
        require_external_processing_allowed(DataPolicy.PRIVATE, DataClass.PRIVATE, evidence)


def test_contributor_variant_requires_verified_public_test_provenance():
    incomplete = ProcessingEvidence(
        provider_mode=ProviderMode.CONTRIBUTOR,
        provider_mode_verified=True,
        rights_confirmed=True,
        public_test_provenance_verified=False,
    )
    with pytest.raises(DataPolicyError, match="provenance"):
        require_external_processing_allowed(
            DataPolicy.PUBLIC_TEST, DataClass.PUBLIC_TEST, incomplete
        )


def test_retry_helper_uses_at_most_two_retries_then_safe_fallback():
    attempts = []
    delays = []

    def fails():
        attempts.append(1)
        raise TimeoutError("synthetic timeout")

    result = call_with_retries(
        fails, lambda: "safe-fallback", retry_delays_s=(0.1, 0.2),
        sleep=delays.append,
    )
    assert result == "safe-fallback"
    assert len(attempts) == 3
    assert delays == [0.1, 0.2]


def test_retry_helper_returns_success_without_retry():
    delays = []
    assert call_with_retries(
        lambda: "ok", lambda: "fallback", retry_delays_s=(0.1, 0.2),
        sleep=delays.append,
    ) == "ok"
    assert delays == []


def test_mock_transport_has_no_live_fallback_path():
    assert type(default_transport()) is FakeSamTransport
    with pytest.raises(SamTransportError, match="no live SAM transport"):
        request_live_transport()


def test_cli_live_switches_are_explicit_and_default_off():
    parser = add_live_arguments(argparse.ArgumentParser())
    defaults = parser.parse_args([])
    assert defaults.live_authorized is False
    assert defaults.max_spend_usd is None
    enabled = parser.parse_args(["--live-authorized", "--max-spend-usd", "0.25"])
    assert enabled.live_authorized is True
    assert enabled.max_spend_usd == "0.25"
