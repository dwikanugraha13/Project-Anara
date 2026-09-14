"""
emotion_engine.py

Dynamic Database-Driven Emotion & Animation Awareness System for 3D AI Avatar.
Loads all animation profiles, trigger keywords, emotions, and gestures dynamically
from the SQLite database table 'animations' in anara_brain.db.

No hardcoded lists — fully editable and extensible by the user via SQLite or voice commands.
"""

import json
import logging
import re
import sqlite3
import os
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "anara_brain.db")


class EmotionEngine:
    """
    Zero-latency dynamic emotion & gesture classifier for 3D Avatar speech.
    Loads behavior profiles from SQLite database.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._behaviors: List[Dict[str, Any]] = []
        self.reload_behaviors()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def reload_behaviors(self):
        """Loads or refreshes all animation profiles from SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, category, emotion, gesture, intensity, duration_sec, keywords_json, description
                    FROM animations
                    ORDER BY 
                        CASE WHEN category = 'dance' THEN 1
                             WHEN category = 'emotion' THEN 2
                             WHEN category = 'gesture' THEN 3
                             ELSE 4 END
                """)
                rows = cursor.fetchall()
                loaded = []
                for r in rows:
                    try:
                        kws = json.loads(r["keywords_json"]) if r["keywords_json"] else []
                    except Exception:
                        kws = []
                    loaded.append({
                        "id": r["id"],
                        "name": r["name"],
                        "category": r["category"],
                        "emotion": r["emotion"],
                        "gesture": r["gesture"],
                        "intensity": float(r["intensity"]),
                        "duration_sec": float(r["duration_sec"]),
                        "keywords": [k.lower().strip() for k in kws if k.strip()],
                        "description": r["description"]
                    })
                self._behaviors = loaded
                logger.info(f"[EmotionEngine] Loaded {len(self._behaviors)} dynamic animation profiles from SQLite.")
        except Exception as e:
            logger.warning(f"[EmotionEngine] Could not load animations from database ({e}). Using empty pool.")
            self._behaviors = []

    def get_all_animations(self) -> List[Dict[str, Any]]:
        """Returns all animation records currently registered in database."""
        return list(self._behaviors)

    def add_or_update_animation(
        self,
        name: str,
        category: str,
        emotion: str,
        gesture: str,
        keywords: List[str],
        intensity: float = 0.8,
        duration_sec: float = 3.0,
        description: str = ""
    ) -> bool:
        """Adds or updates an animation profile in SQLite and reloads."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO animations (name, category, emotion, gesture, intensity, duration_sec, keywords_json, description, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(name) DO UPDATE SET
                        category = excluded.category,
                        emotion = excluded.emotion,
                        gesture = excluded.gesture,
                        intensity = excluded.intensity,
                        duration_sec = excluded.duration_sec,
                        keywords_json = excluded.keywords_json,
                        description = excluded.description,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    name.strip().lower(),
                    category.strip().lower(),
                    emotion.strip().lower(),
                    gesture.strip().lower(),
                    intensity,
                    duration_sec,
                    json.dumps(keywords),
                    description
                ))
                conn.commit()
                self.reload_behaviors()
                logger.info(f"[EmotionEngine] Added/Updated animation '{name}' in database.")
                return True
        except Exception as e:
            logger.error(f"[EmotionEngine] Error adding animation '{name}': {e}")
            return False

    def add_keyword_to_animation(self, animation_name: str, keyword: str) -> bool:
        """Appends a new trigger keyword to an existing animation profile in SQLite."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, keywords_json FROM animations WHERE name = ?", (animation_name.strip().lower(),))
                row = cursor.fetchone()
                if not row:
                    return False
                
                try:
                    kws = json.loads(row["keywords_json"]) if row["keywords_json"] else []
                except Exception:
                    kws = []
                
                clean_kw = keyword.strip().lower()
                if clean_kw not in kws:
                    kws.append(clean_kw)
                    cursor.execute("""
                        UPDATE animations 
                        SET keywords_json = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (json.dumps(kws), row["id"]))
                    conn.commit()
                    self.reload_behaviors()
                    logger.info(f"[EmotionEngine] Added keyword '{clean_kw}' to animation '{animation_name}'")
                    return True
                return True
        except Exception as e:
            logger.error(f"[EmotionEngine] Error adding keyword to '{animation_name}': {e}")
            return False

    def _matches_behavior(self, text_lower: str, behavior: Dict[str, Any]) -> bool:
        """
        Checks if text contains any of the behavior's trigger keywords.

        Uses WHOLE-WORD matching: a plain substring test made "musik" match inside
        "bermusik"/"musiknya", which caused false dance triggers.
        """
        for kw in behavior["keywords"]:
            kw = (kw or "").strip().lower()
            if not kw:
                continue
            try:
                if re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text_lower):
                    return True
            except re.error:
                if kw in text_lower:
                    return True
        return False

    def analyze(self, text: str, allow_dance: bool = True) -> Optional[Dict[str, Any]]:
        """
        Analyzes transcript text against database behavior profiles.
        Returns matching emotion, gesture, intensity, and duration.

        allow_dance=False downgrades a 'dance' verdict to a cheerful reaction.
        Use it whenever the analysed text is ANARA'S OWN speech — her mentioning
        the word "nari"/"musik" must never start the Rumba animation. Dancing is
        reserved for explicit user commands (and their confirmation).
        """
        if not text or not text.strip():
            return None

        t = text.lower().strip()

        # Check against dynamic database animation profiles
        for b in self._behaviors:
            if self._matches_behavior(t, b):
                is_dance = (b.get("emotion") == "dance") or (b.get("category") == "dance")
                if is_dance and not allow_dance:
                    logger.info(
                        f"[EmotionEngine] Dance keyword seen in AI speech — downgraded to happy "
                        f"(text: {t[:48]!r})"
                    )
                    return {
                        "animation_name": "happy",
                        "emotion": "happy",
                        "gesture": "joy",
                        "intensity": 0.75,
                        "duration_sec": 3.0,
                    }
                return {
                    "animation_name": b["name"],
                    "emotion": b["emotion"],
                    "gesture": b["gesture"],
                    "intensity": b["intensity"],
                    "duration_sec": b["duration_sec"],
                }

        # Question mark fallback
        if "?" in t:
            return {"animation_name": "question", "emotion": "curious", "gesture": "question", "intensity": 0.75}

        return {"animation_name": "talking", "emotion": "neutral", "gesture": "talking", "intensity": 0.60}

    def analyze_full_turn(self, full_turn_text: str, allow_dance: bool = True) -> Optional[Dict[str, Any]]:
        """
        Performs comprehensive emotion analysis over the entire AI response turn.
        """
        return self.analyze(full_turn_text, allow_dance=allow_dance)
