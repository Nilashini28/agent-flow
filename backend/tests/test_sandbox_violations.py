"""Confirms out-of-policy actions are blocked and logged, not silently allowed."""
from app.core.sandbox.policy import get_policy
from app.core.sandbox.docker_runner import run_sandboxed
from app.core.sandbox.violations import get_violations


def test_network_denied_tool_raises():
    policy = get_policy("file_write")  # allow_network=False
    try:
        run_sandboxed(policy, ["curl", "--network", "http://example.com"])
        assert False, "expected PermissionError"
    except PermissionError:
        pass

    violations = get_violations()
    assert any(v["tool_name"] == "file_write" for v in violations)
