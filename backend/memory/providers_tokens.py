import json
import logging
import re
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


def _mask_secret_key(k: Optional[str]) -> str:
    """Anara Enterprise Architecture: Standardized secret masking."""
    if not k:
        return "(none)"
    k = k.strip()
    if len(k) <= 8:
        return "••••••••"
    return f"{k[:4]}...{k[-4:]}"


# ── Token Cost Accounting & Prompt Caching Discount Rates (Per 1M Tokens in USD) ──
# Structure: (uncached_prompt_rate, cached_prompt_rate, completion_rate)
MODEL_PRICE_PER_M: Dict[str, Tuple[float, float, float]] = {
    # Claude models (Anthropic: 90% discount on cache read)
    "claude-3-7-sonnet": (3.0, 0.30, 15.0),
    "claude-3-5-sonnet": (3.0, 0.30, 15.0),
    "claude-3-5-haiku": (0.80, 0.08, 4.0),
    "claude-3-opus": (15.0, 1.50, 75.0),
    # OpenAI models (50% discount on cached tokens)
    "gpt-4o": (2.50, 1.25, 10.0),
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "o1": (15.0, 7.50, 60.0),
    "o3-mini": (1.10, 0.55, 4.40),
    # Gemini models (75% discount on cached tokens)
    "gemini-2.5-pro": (1.25, 0.3125, 5.0),
    "gemini-2.0-pro": (1.25, 0.3125, 5.0),
    "gemini-2.5-flash": (0.075, 0.01875, 0.30),
    "gemini-2.0-flash": (0.075, 0.01875, 0.30),
    "gemini-1.5-pro": (1.25, 0.3125, 5.0),
    "gemini-1.5-flash": (0.075, 0.01875, 0.30),
    # DeepSeek models (90% discount on cache hit)
    "deepseek-chat": (0.14, 0.014, 0.28),
    "deepseek-reasoner": (0.55, 0.14, 2.19),
    # Default fallback
    "default": (1.0, 0.25, 3.0),
}


def calculate_token_cost(
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0
) -> float:
    """
    Computes precise estimated cost in USD based on model pricing and prompt caching discounts.
    Anara Enterprise Architecture.
    """
    m_clean = (model_id or "").strip().lower()
    rates = None
    for pattern, price_tuple in MODEL_PRICE_PER_M.items():
        if pattern in m_clean:
            rates = price_tuple
            break
    if not rates:
        rates = MODEL_PRICE_PER_M["default"]

    in_rate, cache_rate, out_rate = rates
    p_tok = max(0, int(prompt_tokens or 0))
    c_tok = max(0, int(completion_tokens or 0))
    ca_tok = min(max(0, int(cached_tokens or 0)), p_tok)
    uncached_tok = max(0, p_tok - ca_tok)

    cost = ((uncached_tok * in_rate) + (ca_tok * cache_rate) + (c_tok * out_rate)) / 1_000_000.0
    return round(cost, 6)


