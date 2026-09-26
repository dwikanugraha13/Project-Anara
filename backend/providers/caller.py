from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple
import httpx
from config import cfg_get

from .accounts import (
    get_provider_key,
)
from .discovery import refresh_codex_oauth_token_if_needed

logger = logging.getLogger(__name__)

THINK_TAG_NAMES: Tuple[str, ...] = (
    "think", "thinking", "reasoning", "thought", "REASONING_SCRATCHPAD",
    "思考", "反思", "推理", "推敲",
)
THINK_OPEN_TAGS: Tuple[str, ...] = tuple(f"<{name.lower()}>" for name in THINK_TAG_NAMES)
THINK_CLOSE_TAGS: Tuple[str, ...] = tuple(f"</{name.lower()}>" for name in THINK_TAG_NAMES)


class StreamingThinkScrubber:
    """
    Anara Enterprise Architecture: Stateful reasoning tag scrubber buffering across chunk boundaries.
    Preserves mid-line mentions of '<think>' while stripping bona-fide open blocks and closed pairs.
    """
    _OPEN_TAGS: Tuple[str, ...] = THINK_OPEN_TAGS
    _CLOSE_TAGS: Tuple[str, ...] = THINK_CLOSE_TAGS
    _ALL_TAGS: Tuple[str, ...] = _OPEN_TAGS + _CLOSE_TAGS
    _MAX_TAG_LEN: int = max(len(tag) for tag in _ALL_TAGS)
    _ORPHAN_CLOSE_RE = re.compile(
        "(?:" + "|".join(re.escape(t) for t in _CLOSE_TAGS) + r")[ 	\n\r]*", re.IGNORECASE
    )

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        """Reset all state. Call at the top of every new turn."""
        self._in_block: bool = False
        self._buf: str = ""
        self._last_emitted_ended_newline: bool = True
        self.last_hidden: str = ""

    def _emit(self, out: list[str], text: str) -> None:
        """Append visible prose to out (orphan close tags stripped) and track the newline flag."""
        text = self._strip_orphan_close_tags(text)
        if text:
            out.append(text)
            self._last_emitted_ended_newline = text.endswith("\n")

    def feed(self, text: str) -> str:
        """Feed one delta; return the scrubbed visible portion."""
        self.last_hidden = ""
        if not text:
            return ""
        buf = self._buf + text
        self._buf = ""
        out: list[str] = []
        hidden: list[str] = []

        while buf:
            if self._in_block:
                close_idx, close_len = self._find_first_tag(buf, self._CLOSE_TAGS)
                if close_idx == -1:
                    hidden.append(self._hold_partial(buf, self._CLOSE_TAGS))
                    break
                hidden.append(buf[:close_idx])
                buf = buf[close_idx + close_len:]
                self._in_block = False
                continue

            pair = self._find_earliest_closed_pair(buf)
            open_idx, open_len = self._find_open_at_boundary(buf, out)
            if pair is not None and (open_idx == -1 or pair[0] <= open_idx):
                self._emit(out, buf[:pair[0]])
                hidden.append(buf[buf.index(">", pair[0]) + 1:buf.rindex("<", pair[0], pair[1])])
                buf = buf[pair[1]:]
                continue
            if open_idx != -1:
                self._emit(out, buf[:open_idx])
                self._in_block = True
                buf = buf[open_idx + open_len:]
                continue

            self._emit(out, self._hold_partial(buf, self._ALL_TAGS))
            break

        self.last_hidden = "".join(hidden)
        return "".join(out)

    def _hold_partial(self, buf: str, tags: Tuple[str, ...]) -> str:
        held = self._max_partial_suffix(buf, tags)
        self._buf = buf[-held:] if held else ""
        return buf[:-held] if held else buf

    def flush(self) -> str:
        tail = "" if self._in_block else self._buf
        self._buf = ""
        self._in_block = False
        self._last_emitted_ended_newline = True
        return self._strip_orphan_close_tags(tail) if tail else ""

    @staticmethod
    def _find_first_tag(buf: str, tags: Tuple[str, ...]) -> Tuple[int, int]:
        buf_lower = buf.lower()
        hits = [(idx, len(tag)) for tag in tags if (idx := buf_lower.find(tag)) != -1]
        return min(hits) if hits else (-1, 0)

    def _find_earliest_closed_pair(self, buf: str):
        buf_lower = buf.lower()
        pairs = []
        for open_tag, close_tag in zip(self._OPEN_TAGS, self._CLOSE_TAGS):
            open_idx = buf_lower.find(open_tag)
            close_idx = buf_lower.find(close_tag, open_idx + len(open_tag)) if open_idx != -1 else -1
            if close_idx != -1:
                pairs.append((open_idx, close_idx + len(close_tag)))
        return min(pairs) if pairs else None

    def _find_open_at_boundary(self, buf: str, already_emitted: list[str]) -> Tuple[int, int]:
        buf_lower = buf.lower()
        hits = []
        for tag in self._OPEN_TAGS:
            idx = buf_lower.find(tag)
            while idx != -1 and not self._is_block_boundary(buf, idx, already_emitted):
                idx = buf_lower.find(tag, idx + 1)
            if idx != -1:
                hits.append((idx, len(tag)))
        return min(hits) if hits else (-1, 0)

    def _is_block_boundary(self, buf: str, idx: int, already_emitted: list[str]) -> bool:
        prior_newline = already_emitted[-1].endswith("\n") if already_emitted else self._last_emitted_ended_newline
        if idx == 0:
            return prior_newline
        preceding = buf[:idx]
        last_nl = preceding.rfind("\n")
        return (prior_newline if last_nl == -1 else True) and preceding[last_nl + 1:].strip() == ""

    @classmethod
    def _max_partial_suffix(cls, buf: str, tags: Tuple[str, ...]) -> int:
        buf_lower = buf.lower()
        for i in range(min(len(buf_lower), cls._MAX_TAG_LEN - 1), 0, -1):
            suffix = buf_lower[-i:]
            if any(len(tag) > i and tag.startswith(suffix) for tag in tags):
                return i
        return 0

    @classmethod
    def _strip_orphan_close_tags(cls, text: str) -> str:
        return cls._ORPHAN_CLOSE_RE.sub("", text) if "</" in text else text


async def stream_universal_chat_model(
    model_id: str,
    user_prompt: str,
    system_instruction: str = "",
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    usage_out: Optional[Dict[str, Any]] = None,
):
    """
    Polymorphic streaming entrypoint (Anara Enterprise Architecture).
    Routes dynamically through ProfileRegistry with integrated StreamingThinkScrubber.
    Zero static hardcoded model shortcuts: 100% Open-Closed Principle compliant.
    """
    scrubber = StreamingThinkScrubber()

    # 1. Polymorphic Profile Streaming
    try:
        from .profile_registry import resolve_provider_profile
        profile = resolve_provider_profile(model_id)
        has_yielded = False
        async for chunk in profile.stream_chat(
            model_id=model_id,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            usage_out=usage_out,
        ):
            if chunk:
                cleaned = scrubber.feed(chunk)
                if cleaned:
                    has_yielded = True
                    yield cleaned
        tail = scrubber.flush()
        if tail:
            has_yielded = True
            yield tail
        if has_yielded:
            return
    except Exception as e_prof:
        logger.warning(f"[Stream] Profile stream error for '{model_id}': {e_prof}")

    # 2. Fallback: Full non-streaming call on primary model
    try:
        full = await call_universal_chat_model(
            model_id=model_id,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            read_only=False,
        )
        if full:
            cleaned_full = _strip_think_blocks(full)
            if cleaned_full:
                yield cleaned_full
                return
    except Exception as e_call:
        logger.warning(f"[Stream] Non-streaming primary call error for '{model_id}': {e_call}")

    # 3. Fallback: Multi-tier fallback model ladder (Anara Standard)
    from .accounts import get_fallback_model_id
    fallback_model = get_fallback_model_id()
    if fallback_model and fallback_model != model_id:
        logger.info(f"[Stream] Primary model '{model_id}' failed; engaging fallback ladder to '{fallback_model}'...")
        try:
            from .profile_registry import resolve_provider_profile
            fb_profile = resolve_provider_profile(fallback_model)
            scrubber.reset()
            has_yielded = False
            async for chunk in fb_profile.stream_chat(
                model_id=fallback_model,
                user_prompt=user_prompt,
                system_instruction=system_instruction,
                max_tokens=max_tokens,
                temperature=temperature,
                usage_out=usage_out,
            ):
                if chunk:
                    cleaned = scrubber.feed(chunk)
                    if cleaned:
                        has_yielded = True
                        yield cleaned
            tail = scrubber.flush()
            if tail:
                has_yielded = True
                yield tail
            if has_yielded:
                return
        except Exception as e_fb:
            logger.warning(f"[Stream] Fallback ladder stream error for '{fallback_model}': {e_fb}")


