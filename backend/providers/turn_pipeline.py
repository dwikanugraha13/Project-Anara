"""
turn_pipeline.py — Phased Agent Turn Pipeline Architecture for Project Anara.
Parity with Hermes Agent (agent/conversation_loop.py _LoopState & phase runners).
Provides modular, decoupled phases for turn execution:
1. Preflight & Steering Phase (token budget, preflight gate, in-flight steering)
2. Tool Execution Phase (parallel read-only via asyncio.gather, serial mutating, stall checks)
3. Convergence & Verification Phase (stop-gate evaluation, code completion check)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class LoopPhaseState:
    """Encapsulates turn state across loop iterations (Hermes _LoopState Parity)."""
    step: int = 0
    max_steps: int = 25
    read_only: bool = False
    model_id: str = ""
    history: List[Any] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    executed_items_for_convergence: List[Dict[str, Any]] = field(default_factory=list)
    circuit_breaker_tripped: bool = False
    budget_exhausted: bool = False
    last_text: str = ""
    interim_commentary: str = ""


class TurnPhasePipeline:
    """Modular phase coordinators for autonomous agent turn loops."""

    @staticmethod
    def run_preflight_and_steering(state: LoopPhaseState, token_tracker: Any) -> None:
        """Hermes Parity: Preflight Gate, budget tracking, and Pi steering queue pop."""
        token_tracker.run_preflight_gate(state.history)
        token_tracker.record_step(state.step, state.history)

        try:
            from core.session_manager import session_state_manager
            from core.channel_adapter import _ACTIVE_CHANNEL_CONTEXT
            _act_ctx = _ACTIVE_CHANNEL_CONTEXT.get() or {}
            _ch = _act_ctx.get("channel")
            _cid = _act_ctx.get("channel_id")
            if _ch and _cid:
                steering = session_state_manager.pop_steering_message(str(_ch), str(_cid))
                if steering:
                    logger.info(f"[TurnPipeline] Steering directive injected at step {state.step}: {steering[:60]}")
                    steer_prompt = f"[USER IN-FLIGHT STEERING DIRECTIVE]: {steering}\nPlease adapt your plan and next actions accordingly."
                    if state.history and isinstance(state.history[0], dict):
                        state.history.append({"role": "user", "content": steer_prompt})
                    else:
                        from google.genai import types as genai_types
                        state.history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=steer_prompt)]))
        except Exception as e_steer:
            logger.debug(f"[TurnPipeline] Steering check pass: {e_steer}")

        # In-Flight Steering Directive check for Subagents
        try:
            from core.subagent import get_current_subagent_task
            cur_task = get_current_subagent_task()
            if cur_task and hasattr(cur_task, "pop_steering_message"):
                sub_steer = cur_task.pop_steering_message()
                if sub_steer:
                    logger.info(f"[TurnPipeline] Subagent in-flight steering directive injected at step {state.step}: {sub_steer[:60]}")
                    steer_prompt = f"[IN-FLIGHT STEERING DIRECTIVE]: {sub_steer}\nPlease adapt your plan and next actions accordingly."
                    if state.history and isinstance(state.history[0], dict):
                        state.history.append({"role": "user", "content": steer_prompt})
                    else:
                        from google.genai import types as genai_types
                        state.history.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=steer_prompt)]))
        except Exception as e_sub_steer:
            logger.debug(f"[TurnPipeline] Subagent steering check pass: {e_sub_steer}")

    @staticmethod
    def partition_tool_batch(
        calls: List[Dict[str, Any]],
        start_idx: int
    ) -> Tuple[List[Dict[str, Any]], int, bool]:
        """
        Partitions calls into parallel read-only batches or single mutating calls.
        Returns: (batch_items, next_index, is_read_only_batch)
        """
        if not calls or start_idx >= len(calls):
            return [], start_idx, False

        first = calls[start_idx]
        if first.get("risk") == "read_only":
            end_idx = start_idx
            while end_idx < len(calls) and calls[end_idx].get("risk") == "read_only":
                end_idx += 1
            return calls[start_idx:end_idx], end_idx, True
        else:
            return [first], start_idx + 1, False

    @staticmethod
    def evaluate_compiler_self_repair(results_by_index: Dict[int, Any], parsed_calls: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Hermes / OMP Parity: Evaluates whether any tool in the turn introduced a syntax regression.
        Returns: (has_syntax_errors, warning_messages)
        """
        has_error = False
        warnings = []
        for idx in range(len(parsed_calls)):
            tool_res = results_by_index.get(idx)
            if isinstance(tool_res, dict) and tool_res.get("lint_warning"):
                has_error = True
                fpath = tool_res.get("file_path") or parsed_calls[idx].get("args", {}).get("file_path") or "file"
                warnings.append(
                    f"[COMPILER SELF-REPAIR GUARD]: File '{fpath}' contains a syntax regression ({tool_res['lint_warning']}). "
                    f"Fix this immediately before proceeding."
                )
        return has_error, warnings

    @staticmethod
    def build_synthesis_prompt(user_prompt: str, highlights: str) -> str:
        """
        Builds a language-agnostic closing narrative synthesis prompt.
        Eliminates hardcoded colloquial language assumptions.
        """
        return (
            f"User asked: \"{user_prompt}\"\n\n"
            f"The agent executed the following workspace actions and checks:\n{highlights}\n\n"
            "Provide a direct, helpful, and natural response to the user in their active language, "
            "summarizing what was checked and the final conclusion."
        )
