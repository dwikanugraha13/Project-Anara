"""
file_memory.py — 4-File Persistent Memory System & Privacy Filter for Project Anara.
Implements the 4-file memory standard from prd-general-agent.md & rancangan-general-agent.md:
1. SOUL.md: Agent core identity & philosophy (user-edited, global).
2. USER.md: User preferences, habits, speaking style (agent-written, global, cap ~1,500 chars).
3. MEMORY.md: Timestamped facts, decisions, learned technical patterns (agent-written, global, cap ~2,200 chars).
4. AGENTS.md: Project-specific instructions & repo rules (user-edited, active when project_root is set).
"""
import os
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Base directories
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
_COGNITION_DIR = os.path.join(_BASE_DIR, "cognition")
os.makedirs(_COGNITION_DIR, exist_ok=True)

USER_FILE_PATH = os.path.join(_COGNITION_DIR, "USER.md")
MEMORY_FILE_PATH = os.path.join(_COGNITION_DIR, "MEMORY.md")

USER_CHAR_CAP = 1500
MEMORY_CHAR_CAP = 2200

# ─────────────────────────────────────────────────────────────────────────────
# Privacy Filter: Sanitizes sensitive credentials before writing to disk
# ─────────────────────────────────────────────────────────────────────────────

SENSITIVE_PATTERNS = [
    # OpenAI, Anthropic, Google, Groq, HuggingFace API Keys
    (r"\bsk-[a-zA-Z0-9_-]{20,}\b", "[REDACTED_API_KEY]"),
    (r"\bAIza[0-9A-Za-z-_]{35}\b", "[REDACTED_API_KEY]"),
    (r"\bgsk_[a-zA-Z0-9]{20,}\b", "[REDACTED_API_KEY]"),
    (r"\bhf_[a-zA-Z0-9]{20,}\b", "[REDACTED_API_KEY]"),
    # Generic Key/Secret assignments (key=xyz, secret=xyz, token=xyz, password=xyz)
    (r"(?i)(api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|password|passwd)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.\$\!\@\#\%\^\&\*]{6,})['\"]?", r"\1: [REDACTED_SECRET]"),
    # Bearer tokens
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer [REDACTED_TOKEN]"),
    # Private keys
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
    # JWT Tokens
    (r"\beyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b", "[REDACTED_JWT_TOKEN]"),
]


def filter_sensitive_data(text: str) -> str:
    """Scans and masks any API keys, passwords, or tokens in text."""
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


# ─────────────────────────────────────────────────────────────────────────────
# 4-File Memory Manager
# ─────────────────────────────────────────────────────────────────────────────

