"""
agent_loops.py — Structured & JSON Agent Execution Loops for Project Anara.
Implements the multi-turn tool loops with LoopBreaker, TokenBudgetTracker,
SelfCorrectionTracker, Plan Mode Interception, and Parallel Tool Execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Set

from providers.payload_parser import (
    _robust_parse_json,
    _sanitize_lead_narration,
    _format_empty_model_notice,
    _strip_think_blocks,
    _clean_model_chat_text,
    _extract_json_balanced,
    _extract_and_parse_tool_calls,
    _extract_and_parse_tool_call,
    _build_closing_history,
)
from providers.think_scrubber import StreamingThinkScrubber
from providers.native_turn import NativeToolCall, NativeTurnResult
from core.action_rationale import generate_dynamic_action_rationale
from core.prompt_loader import load_prompt

logger = logging.getLogger('anara.agent_loops')

async def _execute_native_agent_loop(
    native_turn_caller: Callable[..., Awaitable[Any]],
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
    from tools import dispatch_tool_call, READ_ONLY_TOOL_NAMES, get_tool_risk
    from tools.catalog import is_safe_read_only_cli_command
    from tools.output_manager import compact_tool_output
    from tools.self_correction import (
        AnaraLoopBreaker,
        ContextMicroCompactor,
        ErrorClassifier,
        SelfCorrectionTracker,
        format_graceful_diagnostic_card,
    )
    from core.token_budget import TokenBudgetTracker
    from core.convergence import ConvergenceDetector
    from .native_turn import NativeToolCall, NativeTurnResult

    streamed_chars = [0]
    orig_token_cb = token_cb
    if orig_token_cb:
        def _counting_token_cb(chunk: str):
            if chunk:
                streamed_chars[0] += len(chunk)
                return orig_token_cb(chunk)
        token_cb = _counting_token_cb

    loop_breaker = AnaraLoopBreaker(max_identical=4)
    self_correction_tracker = SelfCorrectionTracker(
        max_retries=5,
        max_identical_failures=5,
        warn_after_exact=2,
        interactive=True
    )
    token_tracker = TokenBudgetTracker(model_id=model_id)
    convergence_detector = ConvergenceDetector(read_only=read_only)

    from providers.turn_pipeline import LoopPhaseState, TurnPhasePipeline
    history = list(initial_history)
    last_text = ""
    circuit_breaker_tripped = False
    budget_exhausted = False

    for step in range(max_steps):
        # Anara Standard Turn Preflight Gate & In-Flight Steering (turn_pipeline)
        loop_state = LoopPhaseState(
            step=step,
            max_steps=max_steps,
            read_only=read_only,
            model_id=model_id,
            history=history,
        )
        TurnPhasePipeline.run_preflight_and_steering(loop_state, token_tracker)

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
                try:
                    final_turn = await native_turn_caller(history, allow_tools=False)
                except TypeError:
                    final_turn = await native_turn_caller(history)
                if final_turn and final_turn.clean_text:
                    return _clean_model_chat_text(final_turn.clean_text) or final_turn.clean_text
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
            from core.image_eviction import evict_historical_images
            if isinstance(history, list) and history and isinstance(history[0], dict):
                history, _ = evict_historical_images(history)
        except Exception:
            pass

        # Transcript Repair & Sanitization Gate (Anara Standard: transcript_repair.py)
        try:
            from core.transcript_repair import repair_transcript_sequence
            if isinstance(history, list) and history and isinstance(history[0], dict):
                history = repair_transcript_sequence(history)
        except Exception as e_repair:
            logger.debug(f"[NativeAgentLoop] Transcript repair notice: {e_repair}")

        try:
            turn = await native_turn_caller(history)
        except Exception as e_call:
            from core.stream_rules import StreamRuleViolation
            if isinstance(e_call, StreamRuleViolation):
                logger.warning(f"[NativeAgentLoop] TTSR hard-aborted stream: {e_call.rule_name}. Course-correcting...")
                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "type": "ttsr_intervention",
                            "rule": e_call.rule_name,
                            "message": e_call.message,
                            "matched_text": e_call.matched_text,
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass
                intervention_prompt = f"[STREAM RULE INTERVENTION]: {e_call.message}"
                if history and not isinstance(history[0], dict):
                    from google.genai import types as genai_types
                    history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=intervention_prompt)]))
                else:
                    history.append({"role": "user", "content": intervention_prompt})
                continue

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

        # If turn has NO tool calls, check Negative Verification Stop-Gate (Anara Standard: turn_stop_gates.py & Anara Agent Protocol)
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

            # Anti-Fabrication & Tool-Use Enforcement Stop Gate (Anara Standard)
            simulated_execution = None
            if not read_only:
                simulated_execution = re.search(
                    r"\*(?:\((?:sedang |mulai |mencoba )?(?:menjalankan|mengeksekusi|eksekusi|executing|running)\s+(?:perintah|command|tool|skrip|script)[^\)]*\)|\b(?:menjalankan|mengeksekusi|eksekusi|executing|running)\s+(?:perintah|command|tool|skrip|script)\b[^\*]+)\*",
                    turn.clean_text,
                    flags=re.IGNORECASE
                )
            if simulated_execution and step < max_steps - 1:
                logger.warning(f"[NativeAgentLoop] Simulated execution detected without tool call: {simulated_execution.group(0)}")
                enforcement_nudge = (
                    "[TOOL USE ENFORCEMENT]: You described or simulated an action in text/parentheses instead of invoking the real tool. "
                    "You MUST make the actual tool call (e.g. execute_cli_command, process_manage, computer_use) to perform the action. "
                    "Do not roleplay or simulate execution in text."
                )
                if history and not isinstance(history[0], dict):
                    from google.genai import types as genai_types
                    history.append(genai_types.Content(role="model", parts=[genai_types.Part.from_text(text=turn.clean_text)]))
                    history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=enforcement_nudge)]))
                else:
                    history.append({"role": "assistant", "content": turn.clean_text})
                    history.append({"role": "user", "content": enforcement_nudge})
                continue

            final_text = _clean_model_chat_text(last_text) or last_text
            if not final_text:
                # Anara Standard: Thinking-Only Response Auto-Nudge (empty_response_guard.py)
                raw_check = getattr(turn, "raw_text", "") or ""
                if step < max_steps - 1 and (
                    "<think>" in raw_check.lower()
                    or "<thought>" in raw_check.lower()
                    or "<reasoning>" in raw_check.lower()
                    or getattr(turn, "thought", "")
                ):
                    logger.info("[NativeAgentLoop] Model emitted thinking scratchpad with zero visible prose. Engaging Anara Standard auto-nudge...")
                    thinking_nudge = (
                        "[System Notice]: You completed your internal reasoning thoughts but provided no visible final response text. "
                        "Please synthesize and output your final response to the user now based on your reasoning above."
                    )
                    if history and not isinstance(history[0], dict):
                        from google.genai import types as genai_types
                        history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=thinking_nudge)]))
                    else:
                        history.append({"role": "user", "content": thinking_nudge})
                    continue
                final_text = _format_empty_model_notice(user_prompt)
            return final_text

        # Emit interim commentary if the model spoke before invoking tools
        if turn.clean_text and progress_cb:
            try:
                res_cb = progress_cb({
                    "type": "interim_text",
                    "text": _clean_model_chat_text(turn.clean_text) or turn.clean_text,
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass

        # Turn emitted native tool calls
        # Anara Standard: Parallel Tool ID Uniquification & Mixed Batch Validation
        from core.transcript_repair import uniquify_tool_call_ids, validate_and_filter_tool_batch
        uniquify_tool_call_ids(turn.tool_calls)

        from tools import get_tools_catalog
        all_catalog = get_tools_catalog()
        valid_tool_names = set(t["name"] for t in all_catalog if t.get("name"))

        executable_calls, invalid_batch_errors = validate_and_filter_tool_batch(turn.tool_calls, valid_tool_names)

        parsed_calls = []
        is_intercepted = False
        interception_result = None

        for call in executable_calls:
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

            # ── Anara Approval Engine (Native Loop) ────────────────────────
            from config import cfg_get
            from core.approval_guard import check_command_safety, normalize_approval_mode
            approval_mode = normalize_approval_mode(cfg_get("approvals.mode", "auto"))
            _danger_desc = ""

            # Hardline safety floor: blocks catastrophic commands even in Off/YOLO mode
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                cmd_text = t_args.get("command", "")
                safety_result = check_command_safety(cmd_text, approval_mode)
                if safety_result and safety_result.get("hardline"):
                    logger.warning(f"[HARDLINE FLOOR] Blocked '{t_name}': {safety_result['reason']}")
                    is_intercepted = True
                    interception_result = {
                        "intercepted": True,
                        "hardline_blocked": True,
                        "tool_name": t_name,
                        "tool_args": t_args,
                        "tool_risk": "hardline",
                        "reason": safety_result["reason"],
                        "cmd_preview": cmd_text[:200],
                        "lead_text": turn.clean_text,
                        "raw_call": call.to_dict(),
                    }
                    break
                elif safety_result and safety_result.get("needs_approval"):
                    t_risk = "ask"
                    _danger_desc = safety_result.get("description", "")

            # Approval gate by canonical mode: auto, plan, off
            if intercept_mutating_tools and t_risk in ("mutating", "ask"):
                should_intercept = True
            elif approval_mode == "auto" and t_risk in ("mutating", "ask"):
                if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                    try:
                        from core.approval_smart import smart_approve
                        cmd_text = t_args.get("command", "")
                        danger_ctx = f"tool={t_name}, risk={t_risk}"
                        if _danger_desc:
                            danger_ctx += f", pattern_match={_danger_desc}"
                        verdict = await smart_approve(cmd_text, danger_ctx)
                        if verdict == "approve":
                            logger.info(f"[SmartApproval] Auto-approved '{t_name}': guardian verdict=APPROVE")
                            should_intercept = False
                        elif verdict == "deny":
                            logger.info(f"[SmartApproval] Denied '{t_name}': guardian verdict=DENY")
                            should_intercept = True
                        else:
                            logger.info(f"[SmartApproval] Escalating '{t_name}': guardian verdict=ESCALATE")
                            should_intercept = True
                    except Exception as e:
                        logger.warning(f"[SmartApproval] Guardian failed: {e}, escalating to manual")
                        should_intercept = True
                else:
                    should_intercept = (t_risk == "ask")
            elif approval_mode == "off":
                should_intercept = False
            elif approval_mode == "plan":
                should_intercept = t_risk in ("mutating", "ask")
            else:
                should_intercept = (t_risk == "ask") or (intercept_mutating_tools and t_risk in ("mutating", "ask"))

            if should_intercept:
                logger.info(f"[NativeToolInterceptor] Intercepted tool '{t_name}' (risk={t_risk}, mode={approval_mode}) for Plan/Safety approval.")
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

        # Append synthetic error observations for invalid/hallucinated tools in parallel batch
        for err_dict in invalid_batch_errors:
            err_name = err_dict.get("name", "unknown_tool")
            err_cid = err_dict.get("tool_call_id", "")
            err_call_obj = next((c for c in turn.tool_calls if getattr(c, "id", "") == err_cid or getattr(c, "name", "") == err_name), None)
            parsed_calls.append({
                "call": err_call_obj or NativeToolCall(call_id=err_cid, name=err_name, arguments={}),
                "name": err_name,
                "args": {},
                "risk": "read_only",
                "stall_error": err_dict["content"],
            })

        if not parsed_calls:
            continue

        # Multi-Tool Execution: Parallelize Read-Only calls via asyncio.gather, serialize Mutating calls
        results_by_index: Dict[int, Any] = {}
        call_idx = 0
        while call_idx < len(parsed_calls):
            ro_batch, next_idx, is_ro_batch = TurnPhasePipeline.partition_tool_batch(parsed_calls, call_idx)
            if is_ro_batch:
                if progress_cb:
                    for item in ro_batch:
                        try:
                            t_args = item.get("args") or {}
                            detail_str = str(
                                t_args.get("query")
                                or t_args.get("file_path")
                                or t_args.get("command")
                                or t_args.get("url")
                                or t_args.get("pattern")
                                or t_args.get("path")
                                or t_args.get("title")
                                or ""
                            )
                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "running",
                                "parallel": len(ro_batch) > 1,
                                "detail": detail_str,
                                "tool_args": t_args,
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
                ], return_exceptions=True)

                for offset_i, raw_res in enumerate(batch_results):
                    if isinstance(raw_res, BaseException):
                        tool_res = {"status": "error", "error": str(raw_res), "output": f"Unhandled tool execution error: {raw_res}"}
                    else:
                        tool_res = raw_res
                    results_by_index[call_idx + offset_i] = tool_res
                    item = ro_batch[offset_i]
                    if progress_cb:
                        try:
                            t_args = item.get("args") or {}
                            detail_str = str(
                                t_args.get("query")
                                or t_args.get("file_path")
                                or t_args.get("command")
                                or t_args.get("url")
                                or t_args.get("pattern")
                                or t_args.get("path")
                                or t_args.get("title")
                                or ""
                            )
                            summary_str = ""
                            raw_str = ""
                            if isinstance(tool_res, dict):
                                summary_str = str(
                                    tool_res.get("summary")
                                    or tool_res.get("message")
                                    or tool_res.get("search_results")
                                    or tool_res.get("output")
                                    or tool_res.get("result")
                                    or tool_res.get("content")
                                    or ""
                                )
                                raw_str = str(
                                    tool_res.get("raw_result")
                                    or tool_res.get("search_results")
                                    or tool_res.get("output")
                                    or tool_res.get("result")
                                    or tool_res.get("content")
                                    or summary_str
                                )
                            else:
                                summary_str = str(tool_res)
                                raw_str = str(tool_res)

                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "done",
                                "summary": summary_str[:160] if summary_str else "Done",
                                "detail": detail_str,
                                "raw_result": raw_str,
                                "tool_args": t_args,
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass
                call_idx = next_idx
            else:
                item = parsed_calls[call_idx]
                t_args = item.get("args") or {}
                detail_str = str(
                    t_args.get("query")
                    or t_args.get("file_path")
                    or t_args.get("command")
                    or t_args.get("url")
                    or t_args.get("pattern")
                    or t_args.get("path")
                    or t_args.get("title")
                    or ""
                )
                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "running",
                            "detail": detail_str,
                            "tool_args": t_args,
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
                        summary_str = ""
                        raw_str = ""
                        if isinstance(mut_res, dict):
                            summary_str = str(
                                mut_res.get("summary")
                                or mut_res.get("message")
                                or mut_res.get("search_results")
                                or mut_res.get("output")
                                or mut_res.get("result")
                                or mut_res.get("content")
                                or ""
                            )
                            raw_str = str(
                                mut_res.get("raw_result")
                                or mut_res.get("search_results")
                                or mut_res.get("output")
                                or mut_res.get("result")
                                or mut_res.get("content")
                                or summary_str
                            )
                        else:
                            summary_str = str(mut_res)
                            raw_str = str(mut_res)

                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "done",
                            "summary": summary_str[:160] if summary_str else "Done",
                            "detail": detail_str,
                            "raw_result": raw_str,
                            "tool_args": t_args,
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
            has_lint_err = bool(isinstance(tool_res, dict) and tool_res.get("lint_warning"))
            raw_err = (
                isinstance(tool_res, dict) and (
                    tool_res.get("status") in ("error", "failed")
                    or tool_res.get("return_code", 0) != 0
                    or tool_res.get("is_error") is True
                )
            ) or has_lint_err
            is_err = raw_err and not is_tolerant

            if has_lint_err and isinstance(tool_res, dict):
                lint_msg = tool_res.get("lint_warning")
                fname = tool_res.get("filename") or tool_name
                repair_prompt = (
                    f"\n\n[COMPILER SELF-REPAIR GUARD]: File '{fname}' contains a syntax regression: {lint_msg}.\n"
                    f"You MUST immediately repair this syntax error in your next action using edit_file (Hashline PUT/SWAP). Do not close your response or leave broken syntax."
                )
                res_str += repair_prompt

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
                compacted_res_str = loop_breaker.check_or_stub_duplicate(tool_name, item["args"], compacted_res_str)
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

        # Reset retry budget only when mutating operations succeed (actual progress was made),
        # preserving failure memory during passive/read-only operations to prevent ping-pong loops
        if not turn_had_error:
            has_mutating = any(item.get("risk") in ("mutating", "ask") for item in parsed_calls)
            if has_mutating:
                self_correction_tracker.reset()
                loop_breaker.notify_mutation()

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

        # Inject convergence nudge into the last tool result if model needs guidance
        if conv_status.should_nudge and conv_status.guidance and executed_results_for_history:
            last_call, last_out, last_err = executed_results_for_history[-1]
            nudged_out = f"{last_out}\n\n[System Guidance]: {conv_status.guidance}"
            executed_results_for_history[-1] = (last_call, nudged_out, last_err)

        # Append assistant turn and tool results to native history
        record_results_fn(history, turn, executed_results_for_history)

        # In-Process Compiler Repair Gate: If any tool in the turn introduced a syntax regression, do not converge!
        has_active_syntax_error = any(
            isinstance(results_by_index.get(i), dict) and results_by_index[i].get("lint_warning")
            for i in range(len(parsed_calls))
        )
        if has_active_syntax_error:
            logger.info("[NativeAgentLoop] Active syntax regression detected: withholding convergence to force immediate self-repair.")
            conv_status.is_converged = False

        if conv_status.is_converged:
            # Active Build Turn Protection: If the turn allows mutations (not read_only)
            # and no mutations have been performed yet, do not strip tools unless near step limit!
            if not read_only and convergence_detector.mutations_count == 0 and step < max_steps - 3:
                logger.info(f"[NativeAgentLoop] Build mode with 0 mutations: preserving tools and nudging model to implement (reason={conv_status.reason}).")
            else:
                logger.info(f"[NativeAgentLoop] Trajectory converged (reason: {conv_status.reason}). Forcing final conclusion.")
                try:
                    from core.prompt_loader import load_prompt
                    closing_instruction = load_prompt(
                        "agent_loop/closing_narrative",
                        default="Based on all the work, observations, and attachments above, provide a clear, helpful, and complete final response to the user in natural conversational prose matching the active language."
                    ).strip()
                    closing_history = _build_closing_history(history, closing_instruction)
                    try:
                        final_turn = await native_turn_caller(closing_history, allow_tools=False)
                    except TypeError:
                        final_turn = await native_turn_caller(closing_history)
                    if final_turn and final_turn.clean_text:
                        return _clean_model_chat_text(final_turn.clean_text) or final_turn.clean_text
                except Exception as e_close:
                    logger.warning(f"[NativeAgentLoop] Closing pass error: {e_close}")

                cleaned_last = _clean_model_chat_text(last_text)
                if cleaned_last:
                    return cleaned_last

                # High-assurance conversational fallback: synthesize response via fast auxiliary model
                try:
                    from core.capabilities import get_fast_auxiliary_model
                    from .caller import call_universal_chat_model
                    aux_model = get_fast_auxiliary_model() or model_id
                    highlights = "\n".join([f"- {item.get('tool_name', 'action')}: {str(item.get('summary', ''))[:140]}" for item in executed_items_for_convergence[-10:]])
                    synthesis_prompt = TurnPhasePipeline.build_synthesis_prompt(user_prompt, highlights)
                    fallback_res = await call_universal_chat_model(
                        model_id=aux_model,
                        user_prompt=synthesis_prompt,
                        max_tokens=None,
                        temperature=0.3,
                        read_only=True
                    )
                    cleaned_fallback = _clean_model_chat_text(fallback_res or "")
                    if cleaned_fallback:
                        return cleaned_fallback
                except Exception as e_synth:
                    logger.debug(f"[NativeAgentLoop] Auxiliary synthesis fallback failed: {e_synth}")

            return _format_empty_model_notice(user_prompt)

    cleaned_last = _clean_model_chat_text(last_text)
    if not cleaned_last:
        try:
            from core.prompt_loader import load_prompt
            closing_instruction = load_prompt(
                "agent_loop/closing_narrative",
                default="Based on all the work, observations, and attachments above, provide a clear, helpful, and complete final response to the user in natural conversational prose matching the active language."
            ).strip()
            closing_history = _build_closing_history(history, closing_instruction)
            try:
                final_turn = await native_turn_caller(closing_history, allow_tools=False)
            except TypeError:
                final_turn = await native_turn_caller(closing_history)
            if final_turn and final_turn.clean_text:
                return _clean_model_chat_text(final_turn.clean_text) or final_turn.clean_text
        except Exception:
            pass

        # High-assurance conversational fallback
        try:
            from core.capabilities import get_fast_auxiliary_model
            from .caller import call_universal_chat_model
            aux_model = get_fast_auxiliary_model() or model_id
            synthesis_prompt = (
                f"User asked: \"{user_prompt}\"\n\n"
                "The agent completed workspace actions and observations. Provide a direct, helpful, and natural response "
                "to the user in their active language, summarizing what was checked or asking for clarification if needed."
            )
            fallback_res = await call_universal_chat_model(
                model_id=aux_model,
                user_prompt=synthesis_prompt,
                max_tokens=None,
                temperature=0.3,
                read_only=True
            )
            cleaned_fallback = _clean_model_chat_text(fallback_res or "")
            if cleaned_fallback:
                return cleaned_fallback
        except Exception as e_synth:
            logger.debug(f"[NativeAgentLoop] Auxiliary synthesis fallback failed: {e_synth}")

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

    # Token Budget Tracker (Anara Standard: token-aware context management)
    from core.token_budget import TokenBudgetTracker
    from core.convergence import ConvergenceDetector
    token_tracker = TokenBudgetTracker(model_id=model_id)
    convergence_detector = ConvergenceDetector(read_only=read_only)

    last_response = ""
    empty_turn_retries = 0
    max_steps = 25
    for step in range(max_steps):
        # Anara Standard Turn Preflight Gate (turn_preflight_gate.py)
        token_tracker.run_preflight_gate(messages, tool_schemas=catalog)

        # Pi Parity: In-Flight Dual-Queue Steering Directive Injection
        try:
            from core.session_manager import session_state_manager
            from core.channel_adapter import _ACTIVE_CHANNEL_CONTEXT
            _act_ctx = _ACTIVE_CHANNEL_CONTEXT.get() or {}
            _ch = _act_ctx.get("channel")
            _cid = _act_ctx.get("channel_id")
            if _ch and _cid:
                _steering = session_state_manager.pop_steering_message(str(_ch), str(_cid))
                if _steering:
                    logger.info(f"[AgentLoop] In-flight steering directive injected at step {step}: {_steering[:60]}")
                    messages.append({
                        "role": "user",
                        "content": f"[USER IN-FLIGHT STEERING DIRECTIVE]: {_steering}\nPlease adapt your plan and next actions accordingly."
                    })
        except Exception as e_steer:
            logger.debug(f"[AgentLoop] Steering check pass: {e_steer}")

        # Subagent in-flight steering check
        try:
            from core.subagent import get_current_subagent_task
            cur_task = get_current_subagent_task()
            if cur_task and hasattr(cur_task, "pop_steering_message"):
                _sub_steer = cur_task.pop_steering_message()
                if _sub_steer:
                    logger.info(f"[AgentLoop] Subagent steering directive injected at step {step}: {_sub_steer[:60]}")
                    messages.append({
                        "role": "user",
                        "content": f"[IN-FLIGHT STEERING DIRECTIVE]: {_sub_steer}\nPlease adapt your plan and next actions accordingly."
                    })
        except Exception as e_sub_steer:
            logger.debug(f"[AgentLoop] Subagent steering check pass: {e_sub_steer}")

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
                scrubbed = loop_scrubber.feed(delta)
                if loop_scrubber.last_hidden and progress_cb:
                    p_res = progress_cb({"type": "thought", "thought": loop_scrubber.last_hidden})
                    if asyncio.iscoroutine(p_res):
                        await p_res
                if token_cb and scrubbed:
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
            from core.image_eviction import evict_historical_images
            messages, _ = evict_historical_images(messages)
        except Exception:
            pass

        # Transcript Repair & Sanitization Gate (Anara Standard: transcript_repair.py)
        try:
            from core.transcript_repair import repair_transcript_sequence
            if isinstance(messages, list) and messages and isinstance(messages[0], dict):
                messages = repair_transcript_sequence(messages)
        except Exception as e_repair:
            logger.debug(f"[AgentLoop] Transcript repair notice: {e_repair}")

        try:
            try:
                raw_out = await provider_caller(messages, on_chunk=_chunk_dispatcher)
            except TypeError:
                raw_out = await provider_caller(messages)
        except Exception as e_call:
            from core.stream_rules import StreamRuleViolation
            if isinstance(e_call, StreamRuleViolation):
                logger.warning(f"[AgentLoop] TTSR hard-aborted stream: {e_call.rule_name}. Course-correcting...")
                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "type": "ttsr_intervention",
                            "rule": e_call.rule_name,
                            "message": e_call.message,
                            "matched_text": e_call.matched_text,
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass
                intervention_prompt = f"[STREAM RULE INTERVENTION]: {e_call.message}"
                messages.append({"role": "user", "content": intervention_prompt})
                continue

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
            # Anara turn_empty_response standard:
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
            is_truncated = ("<tool_call>" in raw_out and "</tool_call>" not in raw_out) or (
                raw_out.count("{") > raw_out.count("}") and ('"action"' in raw_out or '"tool"' in raw_out)
            )
            nudge_msg = (
                "[TOOL TRUNCATION RECOVERY]: Your previous tool call was cut off by token limits before completion. "
                "Please output the complete, unbroken tool call JSON again."
                if is_truncated
                else load_prompt("agent_loop/malformed_json")
            )
            logger.warning(f"[AgentLoop] Malformed or truncated tool call syntax detected (truncated={is_truncated}). Triggering recovery...")
            messages.append({"role": "assistant", "content": raw_out})
            messages.append({
                "role": "user",
                "content": nudge_msg
            })
            continue

        if not calls:
            # Check Negative Verification Stop-Gate (Anara Standard: turn_stop_gates.py & Anara Agent Protocol)
            stop_gate_nudge = convergence_detector.evaluate_final_stop_gate(agent_mode="plan" if read_only else "build")
            if stop_gate_nudge and step < max_steps - 1:
                logger.info(f"[AgentLoop] Stop-gate intercepted turn: verification tests required before reporting completion.")
                messages.append({"role": "assistant", "content": last_response})
                messages.append({"role": "user", "content": stop_gate_nudge})
                continue

            # Anti-Fabrication & Tool-Use Enforcement Stop Gate (Anara Standard)
            simulated_execution = None
            if not read_only:
                simulated_execution = re.search(
                    r"\*(?:\((?:sedang |mulai |mencoba )?(?:menjalankan|mengeksekusi|eksekusi|executing|running)\s+(?:perintah|command|tool|skrip|script)[^\)]*\)|\b(?:menjalankan|mengeksekusi|eksekusi|executing|running)\s+(?:perintah|command|tool|skrip|script)\b[^\*]+)\*",
                    last_response,
                    flags=re.IGNORECASE
                )
            if simulated_execution and step < max_steps - 1:
                logger.warning(f"[AgentLoop] Simulated execution detected without tool call: {simulated_execution.group(0)}")
                messages.append({"role": "assistant", "content": last_response})
                messages.append({
                    "role": "user",
                    "content": (
                        "[TOOL USE ENFORCEMENT]: You described or simulated an action in text/parentheses instead of invoking the real tool. "
                        "You MUST make the actual tool call to perform the action. Do not roleplay or simulate execution in text."
                    )
                })
                continue

            # Model responded with actual conversational narrative text!
            # Strip any leaked or orphaned tool tags before presenting to user (Anara Standard)
            cleaned_text = _clean_model_chat_text(last_response)
            # CRITICAL ANARA FIX: If text only contained tool calls or stray braces, invoke dynamic narrative synthesis pass
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
                # Anara Turn Recovery: Extract recent tool observations to construct honest, informative report
                recent_obs = []
                for m in reversed(messages):
                    if isinstance(m, dict) and m.get("role") in ("tool", "user"):
                        c = str(m.get("content", "")).strip()
                        if "[OBSERVATION]" in c or "[TOOL RESULT]" in c or "success" in c.lower() or "exit_code" in c.lower():
                            lines = [ln.strip() for ln in c.splitlines() if ln.strip() and not ln.startswith(("[OBSERVATION]", "[TOOL RESULT]"))]
                            if lines:
                                recent_obs.append(lines[0][:150])
                        if len(recent_obs) >= 2:
                            break
                if recent_obs:
                    obs_detail = "\n".join(f"• {obs}" for obs in reversed(recent_obs))
                    final_text = f"Tugas selesai dijalankan. Observasi:\n{obs_detail}"
                elif step < max_steps - 1 and raw_out and (
                    "<think>" in raw_out.lower()
                    or "<thought>" in raw_out.lower()
                    or "<reasoning>" in raw_out.lower()
                ):
                    # Anara Standard: Thinking-Only Response Auto-Nudge (empty_response_guard.py)
                    logger.info("[AgentLoop] Model emitted thinking blocks with zero visible prose. Engaging Anara Standard auto-nudge...")
                    thinking_nudge = (
                        "[System Notice]: You completed your internal reasoning thoughts but provided no visible final response text. "
                        "Please synthesize and output your final response to the user now based on your reasoning above."
                    )
                    messages.append({"role": "user", "content": thinking_nudge})
                    continue
                else:
                    final_text = _format_empty_model_notice(user_prompt)
            if token_cb and not accumulated_narrative and final_text:
                res = token_cb(final_text)
                if asyncio.iscoroutine(res):
                    await res
            return final_text

        # Emit interim commentary if the model spoke before invoking tools
        if lead_text and progress_cb:
            try:
                res_cb = progress_cb({
                    "type": "interim_text",
                    "text": _clean_model_chat_text(lead_text) or lead_text,
                })
                if asyncio.iscoroutine(res_cb):
                    await res_cb
            except Exception:
                pass

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
                parsed_calls.append({
                    "name": t_name,
                    "args": t_args,
                    "risk": "read_only",
                    "raw": call,
                    "stall_error": stall_msg,
                })
                continue

            t_risk = get_tool_risk(t_name)
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                from core.plan_detector import smart_evaluate_command_safety
                t_risk = await smart_evaluate_command_safety(t_args.get("command", ""), description=user_prompt[:80])

            # ── Anara Approval Engine (JSON Loop) ──────────────────────────
            from config import cfg_get
            from core.approval_guard import check_command_safety, normalize_approval_mode
            approval_mode = normalize_approval_mode(cfg_get("approvals.mode", "auto"))
            _danger_desc = ""

            # Hardline safety floor: blocks catastrophic commands even in Off/YOLO mode
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                cmd_text = t_args.get("command", "")
                safety_result = check_command_safety(cmd_text, approval_mode)
                if safety_result and safety_result.get("hardline"):
                    logger.warning(f"[HARDLINE FLOOR] Blocked '{t_name}': {safety_result['reason']}")
                    is_intercepted = True
                    interception_result = {
                        "intercepted": True,
                        "hardline_blocked": True,
                        "tool_name": t_name,
                        "tool_args": t_args,
                        "tool_risk": "hardline",
                        "reason": safety_result["reason"],
                        "cmd_preview": cmd_text[:200],
                        "lead_text": lead_text,
                        "raw_call": call,
                    }
                    break
                elif safety_result and safety_result.get("needs_approval"):
                    t_risk = "ask"
                    _danger_desc = safety_result.get("description", "")

            # Approval gate by canonical mode: auto, plan, off
            if intercept_mutating_tools and t_risk in ("mutating", "ask"):
                should_intercept = True
            elif approval_mode == "auto" and t_risk in ("mutating", "ask"):
                if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                    try:
                        from core.approval_smart import smart_approve
                        cmd_text = t_args.get("command", "")
                        danger_ctx = f"tool={t_name}, risk={t_risk}"
                        if _danger_desc:
                            danger_ctx += f", pattern_match={_danger_desc}"
                        verdict = await smart_approve(cmd_text, danger_ctx)
                        if verdict == "approve":
                            logger.info(f"[SmartApproval] Auto-approved '{t_name}': guardian verdict=APPROVE")
                            should_intercept = False
                        elif verdict == "deny":
                            logger.info(f"[SmartApproval] Denied '{t_name}': guardian verdict=DENY")
                            should_intercept = True
                        else:
                            logger.info(f"[SmartApproval] Escalating '{t_name}': guardian verdict=ESCALATE")
                            should_intercept = True
                    except Exception as e:
                        logger.warning(f"[SmartApproval] Guardian failed: {e}, escalating to manual")
                        should_intercept = True
                else:
                    should_intercept = (t_risk == "ask")
            elif approval_mode == "off":
                should_intercept = False
            elif approval_mode == "plan":
                should_intercept = t_risk in ("mutating", "ask")
            else:
                should_intercept = (t_risk == "ask") or (intercept_mutating_tools and t_risk in ("mutating", "ask"))

            if should_intercept:
                logger.info(f"[ToolInterceptor JSON] Intercepted tool '{t_name}' (risk={t_risk}, mode={approval_mode}) for Plan/Safety approval.")
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
                            t_args = item.get("args") or {}
                            detail_str = str(
                                t_args.get("query")
                                or t_args.get("file_path")
                                or t_args.get("command")
                                or t_args.get("url")
                                or t_args.get("pattern")
                                or t_args.get("path")
                                or t_args.get("title")
                                or ""
                            )
                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "running",
                                "parallel": len(ro_batch) > 1,
                                "detail": detail_str,
                                "tool_args": t_args,
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass

                batch_tasks = []
                for item in ro_batch:
                    if item.get("stall_error"):
                        async def _synth_stall(m=item["stall_error"]):
                            return {"status": "error", "message": f"[LOOP BREAKER INTERVENTION]: {m}"}
                        batch_tasks.append(_synth_stall())
                    else:
                        batch_tasks.append(dispatch_tool_call(item["name"], item["args"], read_only=read_only))
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                for offset_i, raw_res in enumerate(batch_results):
                    if isinstance(raw_res, BaseException):
                        tool_res = {"status": "error", "error": str(raw_res), "output": f"Unhandled tool execution error: {raw_res}"}
                    else:
                        tool_res = raw_res
                    results_by_index[call_idx + offset_i] = tool_res
                    item = ro_batch[offset_i]
                    if progress_cb:
                        try:
                            t_args = item.get("args") or {}
                            detail_str = str(
                                t_args.get("query")
                                or t_args.get("file_path")
                                or t_args.get("command")
                                or t_args.get("url")
                                or t_args.get("pattern")
                                or t_args.get("path")
                                or t_args.get("title")
                                or ""
                            )
                            summary_str = ""
                            raw_str = ""
                            if isinstance(tool_res, dict):
                                summary_str = str(
                                    tool_res.get("summary")
                                    or tool_res.get("message")
                                    or tool_res.get("search_results")
                                    or tool_res.get("output")
                                    or tool_res.get("result")
                                    or tool_res.get("content")
                                    or ""
                                )
                                raw_str = str(
                                    tool_res.get("raw_result")
                                    or tool_res.get("search_results")
                                    or tool_res.get("output")
                                    or tool_res.get("result")
                                    or tool_res.get("content")
                                    or summary_str
                                )
                            else:
                                summary_str = str(tool_res)
                                raw_str = str(tool_res)

                            res_cb = progress_cb({
                                "tool_name": item["name"],
                                "status": "done",
                                "summary": summary_str[:160] if summary_str else "Done",
                                "detail": detail_str,
                                "raw_result": raw_str,
                                "tool_args": t_args,
                            })
                            if asyncio.iscoroutine(res_cb):
                                await res_cb
                        except Exception:
                            pass
                call_idx = end_idx
            else:
                item = parsed_calls[call_idx]
                t_args = item.get("args") or {}
                detail_str = str(
                    t_args.get("query")
                    or t_args.get("file_path")
                    or t_args.get("command")
                    or t_args.get("url")
                    or t_args.get("pattern")
                    or t_args.get("path")
                    or t_args.get("title")
                    or ""
                )
                if progress_cb:
                    try:
                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "running",
                            "detail": detail_str,
                            "tool_args": t_args,
                        })
                        if asyncio.iscoroutine(res_cb):
                            await res_cb
                    except Exception:
                        pass

                is_safe_cli = (item["name"] == "execute_cli_command" and is_safe_read_only_cli_command(item["args"].get("command", "")))
                if item.get("stall_error"):
                    mut_res = {"status": "error", "message": f"[LOOP BREAKER INTERVENTION]: {item['stall_error']}"}
                elif read_only and item["name"] not in READ_ONLY_TOOL_NAMES and not is_safe_cli:
                    mut_res = {"status": "error", "message": f"Tool '{item['name']}' is disabled in Plan Mode (Read-Only)."}
                else:
                    mut_res = await dispatch_tool_call(item["name"], item["args"], read_only=read_only)
                results_by_index[call_idx] = mut_res

                if progress_cb:
                    try:
                        summary_str = ""
                        raw_str = ""
                        if isinstance(mut_res, dict):
                            summary_str = str(
                                mut_res.get("summary")
                                or mut_res.get("message")
                                or mut_res.get("search_results")
                                or mut_res.get("output")
                                or mut_res.get("result")
                                or mut_res.get("content")
                                or ""
                            )
                            raw_str = str(
                                mut_res.get("raw_result")
                                or mut_res.get("search_results")
                                or mut_res.get("output")
                                or mut_res.get("result")
                                or mut_res.get("content")
                                or summary_str
                            )
                        else:
                            summary_str = str(mut_res)
                            raw_str = str(mut_res)

                        res_cb = progress_cb({
                            "tool_name": item["name"],
                            "status": "done",
                            "summary": summary_str[:160] if summary_str else "Done",
                            "detail": detail_str,
                            "raw_result": raw_str,
                            "tool_args": t_args,
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
            has_lint_err = bool(isinstance(tool_res, dict) and tool_res.get("lint_warning"))
            raw_err = (
                isinstance(tool_res, dict) and (
                    tool_res.get("status") in ("error", "failed")
                    or tool_res.get("return_code", 0) != 0
                    or tool_res.get("is_error") is True
                )
            ) or has_lint_err

            # Anara Standard: Exploratory tools (read_file, grep, glob, list_dir) returning "not found" or 0 matches
            # are observations, not system execution failures.
            is_err = raw_err and not is_tolerant

            if has_lint_err and isinstance(tool_res, dict):
                lint_msg = tool_res.get("lint_warning")
                fname = tool_res.get("filename") or tool_name
                recovery_hints.append(
                    f"\n[COMPILER SELF-REPAIR GUARD]: File '{fname}' contains a syntax regression: {lint_msg}.\n"
                    f"You MUST immediately repair this syntax error in your next action using edit_file (Hashline PUT/SWAP). Do not close your response or leave broken syntax."
                )

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
                compacted_res_str = loop_breaker.check_or_stub_duplicate(tool_name, item["args"], compacted_res_str)
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

        # Reset retry budget only when mutating operations succeed (actual progress was made),
        # preserving failure memory during passive/read-only operations to prevent ping-pong loops
        if not turn_had_error:
            has_mutating = any(item.get("risk") in ("mutating", "ask") for item in parsed_calls)
            if has_mutating:
                self_correction_tracker.reset()
                loop_breaker.notify_mutation()

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

        # In-Process Compiler Repair Gate: If any tool introduced a syntax regression, do not converge!
        has_active_syntax_error = any(
            isinstance(results_by_index.get(i), dict) and results_by_index[i].get("lint_warning")
            for i in range(len(parsed_calls))
        )
        if has_active_syntax_error:
            logger.info("[AgentLoop] Active syntax regression detected: withholding convergence to force immediate self-repair.")
            conv_status.is_converged = False

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
            if not read_only and convergence_detector.mutations_count == 0 and step < max_steps - 3:
                logger.info(f"[AgentLoop] Build mode with 0 mutations: preserving tools and nudging model to implement (reason={conv_status.reason}).")
            else:
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
        
    # If the loop finished and last_response is STILL a tool call or stray bracket (Anara Turn-Completion Enforcement):
    # Never return raw JSON tool call or stray bracket artifacts to the user!
    cleaned_last = _clean_model_chat_text(last_response)
    if '"action": "tool_call"' in last_response or '<tool_call>' in last_response or not cleaned_last:
        logger.info("[AgentLoop] Final turn terminated on unclosed tool call or missing narrative. Executing Closing Narrative Pass...")
        try:
            # Compact message history for closing pass to avoid token exhaustion
            effective_messages = list(messages)
            if len(effective_messages) > 10:
                head_msgs = effective_messages[:2]
                tail_msgs = effective_messages[-6:]
                effective_messages = [*head_msgs, {"role": "user", "content": "[... intermediate tool execution turns compacted ...]"}, *tail_msgs]

            closing_prompt = [
                *effective_messages,
                {
                    "role": "user",
                    "content": load_prompt(
                        "agent_loop/closing_narrative",
                        default="Based on all the work, observations, and attachments above, provide a clear, helpful, and complete final response to the user in natural conversational prose matching the active language."
                    )
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

        # Fallback: Extract recent tool observations from messages to construct honest, informative report
        recent_obs = []
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") in ("tool", "user"):
                c = str(m.get("content", "")).strip()
                if "[OBSERVATION]" in c or "[TOOL RESULT]" in c or "success" in c.lower():
                    lines = [ln.strip() for ln in c.splitlines() if ln.strip() and not ln.startswith(("[OBSERVATION]", "[TOOL RESULT]"))]
                    if lines:
                        recent_obs.append(lines[0][:150])
                if len(recent_obs) >= 2:
                    break
        if recent_obs:
            obs_detail = "\n".join(f"• {obs}" for obs in reversed(recent_obs))
            return f"Langkah tugas telah selesai dijalankan. Observasi terakhir:\n{obs_detail}"

        return _format_empty_model_notice(user_prompt)

    return cleaned_last or last_response


