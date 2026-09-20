"""
computer_use_tool.py — OS Desktop Control & Vision Automation for Project Anara.
Anara Standard computer_use (CUA): allows Anara to capture the screen,
move/click the mouse, drag elements, and type/press keys at the OS level on Windows.
"""

import asyncio
import ctypes
from ctypes import wintypes
import hashlib
import logging
import os
import re
import shutil
import subprocess
import time
from typing import Any, Dict, Optional, Tuple
from PIL import ImageGrab

from .events import _emit_agent_event
from constants import get_anara_staging_dir

logger = logging.getLogger(__name__)

STAGING_DIR = str(get_anara_staging_dir("screenshots"))
os.makedirs(STAGING_DIR, exist_ok=True)

# Windows mouse_event flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800

# Virtual Key Codes
VK_CODES = {
    "enter": 0x0D,
    "return": 0x0D,
    "escape": 0x1B,
    "esc": 0x1B,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "win": 0x5B,
    "windows": 0x5B,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B
}


def _get_screen_metrics() -> Tuple[int, int, int, int]:
    """Returns the virtual screen coordinates and dimensions (vx, vy, width, height) in pixels (Hermes Standard)."""
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if not user32:
        return 0, 0, 1920, 1080
    try:
        # SM_XVIRTUALSCREEN = 76, SM_YVIRTUALSCREEN = 77
        # SM_CXVIRTUALSCREEN = 78, SM_CYVIRTUALSCREEN = 79
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)
        if vw > 0 and vh > 0:
            return vx, vy, vw, vh
        # Fallback to primary monitor metrics (0, 1)
        w = user32.GetSystemMetrics(0) or 1920
        h = user32.GetSystemMetrics(1) or 1080
        return 0, 0, w, h
    except Exception:
        return 0, 0, 1920, 1080


