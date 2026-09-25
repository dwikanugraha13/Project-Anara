"""
registry.py — Decentralized Tool Registry Engine for Project Anara.
Anara Standard tools/registry.py:
1. Decentralized self-registration for every tool (Zero if-elif ladder).
2. Dynamic FunctionDeclaration generation for Gemini / OpenAI / Anthropic models.
3. Automated risk taxonomy mapping (read_only, action, mutating, ask).
4. Dynamic toolset membership mapping.
"""

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from google.genai import types

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Represents a registered Anara tool with execution handler, schema, and security metadata."""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    risk: str = "mutating"  # 'read_only', 'action', 'mutating', 'ask'
    toolset: str = "general"
    category: str = "system"  # 'coding', 'exploration', 'multimedia', 'system', 'intelligence', 'connectivity'
    icon: str = "terminal"
    enabled_by_default: bool = True
    declaration: Optional[types.FunctionDeclaration] = None


class ToolRegistry:
    """Central dynamic registry managing tool definitions, handlers, and schema generation."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._aliases: Dict[str, str] = {}

    def register_alias(self, alias_name: str, target_name: str):
        """Registers a backward-compatible alias for an existing tool."""
        self._aliases[alias_name] = target_name

    def resolve_name(self, name: str) -> str:
        """Resolves alias to canonical tool name."""
        return self._aliases.get(name, name)

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        risk: str = "mutating",
        toolset: str = "general",
        category: str = "system",
        icon: str = "terminal",
        enabled_by_default: bool = True
    ):
        """Decorator or direct method to register a tool with its handler and metadata."""
        def decorator(fn: Callable[..., Any]):
            decl = types.FunctionDeclaration(
                name=name,
                description=description,
                parameters=parameters
            )
            tool_def = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                handler=fn,
                risk=risk,
                toolset=toolset,
                category=category,
                icon=icon,
                enabled_by_default=enabled_by_default,
                declaration=decl
            )
            self._tools[name] = tool_def
            return fn

        return decorator

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[..., Any],
        risk: str = "mutating",
        toolset: str = "general",
        category: str = "system",
        icon: str = "terminal",
        enabled_by_default: bool = True
    ):
        """Direct registration function without decorator."""
        decl = types.FunctionDeclaration(
            name=name,
            description=description,
            parameters=parameters
        )
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            risk=risk,
            toolset=toolset,
            category=category,
            icon=icon,
            enabled_by_default=enabled_by_default,
            declaration=decl
        )

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        canonical = self.resolve_name(name)
        return self._tools.get(canonical)

    def get_handler(self, name: str) -> Optional[Callable[..., Any]]:
        tool = self.get_tool(name)
        return tool.handler if tool else None

    def get_risk(self, name: str) -> str:
        tool = self.get_tool(name)
        return tool.risk if tool else "mutating"

    def get_all_declarations(self, read_only: bool = False, enabled_set: Optional[Set[str]] = None) -> List[types.FunctionDeclaration]:
        """Returns types.FunctionDeclaration for all active tools, filtered by mode."""
        decls = []
        for name, t in self._tools.items():
            if enabled_set is not None and name not in enabled_set:
                continue
            if read_only and t.risk != "read_only":
                continue
            if t.declaration:
                decls.append(t.declaration)
        return decls

    def get_risk_classification(self) -> Dict[str, str]:
        """Returns dictionary of tool_name -> risk_tier ('read_only', 'action', 'mutating', 'ask')."""
        return {name: t.risk for name, t in self._tools.items()}

    def get_tools_catalog(self, enabled_set: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
        """Returns serializable JSON catalog of all registered tools for the Web UI."""
        catalog = []
        for name, t in self._tools.items():
            is_ro = (t.risk == "read_only")
            catalog.append({
                "name": name,
                "description": t.description,
                "category": t.category,
                "icon": t.icon,
                "risk": t.risk,
                "is_read_only": is_ro,
                "mode_label": "Plan & Build" if is_ro else "Build Only",
                "toolset_id": t.toolset,
                "toolset_title": t.toolset.replace("_", " ").title(),
                "is_enabled": name in enabled_set if enabled_set else True,
                "parameters": t.parameters
            })
        return catalog

    def get_toolsets_mapping(self) -> Dict[str, List[str]]:
        """Returns dynamic mapping of toolset_id -> list of tool names."""
        mapping: Dict[str, List[str]] = {}
        for name, t in self._tools.items():
            mapping.setdefault(t.toolset, []).append(name)
        return mapping

    async def dispatch(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool by looking up its handler dynamically (Zero if-elif ladder)."""
        tool = self.get_tool(name)
        if not tool:
            return {"status": "error", "message": f"Tool '{name}' is not registered."}

        fn = tool.handler
        try:
            res = fn(**args)
            if inspect.isawaitable(res):
                return await res
            return res
        except TypeError as te:
            # Handle possible extra/missing kwargs
            try:
                sig = inspect.signature(fn)
                valid_args = {k: v for k, v in args.items() if k in sig.parameters}
                res = fn(**valid_args)
                if inspect.isawaitable(res):
                    return await res
                return res
            except Exception as e:
                logger.error(f"[ToolRegistry] Error calling {name}: {e}")
                return {"status": "error", "message": f"Tool call error for '{name}': {str(e)}"}
        except Exception as e:
            logger.error(f"[ToolRegistry] Execution error in {name}: {e}", exc_info=True)
            return {"status": "error", "message": f"Error in tool {name}: {str(e)}"}


# Global singleton registry instance
registry = ToolRegistry()
