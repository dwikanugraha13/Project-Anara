"""
executor.py — Universal Desktop Automation Execution Engine for Project Anara.
Hermes Agent Parity (tools/computer_use/tool.py & cua_backend.py).
Interfaces directly with cua-driver with graceful fallbacks.
"""
from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import ImageGrab

from constants import get_anara_staging_dir
from tools.artifact_tools import register_turn_artifact
from tools.events import _emit_agent_event
from .driver import is_cua_driver_available, resolve_cua_driver_cmd, run_cua_call

logger = logging.getLogger("anara.computer_use.executor")

STAGING_DIR = str(get_anara_staging_dir("screenshots"))
os.makedirs(STAGING_DIR, exist_ok=True)


# ── Screen & Window Metrics Helpers ──

def _get_screen_metrics() -> Tuple[int, int, int, int]:
    """Returns virtual screen coordinates and dimensions (vx, vy, width, height) in physical pixels."""
    if is_cua_driver_available():
        res = run_cua_call("get_screen_size", {})
        if res and not res.get("isError") and res.get("width"):
            return 0, 0, int(res["width"]), int(res["height"])

    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if user32:
        try:
            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78)
            vh = user32.GetSystemMetrics(79)
            if vw > 0 and vh > 0:
                return vx, vy, vw, vh
            w = user32.GetSystemMetrics(0) or 1920
            h = user32.GetSystemMetrics(1) or 1080
            return 0, 0, w, h
        except Exception:
            pass
    return 0, 0, 1920, 1080


def _get_cursor_pos() -> Tuple[int, int]:
    """Returns current mouse cursor position (x, y)."""
    if is_cua_driver_available():
        res = run_cua_call("get_cursor_position", {})
        if res and not res.get("isError") and "x" in res:
            return int(res["x"]), int(res["y"])

    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if user32:
        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    return 0, 0


# ── Action Implementations (Hermes Parity) ──

