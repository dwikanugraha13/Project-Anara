"""
catalog.py — Central Dynamic Tool Catalog & Execution Dispatcher for Project Anara.
Hermes Agent Parity:
1. Dynamic Tool Declarations & Risk Classification derived directly from ToolRegistry (Zero hardcoding).
2. Pure polymorphic dispatching via ToolRegistry.dispatch (Zero 200-line if-elif ladder).
3. Parameter normalization and output compaction (ContextMicroCompactor).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Set
from google.genai import types

import tools.tool_specs
from .registry import registry

logger = logging.getLogger("anara.tools.catalog")

# ── Dynamic Tool Declarations & Risk Classification (Zero Hardcode) ──
ANARA_FUNCTION_DECLARATIONS: List[types.FunctionDeclaration] = registry.get_all_declarations()
TOOL_RISK_CLASSIFICATION: Dict[str, str] = registry.get_risk_classification()

READ_ONLY_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "read_only"
}
ACTION_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "action"
}
MUTATING_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "mutating"
}
ASK_TOOL_NAMES = {
    name for name, risk in TOOL_RISK_CLASSIFICATION.items() if risk == "ask"
}


def get_tool_risk(tool_name: str) -> str:
    """Returns the risk tier of a given tool ('read_only', 'action', 'mutating', or 'ask')."""
    return registry.get_risk(tool_name)


def is_safe_read_only_cli_command(command: str) -> bool:
    """
    Validates if a CLI command in Plan Mode is purely for safe host/environment inspection
    using the unified Parameter-Aware AST Dissector in plan_detector.py (Hermes Parity).
    Zero duplicate regex lists or static keyword branches.
    """
    cmd = (command or "").strip()
    if not cmd:
        return False

    try:
        from core.plan_detector import evaluate_command_safety
        return evaluate_command_safety(cmd) == "read_only"
    except Exception:
        return False


def check_tool_permission(tool_name: str, mode: str = "plan", args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Anara Standard Permission Gate:
    Enforces 3-tier risk boundary (read_only, mutating, ask) programmatically at code level.
    """
    risk = get_tool_risk(tool_name)

    # Plan Mode Gate: strictly block mutating tools, permit safe read-only CLI inspection
    if mode == "plan":
        if tool_name == "execute_cli_command":
            cmd = (args or {}).get("command", "")
            if is_safe_read_only_cli_command(cmd):
                return {"allowed": True, "risk": "read_only"}
            return {
                "allowed": False,
                "risk": "mutating",
                "message": (
                    f"PERMISSION GATE DENIAL: Terminal command '{cmd}' is mutating and not permitted in Plan Mode. "
                    "Only safe read-only inspection commands (such as version checks, directory listing, environment probes) are allowed. "
                    "Propose this command in your structured plan for execution in Build Mode."
                )
            }
        if risk != "read_only":
            return {
                "allowed": False,
                "risk": risk,
                "message": (
                    f"PERMISSION GATE DENIAL: Tool '{tool_name}' ({risk}) cannot be executed in Plan Mode. "
                    "Plan Mode operates in Read-Only for exploration and architectural planning. "
                    "Incorporate this action into a structured implementation plan and request user approval."
                )
            }

    # Granular Risk Gate for 'ask' category tools (destructive commands, etc.)
    if tool_name == "execute_cli_command":
        cmd = (args or {}).get("command", "")
        from core.plan_detector import evaluate_command_safety
        cmd_risk = evaluate_command_safety(cmd)
        if cmd_risk == "ask":
            return {
                "allowed": False,
                "risk": "ask",
                "requires_prompt": True,
                "message": f"PERMISSION GATE ESCALATION: High-blast-radius system command '{cmd}' requires explicit user confirmation."
            }

    return {"allowed": True, "risk": risk}


