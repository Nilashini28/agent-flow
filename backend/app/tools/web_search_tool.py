"""Example low-risk tool: web search."""
from app.core.sandbox.policy import get_policy
from app.core.sandbox.docker_runner import run_sandboxed


def web_search(query: str) -> str:
    policy = get_policy("web_search")
    # TODO: replace with a real search call; sandbox-wrapped for demo purposes
    return run_sandboxed(policy, ["python3", "-c", f"print('search results for {query}')"])
