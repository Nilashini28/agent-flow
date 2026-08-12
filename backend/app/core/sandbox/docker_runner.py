"""Execute a tool command inside a resource-capped execution environment.

TWO SANDBOX BACKENDS — same interface, different isolation strength:
─────────────────────────────────────────────────────────────────────

DOCKER MODE  (SANDBOX_MODE=docker)
  Full container isolation: separate filesystem namespace, no host network
  (unless explicitly allowed), memory and CPU hard limits enforced by the
  Linux kernel cgroup.  Strongest isolation available without paid
  gVisor/Firecracker.

  Limitation: requires a Docker daemon socket.  Most free-tier PaaS hosts
  (Render, Fly.io free, Railway free) do NOT provide a Docker socket, so
  this mode only works in local development.

  Auto-fallback: if docker.from_env() raises DockerException at import
  time or at the first connection attempt, a WARNING is emitted once and
  the system falls back to subprocess mode for that invocation.  This
  prevents every run from crashing when the same codebase is deployed to
  a host without Docker.

SUBPROCESS MODE  (SANDBOX_MODE=subprocess)  ← default for hosted deployment
  Runs the command as a child process of the main Python interpreter.

  Resources enforced:
    - Wall-clock timeout via subprocess.run(timeout=...) — kills the
      process with SIGKILL if it exceeds the policy's timeout_seconds.
    - Memory limit (POSIX/Linux only): resource.setrlimit(RLIMIT_AS, ...)
      sets the address-space limit in the child process's preexec_fn.
      Exceeding this causes the kernel to kill the process with SIGKILL.
    - CPU time (POSIX/Linux only): resource.setrlimit(RLIMIT_CPU, ...)
      limits CPU seconds; the process receives SIGXCPU then SIGKILL.

  HONEST ISOLATION TRADE-OFF (important — read this):
    Subprocess mode does NOT provide:
      • Filesystem namespace isolation — the child can read any file the
        main process can read.
      • Network namespace isolation — the child can make network calls
        even if the policy says allow_network=False (we block this in
        run_sandboxed() before spawning, but a malicious script could
        bypass the check by not using our API).
      • Privilege isolation — the child runs as the same OS user.

    This means subprocess mode is suitable for:
      ✓ Limiting runaway resource usage (timeouts, OOM).
      ✓ Enforcing AgentFlow's own policy checks (path, network flags).
      ✓ Containing honest tool-code that follows the API.

    It is NOT suitable for:
      ✗ Executing untrusted third-party code from the internet.
      ✗ Preventing a determined attacker who controls the command string.

    For the AgentFlow demo and free-tier deployment, subprocess mode is
    the right trade-off: it provides meaningful guardrails without
    requiring infrastructure that costs money or excludes free hosting.
    Docker mode is the right answer for production deployments where a
    daemon is available.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any

from app.config import get_settings
from app.core.sandbox.policy import ToolPolicy
from app.core.sandbox.violations import log_violation

logger = logging.getLogger(__name__)
_settings = get_settings()

# ── Resource limit support (POSIX only) ──────────────────────────────────────
# `resource` is a stdlib module on Linux/macOS but does NOT exist on Windows.
# We gate all usage behind this flag so the module imports cleanly on Windows.
try:
    import resource as _resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

# ── Docker availability ───────────────────────────────────────────────────────
# Import docker-py lazily so subprocess-only environments don't need it.
# _DOCKER_UNAVAILABLE is set to True the first time docker.from_env() fails;
# subsequent calls skip the Docker attempt entirely (one warning, not N).
_DOCKER_UNAVAILABLE: bool = False


def _get_docker_client():
    """Return a Docker client, or None if Docker is unavailable.

    Side-effect on first failure: sets _DOCKER_UNAVAILABLE=True and emits a
    WARNING so the caller can fall back to subprocess mode.
    """
    global _DOCKER_UNAVAILABLE  # noqa: PLW0603
    if _DOCKER_UNAVAILABLE:
        return None
    try:
        import docker
        client = docker.from_env()
        client.ping()  # confirm socket is reachable
        return client
    except Exception as exc:  # noqa: BLE001
        _DOCKER_UNAVAILABLE = True
        logger.warning(
            "Docker is unavailable (%s: %s). "
            "Falling back to subprocess sandbox mode for this and all subsequent runs. "
            "Set SANDBOX_MODE=subprocess to suppress this warning.",
            type(exc).__name__,
            exc,
        )
        return None


# ── Subprocess resource-limit helpers ────────────────────────────────────────


def _make_preexec_fn(mem_limit_bytes: int | None, cpu_limit_seconds: int | None):
    """Return a preexec_fn closure that sets POSIX resource limits.

    Returns None on Windows (resource module unavailable) so subprocess.run
    can be called without a preexec_fn argument.

    The limits are set INSIDE the child process before exec() replaces the
    image, so they apply to the tool command and not to the parent process.
    """
    if not HAS_RESOURCE:
        return None  # Windows: no preexec_fn support; timeout-only enforcement

    def _set_limits():
        if mem_limit_bytes:
            # RLIMIT_AS caps virtual address space (includes mmap/malloc).
            # Exceeding it causes malloc() to return NULL and new() to throw,
            # or the kernel kills the process with SIGKILL on the next mmap.
            _resource.setrlimit(
                _resource.RLIMIT_AS,
                (mem_limit_bytes, mem_limit_bytes),
            )
        if cpu_limit_seconds:
            # RLIMIT_CPU caps CPU time in seconds.  When exceeded the process
            # receives SIGXCPU (soft), then SIGKILL (hard).
            _resource.setrlimit(
                _resource.RLIMIT_CPU,
                (cpu_limit_seconds, cpu_limit_seconds + 1),
            )

    return _set_limits


def _parse_mem_limit(mem_limit_str: str) -> int:
    """Convert Docker-style memory string to bytes ('256m' → 268435456)."""
    mem_limit_str = mem_limit_str.strip().lower()
    if mem_limit_str.endswith("g"):
        return int(float(mem_limit_str[:-1]) * 1024 ** 3)
    if mem_limit_str.endswith("m"):
        return int(float(mem_limit_str[:-1]) * 1024 ** 2)
    if mem_limit_str.endswith("k"):
        return int(float(mem_limit_str[:-1]) * 1024)
    return int(mem_limit_str)


# ── Core runners ─────────────────────────────────────────────────────────────


def run_in_docker(
    policy: ToolPolicy,
    command: list[str],
    run_id: str | None = None,
) -> str:
    """Run *command* inside an ephemeral Docker container.

    Resource limits enforced by the Linux cgroup (hard limits):
      - Memory: policy.mem_limit (e.g. "256m")
      - CPU: policy.cpu_limit (fraction of one core → nano_cpus)
      - Wall-clock timeout: policy.timeout_seconds

    Network is disabled unless policy.allow_network=True.

    Raises:
        ConnectionError: if Docker is unavailable (caller should fall back).
        TimeoutError: if the container exceeds timeout_seconds.
        PermissionError: if a policy violation is detected.
    """
    client = _get_docker_client()
    if client is None:
        raise ConnectionError(
            "Docker daemon is not reachable.  "
            "Ensure Docker is running, or set SANDBOX_MODE=subprocess."
        )

    try:
        result = client.containers.run(
            image="python:3.11-slim",
            command=command,
            mem_limit=policy.mem_limit,
            nano_cpus=int(policy.cpu_limit * 1e9),
            network_disabled=not policy.allow_network,
            remove=True,
            stdout=True,
            stderr=True,
        )
        return result.decode() if isinstance(result, bytes) else str(result)

    except Exception as exc:  # noqa: BLE001
        exc_name = type(exc).__name__
        # docker.errors.APIError with status 137 = OOM / resource limit.
        if "137" in str(exc) or "OOMKilled" in str(exc):
            log_violation(
                policy.tool_name,
                f"docker_resource_limit_exceeded: {exc_name}",
                run_id=run_id,
            )
            raise MemoryError(
                f"Docker container for {policy.tool_name!r} was killed by "
                f"resource limits (OOM or CPU): {exc}"
            ) from exc
        # ContainerError / APIError for other failures
        log_violation(
            policy.tool_name,
            f"docker_execution_failed: {exc_name}: {exc}",
            run_id=run_id,
        )
        raise ConnectionError(
            f"Docker execution failed for {policy.tool_name!r}: {exc}"
        ) from exc


def run_in_subprocess(
    policy: ToolPolicy,
    command: list[str],
    run_id: str | None = None,
) -> str:
    """Run *command* in a child process with resource limits.

    Resource limits applied (where supported by OS):
      - Wall-clock timeout: always enforced via subprocess.run(timeout=...).
      - Memory (POSIX only): RLIMIT_AS set via preexec_fn.
      - CPU time (POSIX only): RLIMIT_CPU set via preexec_fn.

    On Windows: timeout-only enforcement.  Memory and CPU limits are not
    available because the `resource` module is POSIX-only.  See module
    docstring for the full isolation trade-off.

    Raises:
        TimeoutError: wall-clock timeout exceeded.  Classified as RETRYABLE
            by Stage 3's is_retryable() because TimeoutError is in the
            RETRYABLE_EXCEPTIONS tuple.
        MemoryError: subprocess killed by RLIMIT_AS (POSIX).  The process
            returns exit code -signal.SIGKILL (typically -9) or similar.
        PermissionError: policy pre-check failed (network/path violation).
    """
    mem_bytes = getattr(policy, "mem_limit_bytes", None) or _parse_mem_limit(policy.mem_limit)
    cpu_seconds = max(1, int(policy.cpu_limit * policy.timeout_seconds))
    preexec_fn = _make_preexec_fn(mem_bytes, cpu_seconds)

    kwargs: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "timeout": policy.timeout_seconds,
    }
    # preexec_fn is POSIX-only; subprocess.run raises TypeError on Windows if set.
    if preexec_fn is not None:
        kwargs["preexec_fn"] = preexec_fn

    try:
        result = subprocess.run(command, **kwargs)

        # Negative exit codes on POSIX = killed by signal.
        # -9 (SIGKILL) or -6 (SIGABRT) often indicate OOM kill.
        if result.returncode < 0:
            log_violation(
                policy.tool_name,
                f"subprocess_killed_by_signal: returncode={result.returncode}",
                run_id=run_id,
                extra={"returncode": result.returncode},
            )
            raise MemoryError(
                f"Subprocess for {policy.tool_name!r} was killed by signal "
                f"(returncode={result.returncode}). "
                "Likely cause: memory limit (RLIMIT_AS) exceeded."
            )

        if result.returncode != 0:
            log_violation(
                policy.tool_name,
                f"subprocess_non_zero_exit: {result.stderr[:200]}",
                run_id=run_id,
                extra={"returncode": result.returncode},
            )

        return result.stdout

    except subprocess.TimeoutExpired as exc:
        log_violation(
            policy.tool_name,
            f"subprocess_timeout_exceeded: limit={policy.timeout_seconds}s",
            run_id=run_id,
        )
        # Re-raise as TimeoutError so Stage 3's is_retryable() classifies
        # this as RETRYABLE (TimeoutError is in RETRYABLE_EXCEPTIONS).
        raise TimeoutError(
            f"Tool {policy.tool_name!r} exceeded its {policy.timeout_seconds}s "
            "wall-clock timeout.  This is a transient error and will be retried."
        ) from exc


def run_sandboxed(
    policy: ToolPolicy,
    command: list[str],
    run_id: str | None = None,
) -> str:
    """Execute *command* in the appropriate sandbox backend.

    Pre-flight policy checks (before spawning anything):
      1. Network access — raises PermissionError immediately if the command
         includes explicit network flags while policy.allow_network=False.

    Backend selection:
      - SANDBOX_MODE=docker AND Docker daemon reachable → run_in_docker().
      - Otherwise (SANDBOX_MODE=subprocess, OR docker auto-fallback) →
        run_in_subprocess().

    All callers should treat the return value as an opaque string (the
    tool's stdout).  Exceptions propagate unchanged for Stage 3 retry logic.
    """
    from app.core.sandbox.violations import check_network_policy

    # Pre-flight: network check (command-level flag, not just policy flag).
    if "--network" in command and not policy.allow_network:
        check_network_policy(policy.tool_name, allow_network=False, run_id=run_id)

    mode = _settings.sandbox_mode

    if mode == "docker":
        client = _get_docker_client()
        if client is None:
            # Auto-fallback: Docker unavailable, warn already logged once.
            return run_in_subprocess(policy, command, run_id=run_id)
        return run_in_docker(policy, command, run_id=run_id)

    return run_in_subprocess(policy, command, run_id=run_id)