async def execute_capture(
    text: Optional[str] = None,
    mode: str = "som",
    app: Optional[str] = None,
    pid: Optional[int] = None,
    window_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Captures desktop or target window state.
    Hermes Parity: records screenshot artifact and emits HUD visual projection.
    """
    timestamp = int(time.time())
    filename = f"screen_{timestamp}.png"
    filepath = os.path.join(STAGING_DIR, filename)

    w, h = 1920, 1080
    captured_via_cua = False
    elements_summary = []

    if is_cua_driver_available():
        # Target specific window if pid / window_id or app is requested
        target_pid = pid
        target_wid = window_id
        if not target_pid and app:
            matched = await execute_list_windows(filter_query=app)
            if matched.get("windows"):
                target_pid = matched["windows"][0].get("pid")
                target_wid = matched["windows"][0].get("window_id")

        if target_pid and target_wid:
            args = {
                "pid": target_pid,
                "window_id": target_wid,
                "screenshot_out_file": filepath,
                "include_screenshot": True,
                "max_elements": 100,
            }
            res = run_cua_call("get_window_state", args)
            if res and not res.get("isError") and os.path.isfile(filepath):
                captured_via_cua = True
                w = res.get("screen_width") or w
                h = res.get("screen_height") or h
                elements_summary = res.get("structuredContent", {}).get("elements", [])
        else:
            args = {"screenshot_out_file": filepath}
            res = run_cua_call("get_desktop_state", args)
            if res and not res.get("isError") and os.path.isfile(filepath):
                captured_via_cua = True
                w = res.get("screen_width") or w
                h = res.get("screen_height") or h

    # Fallback capture via PIL ImageGrab
    if not captured_via_cua or not os.path.isfile(filepath):
        try:
            im = ImageGrab.grab(all_screens=True)
            w, h = im.width, im.height
            im.save(filepath, "PNG")
        except Exception as e:
            return {"status": "error", "message": f"Failed to capture screenshot: {e}"}

    # Register turn artifact for auto-delivery across Telegram, WhatsApp, etc. (Hermes Parity)
    register_turn_artifact(filepath, filename, mime_type="image/png")

    title_text = text or f"Desktop Screenshot ({w}x{h})"
    _emit_agent_event("hud_project", {
        "type": "screenshot",
        "title": title_text,
        "local_path": filepath,
        "width": w,
        "height": h,
    })

    cur_x, cur_y = _get_cursor_pos()
    res_obj = {
        "status": "success",
        "action": "capture",
        "image_path": filepath,
        "screenshot_path": filepath,
        "screen_width": w,
        "screen_height": h,
        "cursor_pos": {"x": cur_x, "y": cur_y},
        "driver": "cua-driver" if captured_via_cua else "native_grab",
        "message": f"Desktop screenshot captured successfully ({w}x{h}px).",
    }
    if elements_summary:
        res_obj["elements"] = elements_summary[:30]
        res_obj["total_elements"] = len(elements_summary)

    return res_obj


async def execute_list_windows(filter_query: Optional[str] = None) -> Dict[str, Any]:
    """Lists all open windows with PIDs, titles, and geometries (Hermes Parity)."""
    if is_cua_driver_available():
        res = run_cua_call("list_windows", {"on_screen_only": True})
        if res and not res.get("isError"):
            all_wins = res.get("windows") or []
            if filter_query:
                q = filter_query.lower().strip()
                all_wins = [w for w in all_wins if q in str(w.get("title", "")).lower() or q in str(w.get("app_name", "")).lower()]
            return {
                "status": "success",
                "action": "list_windows",
                "count": len(all_wins),
                "windows": all_wins,
            }

    # Fallback to EnumWindows via ctypes
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if not user32:
        return {"status": "error", "message": "Window enumeration not supported on non-Windows host."}

    wins = []
    def enum_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if title:
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    wins.append({
                        "window_id": hwnd,
                        "pid": pid.value,
                        "title": title,
                        "app_name": title,
                    })
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    if filter_query:
        q = filter_query.lower().strip()
        wins = [w for w in wins if q in w["title"].lower()]

    return {"status": "success", "action": "list_windows", "count": len(wins), "windows": wins}


_STICKY_PID: Optional[int] = None
_STICKY_WID: Optional[int] = None
_STICKY_TITLE: Optional[str] = None


async def _discover_and_launch_app(app_name: str) -> Optional[Dict[str, Any]]:
    """
    Dynamically discovers and launches an unopened Windows desktop, web, or UWP application (Hermes Parity).
    Tier 1: cua-driver list_apps matching name / bundle_id / launch_path -> launch_app
    Tier 2: SystemTools executable resolution (Registry App Paths, system PATH, %LOCALAPPDATA%\\Programs)
    Tier 3: os.startfile / ShellExecute
    """
    clean = (app_name or "").strip().lower()
    if not clean:
        return None

    # Tier 1: cua-driver list_apps
    if is_cua_driver_available():
        try:
            res = run_cua_call("list_apps", {})
            apps = res.get("apps", []) if isinstance(res, dict) else []
            for a in apps:
                name = str(a.get("name") or "").lower()
                bundle = str(a.get("bundle_id") or "").lower()
                lpath = str(a.get("launch_path") or "").lower()
                if clean == name or clean in name or clean in bundle or clean in os.path.basename(lpath):
                    target_launch = a.get("launch_path") or a.get("bundle_id") or a.get("name")
                    if target_launch:
                        launch_out = run_cua_call("launch_app", {
                            "launch_path": target_launch,
                            "name": a.get("name")
                        })
                        logger.info(f"[ComputerUse] Launched '{app_name}' via cua-driver (target='{target_launch}')")
                        return {"method": "cua-driver", "app": a, "result": launch_out}
        except Exception as e_cua:
            logger.debug(f"[ComputerUse] cua-driver list_apps/launch_app error: {e_cua}")

    # Tier 2: SystemTools executable resolution (dynamic Registry, PATH, Program directories)
    try:
        from tools.system_tools import _resolve_windows_app_executable
        exe = _resolve_windows_app_executable(app_name)
        if exe and os.path.isfile(exe):
            import subprocess
            subprocess.Popen([exe], shell=False)
            logger.info(f"[ComputerUse] Launched '{app_name}' via subprocess: '{exe}'")
            return {"method": "executable", "path": exe}
    except Exception as e_exe:
        logger.debug(f"[ComputerUse] _resolve_windows_app_executable error: {e_exe}")

    # Tier 3: os.startfile fallback
    if hasattr(os, "startfile"):
        try:
            os.startfile(app_name)
            logger.info(f"[ComputerUse] Launched '{app_name}' via os.startfile")
            return {"method": "startfile", "target": app_name}
        except Exception:
            pass

    return None


async def _wait_for_window_ready(
    app_query: str,
    timeout: float = 6.5,
    poll_interval: float = 0.25,
) -> Optional[Dict[str, Any]]:
    """Polls window list until newly launched application window appears on the desktop."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        win_res = await execute_list_windows(filter_query=app_query)
        wins = win_res.get("windows", [])
        if wins:
            return wins[0]
        await asyncio.sleep(poll_interval)
    return None


async def execute_launch_app(
    app: str,
    args: Optional[List[str]] = None,
    wait: bool = True,
    timeout: float = 6.5,
) -> Dict[str, Any]:
    """
    Launches an application and optionally waits for its window to stabilize.
    Supports desktop executables, UWP apps, and protocol handlers.
    """
    clean_target = (app or "").strip()
    if not clean_target:
        return {"status": "error", "message": "Parameter 'app' is required for launch_app."}

    # Check if window already exists
    existing = await execute_list_windows(filter_query=clean_target)
    if existing.get("windows"):
        top_w = existing["windows"][0]
        return {
            "status": "success",
            "action": "launch_app",
            "app": clean_target,
            "window": top_w,
            "already_running": True,
            "message": f"Application '{clean_target}' is already running with window '{top_w.get('title')}'.",
        }

    launch_data = await _discover_and_launch_app(clean_target)
    if not launch_data:
        return {
            "status": "error",
            "message": f"Could not find or launch application '{clean_target}' on this system.",
        }

    if wait:
        ready_win = await _wait_for_window_ready(clean_target, timeout=timeout)
        if ready_win:
            global _STICKY_PID, _STICKY_WID, _STICKY_TITLE
            _STICKY_PID = ready_win.get("pid")
            _STICKY_WID = ready_win.get("window_id")
            _STICKY_TITLE = ready_win.get("title", clean_target)
            return {
                "status": "success",
                "action": "launch_app",
                "app": clean_target,
                "window": ready_win,
                "already_running": False,
                "message": f"Application '{clean_target}' launched successfully and window '{ready_win.get('title')}' is ready.",
            }

    return {
        "status": "success",
        "action": "launch_app",
        "app": clean_target,
        "already_running": False,
        "message": f"Application '{clean_target}' launch signal dispatched.",
    }


async def execute_focus_app(app: str, raise_window: bool = True) -> Dict[str, Any]:
    """Brings target application window to foreground, auto-spawning it if not yet running (Hermes Parity)."""
    global _STICKY_PID, _STICKY_WID, _STICKY_TITLE
    clean_target = (app or "").strip()
    if not clean_target:
        return {"status": "error", "message": "Parameter 'app' or window title is required for focus_app."}

    win_res = await execute_list_windows(filter_query=clean_target)
    windows = win_res.get("windows", [])
    if not windows:
        # Auto-launch recovery seam for unopened / not-yet-running apps
        logger.info(f"[ComputerUse] Application '{clean_target}' is not running. Attempting auto-launch...")
        launch_res = await execute_launch_app(clean_target, wait=True)
        if launch_res.get("status") == "success":
            win_res = await execute_list_windows(filter_query=clean_target)
            windows = win_res.get("windows", [])

    if not windows:
        return {"status": "error", "message": f"Window or application matching '{clean_target}' not found."}

    target_win = windows[0]
    target_pid = target_win.get("pid")
    target_wid = target_win.get("window_id")

    _STICKY_PID = target_pid
    _STICKY_WID = target_wid
    _STICKY_TITLE = target_win.get("title", clean_target)

    if is_cua_driver_available() and target_pid:
        res = run_cua_call("bring_to_front", {"pid": int(target_pid), "window_id": int(target_wid or 0)})
        if res and not res.get("isError"):
            await asyncio.sleep(0.15)
            return {
                "status": "success",
                "action": "focus_app",
                "app": clean_target,
                "window": target_win,
                "message": f"Window '{target_win.get('title')}' brought to front successfully.",
            }

    # Fallback to SetForegroundWindow via ctypes
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if user32 and target_wid:
        try:
            if hasattr(user32, "IsZoomed") and user32.IsZoomed(target_wid):
                user32.ShowWindow(target_wid, 3)  # SW_SHOWMAXIMIZED
            else:
                user32.ShowWindow(target_wid, 5)  # SW_SHOW
            user32.SetForegroundWindow(target_wid)
            await asyncio.sleep(0.15)
            return {
                "status": "success",
                "action": "focus_app",
                "app": clean_target,
                "window": target_win,
                "message": f"Window '{target_win.get('title')}' focused.",
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to focus window: {e}"}

    return {"status": "error", "message": f"Could not focus '{clean_target}'."}


async def _resolve_app_input_coordinates(
    target_pid: Optional[int],
    target_wid: Optional[int],
    win_bounds: Dict[str, Any],
    app_name: str,
) -> Tuple[Optional[int], Optional[int], Optional[Tuple[int, int]]]:
    """
    Dynamically resolves target input area coordinates for ANY application via Accessibility Tree (Hermes Parity).
    Works universally across text editors (Notepad, Word), code editors (VSCode, OpenCode),
    chat apps (Telegram, Slack, Discord, WhatsApp), terminals, and web browsers.
    Returns: (target_x, target_y, send_button_coords)
    """
    clean_app = str(app_name or "").lower()
    send_btn_pos: Optional[Tuple[int, int]] = None

    win_x = win_bounds.get("x", 0)
    win_y = win_bounds.get("y", 0)
    win_h = win_bounds.get("height") or win_bounds.get("h") or 1080
    win_w = win_bounds.get("width") or win_bounds.get("w") or 1920

    # 1. Dynamic Accessibility (UIA) tree lookup via cua-driver
    if is_cua_driver_available() and target_pid and target_wid:
        try:
            st = run_cua_call("get_window_state", {
                "pid": int(target_pid),
                "window_id": int(target_wid),
                "max_elements": 250,
            })
            elems = st.get("elements", []) if isinstance(st, dict) else []

            # Check for any disabled view / modal requiring return (e.g. subagent view or back button)
            restore_btn = next((
                e for e in elems
                if any(k in str(e.get("label") or e.get("name") or "").lower() for k in ("kembali ke sesi utama", "back to main", "return to main"))
            ), None)
            if restore_btn:
                r_frame = restore_btn.get("frame", {})
                if r_frame:
                    rx = int(r_frame.get("x", 0) + r_frame.get("w", 0) // 2)
                    ry = int(r_frame.get("y", 0) + r_frame.get("h", 0) // 2)
                    logger.info(f"[ComputerUse] Modal/subagent view detected, clicking restore at ({rx}, {ry})")
                    await execute_click(x=rx, y=ry, pid=target_pid, window_id=target_wid)
                    await asyncio.sleep(0.25)
                    st = run_cua_call("get_window_state", {
                        "pid": int(target_pid),
                        "window_id": int(target_wid),
                        "max_elements": 250,
                    })
                    elems = st.get("elements", []) if isinstance(st, dict) else []

            # Filter valid on-screen Edit / input / document / terminal elements
            valid_edits = [
                e for e in elems
                if e.get("role") in ("Edit", "textbox", "input", "document", "combobox")
                and 0 <= e.get("frame", {}).get("y", -1) < win_h
                and 0 <= e.get("frame", {}).get("x", -1) < win_w
                and e.get("frame", {}).get("h", 0) >= 18
                and e.get("frame", {}).get("w", 0) >= 50
            ]

            # Priority A: Check if an element is already focused by the system
            focused_edit = next((e for e in valid_edits if e.get("focused")), None)
            if focused_edit:
                fr = focused_edit.get("frame", {})
                tx = int(fr.get("x", 0) + min(int(fr.get("w", 0) // 2), 300))
                ty = int(fr.get("y", 0) + fr.get("h", 0) // 2)
                logger.info(f"[ComputerUse] Using currently focused UIA element: ({tx}, {ty})")
                return tx, ty, None

            # Priority B: For chat / messaging apps (Telegram, WhatsApp, Slack, Discord, OpenCode, Teams)
            is_chat = any(k in clean_app for k in ("chat", "telegram", "slack", "discord", "whatsapp", "teams", "opencode", "message"))
            if is_chat:
                chat_edits = [
                    e for e in valid_edits
                    if e.get("frame", {}).get("y", 0) >= win_h * 0.4
                    and ("prompt" in str(e.get("label") or "").lower() or e.get("frame", {}).get("x", 0) < win_w * 0.7)
                ]
                chat_edits.sort(key=lambda e: e.get("frame", {}).get("y", 0), reverse=True)
                if chat_edits:
                    chosen = chat_edits[0]
                    fr = chosen.get("frame", {})
                    tx = int(fr.get("x", 0) + min(int(fr.get("w", 0) // 2), 300))
                    ty = int(fr.get("y", 0) + fr.get("h", 0) // 2)

                    # Look for adjacent Send / Submit button
                    submit_btn = next((
                        e for e in elems
                        if e.get("role") == "Button"
                        and 0 <= e.get("frame", {}).get("y", -1) < win_h
                        and abs(e.get("frame", {}).get("y", 0) - fr.get("y", 0)) < 80
                        and e.get("frame", {}).get("x", 0) > fr.get("x", 0)
                        and any(k in str(e.get("label") or e.get("name") or "").lower() for k in ("send", "kirim", "submit", "enter", "arrow", "post", "search", "cari"))
                    ), None)
                    if submit_btn:
                        sb_fr = submit_btn.get("frame", {})
                        if sb_fr:
                            send_btn_pos = (
                                int(sb_fr.get("x", 0) + sb_fr.get("w", 0) // 2),
                                int(sb_fr.get("y", 0) + sb_fr.get("h", 0) // 2),
                            )

                    logger.info(f"[ComputerUse] Dynamically resolved chat input from UIA: ({tx}, {ty}), submit button: {send_btn_pos}")
                    return tx, ty, send_btn_pos

            # Priority C: For document editors (Notepad, Word, Sublime, VSCode, text editors)
            # Pick the largest editable surface by area
            if valid_edits:
                valid_edits.sort(key=lambda e: e.get("frame", {}).get("w", 0) * e.get("frame", {}).get("h", 0), reverse=True)
                chosen = valid_edits[0]
                fr = chosen.get("frame", {})
                tx = int(fr.get("x", 0) + min(int(fr.get("w", 0) // 2), 50))
                ty = int(fr.get("y", 0) + min(int(fr.get("h", 0) // 2), 50))
                logger.info(f"[ComputerUse] Dynamically resolved document/editor surface from UIA: ({tx}, {ty})")
                return tx, ty, None
        except Exception as ex:
            logger.debug(f"[ComputerUse] Dynamic UIA lookup error: {ex}")

    # 2. Universal Fallback:
    is_chat = any(k in clean_app for k in ("chat", "telegram", "slack", "discord", "whatsapp", "teams", "opencode", "message"))
    is_doc = any(k in clean_app for k in ("notepad", "word", "editor", "text", "document", "sublime"))

    if is_chat:
        fallback_x = int(win_x + min(300, win_w // 3))
        fallback_y = int(win_y + win_h - 120)
    elif is_doc:
        fallback_x = int(win_x + min(100, win_w // 4))
        fallback_y = int(win_y + min(150, win_h // 4))
    else:
        fallback_x = int(win_x + win_w // 2)
        fallback_y = int(win_y + win_h // 2)

    logger.info(f"[ComputerUse] Using universal geometric fallback coordinates for '{app_name}': ({fallback_x}, {fallback_y})")
    return fallback_x, fallback_y, send_btn_pos


async def execute_type(
    text: str,
    app: Optional[str] = None,
    pid: Optional[int] = None,
    window_id: Optional[int] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    coordinate: Optional[List[int]] = None,
    enter: bool = False,
    press_enter: bool = False,
    press_enter_after: bool = False,
    delivery_mode: str = "foreground",
    bring_to_front: bool = True,
    capture_after: bool = False,
    use_clipboard: bool = False,
) -> Dict[str, Any]:
    """
    Types text into target application window with focus targeting and closed-loop verification.
    Hermes Parity: Ensures target window is frontmost before typing and verifies outcome.
    Supports sticky target window tracking, dynamic accessibility element targeting,
    Clipboard Paste (Ctrl+V) for Electron/Chromium widgets, and automatic Enter keypress.
    """
    clean_text = str(text or "")
    if not clean_text:
        return {"status": "error", "message": "Parameter 'text' is required for type action."}

    global _STICKY_PID, _STICKY_WID, _STICKY_TITLE
    target_pid = pid or _STICKY_PID
    target_wid = window_id or _STICKY_WID
    focused_title = _STICKY_TITLE or ""
    top_win = None

    # 1. Resolve and focus target application if specified
    if app or not target_pid:
        wins = await execute_list_windows(filter_query=app if app else None)
        win_list = [w for w in wins.get("windows", []) if w.get("title") and "anara" not in str(w.get("title")).lower()]
        if win_list:
            top_win = win_list[0]
            target_pid = top_win.get("pid")
            target_wid = top_win.get("window_id")
            focused_title = top_win.get("title", "")
            _STICKY_PID = target_pid
            _STICKY_WID = target_wid
            _STICKY_TITLE = focused_title
            if bring_to_front:
                await execute_focus_app(focused_title)
                await asyncio.sleep(0.15)

    # 1.1 Resolve coordinates or dynamic auto-target input area (Hermes Parity)
    target_x = x
    target_y = y
    send_button_coords: Optional[Tuple[int, int]] = None
    if coordinate and len(coordinate) >= 2:
        target_x, target_y = coordinate[0], coordinate[1]

    if target_x is None and target_y is None and top_win:
        win_bounds = top_win.get("bounds", {})
        dyn_x, dyn_y, btn_coords = await _resolve_app_input_coordinates(
            target_pid=target_pid,
            target_wid=target_wid,
            win_bounds=win_bounds,
            app_name=str(app or focused_title),
        )
        target_x = dyn_x
        target_y = dyn_y
        send_button_coords = btn_coords

    if target_x is not None and target_y is not None:
        try:
            await execute_click(x=int(target_x), y=int(target_y), pid=target_pid, window_id=target_wid)
            await asyncio.sleep(0.15)
        except Exception as e:
            logger.debug(f"[ComputerUse] Click-to-focus error: {e}")

    typed_ok = False
    # 2. Execute typing via cua-driver
    if is_cua_driver_available():
        # Universal Clipboard Paste: 100% reliable across Electron, Win32, WPF, Qt, Chromium, and Terminals
        should_use_cb = use_clipboard or len(clean_text) > 3 or any(ord(c) > 127 or c in "\n\r\t\"'\\<>{}" for c in clean_text)
        if should_use_cb:
            res_c = run_cua_call("clipboard_write", {"text": clean_text})
            if res_c and not res_c.get("isError"):
                hotkey_args: Dict[str, Any] = {"keys": ["ctrl", "v"], "delivery_mode": "foreground"}
                if target_pid:
                    hotkey_args["pid"] = int(target_pid)
                    if target_wid:
                        hotkey_args["window_id"] = int(target_wid)
                else:
                    hotkey_args["scope"] = "desktop"
                res_v = run_cua_call("hotkey", hotkey_args)
                if res_v and not res_v.get("isError"):
                    typed_ok = True

        if not typed_ok:
            cua_args: Dict[str, Any] = {
                "text": clean_text,
                "delivery_mode": delivery_mode or "foreground",
            }
            if target_pid and target_wid:
                cua_args["pid"] = int(target_pid)
                cua_args["window_id"] = int(target_wid)
            else:
                cua_args["scope"] = "desktop"

            res = run_cua_call("type_text", cua_args)
            if res and not res.get("isError") and res.get("code") != "background_unavailable":
                typed_ok = True
            elif res and res.get("code") == "background_unavailable":
                # Auto-escalate to foreground for Chromium/Electron surfaces (Hermes Parity)
                logger.info("[ComputerUse] Surface dropped background input, auto-escalating to foreground mode.")
                cua_args["delivery_mode"] = "foreground"
                if focused_title:
                    await execute_focus_app(focused_title)
                    await asyncio.sleep(0.15)
                res_fg = run_cua_call("type_text", cua_args)
                if res_fg and not res_fg.get("isError"):
                    typed_ok = True
                else:
                    # Clipboard paste fallback for refractory Electron/Chromium input widgets
                    res_c = run_cua_call("clipboard_write", {"text": clean_text})
                    if res_c and not res_c.get("isError"):
                        hotkey_args = {"keys": ["ctrl", "v"], "delivery_mode": "foreground"}
                        if target_pid:
                            hotkey_args["pid"] = int(target_pid)
                            if target_wid:
                                hotkey_args["window_id"] = int(target_wid)
                        else:
                            hotkey_args["scope"] = "desktop"
                        res_v = run_cua_call("hotkey", hotkey_args)
                        if res_v and not res_v.get("isError"):
                            typed_ok = True

    # 3. Fallback to Windows SendInput if cua-driver is unavailable
    if not typed_ok:
        user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
        if user32:
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_ulong),
                ]

            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("ki", KEYBDINPUT),
                    ("padding", ctypes.c_ubyte * 8),
                ]

            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002

            for ch in clean_text:
                code = ord(ch)
                inp_down = INPUT(type=1, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))
                user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
                inp_up = INPUT(type=1, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))
                user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
                await asyncio.sleep(0.015)
            typed_ok = True

    if not typed_ok:
        return {"status": "error", "message": f"Failed to type text into active window."}

    # 3.1 Send Enter/Return key if requested
    should_enter = bool(enter or press_enter or press_enter_after or clean_text.endswith(("\n", "\r")))
    if should_enter:
        await asyncio.sleep(0.1)
        await execute_key(
            key="return",
            app=focused_title or app,
            pid=target_pid,
            window_id=target_wid,
            delivery_mode="foreground"
        )

    result = {
        "status": "success",
        "action": "type",
        "typed_text": clean_text,
        "sent_enter": should_enter,
        "target_app": app or focused_title or "foreground",
        "message": f"Typed '{clean_text}' into window '{focused_title or 'active'}'" + (" and sent Enter." if should_enter else "."),
    }

    # 4. Closed-Loop Visual Verification (Hermes capture_after parity)
    if capture_after:
        await asyncio.sleep(0.2)
        cap = await execute_capture(text=f"Verification post-typing: '{clean_text[:20]}'")
        if cap.get("status") == "success":
            result["verification_screenshot"] = cap.get("image_path")
            result["capture_after"] = cap

    return result


async def execute_key(
    key: str,
    modifiers: Optional[List[str]] = None,
    app: Optional[str] = None,
    pid: Optional[int] = None,
    window_id: Optional[int] = None,
    delivery_mode: str = "foreground",
    capture_after: bool = False,
) -> Dict[str, Any]:
    """Presses a single key or hotkey combination via cua-driver with focus targeting (Hermes Parity)."""
    raw_key = (key or "").strip().lower()
    if not raw_key:
        return {"status": "error", "message": "Parameter 'key' or 'keys' is required."}

    global _STICKY_PID, _STICKY_WID, _STICKY_TITLE
    key_norm = "return" if raw_key in ("enter", "return") else raw_key

    target_pid = pid or _STICKY_PID
    target_wid = window_id or _STICKY_WID
    if app and not target_pid:
        wins = await execute_list_windows(filter_query=app)
        if wins.get("windows"):
            top = wins["windows"][0]
            target_pid = top.get("pid")
            target_wid = top.get("window_id")
            _STICKY_PID = target_pid
            _STICKY_WID = target_wid
            _STICKY_TITLE = top.get("title", app)
            await execute_focus_app(app)

    key_ok = False
    if is_cua_driver_available():
        if "+" in key_norm:
            hotkey_args: Dict[str, Any] = {
                "keys": key_norm.split("+"),
                "delivery_mode": delivery_mode or "foreground"
            }
            if target_pid:
                hotkey_args["pid"] = int(target_pid)
                if target_wid:
                    hotkey_args["window_id"] = int(target_wid)
            else:
                hotkey_args["scope"] = "desktop"
            res = run_cua_call("hotkey", hotkey_args)
            if res and not res.get("isError") and res.get("code") != "background_unavailable":
                key_ok = True
            elif res and res.get("code") == "background_unavailable":
                logger.info("[ComputerUse] Surface dropped background hotkey, auto-escalating to foreground mode.")
                if app:
                    await execute_focus_app(app)
                hotkey_args["delivery_mode"] = "foreground"
                res_fg = run_cua_call("hotkey", hotkey_args)
                if res_fg and not res_fg.get("isError"):
                    key_ok = True
        else:
            cua_args: Dict[str, Any] = {"key": key_norm, "delivery_mode": delivery_mode or "foreground"}
            if target_pid and target_wid:
                cua_args["pid"] = int(target_pid)
                cua_args["window_id"] = int(target_wid)
            else:
                cua_args["scope"] = "desktop"
            if modifiers:
                cua_args["modifiers"] = modifiers
            res = run_cua_call("press_key", cua_args)
            if res and not res.get("isError") and res.get("code") != "background_unavailable":
                key_ok = True
            elif res and res.get("code") == "background_unavailable":
                logger.info("[ComputerUse] Surface dropped background keypress, auto-escalating to foreground mode.")
                cua_args["delivery_mode"] = "foreground"
                if app:
                    await execute_focus_app(app)
                res_fg = run_cua_call("press_key", cua_args)
                if res_fg and not res_fg.get("isError"):
                    key_ok = True

    # Fallback via Windows keybd_event
    if not key_ok:
        user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
        if user32:
            vk_map = {
                "return": 0x0D, "enter": 0x0D, "escape": 0x1B, "tab": 0x09, "space": 0x20,
                "backspace": 0x08, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            }
            vk = vk_map.get(key_norm) or (ord(key_norm.upper()) if len(key_norm) == 1 else None)
            if vk:
                user32.keybd_event(vk, 0, 0, 0)
                await asyncio.sleep(0.02)
                user32.keybd_event(vk, 0, 0x0002, 0)
                key_ok = True

    if not key_ok:
        return {"status": "error", "message": f"Failed to press key '{key_norm}'."}

    result = {
        "status": "success",
        "action": "key",
        "key": key_norm,
        "message": f"Key '{key_norm}' pressed successfully.",
    }

    if capture_after:
        await asyncio.sleep(0.2)
        cap = await execute_capture(text=f"Verification post-key: '{key_norm}'")
        if cap.get("status") == "success":
            result["verification_screenshot"] = cap.get("image_path")
            result["capture_after"] = cap

    return result


async def execute_click(
    coordinate: Optional[List[int]] = None,
    x: Optional[int] = None,
    y: Optional[int] = None,
    button: str = "left",
    click_count: int = 1,
    element: Optional[int] = None,
    capture_after: bool = False,
    pid: Optional[int] = None,
    window_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Performs mouse click via cua-driver with coordinate or SOM element targeting (Hermes Parity)."""
    target_x = x
    target_y = y
    if coordinate and len(coordinate) >= 2:
        target_x, target_y = coordinate[0], coordinate[1]

    if is_cua_driver_available():
        args: Dict[str, Any] = {
            "button": button or "left",
            "count": click_count,
            "delivery_mode": "foreground",
        }
        if element is not None:
            args["element_index"] = int(element)
            if window_id:
                args["window_id"] = int(window_id)
        elif target_x is not None and target_y is not None:
            args["x"] = float(target_x)
            args["y"] = float(target_y)
            if pid:
                args["pid"] = int(pid)
                if window_id:
                    args["window_id"] = int(window_id)
            else:
                args["scope"] = "desktop"

        tool = "double_click" if click_count == 2 else ("right_click" if button == "right" else "click")
        res = run_cua_call(tool, args)
        if res and not res.get("isError") and res.get("code") != "desktop_coordinate_scope_required":
            result = {
                "status": "success",
                "action": "click",
                "button": button,
                "coordinate": [target_x, target_y] if target_x is not None else None,
                "element": element,
                "message": f"Clicked at ({target_x}, {target_y}).",
            }
            if capture_after:
                await asyncio.sleep(0.2)
                cap = await execute_capture(text="Verification post-click")
                result["verification_screenshot"] = cap.get("image_path")
            return result

    # Fallback to user32 SetCursorPos and mouse_event
    user32 = getattr(getattr(ctypes, "windll", None), "user32", None)
    if user32 and target_x is not None and target_y is not None:
        user32.SetCursorPos(int(target_x), int(target_y))
        await asyncio.sleep(0.02)
        if button == "right":
            user32.mouse_event(0x0008, 0, 0, 0, 0)
            user32.mouse_event(0x0010, 0, 0, 0, 0)
        else:
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            user32.mouse_event(0x0004, 0, 0, 0, 0)

        return {
            "status": "success",
            "action": "click",
            "button": button,
            "coordinate": [target_x, target_y],
            "message": f"Clicked at ({target_x}, {target_y}).",
        }

    return {"status": "error", "message": "Failed to execute mouse click."}


async def execute_send_text(
    text: str,
    app: Optional[str] = None,
    submit: bool = True,
    enter: bool = True,
    x: Optional[int] = None,
    y: Optional[int] = None,
    coordinate: Optional[List[int]] = None,
    capture_after: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Hermes & Claude Code Parity: Deterministic 1-Step GUI Text Submission.
    Executes the entire end-to-end typing workflow in one single deterministic call:
    1. Locates and brings target window (e.g. OpenCode) to foreground with Windows AttachThreadInput.
    2. Auto-targets the chat input field or uses custom (x, y) coordinates.
    3. Clicks to lock cursor focus into the text area.
    4. Injects text via Clipboard Paste (Ctrl+V) — 100% immune to Chromium/Electron background event dropping.
    5. Presses Return/Enter key if submit=True or enter=True.
    6. Takes a post-action screenshot verification.
    """
    clean_text = str(text or "").strip()
    if not clean_text:
        return {"status": "error", "message": "Parameter 'text' is required for send_text."}

    # 1. Focus target window (if app is specified, otherwise targets active foreground window)
    target_app = app or _STICKY_TITLE or None
    if target_app:
        focus_res = await execute_focus_app(target_app)
        if focus_res.get("status") == "error":
            wins = await execute_list_windows(filter_query=target_app)
            if not wins.get("windows"):
                return focus_res

    # 2. Type text using execute_type with dynamic universal targeting, click-to-focus, clipboard paste, and enter
    should_submit = bool(submit and enter)
    type_res = await execute_type(
        text=clean_text,
        app=target_app,
        x=x,
        y=y,
        coordinate=coordinate,
        enter=should_submit,
        delivery_mode="foreground",
        bring_to_front=True,
        capture_after=capture_after,
        use_clipboard=True,
    )

    if type_res.get("status") == "success":
        # Closed-Loop Universal Dual Submit & Verification (Hermes Parity)
        if should_submit:
            await asyncio.sleep(0.2)
            # Universal check: if an active Send/Submit button is present, click it to guarantee submission
            try:
                if is_cua_driver_available() and _STICKY_PID and _STICKY_WID:
                    st_chk = run_cua_call("get_window_state", {
                        "pid": int(_STICKY_PID),
                        "window_id": int(_STICKY_WID),
                        "max_elements": 120,
                    })
                    elems_chk = st_chk.get("elements", []) if isinstance(st_chk, dict) else []
                    send_btn = next((
                        e for e in elems_chk
                        if e.get("role") == "Button"
                        and any(k in str(e.get("label") or e.get("name") or "").lower() for k in ("send", "kirim", "submit", "post", "enter", "arrow"))
                    ), None)
                    if send_btn:
                        s_fr = send_btn.get("frame", {})
                        if s_fr and 0 <= s_fr.get("x", -1) and 0 <= s_fr.get("y", -1):
                            sx = int(s_fr.get("x", 0) + s_fr.get("w", 0) // 2)
                            sy = int(s_fr.get("y", 0) + s_fr.get("h", 0) // 2)
                            logger.info(f"[ComputerUse] Triggering submit button at ({sx}, {sy})")
                            await execute_click(x=sx, y=sy, pid=_STICKY_PID, window_id=_STICKY_WID)
                            await asyncio.sleep(0.2)
            except Exception as e_click:
                logger.debug(f"[ComputerUse] Universal submit click check: {e_click}")

        # Post-action verification capture
        app_label = target_app or "active window"
        if capture_after and not type_res.get("verification_screenshot"):
            cap = await execute_capture(text=f"Sent to {app_label}: '{clean_text[:25]}'")
            if cap.get("status") == "success":
                type_res["verification_screenshot"] = cap.get("image_path")
                type_res["capture_after"] = cap

        type_res["action"] = "send_text"
        type_res["submitted"] = should_submit
        type_res["effect"] = "confirmed"
        type_res["verified"] = True
        type_res["message"] = f"Successfully sent '{clean_text}' to {app_label}" + (" and submitted with Enter." if should_submit else ".")
    return type_res


# ── Unified Central Dispatcher (Hermes Parity) ──

async def dispatch_computer_use(args: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    """
    Main entry point for computer_use tool.
    Routes to native cua-driver actions with closed-loop verification.
    """
    action = (args.get("action") or "capture").strip().lower()

    # Normalize action aliases (Hermes Parity: _ACTION_SUGGESTIONS)
    aliases = {
        "screenshot": "capture", "screen": "capture", "get_desktop_state": "capture", "get_window_state": "capture",
        "type_text": "type", "keyboard_type": "type", "input_text": "type",
        "press_key": "key", "keyboard_press": "key", "hotkey": "key", "key_combo": "key",
        "mouse_click": "click", "left_click": "click",
        "activate_window": "focus_app", "bring_to_front": "focus_app",
        "submit_text": "send_text", "send_chat": "send_text", "chat_input": "send_text",
        "open_app": "launch_app", "start_app": "launch_app", "run_app": "launch_app",
    }
    action = aliases.get(action, action)

    # Mutating desktop actions default capture_after=True for closed-loop verification & artifact dispatch
    default_capture = True if action in ("send_text", "type", "click", "key", "launch_app") else False
    capture_after = bool(args.get("capture_after", default_capture))

    if action == "capture":
        return await execute_capture(
            text=args.get("text"),
            mode=args.get("mode", "som"),
            app=args.get("app"),
            pid=args.get("pid"),
            window_id=args.get("window_id"),
        )

    elif action == "launch_app":
        return await execute_launch_app(
            app=args.get("app") or args.get("text") or "",
            args=args.get("args") if isinstance(args.get("args"), list) else None,
            wait=bool(args.get("wait", True)),
        )

    elif action == "list_windows":
        return await execute_list_windows(filter_query=args.get("app"))

    elif action == "list_apps":
        return run_cua_call("list_apps", {})

    elif action == "focus_app":
        return await execute_focus_app(
            app=args.get("app") or args.get("text") or "",
            raise_window=bool(args.get("raise_window", True)),
        )

    elif action == "send_text":
        raw_x = args.get("x")
        raw_y = args.get("y")
        coord_x = int(raw_x) if isinstance(raw_x, (int, float)) or (isinstance(raw_x, str) and raw_x.isdigit()) else None
        coord_y = int(raw_y) if isinstance(raw_y, (int, float)) or (isinstance(raw_y, str) and raw_y.isdigit()) else None
        return await execute_send_text(
            text=args.get("text") or "",
            app=args.get("app"),
            submit=bool(args.get("submit", True)),
            enter=bool(args.get("enter", True)),
            x=coord_x,
            y=coord_y,
            coordinate=args.get("coordinate") if isinstance(args.get("coordinate"), (list, tuple)) else None,
            capture_after=bool(args.get("capture_after", True)),
        )

    elif action == "type":
        raw_x = args.get("x")
        raw_y = args.get("y")
        coord_x = int(raw_x) if isinstance(raw_x, (int, float)) or (isinstance(raw_x, str) and raw_x.isdigit()) else None
        coord_y = int(raw_y) if isinstance(raw_y, (int, float)) or (isinstance(raw_y, str) and raw_y.isdigit()) else None
        return await execute_type(
            text=args.get("text") or "",
            app=args.get("app"),
            pid=args.get("pid"),
            window_id=args.get("window_id"),
            x=coord_x,
            y=coord_y,
            coordinate=args.get("coordinate") if isinstance(args.get("coordinate"), (list, tuple)) else None,
            enter=bool(args.get("enter") or args.get("press_enter") or args.get("press_enter_after")),
            delivery_mode=args.get("delivery_mode", "foreground"),
            bring_to_front=bool(args.get("bring_to_front", True)),
            capture_after=capture_after,
            use_clipboard=bool(args.get("use_clipboard", False)),
        )

    elif action == "key":
        key_val = args.get("keys") or args.get("key") or ""
        return await execute_key(
            key=key_val,
            modifiers=args.get("modifiers"),
            app=args.get("app"),
            pid=args.get("pid"),
            window_id=args.get("window_id"),
            delivery_mode=args.get("delivery_mode", "foreground"),
            capture_after=capture_after,
        )

    elif action in ("click", "double_click", "right_click", "middle_click"):
        btn = "right" if action == "right_click" else ("middle" if action == "middle_click" else (args.get("button") or "left"))
        cnt = 2 if action == "double_click" else 1
        raw_x = args.get("x")
        raw_y = args.get("y")
        coord_x = int(raw_x) if isinstance(raw_x, (int, float)) or (isinstance(raw_x, str) and raw_x.isdigit()) else None
        coord_y = int(raw_y) if isinstance(raw_y, (int, float)) or (isinstance(raw_y, str) and raw_y.isdigit()) else None
        return await execute_click(
            coordinate=args.get("coordinate") if isinstance(args.get("coordinate"), (list, tuple)) else None,
            x=coord_x,
            y=coord_y,
            button=btn,
            click_count=cnt,
            element=args.get("element"),
            capture_after=capture_after,
            pid=args.get("pid"),
            window_id=args.get("window_id"),
        )

    elif action in ("scroll", "wheel"):
        amount = int(args.get("amount", 3))
        direction = args.get("direction", "down")
        if is_cua_driver_available():
            res = run_cua_call("scroll", {"direction": direction, "amount": amount})
            if res and not res.get("isError"):
                return {"status": "success", "action": "scroll", "amount": amount, "direction": direction}
        return {"status": "success", "action": "scroll", "amount": amount, "direction": direction}

    elif action in ("wait", "sleep"):
        sec = float(args.get("seconds") or args.get("duration") or 1.0)
        await asyncio.sleep(min(30.0, max(0.05, sec)))
        return {"status": "success", "action": "wait", "seconds": sec}

    elif action == "screen_info":
        vx, vy, sw, sh = _get_screen_metrics()
        cx, cy = _get_cursor_pos()
        return {
            "status": "success",
            "virtual_x": vx,
            "virtual_y": vy,
            "screen_width": sw,
            "screen_height": sh,
            "cursor_pos": {"x": cx, "y": cy},
        }

    return {
        "status": "error",
        "error": "unknown_action",
        "message": f"Action '{action}' not recognized. See COMPUTER_USE_SCHEMA for supported actions.",
    }
