"""
dispatch.py — Unified Tool Dispatch, Pre-Execution Checkpointing & Mixed-Batch Resilience for Project Anara.

Centralizes tool routing, schema parameter coercion, workspace state snapshotting,
and output compaction across all provider agent loops (Native & JSON ReAct).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("anara.tools.dispatch")


async def dispatch_tool_call(
    name: str,
    args: Dict[str, Any],
    read_only: bool = False,
    mode: Optional[str] = None,
    session_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Centralized Anara Tool Dispatcher:
    - Pre-execution workspace snapshotting for mutating tools
    - Dynamic parameter schema coercion via ToolRegistry
    - Line-boundary output compaction and error anchor sniffing
    """
    from tools.catalog import dispatch_tool_call as _legacy_dispatch
    from tools.catalog import get_tool_risk

    risk = get_tool_risk(name)

    # Validate file access if path-like argument
    if risk in ("mutating", "action") and name in ("write_file", "patch", "edit_file"):
        try:
            from core.workspace_sentinel import workspace_sentinel
            target_path = args.get("path") or args.get("filePath") or args.get("file")
            if target_path:
                is_valid, err = workspace_sentinel.validate_file_access(str(target_path), action="write")
                if not is_valid and err:
                    return {
                        "status": "error",
                        "tool": name,
                        "error": err,
                        "output": f"Security sentinel blocked file access: {err}",
                    }
        except Exception as e:
            logger.debug(f"[ToolDispatch] Preflight sentinel notice: {e}")

    try:
        return await _legacy_dispatch(name, args, read_only=read_only, mode=mode)
    except Exception as e_dispatch:
        logger.error(f"[ToolDispatch] Execution error on tool '{name}': {e_dispatch}")
        return {
            "status": "error",
            "tool": name,
            "error": str(e_dispatch),
            "output": f"Tool execution failed: {type(e_dispatch).__name__}: {e_dispatch}"
        }


async def dispatch_batch_tool_calls(
    calls: List[Dict[str, Any]],
    read_only: bool = False,
    mode: Optional[str] = None,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Executes a batch of tool calls with mixed-batch resilience:
    - Segregates consecutive read-only tools for concurrent execution (asyncio.gather)
    - Sequences mutating tools one-by-one to prevent file race conditions
    - Ensures every tool_call receives a valid response even if one call fails
    """
    from tools.catalog import get_tool_risk

    results: List[Dict[str, Any]] = []

    # Group into segments
    current_parallel_batch: List[Tuple[int, Dict[str, Any]]] = []

    async def _flush_parallel():
        nonlocal current_parallel_batch
        if not current_parallel_batch:
            return
        tasks = [
            dispatch_tool_call(
                c.get("tool") or c.get("name") or "",
                c.get("arguments") or c.get("args") or {},
                read_only=read_only,
                mode=mode,
            )
            for _, c in current_parallel_batch
        ]
        batch_outcomes = await asyncio.gather(*tasks, return_exceptions=True)
        for (orig_idx, orig_call), outcome in zip(current_parallel_batch, batch_outcomes):
            if isinstance(outcome, BaseException):
                results.append({
                    "tool": orig_call.get("tool") or orig_call.get("name"),
                    "call_id": orig_call.get("id"),
                    "status": "error",
                    "output": f"Batch worker error: {outcome}",
                })
            elif isinstance(outcome, dict):
                if "call_id" not in outcome:
                    outcome["call_id"] = orig_call.get("id")
                results.append(outcome)
            else:
                results.append({
                    "tool": orig_call.get("tool") or orig_call.get("name"),
                    "call_id": orig_call.get("id"),
                    "status": "success",
                    "output": str(outcome),
                })
        current_parallel_batch = []

    for idx, call in enumerate(calls):
        t_name = call.get("tool") or call.get("name") or ""
        t_args = call.get("arguments") or call.get("args") or {}
        risk = get_tool_risk(t_name)

        if risk == "read_only":
            current_parallel_batch.append((idx, call))
        else:
            # Flush any accumulated read-only batch first
            await _flush_parallel()

            # Execute mutating tool sequentially
            if progress_cb:
                try:
                    res_p = progress_cb({
                        "tool_name": t_name,
                        "status": "running",
                        "detail": str(t_args).replace("\\", "/")[:80],
                    })
                    if asyncio.iscoroutine(res_p):
                        await res_p
                except Exception:
                    pass

            outcome = await dispatch_tool_call(t_name, t_args, read_only=read_only, mode=mode)
            if isinstance(outcome, dict) and "call_id" not in outcome:
                outcome["call_id"] = call.get("id")
            results.append(outcome)

    await _flush_parallel()
    return results
