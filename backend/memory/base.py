import asyncio
import contextlib
import json
import logging
import os
import sqlite3
from typing import Optional, Dict, Any, List, Tuple, Callable

from constants import get_anara_db_path

logger = logging.getLogger(__name__)

# DB Path resolves to canonical ANARA_HOME/anara_brain.db (Hermes Parity)
DB_PATH = get_anara_db_path()

MAX_VOICE_SAMPLES = 30          # sample counter cap per profile (voiceprint considered mature)
MATURE_ADAPT_INTERVAL = 600.0   # seconds; mature profiles adapt at most once per 10 minutes


class BaseMemoryEngine:
    """Core SQLite connection, schema lifecycle, mutation events, and database seeding."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._pending_proposals: Dict[str, Dict[str, Any]] = {}
        self._mutation_listeners: List[Callable[[str, Dict[str, Any]], Any]] = []
        self._last_adapt_ts: Dict[int, float] = {}
        self._prompt_context_cache: Dict[Tuple[str, bool], Tuple[float, str]] = {}
        self._init_db()

    def register_mutation_listener(self, listener: Callable[[str, Dict[str, Any]], Any]):
        """Registers a callback for real-time memory/todo mutations (for live WebSocket sync)."""
        if listener not in self._mutation_listeners:
            self._mutation_listeners.append(listener)

    def _emit_mutation(self, event_type: str, data: Dict[str, Any]):
        """Invokes all registered mutation listeners safely and invalidates prompt context cache."""
        self._prompt_context_cache.clear()
        for listener in self._mutation_listeners:
            try:
                res = listener(event_type, data)
                if asyncio.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        res.close()
            except Exception as e:
                logger.warning(f"[MemoryMutation] Error in listener callback: {e}")

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=15000;")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initializes full database schema with WAL mode & unique constraints."""
        try:
            init_conn = sqlite3.connect(self.db_path, timeout=15.0)
            init_conn.execute("PRAGMA journal_mode=WAL;")
            init_conn.execute("PRAGMA synchronous=NORMAL;")
            init_conn.execute("PRAGMA busy_timeout=15000;")
            init_conn.commit()
            init_conn.close()
        except Exception as e:
            logger.warning(f"[DB] Could not set WAL mode: {e}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Registered Speakers & Voice Biometrics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS speakers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE COLLATE NOCASE,
                    voice_embedding TEXT,
                    sample_count INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. Categorized Long-Term Memories & Facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id INTEGER,
                    category TEXT,
                    key TEXT,
                    value TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE CASCADE,
                    UNIQUE(speaker_id, key) ON CONFLICT REPLACE
                );
            """)
            
            # 3. Notes & To-Do Lists (JARVIS Task Tracker)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notes_and_todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id INTEGER,
                    category TEXT DEFAULT 'todo', -- 'todo', 'note', 'reminder'
                    title TEXT NOT NULL,
                    content TEXT,
                    is_completed INTEGER DEFAULT 0,
                    due_date TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE SET NULL
                );
            """)
            
            # 4. Episodic Multi-Session Conversation Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_name TEXT,
                    speaker_id INTEGER,
                    user_text TEXT,
                    ai_text TEXT,
                    media_type TEXT,
                    media_url TEXT,
                    visual_data_json TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 5. Knowledge Base & Custom Learned Schematics
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT UNIQUE COLLATE NOCASE,
                    content TEXT NOT NULL,
                    tags_json TEXT,
                    source TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 6. 3D Animations & Behaviors
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS animations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE COLLATE NOCASE,
                    category TEXT,
                    emotion TEXT,
                    gesture TEXT,
                    intensity REAL DEFAULT 0.8,
                    duration_sec REAL DEFAULT 3.0,
                    keywords_json TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 7. User Personal Projects & Work Context
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_id INTEGER,
                    name TEXT NOT NULL,
                    tech_stack TEXT,
                    goal TEXT,
                    status TEXT DEFAULT 'active', -- 'active', 'completed', 'paused'
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (speaker_id) REFERENCES speakers(id) ON DELETE CASCADE
                );
            """)

            # 7b. Chat Sessions (ChatGPT/Claude-style conversation threads)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    speaker_name TEXT,
                    message_count INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    is_pinned INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated
                ON chat_sessions(is_archived, updated_at DESC);
            """)

            # 8. Acoustic Emotion History (Emotion-Aware Anara)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emotion_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_name TEXT,
                    emotion TEXT NOT NULL,
                    pitch_hz REAL DEFAULT 0,
                    rms REAL DEFAULT 0,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_emotion_history_speaker_time
                ON emotion_history(speaker_name, created_at DESC);
            """)

            # 9. Music Playlists (Smart Playlist Engine)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE,
                    speaker_name TEXT,
                    last_index INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, speaker_name) ON CONFLICT REPLACE
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT,
                    channel TEXT,
                    thumbnail TEXT,
                    duration TEXT,
                    position INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
                );
            """)

            # 10. Media Play History (personal recommendations)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    speaker_name TEXT,
                    kind TEXT DEFAULT 'music',
                    video_id TEXT NOT NULL,
                    title TEXT,
                    channel TEXT,
                    thumbnail TEXT,
                    duration TEXT,
                    played_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 10b. Multi-Account AI Model Keys Pool
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    account_label TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    requests_count INTEGER DEFAULT 0,
                    cooldown_until REAL DEFAULT 0.0,
                    is_enabled INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 11. Communication Contacts (WhatsApp, Telegram, Phone Book)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE,
                    phone_number TEXT NOT NULL,
                    platform TEXT DEFAULT 'whatsapp',
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, platform) ON CONFLICT REPLACE
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_contacts_name
                ON contacts(name COLLATE NOCASE);
            """)

            # 12. Application Settings Key-Value Store (Telegram tokens, Google configs, integrations)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 14. Autonomous Anara Agent Skills & Procedural Learning Engine
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE COLLATE NOCASE,
                    category TEXT DEFAULT 'general',
                    description TEXT NOT NULL,
                    trigger_keywords_json TEXT,
                    procedure_steps_json TEXT NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    learned_from_experience INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_skills_active
                ON agent_skills(is_active, usage_count DESC);
            """)

            # 15. Custom Providers (OpenAI & Anthropic Compatible, vLLM, 9Router, Local)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    prefix TEXT UNIQUE COLLATE NOCASE NOT NULL,
                    api_type TEXT DEFAULT 'chat_completions',
                    base_url TEXT NOT NULL,
                    api_key TEXT,
                    default_model TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 16. Hidden / Blacklisted Models (User can prune unwanted models from catalog)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hidden_models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id TEXT UNIQUE COLLATE NOCASE NOT NULL,
                    provider TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 17. Token Usage & Credit Tracking Logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS token_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    model_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    estimated_cost REAL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_token_usage_created
                ON token_usage_logs(created_at DESC);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_speaker_id
                ON memories(speaker_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_speaker_name
                ON conversations(speaker_name);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_notes_speaker_cat
                ON notes_and_todos(speaker_id, category);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_projects_speaker_id
                ON projects(speaker_id);
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_media_history_speaker
                ON media_history(speaker_name);
            """)

            # ── Dynamic Column Migrations for Existing Databases ──
            try:
                cursor.execute("ALTER TABLE ai_accounts ADD COLUMN is_enabled INTEGER DEFAULT 1")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE speakers ADD COLUMN voice_snapshots_json TEXT")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE speakers ADD COLUMN preferred_tone TEXT DEFAULT 'balanced'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE conversations ADD COLUMN session_id INTEGER")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN workspace_info_json TEXT")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN pending_plan_json TEXT")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN run_type TEXT DEFAULT 'interactive'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN trust_level TEXT DEFAULT 'supervised'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN session_type TEXT DEFAULT 'chat'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN channel TEXT DEFAULT 'web'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE chat_sessions ADD COLUMN session_mode TEXT DEFAULT 'conversational'")
            except Exception:
                pass
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_type
                    ON chat_sessions(session_type, is_archived, updated_at DESC);
                """)
            except Exception:
                pass
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_conversations_session
                    ON conversations(session_id, id DESC);
                """)
            except Exception:
                pass

            conn.commit()
            
            # ── Backfill: group legacy conversations into chat sessions ──
            try:
                cursor.execute(
                    "SELECT id, speaker_name, user_text, created_at FROM conversations "
                    "WHERE session_id IS NULL ORDER BY id ASC"
                )
                orphans = cursor.fetchall()
                if orphans:
                    from datetime import datetime as _dt

                    def _parse(ts):
                        try:
                            return _dt.fromisoformat(str(ts).replace("Z", "+00:00").split("+")[0])
                        except Exception:
                            return None

                    session_id = None
                    prev_time = None
                    grouped = 0
                    for row in orphans:
                        cur_time = _parse(row["created_at"])
                        gap_too_big = (
                            prev_time is None
                            or cur_time is None
                            or (cur_time - prev_time).total_seconds() > 1800
                        )
                        if gap_too_big:
                            raw_title = (row["user_text"] or "Session").strip()
                            title = (raw_title[:44] + "...") if len(raw_title) > 44 else raw_title
                            cursor.execute(
                                "INSERT INTO chat_sessions (title, speaker_name, created_at, updated_at) "
                                "VALUES (?, ?, ?, ?)",
                                (title or "Previous Session", row["speaker_name"],
                                 row["created_at"], row["created_at"])
                            )
                            session_id = cursor.lastrowid
                            grouped += 1
                        cursor.execute(
                            "UPDATE conversations SET session_id = ? WHERE id = ?",
                            (session_id, row["id"])
                        )
                        prev_time = cur_time

                    cursor.execute("""
                        UPDATE chat_sessions SET message_count = (
                            SELECT COUNT(*) FROM conversations WHERE conversations.session_id = chat_sessions.id
                        )
                    """)
                    conn.commit()
                    logger.info(
                        f"[ChatSessions] Backfilled {len(orphans)} legacy message(s) into {grouped} session(s)"
                    )
            except Exception as e:
                logger.warning(f"[ChatSessions] Backfill error: {e}")

            # ── Purge control frames that leaked into conversation memory ──
            try:
                cursor.execute("""
                    DELETE FROM conversations
                    WHERE user_text LIKE '{%"type"%'
                       OR user_text LIKE '%{"type":"dance_%'
                """)
                if cursor.rowcount > 0:
                    logger.info(f"[AnaraMemory] Purged {cursor.rowcount} polluted control-frame conversation(s)")
                conn.commit()
            except Exception as e:
                logger.warning(f"[AnaraMemory] Control-frame purge error: {e}")

            # ── Tighten dance trigger keywords ──
            try:
                cursor.execute(
                    "UPDATE animations SET keywords_json = ? WHERE name = 'dance' OR category = 'dance'",
                    (json.dumps(["dance", "dancing", "rumba"]),)
                )
                if cursor.rowcount > 0:
                    logger.info("[AnaraMemory] Dance keywords tightened")
                conn.commit()
            except Exception as e:
                logger.warning(f"[AnaraMemory] Dance keyword migration error: {e}")

            # ── One-time clamp of runaway sample counters to the mature cap ──
            try:
                cursor.execute(
                    "UPDATE speakers SET sample_count = ? WHERE sample_count > ?",
                    (MAX_VOICE_SAMPLES, MAX_VOICE_SAMPLES)
                )
                if cursor.rowcount > 0:
                    logger.info(f"[Voice Biometrics] Clamped {cursor.rowcount} profile sample counter(s) to cap {MAX_VOICE_SAMPLES}")
                conn.commit()
            except Exception as e:
                logger.warning(f"[Voice Biometrics] Sample cap migration error: {e}")

            self._seed_default_animations(conn)
            self._seed_default_notes(conn)
            self._seed_default_skills(conn)
            logger.info(f"[AnaraMemory] SQLite Brain initialized at {self.db_path}")

    def _seed_default_animations(self, conn: sqlite3.Connection):
        """Seeds standard built-in 3D animations and behavior profiles if not yet present."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM animations")
        if cursor.fetchone()[0] > 0:
            return

        defaults = [
            ("dance", "dance", "dance", "dance", 1.0, 9.0, "[]", "3D Latin Rumba celebratory animation"),
            ("angry", "emotion", "angry", "angry_pointing", 0.9, 4.0, "[]", "Stern assertive expression with pointing gesture"),
            ("crying", "emotion", "sad", "sad", 0.85, 4.0, "[]", "Empathetic emotional expression with head lowered"),
            ("laughing", "emotion", "happy", "joy", 0.95, 4.0, "[]", "Joyful celebration and laughter animation"),
            ("shy", "emotion", "shy", "shy_movement", 0.8, 3.5, "[]", "Humble flattered gesture and pleasant smile"),
            ("salute", "gesture", "happy", "salute", 0.85, 3.0, "[]", "Professional agent salute posture"),
            ("greeting", "gesture", "happy", "wave", 0.85, 3.0, "[]", "Friendly wave greeting gesture"),
            ("thinking", "gesture", "thinking", "think", 0.75, 3.5, "[]", "Analytical thinking pose with hand at chin"),
            ("empathy", "emotion", "empathetic", "empathy", 0.8, 3.5, "[]", "Calming supportive posture and focused gaze"),
            ("agree", "reaction", "happy", "nod", 0.75, 2.5, "[]", "Affirmative nodding gesture"),
            ("disagree", "reaction", "neutral", "shake", 0.75, 2.5, "[]", "Gentle head shake disagreement reaction"),
            ("explaining", "gesture", "curious", "explaining", 0.75, 3.0, "[]", "Open-handed informative explanatory gesture")
        ]

        cursor.executemany("""
            INSERT INTO animations (name, category, emotion, gesture, intensity, duration_sec, keywords_json, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, defaults)
        conn.commit()
        logger.info(f"[AnaraMemory] Seeded {len(defaults)} default animations into SQLite database.")

    def _seed_default_notes(self, conn: sqlite3.Connection):
        """Seeds standard welcoming notes/todos if table is empty."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notes_and_todos")
        if cursor.fetchone()[0] > 0:
            return

        defaults = [
            (None, "todo", "Explore Anara Capabilities", "Ask Anara to analyze code, inspect workspace, or run testing suites.", 0, None),
            (None, "note", "Anara Autonomous Agent Protocol", "Anara operates with persistent memory, autonomous multi-tool execution, and safety-gated plan/build modes.", 0, None)
        ]
        cursor.executemany("""
            INSERT INTO notes_and_todos (speaker_id, category, title, content, is_completed, due_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, defaults)
        conn.commit()

    def _seed_default_skills(self, conn: sqlite3.Connection):
        """Hermes Parity: Skills are managed directly from filesystem skills/ (agentskills.io standard)."""
        pass

    def get_brain_stats(self) -> Dict[str, Any]:
        """Returns database node counts and physical size telemetry."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            mem_c = cursor.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            notes_c = cursor.execute("SELECT COUNT(*) FROM notes_and_todos").fetchone()[0]
            conv_c = cursor.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            sess_c = cursor.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
            skills_c = cursor.execute("SELECT COUNT(*) FROM agent_skills").fetchone()[0]
            spk_c = cursor.execute("SELECT COUNT(*) FROM speakers").fetchone()[0]

        size_b = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
        return {
            "memories_count": mem_c,
            "notes_count": notes_c,
            "conversations_count": conv_c,
            "sessions_count": sess_c,
            "skills_count": skills_c,
            "speakers_count": spk_c,
            "db_size_bytes": size_b,
        }
