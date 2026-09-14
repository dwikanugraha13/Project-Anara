import asyncio
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)

_HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

_MEDIA_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_MEDIA_CACHE_MAX = 64


def _parse_duration_text(item: Dict[str, Any]) -> str:
    """Extracts a human duration like '4:32' from a videoRenderer blob."""
    for key in ("lengthText", "thumbnailOverlayTimeStatusRenderer"):
        node = item.get(key)
        if isinstance(node, dict):
            txt = node.get("simpleText")
            if txt:
                return str(txt)
    overlays = item.get("thumbnailOverlays") or []
    for ov in overlays:
        st = (ov or {}).get("thumbnailOverlayTimeStatusRenderer") or {}
        txt = (st.get("text") or {}).get("simpleText")
        if txt:
            return str(txt)
    return ""


def _normalize_duration_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if ":" not in t and "." in t:
        t = t.replace(".", ":")
    return t


def _duration_to_seconds(text: str) -> int:
    t = _normalize_duration_text(text)
    if not t:
        return 0
    parts = [p for p in t.split(":") if p.isdigit()]
    if not parts:
        return 0
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total


def _extract_renderers(html: str) -> List[Dict[str, Any]]:
    m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html, re.DOTALL)
    if not m:
        m = re.search(r'ytInitialData"\]\s*=\s*(\{.*?\});', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    renderers: List[Dict[str, Any]] = []

    def walk(node: Any):
        if isinstance(node, dict):
            if "videoRenderer" in node and isinstance(node["videoRenderer"], dict):
                renderers.append(node["videoRenderer"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return renderers


def _renderer_to_track(vr: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    video_id = vr.get("videoId")
    if not video_id:
        return None

    title = ""
    title_node = vr.get("title") or {}
    if title_node.get("simpleText"):
        title = title_node["simpleText"]
    else:
        runs = title_node.get("runs") or []
        title = "".join(r.get("text", "") for r in runs)
    title = title.strip()
    if not title:
        return None

    channel = ""
    for key in ("ownerText", "longBylineText", "shortBylineText"):
        node = vr.get(key) or {}
        runs = node.get("runs") or []
        if runs:
            channel = (runs[0].get("text") or "").strip()
            if channel:
                break

    thumb = ""
    thumbs = ((vr.get("thumbnail") or {}).get("thumbnails")) or []
    if thumbs:
        thumb = thumbs[-1].get("url", "")
    if not thumb:
        thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    duration_text = _normalize_duration_text(_parse_duration_text(vr))

    return {
        "video_id": video_id,
        "title": title,
        "channel": channel or "YouTube",
        "thumbnail": thumb,
        "duration": duration_text,
        "duration_seconds": _duration_to_seconds(duration_text),
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


async def search_youtube(query: str, kind: str = "music", limit: int = 5) -> List[Dict[str, Any]]:
    """Searches YouTube and returns a list of playable tracks/videos."""
    q = (query or "").strip()
    if not q:
        return []

    search_query = f"{q} official audio" if kind == "music" else q
    cache_key = f"{kind}::{search_query.lower()}"
    if cache_key in _MEDIA_CACHE:
        return _MEDIA_CACHE[cache_key][:limit]

    url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(search_query)
        + "&sp=EgIQAQ%253D%253D"
    )

    html = ""
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            res = await client.get(url, headers=_HEADERS)
            if res.status_code == 200:
                html = res.text
    except Exception as e:
        logger.warning(f"[MediaEngine] YouTube search failed for {q!r}: {e}")
        return []

    if not html:
        return []

    tracks: List[Dict[str, Any]] = []
    seen = set()
    for vr in _extract_renderers(html):
        track = _renderer_to_track(vr)
        if not track or track["video_id"] in seen:
            continue

        secs = track["duration_seconds"]
        if kind == "music":
            if secs and (secs < 40 or secs > 720):
                continue
        else:
            if secs and secs > 3600:
                continue

        seen.add(track["video_id"])
        tracks.append(track)
        if len(tracks) >= max(limit, 5):
            break

    if tracks:
        if len(_MEDIA_CACHE) >= _MEDIA_CACHE_MAX:
            _MEDIA_CACHE.clear()
        _MEDIA_CACHE[cache_key] = tracks
        logger.info(f"[MediaEngine] Found {len(tracks)} {kind} result(s) for {q!r} — top: {tracks[0]['title']!r}")
    else:
        logger.warning(f"[MediaEngine] No {kind} results parsed for {q!r}")

    return tracks[:limit]


async def resolve_media_request(query: str, kind: str = "music") -> Optional[Dict[str, Any]]:
    tracks = await search_youtube(query, kind=kind, limit=5)
    if not tracks:
        return None

    best = tracks[0]
    return {
        "kind": kind,
        "video_id": best["video_id"],
        "title": best["title"],
        "channel": best["channel"],
        "thumbnail": best["thumbnail"],
        "duration": best["duration"],
        "queue": tracks[1:5],
    }
