"""Guarded Spark client specialization for documented Chat Completions."""

from __future__ import annotations

import base64
from collections.abc import Callable, Collection, Mapping
from dataclasses import asdict
import json
import time
from typing import Any

from mydrak.live.clients import _BaseClient
from mydrak.live.guard import LiveConfigError
from mydrak.live.http import JsonTransport, UrllibJsonTransport
from mydrak.privacy.data_policy import (
    DataClass, DataPolicy, DataPolicyError, ProcessingEvidence, ProviderMode,
    require_external_processing_allowed,
)
from mydrak.trace.store import TraceStep
from mydrak.vision.diagnosis import DiagnosisOutput, validate_diagnosis_json


class SparkClient(_BaseClient):
    """Meta Spark Chat Completions client with optional JPEG image input.

    The multimodal message shape mirrors the user-supplied reference in
    ``docs/providers/meta_spark.md``; it is not independent API verification.
    """

    def __init__(
        self, config: Mapping[str, Any], *,
        context: DiagnosisOutput | tuple[DiagnosisOutput, ...] | None,
        data_policy: DataPolicy, data_class: DataClass,
        evidence: ProcessingEvidence, use_contributor: bool = False,
        image_bytes: bytes | None = None, image_provenance: str | None = None,
        cli_authorized: bool, max_spend_usd: Any, ledger_path: str,
        environ: Mapping[str, str] | None = None,
        transport: JsonTransport | None = None,
        trace_callback: Callable[[TraceStep], None] | None = None,
        retry_delays_s: tuple[float, ...] = (0.1, 0.2),
        sleep: Callable[[float], None] = time.sleep,
        supported_crops: Collection[str] = (), disease_ids: Collection[str] = (),
        confidence_bands: Collection[str] = ("low", "medium", "high"),
    ) -> None:
        values = dict(config)
        if not isinstance(evidence, ProcessingEvidence):
            raise DataPolicyError("Spark processing evidence is unavailable")
        if image_bytes is not None:
            if not isinstance(image_bytes, bytes) or not image_bytes.startswith(b"\xff\xd8\xff"):
                raise DataPolicyError("Spark image input must be preprocessed JPEG bytes")
            expected_provenance = "public-test" if data_class is DataClass.PUBLIC_TEST else "private"
            if image_provenance != expected_provenance:
                raise DataPolicyError("Spark image requires an explicit matching provenance marker")
            if (
                data_class is DataClass.PUBLIC_TEST and data_policy is not DataPolicy.PUBLIC_TEST
                or data_class is DataClass.PRIVATE and data_policy is not DataPolicy.PRIVATE
            ):
                raise DataPolicyError("Spark data policy does not match image classification")
            if data_class is DataClass.PRIVATE and values.get("allow_private_upload") is not True:
                raise DataPolicyError("private image upload is not explicitly enabled in provider config")
            diagnosis_cap = values.get("diagnosis_max_tokens")
            if type(diagnosis_cap) is not int or diagnosis_cap <= 0:
                raise LiveConfigError(
                    "diagnosis_max_tokens is missing or invalid", condition="diagnosis_max_tokens"
                )
            configured_cap = values.get("max_tokens")
            if type(configured_cap) is not int or diagnosis_cap > configured_cap:
                raise LiveConfigError(
                    "diagnosis_max_tokens exceeds the configured provider cap",
                    condition="diagnosis_max_tokens",
                )
            values["max_tokens"] = diagnosis_cap
            self._image_data = base64.b64encode(image_bytes).decode("ascii")
        else:
            self._image_data = None

        if context is None:
            self._context = "Synthetic connectivity check; no crop or disease finding is supplied."
        else:
            outputs = context if isinstance(context, tuple) else (context,)
            if not outputs or any(type(item) is not DiagnosisOutput for item in outputs):
                raise ValueError("Spark context must contain validated diagnosis outputs")
            for item in outputs:
                validate_diagnosis_json(
                    json.dumps(asdict(item)), supported_crops=supported_crops,
                    disease_ids=disease_ids, confidence_bands=confidence_bands,
                )
            self._context = json.dumps([asdict(item) for item in outputs], separators=(",", ":"))
        if type(use_contributor) is not bool:
            raise DataPolicyError("Spark provider mode selection is invalid")
        expected_mode = ProviderMode.CONTRIBUTOR if use_contributor else ProviderMode.STANDARD
        if evidence.provider_mode is not expected_mode:
            raise DataPolicyError("Spark evidence does not match selected provider mode")
        require_external_processing_allowed(data_policy, data_class, evidence)
        model_key = "model_id_contributor" if use_contributor else "model_id"
        values["model_id"] = values.get(model_key)
        super().__init__(
            values, cli_authorized=cli_authorized, max_spend_usd=max_spend_usd,
            ledger_path=ledger_path, credential_env_var="META_API_KEY",
            environ=environ, transport=transport if transport is not None else UrllibJsonTransport(),
            trace_callback=trace_callback, retry_delays_s=retry_delays_s, sleep=sleep,
            supported_crops=supported_crops, disease_ids=disease_ids,
            confidence_bands=confidence_bands,
        )

    @property
    def _step_name(self) -> str:
        return "spark_meta"

    @property
    def execution_provenance(self) -> str:
        """Distinguish the built-in HTTP path from an injected test transport."""
        return "live-spark" if type(self._transport) is UrllibJsonTransport else "injected-transport"

    def _body(self, model: str, text: str) -> dict[str, Any]:
        content: Any = text + " Evidence: " + self._context
        if self._image_data is not None:
            content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {
                    "url": "data:image/jpeg;base64," + self._image_data,
                }},
            ]
        return {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": self._config["max_tokens"],
        }
