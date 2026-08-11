"""Example high-risk tool: writes to the filesystem.

Deliberately marked high-risk / irreversible in policy.py so it exercises
both the sandbox boundary and the escalation model in the demo.
"""
from app.core.sandbox.policy import get_policy
from app.core.sandbox.docker_runner import run_sandboxed


def write_file(path: str, content: str) -> str:
    policy = get_policy("file_write")
    escaped = content.replace(chr(39), chr(92) + chr(39))
    command = ["python3", "-c", "open('" + path + "', 'w').write('" + escaped + "')"]
    return run_sandboxed(policy, command)