def get_agent_tools(read_only: bool = False, enabled_set: Optional[Set[str]] = None) -> List[types.Tool]:
    """Returns dynamic agent tools formatted for Gemini API (Hermes Parity)."""
    decls = registry.get_all_declarations(read_only=read_only, enabled_set=enabled_set)
    return [types.Tool(function_declarations=decls)]


def _convert_to_standard_json_schema(val: Any) -> Any:
    """Recursively converts uppercase Gemini types (OBJECT, STRING, etc.) to lowercase OpenAPI types."""
    if isinstance(val, dict):
        res = {}
        for k, v in val.items():
            if k == "type" and isinstance(v, str):
                res[k] = v.lower()
            elif k == "properties" and isinstance(v, dict):
                # 'properties' is a mapping of property_name -> property_definition
                # Do NOT inject "type": "object" into the properties dictionary itself!
                res[k] = {
                    prop_name: _convert_to_standard_json_schema(prop_val)
                    for prop_name, prop_val in v.items()
                }
            else:
                res[k] = _convert_to_standard_json_schema(v)
        return res
    elif isinstance(val, list):
        return [_convert_to_standard_json_schema(x) for x in val]
    return val


def get_native_tools_anthropic(read_only: bool = False, enabled_set: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """Returns dynamic agent tools formatted for Anthropic Messages API (Claude Code Parity)."""
    tools = []
    for name, t in registry._tools.items():
        if enabled_set is not None and name not in enabled_set:
            continue
        if read_only and t.risk != "read_only":
            continue
        schema = _convert_to_standard_json_schema(t.parameters or {"type": "object", "properties": {}})
        tools.append({
            "name": t.name,
            "description": t.description or "",
            "input_schema": schema
        })
    return tools


def get_native_tools_openai(read_only: bool = False, enabled_set: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """Returns dynamic agent tools formatted for OpenAI / Codex / Custom Providers."""
    tools = []
    for name, t in registry._tools.items():
        if enabled_set is not None and name not in enabled_set:
            continue
        if read_only and t.risk != "read_only":
            continue
        schema = _convert_to_standard_json_schema(t.parameters or {"type": "object", "properties": {}})
        tools.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": schema
            }
        })
    return tools