def _robust_parse_json(candidate_str: str) -> Optional[Any]:
    """Attempts standard and fault-tolerant JSON deserialization with safe repair."""
    if not candidate_str or not candidate_str.strip():
        return None
    s = candidate_str.strip()

    # Attempt 1: Standard load
    try:
        return json.loads(s)
    except Exception:
        pass

    # Attempt 2: Trailing comma repair
    try:
        repaired = re.sub(r',\s*([\}\]])', r'\1', s)
        return json.loads(repaired)
    except Exception:
        pass

    # Attempt 3: AST literal eval fallback for Python dict/list structures
    try:
        import ast
        val = ast.literal_eval(s)
        if isinstance(val, (dict, list)):
            return val
    except Exception:
        pass

    return None


def _sanitize_lead_narration(raw_lead: str) -> str:
    """
    Anara Anti-Leak Sanitizer for narrative text:
    Strips raw tool call blocks, XML tags, observation dumps, and directory listings.
    Guarantees pure human conversational prose without technical payload residue.
    """
    if not raw_lead or not raw_lead.strip():
        return ""

    text = raw_lead.strip()

    # 1. Strip any markdown code blocks containing tool calls or JSON
    text = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", text)
    text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.IGNORECASE)

    # 2. Strip standalone JSON objects with action: tool_call
    text = re.sub(r"\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}", "", text)

    # 3. Strip observation artifacts (e.g. \f"...", [TOOL RESULT], [OBSERVATION], [DIRECTORY STATUS])
    text = re.sub(r'\\f["\'][^\n]*', "", text)
    text = re.sub(r'\[(?:TOOL[ _](?:RESULT|OBSERVATION|ERROR)|OBSERVATION|DIRECTORY[ _]STATUS|TOOL RESULT|STATUS[^\]]*|OBSERVASI|HASIL)[^\]]*\][^\n]*', "", text, flags=re.IGNORECASE)

    # 4. Strip directory listing lines (e.g. - [DIR] ..., - [FILE] ...)
    text = re.sub(r"(?m)^\s*-\s*\[(?:DIR|FILE)\][^\n]*\n?", "", text)

    # 5. Strip isolated backticks or broken fence remnants
    text = re.sub(r"```(?:json|shell|bash)?\s*```", "", text)
    text = text.strip()

    # If the text has no meaningful narrative words (only punctuation, whitespace, or technical tokens)
    words = [w for w in re.findall(r"\b\w+\b", text) if w.lower() not in ("json", "action", "tool", "tool_call", "arguments")]
    if len(words) < 2:
        return ""

    return text


def _format_empty_model_notice(prompt: str = "") -> str:
    """
    Hermes Dynamic Universal Fallback Notice:
    Returns a clean, neutral technical fallback notice when the model produces an empty turn,
    without brittle Unicode character range checks, biased language assumptions, or rigid hardcoding.
    """
    return "No response was generated for this turn. Please retry or rephrase your request."


def _strip_think_blocks(text: str) -> str:
    """
    Anara Standard (agent/think_scrubber.py & gateway/stream_consumer_think.py):
    Strips inline <think>, <thought>, <reasoning>, and multilingual thinking blocks,
    orphan tags, and bare thinking monologue preambles from model responses.
    """
    if not text:
        return ""
    tag_pattern = "|".join(re.escape(name) for name in THINK_TAG_NAMES)
    pattern = rf"(?is)<(?:{tag_pattern})\b[^>]*>[\s\S]*?</(?:{tag_pattern})>"
    text = re.sub(pattern, "", text)
    # Strip unclosed opening think tag at start of output
    text = re.sub(rf"(?is)^<(?:{tag_pattern})\b[^>]*>[\s\S]*?(?:(?=```)|$)", "", text)
    # Strip orphan closing tags
    text = re.sub(rf"(?i)</(?:{tag_pattern})>", "", text)
    return text.strip()


def _clean_model_chat_text(raw_text: str) -> str:
    """
    Cleans model chat responses by removing markdown tool-call fences,
    bare JSON tool payloads, reasoning/think blocks, observation tags, and trailing punctuation/braces (Anara Standard).
    Guarantees that responses consisting solely of brackets or punctuation (e.g. '}', '{}', '```')
    are treated as empty so proper conversational synthesis is executed.
    """
    if not raw_text or not isinstance(raw_text, str):
        return ""
    text = _strip_think_blocks(raw_text.strip())

    # 1. Strip markdown fences containing tool calls
    text = re.sub(r"```(?:json)?\s*\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}\s*```", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.IGNORECASE)

    # 2. Strip standalone/bare JSON blocks containing action: tool_call
    text = re.sub(r"\{[\s\S]*?\"action\"\s*:\s*\"tool_call\"[\s\S]*?\}", "", text, flags=re.IGNORECASE)

    # 3. Strip observation tags
    text = re.sub(r'\[(?:TOOL[ _](?:RESULT|OBSERVATION|ERROR)|OBSERVATION|DIRECTORY[ _]STATUS|TOOL RESULT)[^\]]*\][^\n]*', "", text, flags=re.IGNORECASE)

    # 4. Strip empty fences and trailing/leading structural punctuation
    text = re.sub(r"```(?:json|shell|bash)?\s*```", "", text)
    text = text.strip()
    text = text.strip("{}[]` \t\r\n")

    # 5. Check if remaining text contains actual words (Unicode word characters)
    words = [w for w in re.findall(r"[\w\d]+", text, re.UNICODE) if w.lower() not in ("json", "action", "tool", "tool_call", "arguments")]
    if not words:
        return ""

    return text


def _extract_json_balanced(text: str) -> List[tuple[str, int, int]]:
    """
    Deterministic bracket-balancing parser for JSON objects in text (Anara Standard).
    Accurately extracts top-level { ... } pairs while respecting quotes and escape characters.
    Returns: list of (json_str, start_pos, end_pos)
    """
    results = []
    in_str = False
    escape = False
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if not in_str:
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    results.append((text[start:i+1], start, i+1))
                    start = None
                elif depth < 0:
                    depth = 0
                    start = None

    return results


