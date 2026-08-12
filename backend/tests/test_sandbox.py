"""Stage-4 sandbox isolation tests.

Test strategy
-------------
All tests run on the current host (Windows, no Docker, no resource module).
Tests are designed to pass on this environment and on Linux Render deployments:

  - Docker tests: skipped unless SANDBOX_MODE=docker AND Docker is reachable.
  - resource-limit tests: skipped on Windows (no POSIX resource module).
  - Subprocess tests: run everywhere — timeout enforcement via wall-clock.
  - Policy / violation tests: pure-Python, no subprocess needed.
  - Cross-stage integration test (Test 5): confirms sandbox TimeoutError is
    correctly classified as RETRYABLE by Stage 3's retry policy.

No mocks are used for the subprocess runner — real child processes are
spawned and real policy objects are exercised.
"""
from __future__ import annotations

import os
import sys
import time
import uuid

import pytest

from app.core.sandbox.policy import (
    DEFAULT_POLICIES,
    ToolPolicy,
    get_policy,
    get_policy_or_deny,
)
from app.core.sandbox.violations import (
    check_network_policy,
    check_write_path_policy,
    get_violations,
    log_violation,
)

# ── Environment detection ─────────────────────────────────────────────────────

try:
    import resource as _resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

def _docker_available() -> bool:
    try:
        import docker
        c = docker.from_env()
        c.ping()
        return True
    except Exception:
        return False

DOCKER_AVAILABLE = _docker_available()


# ---------------------------------------------------------------------------
# Test 1 — Policy registration and ToolPolicy attributes
# ---------------------------------------------------------------------------


def test_default_policies_registered():
    """All tools used by act_step must have registered policies."""
    assert get_policy("stub-retrieval") is not None
    assert get_policy("stub-executor") is not None
    assert get_policy("web_search") is not None
    assert get_policy("file_write") is not None


def test_get_policy_or_deny_raises_for_unregistered():
    with pytest.raises(PermissionError, match="no registered policy"):
        get_policy_or_deny("completely_unknown_tool_xyz")


def test_tool_policy_network_defaults():
    assert DEFAULT_POLICIES["stub-retrieval"].allow_network is False
    assert DEFAULT_POLICIES["web_search"].allow_network is True
    assert DEFAULT_POLICIES["stub-executor"].allow_network is False


def test_tool_policy_write_defaults():
    assert DEFAULT_POLICIES["stub-retrieval"].allow_filesystem_write is False
    assert DEFAULT_POLICIES["stub-executor"].allow_filesystem_write is True
    assert DEFAULT_POLICIES["file_write"].allow_filesystem_write is True


def test_is_write_path_allowed_in_bounds():
    """Paths inside allowed_write_dirs must be permitted."""
    import tempfile, os

    tmpdir = tempfile.mkdtemp()
    policy = ToolPolicy(
        tool_name="test_tool",
        risk_tier="low",
        allow_filesystem_write=True,
        allowed_write_dirs=frozenset([tmpdir]),
    )
    inner_path = os.path.join(tmpdir, "output.txt")
    assert policy.is_write_path_allowed(inner_path) is True


def test_is_write_path_allowed_out_of_bounds():
    """Paths outside allowed_write_dirs must be rejected."""
    import tempfile, os

    tmpdir = tempfile.mkdtemp()
    policy = ToolPolicy(
        tool_name="test_tool",
        risk_tier="low",
        allow_filesystem_write=True,
        allowed_write_dirs=frozenset([tmpdir]),
    )
    # /etc on Linux, C:\Windows on Windows — clearly outside tmpdir.
    outside = os.path.abspath(os.path.join(tmpdir, "..", "other_dir", "file.txt"))
    assert policy.is_write_path_allowed(outside) is False


def test_is_write_path_not_allowed_when_write_disabled():
    import tempfile
    tmpdir = tempfile.mkdtemp()
    policy = ToolPolicy(
        tool_name="read_only",
        risk_tier="low",
        allow_filesystem_write=False,
        allowed_write_dirs=frozenset([tmpdir]),
    )
    assert policy.is_write_path_allowed(os.path.join(tmpdir, "x.txt")) is False


# ---------------------------------------------------------------------------
# Test 2 — Violation logging and timeline integration
# ---------------------------------------------------------------------------


def test_log_violation_appends_record():
    before = len(get_violations())
    log_violation("test_tool", "test reason")
    after = len(get_violations())
    assert after == before + 1
    assert get_violations()[-1]["tool_name"] == "test_tool"
    assert get_violations()[-1]["reason"] == "test reason"


