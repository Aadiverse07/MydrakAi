"""Offline tests for the future live-call gate; no credential or network use."""

from decimal import Decimal
import argparse
from pathlib import Path

import pytest
import yaml

from mydrak.live.guard import (
    LiveGuardError, add_live_arguments, load_live_provider_config,
    reserve_live_call, reserve_live_estimated_cost,
)
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
    "max_input_tokens_estimate": 1000,
    "max_tokens": 1000,
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
        ({"config": GOOD_CONFIG | {"max_input_tokens_estimate": None}}, "input tokens estimate"),
        ({"config": GOOD_CONFIG | {"max_tokens": None}}, "output tokens"),
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


def test_fixed_cost_reservation_shares_guards_and_accumulates(tmp_path):
    config = {"model_id": "sam-3.1", "endpoint": "https://api.meta.ai/v1", "timeout_s": 30}
    arguments = {
        "config": config, "estimated_usd": "0.0025", "cli_authorized": True,
        "environ": GOOD_ENV, "max_spend_usd": "0.01",
        "ledger_path": tmp_path / "ledger.sqlite3",
    }
    first = reserve_live_estimated_cost(**arguments)
    second = reserve_live_estimated_cost(**arguments)
    assert first.estimated_usd == Decimal("0.0025")
    assert first.cumulative_reserved_usd == Decimal("0.0025")
    assert second.cumulative_reserved_usd == Decimal("0.0050")


@pytest.mark.parametrize("override,condition", [
    ({"cli_authorized": False}, "cli_authorization"),
    ({"environ": {"META_API_KEY": "synthetic-test-key"}}, "MYDRAK_LIVE"),
    ({"environ": {"MYDRAK_LIVE": "1"}}, "credential_missing"),
    ({"max_spend_usd": None}, "max_spend_usd"),
    ({"estimated_usd": None}, "cost_unknown"),
])
def test_fixed_cost_reservation_refuses_missing_live_gates(tmp_path, override, condition):
    arguments = {
        "config": {"model_id": "voice", "endpoint": "https://api.meta.ai/v1", "timeout_s": 30},
        "estimated_usd": "0.001", "cli_authorized": True, "environ": GOOD_ENV,
        "max_spend_usd": "0.01", "ledger_path": tmp_path / "ledger.sqlite3",
    }
    arguments.update(override)
    with pytest.raises(LiveGuardError) as exc:
        reserve_live_estimated_cost(**arguments)
    assert exc.value.condition == condition
    assert not (tmp_path / "ledger.sqlite3").exists()


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


def test_config_loader_accepts_numeric_prices_without_claiming_verification(tmp_path):
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        "tier1:\n  model_id: example\n  endpoint: https://example.test/v1\n"
        "  timeout_s: 3\n  max_tokens: 12\n  max_input_tokens_estimate: 99\n"
        "  price_input_per_1m: 0.35\n  price_output_per_1m: 1.5\n"
        "glimmer_host:\n  choice: together\n",
        encoding="utf-8",
    )
    loaded = load_live_provider_config(config_path, "tier1")
    assert loaded["price_input_per_1m"] == 0.35
    assert loaded["price_output_per_1m"] == 1.5


def test_spark_diagnosis_token_cap_is_optional_but_must_be_bounded(tmp_path):
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        "tier2:\n  model_id: spark\n  model_id_contributor: spark-contributor\n"
        "  endpoint: https://example.test/v1\n  timeout_s: 3\n  max_tokens: 2048\n"
        "  diagnosis_max_tokens: 512\n  max_input_tokens_estimate: 99\n"
        "  price_input_per_1m: 0.35\n  price_output_per_1m: 1.5\n",
        encoding="utf-8",
    )
    loaded = load_live_provider_config(config_path, "tier2")
    assert loaded["diagnosis_max_tokens"] == 512
    config_path.write_text(config_path.read_text().replace("diagnosis_max_tokens: 512", "diagnosis_max_tokens: 4096"))
    with pytest.raises(LiveGuardError, match="exceeds max_tokens"):
        load_live_provider_config(config_path, "tier2")


def test_config_loader_requires_input_token_estimate(tmp_path):
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        "tier1:\n  model_id: example\n  endpoint: https://example.test/v1\n"
        "  timeout_s: 3\n  max_tokens: 12\n"
        "  price_input_per_1m: 0.35\n  price_output_per_1m: 1.5\n"
        "glimmer_host:\n  choice: together\n",
        encoding="utf-8",
    )
    with pytest.raises(LiveGuardError, match="max_input_tokens_estimate is missing"):
        load_live_provider_config(config_path, "tier1")


