"""
token_budget.py — Token Budget Tracker for Project Anara (Hermes/Claude Code Parity).

Provides model-aware token counting and budget enforcement for:
1. ReAct loop iteration budget (caller.py) — stops before context overflow
2. Prompt assembler slot pruning (prompt_assembler.py) — dynamic context filling
3. Context compactor (context_compactor.py) — token-aware compaction thresholds
4. In-loop message truncation (caller.py) — replaces the 24-msg char heuristic

Uses tiktoken for OpenAI/Anthropic models and a calibrated heuristic (1 token ≈ 3.4 chars)
for Gemini and unknown models.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Model Context Window Registry ──────────────────────────────────────────────
# Maps model ID patterns to (context_window_tokens, max_output_tokens).
# Patterns are matched in order; first match wins.
# Sources: official docs for Gemini, OpenAI, Anthropic as of 2026-09.

_MODEL_CONTEXT_WINDOWS: List[Tuple[str, int, int]] = [
    # ── Gemini ──
    ("gemini-2.5-pro",       1_048_576, 65_536),
    ("gemini-2.5-flash",     1_048_576, 65_536),
    ("gemini-3",             1_048_576, 65_536),   # catch-all for gemini-3.x family
    ("gemini-2.0",             1_048_576, 8_192),
    ("gemini-1.5-pro",       2_097_152, 8_192),
    ("gemini-1.5-flash",     1_048_576, 8_192),
    ("gemini",                 128_000, 8_192),     # generic gemini fallback
    ("gemma",                    8_192, 4_096),

    # ── OpenAI ──
    ("o3",                     200_000, 100_000),
    ("o4-mini",                200_000, 100_000),
    ("o1",                     200_000, 100_000),
    ("gpt-4.1",               1_047_576, 32_768),
    ("gpt-4o",                 128_000, 16_384),
    ("gpt-4-turbo",            128_000, 4_096),
    ("gpt-4",                    8_192, 4_096),
    ("gpt-3.5",                 16_385, 4_096),

    # ── Anthropic ──
    ("claude-sonnet-4",        200_000, 64_000),
    ("claude-opus-4",          200_000, 64_000),
    ("claude-3-7",             200_000, 64_000),
    ("claude-3.7",             200_000, 64_000),
    ("claude-3-5",             200_000, 8_192),
    ("claude-3-opus",          200_000, 4_096),
    ("claude-3-haiku",         200_000, 4_096),
    ("claude",                 200_000, 8_192),     # generic claude fallback

    # ── Open / Custom ──
    ("deepseek",               128_000, 8_192),
    ("qwen",                   128_000, 8_192),
    ("llama",                  128_000, 8_192),
    ("mistral",                128_000, 8_192),
    ("mixtral",                 32_768, 8_192),
    ("codestral",              256_000, 8_192),
    ("command-r",              128_000, 4_096),
]

# Conservative default for completely unknown models
_DEFAULT_CONTEXT_WINDOW = 32_000
_DEFAULT_MAX_OUTPUT = 4_096

# Reserve ratio: fraction of context window reserved for output + safety margin
_OUTPUT_RESERVE_RATIO = 0.15
_SAFETY_MARGIN_TOKENS = 500

# Heuristic: average characters per token (calibrated across GPT-4, Claude, Gemini)
_CHARS_PER_TOKEN_HEURISTIC = 3.4

# In-memory dynamic context length cache (model@base_url -> (context_window, max_output))
_DYNAMIC_CONTEXT_CACHE: Dict[str, Tuple[int, int]] = {}


def parse_context_limit_from_error(error_msg: str) -> Optional[int]:
    """
    Hermes Agent Parity (agent/model_metadata.py:parse_context_limit_from_error):
    Extracts context limit quoted dynamically in a provider error message.
    Handles vLLM, OpenRouter, Google Gemini, Anthropic, and OpenAI error formats.
    """
    if not error_msg:
        return None
    error_lower = str(error_msg).lower()
    patterns = (
        r'max_model_len\s*(?:is\s*)?[:=(]?\s*(\d{4,})',          # vLLM
        r'maximum model length\s*(?:is\s*)?[:=(]?\s*(\d{4,})',  # vLLM alt
        r'(?:max(?:imum)?|limit)\s*(?:context\s*)?(?:length|size|window)?\s*(?:is|of|:)?\s*(\d{4,})',
        r'context\s*(?:length|size|window)\s*(?:is|of|:)?\s*(\d{4,})',
        r'(\d{4,})\s*(?:token)?\s*(?:context|limit)',
        r'>\s*(\d{4,})\s*(?:max|limit|token)',                 # "250000 tokens > 200000 maximum"
        r'(\d{4,})\s*(?:max(?:imum)?)\b',                     # "200000 maximum"
        r'supports?\s+(?:only\s+)?up\s+to\s+(\d{4,})',        # Gemini: "only supports up to 32768"
    )
    for pattern in patterns:
        m = re.search(pattern, error_lower)
        if m:
            val = int(m.group(1))
            if 1024 <= val <= 10_000_000:
                return val
    return None


def _clean_model_key(model: str, base_url: str = "") -> str:
    m = (model or "").strip().lower()
    b = (base_url or "").strip().lower().rstrip("/")
    return f"{m}@{b}" if b else m


def save_context_length(model: str, length: int, max_output: Optional[int] = None, base_url: str = "") -> None:
    """
    Persists a dynamically discovered or error-learned context window limit (Hermes Parity).
    Zero manual configuration required: model limits are saved across server runs.
    """
    if not model or length <= 0:
        return
    out_cap = max_output or min(65536, max(4096, int(length * _OUTPUT_RESERVE_RATIO)))
    key = _clean_model_key(model, base_url)
    _DYNAMIC_CONTEXT_CACHE[key] = (length, out_cap)
    _DYNAMIC_CONTEXT_CACHE[model.strip().lower()] = (length, out_cap)

    # Persist to backend/prompts/config/context_length_cache.yaml
    try:
        from core.prompt_loader import load_config_yaml, _get_prompts_dir
        cfg_path = _get_prompts_dir() / "config" / "context_length_cache.yaml"
        current_cfg = load_config_yaml("config/context_length_cache.yaml", default={}) or {}
        lengths_dict = current_cfg.get("context_lengths") or {}
        if lengths_dict.get(key) != length:
            lengths_dict[key] = length
            current_cfg["context_lengths"] = lengths_dict
            import yaml
            os.makedirs(cfg_path.parent, exist_ok=True)
            with open(cfg_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(current_cfg, f, default_flow_style=False)
            logger.info(f"[TokenBudget] Persisted learned context window: {key} -> {length:,} tokens (out={out_cap:,})")
    except Exception as e:
        logger.debug(f"[TokenBudget] Cache persist notice: {e}")


def get_cached_context_length(model: str, base_url: str = "") -> Optional[Tuple[int, int]]:
    """Retrieves context length from memory cache or persistent context_length_cache.yaml."""
    if not model:
        return None
    key = _clean_model_key(model, base_url)
    if key in _DYNAMIC_CONTEXT_CACHE:
        return _DYNAMIC_CONTEXT_CACHE[key]
    m_clean = model.strip().lower()
    if m_clean in _DYNAMIC_CONTEXT_CACHE:
        return _DYNAMIC_CONTEXT_CACHE[m_clean]

    # Check YAML cache
    try:
        from core.prompt_loader import load_config_yaml
        cfg = load_config_yaml("config/context_length_cache.yaml", default={}) or {}
        lengths = cfg.get("context_lengths") or {}
        for probe in (key, m_clean, f"{m_clean}/"):
            if probe in lengths:
                val = lengths[probe]
                if isinstance(val, int) and val > 0:
                    out = min(65536, max(4096, int(val * _OUTPUT_RESERVE_RATIO)))
                    _DYNAMIC_CONTEXT_CACHE[probe] = (val, out)
                    return (val, out)
    except Exception:
        pass
    return None


def _infer_context_from_model_name(clean_model_id: str) -> Optional[Tuple[int, int]]:
    """
    Dynamically infers context window from model naming tokens (e.g. '1m', '128k', '32k')
    for custom/unknown models without requiring manual code entry.
    """
    m = clean_model_id.lower()
    # 1. Million token models (1M, 2M)
    if any(tag in m for tag in ("-1m", "_1m", "1m-", "-2m", "_2m", "2m-")):
        return 1_048_576, 65_536

    # 2. Explicit K-token sizes in name (e.g. 'qwen-128k', 'model:32k', '128k-context')
    k_match = re.search(r"[-_:](\d+)[kK]\b", m)
    if k_match:
        k_val = int(k_match.group(1))
        if 4 <= k_val <= 2048:
            ctx = k_val * 1024
            return ctx, min(65536, max(4096, int(ctx * _OUTPUT_RESERVE_RATIO)))

    # 3. Known modern open-weights model families defaulting to 128k/256k
    if any(tag in m for tag in ("minimax", "minimax-m3")):
        return 1_048_576, 32_768
    if any(tag in m for tag in ("deepseek-v3", "deepseek-r1", "deepseek")):
        return 128_000, 8_192
    if any(tag in m for tag in ("qwen2.5", "qwen-2.5", "qwen2", "qwen")):
        return 128_000, 8_192
    if any(tag in m for tag in ("llama-3.1", "llama-3.2", "llama-3.3", "llama-3")):
        return 128_000, 8_192
    if "codestral" in m:
        return 256_000, 8_192
    if any(tag in m for tag in ("mistral-large", "mistral-small", "pixtral")):
        return 128_000, 8_192
    if "internlm" in m:
        return 200_000, 8_192

    return None


def get_model_context_window(model_id: str, base_url: str = "") -> Tuple[int, int]:
    """
    Returns (context_window_tokens, max_output_tokens) for a model.
    Hermes & Claude Code Parity 4-Tier Dynamic Resolution:
    1. Persistent Context Cache (context_length_cache.yaml + live memory)
    2. Model Context Registry prefix match
    3. Model Name Token Heuristics (1m, 128k, etc.)
    4. Conservative default fallback (32,000 tokens)
    """
    if not model_id:
        return _DEFAULT_CONTEXT_WINDOW, _DEFAULT_MAX_OUTPUT

    # Tier 1: Check dynamic persistent cache
    cached = get_cached_context_length(model_id, base_url=base_url)
    if cached is not None:
        return cached

    # Normalize: strip provider prefixes iteratively (handles openrouter/google/gemini-... etc.)
    clean = model_id.lower().strip()
    _PROVIDER_PREFIXES = (
        "models/", "9router/ag/", "9router/", "ag/",
        "openrouter/", "groq/", "anthropic/", "openai/",
        "codex/", "xai/", "deepseek/", "ollama/",
        "google/", "meta-llama/", "mistralai/", "cohere/",
    )
    changed = True
    while changed:
        changed = False
        for prefix in _PROVIDER_PREFIXES:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                changed = True
                break

    # Strip common suffixes that don't affect context window
    for suffix in ("-thinking", "-high", "-latest", "-preview",
                   "-live-preview", "-native-audio", ":free"):
        clean = clean.replace(suffix, "")

    # Check cache again with normalized clean name
    cached_clean = get_cached_context_length(clean, base_url=base_url)
    if cached_clean is not None:
        return cached_clean

    # Tier 2: Check registry
    for pattern, ctx_window, max_output in _MODEL_CONTEXT_WINDOWS:
        if clean.startswith(pattern):
            return ctx_window, max_output

    # Tier 3: Infer dynamically from model name tokens (e.g. 1m, 128k, minimax, deepseek)
    inferred = _infer_context_from_model_name(clean) or _infer_context_from_model_name(model_id)
    if inferred is not None:
        # Cache for subsequent turns
        save_context_length(model_id, inferred[0], max_output=inferred[1], base_url=base_url)
        return inferred

    # Tier 4: Fallback
    return _DEFAULT_CONTEXT_WINDOW, _DEFAULT_MAX_OUTPUT


def get_input_budget(model_id: str, base_url: str = "") -> int:
    """
    Returns the maximum number of tokens available for input (system prompt + messages).
    Calculated as: context_window - max_output - safety_margin.
    """
    ctx_window, max_output = get_model_context_window(model_id, base_url=base_url)
    reserve = max(max_output, int(ctx_window * _OUTPUT_RESERVE_RATIO))
    return max(ctx_window - reserve - _SAFETY_MARGIN_TOKENS, 1024)


# ── Tokenizer ──────────────────────────────────────────────────────────────────

_tiktoken_encoding = None
_tiktoken_load_attempted = False


def _get_tiktoken_encoding():
    """Lazily loads the cl100k_base tiktoken encoding (GPT-4/Claude compatible)."""
    global _tiktoken_encoding, _tiktoken_load_attempted
    if _tiktoken_load_attempted:
        return _tiktoken_encoding
    _tiktoken_load_attempted = True
    try:
        import tiktoken
        _tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
        logger.debug("[TokenBudget] tiktoken cl100k_base encoding loaded.")
    except Exception as e:
        logger.info(f"[TokenBudget] tiktoken unavailable, using heuristic: {e}")
        _tiktoken_encoding = None
    return _tiktoken_encoding


def count_tokens(text: str) -> int:
    """
    Counts tokens in a text string.
    Uses tiktoken cl100k_base if available, otherwise falls back to a calibrated heuristic.
    """
    if not text:
        return 0
    enc = _get_tiktoken_encoding()
    if enc is not None:
        try:
            return len(enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Heuristic fallback: 1 token ≈ 3.4 characters (tuned for English + code + multilingual)
    return max(1, int(len(text) / _CHARS_PER_TOKEN_HEURISTIC))


def count_messages_tokens(messages: List[Any]) -> int:
    """
    Estimates total tokens across a list of chat messages.
    Supports standard OpenAI dicts, Anthropic content-block lists, and Gemini types.Content objects.
    Includes per-message overhead (role label, formatting tokens).
    """
    total = 0
    for msg in messages:
        content_str = ""
        if isinstance(msg, dict):
            c = msg.get("content", "")
            if isinstance(c, str):
                content_str = c
            elif isinstance(c, list):
                content_str = " ".join(
                    str(b.get("text", "") or b.get("content", ""))
                    for b in c if isinstance(b, dict)
                )
        elif hasattr(msg, "parts") and msg.parts:
            # Gemini types.Content: accurately measure text, function_call, and function_response
            parts_txt = []
            for p in msg.parts:
                t = getattr(p, "text", None)
                if t:
                    parts_txt.append(t)
                fc = getattr(p, "function_call", None)
                if fc:
                    fc_name = getattr(fc, "name", "") or ""
                    fc_args = getattr(fc, "args", {}) or {}
                    parts_txt.append(f"{fc_name} {json.dumps(fc_args) if isinstance(fc_args, dict) else str(fc_args)}")
                fr = getattr(p, "function_response", None)
                if fr:
                    fr_name = getattr(fr, "name", "") or ""
                    fr_resp = getattr(fr, "response", {}) or {}
                    parts_txt.append(f"{fr_name} {json.dumps(fr_resp) if isinstance(fr_resp, dict) else str(fr_resp)}")
            content_str = " ".join(parts_txt)
        else:
            content_str = str(msg)

        total += count_tokens(content_str) + 4  # ~4 tokens overhead per message (role + delimiters)
    total += 3  # priming tokens
    return total


# ── Token Budget Tracker ───────────────────────────────────────────────────────

class TokenBudgetTracker:
    """
    Tracks token consumption within a ReAct agent loop and provides budget-aware
    decisions for context management.

    Usage in the ReAct loop:
        tracker = TokenBudgetTracker(model_id="gemini-2.5-flash")
        for step in range(max_steps):
            if tracker.is_budget_critical(messages):
                # Force final narrative response
                break
            # ... execute step ...
            tracker.record_step(step, messages)
    """

    def __init__(self, model_id: str = ""):
        self.model_id = model_id
        self.context_window, self.max_output = get_model_context_window(model_id)
        self.input_budget = get_input_budget(model_id)
        self._step_token_history: List[int] = []

        logger.debug(
            f"[TokenBudget] Initialized: model={model_id}, "
            f"context_window={self.context_window:,}, "
            f"input_budget={self.input_budget:,}"
        )

    def update_model_context(self, new_context_length: int, new_max_output: Optional[int] = None) -> None:
        """Dynamically updates context limits when learned from provider error or endpoint (Hermes Parity)."""
        if new_context_length <= 0:
            return
        self.context_window = new_context_length
        if new_max_output:
            self.max_output = new_max_output
        reserve = max(self.max_output, int(self.context_window * _OUTPUT_RESERVE_RATIO))
        self.input_budget = max(self.context_window - reserve - _SAFETY_MARGIN_TOKENS, 1024)
        logger.info(f"[TokenBudget] Dynamically updated context limits: window={self.context_window:,}, budget={self.input_budget:,}")

    def current_usage(self, messages: List[Dict[str, str]]) -> int:
        """Returns the current token count of the messages list."""
        return count_messages_tokens(messages)

    def remaining_budget(self, messages: List[Dict[str, str]]) -> int:
        """Returns how many input tokens are left before hitting the budget."""
        return max(0, self.input_budget - self.current_usage(messages))

    def usage_ratio(self, messages: List[Dict[str, str]]) -> float:
        """Returns the fraction of input budget consumed (0.0 to 1.0+)."""
        usage = self.current_usage(messages)
        return usage / self.input_budget if self.input_budget > 0 else 1.0

    def is_budget_critical(self, messages: List[Dict[str, str]]) -> bool:
        """
        Returns True if the context is critically full and the loop should
        force a final narrative response on the next turn.
        Threshold: >90% of input budget consumed.
        """
        return self.usage_ratio(messages) > 0.90

    def should_compact_context(self, messages: List[Dict[str, str]]) -> bool:
        """
        Returns True if context has grown enough to warrant compaction.
        Threshold: >65% of input budget consumed.
        """
        return self.usage_ratio(messages) > 0.65

    def record_step(self, step: int, messages: List[Dict[str, str]]) -> None:
        """Records token usage for a loop step (for diagnostics/telemetry)."""
        usage = self.current_usage(messages)
        self._step_token_history.append(usage)

    def compact_messages_if_needed(self, messages: List[Dict[str, str]]) -> bool:
        """
        Token-aware in-loop context compaction. Replaces the old 24-message / 4000-char heuristic.

        Strategy:
        - Preserves messages[0] (system) and messages[1] (original user prompt)
        - Preserves the last 6 messages (recent context)
        - Truncates older tool observation messages proportionally to free up budget

        Returns True if any compaction was performed.
        """
        if not self.should_compact_context(messages):
            return False

        if len(messages) <= 8:
            return False

        compacted = False
        # Target: compact until we're below 70% usage
        target_tokens = int(self.input_budget * 0.70)
        current = self.current_usage(messages)

        if current <= target_tokens:
            return False

        # Compact from oldest to newest, skip first 2 (system + user) and last 6
        safe_start = 2
        safe_end = len(messages) - 6

        for idx in range(safe_start, safe_end):
            if current <= target_tokens:
                break

            msg = messages[idx]
            content = msg.get("content", "")
            if not content or len(content) < 500:
                continue

            # Only compact user messages (tool observations) and assistant messages
            old_tokens = count_tokens(content)

            # Progressive truncation based on how far over budget we are
            overflow_ratio = current / target_tokens
            if overflow_ratio > 1.5:
                # Aggressive: keep only first line + last 200 chars
                first_line = content.split("\n")[0][:200]
                tail = content[-200:] if len(content) > 200 else ""
                new_content = f"{first_line}\n[... compacted for context efficiency — {old_tokens} tokens ...]\n{tail}"
            elif overflow_ratio > 1.2:
                # Moderate: head 800 + tail 400
                new_content = content[:800] + f"\n[... compacted — {old_tokens} tokens ...]\n" + content[-400:]
            else:
                # Light: head 1500 + tail 600
                new_content = content[:1500] + f"\n[... compacted — {old_tokens} tokens ...]\n" + content[-600:]

            new_tokens = count_tokens(new_content)
            if new_tokens < old_tokens:
                messages[idx] = {**msg, "content": new_content}
                current -= (old_tokens - new_tokens)
                compacted = True

        if compacted:
            logger.info(
                f"[TokenBudget] Context compacted: {self.current_usage(messages):,} tokens "
                f"(budget: {self.input_budget:,}, ratio: {self.usage_ratio(messages):.1%})"
            )

        return compacted

    def get_diagnostics(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Returns diagnostic info for telemetry/debugging."""
        usage = self.current_usage(messages)
        return {
            "model_id": self.model_id,
            "context_window": self.context_window,
            "input_budget": self.input_budget,
            "current_usage": usage,
            "remaining": max(0, self.input_budget - usage),
            "usage_ratio": round(self.usage_ratio(messages), 3),
            "is_critical": self.is_budget_critical(messages),
            "message_count": len(messages),
            "step_history": self._step_token_history[-10:],  # last 10 steps
        }


