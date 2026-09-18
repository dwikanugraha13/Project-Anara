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
import time
from typing import Any, Dict, Optional, Tuple
from PIL import ImageGrab

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

STAGING_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "staging", "screenshots")
os.makedirs(STAGING_DIR, exist_ok=True)

# Windows mouse_event flags
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

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
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f11": 0x7A,
    "f12": 0x7B
}


def _get_screen_metrics() -> Tuple[int, int]:
    """Returns the primary monitor (width, height) in pixels."""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _get_cursor_pos() -> Tuple[int, int]:
    """Returns current mouse cursor (x, y) coordinates."""
    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


async def _tool_computer_use(
    action: str,
    coordinate: Optional[Tuple[int, int]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    text: Optional[str] = None,
    key: Optional[str] = None,
    button: str = "left",
    duration: float = 0.5
) -> Dict[str, Any]:
    """
    Direct OS desktop automation (Mouse, Keyboard, Screen Capture).
    Actions:
    - 'screenshot': Captures full monitor screenshot and projects to HUD.
    - 'mouse_click': Clicks at coordinates (x, y). button: 'left', 'right', 'double'.
    - 'mouse_move': Moves cursor to (x, y).
    - 'mouse_drag': Drags from current position to (x, y).
    - 'keyboard_type': Types given text string into the active window.
    - 'keyboard_press': Presses a specific key (e.g. 'enter', 'escape', 'win', 'tab').
    - 'screen_info': Returns screen resolution and current cursor position.
    """
    act = (action or "screenshot").strip().lower()
    vx, vy, screen_w, screen_h = _get_screen_metrics()

    # Resolve target coordinate
    target_x = x
    target_y = y
    if coordinate and len(coordinate) >= 2:
        target_x, target_y = coordinate[0], coordinate[1]

    _emit_agent_event("agent_action_start", {
        "tool_name": "computer_use",
        "action_title": f"Computer Use ({act.upper()})",
        "detail": f"{f'at ({target_x}, {target_y})' if target_x is not None else (text or key or '')}",
        "icon": "monitor"
    })

    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)

    # 1. SCREENSHOT
    if act in ("screenshot", "screen"):
        try:
            im = ImageGrab.grab(all_screens=True)
            timestamp = int(time.time())
            filename = f"screen_{timestamp}.png"
            filepath = os.path.join(STAGING_DIR, filename)
            im.save(filepath, "PNG")

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
                "action": "screenshot",
                "image_path": filepath,
                "screen_width": im.width,
                "screen_height": im.height,
                "cursor_pos": {"x": cur_x, "y": cur_y},
                "message": f"Tangkapan layar desktop berhasil disimpan ({im.width}x{im.height}px)."
            }
        except Exception as e:
            return {"status": "error", "message": f"Gagal mengambil tangkapan layar: {e}"}

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
            return {"status": "error", "message": "Otomasi mouse hanya didukung di Windows."}
        if target_x is None or target_y is None:
            return {"status": "error", "message": "Koordinat x dan y wajib diisi untuk mouse_move."}
        clamped_x = max(vx, min(vx + screen_w - 1, int(target_x)))
        clamped_y = max(vy, min(vy + screen_h - 1, int(target_y)))
        user32.SetCursorPos(clamped_x, clamped_y)
        return {
            "status": "success",
            "action": "mouse_move",
            "target": {"x": clamped_x, "y": clamped_y},
            "message": f"Kursor dipindahkan ke ({clamped_x}, {clamped_y})."
        }

    # 4. MOUSE CLICK
    elif act in ("mouse_click", "click"):
        if not user32:
            return {"status": "error", "message": "Otomasi mouse hanya didukung di Windows."}
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
            "message": f"Klik {btn} berhasil dilakukan pada ({clamped_x}, {clamped_y})."
        }

    # 5. MOUSE DRAG
    elif act in ("mouse_drag", "drag"):
        if not user32:
            return {"status": "error", "message": "Otomasi mouse hanya didukung di Windows."}
        if target_x is None or target_y is None:
            return {"status": "error", "message": "Koordinat target (x, y) wajib diisi untuk mouse_drag."}
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
            "message": f"Mouse di-drag ke ({clamped_x}, {clamped_y})."
        }

    # 6. KEYBOARD TYPE
    elif act in ("keyboard_type", "type"):
        if not text:
            return {"status": "error", "message": "Parameter 'text' wajib diisi untuk keyboard_type."}

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
            "message": f"Teks berhasil diketik ke jendela aktif ({len(text)} karakter)."
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
            "message": f"Tombol '{clean_k}' berhasil ditekan."
        }

    return {
        "status": "error",
        "message": f"Aksi '{act}' tidak dikenal. Pilih dari: 'screenshot', 'mouse_click', 'mouse_move', 'mouse_drag', 'keyboard_type', 'keyboard_press', 'screen_info'."
    }
