import asyncio
import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional
import httpx
from config import cfg_get

from .accounts import (
    get_provider_key,
)
from .discovery import refresh_codex_oauth_token_if_needed

logger = logging.getLogger(__name__)


async def stream_universal_chat_model(
    model_id: str,
    user_prompt: str,
    system_instruction: str = "",
    max_tokens: Optional[int] = None,
    temperature: float = 0.7,
    usage_out: Optional[Dict[str, Any]] = None,
):
    """
    Async generator that streams model text chunks in real-time. Yields str fragments.
    Uncapped native generation by default — allows models to output full deep blueprints and code without artificial throttling.
    """
    if model_id.startswith("gemini") or model_id.startswith("gemma") or model_id.startswith("models/"):
        from core import key_manager
        from google import genai
        from google.genai import types
        gemini_model_name = model_id.replace("models/", "")
        if "live-preview" in gemini_model_name or "native-audio" in gemini_model_name:
            from core.capabilities import get_fast_auxiliary_model
            gemini_model_name = get_fast_auxiliary_model()
        cfg_kwargs: Dict[str, Any] = {
            "temperature": temperature,
        }
        if max_tokens is not None and max_tokens > 0:
            cfg_kwargs["max_output_tokens"] = max_tokens
        if system_instruction and system_instruction.strip():
            cfg_kwargs["system_instruction"] = system_instruction.strip()
        cfg = types.GenerateContentConfig(**cfg_kwargs)
        active_key = key_manager.get_active_key()
        if active_key:
            client = genai.Client(api_key=active_key)
            try:
                stream_res = client.aio.models.generate_content_stream(
                    model=gemini_model_name,
                    contents=user_prompt,
                    config=cfg,
                )
                async for chunk in await stream_res:
                    if chunk.text:
                        yield chunk.text
                    if usage_out is not None and hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        u = chunk.usage_metadata
                        p_t = getattr(u, "prompt_token_count", 0) or 0
                        c_t = getattr(u, "candidates_token_count", 0) or 0
                        usage_out["prompt_tokens"] = p_t
                        usage_out["completion_tokens"] = c_t
                        usage_out["total_tokens"] = p_t + c_t
                        usage_out["source"] = "actual"
                return
            except Exception as g_err:
                logger.warning(f"[Stream] Gemini streaming error, falling back: {g_err}")

    if model_id.startswith("codex/") or model_id.startswith("openai/"):
        from memory import memory_engine
        accounts = memory_engine.get_ai_accounts("codex") or memory_engine.get_ai_accounts("openai")
        keys_to_try = [a["api_key"] for a in accounts if a.get("api_key")]
        if not keys_to_try:
            k = get_provider_key("codex") or get_provider_key("openai")
            if k:
                keys_to_try.append(k)
        if not keys_to_try:
            return
        target_model = model_id.replace("codex/", "").replace("openai/", "")
        active_key = keys_to_try[0]
        acc_id = accounts[0]["id"] if accounts else None

        is_oauth_jwt = active_key.startswith("eyJ")

        if is_oauth_jwt:
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json",
                "originator": "codex_cli_rs",
                "User-Agent": "codex_cli_rs/0.136.0",
            }
            payload = {
                "model": target_model,
                "input": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    }
                ],
                "instructions": system_instruction,
                "store": False,
                "stream": True,
            }
            endpoint_url = "https://chatgpt.com/backend-api/codex/responses"
        else:
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": target_model,
                "stream": True,
                "stream_options": {"include_usage": True},
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
            }
            if max_tokens is not None and max_tokens > 0:
                payload["max_tokens"] = max_tokens
            if target_model.startswith("o1") or target_model.startswith("o3"):
                payload.pop("temperature", None)
                payload["messages"] = [
                    {"role": "user", "content": f"{system_instruction}\n\n{user_prompt}"}
                ]
                if "max_tokens" in payload:
                    payload["max_completion_tokens"] = payload.pop("max_tokens")
            endpoint_url = "https://api.openai.com/v1/chat/completions"

        gen_timeout = float(cfg_get("agent.generation.timeout", 45.0))
        try:
            async with httpx.AsyncClient(timeout=gen_timeout) as client:
                async with client.stream("POST", endpoint_url, headers=headers, json=payload) as response:
                    if response.status_code == 401 and is_oauth_jwt:
                        new_tok = await refresh_codex_oauth_token_if_needed(acc_id)
                        if new_tok:
                            headers["Authorization"] = f"Bearer {new_tok}"
                            async with client.stream("POST", endpoint_url, headers=headers, json=payload) as retry_res:
                                if retry_res.status_code == 200:
                                    async for line in retry_res.aiter_lines():
                                        if not line:
                                            continue
                                        data = line[5:].strip() if line.startswith("data:") else line.strip()
                                        if data == "[DONE]":
                                            break
                                        try:
                                            obj = json.loads(data)
                                            if usage_out is not None and obj.get("usage"):
                                                u = obj["usage"]
                                                usage_out["prompt_tokens"] = u.get("prompt_tokens", 0)
                                                usage_out["completion_tokens"] = u.get("completion_tokens", 0)
                                                usage_out["total_tokens"] = u.get("total_tokens", 0)
                                                usage_out["source"] = "actual"
                                            content = ""
                                            if obj.get("type") == "response.text.delta":
                                                content = obj.get("delta", "")
                                            elif obj.get("choices"):
                                                choice = obj["choices"][0] or {}
                                                content = (choice.get("delta") or {}).get("content", "") or choice.get("text", "")
                                            if content:
                                                yield content
                                        except json.JSONDecodeError:
                                            pass
                        return

                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            data = line[5:].strip() if line.startswith("data:") else line.strip()
                            if data == "[DONE]":
                                break
                            try:
                                obj = json.loads(data)
                                if usage_out is not None and obj.get("usage"):
                                    u = obj["usage"]
                                    usage_out["prompt_tokens"] = u.get("prompt_tokens", 0)
                                    usage_out["completion_tokens"] = u.get("completion_tokens", 0)
                                    usage_out["total_tokens"] = u.get("total_tokens", 0)
                                    usage_out["source"] = "actual"
                                content = ""
                                if obj.get("type") == "response.text.delta":
                                    content = obj.get("delta", "")
                                elif obj.get("choices"):
                                    choice = obj["choices"][0] or {}
                                    content = (choice.get("delta") or {}).get("content", "") or choice.get("text", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                pass
                        return
                    else:
                        logger.warning(f"[Stream] OpenAI Codex error HTTP {response.status_code}")
        except Exception as e:
            logger.warning(f"[Stream] OpenAI Codex stream error: {e}")

    # Fallback to full non-streaming call
    full = await call_universal_chat_model(
        model_id=model_id,
        user_prompt=user_prompt,
        system_instruction=system_instruction,
        max_tokens=max_tokens,
        temperature=temperature,
        read_only=False,
    )
    if full:
        yield full


def _robust_parse_json(candidate_str: str) -> Optional[Any]:
    """Attempts standard and fault-tolerant JSON deserialization with Windows path unescaping."""
    if not candidate_str or not candidate_str.strip():
        return None
    s = candidate_str.strip()

    # Attempt 1: Standard load
    try:
        return json.loads(s)
    except Exception:
        pass

    # Attempt 2: Dynamic repair for Windows unescaped backslashes and trailing commas
    try:
        def fix_quotes(m):
            val = m.group(1)
            def repl_backslash(bm):
                next_ch = bm.group(1)
                if next_ch in ['"', '\\', '/']:
                    return '\\' + next_ch
                return '/' + next_ch
            fixed = re.sub(r'\\(.)', repl_backslash, val)
            return f'"{fixed}"'

        repaired = re.sub(r'"((?:[^"\\]|\\.)*)"', fix_quotes, s)
        repaired = re.sub(r',\s*([\}\]])', r'\1', repaired)
        return json.loads(repaired)
    except Exception:
        pass

    # Attempt 3: Single quotes to double quotes repair
    try:
        repaired_sq = re.sub(r"'([^']+)'", r'"\1"', s)
        repaired_sq = re.sub(r',\s*([\}\]])', r'\1', repaired_sq)
        return json.loads(repaired_sq)
    except Exception:
        pass

    return None


def _sanitize_lead_narration(raw_lead: str) -> str:
    """
    Hermes Anti-Leak Sanitizer for narrative text:
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
    Hermes Agent Parity (agent/think_scrubber.py & gateway/stream_consumer_think.py):
    Strips inline <think>, <thought>, <reasoning>, and <REASONING_SCRATCHPAD> blocks,
    orphan tags, and bare thinking monologue preambles from model responses.
    """
    if not text:
        return ""
    # 1. Strip paired think / reasoning tags
    pattern = r"(?is)<(think|thought|reasoning|thinking|REASONING_SCRATCHPAD)\b[^>]*>[\s\S]*?</\1>"
    text = re.sub(pattern, "", text)
    # 2. Strip unclosed opening think tag at start of output
    text = re.sub(r"(?is)^<(think|thought|reasoning|thinking|REASONING_SCRATCHPAD)\b[^>]*>[\s\S]*?(?:(?=```)|$)", "", text)
    # 3. Strip orphan closing tags
    text = re.sub(r"(?i)</(?:think|thought|reasoning|thinking|REASONING_SCRATCHPAD)>", "", text)
    return text.strip()


def _clean_model_chat_text(raw_text: str) -> str:
    """
    Cleans model chat responses by removing markdown tool-call fences,
    bare JSON tool payloads, reasoning/think blocks, observation tags, and trailing punctuation/braces (Hermes Parity).
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
    if len(words) < 2:
        return ""

    return text


def _extract_json_balanced(text: str) -> List[tuple[str, int, int]]:
    """
    Deterministic bracket-balancing parser for JSON objects in text (Hermes Parity).
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
    Guarantees earliest-boundary lead text extraction with Hermes Anti-Leak Sanitization.
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
            # Deterministic Bracket-Balancing JSON extraction (Hermes Parity)
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
    Hermes & Claude Code Parity: Native Structured Tool Calling Agent Loop.
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
        # Token Budget Management (Hermes Parity: Gap 1 in Native Loop)
        token_tracker.record_step(step, history)

        # Mid-Turn In-Loop Context Compaction at 80% pressure (Hermes Parity: conversation_compression.py)
        if step > 1 and token_tracker.usage_ratio(history) >= 0.80 and not getattr(token_tracker, "_compacted_in_loop", False):
            logger.info(f"[NativeAgentLoop] Token pressure at 80% ({token_tracker.usage_ratio(history):.0%}). Triggering in-loop context compaction...")
            token_tracker._compacted_in_loop = True
            if len(history) > 6:
                head = history[0]
                tail = history[-4:]
                middle = history[1:-4]
                summary_lines = []
                for m in middle:
                    role = m.get("role", "assistant")
                    content = str(m.get("content", ""))[:120].replace("\n", " ")
                    summary_lines.append(f"- [{role}]: {content}...")
                compact_msg = {
                    "role": "user",
                    "content": f"[SYSTEM CONTEXT COMPACTION]: Earlier intermediate execution steps ({len(middle)} turns) were summarized to preserve context budget:\n" + "\n".join(summary_lines)
                }
                history = [head, compact_msg, *tail]
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
        turn = await native_turn_caller(history)
        if not isinstance(turn, NativeTurnResult):
            # If provider returned raw string or unexpected type, fallback
            return str(turn)

        last_text = turn.clean_text

        # If turn has NO tool calls, check Negative Verification Stop-Gate (Hermes Parity: turn_stop_gates.py & Claude Code)
        if not turn.has_tool_calls:
            stop_gate_nudge = convergence_detector.evaluate_final_stop_gate(agent_mode="plan" if read_only else "build")
            if stop_gate_nudge and step < max_steps - 1:
                logger.info(f"[NativeAgentLoop] Stop-gate intercepted turn: verification tests required before reporting completion.")
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

            # Loop Breaker check
            is_stalled, stall_msg = loop_breaker.record_and_check(t_name, t_args)
            if is_stalled and stall_msg:
                logger.warning(f"[NativeAgentLoop] LoopBreaker triggered on tool '{t_name}'")

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

            # Ground-Truth Test Verification
            if tool_name == "execute_cli_command":
                cmd_str = str(item["args"].get("command", "")).lower()
                if any(k in cmd_str for k in ("run_tests", "pytest", "npm test", "npm run test", "test_general_agent")):
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

        # Convergence Tracking (Hermes & Claude Code Parity: Gap 3)
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
                closing_history = [
                    *history,
                    {"role": "user", "content": closing_instruction}
                ]
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
            closing_history = [
                *history,
                {"role": "user", "content": closing_instruction}
            ]
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

    # Token Budget Tracker (Hermes/Claude Code Parity: token-aware context management)
    from core.token_budget import TokenBudgetTracker
    from core.convergence import ConvergenceDetector
    token_tracker = TokenBudgetTracker(model_id=model_id)
    convergence_detector = ConvergenceDetector(read_only=read_only)

    last_response = ""
    empty_turn_retries = 0
    for step in range(25):
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

        # Mid-Turn In-Loop Context Compaction at 80% pressure (Hermes Parity: conversation_compression.py)
        if step > 1 and token_tracker.usage_ratio(messages) >= 0.80 and not getattr(token_tracker, "_compacted_in_loop", False):
            logger.info(f"[AgentLoop] Token pressure at 80% ({token_tracker.usage_ratio(messages):.0%}). Triggering in-loop context compaction...")
            token_tracker._compacted_in_loop = True
            if len(messages) > 6:
                head = messages[0]
                tail = messages[-4:]
                middle = messages[1:-4]
                summary_lines = []
                for m in middle:
                    role = m.get("role", "assistant")
                    content = str(m.get("content", ""))[:120].replace("\n", " ")
                    summary_lines.append(f"- [{role}]: {content}...")
                compact_msg = {
                    "role": "user",
                    "content": f"[SYSTEM CONTEXT COMPACTION]: Earlier intermediate execution steps ({len(middle)} turns) were summarized to preserve context budget:\n" + "\n".join(summary_lines)
                }
                messages = [head, compact_msg, *tail]
                logger.info(f"[AgentLoop] In-loop compaction successfully compressed messages to {len(messages)} turns.")

        buffered_chunks = []
        is_tool_candidate = None  # None: undetermined, True: looks like JSON tool call, False: narrative streaming
        accumulated_narrative = []

        async def _chunk_dispatcher(delta: str):
            nonlocal is_tool_candidate
            if not delta:
                return

            if is_tool_candidate is False:
                accumulated_narrative.append(delta)
                if token_cb:
                    scrubbed = _strip_think_blocks("".join(accumulated_narrative))
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
                    accumulated_narrative.extend(buffered_chunks)
                    if token_cb:
                        scrubbed = _strip_think_blocks("".join(accumulated_narrative))
                        if scrubbed:
                            res = token_cb(scrubbed)
                            if asyncio.iscoroutine(res):
                                await res
                return

            if trimmed.startswith("```json") or trimmed.startswith("```") or (trimmed.startswith("{") and ('"action"' in trimmed or '"tool"' in trimmed)):
                is_tool_candidate = True
            else:
                is_tool_candidate = False
                accumulated_narrative.extend(buffered_chunks)
                if token_cb:
                    scrubbed = _strip_think_blocks("".join(accumulated_narrative))
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
            raw_out = await provider_caller(messages, on_chunk=_chunk_dispatcher)
        except TypeError:
            raw_out = await provider_caller(messages)

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
            # Check Negative Verification Stop-Gate (Hermes Parity: turn_stop_gates.py & Claude Code)
            stop_gate_nudge = convergence_detector.evaluate_final_stop_gate(agent_mode="plan" if read_only else "build")
            if stop_gate_nudge and step < max_steps - 1:
                logger.info(f"[AgentLoop] Stop-gate intercepted turn: verification tests required before reporting completion.")
                messages.append({"role": "assistant", "content": last_response})
                messages.append({"role": "user", "content": stop_gate_nudge})
                continue

            # Model responded with actual conversational narrative text!
            # Strip any leaked or orphaned tool tags before presenting to user (Hermes parity)
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

            # Hermes Parity: Exploratory tools (read_file, grep, glob, list_dir) returning "not found" or 0 matches
            # are observations, not system execution failures.
            is_err = raw_err and not is_tolerant

            # Ground-Truth Test Verification (Hermes Parity Subsystem 5)
            if tool_name == "execute_cli_command":
                cmd_str = str(item["args"].get("command", "")).lower()
                if any(k in cmd_str for k in ("run_tests", "pytest", "npm test", "npm run test", "test_general_agent")):
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

        # Graceful Root Cause Card Escalation (Pilar D — Hermes Standard: Only on 5+ runaway identical stalls)
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

        # Convergence Tracking (Hermes & Claude Code Parity: Gap 3)
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
    """OpenAI-to-Gemini raw provider adapter (Hermes Agent gemini_native_adapter Parity)."""
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
        return NativeTurnResult(
            text=full_text,
            tool_calls=tool_calls,
            raw_response=cand_content,
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
    Polymorphic universal model caller (Hermes Agent Parity).
    Dynamically resolves provider profile via ProfileRegistry and executes through the unified ReAct loop.
    Zero hardcoded if-else model branching: Open-Closed Principle compliant.
    """
    from .profile_registry import resolve_provider_profile

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
