"""
computer_use_tool.py — Top-level discovery shim for tools.computer_use package.
Hermes Agent Parity (tools/computer_use_tool.py).
Delegates all desktop automation to native cua-driver with closed-loop verification.
"""
from typing import Any, Dict, List, Optional, Tuple

from .computer_use import (
    COMPUTER_USE_SCHEMA,
    handle_computer_use,
    dispatch_computer_use,
    resolve_cua_driver_cmd,
    is_cua_driver_available,
    install_cua_driver,
    run_cua_call,
    execute_capture,
    execute_list_windows,
    execute_focus_app,
    execute_type,
    execute_key,
    execute_click,
    execute_send_text,
)
from .computer_use.executor import _get_screen_metrics, _get_cursor_pos


async def _tool_computer_use(
    action: str = "capture",
    coordinate: Optional[Tuple[int, int]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    text: Optional[str] = None,
    key: Optional[str] = None,
    keys: Optional[str] = None,
    button: str = "left",
    duration: float = 0.5,
    amount: int = 120,
    app: Optional[str] = None,
    pid: Optional[int] = None,
    window_id: Optional[int] = None,
    capture_after: Optional[bool] = None,
    submit: Optional[bool] = None,
    enter: Optional[bool] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Unified handler forwarding all computer_use calls to the native Cua driver engine."""
    norm_action = str(action or "capture").strip().lower()
    effective_capture = capture_after if capture_after is not None else (
        True if norm_action in ("send_text", "type", "click", "key", "submit_text") else False
    )
    args = {
        "action": action,
        "coordinate": coordinate,
        "x": x,
        "y": y,
        "text": text,
        "key": key or keys,
        "keys": keys or key,
        "button": button,
        "duration": duration,
        "amount": amount,
        "app": app,
        "pid": pid,
        "window_id": window_id,
        "capture_after": effective_capture,
        **kwargs,
    }
    if submit is not None:
        args["submit"] = submit
    if enter is not None:
        args["enter"] = enter
    return await handle_computer_use(args)


async def _tool_take_screenshot(title: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    """Dedicated screenshot convenience tool alias."""
    return await execute_capture(text=title, mode="vision")


def _focus_desktop_window(target: str) -> Tuple[bool, str]:
    """Synchronous focus helper for backward compatibility."""
    import asyncio
    try:
        res = asyncio.run(execute_focus_app(target))
        return (res.get("status") == "success", res.get("message", ""))
    except Exception as e:
        return False, str(e)


__all__ = [
    "_tool_computer_use",
    "_tool_take_screenshot",
    "_get_screen_metrics",
    "_get_cursor_pos",
    "_focus_desktop_window",
    "handle_computer_use",
    "COMPUTER_USE_SCHEMA",
    "resolve_cua_driver_cmd",
    "is_cua_driver_available",
    "install_cua_driver",
]