def _extract_and_parse_tool_calls(raw_out: str) -> tuple[List[Dict[str, Any]], str, bool]:
    """
    Extracts and robustly parses one or more tool call payloads from model output text.
    Supports:
    - Multiple ```json ... ``` blocks
    - Array of tool calls: [ {"action": "tool_call", ...}, ... ]
    - Multiple XML style: <tool_call>{ ... }</tool_call>
    - Bare JSON object: { "action": "tool_call", ... }
    Guarantees earliest-boundary lead text extraction with Anara Anti-Leak Sanitization.
    Returns: (list_of_payloads, lead_text, is_malformed_candidate)
    """
    if not raw_out or not raw_out.strip():
        return [], "", False

    text = raw_out.strip()
    calls: List[Dict[str, Any]] = []
    earliest_tool_start = None

    def _normalize_and_add(parsed_obj: Any):
        if isinstance(parsed_obj, dict):
            if parsed_obj.get("action") == "tool_call" or "tool" in parsed_obj:
                calls.append({
                    "action": "tool_call",
                    "tool": parsed_obj.get("tool", ""),
                    "arguments": parsed_obj.get("arguments", {}) or {},
                })
            elif isinstance(parsed_obj.get("tool_calls"), list):
                for sub in parsed_obj["tool_calls"]:
                    _normalize_and_add(sub)
        elif isinstance(parsed_obj, list):
            for sub in parsed_obj:
                _normalize_and_add(sub)

    # 1. Look for all XML style <tool_call>...</tool_call> blocks
    xml_matches = list(re.finditer(r"<tool_call>\s*([\s\S]*?)\s*</tool_call>", text, re.IGNORECASE))
    if xml_matches:
        for xm in xml_matches:
            parsed = _robust_parse_json(xm.group(1))
            if parsed is not None:
                if earliest_tool_start is None or xm.start() < earliest_tool_start:
                    earliest_tool_start = xm.start()
                _normalize_and_add(parsed)

    # 2. Look for all markdown code blocks ```json ... ``` or ``` ... ```
    block_matches = list(re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text))
    if block_matches:
        for bm in block_matches:
            block_content = bm.group(1).strip()
            if ('"action"' in block_content and '"tool"' in block_content) or ('"tool"' in block_content and '{' in block_content):
                parsed = _robust_parse_json(block_content)
                if parsed is not None:
                    if earliest_tool_start is None or bm.start() < earliest_tool_start:
                        earliest_tool_start = bm.start()
                    _normalize_and_add(parsed)

    # 3. Look for bare JSON objects or array if no blocks matched
    if not calls:
        if (text.startswith("{") or text.startswith("[")) and ('"tool"' in text or '"action"' in text):
            parsed = _robust_parse_json(text)
            if parsed is not None:
                earliest_tool_start = 0
                _normalize_and_add(parsed)
        else:
            # Deterministic Bracket-Balancing JSON extraction (Anara Standard)
            for candidate, start_idx, _ in _extract_json_balanced(text):
                if ('"action"' in candidate and '"tool_call"' in candidate) or ('"tool"' in candidate and '"arguments"' in candidate):
                    parsed = _robust_parse_json(candidate)
                    if parsed is not None:
                        if earliest_tool_start is None or start_idx < earliest_tool_start:
                            earliest_tool_start = start_idx
                        _normalize_and_add(parsed)

    lead_text = ""
    if earliest_tool_start is not None and earliest_tool_start > 0:
        lead_text = text[:earliest_tool_start].strip()

    lead_text = _sanitize_lead_narration(lead_text)

    if calls:
        return calls, lead_text, False

    # Check if text was likely an intended tool call that failed parsing
    if re.search(r'["\']action["\']\s*:\s*["\']tool_call["\']', text) or "<tool_call>" in text:
        return [], text, True

    return [], text, False


def _extract_and_parse_tool_call(raw_out: str) -> tuple[Optional[Dict[str, Any]], str, bool]:
    """Compatibility wrapper returning single tool call payload."""
    calls, lead_text, is_malformed = _extract_and_parse_tool_calls(raw_out)
    return (calls[0] if calls else None, lead_text, is_malformed)


