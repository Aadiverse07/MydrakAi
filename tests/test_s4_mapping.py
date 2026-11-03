"""S4 mapping tests use the explicitly UNVERIFIED project configuration."""

from pathlib import Path

import pytest

from mydrak.decider.signals import aggregate_stated_confidence
from mydrak.workflow.pipeline_support import load_router_config


CONFIG = Path(__file__).parents[1] / "config" / "thresholds.yaml"
EXPECTED = {"low": 0.25, "medium": 0.5, "high": 0.75}


@pytest.mark.parametrize("band,value", EXPECTED.items())
def test_each_configured_band_maps_to_its_value(band, value):
    _, config = load_router_config(CONFIG)
    assert aggregate_stated_confidence(band, band, config["confidence_bands"]) == value


@pytest.mark.parametrize(
    "first,second,expected",
    [
        ("low", "medium", 0.25),
        ("high", "medium", 0.5),
        ("high", "low", 0.25),
        (0.9, 0.5, 0.5),
        ("high", 0.2, 0.2),
    ],
)
def test_two_sample_aggregation_uses_lower_value(first, second, expected):
    assert aggregate_stated_confidence(first, second, EXPECTED) == expected


@pytest.mark.parametrize(
    "first,second",
    [(None, "low"), ("medium", None), ("unlisted", "low"), ("high", "invalid"), (True, "low")],
)
def test_missing_or_invalid_sample_makes_s4_unavailable(first, second):
    assert aggregate_stated_confidence(first, second, EXPECTED) is None


def test_both_missing_samples_make_s4_unavailable():
    assert aggregate_stated_confidence(None, None, EXPECTED) is None


def test_mapping_values_are_loaded_from_config_not_embedded_in_code(tmp_path):
    config_path = tmp_path / "thresholds.yaml"
    config_path.write_text("confidence_bands:\n  low: 0.1\n  medium: 0.4\n  high: 0.8\n")
    _, config = load_router_config(config_path)
    assert aggregate_stated_confidence("low", "high", config["confidence_bands"]) == 0.1


@pytest.mark.parametrize(
    "yaml_text",
    [
        "confidence_bands:\n  low: 0.1\n  medium: 0.4\n",
        "confidence_bands:\n  low: -0.1\n  medium: 0.4\n  high: 0.8\n",
        "confidence_bands:\n  low: nope\n  medium: 0.4\n  high: 0.8\n",
    ],
)
def test_malformed_mapping_config_raises_clear_error(tmp_path, yaml_text):
    config_path = tmp_path / "bad-thresholds.yaml"
    config_path.write_text(yaml_text)
    with pytest.raises(ValueError, match="confidence band"):
        load_router_config(config_path)
