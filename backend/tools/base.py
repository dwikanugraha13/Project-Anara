"""
base.py — Dynamic Tool Decorator & Reflection Schema Extractor for Project Anara.
Anara Standard tool reflection engine:
1. Automatically extracts OpenAPI/Gemini FunctionDeclaration JSON schema from
   standard Python type hints (inspect, typing, Pydantic).
2. Provides the @anara_tool decorator for effortless, zero-boilerplate tool registration.
3. Automatically maps parameter types, defaults, and docstrings.
"""

from __future__ import annotations

import functools
import inspect
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, get_args, get_origin, get_type_hints

logger = logging.getLogger(__name__)


def _map_py_type_to_json_schema(py_type: Any) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Maps Python types (str, int, float, bool, List, Dict, Optional) to Gemini/OpenAPI schema types."""
    origin = get_origin(py_type)
    args = get_args(py_type)

    if origin is Union:
        # Handles Optional[T] which is Union[T, type(None)]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _map_py_type_to_json_schema(non_none[0])
        return "STRING", None

    if py_type in (str, Optional[str]):
        return "STRING", None
    elif py_type in (int, Optional[int]):
        return "INTEGER", None
    elif py_type in (float, Optional[float]):
        return "NUMBER", None
    elif py_type in (bool, Optional[bool]):
        return "BOOLEAN", None
    elif py_type is list or origin in (list, List):
        item_type = "STRING"
        if args:
            item_t, _ = _map_py_type_to_json_schema(args[0])
            item_type = item_t
        return "ARRAY", {"type": item_type}
    elif py_type is dict or origin in (dict, Dict):
        return "OBJECT", None

    return "STRING", None


def extract_schema_from_callable(fn: Callable[..., Any], override_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Reflectively extracts function parameter schema from callable's type hints and docstrings.
    Compatible with Google GenAI FunctionDeclaration and OpenAI Tools schema.
    """
    if override_params:
        return override_params

    sig = inspect.signature(fn)
    hints = {}
    try:
        hints = get_type_hints(fn)
    except Exception:
        pass

    doc = inspect.getdoc(fn) or ""
    param_docs: Dict[str, str] = {}
    for line in doc.splitlines():
        m = re.match(r"^:(?:param|arg)\s+(\w+):\s*(.+)$", line.strip())
        if m:
            param_docs[m.group(1)] = m.group(2).strip()

    properties: Dict[str, Any] = {}
    required: List[str] = []

    for p_name, p in sig.parameters.items():
        if p_name in ("self", "cls"):
            continue

        p_type = hints.get(p_name, str)
        type_str, extra = _map_py_type_to_json_schema(p_type)

        p_dict: Dict[str, Any] = {"type": type_str}
        desc = param_docs.get(p_name, f"Parameter {p_name}")
        p_dict["description"] = desc

        if extra and "type" in extra:
            p_dict["items"] = {"type": extra["type"]}

        properties[p_name] = p_dict

        if p.default is inspect.Parameter.empty:
            required.append(p_name)

    schema: Dict[str, Any] = {
        "type": "OBJECT",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


def anara_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    risk: str = "mutating",
    toolset: str = "general",
    category: str = "system",
    icon: str = "terminal",
    parameters: Optional[Dict[str, Any]] = None,
    enabled_by_default: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for defining and auto-registering an Anara tool.
    Automatically extracts schema from type annotations and docstring if not explicitly provided.

    Example:
        @anara_tool(risk="read_only", category="exploration", icon="folder")
        async def inspect_directory(path: str, max_depth: int = 2) -> Dict[str, Any]:
            '''Inspects folder contents.
            :param path: The folder path to inspect
            :param max_depth: Maximum recursion depth
            '''
            ...
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = (name or fn.__name__).lstrip("_")
        raw_doc = inspect.getdoc(fn) or f"Tool {tool_name} for Project Anara."
        # Use first paragraph of docstring as description if not explicitly set
        doc_lines = [l.strip() for l in raw_doc.splitlines() if l.strip() and not l.strip().startswith(":")]
        tool_desc = description or (" ".join(doc_lines) if doc_lines else raw_doc)

        extracted_params = extract_schema_from_callable(fn, override_params=parameters)

        # Register dynamically into central ToolRegistry
        try:
            from tools.registry import registry
            registry.register_tool(
                name=tool_name,
                description=tool_desc,
                parameters=extracted_params,
                handler=fn,
                risk=risk,
                toolset=toolset,
                category=category,
                icon=icon,
                enabled_by_default=enabled_by_default,
            )
            logger.info(f"[AnaraTool] Auto-registered tool '@{tool_name}' ({risk}) via decorator.")
        except Exception as e:
            logger.debug(f"[AnaraTool] Registration deferred for '{tool_name}': {e}")

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        setattr(wrapper, "__anara_tool_name__", tool_name)
        setattr(wrapper, "__anara_tool_schema__", extracted_params)
        setattr(wrapper, "__anara_tool_risk__", risk)

        return wrapper

    return decorator