async def _execute_native_agent_loop(
    native_turn_caller: Callable[[List[Any]], Awaitable[Any]],
    record_results_fn: Callable[[List[Any], Any, List[Tuple[Any, str, bool]]], None],
    initial_history: List[Any],
    user_prompt: str,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
    intercept_mutating_tools: bool = False,
    model_id: str = "",
    max_steps: int = 25,
) -> Any:
    """
    Anara Enterprise Architecture: Native Structured Tool Calling Agent Loop.
    Executes multi-turn tool loops using native API tool_use/function_call structures
    instead of stringified text JSON blocks.
    Preserves all 10 Anara safety pillars:
    - AnaraLoopBreaker (cycle prevention)
    - TokenBudgetTracker (context window safety)
    - SelfCorrectionTracker & ErrorClassifier
    - Plan Mode Interception & Smart Command Safety
    - Parallel read-only tool execution (asyncio.gather)
    - Workspace Sentinel Ground-Truth Test Verification
    - ContextMicroCompactor & Head:Tail Output Compaction
    """
    from tools import dispatch_tool_call, READ_ONLY_TOOL_NAMES, get_tool_risk, AnaraLoopBreaker
    from tools.catalog import is_safe_read_only_cli_command
    from tools.output_manager import compact_tool_output
    from tools.self_correction import (
        AnaraLoopBreaker,
        ContextMicroCompactor,
        ErrorClassifier,
        SelfCorrectionTracker,
        format_recovery_guidance,
        format_graceful_diagnostic_card,
    )
    from core.token_budget import TokenBudgetTracker
    from core.convergence import ConvergenceDetector
    from .native_turn import NativeToolCall, NativeTurnResult

    loop_breaker = AnaraLoopBreaker(max_identical=4)
    self_correction_tracker = SelfCorrectionTracker(
        max_retries=5,
        max_identical_failures=5,
        warn_after_exact=2,
        interactive=True
    )
    token_tracker = TokenBudgetTracker(model_id=model_id)
    convergence_detector = ConvergenceDetector(read_only=read_only)

    history = list(initial_history)
    last_text = ""
    circuit_breaker_tripped = False
    budget_exhausted = False

    for step in range(max_steps):
        # Token Budget Management (Anara Standard: Gap 1 in Native Loop)
        token_tracker.record_step(step, history)

        # Mid-Turn In-Loop Context Compaction at 80% pressure (Anara Standard: conversation_compression.py)
        if step > 1 and token_tracker.usage_ratio(history) >= 0.80 and not getattr(token_tracker, "_compacted_in_loop", False):
            logger.info(f"[NativeAgentLoop] Token pressure at 80% ({token_tracker.usage_ratio(history):.0%}). Triggering in-loop context compaction...")
            token_tracker._compacted_in_loop = True
            if len(history) > 6:
                # Identify preserved prefix (system/developer message + initial user prompt)
                if isinstance(history[0], dict) and history[0].get("role") in ("system", "developer") and len(history) > 1:
                    prefix_count = 2
                else:
                    prefix_count = 1
                preserved_prefix = list(history[:prefix_count])

                cut_idx = max(prefix_count, len(history) - 4)
                while cut_idx > prefix_count:
                    item = history[cut_idx]
                    is_tool_res = False
                    if isinstance(item, dict):
                        if item.get("role") in ("tool", "function"):
                            is_tool_res = True
                        elif item.get("role") == "user" and isinstance(item.get("content"), list):
                            # Anthropic tool results are role: user with type: tool_result blocks
                            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in item.get("content")):
                                is_tool_res = True
                    elif hasattr(item, "parts") and any(getattr(p, "function_response", None) for p in getattr(item, "parts", [])):
                        is_tool_res = True
                    if not is_tool_res:
                        break
                    cut_idx -= 1

                tail = history[cut_idx:]
                middle = history[prefix_count:cut_idx]
                if middle:
                    summary_lines = []
                    for m in middle:
                        if isinstance(m, dict):
                            role = m.get("role", "assistant")
                            content = str(m.get("content", ""))[:120].replace("\n", " ")
                        else:
                            role = getattr(m, "role", "assistant")
                            content = str(getattr(m, "parts", ""))[:120].replace("\n", " ")
                        summary_lines.append(f"- [{role}]: {content}...")
                    compact_text = f"[SYSTEM CONTEXT COMPACTION]: Earlier intermediate execution steps ({len(middle)} turns) were summarized to preserve context budget:\n" + "\n".join(summary_lines)

                    # Merge compaction summary into initial user turn to prevent consecutive user turns and ensure strict role alternation
                    orig_user = preserved_prefix[-1]
                    if isinstance(orig_user, dict):
                        compacted_user = dict(orig_user)
                        orig_content = compacted_user.get("content", "")
                        if isinstance(orig_content, str):
                            compacted_user["content"] = f"{orig_content}\n\n{compact_text}"
                        elif isinstance(orig_content, list):
                            compacted_user["content"] = [*orig_content, {"type": "text", "text": f"\n\n{compact_text}"}]
                        history = [*preserved_prefix[:-1], compacted_user, *tail]
                    else:
                        from google.genai import types as genai_types
                        compacted_parts = list(getattr(orig_user, "parts", []))
                        compacted_parts.append(genai_types.Part.from_text(text=f"\n\n{compact_text}"))
                        compacted_user = genai_types.Content(role="user", parts=compacted_parts)
                        history = [*preserved_prefix[:-1], compacted_user, *tail]
                    logger.info(f"[NativeAgentLoop] In-loop compaction successfully compressed history to {len(history)} turns.")

        if step > 0 and token_tracker.is_budget_critical(history):
            logger.warning(
                f"[NativeAgentLoop] Token budget critical at step {step+1}: "
                f"{token_tracker.usage_ratio(history):.0%} of {token_tracker.input_budget:,} tokens consumed. "
                f"Forcing final narrative conclusion."
            )
            try:
                final_turn = await native_turn_caller(history)
                if final_turn and final_turn.clean_text:
                    final_text = _clean_model_chat_text(final_turn.clean_text) or final_turn.clean_text
                    if token_cb and final_text:
                        r = token_cb(final_text)
                        if asyncio.iscoroutine(r):
                            await r
                    return final_text
            except Exception:
                pass
            return _clean_model_chat_text(last_text) or last_text or _format_empty_model_notice(user_prompt)

        # Progress callback: thinking/reasoning
        if progress_cb:
            try:
                res_cb = progress_cb({
                    "tool_name": "agent",
                    "status": "thinking",
                    "step": step + 1,
                    "summary": "Reasoning & planning..." if read_only else "Reasoning & planning actions..."
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass

        # Call provider for single turn
        try:
            turn = await native_turn_caller(history)
        except Exception as e_call:
            from core.token_budget import parse_context_limit_from_error, save_context_length
            err_msg = str(e_call)
            parsed_limit = parse_context_limit_from_error(err_msg)
            if parsed_limit and parsed_limit < token_tracker.context_window:
                logger.warning(
                    f"[NativeAgentLoop] Discovered context limit ({parsed_limit:,} tokens) from provider error: {e_call}. "
                    f"Auto-updating context cache and compacting..."
                )
                save_context_length(model_id, parsed_limit)
                token_tracker.update_model_context(parsed_limit)
                token_tracker.compact_messages_if_needed(history)
                turn = await native_turn_caller(history)
            else:
                raise e_call

        if not isinstance(turn, NativeTurnResult):
            # If provider returned raw string or unexpected type, fallback
            return str(turn)

        last_text = turn.clean_text

        # If turn has NO tool calls, check Negative Verification Stop-Gate (Anara Standard: turn_stop_gates.py & Claude Code)
        if not turn.has_tool_calls:
            stop_gate_nudge = convergence_detector.evaluate_final_stop_gate(agent_mode="plan" if read_only else "build")
            if stop_gate_nudge and step < max_steps - 1:
                logger.info(f"[NativeAgentLoop] Stop-gate intercepted turn: verification tests required before reporting completion.")
                if history and not isinstance(history[0], dict):
                    from google.genai import types as genai_types
                    history.append(genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=turn.clean_text)]))
                    history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=stop_gate_nudge)]))
                else:
                    history.append({"role": "assistant", "content": turn.clean_text})
                    history.append({"role": "user", "content": stop_gate_nudge})
                continue

            final_text = _clean_model_chat_text(last_text) or last_text
            if not final_text:
                final_text = _format_empty_model_notice(user_prompt)
            if token_cb and final_text:
                res = token_cb(final_text)
                if asyncio.iscoroutine(res):
                    await res
            return final_text

        # Turn emitted native tool calls
        parsed_calls = []
        is_intercepted = False
        interception_result = None

        for call in turn.tool_calls:
            t_name = call.name
            t_args = call.arguments or {}

            # Loop Breaker check (Anara Enterprise Architecture: Stop infinite repetitive tool invocations)
            is_stalled, stall_msg = loop_breaker.record_and_check(t_name, t_args)
            if is_stalled and stall_msg:
                logger.warning(f"[NativeAgentLoop] LoopBreaker triggered on tool '{t_name}': {stall_msg}")
                parsed_calls.append({
                    "call": call,
                    "name": t_name,
                    "args": t_args,
                    "risk": "read_only",
                    "stall_error": stall_msg,
                })
                continue

            t_risk = get_tool_risk(t_name)
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                from core.plan_detector import smart_evaluate_command_safety
                t_risk = await smart_evaluate_command_safety(t_args.get("command", ""), description=user_prompt[:80])

            # Safety Interception:
            # 1. 'ask' tier (fatal commands: rm -rf /, format, drop db, bulk wipes) ALWAYS intercepts
            # 2. Plan Mode (intercept_mutating_tools=True) intercepts both 'mutating' and 'ask'
            should_intercept = (t_risk == "ask") or (intercept_mutating_tools and t_risk in ("mutating", "ask"))
            if should_intercept:
                logger.info(f"[NativeToolInterceptor] Intercepted tool '{t_name}' (risk={t_risk}) for Plan/Safety approval.")
                cmd_preview = t_args.get("command") or t_args.get("file_path") or t_args.get("title") or t_args.get("app") or ""
                is_intercepted = True
                interception_result = {
                    "intercepted": True,
                    "tool_name": t_name,
                    "tool_args": t_args,
                    "tool_risk": t_risk,
                    "cmd_preview": cmd_preview,
                    "lead_text": turn.clean_text,
                    "raw_call": call.to_dict(),
                }
                break

            parsed_calls.append({
                "call": call,
                "name": t_name,
                "args": t_args,
                "risk": t_risk,
            })

        if is_intercepted:
            return interception_result

        if not parsed_calls:
            continue

        # Multi-Tool Execution: Parallelize Read-Only calls via asyncio.gather, serialize Mutating calls
        results_by_index: Dict[int, Any] = {}
        call_idx = 0
        while call_idx < len(parsed_calls):
            if parsed_calls[call_idx]["risk"] == "read_only":
                end_idx = call_idx
                while end_idx < len(parsed_calls) and parsed_calls[end_idx]["risk"] == "read_only":
                    end_idx += 1
                ro_batch = parsed_calls[call_idx:end_idx]

                if progress_cb:
                    for item in ro_batch:
                        try:
                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "running",
                                "parallel": len(ro_batch) > 1,
                                "detail": str(item["args"].get("file_path") or item["args"].get("command") or item["args"].get("pattern") or "")
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass

                batch_results = await asyncio.gather(*[
                    asyncio.sleep(0, result={"status": "error", "error": item["stall_error"], "is_stalled": True})
                    if item.get("stall_error")
                    else dispatch_tool_call(item["name"], item["args"], read_only=read_only)
                    for item in ro_batch
                ])

                for offset_i, tool_res in enumerate(batch_results):
                    results_by_index[call_idx + offset_i] = tool_res
                    item = ro_batch[offset_i]
                    if progress_cb:
                        try:
                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "done",
                                "summary": (tool_res.get("message") or tool_res.get("summary") or "")[:160] if isinstance(tool_res, dict) else str(tool_res)[:160]
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass
                call_idx = end_idx
            else:
                item = parsed_calls[call_idx]
                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "running",
                            "detail": str(item["args"].get("file_path") or item["args"].get("command") or item["args"].get("title") or "")
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass

                is_safe_cli = (item["name"] == "execute_cli_command" and is_safe_read_only_cli_command(item["args"].get("command", "")))
                if read_only and item["name"] not in READ_ONLY_TOOL_NAMES and not is_safe_cli:
                    mut_res = {"status": "error", "message": f"Tool '{item['name']}' is disabled in Plan Mode (Read-Only)."}
                else:
                    mut_res = await dispatch_tool_call(item["name"], item["args"], read_only=read_only)
                results_by_index[call_idx] = mut_res

                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "done",
                            "summary": (mut_res.get("message") or mut_res.get("summary") or "")[:160] if isinstance(mut_res, dict) else str(mut_res)[:160]
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass
                call_idx += 1

        # Format and compact tool observations with Self-Correction & Micro-Compactor
        executed_results_for_history: List[Tuple[Any, str, bool]] = []
        turn_had_error = False
        last_err_str = ""

        for idx, item in enumerate(parsed_calls):
            call_obj: NativeToolCall = item["call"]
            tool_name: str = item["name"]
            tool_res = results_by_index.get(idx, {})

            if tool_name == "interactive_question" and isinstance(tool_res, dict) and tool_res.get("dismissed"):
                dismiss_notice = "Question dismissed."
                if token_cb:
                    res = token_cb(dismiss_notice)
                    if asyncio.iscoroutine(res):
                        await res
                return dismiss_notice

            res_str = json.dumps(tool_res, ensure_ascii=False) if not isinstance(tool_res, str) else tool_res

            is_tolerant = self_correction_tracker.is_failure_tolerant(tool_name)
            raw_err = isinstance(tool_res, dict) and (
                tool_res.get("status") in ("error", "failed")
                or tool_res.get("return_code", 0) != 0
                or tool_res.get("is_error") is True
            )
            is_err = raw_err and not is_tolerant

            # Ground-Truth Test Verification (Dynamic Language-Agnostic)
            if tool_name == "execute_cli_command":
                cmd_str = str(item["args"].get("command", "")).lower()
                from core.convergence import _is_verification_command
                if _is_verification_command(cmd_str):
                    from core.workspace_sentinel import workspace_sentinel
                    gt = workspace_sentinel.verify_ground_truth(res_str, tool_res.get("return_code", 0) if isinstance(tool_res, dict) else 0)
                    if not gt.get("verified"):
                        is_err = True

            loop_breaker.record_result(is_err)

            if is_err:
                turn_had_error = True
                compacted_err_str = ContextMicroCompactor.compact_output(res_str, max_lines=35, source_label=f"err_{tool_name}")
                last_err_str = compacted_err_str
                err_type, detail = ErrorClassifier.classify(compacted_err_str)

                target_arg = str(item["args"].get("command") or item["args"].get("file_path") or item["args"].get("query") or "")
                track_res = self_correction_tracker.register_attempt(
                    tool_name=tool_name,
                    command_or_arg=target_arg,
                    err_type=err_type or "execution_error",
                    detail=detail or "",
                )
                if track_res.get("is_stalled"):
                    circuit_breaker_tripped = True
                if track_res.get("budget_exhausted"):
                    budget_exhausted = True

                executed_results_for_history.append((call_obj, compacted_err_str, True))
            else:
                compacted_res_str = compact_tool_output(res_str, max_lines=60, max_chars=4000, source_label=f"caller_{tool_name}")
                executed_results_for_history.append((call_obj, compacted_res_str, False))

        # Circuit breaker check
        if circuit_breaker_tripped or (budget_exhausted and not self_correction_tracker.interactive):
            diag_card = format_graceful_diagnostic_card(
                history=self_correction_tracker.history,
                last_error_text=last_err_str,
                original_task=user_prompt
            )
            logger.warning("[NativeAgentLoop] Circuit breaker tripped on repeated identical stall. Delivering graceful diagnostic card.")
            if token_cb:
                res = token_cb(diag_card)
                if asyncio.iscoroutine(res):
                    await res
            return diag_card

        if not turn_had_error:
            self_correction_tracker.reset()

        # Convergence Tracking (Anara Enterprise Architecture: Gap 3)
        executed_items_for_convergence = []
        for idx, item in enumerate(parsed_calls):
            tool_res = results_by_index.get(idx, {})
            is_e = bool(isinstance(tool_res, dict) and (tool_res.get("status") in ("error", "failed") or tool_res.get("return_code", 0) != 0))
            executed_items_for_convergence.append({
                "tool_name": item["name"],
                "args": item["args"],
                "risk": item["risk"],
                "is_error": is_e,
                "summary": str(tool_res)[:200]
            })
        conv_status = convergence_detector.record_turn_actions(step, executed_items_for_convergence)

        # Append assistant turn and tool results to native history
        record_results_fn(history, turn, executed_results_for_history)

        if conv_status.is_converged:
            logger.info(f"[NativeAgentLoop] Trajectory converged (reason: {conv_status.reason}). Forcing final conclusion.")
            try:
                from core.prompt_loader import load_prompt
                closing_instruction = load_prompt("agent_loop/closing_narrative").strip()
                if history and not isinstance(history[0], dict):
                    from google.genai import types as genai_types
                    closing_history = [*history, genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=closing_instruction)])]
                else:
                    closing_history = [*history, {"role": "user", "content": closing_instruction}]
                final_turn = await native_turn_caller(closing_history)
                if final_turn and final_turn.clean_text:
                    final_text = _clean_model_chat_text(final_turn.clean_text) or final_turn.clean_text
                    if token_cb and final_text:
                        r = token_cb(final_text)
                        if asyncio.iscoroutine(r):
                            await r
                    return final_text
            except Exception as e_close:
                logger.warning(f"[NativeAgentLoop] Closing pass error: {e_close}")

            cleaned_last = _clean_model_chat_text(last_text)
            if cleaned_last:
                return cleaned_last
            return _format_empty_model_notice(user_prompt)

    cleaned_last = _clean_model_chat_text(last_text)
    if not cleaned_last:
        try:
            from core.prompt_loader import load_prompt
            closing_instruction = load_prompt("agent_loop/closing_narrative").strip()
            if history and not isinstance(history[0], dict):
                from google.genai import types as genai_types
                closing_history = [*history, genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=closing_instruction)])]
            else:
                closing_history = [*history, {"role": "user", "content": closing_instruction}]
            final_turn = await native_turn_caller(closing_history)
            if final_turn and final_turn.clean_text:
                return _clean_model_chat_text(final_turn.clean_text) or final_turn.clean_text
        except Exception:
            pass
    return cleaned_last or _format_empty_model_notice(user_prompt)


