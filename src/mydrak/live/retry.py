"""Small injected retry primitive for B11-compatible future clients."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import math
from typing import TypeVar

T = TypeVar("T")


def call_with_retries(
    operation: Callable[[], T],
    fallback: Callable[[], T],
    *,
    retry_delays_s: Sequence[float],
    sleep: Callable[[float], None],
    retry_on: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Retry an injected operation at most twice, then use its safe fallback.

    Delay values and sleeping are injected so tests remain deterministic and
    callers cannot silently inherit an unverified retry schedule.
    """
    if not callable(operation) or not callable(fallback) or not callable(sleep):
        raise ValueError("operation, fallback, and sleep must be callable")
    if (not isinstance(retry_on, tuple) or not retry_on
            or any(not isinstance(item, type) or not issubclass(item, Exception) for item in retry_on)):
        raise ValueError("retry_on must contain exception classes")
    if not isinstance(retry_delays_s, (tuple, list)) or len(retry_delays_s) > 2:
        raise ValueError("retry schedule must contain zero to two delays")
    delays: list[float] = []
    for value in retry_delays_s:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("retry delays must be positive numbers")
        delays.append(float(value))
    for attempt in range(len(delays) + 1):
        try:
            return operation()
        except Exception as exc:
            if not isinstance(exc, retry_on):
                raise
            if attempt == len(delays):
                return fallback()
            sleep(delays[attempt])
    raise AssertionError("unreachable")
