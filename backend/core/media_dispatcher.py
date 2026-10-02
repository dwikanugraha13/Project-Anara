"""
media_dispatcher.py — Omnichannel Media & Artifact Dispatcher for Project Anara.
Detects MEDIA:<path> and [[audio_as_voice]] directives and dispatches files
directly as native photos, videos, voice bubbles, audio, and documents across channels.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Dict, Any, List

logger = logging.getLogger("anara.media_dispatcher")

_MEDIA_TAG_RE = re.compile(
    r'[`"\'*_]{0,3}MEDIA:\s*([A-Za-z]:[/\\][^\s`"\'*]+|/(?:Users|home|tmp|var|etc|\.|\w)[^\s`"\'*]+|~/[^\s`"\'*]+)[`"\'*_]{0,3}'
)
_VOICE_DIRECTIVE_RE = re.compile(r'\[\[audio_as_voice\]\]', re.IGNORECASE)


async def _auto_dispatch_artifacts_to_channel(channel: str, channel_id: str, artifacts: List[Dict[str, Any]]) -> None:
    """Auto-dispatches generated documents and media directly to target channel via ChannelManager (Anara Standard)."""
    if not artifacts or not channel_id or channel_id.startswith("default"):
        return
    from integrations.manager import channel_manager
    for art in artifacts:
        f_path = art.get("path")
        f_name = art.get("filename") or (os.path.basename(f_path) if f_path else "")
        if not f_path or not os.path.isfile(f_path):
            continue
        try:
            sz_bytes = os.path.getsize(f_path)
            max_size_bytes = 25 * 1024 * 1024 if channel == "discord" else 48 * 1024 * 1024
            if sz_bytes > max_size_bytes:
                sz_mb = sz_bytes / (1024 * 1024)
                logger.warning(f"[AutoDispatch] Media '{f_name}' exceeds upload limit ({sz_mb:.1f}MB). Delivering local path notice.")
                await channel_manager.send_message(
                    channel=channel,
                    target_id=channel_id,
                    text=f"📁 Generated file <code>{f_name}</code> ({sz_mb:.1f} MB) exceeds upload limit. Stored at:\n<code>{f_path}</code>"
                )
                continue

            logger.info(f"[AutoDispatch] Dispatching media '{f_name}' to {channel} {channel_id}")
            ext = os.path.splitext(f_name)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                media_type = "photo"
                caption = f"📸 Screenshot: {f_name}" if ("screen" in f_name.lower() or "verify" in f_name.lower()) else f"📸 {f_name}"
            elif ext in (".mp4", ".mov", ".avi", ".mkv"):
                media_type = "video"
                caption = f"🎬 {f_name}"
            elif ext in (".mp3", ".m4a", ".wav"):
                media_type = "audio"
                caption = f"🎵 {f_name}"
            elif ext in (".ogg", ".opus"):
                media_type = "voice"
                caption = ""
            else:
                media_type = "document"
                caption = f"📄 File: {f_name}"

            await channel_manager.send_media(
                channel=channel,
                target_id=channel_id,
                file_path=f_path,
                caption=caption,
                media_type=media_type
            )
        except Exception as e:
            logger.error(f"[AutoDispatch] Failed to dispatch '{f_name}' to {channel}: {e}")


async def _extract_and_dispatch_media_tags(channel: str, channel_id: str, text: str) -> str:
    """
    Extracts native MEDIA:<path> and [[audio_as_voice]] directives (Anara Omnichannel Standard).
    Dispatches matched files as native photos/videos/audio/voice/documents, and strips tags from chat text.
    """
    if not text or ("MEDIA:" not in text and "[[audio_as_voice]]" not in text):
        return text

    is_voice_directive = bool(_VOICE_DIRECTIVE_RE.search(text))
    cleaned_text = _VOICE_DIRECTIVE_RE.sub("", text)
    if "MEDIA:" not in cleaned_text or not channel_id or channel_id.startswith("default"):
        return re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()

    from integrations.manager import channel_manager

    def _replace_tag(match: re.Match) -> str:
        raw_path = match.group(1).strip()
        expanded_path = os.path.expanduser(raw_path)
        if os.path.isfile(expanded_path):
            f_name = os.path.basename(expanded_path)
            ext = os.path.splitext(f_name)[1].lower()
            if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                media_type = "photo"
                caption = f"📸 {f_name}"
            elif ext in (".mp4", ".mov", ".avi", ".mkv"):
                media_type = "video"
                caption = f"🎬 {f_name}"
            elif ext in (".ogg", ".opus") or (is_voice_directive and ext in (".mp3", ".m4a", ".wav")):
                media_type = "voice"
                caption = ""
            elif ext in (".mp3", ".m4a", ".wav"):
                media_type = "audio"
                caption = f"🎵 {f_name}"
            else:
                media_type = "document"
                caption = f"📄 {f_name}"

            asyncio.create_task(
                channel_manager.send_media(
                    channel=channel,
                    target_id=channel_id,
                    file_path=expanded_path,
                    caption=caption,
                    media_type=media_type,
                )
            )
            return ""
        return match.group(0)

    cleaned_text = _MEDIA_TAG_RE.sub(_replace_tag, cleaned_text)
    return re.sub(r'\n{3,}', '\n\n', cleaned_text).strip()
