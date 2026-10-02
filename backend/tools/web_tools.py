import asyncio
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, Optional, Set
import httpx

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

_BACKGROUND_TASKS: Set[asyncio.Task] = set()


def _safe_create_task(coro) -> asyncio.Task:
    """Creates a background task and maintains a strong reference to prevent GC eviction."""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def _is_safe_public_url(url: str) -> tuple[bool, Optional[str]]:
    """SSRF & DNS rebinding safety barrier with non-blocking async DNS resolution."""
    try:
        from urllib.parse import urlparse
        import ipaddress
        import socket
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, f"Unsupported scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False, "Target URL missing valid hostname."
        if host in ("localhost", "metadata.google.internal", "instance-data"):
            return False, f"Access to internal host '{host}' is forbidden."

        loop = asyncio.get_running_loop()
        try:
            addr_info = await loop.getaddrinfo(host, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_unspecified
                    or ip.is_multicast
                    or ip in ipaddress.ip_network("100.64.0.0/10")
                ):
                    return False, f"Access to private/internal network IP '{ip_str}' is forbidden."
        except socket.gaierror:
            return False, f"Could not resolve hostname '{host}'."
        return True, None
    except Exception as e:
        return False, f"Invalid URL: {e}"


async def _tool_web_search(query: str) -> Dict[str, Any]:
    """Searches the live web via DuckDuckGo HTML index for real-time answers."""
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Search query cannot be empty."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "web_search",
        "action_title": "Web Search",
        "detail": f"Query: '{q}'",
        "icon": "globe"
    })

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "*",
    }

    snippets = []
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.post(url, headers=headers, data={"q": q})
            if res.status_code == 200:
                results = re.findall(
                    r'<a class="result__snippet[^>]*>(.*?)</a>',
                    res.text,
                    re.DOTALL
                )
                for r in results[:4]:
                    clean = re.sub(r"<[^>]+>", "", r).strip()
                    clean = clean.replace("&quot;", '"').replace("&#x27;", "'").replace("&amp;", "&")
                    if clean and len(clean) > 20:
                        snippets.append(clean)
    except Exception as e:
        logger.warning(f"[AgentTools] Web search error: {e}")

    if not snippets:
        try:
            wiki_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}&format=json&utf8="
            wiki_headers = {
                "User-Agent": "AnaraAgent/1.0 (https://project-anara.local; contact@anara.local)",
                "Accept": "application/json"
            }
            async with httpx.AsyncClient(timeout=5.0) as client:
                w_res = await client.get(wiki_url, headers=wiki_headers)
                if w_res.status_code == 200:
                    w_data = w_res.json()
                    for item in w_data.get("query", {}).get("search", [])[:3]:
                        snip = re.sub(r"<[^>]+>", "", item.get("snippet", "")).strip()
                        if snip:
                            snippets.append(f"[{item.get('title')}] {snip}")
        except Exception:
            pass

    result_text = "\n---\n".join(snippets) if snippets else "No specific web results found."
    
    _emit_agent_event("agent_action_complete", {
        "tool_name": "web_search",
        "action_title": "Web Search Results",
        "summary": result_text[:200] + "..." if len(result_text) > 200 else result_text,
        "raw_result": result_text,
        "icon": "globe"
    })

    return {
        "status": "success" if snippets else "no_results",
        "query": q,
        "search_results": result_text
    }


