"""
computer_use package — Universal OS Desktop Control via cua-driver.
Hermes Agent Parity.
"""
from typing import Any, Dict

from .schema import COMPUTER_USE_SCHEMA, get_computer_use_schema
from .driver import resolve_cua_driver_cmd, is_cua_driver_available, install_cua_driver, run_cua_call
from .executor import (
    dispatch_computer_use,
    execute_capture,
    execute_list_windows,
    execute_focus_app,
    execute_type,
    execute_key,
    execute_click,
    execute_send_text,
)


async def handle_computer_use(args: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    """Top-level handler for computer_use tool invocations."""
    return await dispatch_computer_use(args, **kwargs)


__all__ = [
    "COMPUTER_USE_SCHEMA",
    "get_computer_use_schema",
    "resolve_cua_driver_cmd",
    "is_cua_driver_available",
    "install_cua_driver",
    "run_cua_call",
    "handle_computer_use",
    "dispatch_computer_use",
    "execute_capture",
    "execute_list_windows",
    "execute_focus_app",
    "execute_type",
    "execute_key",
    "execute_click",
    "execute_send_text",
]
