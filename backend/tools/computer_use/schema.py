"""
schema.py — Universal model-facing schema for computer_use tool.
Hermes Agent Parity (tools/computer_use/schema.py).
"""
from typing import Any, Dict

_PROPERTIES: Dict[str, Any] = {
    "action": {
        "type": "STRING",
        "enum": [
            "send_text",
            "launch_app",
            "capture",
            "click",
            "double_click",
            "right_click",
            "middle_click",
            "drag",
            "scroll",
            "type",
            "key",
            "set_value",
            "wait",
            "list_apps",
            "list_windows",
            "focus_app",
        ],
        "description": (
            "Action to execute (Hermes & CUA Parity). "
            "'capture' (captures desktop screenshot and visual UI element tree). "
            "'click', 'double_click', 'right_click' (clicks on screen coordinates [x, y] or element index to focus input fields or click buttons). "
            "'type' (types text into the currently active/focused input field). "
            "'key' (presses key or hotkeys, e.g. Return, Enter, Tab, Escape, ctrl+c). "
            "'focus_app' (brings target window to the foreground). "
            "'send_text' (convenience 1-step focus, input targeting, clipboard typing, and Enter submission). "
            "'launch_app' (launches an application by name and waits for its window). "
            "'list_windows' and 'list_apps' (inspect active windows or installed apps). "
            "'scroll' (scrolls page up/down). 'drag' (drags from coordinate to coordinate)."
        ),
    },
    "mode": {
        "type": "STRING",
        "enum": ["som", "vision", "ax"],
        "description": "Capture mode. 'som' (Set-of-Marks with numbered overlays), 'vision' (plain screenshot), 'ax' (accessibility tree only).",
    },
    "app": {
        "type": "STRING",
        "description": "Optional target application name or window title to focus or capture (e.g. 'Code', 'Telegram', 'Brave', 'Terminal').",
    },
    "pid": {
        "type": "INTEGER",
        "description": "Optional process ID (PID) of the target application.",
    },
    "window_id": {
        "type": "INTEGER",
        "description": "Optional native window handle (HWND on Windows).",
    },
    "element": {
        "type": "INTEGER",
        "description": "1-based element index from the last capture(mode='som') or accessibility tree walk.",
    },
    "coordinate": {
        "type": "ARRAY",
        "items": {"type": "INTEGER"},
        "description": "Pixel coordinates [x, y] on the screen (top-left origin).",
    },
    "button": {
        "type": "STRING",
        "enum": ["left", "right", "middle"],
        "description": "Mouse button for click action (default 'left').",
    },
    "modifiers": {
        "type": "ARRAY",
        "items": {"type": "STRING"},
        "description": "Modifier keys held during the action ('ctrl', 'alt', 'shift', 'win').",
    },
    "text": {
        "type": "STRING",
        "description": "Text string to type into the target window or element.",
    },
    "keys": {
        "type": "STRING",
        "description": "Key or hotkey combination to press (e.g. 'return', 'enter', 'escape', 'tab', 'ctrl+c', 'win+r').",
    },
    "key": {
        "type": "STRING",
        "description": "Alias for keys parameter.",
    },
    "duration": {
        "type": "NUMBER",
        "description": "Duration or pause in seconds.",
    },
    "amount": {
        "type": "INTEGER",
        "description": "Scroll wheel amount or step ticks (default 3).",
    },
    "direction": {
        "type": "STRING",
        "enum": ["up", "down", "left", "right"],
        "description": "Scroll direction (default 'down').",
    },
    "delivery_mode": {
        "type": "STRING",
        "enum": ["background", "foreground"],
        "description": "'background' (default) sends input directly without stealing focus. 'foreground' brings the window to front first.",
    },
    "bring_to_front": {
        "type": "BOOLEAN",
        "description": "Explicitly bring the target window to the OS foreground before executing input.",
    },
    "capture_after": {
        "type": "BOOLEAN",
        "description": "Automatically take a follow-up screenshot after the action to visually verify its outcome.",
    },
    "submit": {
        "type": "BOOLEAN",
        "description": "Whether to submit with Enter key (default true for send_text).",
    },
    "enter": {
        "type": "BOOLEAN",
        "description": "Whether to press Enter/Return key immediately after typing (default true for send_text).",
    },
    "x": {
        "type": "INTEGER",
        "description": "Optional physical screen X pixel coordinate to click or target before typing.",
    },
    "y": {
        "type": "INTEGER",
        "description": "Optional physical screen Y pixel coordinate to click or target before typing.",
    },
}

COMPUTER_USE_SCHEMA: Dict[str, Any] = {
    "name": "computer_use",
    "description": (
        "Universal desktop control via cua-driver (Windows, macOS, Linux). "
        "Allows the agent to capture screenshots, inspect active windows, move/click the mouse, "
        "type text, press hotkeys, and automate host OS applications. "
        "Background-first delivery: input can be routed directly to target windows without stealing cursor focus. "
        "Supports window targeting and post-action visual verification via capture_after=true."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": _PROPERTIES,
        "required": ["action"],
    },
}


def get_computer_use_schema() -> Dict[str, Any]:
    """Returns OpenAI/Gemini compatible tool definition dictionary."""
    return COMPUTER_USE_SCHEMA
