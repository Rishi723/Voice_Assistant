"""
tools/executor.py
──────────────────
Receives the parsed intent dict from the classifier and dispatches
to the registered tool – no if/else chains, no switch statements.

Input contract:
    {
        "mode":      "tool",
        "tool":      "<registered_name>",
        "arguments": { ... }          # may be empty
    }

Returns True if the tool was found and called, False otherwise.
"""

from core import get_logger
from .registry import REGISTRY

log = get_logger(__name__)


def execute_tool(tool_name: str, arguments: dict) -> bool:
    """
    Look up *tool_name* in the registry and call it with **arguments.
    Returns True on success, False if the tool is unknown.
    """
    fn = REGISTRY.get(tool_name)
    if fn is None:
        log.warning("Unknown tool requested: '%s'", tool_name)
        return False

    try:
        fn(**arguments)
        return True
    except TypeError as exc:
        log.error("Tool '%s' argument error: %s | args=%s", tool_name, exc, arguments)
        return False
    except Exception:
        log.exception("Tool '%s' raised an unexpected exception", tool_name)
        return False