# ── Prompt Assembly Budget Helper ──────────────────────────────────────────────

def budget_aware_slot_assembly(
    slots: List[str],
    model_id: str = "",
    reserved_for_conversation: int = 0,
) -> str:
    """
    Assembles prompt slots with token budget awareness.
    If the total exceeds the available budget, prunes optional slots (last to first)
    and truncates the largest remaining slot.

    Args:
        slots: List of prompt slot strings (slot 0 = identity, always kept)
        model_id: Active model ID for context window lookup
        reserved_for_conversation: Tokens to reserve for conversation history + tool spec

    Returns:
        Assembled prompt string that fits within the budget.
    """
    input_budget = get_input_budget(model_id)
    available = input_budget - reserved_for_conversation

    # Minimum viable prompt: at least 2000 tokens for identity + mode
    if available < 2000:
        available = 2000

    full_prompt = "\n\n".join(slots)
    total_tokens = count_tokens(full_prompt)

    if total_tokens <= available:
        return full_prompt

    logger.info(
        f"[TokenBudget] Prompt slots exceed budget: {total_tokens:,} > {available:,} tokens. "
        f"Pruning optional slots..."
    )

    # Measure each slot
    slot_tokens = [count_tokens(s) for s in slots]

    # Prune from the last slot backward (slots 0-1 are always kept: identity + mode)
    pruned_slots = list(slots)
    pruned_tokens = list(slot_tokens)
    min_protected = 2  # identity + mode always kept

    while sum(pruned_tokens) > available and len(pruned_slots) > min_protected:
        removed_slot = pruned_slots.pop()
        removed_tokens = pruned_tokens.pop()
        logger.debug(f"[TokenBudget] Pruned slot ({removed_tokens:,} tokens): {removed_slot[:60]}...")

    # If still over budget, truncate the largest non-identity slot
    current_total = sum(pruned_tokens)
    if current_total > available and len(pruned_slots) > 1:
        # Find the largest slot (skip slot 0)
        largest_idx = max(range(1, len(pruned_slots)), key=lambda i: pruned_tokens[i])
        overflow = current_total - available
        content = pruned_slots[largest_idx]

        # Truncate to fit
        target_chars = max(200, len(content) - int(overflow * _CHARS_PER_TOKEN_HEURISTIC * 1.2))
        pruned_slots[largest_idx] = content[:target_chars] + "\n[... truncated for context budget ...]"

        logger.debug(
            f"[TokenBudget] Truncated slot {largest_idx} from "
            f"{pruned_tokens[largest_idx]:,} to ~{count_tokens(pruned_slots[largest_idx]):,} tokens"
        )

    return "\n\n".join(pruned_slots)
