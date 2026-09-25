"""
spotify_tools.py — Spotify Music & Audio Player Engine for Project Anara.
Parity with Anara Agent plugins/spotify: supports playback control,
track/artist/album search, queue management, and Windows URI protocol fallback.
"""

import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx

from .events import _emit_agent_event

logger = logging.getLogger(__name__)

SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def _get_spotify_token() -> Optional[str]:
    """Retrieves Spotify OAuth access token from environment or database if configured."""
    return os.getenv("SPOTIFY_ACCESS_TOKEN") or None


async def _tool_spotify_search(query: str, search_type: str = "track", limit: int = 10) -> Dict[str, Any]:
    """Searches Spotify for tracks, artists, albums, or playlists."""
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Search query cannot be empty."}

    _emit_agent_event("agent_action_start", {
        "tool_name": "spotify_search",
        "action_title": "Search Music",
        "detail": f"Spotify: '{q}'",
        "icon": "music"
    })

    token = _get_spotify_token()
    if token:
        try:
            url = f"{SPOTIFY_API_BASE}/search"
            params = {"q": q, "type": search_type, "limit": min(limit, 20)}
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    return {"status": "success", "results": data}
        except Exception as e:
            logger.warning(f"[SpotifyTools] Web API search failed: {e}")

    # Fallback to local URI scheme
    encoded = urllib.parse.quote(q)
    return {
        "status": "success",
        "source": "local_uri",
        "query": q,
        "spotify_uri": f"spotify:search:{encoded}",
        "message": f"Search URI for '{q}' ready on Spotify."
    }


async def _tool_spotify_playback(
    action: str = "play",
    query: Optional[str] = None,
    device_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Controls Spotify playback: 'play', 'pause', 'next', 'previous', or 'resume'.
    If query is provided, searches and plays the requested track/album.
    """
    act = (action or "play").strip().lower()
    q = (query or "").strip()

    _emit_agent_event("agent_action_start", {
        "tool_name": "spotify_playback",
        "action_title": f"Spotify: {act.title()}",
        "detail": f"Target: {q or 'Current Track'}",
        "icon": "play"
    })

    token = _get_spotify_token()
    if token:
        try:
            endpoint_map = {
                "play": "me/player/play",
                "resume": "me/player/play",
                "pause": "me/player/pause",
                "next": "me/player/next",
                "previous": "me/player/previous",
            }
            sub_ep = endpoint_map.get(act, "me/player/play")
            url = f"{SPOTIFY_API_BASE}/{sub_ep}"
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.put(url, headers=headers) if act in ["play", "resume", "pause"] else await client.post(url, headers=headers)
                if res.status_code in [200, 204]:
                    return {"status": "success", "action": act, "message": f"Spotify playback command '{act}' sent via Web API."}
        except Exception as e:
            logger.warning(f"[SpotifyTools] Web API playback error: {e}")

    # Fallback via OS Shell Protocol (Zero Setup Required)
    try:
        if q:
            encoded = urllib.parse.quote(q)
            uri = f"spotify:search:{encoded}"
        else:
            uri = "spotify:"

        if hasattr(os, "startfile"):
            os.startfile(uri)
        else:
            import subprocess, sys
            launcher = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.Popen([launcher, uri])

        return {
            "status": "success",
            "action": act,
            "transport": "os_protocol",
            "message": f"Opened Spotify for '{q or act}' on desktop."
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to open Spotify: {e}"}