async def _execute_json_agent_loop(
    provider_caller: Callable[..., Awaitable[str]],
    user_prompt: str,
    system_instruction: str,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
    intercept_mutating_tools: bool = False,
    platform: Optional[str] = None,
    model_id: str = "",
) -> Any:
    """Universal multi-turn JSON tool loop for OpenAI Codex, Claude, and Custom Providers."""
    from tools import dispatch_tool_call, READ_ONLY_TOOL_NAMES, get_tool_risk, get_tools_catalog, AnaraLoopBreaker
    from tools.catalog import is_safe_read_only_cli_command
    from tools.toolsets import PlatformToolRegistry

    target_platform = platform or "web_studio"
    active_tool_names = set(PlatformToolRegistry.get_pruned_tools_for_execution(target_platform, user_task=user_prompt, read_only=read_only))
    catalog = get_tools_catalog(enabled_set=active_tool_names)
    tool_lines = []
    for t in catalog:
        if read_only and not t.get("is_read_only"):
            continue
        tool_lines.append(f"- '{t['name']}': {t.get('description', '')}")

    dynamic_catalog_str = "\n".join(tool_lines)

    from core.prompt_loader import load_prompt
    tool_spec_doc = "\n\n" + load_prompt(
        "agent_protocol",
        tool_count=len(tool_lines),
        dynamic_catalog_str=dynamic_catalog_str
    )
    
    messages = [
        {"role": "system", "content": f"{system_instruction}{tool_spec_doc}"},
        {"role": "user", "content": user_prompt}
    ]
    
    from tools.self_correction import (
        AnaraLoopBreaker,
        ContextMicroCompactor,
        ErrorClassifier,
        SelfCorrectionTracker,
        format_recovery_guidance,
        format_graceful_diagnostic_card,
    )
    loop_breaker = AnaraLoopBreaker(max_identical=4)
    self_correction_tracker = SelfCorrectionTracker(
        max_retries=5,
        max_identical_failures=5,
        warn_after_exact=2,
        interactive=True
    )

    # Token Budget Tracker (Hermes/Anara Standard: token-aware context management)
    from core.token_budget import TokenBudgetTracker
    from core.convergence import ConvergenceDetector
    token_tracker = TokenBudgetTracker(model_id=model_id)
    convergence_detector = ConvergenceDetector(read_only=read_only)

    last_response = ""
    empty_turn_retries = 0
    max_steps = 25
    for step in range(max_steps):
        # Token-aware context compaction (replaces old 24-message char-based heuristic)
        token_tracker.compact_messages_if_needed(messages)

        # Budget-critical stop: if >90% of context consumed, force final response
        if step > 0 and token_tracker.is_budget_critical(messages):
            logger.warning(
                f"[AgentLoop] Token budget critical at step {step+1}: "
                f"{token_tracker.usage_ratio(messages):.0%} of {token_tracker.input_budget:,} tokens consumed. "
                f"Forcing final narrative response."
            )
            messages.append({
                "role": "user",
                "content": load_prompt("agent_loop/budget_critical")
            })
            try:
                final_raw = await provider_caller(messages)
                if final_raw and final_raw.strip():
                    cleaned = _clean_model_chat_text(final_raw)
                    if cleaned and '"action": "tool_call"' not in cleaned:
                        return cleaned
            except Exception:
                pass
            break

        # Record step for diagnostics
        token_tracker.record_step(step, messages)

        # Mid-Turn In-Loop Context Compaction at 80% pressure (Anara Standard: conversation_compression.py)
        if step > 1 and token_tracker.usage_ratio(messages) >= 0.80 and not getattr(token_tracker, "_compacted_in_loop", False):
            logger.info(f"[AgentLoop] Token pressure at 80% ({token_tracker.usage_ratio(messages):.0%}). Triggering in-loop context compaction...")
            token_tracker._compacted_in_loop = True
            if len(messages) > 6:
                prefix_count = 2 if messages[0].get("role") in ("system", "developer") and len(messages) > 1 else 1
                preserved_prefix = list(messages[:prefix_count])
                cut_idx = max(prefix_count, len(messages) - 4)
                while cut_idx > prefix_count:
                    item = messages[cut_idx]
                    if item.get("role") not in ("tool", "function") and not (
                        item.get("role") == "user" and "[TOOL" in str(item.get("content", ""))
                    ):
                        break
                    cut_idx -= 1
                tail = messages[cut_idx:]
                middle = messages[prefix_count:cut_idx]
                if middle:
                    summary_lines = []
                    for m in middle:
                        role = m.get("role", "assistant")
                        content = str(m.get("content", ""))[:120].replace("\n", " ")
                        summary_lines.append(f"- [{role}]: {content}...")
                    compact_text = f"[SYSTEM CONTEXT COMPACTION]: Earlier intermediate execution steps ({len(middle)} turns) were summarized to preserve context budget:\n" + "\n".join(summary_lines)
                    orig_user = dict(preserved_prefix[-1])
                    orig_user["content"] = f"{orig_user.get('content', '')}\n\n{compact_text}"
                    messages = [*preserved_prefix[:-1], orig_user, *tail]
                    logger.info(f"[AgentLoop] In-loop compaction successfully compressed messages to {len(messages)} turns.")

        buffered_chunks = []
        is_tool_candidate = None  # None: undetermined, True: looks like JSON tool call, False: narrative streaming
        accumulated_narrative = []
        loop_scrubber = StreamingThinkScrubber()

        async def _chunk_dispatcher(delta: str):
            nonlocal is_tool_candidate
            if not delta:
                return

            if is_tool_candidate is False:
                accumulated_narrative.append(delta)
                if token_cb:
                    scrubbed = loop_scrubber.feed(delta)
                    if scrubbed:
                        res = token_cb(scrubbed)
                        if asyncio.iscoroutine(res):
                            await res
                return

            buffered_chunks.append(delta)
            joined = "".join(buffered_chunks)
            trimmed = joined.strip()

            if len(trimmed) < 7:
                if trimmed and not any(trimmed.startswith(p) for p in ["`", "{"]):
                    is_tool_candidate = False
                    for chunk_item in buffered_chunks:
                        accumulated_narrative.append(chunk_item)
                        if token_cb:
                            scrubbed = loop_scrubber.feed(chunk_item)
                            if scrubbed:
                                res = token_cb(scrubbed)
                                if asyncio.iscoroutine(res):
                                    await res
                return

            if trimmed.startswith("```json") or trimmed.startswith("```") or (trimmed.startswith("{") and ('"action"' in trimmed or '"tool"' in trimmed)):
                is_tool_candidate = True
            else:
                is_tool_candidate = False
                for chunk_item in buffered_chunks:
                    accumulated_narrative.append(chunk_item)
                    if token_cb:
                        scrubbed = loop_scrubber.feed(chunk_item)
                        if scrubbed:
                            res = token_cb(scrubbed)
                            if asyncio.iscoroutine(res):
                                await res

        if progress_cb:
            try:
                res_cb = progress_cb({
                    "tool_name": "agent",
                    "status": "thinking",
                    "step": step + 1,
                    "summary": "Analyzing & reasoning..." if read_only else "Reasoning & planning actions..."
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass

        try:
            try:
                raw_out = await provider_caller(messages, on_chunk=_chunk_dispatcher)
            except TypeError:
                raw_out = await provider_caller(messages)
        except Exception as e_call:
            from core.token_budget import parse_context_limit_from_error, save_context_length
            err_msg = str(e_call)
            parsed_limit = parse_context_limit_from_error(err_msg)
            if parsed_limit and parsed_limit < token_tracker.context_window:
                logger.warning(
                    f"[AgentLoop] Discovered context limit ({parsed_limit:,} tokens) from provider error: {e_call}. "
                    f"Auto-updating context cache and compacting..."
                )
                save_context_length(model_id, parsed_limit)
                token_tracker.update_model_context(parsed_limit)
                token_tracker.compact_messages_if_needed(messages)
                try:
                    raw_out = await provider_caller(messages, on_chunk=_chunk_dispatcher)
                except TypeError:
                    raw_out = await provider_caller(messages)
            else:
                raise e_call

        tail_scrub = loop_scrubber.flush()
        if tail_scrub and token_cb and is_tool_candidate is False:
            res = token_cb(tail_scrub)
            if asyncio.iscoroutine(res):
                await res

        if not raw_out or not raw_out.strip():
            # Hermes conversation_loop.py & turn_empty_response.py parity:
            # Ladder: 1) if empty/reasoning-only, nudge model up to 2 times to produce visible prose
            if empty_turn_retries < 2:
                empty_turn_retries += 1
                logger.info(f"[AgentLoop] Empty or thinking-only response detected (turn {step+1}). Nudging model continuation ({empty_turn_retries}/2)...")
                nudge_content = (
                    load_prompt("agent_loop/empty_turn_nudge_tool")
                    if (step > 0 and len(messages) >= 2 and "[TOOL" in messages[-1].get("content", ""))
                    else load_prompt("agent_loop/empty_turn_nudge_general")
                )
                messages.append({
                    "role": "user",
                    "content": nudge_content
                })
                continue
            break

        last_response = raw_out.strip()
        empty_turn_retries = 0
        
        calls, lead_text, is_malformed = _extract_and_parse_tool_calls(raw_out)

        if is_malformed:
            logger.warning(f"[AgentLoop] Malformed tool call syntax detected from model. Triggering autonomous self-correction loop...")
            messages.append({"role": "assistant", "content": raw_out})
            messages.append({
                "role": "user",
                "content": load_prompt("agent_loop/malformed_json")
            })
            continue

        if not calls:
            # Check Negative Verification Stop-Gate (Anara Standard: turn_stop_gates.py & Claude Code)
            stop_gate_nudge = convergence_detector.evaluate_final_stop_gate(agent_mode="plan" if read_only else "build")
            if stop_gate_nudge and step < max_steps - 1:
                logger.info(f"[AgentLoop] Stop-gate intercepted turn: verification tests required before reporting completion.")
                messages.append({"role": "assistant", "content": last_response})
                messages.append({"role": "user", "content": stop_gate_nudge})
                continue

            # Model responded with actual conversational narrative text!
            # Strip any leaked or orphaned tool tags before presenting to user (Anara Standard)
            cleaned_text = _clean_model_chat_text(last_response)
            # CRITICAL HERMES FIX: If text only contained tool calls or stray braces, invoke dynamic narrative synthesis pass
            if not cleaned_text or '"action": "tool_call"' in cleaned_text or '<tool_call>' in cleaned_text:
                try:
                    synth = await provider_caller([
                        *messages,
                        {"role": "assistant", "content": last_response},
                        {"role": "user", "content": load_prompt("agent_loop/narrative_synthesis").strip()}
                    ])
                    cleaned_text = _clean_model_chat_text(synth or "")
                except Exception:
                    pass
            final_text = cleaned_text or (last_response.strip() if '"action": "tool_call"' not in last_response else "")
            if not final_text:
                final_text = _format_empty_model_notice(user_prompt)
            if token_cb and not accumulated_narrative and final_text:
                res = token_cb(final_text)
                if asyncio.iscoroutine(res):
                    await res
            return final_text

        # Validate tools, check stalls, and handle Plan interception
        parsed_calls = []
        is_intercepted = False
        interception_result = None

        for call in calls:
            t_name = call.get("tool", "")
            t_args = call.get("arguments", {}) or {}

            # Anara Loop Breaker (Universal dynamic call fingerprinting & cycle prevention)
            is_stalled, stall_msg = loop_breaker.record_and_check(t_name, t_args)
            if is_stalled and stall_msg:
                logger.warning(f"[AgentLoop] LoopBreaker triggered on tool '{t_name}'")
                messages.append({"role": "assistant", "content": raw_out})
                messages.append({"role": "user", "content": stall_msg})
                parsed_calls = []
                break

            t_risk = get_tool_risk(t_name)
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                from core.plan_detector import smart_evaluate_command_safety
                t_risk = await smart_evaluate_command_safety(t_args.get("command", ""), description=user_prompt[:80])

            # Safety Interception:
            # 1. 'ask' tier (fatal commands: rm -rf /, format, drop db, bulk wipes) ALWAYS intercepts
            # 2. Plan Mode (intercept_mutating_tools=True) intercepts both 'mutating' and 'ask'
            should_intercept = (t_risk == "ask") or (intercept_mutating_tools and t_risk in ("mutating", "ask"))
            if should_intercept:
                logger.info(f"[ToolInterceptor JSON] Intercepted tool '{t_name}' (risk={t_risk}) for Plan/Safety approval.")
                cmd_preview = t_args.get("command") or t_args.get("file_path") or t_args.get("title") or t_args.get("app") or ""
                is_intercepted = True
                interception_result = {
                    "intercepted": True,
                    "tool_name": t_name,
                    "tool_args": t_args,
                    "tool_risk": t_risk,
                    "cmd_preview": cmd_preview,
                    "lead_text": lead_text,
                    "raw_call": call,
                }
                break

            parsed_calls.append({
                "name": t_name,
                "args": t_args,
                "risk": t_risk,
                "raw": call
            })

        if is_intercepted:
            return interception_result

        if not parsed_calls:
            continue

        # Multi-Tool Execution: Parallelize Read-Only calls via asyncio.gather, serialize Mutating calls
        results_by_index = {}
        call_idx = 0
        while call_idx < len(parsed_calls):
            if parsed_calls[call_idx]["risk"] == "read_only":
                end_idx = call_idx
                while end_idx < len(parsed_calls) and parsed_calls[end_idx]["risk"] == "read_only":
                    end_idx += 1
                ro_batch = parsed_calls[call_idx:end_idx]

                if progress_cb:
                    for item in ro_batch:
                        try:
                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "running",
                                "parallel": len(ro_batch) > 1,
                                "detail": str(item["args"].get("file_path") or item["args"].get("command") or item["args"].get("pattern") or "")
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass

                batch_results = await asyncio.gather(*[
                    dispatch_tool_call(item["name"], item["args"], read_only=read_only)
                    for item in ro_batch
                ])

                for offset_i, tool_res in enumerate(batch_results):
                    results_by_index[call_idx + offset_i] = tool_res
                    item = ro_batch[offset_i]
                    if progress_cb:
                        try:
                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "done",
                                "summary": (tool_res.get("message") or tool_res.get("summary") or "")[:160] if isinstance(tool_res, dict) else str(tool_res)[:160]
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass
                call_idx = end_idx
            else:
                item = parsed_calls[call_idx]
                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "running",
                            "detail": str(item["args"].get("file_path") or item["args"].get("command") or item["args"].get("title") or "")
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass

                is_safe_cli = (item["name"] == "execute_cli_command" and is_safe_read_only_cli_command(item["args"].get("command", "")))
                if read_only and item["name"] not in READ_ONLY_TOOL_NAMES and not is_safe_cli:
                    mut_res = {"status": "error", "message": f"Tool '{item['name']}' is disabled in Plan Mode (Read-Only)."}
                else:
                    mut_res = await dispatch_tool_call(item["name"], item["args"], read_only=read_only)
                results_by_index[call_idx] = mut_res

                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "done",
                            "summary": (mut_res.get("message") or mut_res.get("summary") or "")[:160] if isinstance(mut_res, dict) else str(mut_res)[:160]
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass
                call_idx += 1

        # Format and compact tool observations with Subsystem 4 Self-Correction & Micro-Compactor
        from tools.output_manager import compact_tool_output

        tool_result_blocks = []
        turn_had_error = False
        error_tool_names = []
        last_err_str = ""
        circuit_breaker_tripped = False
        budget_exhausted = False
        recovery_hints = []

        for idx, item in enumerate(parsed_calls):
            tool_name = item["name"]
            tool_res = results_by_index.get(idx, {})

            if tool_name == "interactive_question" and isinstance(tool_res, dict) and tool_res.get("dismissed"):
                dismiss_notice = "Question dismissed."
                if token_cb:
                    res = token_cb(dismiss_notice)
                    if asyncio.iscoroutine(res):
                        await res
                return dismiss_notice

            res_str = json.dumps(tool_res, ensure_ascii=False) if not isinstance(tool_res, str) else tool_res

            is_tolerant = self_correction_tracker.is_failure_tolerant(tool_name)
            raw_err = isinstance(tool_res, dict) and (
                tool_res.get("status") in ("error", "failed")
                or tool_res.get("return_code", 0) != 0
                or tool_res.get("is_error") is True
            )

            # Anara Standard: Exploratory tools (read_file, grep, glob, list_dir) returning "not found" or 0 matches
            # are observations, not system execution failures.
            is_err = raw_err and not is_tolerant

            # Ground-Truth Test Verification (Dynamic Language-Agnostic)
            if tool_name == "execute_cli_command":
                cmd_str = str(item["args"].get("command", "")).lower()
                from core.convergence import _is_verification_command
                if _is_verification_command(cmd_str):
                    from core.workspace_sentinel import workspace_sentinel
                    gt = workspace_sentinel.verify_ground_truth(res_str, tool_res.get("return_code", 0) if isinstance(tool_res, dict) else 0)
                    if not gt.get("verified"):
                        is_err = True
                        recovery_hints.append(f"\n[GROUND-TRUTH TEST VERIFICATION ALERT]: {gt.get('guidance')}")

            loop_breaker.record_result(is_err)

            if is_err:
                turn_had_error = True
                error_tool_names.append(tool_name)
                # Sniff error anchor & compact via ContextMicroCompactor (Pilar A)
                compacted_err_str = ContextMicroCompactor.compact_output(res_str, max_lines=35, source_label=f"err_{tool_name}")
                last_err_str = compacted_err_str
                err_type, detail = ErrorClassifier.classify(compacted_err_str)

                target_arg = str(item["args"].get("command") or item["args"].get("file_path") or item["args"].get("query") or "")
                track_res = self_correction_tracker.register_attempt(
                    tool_name=tool_name,
                    command_or_arg=target_arg,
                    err_type=err_type or "execution_error",
                    detail=detail or "",
                )
                if track_res.get("is_stalled"):
                    circuit_breaker_tripped = True
                if track_res.get("budget_exhausted"):
                    budget_exhausted = True

                if track_res.get("should_warn", True):
                    recovery_hints.append(format_recovery_guidance(
                        err_type=err_type,
                        detail=detail,
                        attempt=track_res["attempt"],
                        max_retries=self_correction_tracker.max_retries
                    ))
                tool_result_blocks.append(f"[TOOL ERROR for {tool_name}]:\n{compacted_err_str}")
            else:
                compacted_res_str = compact_tool_output(res_str, max_lines=60, max_chars=4000, source_label=f"caller_{tool_name}")
                prefix = "[TOOL OBSERVATION" if is_tolerant and raw_err else "[TOOL RESULT"
                tool_result_blocks.append(f"{prefix} for {tool_name}]:\n{compacted_res_str}")

        messages.append({"role": "assistant", "content": raw_out})

        # Graceful Root Cause Card Escalation (Pilar D — Anara Engineering Standards: Only on 5+ runaway identical stalls)
        if circuit_breaker_tripped or (budget_exhausted and not self_correction_tracker.interactive):
            diag_card = format_graceful_diagnostic_card(
                history=self_correction_tracker.history,
                last_error_text=last_err_str,
                original_task=user_prompt
            )
            logger.warning("[AgentLoop] Circuit breaker tripped on repeated identical stall. Delivering graceful diagnostic card.")
            if token_cb:
                res = token_cb(diag_card)
                if asyncio.iscoroutine(res):
                    await res
            return diag_card

        if not turn_had_error:
            self_correction_tracker.reset()

        # Convergence Tracking (Anara Enterprise Architecture: Gap 3)
        executed_items_for_convergence = []
        for idx, item in enumerate(parsed_calls):
            tool_res = results_by_index.get(idx, {})
            is_e = bool(isinstance(tool_res, dict) and (tool_res.get("status") in ("error", "failed") or tool_res.get("return_code", 0) != 0))
            executed_items_for_convergence.append({
                "tool_name": item["name"],
                "args": item["args"],
                "risk": item["risk"],
                "is_error": is_e,
                "summary": str(tool_res)[:200]
            })
        conv_status = convergence_detector.record_turn_actions(step, executed_items_for_convergence)

        if turn_had_error:
            guidance = "\n\n".join(recovery_hints)
        else:
            if conv_status.is_converged:
                logger.info(f"[AgentLoop] Trajectory converged (reason: {conv_status.reason}). Forcing closing pass.")
                guidance = f"\n\n{conv_status.guidance}"
            elif conv_status.should_nudge:
                guidance = f"\n\n{conv_status.guidance}"
            else:
                guidance = "\n\nProceed with the next required action, or provide your final response matching the user's active language if all steps are complete."

        combined_tool_feedback = "\n\n".join(tool_result_blocks) + guidance
        messages.append({
            "role": "user",
            "content": combined_tool_feedback
        })

        if conv_status.is_converged:
            break

        if progress_cb:
            try:
                res_cb = progress_cb({
                    "tool_name": "agent",
                    "status": "thinking",
                    "step": step + 2,
                    "summary": "Reasoning & planning..." if read_only else "Analyzing results & planning next action..."
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass
        
    # If the loop finished and last_response is STILL a tool call or stray bracket (Hermes Turn-Completion Enforcement):
    # Never return raw JSON tool call or stray bracket artifacts to the user!
    cleaned_last = _clean_model_chat_text(last_response)
    if '"action": "tool_call"' in last_response or '<tool_call>' in last_response or not cleaned_last:
        logger.info("[AgentLoop] Final turn terminated on unclosed tool call or missing narrative. Executing Hermes Closing Narrative Pass...")
        try:
            closing_prompt = [
                *messages,
                {
                    "role": "user",
                    "content": load_prompt("agent_loop/closing_narrative")
                }
            ]
            synth = await provider_caller(closing_prompt)
            if synth and synth.strip():
                cleaned_synth = _clean_model_chat_text(synth)
                if cleaned_synth and '"action": "tool_call"' not in cleaned_synth:
                    return cleaned_synth
                if synth.strip() and '"action": "tool_call"' not in synth:
                    return synth.strip()
        except Exception as e_synth:
            logger.warning(f"[AgentLoop] Closing narrative synthesis pass error: {e_synth}")

        if cleaned_last:
            return cleaned_last
        return _format_empty_model_notice(user_prompt)

    return cleaned_last or last_response


async def _make_gemini_raw_call(
    model_name: str,
    msgs: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    on_chunk: Optional[Callable[[str], Any]] = None,
) -> str:
    """OpenAI-to-Gemini raw provider adapter (Anara Agent gemini_native_adapter Parity)."""
    from core import key_manager
    from google.genai import types

    sys_msg = next((m["content"] for m in msgs if m["role"] == "system"), "")
    cfg_kwargs: Dict[str, Any] = {"temperature": temperature}
    if max_tokens is not None and max_tokens > 0:
        cfg_kwargs["max_output_tokens"] = max_tokens
    if sys_msg:
        cfg_kwargs["system_instruction"] = sys_msg.strip()
    config = types.GenerateContentConfig(**cfg_kwargs)

    contents = []
    for m in msgs:
        r = m.get("role", "")
        c = m.get("content", "")
        if r == "system":
            continue
        role = "user" if r == "user" else "model"
        if contents and contents[-1].role == role:
            contents[-1].parts.append(types.Part.from_text(text=c))
        else:
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=c)]))

    if not contents:
        contents = [types.Content(role="user", parts=[types.Part.from_text(text="Continue.")])]

    async def _exec(client):
        chunks = []
        try:
            stream = await client.aio.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            )
            async for chunk in stream:
                txt = chunk.text or ""
                if txt:
                    chunks.append(txt)
                    if on_chunk:
                        res = on_chunk(txt)
                        if asyncio.iscoroutine(res):
                            await res
            return "".join(chunks)
        except Exception:
            res = await client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=config,
            )
            txt = res.text or ""
            if on_chunk and txt:
                r = on_chunk(txt)
                if asyncio.iscoroutine(r):
                    await r
            return txt

    return await key_manager.execute_with_failover(_exec)


