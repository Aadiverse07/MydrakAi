"""Safe machine-readable diagnostics shared by explicit smoke CLIs."""

_SAFE_IDS = frozenset({
    "MYDRAK_LIVE", "cli_authorization", "max_spend_usd", "credential_missing",
    "provider_config", "provider_section", "config_read", "config_section",
    "config_shape", "config_unresolved", "provider_request", "model_id",
    "endpoint", "timeout_s", "max_input_tokens_estimate", "max_tokens",
    "price_input_per_1m", "price_output_per_1m", "spend_cap", "spend_ledger",
    "credential_env_var", "diagnosis_max_tokens", "glimmer_host", "glimmer_profile",
    "audio_bounds", "language_or_keyword_bias", "mode", "price_per_1k_minutes",
    "request_path", "target_sample_rate", "voice", "campaign_guard", "image",
    "image_dimensions", "max_response_bytes", "price_per_1k_images", "prompt",
    "sam_campaign", "scope",
})
_CONFIG_FIELDS = frozenset({
    "model_id", "model_id_contributor", "endpoint", "timeout_s", "max_tokens",
    "max_input_tokens_estimate", "price_input_per_1m", "price_output_per_1m",
    "diagnosis_max_tokens", "price_per_1k_minutes", "price_per_1k_images",
})


def safe_condition_id(value: object) -> str:
    """Return a bounded identifier only; never echo arbitrary error content."""
    if isinstance(value, str) and (
        value in _SAFE_IDS
        or any(value == f"{prefix}_{field}" for prefix in ("missing", "unresolved")
               for field in _CONFIG_FIELDS)
    ):
        return value
    return "unknown"
