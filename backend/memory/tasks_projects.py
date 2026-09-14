import json
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class TasksProjectsMixin:
    """Contacts, settings, notes, to-dos, personal projects, emotion logs, and playlists."""

    def save_contact(self, name: str, phone_number: str, platform: str = "whatsapp", notes: Optional[str] = None) -> Dict[str, Any]:
        """Saves or updates a contact mapping."""
        clean_name = (name or "").strip().title()
        clean_phone = re.sub(r"[^0-9]", "", str(phone_number))
        if clean_phone.startswith("08"):
            clean_phone = "628" + clean_phone[2:]
        elif clean_phone.startswith("8"):
            clean_phone = "628" + clean_phone[1:]

        if not clean_name or len(clean_phone) < 8:
            return {"status": "error", "message": "Nama atau nomor telepon tidak valid."}

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO contacts (name, phone_number, platform, notes, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name, platform) DO UPDATE SET
                    phone_number = excluded.phone_number,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
            """, (clean_name, clean_phone, platform.lower(), notes))
            conn.commit()
            cid = cursor.lastrowid

        logger.info(f"[Contacts] Saved contact: {clean_name} -> {clean_phone} ({platform})")
        self._emit_mutation("contact_saved", {"id": cid, "name": clean_name, "phone": clean_phone})
        return {"status": "ok", "id": cid, "name": clean_name, "phone": clean_phone}

    def get_contact(self, name: str, platform: str = "whatsapp") -> Optional[Dict[str, Any]]:
        """Finds a contact by name (fuzzy / exact)."""
        clean = (name or "").strip().lower()
        if not clean:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contacts WHERE platform = ?", (platform.lower(),))
            rows = [dict(r) for r in cursor.fetchall()]
            match = next((r for r in rows if r["name"].lower() == clean), None)
            if not match:
                match = next((r for r in rows if clean in r["name"].lower() or r["name"].lower() in clean), None)
            return match

    def get_all_contacts(self, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute("SELECT * FROM contacts WHERE platform = ? ORDER BY name ASC", (platform.lower(),))
            else:
                cursor.execute("SELECT * FROM contacts ORDER BY name ASC")
            return [dict(r) for r in cursor.fetchall()]

    def delete_contact(self, contact_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("contact_deleted", {"id": contact_id})
            return ok

    def resolve_contact_phone(self, target: str) -> Optional[str]:
        """Resolves target string to digits only phone number."""
        raw = target.strip()
        digits = re.sub(r"[^0-9]", "", raw)
        if len(digits) >= 9:
            if digits.startswith("08"):
                return "628" + digits[2:]
            elif digits.startswith("8"):
                return "628" + digits[1:]
            return digits

        c = self.get_contact(raw, platform="whatsapp")
        if c:
            return c["phone_number"]
        return None

    def get_app_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves a persistent setting value from the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key.strip(),))
                row = cursor.fetchone()
                return row["value"] if row else default
        except Exception:
            return default

    def set_app_setting(self, key: str, value: str) -> bool:
        """Saves or updates a persistent setting in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """, (key.strip(), str(value)))
                conn.commit()
                return True
        except Exception:
            return False

    def create_note_or_todo(
        self,
        title: str,
        content: str = "",
        category: str = "todo",
        due_date: Optional[str] = None,
        speaker_name: Optional[str] = None
    ) -> int:
        """Creates a new note, to-do, or reminder item in SQLite."""
        speaker_id = None
        if speaker_name:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
                r = cur.fetchone()
                if r:
                    speaker_id = r["id"]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notes_and_todos (speaker_id, category, title, content, is_completed, due_date, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
            """, (speaker_id, category.strip().lower(), title.strip(), content.strip(), due_date))
            conn.commit()
            new_id = cursor.lastrowid or 0
            self._emit_mutation("todo_created", {
                "id": new_id,
                "speaker_name": speaker_name.strip().title() if speaker_name else None,
                "title": title.strip(),
                "category": category.strip().lower()
            })
            return new_id

    def get_notes_and_todos(self, category: Optional[str] = None, speaker_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves active notes and to-dos."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT n.id, n.category, n.title, n.content, n.is_completed, n.due_date,
                       n.created_at, n.updated_at, s.name as speaker_name
                FROM notes_and_todos n
                LEFT JOIN speakers s ON n.speaker_id = s.id
                WHERE 1=1
            """
            params = []
            if category:
                query += " AND n.category = ?"
                params.append(category.strip().lower())
            if speaker_name:
                query += " AND (s.name = ? OR n.speaker_id IS NULL)"
                params.append(speaker_name.strip().title())

            query += " ORDER BY n.is_completed ASC, n.updated_at DESC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def toggle_todo(self, note_id: int) -> bool:
        """Toggles a to-do item between completed and active."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notes_and_todos
                SET is_completed = CASE WHEN is_completed = 1 THEN 0 ELSE 1 END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (note_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("todo_toggled", {"id": note_id})
            return ok

    def delete_note_or_todo(self, note_id: int) -> bool:
        """Deletes a note or to-do by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM notes_and_todos WHERE id = ?", (note_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("todo_deleted", {"id": note_id})
            return ok

    def create_or_update_project(
        self,
        name: str,
        speaker_name: Optional[str] = None,
        tech_stack: str = "",
        goal: str = "",
        status: str = "active",
        notes: str = ""
    ) -> int:
        """Creates or updates an ongoing personal project for a speaker."""
        speaker_id = None
        if speaker_name:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
                r = cur.fetchone()
                if r:
                    speaker_id = r["id"]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM projects WHERE LOWER(name) = LOWER(?) AND (speaker_id = ? OR (speaker_id IS NULL AND ? IS NULL))", (name.strip(), speaker_id, speaker_id))
            existing = cursor.fetchone()
            if existing:
                proj_id = existing["id"]
                cursor.execute("""
                    UPDATE projects
                    SET tech_stack = COALESCE(NULLIF(?, ''), tech_stack),
                        goal = COALESCE(NULLIF(?, ''), goal),
                        status = COALESCE(NULLIF(?, ''), status),
                        notes = COALESCE(NULLIF(?, ''), notes),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (tech_stack.strip(), goal.strip(), status.strip().lower(), notes.strip(), proj_id))
            else:
                cursor.execute("""
                    INSERT INTO projects (speaker_id, name, tech_stack, goal, status, notes, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (speaker_id, name.strip(), tech_stack.strip(), goal.strip(), status.strip().lower(), notes.strip()))
                proj_id = cursor.lastrowid or 0
            conn.commit()

            self._emit_mutation("project_saved", {
                "id": proj_id,
                "name": name.strip(),
                "speaker_name": speaker_name.strip().title() if speaker_name else None,
                "status": status.strip().lower()
            })
            return proj_id

    def get_projects_for_speaker(self, speaker_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves active projects for a speaker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT p.id, p.name, p.tech_stack, p.goal, p.status, p.notes,
                       p.created_at, p.updated_at, s.name as speaker_name
                FROM projects p
                LEFT JOIN speakers s ON p.speaker_id = s.id
                WHERE 1=1
            """
            params = []
            if speaker_name:
                query += " AND (s.name = ? OR p.speaker_id IS NULL)"
                params.append(speaker_name.strip().title())
            query += " ORDER BY p.updated_at DESC"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def delete_project(self, project_id: int) -> bool:
        """Deletes a project by its primary key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("project_deleted", {"id": project_id})
            return ok

    def log_emotion(self, speaker_name: Optional[str], emotion: str, pitch_hz: float = 0.0,
                    rms: float = 0.0, description: str = "") -> None:
        """Records one acoustic emotion sample for long-term mood trends."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO emotion_history (speaker_name, emotion, pitch_hz, rms, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (speaker_name, emotion, pitch_hz, rms, description))
                conn.commit()
        except Exception as e:
            logger.debug(f"[EmotionHistory] log failed: {e}")

    def get_recent_emotions(self, speaker_name: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Returns the most recent emotion samples for mood trend analysis."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if speaker_name:
                    cursor.execute("""
                        SELECT emotion, pitch_hz, rms, description, created_at
                        FROM emotion_history WHERE speaker_name = ?
                        ORDER BY id DESC LIMIT ?
                    """, (speaker_name, limit))
                else:
                    cursor.execute("""
                        SELECT speaker_name, emotion, pitch_hz, rms, description, created_at
                        FROM emotion_history ORDER BY id DESC LIMIT ?
                    """, (limit,))
                return [dict(r) for r in cursor.fetchall()]
        except Exception:
            return []

    def save_playlist(
        self,
        name: str,
        tracks: List[Dict[str, Any]],
        speaker_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates/replaces a playlist and its ordered tracks."""
        clean_name = (name or "").strip().title()[:80]
        if not clean_name or not tracks:
            return {"status": "error", "message": "Nama playlist atau daftar lagu kosong."}

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO playlists (name, speaker_name, last_index, updated_at)
                VALUES (?, ?, 0, CURRENT_TIMESTAMP)
            """, (clean_name, speaker_name))
            pl_id = cursor.lastrowid
            cursor.execute(
                "DELETE FROM playlist_tracks WHERE playlist_id NOT IN (SELECT id FROM playlists)"
            )
            cursor.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (pl_id,))
            for pos, t in enumerate(tracks):
                vid = t.get("video_id") or t.get("videoId")
                if not vid:
                    continue
                cursor.execute("""
                    INSERT INTO playlist_tracks (playlist_id, video_id, title, channel, thumbnail, duration, position)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (pl_id, vid, t.get("title"), t.get("channel"), t.get("thumbnail"), t.get("duration"), pos))
            conn.commit()

        logger.info(f"[Playlist] Saved '{clean_name}' with {len(tracks)} track(s)")
        self._emit_mutation("playlist_saved", {"id": pl_id, "name": clean_name, "count": len(tracks)})
        return {"status": "ok", "id": pl_id, "name": clean_name, "count": len(tracks)}

    def get_playlist(self, name: str, speaker_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetches a playlist by (fuzzy) name plus its ordered tracks."""
        q = (name or "").strip().lower()
        if not q:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM playlists ORDER BY updated_at DESC")
            rows = [dict(r) for r in cursor.fetchall()]
            match = next((r for r in rows if (r["name"] or "").lower() == q), None)
            if not match:
                match = next((r for r in rows if q in (r["name"] or "").lower()), None)
            if not match:
                return None
            cursor.execute("""
                SELECT video_id, title, channel, thumbnail, duration, position
                FROM playlist_tracks WHERE playlist_id = ? ORDER BY position ASC
            """, (match["id"],))
            match["tracks"] = [dict(r) for r in cursor.fetchall()]
            return match

    def get_all_playlists(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.id, p.name, p.speaker_name, p.last_index, p.updated_at,
                       COUNT(t.id) AS track_count
                FROM playlists p LEFT JOIN playlist_tracks t ON t.playlist_id = p.id
                GROUP BY p.id ORDER BY p.updated_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def set_playlist_position(self, playlist_id: int, index: int) -> None:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE playlists SET last_index = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (max(0, int(index)), playlist_id),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"[Playlist] position update failed: {e}")

    def add_track_to_playlist(self, name: str, track: Dict[str, Any],
                              speaker_name: Optional[str] = None) -> Dict[str, Any]:
        pl = self.get_playlist(name, speaker_name)
        vid = track.get("video_id") or track.get("videoId")
        if not vid:
            return {"status": "error", "message": "Lagu tidak valid."}
        if not pl:
            return self.save_playlist(name, [track], speaker_name)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_tracks WHERE playlist_id = ?", (pl["id"],))
            pos = cursor.fetchone()[0]
            cursor.execute("""
                INSERT INTO playlist_tracks (playlist_id, video_id, title, channel, thumbnail, duration, position)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (pl["id"], vid, track.get("title"), track.get("channel"),
                  track.get("thumbnail"), track.get("duration"), pos))
            cursor.execute("UPDATE playlists SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (pl["id"],))
            conn.commit()

        self._emit_mutation("playlist_saved", {"id": pl["id"], "name": pl["name"], "count": pos + 1})
        return {"status": "ok", "id": pl["id"], "name": pl["name"], "count": pos + 1}

    def log_media_play(self, speaker_name: Optional[str], track: Dict[str, Any], kind: str = "music") -> None:
        vid = track.get("video_id") or track.get("videoId")
        if not vid:
            return
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO media_history (speaker_name, kind, video_id, title, channel, thumbnail, duration)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (speaker_name, kind, vid, track.get("title"), track.get("channel"),
                      track.get("thumbnail"), track.get("duration")))
                conn.commit()
        except Exception as e:
            logger.debug(f"[MediaHistory] log failed: {e}")

    def get_top_media(self, speaker_name: Optional[str] = None, limit: int = 5,
                      kind: str = "music") -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if speaker_name:
                    cursor.execute("""
                        SELECT video_id, title, channel, thumbnail, duration, COUNT(*) AS plays
                        FROM media_history WHERE kind = ? AND speaker_name = ?
                        GROUP BY video_id ORDER BY plays DESC, played_at DESC LIMIT ?
                    """, (kind, speaker_name, limit))
                else:
                    cursor.execute("""
                        SELECT video_id, title, channel, thumbnail, duration, COUNT(*) AS plays
                        FROM media_history WHERE kind = ?
                        GROUP BY video_id ORDER BY plays DESC, played_at DESC LIMIT ?
                    """, (kind, limit))
                return [dict(r) for r in cursor.fetchall()]
        except Exception:
            return []