async def _make_gemini_native_turn(
    model_name: str,
    contents: List[Any],
    tools: List[Any],
    system_instruction: str = "",
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
    on_chunk: Optional[Callable[[str], Any]] = None,
) -> Any:
    """Executes a single native tool-calling turn via Google GenAI SDK (Hermes/Gemini Parity)."""
    from core import key_manager
    from google.genai import types
    from .native_turn import NativeToolCall, NativeTurnResult

    cfg_kwargs: Dict[str, Any] = {
        "temperature": temperature,
        "tools": tools,
    }
    if max_tokens is not None and max_tokens > 0:
        cfg_kwargs["max_output_tokens"] = max_tokens
    if system_instruction and system_instruction.strip():
        cfg_kwargs["system_instruction"] = system_instruction.strip()
    config = types.GenerateContentConfig(**cfg_kwargs)

    async def _exec(client):
        res = await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
        text_parts = []
        tool_calls = []

        if res.candidates and len(res.candidates) > 0:
            cand = res.candidates[0]
            if cand.content and cand.content.parts:
                for idx, part in enumerate(cand.content.parts):
                    if getattr(part, "text", None):
                        text_parts.append(part.text)
                        if on_chunk:
                            r = on_chunk(part.text)
                            if asyncio.iscoroutine(r):
                                await r
                    if getattr(part, "function_call", None):
                        fc = part.function_call
                        call_id = f"call_{fc.name}_{idx}"
                        args_dict = dict(fc.args) if fc.args else {}
                        tool_calls.append(NativeToolCall(
                            call_id=call_id,
                            name=fc.name,
                            arguments=args_dict
                        ))

        full_text = "".join(text_parts)
        cand_content = res.candidates[0].content if (res.candidates and res.candidates[0].content) else None
        finish_reason = None
        usage_res = None
        if res.candidates:
            finish_reason = getattr(res.candidates[0], "finish_reason", None)
            if finish_reason is not None:
                finish_reason = str(finish_reason)
        if hasattr(res, "usage_metadata") and res.usage_metadata:
            u = res.usage_metadata
            usage_res = {
                "prompt_tokens": getattr(u, "prompt_token_count", 0) or 0,
                "completion_tokens": getattr(u, "candidates_token_count", 0) or 0,
                "total_tokens": getattr(u, "total_token_count", 0) or 0,
            }
        return NativeTurnResult(
            text=full_text,
            tool_calls=tool_calls,
            raw_response=cand_content,
            finish_reason=finish_reason,
            usage=usage_res,
        )

    return await key_manager.execute_with_failover(_exec)