def test_config_loader_rejects_todo_placeholder_with_clear_error(tmp_path):
    config_path = tmp_path / "models.yaml"
    config_path.write_text(
        "tier1:\n  model_id: TODO(verify)\n  endpoint: https://example.test/v1\n"
        "  timeout_s: 3\n  max_tokens: 12\n"
        "  price_input_per_1m: 0.35\n  price_output_per_1m: 1.5\n"
        "glimmer_host:\n  choice: together\n",
        encoding="utf-8",
    )
    with pytest.raises(LiveGuardError, match="unresolved TODO"):
        load_live_provider_config(config_path, "tier1")


def test_current_config_estimate_bounds_worst_case_cost(tmp_path):
    repository_config = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
    tier1 = load_live_provider_config(repository_config, "tier1")
    assert tier1["max_tokens"] > 0
    reservation = reserve(tmp_path, config=tier1)
    expected = (
        Decimal(tier1["max_input_tokens_estimate"]) * Decimal(str(tier1["price_input_per_1m"]))
        + Decimal(tier1["max_tokens"]) * Decimal(str(tier1["price_output_per_1m"]))
    ) / Decimal(1_000_000)
    assert reservation.estimated_usd == expected


def test_glimmer_host_profiles_select_nvidia_by_default_and_keep_together_available(tmp_path):
    repository_config = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
    nvidia = load_live_provider_config(repository_config, "tier1")
    assert nvidia["host"] == "nvidia"
    assert nvidia["endpoint"] == "https://integrate.api.nvidia.com/v1"
    assert nvidia["model_id"] == "meta/muse-glimmer-30b"
    assert nvidia["credential_env_var"] == "NVIDIA_API_KEY"
    assert (nvidia["price_input_per_1m"], nvidia["price_output_per_1m"]) == (0.35, 1.50)
    assert nvidia["timeout_s"] == 30 and nvidia["max_tokens"] == 512
    assert nvidia["max_input_tokens_estimate"] == 4000 and nvidia["samples_per_case"] == 2

    document = yaml.safe_load(repository_config.read_text(encoding="utf-8"))
    document["glimmer_host"]["choice"] = "together"
    together_path = tmp_path / "models.yaml"
    together_path.write_text(yaml.safe_dump(document), encoding="utf-8")
    together = load_live_provider_config(together_path, "tier1")
    assert together["host"] == "together"
    assert together["endpoint"] == "https://api.together.xyz/v1"
    assert together["model_id"] == "meta-models/Muse-Glimmer-30B"
    assert together["credential_env_var"] == "TOGETHER_API_KEY"
    assert (together["price_input_per_1m"], together["price_output_per_1m"]) == (0.35, 1.50)


@pytest.mark.parametrize("missing_gate", [
    "cli", "live_env", "cap", "ledger", "unknown_price",
])
def test_selected_nvidia_profile_keeps_every_existing_guard(tmp_path, missing_gate):
    repository_config = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
    config = load_live_provider_config(repository_config, "tier1")
    kwargs = {
        "config": config,
        "cli_authorized": True,
        "environ": {"MYDRAK_LIVE": "1", "NVIDIA_API_KEY": "SYNTHETIC-NVIDIA-KEY"},
        "max_spend_usd": "1",
        "ledger_path": tmp_path / "nvidia-ledger.sqlite",
        "credential_env_var": config["credential_env_var"],
    }
    if missing_gate == "cli":
        kwargs["cli_authorized"] = False
        expected = "cli_authorization"
    elif missing_gate == "live_env":
        kwargs["environ"] = {"NVIDIA_API_KEY": "SYNTHETIC-NVIDIA-KEY"}
        expected = "MYDRAK_LIVE"
    elif missing_gate == "cap":
        kwargs["max_spend_usd"] = None
        expected = "max_spend_usd"
    elif missing_gate == "ledger":
        kwargs["ledger_path"] = tmp_path / "missing-dir" / "ledger.sqlite"
        expected = "spend_ledger"
    else:
        kwargs["config"] = config | {"price_input_per_1m": None}
        expected = "price_input_per_1m"
    with pytest.raises(LiveGuardError) as caught:
        reserve_live_call(**kwargs)
    assert caught.value.condition == expected


def test_missing_input_token_estimate_refuses_before_ledger_write(tmp_path):
    with pytest.raises(LiveGuardError, match="maximum input tokens estimate"):
        reserve(tmp_path, config=GOOD_CONFIG | {"max_input_tokens_estimate": None})
    assert not (tmp_path / ".mydrak-spend-ledger.sqlite3").exists()


@pytest.mark.parametrize("provider", ["tier1", "tier2", "sam", "voice"])
def test_populated_provider_sections_load_but_remain_unverified(provider):
    repository_config = Path(__file__).resolve().parents[1] / "config" / "models.yaml"
    section = load_live_provider_config(repository_config, provider)
    assert section["model_id"]
    assert section["endpoint"].startswith("https://")
