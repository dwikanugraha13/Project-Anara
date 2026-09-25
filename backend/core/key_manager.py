"""
API Key Pool & Auto-Rotation Manager for Google Gemini API.
Allows inserting multiple API keys from different Google accounts into .env
so Anara automatically rotates keys when quota/rate limit (429) is encountered,
ensuring uninterrupted 24/7 operation with unlimited free-tier pool.
"""

import asyncio
import os
import time
import logging
from typing import List, Dict, Optional, Callable, Any, Awaitable
from dotenv import load_dotenv
from google import genai

logger = logging.getLogger(__name__)


class GeminiKeyManager:
    """
    Manages a pool of Gemini API keys with automatic failover,
    cooldown management, and round-robin load balancing.
    """

    def __init__(self):
        self._keys: List[str] = []
        self._cooldowns: Dict[str, float] = {}  # key -> timestamp when cooldown expires
        self._current_index: int = 0
        self.reload_keys()

    def reload_keys(self):
        """
        Loads API keys primarily from SQLite table 'ai_accounts' (Google AI Studio / Gemini pool).
        Falls back to environment variables (if provided) for backward compatibility.
        """
        parsed = []

        # 1. Primary Source: Read dynamically stored keys from SQLite ai_accounts (enabled only)
        try:
            from memory import memory_engine
            accs = memory_engine.get_ai_accounts("gemini")
            for a in accs:
                if a.get("is_enabled", 1) == 1:
                    k = a.get("api_key", "").strip()
                    if k and k not in parsed:
                        parsed.append(k)

            # Legacy app_settings fallback
            db_gemini_val = memory_engine.get_app_setting("gemini_api_key")
            if db_gemini_val:
                for line in db_gemini_val.replace("\r", "").split("\n"):
                    for part in line.split(","):
                        k = part.strip().strip("'\"")
                        if (k.startswith("AIzaSy") or k.startswith("AQ.")) and k not in parsed:
                            parsed.append(k)
                        elif len(k) > 20 and k not in parsed and not k.startswith("http"):
                            parsed.append(k)
        except Exception as e_db:
            logger.debug(f"[KeyManager] Error reading ai_accounts from DB: {e_db}")

        # 2. Secondary Source: Environment variables (optional backward compatibility)
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_file):
            load_dotenv(env_file, override=False)

        for env_k, env_v in os.environ.items():
            if "GEMINI" in env_k.upper() and ("KEY" in env_k.upper() or "TOKEN" in env_k.upper()):
                for line in env_v.replace("\r", "").split("\n"):
                    for part in line.split(","):
                        k = part.strip().strip("'\"")
                        if (k.startswith("AIzaSy") or k.startswith("AQ.") or len(k) > 20) and k not in parsed and not k.startswith("http"):
                            parsed.append(k)

        # 3. Check if Gemini provider was explicitly disconnected
        try:
            from memory import memory_engine
            if memory_engine.get_app_setting("provider_disconnected_gemini") == "true":
                parsed = []
        except Exception:
            pass

        self._keys = parsed
        if not self._keys:
            logger.info("[KeyManager] Google AI Studio has no active account. Add an account via Anara Brain Console (Providers tab).")
        else:
            n_legacy = sum(1 for k in self._keys if k.startswith("AIzaSy"))
            n_new = sum(1 for k in self._keys if k.startswith("AQ."))
            n_other = len(self._keys) - n_legacy - n_new
            fmt_info = f"(AIzaSy: {n_legacy}, AQ.: {n_new}" + (f", others: {n_other})" if n_other else ")")
            logger.info(f"[KeyManager] Loaded {len(self._keys)} Google AI Studio API key(s) into active pool {fmt_info}.")

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    def get_active_key(self) -> str:
        """
        Returns the currently active healthy API key.
        If all keys are in cooldown, picks the one whose cooldown expires soonest.
        """
        if not self._keys:
            return ""

        now = time.time()
        # Find first healthy key starting from current_index
        for offset in range(len(self._keys)):
            idx = (self._current_index + offset) % len(self._keys)
            key = self._keys[idx]
            cooldown_until = self._cooldowns.get(key, 0.0)
            if now >= cooldown_until:
                self._current_index = idx
                return key

        # If all in cooldown, fallback to the one expiring soonest
        soonest_key = min(self._keys, key=lambda k: self._cooldowns.get(k, 0.0))
        self._current_index = self._keys.index(soonest_key)
        logger.warning(f"[KeyManager] All keys in cooldown, falling back to earliest available key ({self._current_index + 1}/{len(self._keys)})")
        return soonest_key

    def mark_key_dead(self, key: str, reason: str = "permission_denied"):
        """Permanently blacklists an invalid/revoked key (24h cooldown)."""
        if key in self._keys:
            self._cooldowns[key] = time.time() + 86400.0
            k_preview = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else key
            logger.error(f"[KeyManager] API Key [{k_preview}] marked DEAD & banned ({reason}).")

    def rotate_key(self, failed_key: Optional[str] = None, reason: str = "quota_exhausted", cooldown_seconds: float = 120.0) -> str:
        """
        Marks the failed key as in cooldown and switches to the next available healthy key.
        """
        if not self._keys:
            return ""

        now = time.time()
        if failed_key and failed_key in self._keys:
            # If permission denied, ban for 24 hours
            if any(w in reason.lower() for w in ["permission_denied", "403", "unauthenticated", "401"]):
                cooldown_seconds = 86400.0
            self._cooldowns[failed_key] = now + cooldown_seconds
            k_preview = f"{failed_key[:8]}...{failed_key[-4:]}" if len(failed_key) > 12 else failed_key
            logger.warning(f"[KeyManager] API Key [{k_preview}] put in {cooldown_seconds:.0f}s cooldown ({reason}).")

        # Advance to next key
        self._current_index = (self._current_index + 1) % len(self._keys)
        new_key = self.get_active_key()
        k_new_prev = f"{new_key[:8]}...{new_key[-4:]}" if len(new_key) > 12 else new_key
        logger.info(f"[KeyManager] Switched active key to: [{k_new_prev}] (Key #{self._current_index + 1}/{len(self._keys)})")
        return new_key

    def get_client(self) -> genai.Client:
        """Creates a genai.Client using the currently active healthy API key."""
        active_key = self.get_active_key()
        return genai.Client(api_key=active_key or "UNCONFIGURED_KEY")

    async def execute_with_failover(
        self,
        coro_func: Callable[[genai.Client], Awaitable[Any]],
        max_attempts: Optional[int] = None
    ) -> Any:
        """
        Executes an async Gemini SDK function across all configured API keys with
        a strict per-key timeout (15s) to ensure fast failover and never hang.
        """
        if not self._keys:
            raise ValueError("Google AI Studio API Key not configured. Add an account in the Providers tab of Anara Brain Console.")

        # Try up to ALL keys in pool so no key is left unattempted
        attempts = max_attempts or len(self._keys)
        last_exception = None

        for attempt in range(attempts):
            active_key = self.get_active_key()
            client = genai.Client(api_key=active_key)
            try:
                # Per-attempt timeout: if Google hangs or queues for >15s, advance key immediately!
                return await asyncio.wait_for(coro_func(client), timeout=45.0)
            except (asyncio.TimeoutError, Exception) as e:
                err_msg = str(e).lower()
                is_timeout = isinstance(e, asyncio.TimeoutError) or "timeout" in err_msg
                is_quota_error = any(q in err_msg for q in [
                    "429", "resource_exhausted", "quota", "rate limit", "too many requests", "limit exceeded"
                ])
                is_permission_error = any(p in err_msg for p in [
                    "permission_denied", "403", "unauthenticated", "401", "api_key_invalid", "denied access"
                ])
                is_unavailable_error = is_timeout or any(u in err_msg for u in [
                    "503", "unavailable", "high demand", "overloaded", "temporarily unavailable"
                ])

                if (is_quota_error or is_permission_error or is_unavailable_error) and len(self._keys) > 1:
                    reason = "403_permission_denied" if is_permission_error else ("503_unavailable" if is_unavailable_error else "429_quota_limit")
                    cooldown = 86400.0 if is_permission_error else (60.0 if is_unavailable_error else 120.0)
                    k_preview = f"{active_key[:8]}...{active_key[-4:]}" if len(active_key) > 12 else active_key
                    logger.warning(f"[KeyManager] Failover on key [{k_preview}] attempt {attempt + 1}/{attempts}: {e}. Rotating to next key...")
                    self.rotate_key(active_key, reason=reason, cooldown_seconds=cooldown)
                    last_exception = e
                    continue
                else:
                    raise e

        if last_exception:
            raise last_exception


# Global singleton instance
key_manager = GeminiKeyManager()
