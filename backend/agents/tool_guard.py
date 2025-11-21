# backend/common/tool_guard.py
from functools import wraps

_seen_tool_calls = set()


def guard_tool(tool_name):
    def decorator(func):
        @wraps(func)
        def wrapper(input=None):
            key = (tool_name, str(input))
            if key in _seen_tool_calls:
                return f"[SKIPPED] Duplicate tool call: {tool_name} with {input}"
            _seen_tool_calls.add(key)
            return func(input)
        return wrapper
    return decorator
