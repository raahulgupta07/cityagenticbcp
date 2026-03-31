"""
Tool registry — @tool decorator for registering agent tools.
"""
import json
import functools
import pandas as pd

_TOOL_SCHEMAS = []
_TOOL_FUNCTIONS = {}


def tool(name, description, parameters=None):
    """Decorator to register a function as an agent tool."""
    def decorator(func):
        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters or {"type": "object", "properties": {}},
            }
        }
        _TOOL_SCHEMAS.append(schema)
        _TOOL_FUNCTIONS[name] = func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_all_tools():
    """Return (schemas, functions) for all registered tools."""
    return _TOOL_SCHEMAS, _TOOL_FUNCTIONS


def get_tool_schemas():
    return _TOOL_SCHEMAS


def execute_tool(name, args):
    """Execute a tool by name with given arguments."""
    func = _TOOL_FUNCTIONS.get(name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        if isinstance(args, str):
            args = json.loads(args)
        result = func(**args)
        return _serialize(result)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _serialize(result):
    """Serialize a tool result to JSON string."""
    if isinstance(result, pd.DataFrame):
        if len(result) > 30:
            result = result.head(30)
        return result.to_json(orient="records", indent=2)
    if isinstance(result, dict):
        # Handle DataFrames nested in dicts
        cleaned = {}
        for k, v in result.items():
            if isinstance(v, pd.DataFrame):
                cleaned[k] = v.head(20).to_dict(orient="records") if len(v) > 0 else []
            else:
                cleaned[k] = v
        return json.dumps(cleaned, default=str, indent=2)
    if isinstance(result, (list, tuple)):
        return json.dumps(result, default=str, indent=2)
    return json.dumps({"result": str(result)}, default=str)
