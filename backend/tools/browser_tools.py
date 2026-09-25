"""
browser_tools.py — Modern Playwright Browser Automation for Project Anara.
Parity with Anara Agent browser tools: provides autonomous navigation,
smart audio/video autoplay, visual clicks, text input, snapshots, and screenshots.
"""

import asyncio
import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Browser = Any  # type: ignore
    BrowserContext = Any  # type: ignore
    Page = Any  # type: ignore
    Playwright = Any  # type: ignore

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

# Global persistent Playwright session manager
_PLAYWRIGHT_INSTANCE: Optional[Playwright] = None
_ACTIVE_BROWSER: Optional[Browser] = None
_ACTIVE_CONTEXT: Optional[BrowserContext] = None
_ACTIVE_PAGE: Optional[Page] = None
_CURRENT_HEADED_STATE: Optional[bool] = None
_LOCK = asyncio.Lock()


def _find_brave_binary() -> Optional[str]:
    """Finds local Brave Browser executable on Windows."""
    paths = [
        shutil.which("brave"),
        shutil.which("brave.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return None


async def _ensure_browser_session(headed: bool = False, use_brave: bool = False) -> Page:
    """Ensures a live Playwright page is open. Re-creates session if switching between headed and headless."""
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Module 'playwright' is not installed. Run 'pip install playwright' to use browser tools.")

    global _PLAYWRIGHT_INSTANCE, _ACTIVE_BROWSER, _ACTIVE_CONTEXT, _ACTIVE_PAGE, _CURRENT_HEADED_STATE

    async with _LOCK:
        needs_restart = (
            _ACTIVE_BROWSER is None or
            _ACTIVE_PAGE is None or
            _ACTIVE_PAGE.is_closed() or
            _CURRENT_HEADED_STATE != headed
        )

        if needs_restart:
            if _ACTIVE_CONTEXT:
                try:
                    await _ACTIVE_CONTEXT.close()
                except Exception:
                    pass
            if _ACTIVE_BROWSER:
                try:
                    await _ACTIVE_BROWSER.close()
                except Exception:
                    pass
            if _PLAYWRIGHT_INSTANCE is None:
                _PLAYWRIGHT_INSTANCE = await async_playwright().start()

            launch_kwargs: Dict[str, Any] = {
                "headless": not headed,
                "args": [
                    "--autoplay-policy=no-user-gesture-required",
                    "--disable-features=PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }

            brave_path = _find_brave_binary()
            if use_brave and brave_path:
                launch_kwargs["executable_path"] = brave_path
                logger.info(f"[BrowserTools] Launching Brave browser: {brave_path} (headed={headed})")
            else:
                logger.info(f"[BrowserTools] Launching Playwright Chromium (headed={headed})")

            _ACTIVE_BROWSER = await _PLAYWRIGHT_INSTANCE.chromium.launch(**launch_kwargs)
            _ACTIVE_CONTEXT = await _ACTIVE_BROWSER.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            )
            _ACTIVE_PAGE = await _ACTIVE_CONTEXT.new_page()
            _CURRENT_HEADED_STATE = headed

        return _ACTIVE_PAGE


async def _tool_browser_navigate(url: str, headed: Optional[bool] = None, use_brave: bool = False) -> Dict[str, Any]:
    """
    Opens and navigates to a URL.
    Auto-detects media playback (YouTube, video, audio) to open with headed=True so audio plays aloud.
    """
    clean_url = (url or "").strip()
    if not clean_url:
        return {"status": "error", "message": "URL cannot be empty."}

    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = f"https://{clean_url}"

    # Auto-headed determination: media playback requires headed mode for reliable sound output
    from config import cfg_get
    media_domains = cfg_get("browser.media_domains", ["youtube.com", "youtu.be", "spotify.com", "soundcloud.com", "twitch.tv"])
    is_media = any(k in clean_url.lower() for k in media_domains)
    effective_headed = headed if headed is not None else is_media

    _emit_agent_event("agent_action_start", {
        "tool_name": "browser_navigate",
        "action_title": "Navigate Browser",
        "detail": clean_url,
        "icon": "globe"
    })

    try:
        page = await _ensure_browser_session(headed=effective_headed, use_brave=use_brave)
        await page.goto(clean_url, wait_until="domcontentloaded", timeout=25000)
        title = await page.title()

        msg = f"Navigated successfully to '{title or clean_url}' (URL: {page.url})."
        _emit_agent_event("agent_action_complete", {
            "tool_name": "browser_navigate",
            "action_title": "Page Navigated",
            "detail": title,
            "summary": msg,
            "icon": "globe"
        })

        return {
            "status": "success",
            "url": page.url,
            "title": title,
            "headed": effective_headed,
            "message": msg
        }
    except Exception as e:
        logger.error(f"[BrowserTools] Navigate error: {e}")
        return {"status": "error", "message": f"Failed to open URL: {e}"}


async def _tool_browser_click(selector_or_text: str) -> Dict[str, Any]:
    """Clicks an interactive element on the current page by CSS selector or text."""
    target = (selector_or_text or "").strip()
    if not target:
        return {"status": "error", "message": "Selector or target text cannot be empty."}

    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open. Call 'browser_navigate' first."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "browser_click",
        "action_title": "Click Element",
        "detail": target,
        "icon": "mouse-pointer"
    })

    try:
        page = _ACTIVE_PAGE
        # Try CSS selector first
        clicked = False
        try:
            await page.click(target, timeout=4000)
            clicked = True
        except Exception:
            pass

        # Try clicking by text or role if CSS selector failed
        if not clicked:
            try:
                locator = page.get_by_text(target, exact=False).first
                await locator.click(timeout=4000)
                clicked = True
            except Exception:
                pass

        # Try locator by attribute or tag if previous attempts failed
        if not clicked:
            try:
                locator = page.locator(target).first
                if await locator.count() > 0:
                    await locator.click(timeout=4000)
                    clicked = True
            except Exception:
                pass

        if clicked:
            await page.wait_for_timeout(1000)
            title = await page.title()
            msg = f"Clicked '{target}' successfully (Current page: {title})."
            return {"status": "success", "url": page.url, "title": title, "message": msg}
        else:
            return {"status": "error", "message": f"Element '{target}' could not be located or clicked on current page."}
    except Exception as e:
        logger.error(f"[BrowserTools] Click error: {e}")
        return {"status": "error", "message": f"Failed to click: {e}"}


async def _tool_browser_type(selector: str, text: str, press_enter: bool = False) -> Dict[str, Any]:
    """Types text into an input field identified by selector, optionally pressing Enter."""
    sel = (selector or "").strip()
    val = str(text or "").strip()

    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open. Call 'browser_navigate' first."}

    try:
        page = _ACTIVE_PAGE
        loc = page.locator(sel).first
        if await loc.count() == 0:
            # Common search input fallbacks
            for alt in ["input[name='search_query']", "input[type='search']", "input[type='text']", "textarea"]:
                alt_loc = page.locator(alt).first
                if await alt_loc.count() > 0:
                    loc = alt_loc
                    break

        await loc.fill(val, timeout=5000)
        if press_enter:
            await loc.press("Enter")
            await page.wait_for_timeout(1500)

        msg = f"Typed '{val}' into input '{sel}' successfully."
        return {"status": "success", "url": page.url, "message": msg}
    except Exception as e:
        logger.error(f"[BrowserTools] Type error: {e}")
        return {"status": "error", "message": f"Failed to type: {e}"}


async def _tool_browser_snapshot() -> Dict[str, Any]:
    """Returns a clean accessibility summary of interactive elements on the current page."""
    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open."}

    try:
        page = _ACTIVE_PAGE
        title = await page.title()
        url = page.url

        # Extract top interactive elements cleanly
        elements = await page.evaluate("""() => {
            const items = [];
            const interactive = document.querySelectorAll('button, a, input, textarea, [role="button"]');
            for (let el of Array.from(interactive).slice(0, 35)) {
                const text = (el.innerText || el.placeholder || el.getAttribute('aria-label') || el.value || '').trim();
                if (text && text.length < 80) {
                    items.push({
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        id: el.id || null,
                        selector: el.id ? '#' + el.id : (el.className ? '.' + el.className.split(' ')[0] : el.tagName.toLowerCase())
                    });
                }
            }
            return items;
        }""")

        return {
            "status": "success",
            "url": url,
            "title": title,
            "interactive_elements_count": len(elements),
            "elements": elements
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to capture snapshot: {e}"}


async def _tool_browser_screenshot(filename: Optional[str] = None) -> Dict[str, Any]:
    """Captures a screenshot of the current page and saves it to staging directory."""
    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open."}

    try:
        page = _ACTIVE_PAGE
        staging_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "staging", "screenshots"))
        os.makedirs(staging_dir, exist_ok=True)

        safe_name = re.sub(r'[^\w\-_\.]', '_', filename or f"screenshot_{int(asyncio.get_event_loop().time())}.png")
        if not safe_name.endswith(".png"):
            safe_name += ".png"
        out_path = os.path.join(staging_dir, safe_name)

        await page.screenshot(path=out_path, full_page=False)
        logger.info(f"[BrowserTools] Screenshot saved: {out_path}")
        return {
            "status": "success",
            "file_path": out_path,
            "filename": safe_name,
            "message": f"Screenshot saved successfully: {out_path}"
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to capture screenshot: {e}"}


async def _tool_browser_close() -> Dict[str, Any]:
    """Closes the current browser automation session."""
    global _ACTIVE_BROWSER, _ACTIVE_CONTEXT, _ACTIVE_PAGE, _CURRENT_HEADED_STATE
    async with _LOCK:
        if _ACTIVE_PAGE:
            try:
                await _ACTIVE_PAGE.close()
            except Exception:
                pass
            _ACTIVE_PAGE = None
        if _ACTIVE_CONTEXT:
            try:
                await _ACTIVE_CONTEXT.close()
            except Exception:
                pass
            _ACTIVE_CONTEXT = None
        if _ACTIVE_BROWSER:
            try:
                await _ACTIVE_BROWSER.close()
            except Exception:
                pass
            _ACTIVE_BROWSER = None
        _CURRENT_HEADED_STATE = None

    return {"status": "success", "message": "Browser session closed successfully."}


async def _tool_browser_scroll(direction: str = "down", amount: int = 500) -> Dict[str, Any]:
    """Scrolls the current browser page up or down."""
    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open."}

    dir_clean = (direction or "down").strip().lower()
    scroll_amt = max(100, int(amount or 500))
    delta_y = scroll_amt if dir_clean in ("down", "bawah") else -scroll_amt

    try:
        page = _ACTIVE_PAGE
        if dir_clean == "top":
            await page.evaluate("window.scrollTo(0, 0)")
        elif dir_clean in ("bottom", "end"):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        else:
            await page.mouse.wheel(0, delta_y)

        await page.wait_for_timeout(300)
        return {"status": "success", "message": f"Page scrolled {dir_clean} ({scroll_amt}px)."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to scroll page: {e}"}


async def _tool_browser_press(key: str) -> Dict[str, Any]:
    """Presses a keyboard key on the active browser page (e.g. Enter, Escape, Tab, ArrowDown, Backspace)."""
    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open."}

    clean_key = (key or "").strip()
    if not clean_key:
        return {"status": "error", "message": "Parameter 'key' is required (e.g. 'Enter', 'Escape', 'Tab')."}

    try:
        page = _ACTIVE_PAGE
        await page.keyboard.press(clean_key)
        await page.wait_for_timeout(300)
        return {"status": "success", "message": f"Key '{clean_key}' pressed successfully."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to press key '{clean_key}': {e}"}


async def _tool_browser_back() -> Dict[str, Any]:
    """Navigates back to the previous page in history."""
    if not _ACTIVE_PAGE or _ACTIVE_PAGE.is_closed():
        return {"status": "error", "message": "No active browser session open."}

    try:
        page = _ACTIVE_PAGE
        await page.go_back()
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        return {
            "status": "success",
            "url": page.url,
            "title": await page.title(),
            "message": f"Navigated back to previous page: {page.url}"
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to navigate back: {e}"}

