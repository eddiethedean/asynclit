from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, Tuple, Type


ExceptionTypes = Tuple[Type[BaseException], ...]


@dataclass(frozen=True)
class RetryPolicy:
    """
    Retry configuration for tasks that raise exceptions.

    Notes:
    - Retries are **exception-based** only (no result predicates).
    - Jitter is optional; disable for deterministic tests.
    """

    max_attempts: int = 1
    retry_on: ExceptionTypes = (Exception,)
    base_delay: float = 0.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: float = 0.0
    max_elapsed: Optional[float] = None
    retry_if: Optional[Callable[[BaseException], bool]] = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("RetryPolicy.max_attempts must be >= 1")
        if self.base_delay < 0:
            raise ValueError("RetryPolicy.base_delay must be >= 0")
        if self.max_delay < 0:
            raise ValueError("RetryPolicy.max_delay must be >= 0")
        if self.multiplier < 1:
            raise ValueError("RetryPolicy.multiplier must be >= 1")
        if not (0.0 <= self.jitter <= 1.0):
            raise ValueError("RetryPolicy.jitter must be in [0, 1]")
        if self.max_elapsed is not None and self.max_elapsed <= 0:
            raise ValueError("RetryPolicy.max_elapsed must be > 0 when set")

    def should_retry(self, exc: BaseException) -> bool:
        if not isinstance(exc, self.retry_on):
            return False
        if self.retry_if is not None and not self.retry_if(exc):
            return False
        return True

    def delay_for_attempt(self, attempt_index: int) -> float:
        """
        Compute the delay before attempt (attempt_index+2).

        attempt_index is 0 for a retry after the first failure, 1 after the second, etc.
        """
        if attempt_index < 0:
            raise ValueError("attempt_index must be >= 0")
        raw = self.base_delay * (self.multiplier**attempt_index)
        delay = min(raw, self.max_delay)
        if self.jitter:
            # Symmetric jitter: +/- jitter*delay.
            span = delay * self.jitter
            delay = max(0.0, delay + random.uniform(-span, span))
        return delay

    def start_time(self) -> float:
        return time.monotonic()

    def exceeded_elapsed(self, started_at: float) -> bool:
        if self.max_elapsed is None:
            return False
        return (time.monotonic() - started_at) >= self.max_elapsed