class FileMemoryManager:
    """Manages the 4-file markdown persistent memory system with strict caps and sanitization."""

    @staticmethod
    def _read_file_safe(path: str, default: str = "") -> str:
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception as e:
                logger.warning(f"[FileMemory] Could not read {path}: {e}")
        return default

    @staticmethod
    def _write_file_safe(path: str, content: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content.strip() + "\n")
            return True
        except Exception as e:
            logger.error(f"[FileMemory] Error writing to {path}: {e}")
            return False

    @classmethod
    def get_soul_content(cls) -> str:
        """Returns SOUL.md content (Identity & Core Persona)."""
        from cognition.soul import get_soul_prompt
        return get_soul_prompt().strip()

    @classmethod
    def get_user_profile(cls) -> str:
        """Returns USER.md content (User Preferences & Profile)."""
        default = "# Profil Pengguna (USER.md)\n- Nama Panggilan: Agnan\n- Bahasa Utama: Bahasa Indonesia & English\n- Preferensi: Solutif, efisien, kode rapi & modular."
        return cls._read_file_safe(USER_FILE_PATH, default=default)

    @classmethod
    def get_memory_facts(cls) -> str:
        """Returns MEMORY.md content (Persistent Facts & Learned Knowledge)."""
        default = "# Memori Jangka Panjang (MEMORY.md)\n- [2026-09-15] Anara General Agent diinisialisasi dengan arsitektur memori 4-file & Anara skill library."
        return cls._read_file_safe(MEMORY_FILE_PATH, default=default)

    @classmethod
    def get_project_agents_rules(cls, project_root: Optional[str] = None) -> Optional[str]:
        """Returns AGENTS.md content from the active project workspace root, if present."""
        if not project_root or not os.path.isdir(project_root):
            return None
        candidates = ["AGENTS.md", "CLAUDE.md", ".anararules", "RULES.md"]
        for c in candidates:
            p = os.path.join(project_root, c)
            if os.path.isfile(p):
                content = cls._read_file_safe(p)
                if content:
                    return f"# Aturan Proyek ({c})\n{content}"
        return None

    @classmethod
    def update_user_profile(cls, new_entry: str, speaker_name: Optional[str] = None) -> bool:
        """
        Updates USER.md with a new user preference/profile fact.
        Enforces privacy filter and ~1,500 characters cap.
        """
        clean_entry = filter_sensitive_data(new_entry.strip())
        if not clean_entry:
            return False

        current = cls.get_user_profile()
        line = f"- {clean_entry}"
        if line.lower() in current.lower():
            return True  # already recorded

        combined = current + "\n" + line

        # If exceeds cap, trim oldest non-header bullets
        if len(combined) > USER_CHAR_CAP:
            lines = combined.split("\n")
            header_lines = [l for l in lines if l.startswith("#")]
            bullet_lines = [l for l in lines if l.startswith("-")]
            while len("\n".join(header_lines + bullet_lines)) > USER_CHAR_CAP and len(bullet_lines) > 2:
                bullet_lines.pop(0)  # remove oldest bullet
            combined = "\n".join(header_lines + bullet_lines)

        ok = cls._write_file_safe(USER_FILE_PATH, combined)
        if ok:
            logger.info(f"[FileMemory] Updated USER.md: {clean_entry[:60]}")
        return ok

    @classmethod
    def append_memory_fact(cls, fact: str) -> bool:
        """
        Appends a timestamped fact or learned decision to MEMORY.md.
        Enforces privacy filter and ~2,200 characters cap.
        """
        clean_fact = filter_sensitive_data(fact.strip())
        if not clean_fact:
            return False

        today_str = datetime.now().strftime("%Y-%m-%d")
        timestamped_line = f"- [{today_str}] {clean_fact}"

        current = cls.get_memory_facts()
        if clean_fact.lower() in current.lower():
            return True

        combined = current + "\n" + timestamped_line

        # If exceeds cap, trim oldest entries
        if len(combined) > MEMORY_CHAR_CAP:
            lines = combined.split("\n")
            header_lines = [l for l in lines if l.startswith("#")]
            bullet_lines = [l for l in lines if l.startswith("-")]
            while len("\n".join(header_lines + bullet_lines)) > MEMORY_CHAR_CAP and len(bullet_lines) > 2:
                bullet_lines.pop(0)
            combined = "\n".join(header_lines + bullet_lines)

        ok = cls._write_file_safe(MEMORY_FILE_PATH, combined)
        if ok:
            logger.info(f"[FileMemory] Appended to MEMORY.md: {clean_fact[:60]}")
        return ok

    @classmethod
    def detect_and_record_memory(cls, user_text: str, speaker_name: Optional[str] = None) -> Optional[str]:
        """
        Detects explicit memory triggers in user speech/text (FR-11):
        'ingat bahwa...', 'catat bahwa...', 'preferensi saya...', 'nama saya...'
        and persists them into USER.md or MEMORY.md.
        """
        text = (user_text or "").strip()
        if not text:
            return None

        # 1. User Profile Triggers -> USER.md
        user_patterns = [
            r"(?i)\b(?:ingat|catat)?\s*(?:bahwa\s+)?nama(?:ku| saya)\s*(?:adalah|:|=)?\s*([a-zA-Z\s]{2,30})",
            r"(?i)\b(?:saya|aku)\s+(?:lebih\s+suka|preferensi\s+saya|biasanya\s+pakai)\s+([^\.\n]+)",
            r"(?i)\b(?:gaya\s+bicara|bicara\s+dengan)\s+([^\.\n]+)",
        ]
        for pat in user_patterns:
            m = re.search(pat, text)
            if m:
                extracted = m.group(0).strip()
                cls.update_user_profile(extracted, speaker_name=speaker_name)
                return f"Tercatat di profil: {extracted}"

        # 2. General Fact / Knowledge Triggers -> MEMORY.md
        fact_patterns = [
            r"(?i)\b(?:ingat|catat|simpan\s+ke\s+memori)\s*(?:bahwa)?\s*:\s*([^\n]+)",
            r"(?i)\b(?:ingat|catat)\s+bahwa\s+([^\n\.]+)",
            r"(?i)\b(?:jangan\s+lupa|pastikan\s+ingat)\s+bahwa\s+([^\n\.]+)",
        ]
        for pat in fact_patterns:
            m = re.search(pat, text)
            if m:
                fact = m.group(1).strip()
                cls.append_memory_fact(fact)
                return f"Tercatat di memori: {fact}"

        return None

    @classmethod
    def get_prompt_context(cls, speaker_name: Optional[str] = None, project_root: Optional[str] = None) -> str:
        """
        Assembles Slot 4 (Memory Snapshot) and Slot 6 (AGENTS.md) cleanly.
        """
        user_md = cls.get_user_profile()
        memory_md = cls.get_memory_facts()
        return f"{user_md}\n\n{memory_md}"


file_memory = FileMemoryManager()
