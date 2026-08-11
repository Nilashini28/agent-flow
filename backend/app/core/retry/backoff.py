"""Exponential backoff with jitter.

Formula
-------
    delay = min(base_delay * (2 ** attempt), max_delay)
    delay += delay * jitter_factor * random.uniform(-1, 1)

where:
  attempt      — 0-indexed attempt number (0 = first retry, 1 = second, …)
  jitter_factor — fraction of the computed delay added as random noise
                  (default ±20%) to avoid thundering-herd when many runs
                  hit the same transient failure simultaneously.

Pure-function design
--------------------
`sleep_fn` is injected rather than hardcoded to `time.sleep` so unit tests
can pass a no-op lambda and run in microseconds without any actual sleeping.
The function returns the delay it computed so tests can assert the sequence
of values is strictly increasing (pre-jitter).
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable


def compute_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_factor: float = 0.2,
) -> float:
    """Return the backoff delay (in seconds) for *attempt* (0-indexed).

    Does NOT sleep — call ``sleep_fn`` with the returned value separately
    so callers can intercept the delay for logging / testing.

    Args:
        attempt:      0-indexed retry attempt number.
        base_delay:   Starting delay in seconds (for attempt=0).
        max_delay:    Hard cap — no single wait exceeds this.
        jitter_factor: Fraction of the pre-jitter delay added as ±noise.

    Returns:
        Delay in seconds (always >= 0).
    """
    if attempt < 0:
        raise ValueError(f"attempt must be >= 0, got {attempt}")

    raw = base_delay * (2 ** attempt)
    capped = min(raw, max_delay)
    jitter = capped * jitter_factor * random.uniform(-1.0, 1.0)
    delay = max(0.0, capped + jitter)
    return delay


def backoff_sleep(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_factor: float = 0.2,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> float:
    """Compute the backoff delay and sleep for that duration.

    Args:
        attempt:      0-indexed retry attempt number.
        base_delay:   Starting delay in seconds.
        max_delay:    Hard cap per sleep.
        jitter_factor: ±fraction noise applied to prevent thundering-herd.
        sleep_fn:     Injectable sleep callable — default ``time.sleep``.
                      Tests inject ``lambda _: None`` to avoid real waits.

    Returns:
        The actual delay value passed to sleep_fn (useful for logging).
    """
    delay = compute_backoff_delay(
        attempt=attempt,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter_factor=jitter_factor,
    )
    sleep_fn(delay)
    return delay