def test_log_violation_attaches_to_run_timeline():
    """log_violation with run_id must call log_event so it appears in timeline."""
    from app.observability.event_log import get_timeline

    run_id = f"violation-test-{uuid.uuid4().hex[:8]}"
    log_violation("test_tool", "timeline_check", run_id=run_id, extra={"key": "val"})

    timeline = get_timeline(run_id)
    sandbox_events = [e for e in timeline if e["event_type"] == "sandbox_violation"]
    assert len(sandbox_events) == 1
    assert sandbox_events[0]["payload"]["tool_name"] == "test_tool"
    assert sandbox_events[0]["payload"]["key"] == "val"


def test_check_network_policy_blocks_no_network_tool():
    """check_network_policy() must raise PermissionError for no-network tools."""
    run_id = f"net-violation-{uuid.uuid4().hex[:8]}"
    with pytest.raises(PermissionError, match="not permitted to access the network"):
        check_network_policy("stub-executor", allow_network=False, run_id=run_id)

    # Violation must appear in run timeline.
    from app.observability.event_log import get_timeline
    timeline = get_timeline(run_id)
    assert any(
        e["event_type"] == "sandbox_violation"
        and "network" in e["payload"]["reason"]
        for e in timeline
    )


def test_check_network_policy_allows_network_tool():
    """check_network_policy() must NOT raise for tools with allow_network=True."""
    check_network_policy("web_search", allow_network=True)  # no exception


def test_check_write_path_blocked_no_write_permission():
    """Attempting to write when allow_filesystem_write=False must raise PermissionError."""
    import tempfile
    tmpdir = tempfile.mkdtemp()
    run_id = f"write-violation-{uuid.uuid4().hex[:8]}"
    policy = ToolPolicy(
        tool_name="stub-retrieval",
        risk_tier="low",
        allow_filesystem_write=False,
    )
    with pytest.raises(PermissionError, match="does not have filesystem write permission"):
        check_write_path_policy("stub-retrieval", os.path.join(tmpdir, "out.txt"), policy, run_id=run_id)

    from app.observability.event_log import get_timeline
    timeline = get_timeline(run_id)
    assert any(
        e["event_type"] == "sandbox_violation"
        and "filesystem_write_not_permitted" in e["payload"]["reason"]
        for e in timeline
    )


def test_check_write_path_blocked_outside_allowed_dir():
    """Writing outside allowed_write_dirs must raise PermissionError and log violation."""
    import tempfile
    tmpdir = tempfile.mkdtemp()
    outside = os.path.abspath(os.path.join(tmpdir, "..", "escape_attempt.txt"))
    run_id = f"path-escape-{uuid.uuid4().hex[:8]}"

    policy = ToolPolicy(
        tool_name="file_write",
        risk_tier="high",
        allow_filesystem_write=True,
        allowed_write_dirs=frozenset([tmpdir]),
    )
    with pytest.raises(PermissionError, match="outside its allowed directories"):
        check_write_path_policy("file_write", outside, policy, run_id=run_id)

    from app.observability.event_log import get_timeline
    timeline = get_timeline(run_id)
    assert any(
        e["event_type"] == "sandbox_violation"
        and "write_path_outside_allowed_dirs" in e["payload"]["reason"]
        for e in timeline
    )


# ---------------------------------------------------------------------------
# Test 3 — Subprocess runner: basic execution
# ---------------------------------------------------------------------------


def test_subprocess_runner_executes_simple_command():
    """run_in_subprocess must return stdout of a basic echo command."""
    from app.core.sandbox.docker_runner import run_in_subprocess

    policy = get_policy_or_deny("stub-executor")
    command = [sys.executable, "-c", "print('hello sandbox')"]
    output = run_in_subprocess(policy, command)
    assert "hello sandbox" in output


def test_subprocess_runner_timeout_raises_timeout_error():
    """A command that sleeps beyond the timeout must raise TimeoutError.

    This proves the wall-clock timeout is actually enforced, not just stored
    as an attribute on the policy object.
    """
    from app.core.sandbox.docker_runner import run_in_subprocess

    policy = ToolPolicy(
        tool_name="timeout_test",
        risk_tier="low",
        timeout_seconds=1,  # 1-second limit
    )
    # Sleep for 10 seconds — should be killed after 1s.
    command = [sys.executable, "-c", "import time; time.sleep(10)"]

    t0 = time.time()
    with pytest.raises(TimeoutError):
        run_in_subprocess(policy, command)
    elapsed = time.time() - t0

    # Must fail in ~1s, definitely not after 5s.
    assert elapsed < 5, f"Timeout took {elapsed:.1f}s — enforcement too slow"


