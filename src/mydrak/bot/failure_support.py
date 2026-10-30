"""Bounded fake-delivery retries and privacy-safe B11 failure traces."""

from hashlib import sha256
import time
import uuid

from mydrak.trace.store import TraceCase, TraceStep, TraceStore


def retry_fake_send(transport, conversation_key: str, text: str) -> tuple[bool, int]:
    """Retry the fake transport at most twice with small local backoff."""
    retries = 0
    for attempt in range(3):
        try:
            transport.send(conversation_key, text)
            return True, retries
        except Exception:
            if attempt == 2:
                return False, retries
            time.sleep(0.01 * (2 ** retries))
            retries += 1
    return False, retries


def record_bot_failure(
    store: TraceStore | None,
    *,
    conversation_key: str,
    language: str,
    input_type: str,
    outcome: str,
    action: str,
    error_code: str,
    retries: int = 0,
) -> None:
    """Persist fixed failure metadata and a digest, never message contents."""
    if store is None:
        return
    case_id = uuid.uuid4().hex
    digest = sha256(conversation_key.encode("utf-8")).hexdigest()
    store.record_case(
        TraceCase(
            case_id=case_id,
            final_action=action,
            lang=language,
            input_type=input_type,
            data_policy=None,
            user_hash=digest,
        ),
        [TraceStep(
            "transcription" if input_type == "voice" else "telegram_send",
            outcome, 0.0, model="synthetic_mock", error_code=error_code,
            retries=retries,
        )],
    )
    store.record_signals(
        case_id, s1=None, s2=None, s3=None, s4=None, score=None,
        decision=action, escalated=False,
    )
