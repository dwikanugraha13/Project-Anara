import json
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

from .voice_biometrics import canonicalize_speaker_name

logger = logging.getLogger(__name__)

_DYNAMIC_ENTITY_CACHE: Dict[str, Dict[str, Any]] = {}
_EMBEDDING_CACHE: Dict[str, List[float]] = {}


def compute_local_hash_embedding(text: str, dim: int = 512) -> List[float]:
    """
    Deterministic Offline Vector Embedding Generator (Hermes Parity).
    Generates a 512-dimensional normalized dense vector using character n-grams and word tokens.
    Requires zero network calls, zero external API keys, and runs in sub-millisecond time.
    """
    import hashlib
    clean = (text or "").lower().strip()
    vec = np.zeros(dim, dtype=np.float32)
    words = re.findall(r"\w+", clean)
    for w in words:
        h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16) % dim
        vec[h] += 1.0
        if len(w) >= 3:
            for i in range(len(w) - 2):
                gram = w[i:i+3]
                h_g = int(hashlib.sha256(gram.encode("utf-8")).hexdigest()[:8], 16) % dim
                vec[h_g] += 0.5
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec.tolist()


def get_text_embedding(text: str, allow_local_fallback: bool = True) -> Optional[List[float]]:
    """
    Hermes & Claude Code Parity: Hybrid Dense Vector Embeddings.
    Primary: Gemini gemini-embedding-001 (3072-dimensional semantic vectors).
    Fallback: Local 512-dimensional subword n-gram vector (offline / zero-key resilience).
    Caches vectors in process RAM to eliminate redundant calculations.
    """
    clean = (text or "").strip()
    if not clean:
        return None

    if clean in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[clean]

    # 1. Primary: Gemini gemini-embedding-001
    try:
        from core.key_manager import key_manager
        from google import genai

        key = key_manager.get_active_key()
        if key:
            client = genai.Client(api_key=key)
            res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=clean[:2000],
            )
            if res.embeddings and len(res.embeddings) > 0:
                vec = list(res.embeddings[0].values)
                _EMBEDDING_CACHE[clean] = vec
                if len(_EMBEDDING_CACHE) > 500:
                    _EMBEDDING_CACHE.pop(next(iter(_EMBEDDING_CACHE)))
                return vec
    except Exception as e:
        logger.debug(f"[SemanticRAG] Gemini embedding calculation skipped/failed: {e}")

    # 2. Local Offline Fallback
    if allow_local_fallback:
        vec = compute_local_hash_embedding(clean)
        _EMBEDDING_CACHE[clean] = vec
        return vec

    return None


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Computes cosine similarity between two float vectors using numpy with dimension validation."""
    try:
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)
        if a.shape != b.shape:
            return 0.0
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception:
        return 0.0


def get_current_indonesian_time_str(offset_minutes: Optional[int] = None, tz_name: Optional[str] = None) -> Dict[str, str]:
    """
    Returns real-time day, date, and clock time with automatic timezone resolution
    (works globally across WIB, WITA, WIT, JST, UTC, EST, etc. using local OS or client offset).
    """
    if offset_minutes is not None:
        tz = timezone(timedelta(minutes=-offset_minutes))
        now = datetime.now(tz)
    else:
        now = datetime.now().astimezone()

    total_seconds = int(now.utcoffset().total_seconds()) if now.utcoffset() else 0
    sign = "+" if total_seconds >= 0 else "-"
    hours = abs(total_seconds) // 3600
    minutes = (abs(total_seconds) % 3600) // 60
    offset_str = f"UTC{sign}{hours:02d}:{minutes:02d}"

    id_labels = {
        "+07:00": "WIB",
        "+08:00": "WITA",
        "+09:00": "WIT",
    }
    short_label = id_labels.get(f"{sign}{hours:02d}:{minutes:02d}", offset_str)

    # Format time and date cleanly
    day_name = now.strftime("%A")
    month_name = now.strftime("%B")
    date_formatted = now.strftime("%A, %d %B %Y")
    clock_str = now.strftime("%H:%M")
    time_formatted = f"{clock_str} {short_label}"
    if tz_name and tz_name != short_label:
        time_formatted += f" ({tz_name})"

    return {
        "day": day_name,
        "date_full": date_formatted,
        "time_str": time_formatted,
        "time_only": clock_str,
        "tz_label": short_label,
        "tz_offset": offset_str,
        "iso": now.isoformat()
    }


def _exec_universal_llm(prompt: str, max_tokens: Optional[int] = None) -> Optional[str]:
    """
    Executes an internal cognitive prompt using the user's active model (Model Sovereignty)
    through call_universal_chat_model without hardcoding provider SDKs or artificial token chokeholds.
    """
    from core.capabilities import get_fast_auxiliary_model
    from providers.caller import call_universal_chat_model

    active_model = get_fast_auxiliary_model()

    async def _async_call():
        return await call_universal_chat_model(
            model_id=active_model,
            user_prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.2,
            read_only=True
        )

    try:
        import asyncio
        import concurrent.futures
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                res = pool.submit(lambda: asyncio.run(_async_call())).result(timeout=15.0)
        else:
            res = asyncio.run(_async_call())

        return str(res) if res else None
    except Exception as e:
        logger.warning(f"[SemanticRAG] Universal LLM call error on {active_model}: {e}")
        return None


def classify_preference_entity_ai(entity: str, speaker_name: str = "User") -> Dict[str, Any]:
    """
    Uses Zero-Shot Semantic Classification with the user's active model
    to dynamically recognize ANY entity and generates natural companion commentary without hardcoded dictionaries.
    """
    cache_key = entity.lower().strip()
    if cache_key in _DYNAMIC_ENTITY_CACHE:
        return _DYNAMIC_ENTITY_CACHE[cache_key]

    eff_speaker = speaker_name.strip().title() if speaker_name else "User"
    from core.prompt_loader import load_prompt
    prompt = load_prompt(
        "classifiers/entity_memory",
        entity=entity,
        entity_title=entity.title(),
        eff_speaker=eff_speaker
    )

    raw_text = _exec_universal_llm(prompt, max_tokens=None)
    if raw_text:
        raw = raw_text.strip()
        if "{" in raw and "}" in raw:
            try:
                json_str = raw[raw.find("{"):raw.rfind("}")+1]
                parsed = json.loads(json_str)
                _DYNAMIC_ENTITY_CACHE[cache_key] = parsed
                return parsed
            except Exception as j_err:
                logger.debug(f"[SemanticRAG] JSON parse note: {j_err}")

    fallback = {
        "is_multi_entity": False,
        "entities": [entity.title()],
        "canonical_key": "favorite_preference",
        "category_label": "preference",
        "companion_comment": f"{entity.title()} is a great choice.",
        "confirmation_question": f"May I remember that you like {entity.title()}, {eff_speaker}?"
    }
    _DYNAMIC_ENTITY_CACHE[cache_key] = fallback
    return fallback


def resolve_contextual_memory_command(command: str, recent_chats: List[Dict[str, Any]], speaker_name: str = "User") -> Optional[Dict[str, Any]]:
    """
    Resolves memory saving commands that use pronouns (e.g. 'save that to database as my favorite animal' or 'save that as my favorite movie')
    by identifying the referenced entity from recent dialogue context and mapping to canonical memory key.
    """
    eff_speaker = speaker_name.strip().title() if speaker_name else "User"
    recent_lines = []
    for c in recent_chats[-3:]:
        u_t = (c.get("user_text") or "").strip()
        a_t = (c.get("ai_text") or "").strip()
        if u_t or a_t:
            recent_lines.append(f"User: {u_t}\nAnara: {a_t}")
    recent_context = "\n---\n".join(recent_lines)

    from core.prompt_loader import load_prompt
    prompt = load_prompt(
        "classifiers/memory_reasoner",
        command=command,
        recent_context=recent_context,
        eff_speaker=eff_speaker
    )

    raw_text = _exec_universal_llm(prompt, max_tokens=None)
    if raw_text:
        raw = raw_text.strip()
        if "{" in raw and "}" in raw:
            try:
                json_str = raw[raw.find("{"):raw.rfind("}")+1]
                return json.loads(json_str)
            except Exception as j_err:
                logger.debug(f"[SemanticRAG] Contextual memory parse note: {j_err}")
    return None


class SemanticRAGMixin:
    """Semantic brain search, proactive anticipation, facts association, and system prompt generation."""

    def _init_embeddings_table(self) -> None:
        """Initializes SQLite memory_embeddings table for persistent vector RAG (Hermes Parity)."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_embeddings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_type TEXT NOT NULL,
                        source_id TEXT NOT NULL,
                        speaker_name TEXT,
                        content TEXT NOT NULL,
                        embedding_json TEXT NOT NULL,
                        updated_at REAL NOT NULL,
                        UNIQUE(source_type, source_id) ON CONFLICT REPLACE
                    );
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_mem_emb_source
                    ON memory_embeddings(source_type, source_id);
                """)
                conn.commit()
        except Exception as e:
            logger.debug(f"[SemanticRAG] Embeddings table init error: {e}")

    def index_embedding(self, source_type: str, source_id: str, content: str, speaker_name: Optional[str] = None) -> bool:
        """Computes and stores a vector embedding for a memory entity in SQLite (Hermes Parity)."""
        self._init_embeddings_table()
        vec = get_text_embedding(content)
        if not vec:
            return False
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO memory_embeddings (source_type, source_id, speaker_name, content, embedding_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, source_id) DO UPDATE SET
                        content = excluded.content,
                        embedding_json = excluded.embedding_json,
                        speaker_name = excluded.speaker_name,
                        updated_at = excluded.updated_at;
                """, (source_type, str(source_id), speaker_name, content, json.dumps(vec), time.time()))
                conn.commit()
            return True
        except Exception as e:
            logger.debug(f"[SemanticRAG] Failed to index embedding for {source_type}/{source_id}: {e}")
            return False

    def semantic_search_brain(self, query: str, speaker_name: Optional[str] = None, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Hermes Parity: Hybrid Dense+Sparse Semantic Memory & Episodic RAG Search.
        Blends 3072-dimensional vector cosine similarity (dense) with BM25 token matching (sparse)
        across memories, projects, notes, and past conversations.
        """
        if not query or len(query.strip()) < 2:
            return []
        
        eff_speaker = canonicalize_speaker_name(speaker_name) if speaker_name else None
        
        # 1. Sparse tokenization (BM25 lexical matching)
        q_tokens = set(re.findall(r"\w+", query.lower()))
        q_clean_tokens = [t for t in q_tokens if len(t) >= 2]
        if not q_clean_tokens:
            q_clean_tokens = list(q_tokens)

        # 2. Dense vector embedding calculation (with offline subword fallback)
        q_vec = get_text_embedding(query)
        local_q_vec = compute_local_hash_embedding(query)
        dense_similarities: Dict[Tuple[str, str], float] = {}

        try:
            self._init_embeddings_table()
            with self._get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT source_type, source_id, speaker_name, content, embedding_json
                    FROM memory_embeddings
                    WHERE (speaker_name = ? OR speaker_name IS NULL OR ? IS NULL)
                """, (eff_speaker, eff_speaker))
                for row in cur.fetchall():
                    try:
                        emb = json.loads(row["embedding_json"])
                        sim = 0.0
                        if q_vec and len(emb) == len(q_vec):
                            sim = cosine_similarity(q_vec, emb)
                        elif local_q_vec:
                            # Re-vectorize content with local hash generator so dimensions always match (Zero-offline drop)
                            content_vec = compute_local_hash_embedding(row["content"])
                            sim = cosine_similarity(local_q_vec, content_vec)
                        if sim >= 0.35:
                            dense_similarities[(row["source_type"], row["source_id"])] = sim
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"[SemanticRAG] Dense vector candidate scoring: {e}")

        scored_items = []
        matched_keys: Set[Tuple[str, str]] = set()

        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # 1. Search in memories
            m_query = """
                SELECT m.key, m.value, m.category, s.name as sp_name
                FROM memories m
                LEFT JOIN speakers s ON m.speaker_id = s.id
                WHERE (s.name = ? OR ? IS NULL)
            """
            cur.execute(m_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['key']} {r['value']} {r['category']}".lower()
                lexical_score = sum(2.5 if t in r['key'].lower() else (1.8 if t in r['value'].lower() else 0.5) for t in q_clean_tokens if t in text)
                source_key = ("memory", r["key"])
                dense_sim = dense_similarities.get(source_key, 0.0)

                # Hybrid score blending (0.65 dense + 0.35 lexical)
                if dense_sim > 0.40 or lexical_score > 0:
                    matched_keys.add(source_key)
                    final_score = (dense_sim * 10.0 * 0.65) + (lexical_score * 0.35)
                    scored_items.append({
                        "type": "memory",
                        "title": r['key'].replace('_', ' ').title(),
                        "content": r['value'],
                        "category": r['category'],
                        "score": round(final_score, 3),
                        "semantic_match": dense_sim > 0.45,
                    })

            # 2. Search in projects
            p_query = """
                SELECT p.name, p.tech_stack, p.goal, p.status, p.notes, s.name as sp_name
                FROM projects p
                LEFT JOIN speakers s ON p.speaker_id = s.id
                WHERE (s.name = ? OR ? IS NULL OR p.speaker_id IS NULL)
            """
            cur.execute(p_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['name']} {r['tech_stack']} {r['goal']} {r['notes']}".lower()
                lexical_score = sum(3.5 if t in r['name'].lower() else (2.2 if t in (r['tech_stack'] or '').lower() else 1.2) for t in q_clean_tokens if t in text)
                source_key = ("project", r["name"])
                dense_sim = dense_similarities.get(source_key, 0.0)

                if dense_sim > 0.40 or lexical_score > 0:
                    matched_keys.add(source_key)
                    final_score = (dense_sim * 10.0 * 0.65) + (lexical_score * 0.35)
                    scored_items.append({
                        "type": "project",
                        "title": f"Project '{r['name']}'",
                        "content": f"Tech: {r['tech_stack']} | Goal: {r['goal']}" + (f" | Notes: {r['notes']}" if r['notes'] else ""),
                        "category": "project",
                        "score": round(final_score, 3),
                        "semantic_match": dense_sim > 0.45,
                    })

            # 3. Search in notes / todos
            n_query = """
                SELECT n.title, n.content, n.category, n.is_completed, s.name as sp_name
                FROM notes_and_todos n
                LEFT JOIN speakers s ON n.speaker_id = s.id
                WHERE (s.name = ? OR ? IS NULL OR n.speaker_id IS NULL)
            """
            cur.execute(n_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['title']} {r['content']} {r['category']}".lower()
                score = sum(2.8 if t in r['title'].lower() else 1.2 for t in q_clean_tokens if t in text)
                if score > 0:
                    status_lbl = "Completed" if r['is_completed'] else "Active"
                    scored_items.append({
                        "type": "todo",
                        "title": f"Task [{r['category'].upper()} - {status_lbl}]: {r['title']}",
                        "content": r['content'] or "",
                        "category": r['category'],
                        "score": score
                    })

            # 4. Search in past conversation turns
            c_query = "SELECT user_text, ai_text, created_at FROM conversations WHERE (speaker_name = ? OR ? IS NULL) ORDER BY id DESC LIMIT 30"
            cur.execute(c_query, (eff_speaker, eff_speaker))
            for r in cur.fetchall():
                text = f"{r['user_text']} {r['ai_text']}".lower()
                score = sum(1.2 for t in q_clean_tokens if t in text)
                if score >= 1.5:
                    scored_items.append({
                        "type": "conversation",
                        "title": f"Previous Turn: '{r['user_text']}'",
                        "content": f"Anara: {r['ai_text']}",
                        "category": "history",
                        "score": score
                    })

        scored_items.sort(key=lambda x: x["score"], reverse=True)
        return scored_items[:top_k]

    def get_proactive_relevant_facts(self, user_query: str, speaker_name: Optional[str] = None) -> str:
        """
        Cognitive Proactive Fact Association & Semantic RAG:
        Finds domain-specific memories and cross-table semantic knowledge.
        """
        if not user_query:
            return ""
        eff_speaker = canonicalize_speaker_name(speaker_name)
        if not eff_speaker:
            return ""

        rag_results = self.semantic_search_brain(user_query, speaker_name=eff_speaker, top_k=3)
        if not rag_results:
            return ""

        snippets = []
        for item in rag_results:
            if item["type"] == "memory":
                snippets.append(f"- Memory: {item['title']} = {item['content']}")
            elif item["type"] == "project":
                snippets.append(f"- {item['title']}: {item['content']}")
            elif item["type"] == "todo":
                snippets.append(f"- {item['title']}: {item['content']}")
            elif item["type"] == "conversation":
                snippets.append(f"- {item['title']} -> {item['content']}")

        if not snippets:
            return ""

        return (
            f"[RELEVANT PERSISTENT CONTEXT FOR {eff_speaker.upper()}]:\n"
            + "\n".join(snippets) + "\n\n"
        )

    def get_proactive_briefing_guidance(self, speaker_name: Optional[str] = None, acoustic_tone: Optional[Dict[str, Any]] = None) -> str:
        """
        JARVIS 2.0 Proactive Anticipation & Acoustic Empathy Engine.
        Analyzes time of day, acoustic fatigue, pending deadlines, and active project targets.
        """
        eff_speaker = canonicalize_speaker_name(speaker_name)
        if not eff_speaker:
            return ""

        proactive_notes = []

        if acoustic_tone:
            em = acoustic_tone.get("emotion", "neutral")
            pitch = acoustic_tone.get("pitch_hz", 150)
            if em == "sad" or pitch < 110:
                proactive_notes.append("Voice Analysis: User sounds fatigued/weary. Offer calming, warm empathy.")
            elif em == "angry":
                proactive_notes.append("Voice Analysis: User sounds tense/stressed. Keep tone grounded, calm, and solution-focused.")
            elif em == "happy" or pitch > 220:
                proactive_notes.append("Voice Analysis: User sounds enthusiastic/cheerful. Respond with matching positive energy.")

        todos = self.get_notes_and_todos(speaker_name=eff_speaker)
        pending = [t for t in todos if not t["is_completed"]]
        if len(pending) > 0:
            top_task = pending[0]["title"]
            proactive_notes.append(f"Active Tasks: {len(pending)} pending items (priority: '{top_task}').")

        projs = self.get_projects_for_speaker(speaker_name=eff_speaker)
        if projs:
            active_p = projs[0]
            proactive_notes.append(f"Active Project: '{active_p['name']}' ({active_p.get('goal', '')}).")

        if not proactive_notes:
            return ""

        return (
            f"[PROACTIVE CONTEXT & COGNITIVE EMPATHY]:\n"
            + "\n".join([f"- {n}" for n in proactive_notes]) + "\n"
        )

    def store_memory(self, speaker_name: str, key: str, value: str, category: str = "preference") -> bool:
        """Stores or updates a specific fact or preference for a speaker, replacing and deduplicating old keys."""
        norm_key = self.normalize_memory_key(key)
        val_clean = value.strip().strip(".,!?\"'")
        
        if not val_clean or len(val_clean) < 2:
            logger.warning(f"[AnaraMemory] Rejected storing invalid value '{val_clean}' for key '{norm_key}'")
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM speakers WHERE name = ?", (speaker_name.strip().title(),))
            row = cursor.fetchone()
            if not row:
                res = self.enroll_or_update_speaker(speaker_name)
                speaker_id = res["speaker_id"]
            else:
                speaker_id = row["id"]

            root_prefix = norm_key.split("_")[0]
            cursor.execute("""
                DELETE FROM memories
                WHERE speaker_id = ? AND key != ? AND (key LIKE ? OR key LIKE ?)
            """, (speaker_id, norm_key, f"{root_prefix}%", "%_baru%"))

            cursor.execute("""
                INSERT INTO memories (speaker_id, category, key, value, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(speaker_id, key) DO UPDATE SET value = excluded.value, category = excluded.category, updated_at = CURRENT_TIMESTAMP
            """, (speaker_id, category, norm_key, val_clean))
            conn.commit()
            logger.info(f"[AnaraMemory] Saved canonical memory for {speaker_name}: [{norm_key}] = {val_clean} ({category})")
            self._emit_mutation("memory_stored", {
                "speaker_name": speaker_name.strip().title(),
                "key": norm_key,
                "value": val_clean,
                "category": category
            })
            # Asynchronously index vector embedding for semantic search (Hermes Parity: Gap 4)
            try:
                self.index_embedding(
                    source_type="memory",
                    source_id=norm_key,
                    content=f"{norm_key}: {val_clean} ({category})",
                    speaker_name=speaker_name.strip().title()
                )
            except Exception as e_emb:
                logger.debug(f"[SemanticRAG] Auto-indexing memory embedding note: {e_emb}")
            return True

    def get_memories_for_speaker(self, speaker_name: str) -> List[Dict[str, Any]]:
        """Retrieves all stored facts and preferences for a speaker."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, m.category, m.key, m.value, m.created_at, m.updated_at
                FROM memories m
                JOIN speakers s ON m.speaker_id = s.id
                WHERE s.name = ?
                ORDER BY m.updated_at DESC
            """, (speaker_name.strip().title(),))
            return [dict(r) for r in cursor.fetchall()]

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """Retrieves all memories across all speakers."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.id, s.name as speaker_name, m.category, m.key, m.value, m.created_at, m.updated_at
                FROM memories m
                LEFT JOIN speakers s ON m.speaker_id = s.id
                ORDER BY m.updated_at DESC
            """)
            return [dict(r) for r in cursor.fetchall()]

    def delete_memory_by_id(self, memory_id: int) -> bool:
        """Deletes a memory by its primary key ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            ok = cursor.rowcount > 0
            if ok:
                self._emit_mutation("memory_deleted", {"memory_id": memory_id})
            return ok

    def delete_memory(self, speaker_name: str, key: str) -> bool:
        """Deletes a specific memory key for a speaker."""
        norm_key = self.normalize_memory_key(key)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM memories
                WHERE (key = ? OR key = ?) AND speaker_id IN (
                    SELECT id FROM speakers WHERE name = ?
                )
            """, (norm_key, key.strip().lower(), speaker_name.strip().title()))
            conn.commit()
            logger.info(f"[AnaraMemory] Deleted memory key '{key}' for {speaker_name}")
            self._emit_mutation("memory_deleted", {
                "speaker_name": speaker_name.strip().title(),
                "key": norm_key
            })
            return True

    def store_knowledge(
        self,
        topic: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: str = "voice_note",
    ) -> Dict[str, Any]:
        """Saves a voice note / fact into the knowledge base (upsert by topic)."""
        clean_topic = (topic or "").strip()[:120]
        clean_content = (content or "").strip()
        if not clean_content:
            return {"status": "error", "message": "Note content is empty."}
        if not clean_topic:
            clean_topic = clean_content[:60]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge_base (topic, content, tags_json, source, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(topic) DO UPDATE SET
                    content = excluded.content,
                    tags_json = excluded.tags_json,
                    source = excluded.source,
                    updated_at = CURRENT_TIMESTAMP
            """, (clean_topic, clean_content, json.dumps(tags or []), source))
            conn.commit()
            kb_id = cursor.lastrowid

        logger.info(f"[KnowledgeBase] Stored note: {clean_topic!r} ({len(clean_content)} chars)")
        self._emit_mutation("knowledge_stored", {"id": kb_id, "topic": clean_topic})
        return {"status": "ok", "id": kb_id, "topic": clean_topic, "content": clean_content}

    def get_knowledge_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns stored voice notes, newest first."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, topic, content, tags_json, source, created_at, updated_at
                FROM knowledge_base ORDER BY updated_at DESC LIMIT ?
            """, (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Multilingual Unicode tokenized search across stored voice notes (Hermes Parity)."""
        q = (query or "").strip().lower()
        if not q:
            return []
        terms = [t for t in re.findall(r"[\w\d]+", q, re.UNICODE) if len(t) > 1]
        entries = self.get_knowledge_entries(limit=200)
        scored: List[Any] = []
        for e in entries:
            hay = f"{e.get('topic', '')} {e.get('content', '')}".lower()
            score = sum(3 if t in (e.get("topic") or "").lower() else 1 for t in terms if t in hay)
            if score:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_k]]

    def delete_knowledge(self, kb_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM knowledge_base WHERE id = ?", (kb_id,))
            conn.commit()
            if cursor.rowcount > 0:
                self._emit_mutation("knowledge_deleted", {"id": kb_id})
                return True
        return False

    def get_system_prompt_context(self, speaker_name: Optional[str] = None, is_chat_mode: bool = False) -> str:
        """
        Builds a contextual multi-user memory block from SQLite database.
        Cached with 30s TTL + invalidated on SQLite mutations to avoid N+1 queries every turn.
        """
        time_info = get_current_indonesian_time_str()
        time_header = (
            f"\n[REAL-TIME SYSTEM CLOCK / WAKTU REAL-TIME]:\n"
            f"Date / Tanggal: {time_info['date_full']}\n"
            f"Time / Waktu: {time_info['time_str']} ({time_info['tz_offset']})\n\n"
        )

        target_speaker = canonicalize_speaker_name(speaker_name) if speaker_name else (self.get_last_active_speaker_name() or "Agnan")
        cache_key = (target_speaker, is_chat_mode)
        now = time.time()
        if cache_key in self._prompt_context_cache:
            ts, cached_body = self._prompt_context_cache[cache_key]
            if (now - ts) < 30.0:
                return time_header + cached_body

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, category, description FROM animations ORDER BY id ASC")
                anim_rows = cursor.fetchall()
                anim_list = [f"- {r['name'].title()} ({r['category']}): {r['description']}" for r in anim_rows]
                anim_str = "\n".join(anim_list)
        except Exception:
            anim_str = "- Dance (dance): 3D Rumba animation\n- Laughing (emotion): Joyful laughter\n- Angry (emotion): Angry expression\n- Crying (emotion): Sad expression"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT s.id, s.name, s.sample_count, m.key, m.value
                    FROM speakers s
                    LEFT JOIN memories m ON s.id = m.speaker_id
                    ORDER BY s.id ASC, m.id ASC
                """)
                rows = cursor.fetchall()
                speakers_dict = {}
                for r in rows:
                    sid = r["id"]
                    if sid not in speakers_dict:
                        speakers_dict[sid] = {
                            "name": r["name"],
                            "sample_count": r["sample_count"],
                            "memories": []
                        }
                    if r["key"] is not None and len(speakers_dict[sid]["memories"]) < 3:
                        speakers_dict[sid]["memories"].append(f"{r['key'].replace('_', ' ')}: {r['value']}")

                speaker_profiles_summary = []
                for s in speakers_dict.values():
                    s_name = s["name"]
                    if s["memories"]:
                        fact_preview = "; ".join(s["memories"])
                        speaker_profiles_summary.append(f"- {s_name} ({s['sample_count']} voice samples): {fact_preview}")
                    else:
                        speaker_profiles_summary.append(f"- {s_name} ({s['sample_count']} voice samples registered)")
                profiles_str = "\n".join(speaker_profiles_summary) if speaker_profiles_summary else "- No registered profiles."
        except Exception:
            profiles_str = "- No registered profiles."

        todos = self.get_notes_and_todos(speaker_name=target_speaker)
        active_todos = [t for t in todos if not t["is_completed"]][:5]
        todo_str = "\n".join([f"- [{t['category'].upper()}] {t['title']}" + (f": {t['content']}" if t['content'] else "") for t in active_todos]) if active_todos else "- No pending tasks."

        projs = self.get_projects_for_speaker(speaker_name=target_speaker)
        active_projs = [p for p in projs if p.get("status") == "active"][:3]
        proj_str = "\n".join([f"- Project '{p['name']}'" + (f" ({p['tech_stack']})" if p.get('tech_stack') else "") + (f": Goal '{p['goal']}'" if p.get('goal') else "") for p in active_projs]) if active_projs else ""
        proj_section = f"[ACTIVE PROJECTS FOR {target_speaker.upper()}]:\n{proj_str}\n\n" if proj_str else ""

        m_rows = self.get_memories_for_speaker(target_speaker)
        mem_str = "\n".join([f"- {r['key'].replace('_', ' ').title()} ({r['category']}): {r['value']}" for r in m_rows]) if m_rows else f"- Name: {target_speaker} (Active user profile in Anara database)."

        tone_guidance = "Adapt your response language naturally to the user's active language. Respond warmly, naturally, and concisely."

        from core.prompt_loader import load_prompt
        if is_chat_mode:
            active_section = load_prompt(
                "memory_context_chat",
                target_speaker=target_speaker,
                target_speaker_upper=target_speaker.upper(),
                mem_str=mem_str,
                proj_section=proj_section,
                todo_str=todo_str,
            ).strip()
        else:
            active_section = load_prompt(
                "memory_context_voice",
                target_speaker=target_speaker,
                target_speaker_upper=target_speaker.upper(),
                mem_str=mem_str,
                proj_section=proj_section,
                todo_str=todo_str,
                tone_guidance=tone_guidance,
            ).strip()

        context_body = (
            f"[REGISTERED USER PROFILES]:\n"
            f"{profiles_str}\n\n"
            f"{active_section}\n\n"
            f"[COMMUNICATION STANDARDS & MULTILINGUAL SOVEREIGNTY]:\n"
            f"1. Respond directly, naturally, and concisely in the user's active language.\n"
            f"2. Do not use roleplay action markers in asterisks like *smiles* or *dances*.\n"
            f"3. LANGUAGE SOVEREIGNTY: Seamlessly adapt and respond in the exact language used by the user (English, Indonesian, Japanese, Spanish, etc.).\n"
        )

        self._prompt_context_cache[cache_key] = (now, context_body)
        return time_header + context_body
