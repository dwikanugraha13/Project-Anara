import json
import logging
import re
import urllib.parse
from typing import Any, Dict, Optional
import httpx

from .events import _emit_agent_event

logger = logging.getLogger(__name__)


async def _tool_web_search(query: str) -> Dict[str, Any]:
    """Searches the live web via DuckDuckGo HTML index for real-time answers."""
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Query pencarian kosong"}

    _emit_agent_event("agent_action_start", {
        "tool_name": "web_search",
        "action_title": "Pencarian Web Real-time",
        "detail": f"Mencari: '{q}'",
        "icon": "🌐"
    })

    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
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
            wiki_url = f"https://id.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(q)}&format=json&utf8="
            async with httpx.AsyncClient(timeout=5.0) as client:
                w_res = await client.get(wiki_url)
                if w_res.status_code == 200:
                    w_data = w_res.json()
                    for item in w_data.get("query", {}).get("search", [])[:3]:
                        snip = re.sub(r"<[^>]+>", "", item.get("snippet", "")).strip()
                        if snip:
                            snippets.append(f"[{item.get('title')}] {snip}")
        except Exception:
            pass

    result_text = "\n---\n".join(snippets) if snippets else "Tidak ditemukan hasil spesifik di web."
    
    _emit_agent_event("agent_action_complete", {
        "tool_name": "web_search",
        "action_title": "Hasil Pencarian Web",
        "summary": result_text[:200] + "..." if len(result_text) > 200 else result_text,
        "raw_result": result_text,
        "icon": "🌐"
    })

    return {
        "status": "success" if snippets else "no_results",
        "query": q,
        "search_results": result_text
    }


async def _tool_fetch_webpage(url: str) -> Dict[str, Any]:
    """Fetches and cleans main text content from a web URL."""
    target_url = (url or "").strip()
    if not target_url.startswith("http"):
        return {"status": "error", "message": "URL harus diawali dengan http:// atau https://"}

    _emit_agent_event("agent_action_start", {
        "tool_name": "fetch_webpage",
        "action_title": "Membaca Webpage Lengkap",
        "detail": f"URL: {target_url[:50]}...",
        "icon": "🌐"
    })

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            res = await client.get(target_url, headers=headers)
            if res.status_code != 200:
                return {"status": "error", "message": f"Gagal membuka URL: HTTP {res.status_code}"}
            
            html = res.text
            clean = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r"<style.*?</style>", "", clean, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()

            preview = clean[:4000]
            _emit_agent_event("agent_action_complete", {
                "tool_name": "fetch_webpage",
                "action_title": "Konten Web Diambil",
                "summary": f"Berhasil membaca {len(clean)} karakter.",
                "raw_result": preview[:250],
                "icon": "🌐"
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
    """Triggers an external automation webhook."""
    target_url = (url or "").strip()
    if not target_url.startswith("http"):
        return {"status": "error", "message": "URL Webhook harus berawalan http:// atau https://"}

    _emit_agent_event("agent_action_start", {
        "tool_name": "custom_webhook",
        "action_title": "Eksekusi Webhook Automasi",
        "detail": f"Target: {target_url}",
        "icon": "⚡"
    })

    method_clean = (method or "POST").upper()
    parsed_payload = {}
    if payload_json:
        try:
            parsed_payload = json.loads(payload_json)
        except Exception:
            parsed_payload = {"raw_data": payload_json}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method_clean == "GET":
                res = await client.get(target_url, params=parsed_payload)
            else:
                res = await client.post(target_url, json=parsed_payload)

        res_text = res.text[:500]
        _emit_agent_event("agent_action_complete", {
            "tool_name": "custom_webhook",
            "action_title": "Webhook Terkirim",
            "summary": f"Status: HTTP {res.status_code}",
            "raw_result": res_text,
            "icon": "⚡"
        })

        return {"status": "success", "http_code": res.status_code, "response": res_text}
    except Exception as e:
        logger.warning(f"[AgentTools] Webhook error: {e}")
        return {"status": "error", "message": str(e)}
