import asyncio
import json
import logging
import os
import re
import shutil
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
            where = "WHERE message_count = 0 AND is_pinned = 0 AND workspace_info_json IS NULL AND (title = 'New Chat' OR title = 'New Project' OR title IS NULL)"
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
                       session_mode: Optional[str] = None,
                       session_key: Optional[str] = None,
                       workspace_path: Optional[str] = None) -> Dict[str, Any]:
        """Starts a new conversation thread (defaults to 'New Chat') with canonical collision-free session_key."""
        from core.session_ids import new_session_key
        canonical_key = session_key or new_session_key()
        clean_name = speaker_name.strip().title() if speaker_name else None
        initial_title = (title or "").strip() or ("New Project" if session_type == "code" else "New Chat")
        clean_type = "code" if str(session_type).lower() == "code" else "chat"
        clean_channel = (channel or "web").strip().lower()
        if not session_mode:
            clean_mode = "build" if clean_type == "code" else "conversational"
        else:
            clean_mode = session_mode.strip().lower()

        # Build workspace_info_json if workspace_path provided
        workspace_info_json = None
        workspace_info = None
        if workspace_path and workspace_path.strip():
            import os
            clean_wp = os.path.abspath(os.path.expanduser(workspace_path.strip()))
            folder_name = os.path.basename(clean_wp.rstrip("\\/")) or "Project Workspace"
            workspace_info = {"name": folder_name, "root_path": clean_wp, "is_external": True}
            workspace_info_json = json.dumps(workspace_info)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_sessions (session_key, title, speaker_name, session_type, channel, session_mode, workspace_info_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (canonical_key, initial_title, clean_name, clean_type, clean_channel, clean_mode, workspace_info_json)
            )
            sid = cursor.lastrowid or 0
            conn.commit()

        self.clean_empty_sessions(clean_name, exclude_session_id=sid)

        logger.info(f"[ChatSessions] Created {clean_type} session #{sid} ({canonical_key}) ('{initial_title}') [channel={clean_channel}, mode={clean_mode}] for {clean_name or 'Guest'}")
        self._emit_mutation("session_created", {"id": sid, "session_key": canonical_key, "title": initial_title, "speaker_name": clean_name, "session_type": clean_type, "channel": clean_channel, "session_mode": clean_mode, "workspace_info": workspace_info})
        return {"id": sid, "session_key": canonical_key, "title": initial_title, "speaker_name": clean_name, "session_type": clean_type, "channel": clean_channel, "session_mode": clean_mode, "message_count": 0, "workspace_info": workspace_info}

    def get_sessions(self, speaker_name: Optional[str] = None,
                     session_type: Optional[str] = None,
                     channel: Optional[str] = None,
                     include_archived: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
        """Lists conversation threads, pinned first then most recently used, optionally filtered by session_type and channel."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT s.id, s.session_key, s.title, s.speaker_name,
                       (SELECT COUNT(*) FROM conversations WHERE conversations.session_id = s.id) AS message_count,
                       s.is_archived, s.is_pinned,
                       COALESCE(s.session_type, 'chat') AS session_type,
                       COALESCE(s.channel, 'web') AS channel,
                       COALESCE(s.session_mode, CASE WHEN s.session_type = 'code' THEN 'build' ELSE 'conversational' END) AS session_mode,
                       COALESCE(s.run_type, 'interactive') AS run_type,
                       COALESCE(s.trust_level, 'supervised') AS trust_level,
                       s.workspace_info_json,
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
            if channel:
                where.append("COALESCE(s.channel, 'web') = ?")
                params.append(channel.strip().lower())
            if speaker_name:
                where.append("(s.speaker_name = ? OR s.speaker_name IS NULL)")
                params.append(speaker_name.strip().title())
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " ORDER BY s.is_pinned DESC, s.updated_at DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = []
            for r in cursor.fetchall():
                row = dict(r)
                # Parse workspace_info_json into workspace_info dict
                wij = row.pop("workspace_info_json", None)
                if wij:
                    try:
                        row["workspace_info"] = json.loads(wij)
                    except (json.JSONDecodeError, TypeError):
                        row["workspace_info"] = None
                else:
                    row["workspace_info"] = None
                rows.append(row)
            return rows

    def _resolve_session_id(self, session_id: Any) -> Optional[int]:
        """Resolves any session identifier (integer ID or canonical string session_key) to its numeric SQLite primary key."""
        if session_id is None:
            return None
        if isinstance(session_id, int):
            return session_id
        if isinstance(session_id, str):
            clean = session_id.strip()
            if clean.isdigit():
                return int(clean)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM chat_sessions WHERE session_key = ?", (clean,))
                row = cursor.fetchone()
                return row["id"] if row else None
        return None

    def get_last_active_session_id(
        self,
        speaker_name: Optional[str] = None,
        session_type: Optional[str] = None,
        channel: Optional[str] = None
    ) -> Optional[int]:
        """Returns the ID of the most recently updated active chat thread, optionally scoped to channel."""
        sessions = self.get_sessions(
            speaker_name=speaker_name,
            session_type=session_type,
            channel=channel,
            include_archived=False,
            limit=1
        )
        if sessions:
            return sessions[0]["id"]
        return None

    def get_session_messages(self, session_id: Any, limit: int = 500) -> List[Dict[str, Any]]:
        """Returns all messages of one thread in chronological order."""
        sid = self._resolve_session_id(session_id) or session_id
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, speaker_name, user_text, ai_text, media_type, media_url,
                       visual_data_json, created_at
                FROM conversations
                WHERE session_id = ?
                ORDER BY id ASC
                LIMIT ?
            """, (sid, limit))
            out = []
            for r in cursor.fetchall():
                item = dict(r)
                if item.get("visual_data_json"):
                    try:
                        item["visual_data"] = json.loads(item["visual_data_json"])
                    except Exception:
                        item["visual_data"] = None
                out.append(item)
            return out

    def rename_session(self, session_id: Any, title: str) -> bool:
        clean = (title or "").strip()[:120]
        if not clean:
            return False
        sid = self._resolve_session_id(session_id) or session_id
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (clean, sid)
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_updated", {"id": sid, "title": clean})
        return ok

    def fork_session(self, session_id: Any, title_prefix: str = "Branch: ") -> Optional[Dict[str, Any]]:
        """
        Forks an existing session into an independent conversation branch (Anara Standard).
        Copies all conversation turns, metadata, and workspace configuration.
        """
        orig = self.get_session(session_id)
        if not orig:
            return None

        orig_id = orig["id"]
        forked_title = f"{title_prefix}{orig.get('title') or 'Chat'}"[:120]
        new_session = self.create_session(
            speaker_name=orig.get("speaker_name"),
            title=forked_title,
            session_type=orig.get("session_type", "chat"),
            channel=orig.get("channel", "web"),
            session_mode=orig.get("session_mode"),
        )
        new_id = new_session["id"]

        # Copy conversation turns
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT speaker_name, user_text, ai_text, media_type, media_url,
                       visual_data_json, created_at
                FROM conversations
                WHERE session_id = ?
                ORDER BY id ASC
            """, (orig_id,))
            rows = cursor.fetchall()
            for r in rows:
                cursor.execute("""
                    INSERT INTO conversations (session_id, speaker_name, user_text, ai_text,
                                              media_type, media_url, visual_data_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (new_id, r["speaker_name"], r["user_text"], r["ai_text"],
                      r["media_type"], r["media_url"], r["visual_data_json"], r["created_at"]))

            cursor.execute("UPDATE chat_sessions SET message_count = ? WHERE id = ?", (len(rows), new_id))
            conn.commit()

        # Copy workspace files if present on disk
        try:
            from core import anara_agent
            orig_dir = anara_agent.get_session_dir(orig_id)
            new_dir = anara_agent.get_session_dir(new_id)
            if os.path.exists(orig_dir) and orig_dir != new_dir and not orig_dir.endswith("Project Anara"):
                if os.path.exists(new_dir):
                    shutil.rmtree(new_dir, ignore_errors=True)
                shutil.copytree(orig_dir, new_dir, dirs_exist_ok=True)
        except Exception as e:
            logger.warning(f"[ChatSessions] Note: workspace copy during fork: {e}")

        logger.info(f"[ChatSessions] Forked session #{orig_id} -> #{new_id} ('{forked_title}') with {len(rows)} messages")
        self._emit_mutation("session_created", {"id": new_id, "forked_from": orig_id, "title": forked_title})
        return self.get_session(new_id)

    def patch_session(self, session_id: Any, title: Optional[str] = None,
                      is_pinned: Optional[bool] = None, is_archived: Optional[bool] = None,
                      session_mode: Optional[str] = None) -> bool:
        """Updates title, pinned, archived, or session_mode status of a session."""
        sid = self._resolve_session_id(session_id) or session_id
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
        if session_mode is not None:
            clean_mode = session_mode.strip().lower()
            if clean_mode in ("conversational", "plan", "build", "explicit_plan_build"):
                sets.append("session_mode = ?")
                params.append(clean_mode)
        if not sets:
            return False
        params.append(sid)
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
                "id": sid, "title": title, "is_pinned": is_pinned, "is_archived": is_archived, "session_mode": session_mode
            })
        return ok

    def delete_session(self, session_id: Any) -> bool:
        """Removes a thread AND all cascading messages, tokens, and settings (Anara Enterprise Architecture)."""
        sid = self._resolve_session_id(session_id) or session_id
        sess = self.get_session(session_id)
        skey = sess.get("session_key") if sess else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (sid,))
            removed_msgs = cursor.rowcount
            try:
                cursor.execute("DELETE FROM token_usage_logs WHERE session_id = ?", (sid,))
            except Exception:
                pass
            try:
                if skey:
                    cursor.execute("DELETE FROM project_adr WHERE session_id = ? OR session_id = ?", (str(sid), str(skey)))
                else:
                    cursor.execute("DELETE FROM project_adr WHERE session_id = ?", (str(sid),))
            except Exception:
                pass
            try:
                if skey:
                    cursor.execute("DELETE FROM app_settings WHERE key = ? OR key = ?", (f"session_scratchpad_{sid}", f"session_scratchpad_{skey}"))
                else:
                    cursor.execute("DELETE FROM app_settings WHERE key = ?", (f"session_scratchpad_{sid}",))
            except Exception:
                pass
            cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
            ok = cursor.rowcount > 0
            conn.commit()
        if ok:
            try:
                from memory.memory_nudge import memory_nudge_manager
                memory_nudge_manager.evict_session(sid)
                if skey:
                    memory_nudge_manager.evict_session(skey)
            except Exception:
                pass
            logger.info(f"[ChatSessions] Deleted session #{sid} with {removed_msgs} message(s)")
            self._emit_mutation("session_deleted", {"id": sid, "messages": removed_msgs})
        return ok

    def clear_session_messages(self, session_id: Any) -> int:
        """Empties a thread but keeps the thread itself."""
        sid = self._resolve_session_id(session_id) or session_id
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM conversations WHERE session_id = ?", (sid,))
            removed = cursor.rowcount
            cursor.execute(
                "UPDATE chat_sessions SET message_count = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (sid,)
            )
            conn.commit()
        self._emit_mutation("session_updated", {"id": sid, "message_count": 0})
        return removed

    def delete_sessions_bulk(self, archived_only: bool = False,
                             keep_pinned: bool = True) -> Dict[str, int]:
        """Bulk cleanup with chunked parameter handling to prevent SQLite variable overflow."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            conds = []
            if archived_only:
                conds.append("is_archived = 1")
            if keep_pinned:
                conds.append("is_pinned = 0")
            where = (" WHERE " + " AND ".join(conds)) if conds else ""
            cursor.execute(f"SELECT id, session_key FROM chat_sessions{where}")
            rows = cursor.fetchall()
            if not rows:
                return {"sessions": 0, "messages": 0}

            ids = [r["id"] for r in rows]
            skeys = [r["session_key"] for r in rows if r["session_key"]]

            msgs = 0
            sess = 0
            # Chunk into batches of 200 to prevent SQLite variable limits
            for i in range(0, len(ids), 200):
                batch = ids[i:i + 200]
                marks = ",".join("?" for _ in batch)
                cursor.execute(f"DELETE FROM conversations WHERE session_id IN ({marks})", batch)
                msgs += cursor.rowcount
                try:
                    cursor.execute(f"DELETE FROM token_usage_logs WHERE session_id IN ({marks})", batch)
                except Exception:
                    pass
                try:
                    cursor.execute(f"DELETE FROM project_adr WHERE session_id IN ({marks})", [str(x) for x in batch])
                except Exception:
                    pass
                try:
                    scratch_keys = [f"session_scratchpad_{x}" for x in batch]
                    kmarks = ",".join("?" for _ in scratch_keys)
                    cursor.execute(f"DELETE FROM app_settings WHERE key IN ({kmarks})", scratch_keys)
                except Exception:
                    pass
                cursor.execute(f"DELETE FROM chat_sessions WHERE id IN ({marks})", batch)
                sess += cursor.rowcount

            if skeys:
                for i in range(0, len(skeys), 200):
                    batch_keys = skeys[i:i + 200]
                    kmarks = ",".join("?" for _ in batch_keys)
                    try:
                        cursor.execute(f"DELETE FROM project_adr WHERE session_id IN ({kmarks})", batch_keys)
                    except Exception:
                        pass
                    try:
                        scratch_keys = [f"session_scratchpad_{k}" for k in batch_keys]
                        skmarks = ",".join("?" for _ in scratch_keys)
                        cursor.execute(f"DELETE FROM app_settings WHERE key IN ({skmarks})", scratch_keys)
                    except Exception:
                        pass

            conn.commit()
        try:
            from memory.memory_nudge import memory_nudge_manager
            for sid_item in ids:
                memory_nudge_manager.evict_session(sid_item)
            for skey_item in skeys:
                memory_nudge_manager.evict_session(skey_item)
        except Exception:
            pass
        logger.info(f"[ChatSessions] Bulk deleted {sess} session(s), {msgs} message(s)")
        self._emit_mutation("session_deleted", {"bulk": True, "sessions": sess})
        return {"sessions": sess, "messages": msgs}

    def get_session(self, session_id: Any) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if isinstance(session_id, int) or (isinstance(session_id, str) and session_id.isdigit()):
                cursor.execute("SELECT * FROM chat_sessions WHERE id = ?", (int(session_id),))
            else:
                cursor.execute("SELECT * FROM chat_sessions WHERE session_key = ?", (str(session_id),))
            r = cursor.fetchone()
            if not r:
                return None
            res = dict(r)
            res["channel"] = res.get("channel") or "web"
            res["session_mode"] = res.get("session_mode") or ("build" if res.get("session_type") == "code" else "conversational")
            if res.get("workspace_info_json"):
                try:
                    res["workspace_info"] = json.loads(res["workspace_info_json"])
                except Exception:
                    res["workspace_info"] = None
            else:
                res["workspace_info"] = None
            return res

    def set_session_workspace_info(self, session_id: Any, workspace_info: Optional[Dict[str, Any]]) -> bool:
        """Stores or clears active project folder metadata for a specific chat session."""
        sid = self._resolve_session_id(session_id)
        if sid is None:
            return False
        info_json = json.dumps(workspace_info) if workspace_info else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET workspace_info_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (info_json, sid)
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_workspace_updated", {"id": sid, "workspace_info": workspace_info})
        return ok

    def get_recent_workspace_paths(self, limit: int = 5) -> List[str]:
        """Returns list of distinct recent project workspace paths from sessions (Anara Standard)."""
        paths: List[str] = []
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT workspace_info_json FROM chat_sessions "
                        "WHERE workspace_info_json IS NOT NULL AND workspace_info_json != '' "
                        "ORDER BY updated_at DESC LIMIT 50"
                    )
                    seen = set()
                    for (wij,) in cursor.fetchall():
                        try:
                            data = json.loads(wij) if isinstance(wij, str) else {}
                            p = data.get("root_path")
                            if p and os.path.isdir(p) and p not in seen:
                                seen.add(p)
                                paths.append(p)
                                if len(paths) >= limit:
                                    break
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"[ChatSessions] Error getting recent workspace paths: {e}")
        return paths

    def get_session_pending_plan(self, session_id: Any) -> Optional[Dict[str, Any]]:
        """Returns the saved Plan Mode proposal for one chat session."""
        sess = self.get_session(session_id)
        if not sess or not sess.get("pending_plan_json"):
            return None
        try:
            return json.loads(sess["pending_plan_json"])
        except Exception:
            return None

    def set_session_pending_plan(self, session_id: Any, plan: Optional[Dict[str, Any]]) -> bool:
        """Persists or clears a session-scoped project plan awaiting Build confirmation."""
        sid = self._resolve_session_id(session_id)
        if sid is None:
            return False
        plan_json = json.dumps(plan) if plan else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE chat_sessions SET pending_plan_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (plan_json, sid),
            )
            conn.commit()
            ok = cursor.rowcount > 0
        if ok:
            self._emit_mutation("session_plan_updated", {"id": sid, "plan": plan})
        return ok

    def clear_session_pending_plan(self, session_id: Any) -> bool:
        """Clears the pending plan proposal for a session."""
        return self.set_session_pending_plan(session_id, None)

    async def auto_title_session_async(self, client: Any, session_id: int) -> Optional[str]:
        """Names a thread dynamically from its first turns."""
        sess = self.get_session(session_id)
        if not sess:
            return None
        current_title = (sess.get("title") or "").strip()
        is_placeholder = (
            not current_title
            or current_title.lower() in ["new chat", "new session", "new project", "session", "chat"]
            or current_title.lower().startswith(("session #", "chat #", "telegram chat (", "web chat (", "discord chat ("))
            or current_title.lower().endswith("]")
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
        fallback = (msgs[0].get("user_text") or "New Session").strip()
        fallback = (fallback[:36] + "...") if len(fallback) > 36 else fallback

        prompt = (
            "Generate a SHORT title (2-5 words) summarizing this conversation.\n"
            "Rules: match the language used by the user, no quotes, no trailing dot, capture the core topic directly.\n\n"
            f"CONVERSATION:\n{convo}\n\nTITLE:"
        )

        title = ""
        try:
            from core.capabilities import get_fast_auxiliary_model
            aux_mdl = get_fast_auxiliary_model()
            if client and getattr(client, "aio", None):
                from google.genai import types as _types
                cfg = _types.GenerateContentConfig(max_output_tokens=30, temperature=0.3)
                for mdl in (aux_mdl, "gemini-2.5-flash"):
                    try:
                        res = await asyncio.wait_for(
                            client.aio.models.generate_content(model=mdl, contents=prompt, config=cfg),
                            timeout=6.0,
                        )
                        if res and res.text:
                            title = res.text.strip().strip('"\'').rstrip(".")
                            title = re.sub(r"^(?:title|topic|subject)\s*[:=]\s*", "", title, flags=re.IGNORECASE).strip()
                            if title:
                                break
                    except Exception:
                        continue

            if not title:
                from providers import call_universal_chat_model
                res_str = await asyncio.wait_for(
                    call_universal_chat_model(
                        model_id=aux_mdl,
                        user_prompt=prompt,
                        system_instruction="You are a concise conversation title generator. Return 2-5 words only.",
                        max_tokens=30,
                        temperature=0.3,
                        read_only=True
                    ),
                    timeout=5.0
                )
                if res_str:
                    clean_res = str(res_str).strip().strip('"\'').rstrip(".")
                    title = re.sub(r"^(?:title|topic|subject)\s*[:=]\s*", "", clean_res, flags=re.IGNORECASE).strip()
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
        session_id: Optional[Any] = None
    ) -> int:
        """Persists a full dialogue turn to SQLite conversations table."""
        # Screen out raw WebSocket control frames (Anara Clean Ingestion Standard)
        clean_user = (user_text or "").strip()
        if clean_user.startswith("{") and ('"type"' in clean_user or '"action"' in clean_user) and len(clean_user) < 500:
            try:
                parsed_frame = json.loads(clean_user)
                if isinstance(parsed_frame, dict) and parsed_frame.get("type") in ("ping", "pong", "handshake", "switch_session", "switch_model"):
                    logger.debug(f"[ChatSessions] Ignored raw WebSocket control frame: {parsed_frame.get('type')}")
                    return 0
            except Exception:
                pass

        sid = self._resolve_session_id(session_id) if session_id is not None else None
        clean_name = speaker_name.strip().title() if speaker_name else None
        vis_json = json.dumps(visual_data, default=str) if visual_data else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            speaker_id = None
            if clean_name:
                cursor.execute("SELECT id FROM speakers WHERE name = ?", (clean_name,))
                r = cursor.fetchone()
                if r:
                    speaker_id = r["id"]

            if sid is not None:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE LOWER(TRIM(user_text)) = LOWER(?) AND session_id = ? AND (ai_text IS NULL OR ai_text = '')
                """, (user_text.strip(), sid))
            elif clean_name:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE LOWER(TRIM(user_text)) = LOWER(?) AND speaker_name = ?
                      AND session_id IS NULL
                """, (user_text.strip(), clean_name))

            cursor.execute("""
                INSERT INTO conversations (speaker_name, speaker_id, user_text, ai_text, media_type, media_url, visual_data_json, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (clean_name, speaker_id, user_text.strip(), ai_text.strip(), media_type, media_url, vis_json, sid))
            last_id = cursor.lastrowid or 0

            if sid is not None:
                cursor.execute("""
                    UPDATE chat_sessions
                    SET message_count = (
                            SELECT COUNT(*) FROM conversations WHERE session_id = ?
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (sid, sid))

            conn.commit()

        self._emit_mutation("conversation_logged", {
            "id": last_id,
            "speaker_name": clean_name,
            "user_text": user_text.strip(),
            "ai_text": ai_text.strip()
        })
        return last_id

    def delete_conversation_by_id(self, conversation_id: int) -> bool:
        """Deletes a single conversation log entry by its ID and synchronizes session message count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT session_id FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            sid = row["session_id"] if row else None

            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            ok = cursor.rowcount > 0
            if ok and sid:
                cursor.execute(
                    "UPDATE chat_sessions SET message_count = (SELECT COUNT(*) FROM conversations WHERE session_id = ?) WHERE id = ?",
                    (sid, sid)
                )
            conn.commit()
            if ok and hasattr(self, "_emit_mutation"):
                self._emit_mutation("conversation_deleted", {"id": conversation_id, "session_id": sid})
            return ok

    def attach_visual_to_latest_conversation(
        self,
        user_text: str,
        ai_text: str,
        speaker_name: Optional[str] = None,
        visual_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[Any] = None,
        conversation_id: Optional[int] = None,
    ) -> bool:
        """Attaches visual telemetry/media to conversation, scoped to session or specific id (Anara Standard)."""
        clean_name = speaker_name.strip().title() if speaker_name else None
        vis_json = json.dumps(visual_data, default=str) if visual_data else None
        vis_type = visual_data.get("visual_type", "hud") if visual_data else "hud"
        vis_url = visual_data.get("image_url") if visual_data else None
        sid = self._resolve_session_id(session_id) if session_id is not None else None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            target_id = None
            if conversation_id:
                target_id = conversation_id
            elif sid is not None:
                cursor.execute(
                    "SELECT id FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                    (sid,)
                )
                row = cursor.fetchone()
                if row:
                    target_id = row["id"]

            if target_id is None:
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
                if row:
                    target_id = row["id"]

            if not target_id:
                return False

            cursor.execute(
                "UPDATE conversations SET media_type = ?, media_url = ?, visual_data_json = ? WHERE id = ?",
                (vis_type, vis_url, vis_json, target_id),
            )
            conn.commit()
            updated = cursor.rowcount > 0
            if updated and hasattr(self, "_emit_mutation"):
                self._emit_mutation("conversation_updated", {"id": target_id, "visual_data": visual_data})
            return updated

    def get_recent_conversations(self, limit: int = 30, speaker_name: Optional[str] = None,
                                 session_id: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Retrieves recent conversation history from SQLite (newest first)."""
        sid = self._resolve_session_id(session_id) if session_id is not None else None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT id, speaker_name, user_text, ai_text, media_type, media_url,
                       visual_data_json, created_at, session_id
                FROM conversations
            """
            conds, params = [], []
            if sid is not None:
                conds.append("session_id = ?")
                params.append(sid)
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

            u = re.sub(r"```[\s\S]*?```", "[code block]", u)
            a = re.sub(r"```[\s\S]*?```", "[code block]", a)
            u = re.sub(r"\s+", " ", u).strip()
            a = re.sub(r"\s+", " ", a).strip()

            if len(u) > 200:
                u = u[:200] + "..."
            if len(a) > 200:
                a = a[:200] + "..."

            sp = r.get("speaker_name") or speaker_name or "User"
            if u:
                dialogue_turns.append(f"{sp}: {u}")
            if a:
                dialogue_turns.append(f"Anara: {a}")

        if not dialogue_turns:
            return ""

        return (
            "## Recent Conversation Context:\n"
            + "\n".join(dialogue_turns) + "\n"
        )


async def maybe_auto_title_session(session_id: int, user_text: str = "", ai_text: str = "") -> Optional[str]:
    """
    Public asynchronous entry point for auto-titling sessions (Anara Standard).
    Generates a concise 2-5 word title using fast auxiliary LLM if title is still default/placeholder.
    """
    if not session_id:
        return None
    try:
        from memory import memory_engine
        sess = await asyncio.to_thread(memory_engine.get_session, session_id)
        if not sess:
            return None
        current_title = (sess.get("title") or "").strip()
        is_placeholder = (
            not current_title
            or current_title.lower() in ["new chat", "new session", "new project", "session", "chat"]
            or current_title.lower().startswith(("session #", "chat #", "telegram chat (", "web chat (", "discord chat ("))
            or current_title.lower().endswith("]")
        )
        if not is_placeholder:
            return None

        # Build short dialogue context
        u = (user_text or "").strip()[:200]
        a = (ai_text or "").strip()[:200]
        if not u:
            msgs = await asyncio.to_thread(memory_engine.get_session_messages, session_id, 3)
            if msgs:
                u = (msgs[0].get("user_text") or "").strip()[:200]
                a = (msgs[0].get("ai_text") or "").strip()[:200]

        if not u:
            return None

        prompt = (
            "Generate a SHORT title (2-5 words) summarizing this conversation.\n"
            "Rules: match the language used by the user, no quotes, no trailing dot, capture the core topic directly.\n\n"
            f"User: {u}\nAnara: {a}\n\nTITLE:"
        )

        title = ""
        try:
            from core.capabilities import get_fast_auxiliary_model
            from providers.caller import call_universal_chat_model
            aux_model = get_fast_auxiliary_model()
            res = await asyncio.wait_for(
                call_universal_chat_model(
                    model_id=aux_model,
                    user_prompt=prompt,
                    max_tokens=25,
                    temperature=0.3,
                    read_only=True
                ),
                timeout=5.0
            )
            if res and isinstance(res, str):
                title = res.strip().strip('"\'').rstrip(".")
                title = re.sub(r"^(?:title|topic|subject)\s*[:=]\s*", "", title, flags=re.IGNORECASE).strip()
        except Exception as e:
            logger.debug(f"[ChatSessions] maybe_auto_title_session LLM error: {e}")

        fallback = u[:36] + ("..." if len(u) > 36 else "")
        final_title = (title or fallback)[:80]
        renamed = await asyncio.to_thread(memory_engine.rename_session, session_id, final_title)
        if renamed:
            logger.info(f"[ChatSessions] Successfully auto-titled session #{session_id}: {final_title!r}")
            return final_title
    except Exception as ex:
        logger.debug(f"[ChatSessions] maybe_auto_title_session error: {ex}")
    return None