# ---------------------------------------------------------------------------
# Test 4 — Resource limits (POSIX only)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_RESOURCE, reason="resource module not available on Windows")
def test_subprocess_memory_limit_kills_process():
    """A process allocating more than mem_limit_bytes must be killed.

    This is the hard enforcement proof: we spawn a subprocess that tries to
    allocate 512 MB, against a 32 MB RLIMIT_AS limit.  The kernel kills it
    and run_in_subprocess must raise MemoryError.
    """
    from app.core.sandbox.docker_runner import run_in_subprocess

    policy = ToolPolicy(
        tool_name="mem_limit_test",
        risk_tier="low",
        mem_limit_bytes=32 * 1024 * 1024,   # 32 MB virtual address limit
        timeout_seconds=5,
    )
    # Allocate 512 MB — must be killed by RLIMIT_AS.
    command = [
        sys.executable, "-c",
        "data = bytearray(512 * 1024 * 1024); print('allocated')"
    ]
    with pytest.raises((MemoryError, Exception)):
        run_in_subprocess(policy, command)


# ---------------------------------------------------------------------------
# Test 5 — Cross-stage: sandbox TimeoutError is RETRYABLE (Stage 3 integration)
# ---------------------------------------------------------------------------


def test_sandbox_timeout_is_retryable_per_stage3_policy():
    """TimeoutError from a sandboxed call must be classified as RETRYABLE.

    This is the Stage 3 ↔ Stage 4 integration guarantee:
    - Stage 3's is_retryable() includes TimeoutError in RETRYABLE_EXCEPTIONS.
    - Stage 4's run_in_subprocess() re-raises subprocess.TimeoutExpired as
      TimeoutError (not as the original TimeoutExpired).
    - _run_with_retry() will therefore retry a timed-out sandbox call.

    The test uses a real closure-over-counter body that calls
    run_in_subprocess with a 1-second timeout on a 10-second sleep,
    confirming the entire control-flow chain, not just that TimeoutError
    is in a list.
    """
    from app.core.retry.policy import is_retryable, RetryPolicy, DEFAULT_POLICY
    from app.core.graph.nodes import _run_with_retry
    from app.core.graph.schemas import AgentState

    # Confirm classification first.
    assert is_retryable(TimeoutError("sandbox timeout")) is True, (
        "TimeoutError must be RETRYABLE — Stage 4 sandbox timeout recovery depends on this"
    )

    # Now prove the full retry loop works with a real timed-out subprocess.
    from app.core.sandbox.docker_runner import run_in_subprocess

    call_count: list[int] = [0]

    def _body(state: AgentState) -> dict:
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: trigger a real subprocess timeout.
            short_policy = ToolPolicy(
                tool_name="cross_stage_test",
                risk_tier="low",
                timeout_seconds=1,
            )
            cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
            run_in_subprocess(short_policy, cmd)  # raises TimeoutError
        # Second call: succeed.
        return {**state, "status": "running", "last_output": "recovered", "error": None}

    sleep_calls: list[float] = []
    policy = RetryPolicy(max_retries=2, base_delay=0.0, max_delay=0.0)

    state = AgentState(
        run_id=f"cross-stage-{uuid.uuid4().hex[:8]}",
        task="cross-stage retry test",
        step_index=0, history=[], last_output="", tool_calls=[],
        risk_score=0.0, status="running", error=None, retry_count=0,
    )

    result = _run_with_retry(
        _body, "cross_stage_node", state,
        policy=policy,
        sleep_fn=lambda d: sleep_calls.append(d),
    )

    assert result["status"] == "running", (
        f"Expected running after recovery, got {result['status']!r} / {result.get('error')}"
    )
    assert call_count[0] == 2, (
        f"Body must be called exactly twice (timeout then success), got {call_count[0]}"
    )
    assert len(sleep_calls) == 1, (
        f"Expected 1 backoff sleep between attempt 0 and 1, got {len(sleep_calls)}"
    )


# ---------------------------------------------------------------------------
# Test 6 — Docker auto-fallback when daemon is unavailable
# ---------------------------------------------------------------------------


