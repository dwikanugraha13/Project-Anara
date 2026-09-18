import asyncio
import json
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ChatSessionsMixin:
    """Chat threads, sessions management, conversation turn logging, and workspace attachments."""

    def clean_empty_sessions(self, speaker_name: Optional[str] = None, exclude_session_id: Optional[int] = None) -> int:
        """Cleans up un-messaged draft sessions (message_count = 0) to avoid duplicate 'New Chat' clutter,
        preserving any session that has an active project workspace, messages, or is currently active."""
        clean_name = speaker_name.strip().title() if speaker_name else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            where = "WHERE message_count = 0 AND is_pinned = 0 AND workspace_info_json IS NULL AND (title = 'New Chat' OR title IS NULL)"
            params = []
            if exclude_session_id is not None:
                where += " AND id != ?"
                params.append(exclude_session_id)
            if clean_name:
                where += " AND (speaker_name = ? OR speaker_name IS NULL)"
                params.append(clean_name)

            cursor.execute(f"DELETE FROM chat_sessions {where}", params)
            conn.commit()
            removed = cursor.rowcount
        if removed > 0:
            logger.info(f"[ChatSessions] Cleaned {removed} empty draft session(s)")
            self._emit_mutation("session_deleted", {"bulk": True, "count": removed})
        return removed

    def create_session(self, speaker_name: Optional[str] = None,
                       title: Optional[str] = None,
                       session_type: str = "chat",
                       channel: str = "web",
                       session_mode: Optional[str] = None) -> Dict[str, Any]:
        """Starts a new conversation thread (defaults to 'New Chat')."""
        clean_name = speaker_name.strip().title() if speaker_name else None
        initial_title = (title or "").strip() or ("New Project" if session_type == "code" else "New Chat")
        clean_type = "code" if str(session_type).lower() == "code" else "chat"
        clean_channel = (channel or "web").strip().lower()
        if not session_mode:
            clean_mode = "explicit_plan_build" if clean_type == "code" else "conversational"
        else:
            clean_mode = session_mode.strip().lower()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_sessions (title, speaker_name, session_type, channel, session_mode) VALUES (?, ?, ?, ?, ?)",
                (initial_title, clean_name, clean_type, clean_channel, clean_mode)
            )
            sid = cursor.lastrowid or 0
            conn.commit()

        self.clean_empty_sessions(clean_name, exclude_session_id=sid)

        logger.info(f"[ChatSessions] Created {clean_type} session #{sid} ('{initial_title}') [channel={clean_channel}, mode={clean_mode}] for {clean_name or 'Tamu'}")
        self._emit_mutation("session_created", {"id": sid, "title": initial_title, "speaker_name": clean_name, "session_type": clean_type, "channel": clean_channel, "session_mode": clean_mode})
        return {"id": sid, "title": initial_title, "speaker_name": clean_name, "session_type": clean_type, "channel": clean_channel, "session_mode": clean_mode, "message_count": 0}

    def get_sessions(self, speaker_name: Optional[str] = None,
                     session_type: Optional[str] = None,
                     include_archived: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        """Lists conversation threads, pinned first then most recently used, optionally filtered by session_type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT s.id, s.title, s.speaker_name,
                       (SELECT COUNT(*) FROM conversations WHERE conversations.session_id = s.id) AS message_count,
                       s.is_archived, s.is_pinned,
                       COALESCE(s.session_type, 'chat') AS session_type,
                       COALESCE(s.channel, 'web') AS channel,
                       COALESCE(s.session_mode, CASE WHEN s.session_type = 'code' THEN 'explicit_plan_build' ELSE 'conversational' END) AS session_mode,
                       COALESCE(s.run_type, 'interactive') AS run_type,
                       COALESCE(s.trust_level, 'supervised') AS trust_level,
                       s.created_at, s.updated_at,
                       (SELECT user_text FROM conversations c
                         WHERE c.session_id = s.id ORDER BY c.id DESC LIMIT 1) AS last_user_text
                FROM chat_sessions s
            """
            where, params = [], []
            if not include_archived:
                where.append("s.is_archived = 0")
            if session_type:
                where.append("COALESCE(s.session_type, 'chat') = ?")
                params.append(session_type.strip().lower())
            if speaker_name:
                where.append("(s.speaker_name = ? OR s.speaker_name IS NULL)")
                params.append(speaker_name.strip().title())
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " ORDER BY s.is_pinned DESC, s.updated_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_last_active_session_id(self, speaker_name: Optional[str] = None, session_type: Optional[str] = None) -> Optional[int]:
        """Returns the ID of the most recently updated active chat thread."""
        sessions = self.get_sessions(speaker_name=speaker_name, session_type=session_type, include_archived=False, limit=1)
        if sessions:
            return sessions[0]["id"]
        return None

    def get_session_messages(self, session_id: int, limit: int = 500) -> List[Dict[str, Any]]:
        """Returns all messages of one thread in chronological order."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, speaker_name, user_text, ai_text, media_type, media_url,
                       visual_data_json, created_at
                FROM conversations
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
            """, (session_id, limit))
            out = []
            for r in cursor.fetchall():
                item = dict(r)
                u_txt = (item.get("user_text") or "").lstrip()
                if u_txt.startswith("{") and '"type"' in u_txt:
                    continue
                if item.get("visual_data_json"):
                    try:
                        item["visual_data"] = json.loads(item["visual_data_json"])
                    except Exception:
                        item["visual_data"] = None
                out.append(item)
            return out

    def rename_session(self, session_id: int, title: str) -> bool:
        clean = (title or "").strip()[:120]
        if not clean:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (clean, session_id)
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_updated", {"id": session_id, "title": clean})
        return ok

    def patch_session(self, session_id: int, title: Optional[str] = None,
                      is_pinned: Optional[bool] = None, is_archived: Optional[bool] = None) -> bool:
        """Updates title, pinned, or archived status of a session."""
        sets, params = [], []
        if title is not None:
            clean = title.strip()[:120]
            if clean:
                sets.append("title = ?")
                params.append(clean)
        if is_pinned is not None:
            sets.append("is_pinned = ?")
            params.append(1 if is_pinned else 0)
        if is_archived is not None:
            sets.append("is_archived = ?")
            params.append(1 if is_archived else 0)
        if not sets:
            return False
        params.append(session_id)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"UPDATE chat_sessions SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                params
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_updated", {
                "id": session_id, "title": title, "is_pinned": is_pinned, "is_archived": is_archived
            })
        return ok

    def delete_session(self, session_id: int) -> bool:
        """Removes a thread AND all of its messages."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            removed_msgs = cursor.rowcount
            cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
            ok = cursor.rowcount > 0
            conn.commit()
        if ok:
            logger.info(f"[ChatSessions] Deleted session #{session_id} with {removed_msgs} message(s)")
            self._emit_mutation("session_deleted", {"id": session_id, "messages": removed_msgs})
        return ok

    def clear_session_messages(self, session_id: int) -> int:
        """Empties a thread but keeps the thread itself."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
            removed = cursor.rowcount
            cursor.execute(
                "UPDATE chat_sessions SET message_count = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            conn.commit()
        self._emit_mutation("session_updated", {"id": session_id, "message_count": 0})
        return removed

    def delete_sessions_bulk(self, archived_only: bool = False,
                             keep_pinned: bool = True) -> Dict[str, int]:
        """Bulk cleanup: archived threads, or everything except pinned ones."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conds = []
            if archived_only:
                conds.append("is_archived = 1")
            if keep_pinned:
                conds.append("is_pinned = 0")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            cursor.execute(f"SELECT id FROM chat_sessions{where}")
            ids = [r["id"] for r in cursor.fetchall()]
            if not ids:
                return {"sessions": 0, "messages": 0}
            marks = ",".join("?" for _ in ids)
            cursor.execute(f"DELETE FROM conversations WHERE session_id IN ({marks})", ids)
            msgs = cursor.rowcount
            cursor.execute(f"DELETE FROM chat_sessions WHERE id IN ({marks})", ids)
            sess = cursor.rowcount
            conn.commit()
        logger.info(f"[ChatSessions] Bulk deleted {sess} session(s), {msgs} message(s)")
        self._emit_mutation("session_deleted", {"bulk": True, "sessions": sess})
        return {"sessions": sess, "messages": msgs}

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (session_id,))
            r = cursor.fetchone()
            if not r:
                return None
            res = dict(r)
            res["channel"] = res.get("channel") or "web"
            res["session_mode"] = res.get("session_mode") or ("explicit_plan_build" if res.get("session_type") == "code" else "conversational")
            if res.get("workspace_info_json"):
                try:
                    res["workspace_info"] = json.loads(res["workspace_info_json"])
                except Exception:
                    res["workspace_info"] = None
            else:
                res["workspace_info"] = None
            return res

    def set_session_workspace_info(self, session_id: int, workspace_info: Optional[Dict[str, Any]]) -> bool:
        """Stores or clears active project folder metadata for a specific chat session."""
        info_json = json.dumps(workspace_info) if workspace_info else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET workspace_info_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (info_json, session_id)
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_workspace_updated", {"id": session_id, "workspace_info": workspace_info})
        return ok

    def get_session_pending_plan(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Returns the saved Plan Mode proposal for one chat session."""
        sess = self.get_session(session_id)
        if not sess or not sess.get("pending_plan_json"):
            return None
        try:
            return json.loads(sess["pending_plan_json"])
        except Exception:
            return None

    def set_session_pending_plan(self, session_id: int, plan: Optional[Dict[str, Any]]) -> bool:
        """Persists or clears a session-scoped project plan awaiting Build confirmation."""
        plan_json = json.dumps(plan) if plan else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET pending_plan_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (plan_json, session_id),
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_plan_updated", {"id": session_id, "plan": plan})
        return ok

    async def auto_title_session_async(self, client: Any, session_id: int) -> Optional[str]:
        """Names a thread dynamically from its first turns."""
        sess = self.get_session(session_id)
        if not sess:
            return None
        current_title = (sess.get("title") or "").strip()
        is_placeholder = (
            not current_title
            or current_title.lower() in ["new chat", "chat baru", "percakapan baru"]
            or current_title.lower().startswith("percakapan #")
        )
        if not is_placeholder:
            return None

        msgs = self.get_session_messages(session_id, limit=4)
        if not msgs:
            return None

        convo = "\n".join(
            f"User: {(m.get('user_text') or '')[:160]}\nAnara: {(m.get('ai_text') or '')[:160]}"
            for m in msgs[:3]
        )
        fallback = (msgs[0].get("user_text") or "Percakapan").strip()
        fallback = (fallback[:36] + "...") if len(fallback) > 36 else fallback

        prompt = (
            "Buat judul SINGKAT (2-5 kata) untuk percakapan berikut, dalam Bahasa Indonesia.\n"
            "Aturan: tanpa tanda kutip, tanpa titik di akhir, langsung inti topiknya.\n"
            "Contoh judul bagus: 'Resep Nasi Goreng', 'Setup VPS Telegram', 'Tips Belajar Efektif'.\n\n"
            f"PERCAKAPAN:\n{convo}\n\nJUDUL:"
        )

        title = ""
        try:
            from google.genai import types as _types
            cfg = _types.GenerateContentConfig(max_output_tokens=30, temperature=0.3)
            for mdl in ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite"):
                try:
                    res = await asyncio.wait_for(
                        client.aio.models.generate_content(model=mdl, contents=prompt, config=cfg),
                        timeout=6.0,
                    )
                    if res and res.text:
                        title = res.text.strip().strip('"\'').rstrip(".")
                        title = re.sub(r"^(?:judul|title)\s*:\s*", "", title, flags=re.IGNORECASE).strip()
                        if title:
                            break
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[ChatSessions] Auto-title model error: {e}")

        final = (title or fallback)[:80]
        if self.rename_session(session_id, final):
            logger.info(f"[ChatSessions] Auto-titled session #{session_id}: {final!r}")
            return final
        return None

    def log_conversation(
        self,
        user_text: str,
        ai_text: str,
        speaker_name: Optional[str] = None,
        media_type: Optional[str] = None,
        media_url: Optional[str] = None,
        visual_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[int] = None
    ) -> int:
        """Persists a full dialogue turn to SQLite conversations table."""
        speaker_id = None
        clean_name = speaker_name.strip().title() if speaker_name else None
        if clean_name:
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM speakers WHERE name = ?", (clean_name,))
                r = cur.fetchone()
                if r:
                    speaker_id = r["id"]

        vis_json = json.dumps(visual_data) if visual_data else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if session_id is not None:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE LOWER(TRIM(user_text)) = LOWER(?) AND session_id = ? AND (ai_text IS NULL OR ai_text = '')
                """, (user_text.strip(), session_id))
            elif clean_name:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE LOWER(TRIM(user_text)) = LOWER(?) AND speaker_name = ?
                      AND session_id IS NULL
                """, (user_text.strip(), clean_name))

            cursor.execute("""
                INSERT INTO conversations (speaker_name, speaker_id, user_text, ai_text, media_type, media_url, visual_data_json, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (clean_name, speaker_id, user_text.strip(), ai_text.strip(), media_type, media_url, vis_json, session_id))
            last_id = cursor.lastrowid or 0

            if session_id is not None:
                cursor.execute("""
                    UPDATE chat_sessions
                    SET message_count = (
                            SELECT COUNT(*) FROM conversations WHERE session_id = ?
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (session_id, session_id))

            conn.commit()

        self._emit_mutation("conversation_logged", {
            "id": last_id,
            "speaker_name": clean_name,
            "user_text": user_text.strip(),
            "ai_text": ai_text.strip()
        })
        return last_id

    def delete_conversation_by_id(self, conversation_id: int) -> bool:
        """Deletes a single conversation log entry by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("conversation_deleted", {"id": conversation_id})
            return ok

    def attach_visual_to_latest_conversation(
        self,
        user_text: str,
        ai_text: str,
        speaker_name: Optional[str] = None,
        visual_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        clean_name = speaker_name.strip().title() if speaker_name else None
        vis_json = json.dumps(visual_data) if visual_data else None
        vis_type = visual_data.get("visual_type", "hud") if visual_data else "hud"
        vis_url = visual_data.get("image_url") if visual_data else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if clean_name:
                cursor.execute(
                    "SELECT id FROM conversations WHERE LOWER(TRIM(user_text)) = LOWER(?) "
                    "AND LOWER(TRIM(ai_text)) = LOWER(?) AND speaker_name = ? ORDER BY id DESC LIMIT 1",
                    (user_text.strip(), ai_text.strip(), clean_name),
                )
            else:
                cursor.execute(
                    "SELECT id FROM conversations WHERE LOWER(TRIM(user_text)) = LOWER(?) "
                    "AND LOWER(TRIM(ai_text)) = LOWER(?) ORDER BY id DESC LIMIT 1",
                    (user_text.strip(), ai_text.strip()),
                )
            row = cursor.fetchone()
            if not row:
                return False
            cursor.execute(
                "UPDATE conversations SET media_type = ?, media_url = ?, visual_data_json = ? WHERE id = ?",
                (vis_type, vis_url, vis_json, row["id"]),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_recent_conversations(self, limit: int = 30, speaker_name: Optional[str] = None,
                                 session_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves recent conversation history from SQLite (newest first)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, speaker_name, user_text, ai_text, media_type, media_url,
                       visual_data_json, created_at, session_id
                FROM conversations
            """
            conds, params = [], []
            if session_id is not None:
                conds.append("session_id = ?")
                params.append(session_id)
            elif speaker_name:
                conds.append("speaker_name = ?")
                params.append(speaker_name.strip().title())
            if conds:
                query += " WHERE " + " AND ".join(conds)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                u_txt = (item.get("user_text") or "").lstrip()
                if u_txt.startswith("{") and '"type"' in u_txt:
                    continue
                if item.get("visual_data_json"):
                    try:
                        item["visual_data"] = json.loads(item["visual_data_json"])
                    except Exception:
                        item["visual_data"] = None
                result.append(item)
            return result

    def get_conversational_bridge_context(self, session_id: Optional[int] = None, speaker_name: Optional[str] = None, limit: int = 4) -> str:
        """Builds a lightweight conversational bridge context between Chat Mode and Voice Mode."""
        recent = self.get_recent_conversations(limit=limit, session_id=session_id, speaker_name=speaker_name)
        if not recent:
            return ""

        dialogue_turns = []
        for r in reversed(recent):
            u = (r.get("user_text") or "").strip()
            a = (r.get("ai_text") or "").strip()

            u = re.sub(r"```[\s\S]*?```", "[cuplikan kode/file]", u)
            a = re.sub(r"```[\s\S]*?```", "[cuplikan kode/file]", a)
            u = re.sub(r"\s+", " ", u).strip()
            a = re.sub(r"\s+", " ", a).strip()

            if len(u) > 200:
                u = u[:200] + "..."
            if len(a) > 200:
                a = a[:200] + "..."

            sp = r.get("speaker_name") or speaker_name or "Pengguna"
            if u:
                dialogue_turns.append(f"{sp}: {u}")
            if a:
                dialogue_turns.append(f"Anara: {a}")

        if not dialogue_turns:
            return ""

        return (
            "[KONTEKS PERCAKAPAN TERAKHIR]:\n"
            + "\n".join(dialogue_turns) + "\n"
        )
