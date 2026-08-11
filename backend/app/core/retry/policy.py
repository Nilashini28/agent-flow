"""Retry policy: which errors are retryable and per-node limits.

Design rationale
----------------
Two error categories, not a blanket "retry everything":

RETRYABLE — transient infrastructure failures where the operation is safe
to attempt again without side effects:
  - ConnectionError, TimeoutError: network/service hiccups
  - OSError (errno-gated): disk/socket I/O errors
  - Custom: RateLimitError (Stage-6 will surface these from LLM clients)
  - Custom: TransientToolError (Stage-4 sandbox: tool timed out)

NON-RETRYABLE — logical/semantic failures where retrying burns budget
without any chance of success:
  - ValueError: the input is invalid; the same input will fail again.
  - TypeError: a programming or schema error; won't self-heal.
  - PermissionError: the agent doesn't have access; won't change.
  - KeyError / AttributeError: state-shape errors; structural, not transient.
  - NotImplementedError: intentional placeholder raise in test stubs.

The line is drawn at: "could waiting and trying again plausibly succeed?"
A rate-limit can clear; a malformed JSON payload won't fix itself.

Per-node overrides
------------------
act_step writes external side effects (Stage-4: real tool calls).
Retrying a partially-applied write can cause duplicate side effects, so
act_step uses max_retries=1 rather than the default 3.  The other nodes
are pure-read/compute, so the default applies.

STAGE-5: once escalation is wired, an override could further reduce
max_retries when risk_score is high (retrying a risky act is worse than
halting fast).  Do not implement this yet.
STAGE-6: RateLimitError from Anthropic/OpenAI SDKs should be added to
RETRYABLE_EXCEPTIONS once real LLM calls land.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Exception classification
# ---------------------------------------------------------------------------

# Exceptions that are safe to retry — transient infrastructure problems.
RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)

# Exceptions that must NOT be retried — logical/semantic failures.
# This is an EXPLICIT denylist; anything not in RETRYABLE_EXCEPTIONS is
# also treated as non-retryable, but listing the most common ones here
# makes the policy auditable without reading the retry loop code.
NON_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    PermissionError,
    NotImplementedError,
)


def is_retryable(exc: BaseException) -> bool:
    """Return True if *exc* is a transient error worth retrying.

    Evaluation order:
    1. If it's explicitly NON-RETRYABLE, return False immediately.
    2. If it's explicitly RETRYABLE, return True.
    3. Default: False — unknown errors are treated as non-retryable to
       avoid silently wasting budget on errors we haven't classified yet.
    """
    if isinstance(exc, NON_RETRYABLE_EXCEPTIONS):
        return False
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True
    return False


# ---------------------------------------------------------------------------
# Per-node policy
# ---------------------------------------------------------------------------


class RetryPolicy:
    """Encapsulates retry configuration for a single node.

    Args:
        max_retries: Maximum number of re-attempts after the first failure.
                     Total invocations = max_retries + 1.
        base_delay:  Starting backoff delay in seconds (passed to backoff.py).
        max_delay:   Hard cap on any single delay in seconds.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ) -> None:
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {max_retries}")
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def __repr__(self) -> str:
        return (
            f"RetryPolicy(max_retries={self.max_retries}, "
            f"base_delay={self.base_delay}, max_delay={self.max_delay})"
        )


# ---------------------------------------------------------------------------
# Default policies per node
# ---------------------------------------------------------------------------
# Pure-read/compute nodes: 3 retries is generous but bounded.
DEFAULT_POLICY = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=30.0)

# act_step writes external side effects; fewer retries to limit duplicate
# writes.  Stage-4 will refine this further once sandbox isolation lands.
ACT_POLICY = RetryPolicy(max_retries=1, base_delay=2.0, max_delay=30.0)

# Mapping from node name → policy (consumed by nodes.py).
NODE_POLICIES: dict[str, RetryPolicy] = {
    "research": DEFAULT_POLICY,
    "draft": DEFAULT_POLICY,
    "verify": DEFAULT_POLICY,
    "act": ACT_POLICY,
}
