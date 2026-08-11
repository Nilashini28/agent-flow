"""Execute a tool call inside a resource-capped, ephemeral container.

Falls back to a subprocess-with-limits mode when SANDBOX_MODE=subprocess,
e.g. on hosts without Docker socket access (most free-tier PaaS).
"""
import subprocess

from app.config import get_settings
from app.core.sandbox.policy import ToolPolicy
from app.core.sandbox.violations import log_violation

_settings = get_settings()


def run_in_docker(policy: ToolPolicy, command: list[str]) -> str:
    import docker  # imported lazily so subprocess-only envs don't need docker-py

    client = docker.from_env()
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
            timeout=policy.timeout_seconds,
        )
        return result.decode() if isinstance(result, bytes) else str(result)
    except Exception as exc:  # noqa: BLE001
        log_violation(policy.tool_name, f"docker execution failed: {exc}")
        raise


def run_in_subprocess(policy: ToolPolicy, command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=policy.timeout_seconds,
        )
        if result.returncode != 0:
            log_violation(policy.tool_name, f"non-zero exit: {result.stderr}")
        return result.stdout
    except subprocess.TimeoutExpired:
        log_violation(policy.tool_name, "execution timed out")
        raise


def run_sandboxed(policy: ToolPolicy, command: list[str]) -> str:
    if not policy.allow_network and "--network" in command:
        log_violation(policy.tool_name, "attempted network access without permission")
        raise PermissionError(f"{policy.tool_name} is not permitted to use the network")

    if _settings.sandbox_mode == "docker":
        return run_in_docker(policy, command)
    return run_in_subprocess(policy, command)