def _get_cursor_pos() -> Tuple[int, int]:
    """Returns current mouse cursor (x, y) coordinates."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def _focus_desktop_window(target: str) -> Tuple[bool, str]:
    """Finds and brings any running window matching the target title to the foreground (Pure OS Primitive)."""
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if not user32:
        return False, "Otomasi jendela hanya didukung di sistem operasi Windows."

    clean_target = target.strip().lower()
    matches = []

    def enum_windows_proc(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if clean_target in title.lower():
                    matches.append((hwnd, title))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)

    if not matches:
        return False, f"Window matching '{target}' was not found among active applications."

    best_hwnd, best_title = matches[0]
    try:
        user32.ShowWindow(best_hwnd, 9)  # SW_RESTORE = 9
        user32.SetForegroundWindow(best_hwnd)
        return True, f"Window '{best_title}' brought to front."
    except Exception as e:
        return False, f"Gagal membawa jendela '{best_title}' ke depan: {e}"


async def _tool_computer_use(
    action: str,
    coordinate: Optional[Tuple[int, int]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    text: Optional[str] = None,
    key: Optional[str] = None,
    button: str = "left",
    duration: float = 0.5,
    amount: int = 120,
    app: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Direct OS desktop automation (Mouse, Keyboard, Screen Capture, Window Control).
    Actions:
    - 'screenshot' / 'capture': Captures full monitor screenshot and projects to HUD.
    - 'launch_app' / 'open': Launches any desktop application dynamically.
    - 'focus_app' / 'activate_window': Brings a running window to foreground.
    - 'mouse_click': Clicks at coordinates (x, y). button: 'left', 'right', 'double'.
    - 'mouse_move': Moves cursor to (x, y).
    - 'mouse_drag': Drags from current position to (x, y).
    - 'scroll': Scrolls mouse wheel up (positive) or down (negative).
    - 'keyboard_type': Types given text string into the active window.
    - 'keyboard_press': Presses a specific key (e.g. 'enter', 'escape', 'win', 'tab').
    - 'hotkey': Presses key combinations (e.g. 'ctrl+c', 'alt+tab', 'win+r', 'ctrl+enter').
    - 'wait': Pauses for specified duration seconds.
    - 'screen_info': Returns screen resolution and current cursor position.
    """
    act = (action or "screenshot").strip().lower()
    vx, vy, screen_w, screen_h = _get_screen_metrics()

    # Resolve target coordinate
    target_x = x
    target_y = y
    if coordinate and len(coordinate) >= 2:
        target_x, target_y = coordinate[0], coordinate[1]

    action_target_desc = f"at ({target_x}, {target_y})" if target_x is not None else (app or text or key or "")
    _emit_agent_event("agent_action_start", {
        "tool_name": "computer_use",
        "action_title": f"Computer Use ({act.upper()})",
        "detail": action_target_desc,
        "icon": "monitor"
    })

    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)

    # 1. SCREENSHOT / CAPTURE (Hermes CUA Parity)
    if act in ("screenshot", "screen", "capture"):
        try:
            im = ImageGrab.grab(all_screens=True)
            timestamp = int(time.time())
            filename = f"screen_{timestamp}.png"
            filepath = os.path.join(STAGING_DIR, filename)
            im.save(filepath, "PNG")

            # Dynamic Turn Artifact Registration for Multi-Channel Auto-Dispatch (Hermes Parity)
            from tools.artifact_tools import register_turn_artifact
            register_turn_artifact(filepath, filename, mime_type="image/png")

            title_text = text or f"Tangkapan Layar Desktop ({im.width}x{im.height})"
            _emit_agent_event("hud_project", {
                "type": "screenshot",
                "title": title_text,
                "local_path": filepath,
                "width": im.width,
                "height": im.height
            })

            cur_x, cur_y = _get_cursor_pos()
            return {
                "status": "success",
                "action": "capture",
                "image_path": filepath,
                "screenshot_path": filepath,
                "screen_width": im.width,
                "screen_height": im.height,
                "cursor_pos": {"x": cur_x, "y": cur_y},
                "message": f"Desktop screenshot captured successfully ({im.width}x{im.height}px)."
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to capture screenshot: {e}"}

    # 2. SCREEN INFO
    elif act == "screen_info":
        cur_x, cur_y = _get_cursor_pos()
        return {
            "status": "success",
            "virtual_x": vx,
            "virtual_y": vy,
            "screen_width": screen_w,
            "screen_height": screen_h,
            "cursor_pos": {"x": cur_x, "y": cur_y}
        }

    # 3. MOUSE MOVE
    elif act in ("mouse_move", "move"):
        if not user32:
            return {"status": "error", "message": "Mouse automation only supported on Windows."}
        if target_x is None or target_y is None:
            return {"status": "error", "message": "Parameters x and y are required for mouse_move."}
        clamped_x = max(vx, min(vx + screen_w - 1, int(target_x)))
        clamped_y = max(vy, min(vy + screen_h - 1, int(target_y)))
        user32.SetCursorPos(clamped_x, clamped_y)
        return {
            "status": "success",
            "action": "mouse_move",
            "target": {"x": clamped_x, "y": clamped_y},
            "message": f"Cursor moved to ({clamped_x}, {clamped_y})."
        }

    # 4. MOUSE CLICK
    elif act in ("mouse_click", "click"):
        if not user32:
            return {"status": "error", "message": "Mouse automation only supported on Windows."}
        if target_x is not None and target_y is not None:
            clamped_x = max(vx, min(vx + screen_w - 1, int(target_x)))
            clamped_y = max(vy, min(vy + screen_h - 1, int(target_y)))
            user32.SetCursorPos(clamped_x, clamped_y)
            await asyncio.sleep(0.05)
        else:
            clamped_x, clamped_y = _get_cursor_pos()

        btn = (button or "left").lower()
        if btn == "right":
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            await asyncio.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        elif btn in ("double", "dblclick"):
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            await asyncio.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        else:
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            await asyncio.sleep(0.02)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        return {
            "status": "success",
            "action": "mouse_click",
            "button": btn,
            "clicked_at": {"x": clamped_x, "y": clamped_y},
            "message": f"{btn.title()} click executed at ({clamped_x}, {clamped_y})."
        }

    # 5. MOUSE DRAG
    elif act in ("mouse_drag", "drag"):
        if not user32:
            return {"status": "error", "message": "Mouse automation only supported on Windows."}
        if target_x is None or target_y is None:
            return {"status": "error", "message": "Target coordinates (x, y) required for mouse_drag."}
        clamped_x = max(vx, min(vx + screen_w - 1, int(target_x)))
        clamped_y = max(vy, min(vy + screen_h - 1, int(target_y)))

        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        await asyncio.sleep(0.1)
        user32.SetCursorPos(clamped_x, clamped_y)
        await asyncio.sleep(0.1)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        return {
            "status": "success",
            "action": "mouse_drag",
            "dragged_to": {"x": clamped_x, "y": clamped_y},
            "message": f"Mouse dragged to ({clamped_x}, {clamped_y})."
        }

    # 6. KEYBOARD TYPE
    elif act in ("keyboard_type", "type"):
        if not text:
            return {"status": "error", "message": "Parameter 'text' is required for keyboard_type."}

        # SendInput via unicode characters
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_ulong)
            ]

        class INPUT(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.DWORD),
                ("ki", KEYBDINPUT),
                ("padding", ctypes.c_ubyte * 8)
            ]

        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        for ch in text:
            code = ord(ch)
            # Press down
            inp_down = INPUT(type=1, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))
            user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
            # Press up
            inp_up = INPUT(type=1, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))
            user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
            await asyncio.sleep(0.01)

        return {
            "status": "success",
            "action": "keyboard_type",
            "typed_chars": len(text),
            "message": f"Text typed successfully to active window ({len(text)} characters)."
        }

    # 7. KEYBOARD PRESS
    elif act in ("keyboard_press", "press_key", "key"):
        if not key:
            return {"status": "error", "message": "Parameter 'key' wajib diisi untuk keyboard_press."}
        clean_k = key.strip().lower()
        vk = VK_CODES.get(clean_k)
        if not vk and len(clean_k) == 1:
            vk = ord(clean_k.upper())

        if not vk:
            return {"status": "error", "message": f"Tombol '{key}' tidak dikenali dalam daftar virtual key."}

        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(vk, 0, 0, 0)
        await asyncio.sleep(0.03)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

        return {
            "status": "success",
            "action": "keyboard_press",
            "key": clean_k,
            "message": f"Key '{clean_k}' pressed successfully."
        }

    # 8. HOTKEY / COMBINATION
    elif act in ("hotkey", "press_hotkey", "combo"):
        combo = (key or text or "").strip().lower()
        if not combo:
            return {"status": "error", "message": "Parameter 'key' required for hotkey (e.g. 'ctrl+enter', 'alt+tab', 'win+r')."}

        parts = [p.strip() for p in re.split(r"[+\s]", combo) if p.strip()]
        down_vks = []
        for part in parts:
            vk = VK_CODES.get(part)
            if not vk and len(part) == 1:
                vk = ord(part.upper())
            if vk:
                user32.keybd_event(vk, 0, 0, 0)
                down_vks.append(vk)
                await asyncio.sleep(0.02)

        await asyncio.sleep(0.05)
        for vk in reversed(down_vks):
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            await asyncio.sleep(0.02)

        return {
            "status": "success",
            "action": "hotkey",
            "combo": combo,
            "message": f"Key combination '{combo}' pressed successfully."
        }

    # 9. SCROLL
    elif act in ("scroll", "wheel"):
        if not user32:
            return {"status": "error", "message": "Otomasi mouse hanya didukung di Windows."}
        scroll_amt = int(amount if amount is not None else 120)
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, scroll_amt, 0)
        return {
            "status": "success",
            "action": "scroll",
            "amount": scroll_amt,
            "message": f"Mouse wheel di-scroll sebesar {scroll_amt} unit."
        }

    # 10. FOCUS APP / WINDOW
    elif act in ("focus_app", "activate_window", "focus"):
        app_target = (app or text or key or kwargs.get("target") or "").strip()
        if not app_target:
            return {"status": "error", "message": "Parameter 'text' atau 'app' berisi nama jendela aplikasi yang akan difokuskan wajib diisi."}
        ok, msg = _focus_desktop_window(app_target)
        await asyncio.sleep(0.3)
        return {
            "status": "success" if ok else "error",
            "action": "focus_app",
            "app": app_target,
            "message": msg
        }

    # 11. WAIT
    elif act in ("wait", "sleep"):
        wait_s = float(duration or 1.0)
        await asyncio.sleep(min(15.0, max(0.05, wait_s)))
        return {
            "status": "success",
            "action": "wait",
            "duration": wait_s,
            "message": f"Menunggu selama {wait_s} detik."
        }

    return {
        "status": "error",
        "message": f"Aksi '{act}' tidak dikenal. Pilih dari aksi murni CUA: 'screenshot', 'focus_app', 'mouse_click', 'mouse_move', 'mouse_drag', 'scroll', 'keyboard_type', 'keyboard_press', 'hotkey', 'wait', 'screen_info'."
    }