def get_tools_catalog(enabled_set: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """Returns dynamic tools catalog from ToolRegistry for Web UI (Hermes Parity)."""
    return registry.get_tools_catalog(enabled_set=enabled_set)


def _get_tool_expected_params(name: str) -> List[str]:
    """Dynamically extracts expected parameter names from tool catalog declarations (Hermes Parity)."""
    canonical = registry.resolve_name(name)
    tool = registry.get_tool(canonical)
    if tool and tool.parameters and "properties" in tool.parameters:
        return list(tool.parameters["properties"].keys())
    return []


def _normalize_tool_args(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dynamically aligns LLM parameter variations to expected tool schema parameters (Hermes Parity).
    Uses fuzzy schema inspection and semantic stemming rather than hardcoded static lookup.
    """
    if not isinstance(args, dict):
        return {}
    a = dict(args)

    expected = _get_tool_expected_params(name)
    clean_incoming = {re.sub(r"[^a-z0-9]", "", k.lower()): (k, v) for k, v in args.items()}

    # 1. Dynamic fuzzy schema alignment
    for target in expected:
        if target in a and a[target]:
            continue
        clean_target = re.sub(r"[^a-z0-9]", "", target.lower())

        # Exact alphanumeric match (e.g. filepath -> file_path, cmd -> command)
        if clean_target in clean_incoming:
            orig_k, val = clean_incoming[clean_target]
            a[target] = val
            continue

        # Substring & semantic prefix/suffix match without cross-parameter collisions
        matched_val = None
        for clean_k, (orig_k, val) in clean_incoming.items():
            if orig_k not in expected and len(clean_k) >= 4:
                if clean_target.endswith(clean_k) or clean_target.startswith(clean_k):
                    matched_val = val
                    break
        if matched_val is not None:
            a[target] = matched_val

    # 2. Universal supplementary fallback for core tools
    if "file_path" in expected or name in ("read_local_file", "write_local_file", "edit_file", "delete_local_file"):
        if "file_path" not in a:
            for alias in ("path", "filePath", "target", "file"):
                if alias in a and isinstance(a[alias], str) and a[alias].strip():
                    a["file_path"] = a[alias].strip()
                    break

    if "pattern" in expected or name in ("grep_search_code", "glob_find_files"):
        if "pattern" not in a:
            for alias in ("query", "regex", "term", "keyword"):
                if alias in a and isinstance(a[alias], str) and a[alias].strip():
                    a["pattern"] = a[alias].strip()
                    break

    if "command" in expected or name in ("execute_cli_command", "terminal"):
        if "command" not in a:
            for alias in ("cmd", "script", "cli"):
                if alias in a and isinstance(a[alias], str) and a[alias].strip():
                    a["command"] = a[alias].strip()
                    break

    # 3. Numeric offsets
    for num_field in ("offset", "limit"):
        if num_field in a and a[num_field] is not None:
            try:
                a[num_field] = int(a[num_field])
            except (ValueError, TypeError):
                a[num_field] = None

    return a


async def _raw_dispatch_tool_call(
    name: str,
    args: Dict[str, Any],
    read_only: bool = False,
    mode: Optional[str] = None
) -> Dict[str, Any]:
    """Routes an incoming function_call dynamically via ToolRegistry (Zero if-elif ladder, Hermes Parity)."""
    args = _normalize_tool_args(name, args)
    canonical = registry.resolve_name(name)
    effective_mode = mode if mode else ("plan" if read_only else "build")
    logger.info(f"[AnaraAgent] Dispatching tool '{name}' (canonical={canonical}) with args: {args} (mode={effective_mode})")

    # ── Permission Gate 3-Tier Enforcement ──
    perm = check_tool_permission(canonical, mode=effective_mode, args=args)
    if not perm["allowed"]:
        logger.warning(f"[PermissionGate] Blocked execution of '{canonical}': {perm['message']}")
        return {
            "status": "error",
            "error_type": "permission_denied",
            "risk": perm.get("risk"),
            "message": perm["message"]
        }

    return await registry.dispatch(canonical, args)


async def dispatch_tool_call(
    name: str,
    args: Dict[str, Any],
    read_only: bool = False,
    mode: Optional[str] = None
) -> Dict[str, Any]:
    """
    Standard Anara Tool Dispatcher:
    Routes function_call to executor, sniffs error anchors via ContextMicroCompactor on failure,
    and enforces micro-compaction (40:60 Head:Tail + disk logging) on all outputs to protect LLM context windows.
    """
    raw_res = await _raw_dispatch_tool_call(name, args, read_only=read_only, mode=mode)
    if isinstance(raw_res, dict) and raw_res.get("status") == "error" and raw_res.get("output"):
        from tools.self_correction import ContextMicroCompactor
        raw_res["output"] = ContextMicroCompactor.compact_output(str(raw_res["output"]), max_lines=35, source_label=f"err_{name}")
    from tools.output_manager import compact_tool_payload
    return compact_tool_payload(raw_res, tool_name=name)


async def generate_text_response_with_tools(
    client: Any,
    model: str,
    user_prompt: str,
    system_instruction: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
    intercept_mutating_tools: bool = False,
    platform: Optional[str] = None,
) -> Any:
    """
    Unified ReAct turn delegator for Google Gemini model (Hermes Agent Parity).
    Routes all Gemini turns through the universal agent execution loop in providers/caller.py.
    """
    from providers.caller import call_universal_chat_model
    return await call_universal_chat_model(
        model_id=model,
        user_prompt=user_prompt,
        system_instruction=system_instruction,
        max_tokens=max_tokens,
        temperature=temperature,
        read_only=read_only,
        progress_cb=progress_cb,
        token_cb=token_cb,
        intercept_mutating_tools=intercept_mutating_tools,
        platform=platform,
    )
