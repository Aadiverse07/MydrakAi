"""Config loading: YAML files parse and threshold weights sum to 1."""

import pytest

from mydrak.util.config import load_yaml

from conftest import REPO_ROOT


def test_thresholds_load_and_weights_sum_to_one():
    cfg = load_yaml(REPO_ROOT / "config" / "thresholds.yaml")
    w = cfg["weights"]
    total = w["s1_agreement"] + w["s2_kb_match"] + w["s3_quality"] + w["s4_stated_confidence"]
    assert total == pytest.approx(1.0)


def test_severity_config_loads():
    cfg = load_yaml(REPO_ROOT / "config" / "severity.yaml")
    assert cfg["bands"]["low_max"] < cfg["bands"]["moderate_max"]
    assert cfg["recovery_margin_pp"] > 0


def test_models_config_is_explicitly_unverified():
    cfg = load_yaml(REPO_ROOT / "config" / "models.yaml")
    text = (REPO_ROOT / "config" / "models.yaml").read_text(encoding="utf-8")
    assert text.startswith("# UNVERIFIED until a smoke test passes.")
    assert cfg["tier1"]["model_id"]
    assert cfg["tier2"]["model_id"]
    assert isinstance(cfg["tier1"]["price_input_per_1m"], (int, float))
    assert isinstance(cfg["tier2"]["price_output_per_1m"], (int, float))


def test_load_yaml_rejects_non_mapping(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_yaml(bad)


def test_env_example_defaults_data_policy_to_private():
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DATA_POLICY=private" in env_example
    assert "DATA_POLICY=public_test" not in env_example
    assert "TOGETHER_API_KEY=" in env_example