async def _tool_fetch_webpage(url: str) -> Dict[str, Any]:
    """Fetches and cleans main text content from a web URL with SSRF protection."""
    target_url = (url or "").strip()
    is_safe, denial_reason = await _is_safe_public_url(target_url)
    if not is_safe:
        return {"status": "error", "message": f"SSRF Blocked: {denial_reason}"}

    _emit_agent_event("agent_action_start", {
        "tool_name": "fetch_webpage",
        "action_title": "Fetch Webpage",
        "detail": f"URL: {target_url[:50]}...",
        "icon": "globe"
    })

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "*"}

        async def _check_redirect(response: httpx.Response):
            if response.is_redirect and "location" in response.headers:
                redirect_url = str(response.url.join(response.headers["location"]))
                safe, reason = await _is_safe_public_url(redirect_url)
                if not safe:
                    raise httpx.RequestError(f"SSRF blocked on redirect to '{redirect_url}': {reason}")

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, event_hooks={"response": [_check_redirect]}) as client:
            res = await client.get(target_url, headers=headers)
            if res.status_code != 200:
                return {"status": "error", "message": f"Failed to fetch URL: HTTP {res.status_code}"}
            
            cl = res.headers.get("Content-Length")
            if cl and cl.isdigit() and int(cl) > 10 * 1024 * 1024:
                return {"status": "error", "message": "Content too large (exceeds 10MB limit)."}

            html = res.text
            clean = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r"<style.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()

            preview = clean[:4000]
            _emit_agent_event("agent_action_complete", {
                "tool_name": "fetch_webpage",
                "action_title": "Webpage Content Fetched",
                "summary": f"Successfully fetched {len(clean)} characters.",
                "raw_result": preview[:250],
                "icon": "globe"
            })

            return {
                "status": "success",
                "url": target_url,
                "total_chars": len(clean),
                "content": preview
            }
    except Exception as e:
        logger.warning(f"[AgentTools] Webpage fetch error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_custom_webhook(url: str, method: str = "POST", payload_json: Optional[str] = None) -> Dict[str, Any]:
    """Triggers an external automation webhook with SSRF protection."""
    target_url = (url or "").strip()
    is_safe, denial_reason = await _is_safe_public_url(target_url)
    if not is_safe:
        return {"status": "error", "message": f"SSRF Blocked: {denial_reason}"}

    method_clean = (method or "POST").upper()
    if method_clean not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return {"status": "error", "message": f"Unsupported HTTP method: {method_clean}"}

    _emit_agent_event("agent_action_start", {
        "tool_name": "custom_webhook",
        "action_title": "Automation Webhook Execution",
        "detail": f"Target: {target_url} [{method_clean}]",
        "icon": "⚡"
    })

    parsed_payload = {}
    if payload_json:
        try:
            parsed_payload = json.loads(payload_json)
        except Exception:
            parsed_payload = {"raw_data": payload_json}

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            if method_clean == "GET":
                res = await client.get(target_url, params=parsed_payload)
            elif method_clean == "DELETE":
                res = await client.delete(target_url, params=parsed_payload)
            elif method_clean == "PUT":
                res = await client.put(target_url, json=parsed_payload)
            elif method_clean == "PATCH":
                res = await client.patch(target_url, json=parsed_payload)
            else:
                res = await client.post(target_url, json=parsed_payload)

        res_text = res.text[:500]
        _emit_agent_event("agent_action_complete", {
            "tool_name": "custom_webhook",
            "action_title": "Webhook Sent",
            "summary": f"Status: HTTP {res.status_code}",
            "raw_result": res_text,
            "icon": "⚡"
        })

        return {"status": "success", "http_code": res.status_code, "response": res_text}
    except Exception as e:
        logger.warning(f"[AgentTools] Webhook error: {e}")
        return {"status": "error", "message": str(e)}


async def _tool_web_search_images(query: str, limit: int = 4) -> Dict[str, Any]:
    """
    Searches the live web for actual image photos, news documentation, or visuals matching query.
    Returns image URLs, thumbnails, titles, and automatically projects them or sends to chat.
    """
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Image search query cannot be empty."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "web_search_images",
        "action_title": "Web Image Search",
        "detail": f"Search: '{q}'",
        "icon": "image"
    })

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "*",
    }

    images = []
    try:
        bing_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(q)}&first=1"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            r = await client.get(bing_url, headers=headers)
            if r.status_code == 200:
                m_tags = re.findall(r'm="([^"]+)"', r.text)
                for m_raw in m_tags[:max(1, limit * 2)]:
                    try:
                        clean_json = m_raw.replace("&quot;", '"').replace("&amp;", "&")
                        d = json.loads(clean_json)
                        img_url = d.get("murl")
                        if img_url and img_url.startswith("http"):
                            images.append({
                                "image_url": img_url,
                                "thumbnail_url": d.get("turl") or img_url,
                                "title": d.get("t", q),
                                "source_domain": d.get("desc", ""),
                                "markdown": f"![{d.get('t', q)}]({img_url})"
                            })
                            if len(images) >= limit:
                                break
                    except Exception:
                        continue
    except Exception as e:
        logger.warning(f"[AgentTools] Image search error: {e}")

    # Fallback to Wikimedia Commons API if Bing has no results
    if not images:
        try:
            wiki_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(q)}&gsrnamespace=6&prop=imageinfo&iiprop=url|extmetadata&format=json"
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                res = await client.get(wiki_url, headers=headers)
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for pid, pdata in pages.items():
                        infos = pdata.get("imageinfo", [])
                        if infos and infos[0].get("url"):
                            u = infos[0]["url"]
                            title = pdata.get("title", "").replace("File:", "")
                            images.append({
                                "image_url": u,
                                "thumbnail_url": u,
                                "title": title,
                                "source_domain": "wikimedia.org",
                                "markdown": f"![{title}]({u})"
                            })
                            if len(images) >= limit:
                                break
        except Exception:
            pass

    if not images:
        return {
            "status": "warning",
            "query": q,
            "total_found": 0,
            "images": [],
            "message": f"No specific web photos found for '{q}'."
        }

    # Emit HUD visual card
    first_img = images[0]
    _emit_agent_event("hud_project", {
        "type": "image",
        "title": first_img["title"],
        "image_url": first_img["image_url"],
        "summary": f"Image related to {q} discovered from web."
    })

    # Auto-dispatch to active remote channel (Telegram / WhatsApp) if user is mobile
    try:
        from core.channel_adapter import get_active_channel_context
        ctx = get_active_channel_context()
        if ctx and ctx.get("channel") == "telegram" and ctx.get("channel_id"):
            from integrations.telegram import send_telegram_photo
            _safe_create_task(send_telegram_photo(
                photo=first_img["image_url"],
                chat_id=ctx["channel_id"],
                caption=f"📷 {first_img['title']}"
            ))
            logger.info(f"[ImageSearch] Auto-sent photo to Telegram chat {ctx['channel_id']}: {first_img['image_url']}")
    except Exception as dispatch_err:
        logger.debug(f"[ImageSearch] Auto-dispatch error: {dispatch_err}")

    return {
        "status": "success",
        "query": q,
        "total_found": len(images),
        "primary_image_url": first_img["image_url"],
        "images": images,
        "message": f"Found {len(images)} photos for '{q}'. First photo has been processed for direct delivery to chat."
    }

