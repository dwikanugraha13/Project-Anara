"""
Media & Playlist Controller for Project Anara WebSocket session.
Handles real-time YouTube music/video playback, queuing, and playlist navigation.
"""
import logging
from typing import Optional, Dict, Any, List, Callable
from fastapi import WebSocket
from memory import memory_engine
from integrations import search_youtube

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
        await self.websocket.send_json(payload)
        try:
            memory_engine.log_media_play(
                self.get_speaker_name(),
                kind=kind,
                video_id=track.get("video_id", ""),
                title=track.get("title", ""),
                channel=track.get("channel", ""),
                thumbnail=track.get("thumbnail", ""),
                duration=track.get("duration", ""),
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
                memory_engine.set_playlist_last_index(int(pid), new_idx)
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
                tracks = await search_youtube(intent["query"], kind="music", limit=8)
                if not tracks:
                    miss = f"Maaf, Anara tidak menemukan lagu untuk playlist '{intent['name']}'."
                    await self.websocket.send_json({"type": "transcript", "data": miss, "speaker": "output"})
                    if gemini_service:
                        await gemini_service.send_text(f"Sistem: Ucapkan dengan ramah: {miss}")
                    return
                res = memory_engine.save_playlist(intent["name"], tracks, speaker_name)
                done = f"Playlist '{res.get('name')}' siap dengan {res.get('count')} lagu. Anara mulai putar ya."
                await self.websocket.send_json({"type": "transcript", "data": done, "speaker": "output"})
                if gemini_service:
                    await gemini_service.send_text(f"Sistem: Ucapkan dengan ceria: {done}")
                await self.send_media_play(
                    tracks[0], "music", tracks[1:],
                    playlist={"id": res.get("id"), "name": res.get("name"), "tracks": tracks, "index": 0}
                )
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
                    msg = "Belum ada lagu yang sedang diputar untuk ditambahkan."
                    await self.websocket.send_json({"type": "transcript", "data": msg, "speaker": "output"})
                    if gemini_service:
                        await gemini_service.send_text(f"Sistem: Ucapkan dengan ramah: {msg}")
                    return
                memory_engine.add_track_to_playlist(intent["name"], self.now_playing, speaker_name)
                return

            elif kind == "media_history":
                tracks = intent.get("tracks") or []
                if tracks:
                    await self.websocket.send_json({
                        "type": "hud_visual",
                        "data": intent.get("reply_text", "Riwayat musik diproyeksikan"),
                        "visualType": "knowledge_card",
                        "knowledgeCardData": {
                            "title": "Lagu Paling Sering Diputar",
                            "category": "Riwayat Musik",
                            "badge": f"{len(tracks)} lagu",
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
                        "data": intent.get("reply_text", "Daftar playlist tersimpan"),
                        "visualType": "knowledge_card",
                        "knowledgeCardData": {
                            "title": "Playlist Tersimpan",
                            "category": "Koleksi Musik",
                            "badge": f"{len(pls)} playlist",
                            "summary": "",
                            "steps": [f"{p.get('name')} — {p.get('track_count', 0)} lagu" for p in pls],
                        },
                        "mediaType": "hud"
                    })
                return
        except Exception as e:
            logger.error(f"[Playlist] Handler failed: {repr(e)}", exc_info=True)
