from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")

_RETRYABLE_MESSAGES = (
    "winerror 10054",
    "readtimeout",
    "read operation timed out",
    "forcibly closed by the remote host",
    "connection reset",
    "server disconnected",
    "connection aborted",
    "timed out",
    "temporary failure",
)


def is_retryable_connection_error(error: Exception) -> bool:
    message = f"{type(error).__name__}: {error}".casefold()
    return any(fragment in message for fragment in _RETRYABLE_MESSAGES)


def retry_read(
    action: Callable[[], T],
    *,
    attempts: int = 2,
    initial_delay_seconds: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry hanya untuk operasi baca/idempotent pada gangguan koneksi sementara."""
    if attempts < 1:
        raise ValueError("attempts minimal 1")
    for attempt in range(attempts):
        try:
            return action()
        except Exception as error:
            last_attempt = attempt == attempts - 1
            if last_attempt or not is_retryable_connection_error(error):
                raise
            sleep(initial_delay_seconds * (2**attempt))
    raise RuntimeError("retry_read reached an unreachable state")
