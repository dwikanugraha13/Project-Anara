"""
Media & Playlist Controller for Project Anara WebSocket session.
Handles real-time YouTube music/video playback, queuing, and playlist navigation.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from fastapi import WebSocket
from memory import memory_engine
from integrations import search_youtube
from core.prompt_loader import load_config_yaml, _safe_format

logger = logging.getLogger("anara.websocket.media")

class MediaController:
    def __init__(
        self,
        websocket: WebSocket,
        get_gemini_service: Callable[[], Any],
        get_speaker_name: Callable[[], str],
    ):
        self.websocket = websocket
        self.get_gemini_service = get_gemini_service
        self.get_speaker_name = get_speaker_name
        self.now_playing: Optional[Dict[str, Any]] = None
        self.active_playlist: Optional[Dict[str, Any]] = None

    async def send_media_play(
        self,
        track: Dict[str, Any],
        kind: str = "music",
        queue: Optional[List[Dict[str, Any]]] = None,
        playlist: Optional[Dict[str, Any]] = None,
    ):
        """Dispatches media playback payload to frontend and logs to memory engine."""
        self.now_playing = track
        if playlist is not None:
            self.active_playlist = playlist
        payload = {
            "type": "media_play",
            "track": track,
            "kind": kind,
            "queue": queue or [],
            "playlist": playlist,
        }
        try:
            await self.websocket.send_json(payload)
        except Exception as e:
            logger.debug(f"[MediaController] Send media play notice: {e}")

        try:
            speaker = self.get_speaker_name() or "default"
            await asyncio.to_thread(
                memory_engine.log_media_play,
                speaker,
                track,
                kind=kind,
            )
        except Exception as e:
            logger.debug(f"[MediaEngine] Log play error: {e}")

    async def playlist_jump(self, step: int) -> bool:
        """Navigates forward or backward through the active playlist queue."""
        if not self.active_playlist:
            return False
        tracks = self.active_playlist.get("tracks") or []
        if not tracks:
            return False
        cur_idx = int(self.active_playlist.get("index") or 0)
        new_idx = cur_idx + step
        if new_idx < 0 or new_idx >= len(tracks):
            return False
        self.active_playlist["index"] = new_idx
        track = tracks[new_idx]
        queue = tracks[new_idx + 1:]
        pid = self.active_playlist.get("id")
        if pid:
            try:
                await asyncio.to_thread(memory_engine.set_playlist_position, int(pid), new_idx)
            except Exception:
                pass
        await self.send_media_play(track, "music", queue, playlist=self.active_playlist)
        return True

    async def handle_playlist_intent(self, intent: Dict[str, Any], user_text: str):
        """Executes high-level user playlist commands (create, jump, add track, list)."""
        kind = intent.get("type")
        speaker_name = self.get_speaker_name()
        gemini_service = self.get_gemini_service()

        try:
            if kind == "playlist_create":
                q = intent.get("query") or intent.get("name") or user_text or ""
                pl_name = intent.get("name") or q or "Playlist"
                tracks = await search_youtube(q, kind="music", limit=8)
                if not tracks:
                    if gemini_service:
                        live_cfg = load_config_yaml("voice/live_directives.yaml", default={})
                        tpl = live_cfg.get(
                            "playlist_not_found",
                            "[SYSTEM NOTIFICATION]: No tracks were found for playlist query '{query}'. Inform the user in their active language."
                        )
                        nf_cmd = _safe_format(tpl, query=pl_name)
                        await gemini_service.send_text(nf_cmd)
                    return
                res = await asyncio.to_thread(memory_engine.save_playlist, pl_name, tracks, speaker_name)
                if gemini_service:
                    live_cfg = load_config_yaml("voice/live_directives.yaml", default={})
                    tpl = live_cfg.get(
                        "playlist_ready",
                        "[SYSTEM NOTIFICATION]: Playlist '{name}' with {count} tracks is ready and playing. Inform the user in their active language."
                    )
                    rdy_cmd = _safe_format(tpl, name=res.get("name", pl_name), count=res.get("count", len(tracks)))
                    await gemini_service.send_text(rdy_cmd)
                await self.send_media_play(
                    tracks[0], "music", tracks[1:],
                    playlist={"id": res.get("id"), "name": res.get("name", pl_name), "tracks": tracks, "index": 0}
                )
                return

            elif kind in ("playlist_next", "media_next"):
                await self.playlist_jump(1)
                return

            elif kind in ("playlist_prev", "media_previous", "media_prev"):
                await self.playlist_jump(-1)
                return

            elif kind == "playlist_jump":
                step = int(intent.get("step") or 1)
                await self.playlist_jump(step)
                return

            elif kind == "playlist_play":
                tracks = intent.get("tracks") or []
                idx = int(intent.get("start_index") or 0)
                if not tracks:
                    return
                idx = max(0, min(idx, len(tracks) - 1))
                await self.send_media_play(
                    tracks[idx], "music", tracks[idx + 1:],
                    playlist={"id": intent.get("playlist_id"), "name": intent.get("name"), "tracks": tracks, "index": idx}
                )
                return

            elif kind == "playlist_add_current":
                if not self.now_playing:
                    if gemini_service:
                        live_cfg = load_config_yaml("voice/live_directives.yaml", default={})
                        no_track_cmd = live_cfg.get(
                            "no_media_playing",
                            "[SYSTEM NOTIFICATION]: No media track is currently playing to add to a playlist. Inform the user in their active language."
                        )
                        await gemini_service.send_text(no_track_cmd)
                    return
                pl_name = intent.get("name") or "Favorites"
                await asyncio.to_thread(memory_engine.add_track_to_playlist, pl_name, self.now_playing, speaker_name)
                return

            elif kind == "media_history":
                tracks = intent.get("tracks") or []
                if tracks:
                    await self.websocket.send_json({
                        "type": "hud_visual",
                        "data": intent.get("reply_text", "Music history"),
                        "visualType": "knowledge_card",
                        "knowledgeCardData": {
                            "title": "Most Played Tracks",
                            "category": "Music History",
                            "badge": f"{len(tracks)} tracks",
                            "summary": "",
                            "steps": [f"{t.get('title')} — {t.get('plays')}x" for t in tracks],
                        },
                        "mediaType": "hud"
                    })
                return

            elif kind == "playlist_list":
                pls = intent.get("playlists") or []
                if pls:
                    await self.websocket.send_json({
                        "type": "hud_visual",
                        "data": intent.get("reply_text", "Saved playlists"),
                        "visualType": "knowledge_card",
                        "knowledgeCardData": {
                            "title": "Saved Playlists",
                            "category": "Music Collection",
                            "badge": f"{len(pls)} playlists",
                            "summary": "",
                            "steps": [f"{p.get('name')} — {p.get('track_count', 0)} tracks" for p in pls],
                        },
                        "mediaType": "hud"
                    })
                return
        except Exception as e:
            logger.error(f"[Playlist] Handler failed: {repr(e)}", exc_info=True)
