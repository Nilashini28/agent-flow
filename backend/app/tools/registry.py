"""Central registry mapping tool names to callables."""
from app.tools.web_search_tool import web_search
from app.tools.file_write_tool import write_file

TOOL_REGISTRY = {
    "web_search": web_search,
    "file_write": write_file,
}


def get_tool(name: str):
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown or unregistered tool: {name}")
    return TOOL_REGISTRY[name]