async def call_universal_chat_model(
    model_id: str,
    user_prompt: str,
    system_instruction: str = "",
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    read_only: bool = False,
    progress_cb: Optional[Callable[[Dict[str, Any]], Any]] = None,
    token_cb: Optional[Callable[[str], Any]] = None,
    intercept_mutating_tools: bool = False,
    platform: Optional[str] = None,
) -> Any:
    """
    Polymorphic universal model caller (Anara Standard).
    Dynamically resolves provider profile via ProfileRegistry and executes through the unified ReAct loop.
    Incorporates multi-tier fallback ladder if primary model is unavailable or encounters fatal failure.
    Zero static hardcoded model shortcuts: Open-Closed Principle compliant.
    """
    from .profile_registry import resolve_provider_profile
    from .accounts import get_fallback_model_id

    try:
        profile = resolve_provider_profile(model_id)
        return await profile.generate_chat(
            model_id=model_id,
            user_prompt=user_prompt,
            system_instruction=system_instruction,
            max_tokens=max_tokens,
            temperature=temperature,
            read_only=read_only,
            progress_cb=progress_cb,
            token_cb=token_cb,
            intercept_mutating_tools=intercept_mutating_tools,
            platform=platform,
        )
    except Exception as e_prim:
        fallback_model = get_fallback_model_id()
        if fallback_model and fallback_model != model_id:
            logger.warning(
                f"[ModelCaller] Primary model '{model_id}' failed ({e_prim}); engaging fallback ladder to '{fallback_model}'..."
            )
            try:
                fb_profile = resolve_provider_profile(fallback_model)
                return await fb_profile.generate_chat(
                    model_id=fallback_model,
                    user_prompt=user_prompt,
                    system_instruction=system_instruction,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    read_only=read_only,
                    progress_cb=progress_cb,
                    token_cb=token_cb,
                    intercept_mutating_tools=intercept_mutating_tools,
                    platform=platform,
                )
            except Exception as e_fb:
                logger.error(f"[ModelCaller] Fallback model '{fallback_model}' also failed: {e_fb}")
        raise e_prim