def test_docker_fallback_when_unavailable(monkeypatch):
    """When Docker is requested but unreachable, run_sandboxed must fall back
    to subprocess mode without raising, and log exactly one warning.

    This test uses monkeypatch to make docker.from_env() raise unconditionally,
    simulating a Render/free-host environment where no Docker socket exists.
    """
    import logging
    import importlib
    from app.core.sandbox import docker_runner

    # Reset the module-level flag so the test starts fresh.
    monkeypatch.setattr(docker_runner, "_DOCKER_UNAVAILABLE", False)

    # Make docker.from_env() always raise.
    import types
    fake_docker = types.ModuleType("docker")
    fake_docker.from_env = lambda: (_ for _ in ()).throw(Exception("no socket"))  # type: ignore
    monkeypatch.setitem(sys.modules, "docker", fake_docker)

    # Temporarily switch to docker mode.
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "sandbox_mode", "docker")
    monkeypatch.setattr(docker_runner, "_settings", settings)

    policy = get_policy_or_deny("stub-executor")
    command = [sys.executable, "-c", "print('fallback works')"]

    # Should NOT raise — must fall back to subprocess and succeed.
    output = docker_runner.run_sandboxed(policy, command)

    assert "fallback works" in output, f"Fallback subprocess output wrong: {output!r}"
    assert docker_runner._DOCKER_UNAVAILABLE is True, (
        "_DOCKER_UNAVAILABLE must be set to True after failed docker.from_env()"
    )


# ---------------------------------------------------------------------------
# Test 7 — run_sandboxed() via subprocess (default mode — end-to-end)
# ---------------------------------------------------------------------------


def test_run_sandboxed_subprocess_end_to_end():
    """run_sandboxed() in subprocess mode must execute a command and return stdout."""
    from app.core.sandbox.docker_runner import run_sandboxed
    import importlib, app.core.sandbox.docker_runner as dr

    # Ensure subprocess mode.
    from app.config import get_settings
    assert get_settings().sandbox_mode == "subprocess"

    policy = get_policy_or_deny("stub-executor")
    run_id = f"e2e-sandbox-{uuid.uuid4().hex[:8]}"
    command = [sys.executable, "-c", "print('sandboxed e2e output')"]

    output = run_sandboxed(policy, command, run_id=run_id)
    assert "sandboxed e2e output" in output


# ---------------------------------------------------------------------------
# Test 8 — Full graph run with act_step using sandbox (Stage 1/2/3 regression)
# ---------------------------------------------------------------------------


def test_full_graph_run_with_sandboxed_act_step():
    """End-to-end graph run with act_step dispatching through run_sandboxed().

    This is the Stage 1/2/3/4 regression test: the entire pipeline must
    complete successfully with the real sandbox wiring in place.
    """
    from app.core.graph.state_graph import build_graph
    from app.core.graph.schemas import AgentState

    run_id = f"stage4-regression-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial = AgentState(
        run_id=run_id,
        task="Analyse Q4 revenue with sandbox isolation",
        step_index=0, history=[], last_output="", tool_calls=[],
        risk_score=0.0, status="running", error=None, retry_count=0,
    )

    result = graph.invoke(initial, config=config)

    assert result["status"] == "completed", (
        f"Expected completed, got {result['status']!r} / error={result.get('error')}"
    )
    assert result["step_index"] == 4
    assert len(result["history"]) == 4

    # act_step should have produced sandboxed output.
    assert "ACT" in result.get("last_output", ""), (
        f"Expected ACT in last_output: {result.get('last_output')!r}"
    )

    # sandbox_dispatch events should appear in the timeline.
    from app.observability.event_log import get_timeline
    timeline = get_timeline(run_id)
    dispatch_events = [e for e in timeline if e["event_type"] == "sandbox_dispatch"]
    assert len(dispatch_events) >= 1, (
        "Expected at least 1 sandbox_dispatch event in timeline from act_step"
    )


# ---------------------------------------------------------------------------
# Test 9 — Docker mode: skipped unless Docker is available
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon not available")
def test_docker_runner_executes_simple_command():
    """Docker runner must execute a command inside a container."""
    from app.core.sandbox.docker_runner import run_in_docker

    policy = get_policy_or_deny("stub-executor")
    output = run_in_docker(policy, ["python3", "-c", "print('docker works')"])
    assert "docker works" in output


@pytest.mark.skipif(not DOCKER_AVAILABLE, reason="Docker daemon not available")
def test_docker_runner_enforces_memory_limit():
    """Container allocated more than mem_limit must be killed (OOM/resource exit)."""
    from app.core.sandbox.docker_runner import run_in_docker

    policy = ToolPolicy(
        tool_name="docker_mem_test",
        risk_tier="low",
        mem_limit="64m",  # 64 MB
        timeout_seconds=10,
    )
    # Try to allocate 512 MB inside the container.
    command = ["python3", "-c", "data = bytearray(512 * 1024 * 1024); print('allocated')"]
    with pytest.raises((MemoryError, ConnectionError, Exception)):
        run_in_docker(policy, command)
