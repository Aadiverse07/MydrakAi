"""Offline-only replay for in-memory cases and fixed cached demo responses.

Registered cached scenarios use the existing B9 SQLite cache and fixed
synthetic text. They never invoke providers or fall through to live execution.
The separate coordinator fixture path remains in-memory and is not serialized.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
import re
import time
from typing import Any
import uuid

from mydrak.privacy.data_policy import DataClass, ProcessingEvidence
from mydrak.reply.templates import OFFLINE_DEMO_RESPONSES
from mydrak.trace.store import (
    CACHE_PROVENANCE,
    CACHE_SCHEMA,
    CachedResponse,
    TraceCase,
    TraceError,
    TraceStep,
    TraceStore,
)
from mydrak.util.config import DemoMode, load_demo_mode, parse_demo_mode
from mydrak.workflow.coordinator import (
    OfflineCoordinationResult,
    OfflineCoordinatorError,
    SyntheticSamReplyFixture,
    coordinate_offline_case,
)

REPLAY_FIXTURE_PROVENANCE = "synthetic-offline-replay-fixture"
REGISTERED_DEMO_SCENARIOS = {
    "synthetic-answer-01": ("answer", "synthetic_answer"),
    "synthetic-ask-01": ("ask", "synthetic_ask"),
    "synthetic-referral-01": ("referred", "safe_referral"),
    "synthetic-retake-01": ("retake", "synthetic_retake"),
}
REGISTERED_DEMO_FIXTURE_IDS = frozenset(REGISTERED_DEMO_SCENARIOS)


class ReplayError(ValueError):
    """Raised when replay input is not an approved synthetic fixture."""


@dataclass(frozen=True)
class OfflineReplayFixture:
    """In-memory input assembled from existing offline coordinator types."""

    image_descriptor: Mapping[str, Any] = field(repr=False)
    sam_fixture: SyntheticSamReplyFixture = field(repr=False)
    safety_card: Mapping[str, Any] = field(repr=False)
    data_policy_value: str | None = None
    data_class: DataClass = DataClass.PRIVATE
    evidence: ProcessingEvidence | None = None
    language: str = "en"
    provenance: str = ""


@dataclass(frozen=True)
class ReplayResult:
    result: OfflineCoordinationResult
    provenance: str = REPLAY_FIXTURE_PROVENANCE


@dataclass(frozen=True)
class CachedReplayResult:
    cache_key: str
    status: str
    response_code: str
    reply: str
    timestamp: str
    provenance: str = CACHE_PROVENANCE


def demo_cache_key(fixture_id: str) -> str:
    """Create a stable key from a project-owned synthetic fixture identifier."""
    if not isinstance(fixture_id, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", fixture_id):
        raise ReplayError("fixture ID must be a bounded project identifier")
    material = f"mydrak-demo-cache-v1:{fixture_id}".encode("ascii")
    return hashlib.sha256(material).hexdigest()


def registered_demo_cache_key(fixture_id: str) -> str:
    """Resolve only fixture IDs explicitly registered in this offline build."""
    if not isinstance(fixture_id, str) or fixture_id not in REGISTERED_DEMO_FIXTURE_IDS:
        raise ReplayError("synthetic replay fixture is not registered")
    return demo_cache_key(fixture_id)


def seed_registered_demo_cache(trace_store: TraceStore) -> int:
    """Insert fixed synthetic demo replies; never overwrite or call providers."""
    if type(trace_store) is not TraceStore:
        raise ReplayError("trace store is required")
    inserted = 0
    for fixture_id, (status, response_code) in REGISTERED_DEMO_SCENARIOS.items():
        key = registered_demo_cache_key(fixture_id)
        try:
            if trace_store.get_cache(key) is None:
                trace_store.put_cache(key, {
                    "schema": CACHE_SCHEMA,
                    "provenance": CACHE_PROVENANCE,
                    "status": status,
                    "response_code": response_code,
                })
                inserted += 1
        except TraceError:
            raise ReplayError("synthetic demo cache could not be seeded") from None
    return inserted


def run_replay(fixture: OfflineReplayFixture, *, trace_store: TraceStore) -> ReplayResult:
    """Run one synthetic fixture through the existing network-free workflow."""
    if not isinstance(fixture, OfflineReplayFixture):
        raise ReplayError("an explicit offline replay fixture is required")
    if fixture.provenance != REPLAY_FIXTURE_PROVENANCE:
        raise ReplayError("replay fixture provenance is invalid")
    if not isinstance(fixture.sam_fixture, SyntheticSamReplyFixture):
        raise ReplayError("synthetic SAM fixture is required")
    if not isinstance(trace_store, TraceStore):
        raise ReplayError("trace store is required")
    try:
        result = coordinate_offline_case(
            fixture.image_descriptor,
            fixture.sam_fixture,
            data_policy_value=fixture.data_policy_value,
            safety_card=fixture.safety_card,
            data_class=fixture.data_class,
            evidence=fixture.evidence,
            language=fixture.language,
            trace_store=trace_store,
        )
    except OfflineCoordinatorError:
        raise ReplayError("offline replay case was rejected") from None
    return ReplayResult(result=result)


def cache_replay_result(
    cache_key: str,
    replay_result: ReplayResult,
    *,
    trace_store: TraceStore,
    timestamp: str | None = None,
) -> CachedResponse:
    """Cache only the allowlisted outcome of a labeled synthetic replay."""
    if not isinstance(trace_store, TraceStore) or not isinstance(replay_result, ReplayResult):
        raise ReplayError("trace store and replay result are required")
    if replay_result.provenance != REPLAY_FIXTURE_PROVENANCE:
        raise ReplayError("only explicitly synthetic replay results can be cached")
    result = replay_result.result
    if not isinstance(result, OfflineCoordinationResult):
        raise ReplayError("replay result does not contain a validated offline outcome")
    outcome_map = {
        ("blocked", "intake_policy_denied"): "policy_blocked",
        ("referred", "no_sam_detections_not_a_health_finding"): "safe_referral",
        ("manual_review", "sam_outcome_requires_manual_review"): "manual_review",
    }
    response_code = outcome_map.get((result.status, result.reason))
    if response_code is None or trace_store.get_case(result.case_id) is None:
        raise ReplayError("replay outcome is not eligible for the synthetic cache")
    payload = {
        "schema": CACHE_SCHEMA,
        "provenance": CACHE_PROVENANCE,
        "status": result.status,
        "response_code": response_code,
    }
    try:
        return trace_store.put_cache(cache_key, payload, timestamp=timestamp)
    except TraceError:
        raise ReplayError("synthetic cache entry was rejected") from None


def run_cached_replay(
    cache_key: str,
    *,
    trace_store: TraceStore,
    demo_mode: DemoMode | str | None = None,
    language: str = "en",
) -> CachedReplayResult:
    """Serve a validated local cache row; there is deliberately no fallback."""
    if not isinstance(trace_store, TraceStore):
        raise ReplayError("trace store is required")
    try:
        mode = load_demo_mode() if demo_mode is None else parse_demo_mode(demo_mode)
    except ValueError:
        raise ReplayError("DEMO_MODE is invalid or live mode is disabled") from None
    if mode is not DemoMode.REPLAY:
        raise ReplayError("only replay mode is supported")
    try:
        cached = trace_store.get_cache(cache_key)
    except TraceError:
        raise ReplayError("cached response is invalid") from None
    if cached is None:
        raise ReplayError("cached response is unavailable")
    if not isinstance(language, str):
        raise ReplayError("cached response language is unavailable")
    localized = OFFLINE_DEMO_RESPONSES.get(language)
    if not isinstance(localized, Mapping):
        raise ReplayError("cached response language is unavailable")
    reply = localized.get(cached.response_code)
    if not isinstance(reply, str):
        raise ReplayError("cached response code is unsupported")
    return CachedReplayResult(
        cache_key=cached.cache_key,
        status=cached.status,
        response_code=cached.response_code,
        reply=reply,
        timestamp=cached.timestamp,
    )


def run_registered_cached_replay(
    fixture_id: str,
    *,
    trace_store: TraceStore,
    demo_mode: DemoMode | str | None = None,
) -> CachedReplayResult:
    """Run the allowlisted caller path and record a privacy-safe cache read."""
    if not isinstance(trace_store, TraceStore) or type(trace_store) is not TraceStore:
        raise ReplayError("trace store is required")
    cache_key = registered_demo_cache_key(fixture_id)
    started = time.perf_counter()
    result = run_cached_replay(cache_key, trace_store=trace_store, demo_mode=demo_mode)
    elapsed_ms = max(0.0, (time.perf_counter() - started) * 1000)
    try:
        trace_store.record_case(
            TraceCase(
                case_id=uuid.uuid4().hex,
                final_action=result.status,
                lang="en",
                input_type="text",
                data_policy=None,
            ),
            [TraceStep("replay_cache_read", "completed", elapsed_ms)],
        )
    except TraceError:
        raise ReplayError("replay result could not be traced") from None
    return result