class ProvidersTokensMixin:
    """Agent skills, AI accounts pool, custom model providers, model visibility, and token usage accounting."""

    # ── Multi-Account AI Model Pool Methods ──

    def get_ai_accounts(self, provider: Optional[str] = None, include_secrets: bool = True) -> List[Dict[str, Any]]:
        """Retrieves stored AI provider API accounts from SQLite with masked_key metadata."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if provider:
                cursor.execute("""
                    SELECT id, provider, account_label, api_key, status, requests_count, cooldown_until, is_enabled, created_at
                    FROM ai_accounts
                    WHERE LOWER(provider) = LOWER(?)
                    ORDER BY id ASC
                """, (provider.strip(),))
            else:
                cursor.execute("""
                    SELECT id, provider, account_label, api_key, status, requests_count, cooldown_until, is_enabled, created_at
                    FROM ai_accounts
                    ORDER BY id ASC
                """)
            rows = [dict(r) for r in cursor.fetchall()]
            for r in rows:
                raw_k = r.get("api_key") or ""
                r["masked_key"] = _mask_secret_key(raw_k)
                if not include_secrets:
                    r["api_key"] = r["masked_key"]
            return rows

    def add_ai_account(self, provider: str, account_label: str, api_key: str) -> Optional[Dict[str, Any]]:
        """Adds a new labeled account to the provider pool."""
        clean_prov = provider.strip().lower()
        clean_label = (account_label or f"{clean_prov.capitalize()} Account").strip()
        clean_key = api_key.strip()
        if not clean_key:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_accounts (provider, account_label, api_key, status, is_enabled)
                VALUES (?, ?, ?, 'active', 1)
            """, (clean_prov, clean_label, clean_key))
            conn.commit()
            new_id = cursor.lastrowid
            return {
                "id": new_id,
                "provider": clean_prov,
                "account_label": clean_label,
                "api_key": _mask_secret_key(clean_key),
                "status": "active",
                "is_enabled": 1,
            }

    def toggle_ai_account(self, account_id: int) -> Optional[int]:
        """Toggles an account's enabled state in the pool atomically."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ai_accounts
                SET is_enabled = CASE WHEN is_enabled = 1 THEN 0 ELSE 1 END
                WHERE id = ?
            """, (account_id,))
            conn.commit()
            if cursor.rowcount > 0:
                cursor.execute("SELECT is_enabled FROM ai_accounts WHERE id = ?", (account_id,))
                row = cursor.fetchone()
                return row["is_enabled"] if row else None
            return None

    def delete_ai_account(self, account_id: int) -> bool:
        """Deletes an account from the pool by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_accounts WHERE id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_ai_accounts_by_provider(self, provider: str) -> int:
        """Deletes all accounts belonging to a provider."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_accounts WHERE LOWER(provider) = LOWER(?)", (provider.strip(),))
            conn.commit()
            return cursor.rowcount

    def increment_ai_account_usage(self, account_id: int):
        """Increments requests_count for an account."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE ai_accounts SET requests_count = requests_count + 1 WHERE id = ?", (account_id,))
                conn.commit()
        except Exception:
            pass

    def set_ai_account_cooldown(self, account_id: int, cooldown_seconds: float = 120.0):
        """Puts an account in cooldown (e.g. on 429 quota exhaustion)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE ai_accounts
                    SET status = 'cooldown', cooldown_until = ?
                    WHERE id = ?
                """, (time.time() + cooldown_seconds, account_id))
                conn.commit()
        except Exception:
            pass

    def add_agent_skill(
        self,
        name: str,
        category: str,
        description: str,
        trigger_keywords: List[str],
        procedure_steps: List[str],
        learned_from_experience: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Registers a new skill into the agent_skills database (manual or learned)."""
        clean_name = name.strip()
        if not clean_name:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_skills (name, category, description, trigger_keywords_json, procedure_steps_json, usage_count, is_active, learned_from_experience, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    category = excluded.category,
                    description = excluded.description,
                    trigger_keywords_json = excluded.trigger_keywords_json,
                    procedure_steps_json = excluded.procedure_steps_json,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                clean_name,
                category.strip().lower() or "general",
                description.strip(),
                json.dumps([k.strip().lower() for k in trigger_keywords if str(k).strip()]),
                json.dumps([s.strip() for s in procedure_steps if str(s).strip()]),
                1 if learned_from_experience else 0
            ))
            conn.commit()
            new_id = cursor.lastrowid
            logger.info(f"[AnaraAgent] Registered skill: '{clean_name}' (learned={learned_from_experience})")
            return {
                "id": new_id,
                "name": clean_name,
                "category": category,
                "description": description,
                "learned_from_experience": learned_from_experience
            }

    def get_all_agent_skills(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Returns all registered agent skills."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute("""
                    SELECT id, name, category, description, trigger_keywords_json, procedure_steps_json, usage_count, is_active, learned_from_experience, created_at, updated_at
                    FROM agent_skills
                    WHERE is_active = 1
                    ORDER BY usage_count DESC, id ASC
                """)
            else:
                cursor.execute("""
                    SELECT id, name, category, description, trigger_keywords_json, procedure_steps_json, usage_count, is_active, learned_from_experience, created_at, updated_at
                    FROM agent_skills
                    ORDER BY learned_from_experience DESC, usage_count DESC, id ASC
                """)
            
            rows = cursor.fetchall()
            result = []
            for r in rows:
                try:
                    triggers = json.loads(r["trigger_keywords_json"] or "[]")
                except Exception:
                    triggers = []
                try:
                    steps = json.loads(r["procedure_steps_json"] or "[]")
                except Exception:
                    steps = []
                
                result.append({
                    "id": r["id"],
                    "name": r["name"],
                    "category": r["category"],
                    "description": r["description"],
                    "trigger_keywords": triggers,
                    "procedure_steps": steps,
                    "usage_count": r["usage_count"] or 0,
                    "is_active": bool(r["is_active"]),
                    "learned_from_experience": bool(r["learned_from_experience"]),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                })
            return result

    def toggle_agent_skill(self, skill_id: int) -> bool:
        """Toggles active/inactive status of a skill."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE agent_skills SET is_active = 1 - is_active WHERE id = ?", (skill_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_agent_skill(self, skill_id: int) -> bool:
        """Deletes a skill from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM agent_skills WHERE id = ?", (skill_id,))
            conn.commit()
            return cursor.rowcount > 0

    def increment_agent_skill_usage(self, skill_name: str):
        """Increments usage counter when a skill is utilized during a mission."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE agent_skills SET usage_count = usage_count + 1 WHERE LOWER(name) = LOWER(?)", (skill_name.strip(),))
                conn.commit()
        except Exception:
            pass

    def get_custom_providers(self, include_secrets: bool = True) -> List[Dict[str, Any]]:
        """
        Returns registered OpenAI/Anthropic-compatible custom providers.
        Anara Standard: Merges persistent SQLite custom_providers with declarative
        YAML configuration from config.yaml (model.custom_providers or custom_providers).
        """
        sqlite_providers: List[Dict[str, Any]] = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, prefix, api_type, base_url, api_key, default_model, is_active, created_at, updated_at
                FROM custom_providers
                ORDER BY id ASC
            """)
            for r in cursor.fetchall():
                d = dict(r)
                k = d.get("api_key") or ""
                d["masked_key"] = _mask_secret_key(k)
                if not include_secrets:
                    d["api_key"] = d["masked_key"]
                sqlite_providers.append(d)

        # Merge declarative providers from config.yaml (Anara Standard)
        yaml_providers: List[Dict[str, Any]] = []
        try:
            from config import cfg_get
            raw_list = cfg_get("model.custom_providers") or cfg_get("custom_providers") or []
            if isinstance(raw_list, list):
                for idx, item in enumerate(raw_list):
                    if isinstance(item, dict) and item.get("base_url"):
                        name = item.get("name") or f"Custom Provider {idx+1}"
                        prefix = re.sub(r"[^a-zA-Z0-9_-]", "-", str(item.get("prefix") or name).strip().lower()).strip("-")
                        key_env = str(item.get("key_env") or "").strip()
                        raw_key = str(item.get("api_key") or (os.getenv(key_env, "") if key_env else "")).strip()
                        default_model = str(item.get("default_model") or item.get("model") or "").strip()
                        base_url = str(item.get("base_url")).strip().rstrip("/")
                        is_active = bool(item.get("is_active", True))
                        yaml_providers.append({
                            "id": -(idx + 1),  # Non-positive ID designates declarative YAML config
                            "name": name,
                            "prefix": prefix,
                            "api_type": str(item.get("api_type") or "chat_completions"),
                            "base_url": base_url,
                            "api_key": _mask_secret_key(raw_key) if not include_secrets else raw_key,
                            "masked_key": _mask_secret_key(raw_key),
                            "default_model": default_model,
                            "is_active": 1 if is_active else 0,
                            "source": "config.yaml",
                        })
        except Exception:
            pass

        # Deduplicate by prefix (SQLite-stored overrides take precedence over YAML defaults)
        existing_prefixes = {p["prefix"].lower() for p in sqlite_providers}
        for yp in yaml_providers:
            if yp["prefix"].lower() not in existing_prefixes:
                sqlite_providers.append(yp)
                existing_prefixes.add(yp["prefix"].lower())

        return sqlite_providers

    def add_custom_provider(
        self,
        name: str,
        prefix: str,
        base_url: str,
        api_type: str = "chat_completions",
        api_key: Optional[str] = None,
        default_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates or updates a custom provider node safely preserving existing key on empty input."""
        clean_name = name.strip()
        clean_prefix = re.sub(r"[^a-zA-Z0-9_-]", "-", prefix.strip().lower()).strip("-")
        clean_url = base_url.strip().rstrip("/")
        clean_key = (api_key or "").strip()
        clean_model = (default_model or "").strip()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO custom_providers (name, prefix, api_type, base_url, api_key, default_model, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(prefix) DO UPDATE SET
                    name = excluded.name,
                    api_type = excluded.api_type,
                    base_url = excluded.base_url,
                    api_key = CASE WHEN excluded.api_key != '' THEN excluded.api_key ELSE custom_providers.api_key END,
                    default_model = excluded.default_model,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (clean_name, clean_prefix, api_type, clean_url, clean_key, clean_model))
            conn.commit()
            new_id = cursor.lastrowid
            return {
                "id": new_id,
                "name": clean_name,
                "prefix": clean_prefix,
                "api_type": api_type,
                "base_url": clean_url,
                "masked_key": _mask_secret_key(clean_key),
                "default_model": clean_model,
                "is_active": 1,
            }

    save_custom_provider = add_custom_provider

    def delete_custom_provider(self, provider_id: int) -> bool:
        """Deletes a custom provider by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM custom_providers WHERE id = ?", (provider_id,))
            conn.commit()
            return cursor.rowcount > 0

    def toggle_custom_provider(self, provider_id: int) -> Optional[int]:
        """Toggles active/disabled state atomically (Anara Standard)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE custom_providers
                SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (provider_id,))
            conn.commit()
            if cursor.rowcount > 0:
                cursor.execute("SELECT is_active FROM custom_providers WHERE id = ?", (provider_id,))
                row = cursor.fetchone()
                return row["is_active"] if row else None
            return None

    def get_hidden_models(self) -> List[Dict[str, str]]:
        """Returns list of hidden models with model_id and provider."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT model_id, provider FROM hidden_models")
            return [{"model_id": r[0], "provider": r[1] or "unknown"} for r in cursor.fetchall()]

    def hide_model(self, model_id: str, provider: Optional[str] = None) -> bool:
        """Prunes a model from view by adding it to hidden_models."""
        clean_id = model_id.strip()
        if not clean_id:
            return False
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO hidden_models (model_id, provider)
                VALUES (?, ?)
            """, (clean_id, provider or ""))
            conn.commit()
            return True

    def unhide_model(self, model_id: str) -> bool:
        """Restores a previously hidden model."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hidden_models WHERE model_id = ?", (model_id.strip(),))
            conn.commit()
            return cursor.rowcount > 0

    def restore_all_hidden_models(self, provider: Optional[str] = None) -> int:
        """Restores all hidden models, optionally for a specific provider."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if provider:
                cursor.execute("DELETE FROM hidden_models WHERE provider = ?", (provider.strip(),))
            else:
                cursor.execute("DELETE FROM hidden_models")
            conn.commit()
            return cursor.rowcount

    def record_token_usage(
        self,
        model_id: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        session_id: Optional[int] = None,
        estimated_cost: float = 0.0,
        cached_tokens: int = 0
    ) -> int:
        """Records token metrics from a single model generation turn into SQLite."""
        p_tok = max(0, int(prompt_tokens or 0))
        c_tok = max(0, int(completion_tokens or 0))
        ca_tok = max(0, int(cached_tokens or 0))
        t_tok = p_tok + c_tok

        eff_cost = float(estimated_cost or 0.0)
        if eff_cost <= 0.0 and (p_tok > 0 or c_tok > 0):
            eff_cost = calculate_token_cost(model_id, p_tok, c_tok, ca_tok)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO token_usage_logs (session_id, model_id, provider, prompt_tokens, completion_tokens, total_tokens, cached_tokens, estimated_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, model_id.strip(), provider.strip().lower(), p_tok, c_tok, t_tok, ca_tok, eff_cost))
            except Exception:
                cursor.execute("""
                    INSERT INTO token_usage_logs (session_id, model_id, provider, prompt_tokens, completion_tokens, total_tokens, estimated_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, model_id.strip(), provider.strip().lower(), p_tok, c_tok, t_tok, eff_cost))
            conn.commit()
            return cursor.lastrowid or 0

    def get_token_usage_summary(self) -> Dict[str, Any]:
        """Returns aggregate token usage stats (all-time, today, and by provider)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(total_tokens), 0) as total_tokens,
                        COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                        COALESCE(SUM(completion_tokens), 0) as total_completion,
                        COALESCE(SUM(cached_tokens), 0) as total_cached_tokens,
                        COALESCE(SUM(estimated_cost), 0.0) as total_cost,
                        COUNT(*) as total_requests
                    FROM token_usage_logs
                """)
            except Exception:
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(total_tokens), 0) as total_tokens,
                        COALESCE(SUM(prompt_tokens), 0) as total_prompt,
                        COALESCE(SUM(completion_tokens), 0) as total_completion,
                        0 as total_cached_tokens,
                        COALESCE(SUM(estimated_cost), 0.0) as total_cost,
                        COUNT(*) as total_requests
                    FROM token_usage_logs
                """)
            overall = dict(cursor.fetchone() or {})

            cursor.execute("""
                SELECT 
                    COALESCE(SUM(total_tokens), 0) as today_tokens,
                    COUNT(*) as today_requests
                FROM token_usage_logs
                WHERE DATE(created_at) = DATE('now', 'localtime')
            """)
            today = dict(cursor.fetchone() or {})

            cursor.execute("""
                SELECT provider, 
                       COUNT(*) as requests, 
                       COALESCE(SUM(total_tokens), 0) as total_tokens
                FROM token_usage_logs
                GROUP BY provider
                ORDER BY total_tokens DESC
            """)
            by_provider = [dict(r) for r in cursor.fetchall()]

            cursor.execute("""
                SELECT model_id, 
                       COUNT(*) as requests, 
                       COALESCE(SUM(total_tokens), 0) as total_tokens
                FROM token_usage_logs
                GROUP BY model_id
                ORDER BY total_tokens DESC
                LIMIT 6
            """)
            top_models = [dict(r) for r in cursor.fetchall()]

            return {
                "overall": overall,
                "today": today,
                "by_provider": by_provider,
                "top_models": top_models
            }

    def get_recent_token_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent individual token usage transaction records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT id, session_id, model_id, provider, prompt_tokens, completion_tokens, total_tokens, cached_tokens, estimated_cost, created_at
                    FROM token_usage_logs
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
            except Exception:
                cursor.execute("""
                    SELECT id, session_id, model_id, provider, prompt_tokens, completion_tokens, total_tokens, 0 as cached_tokens, estimated_cost, created_at
                    FROM token_usage_logs
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
            return [dict(r) for r in cursor.fetchall()]
