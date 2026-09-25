"""
self_correction.py — Unified Autonomous Self-Correction & Execution Sentinel Engine for Project Anara.
Consolidates pre-execution loop prevention, dynamic error recovery, context micro-compaction,
and circuit breakers into a cohesive architecture (Hermes Agent Parity).

Pillars:
1. Pre-Execution Sentinel (AnaraLoopBreaker): Mathematical SHA-256 fingerprinting to prevent
   infinite identical loops (A -> A -> A -> A) and ping-pong tool thrashing (A -> B -> A -> B).
2. Context Micro-Compactor (ContextMicroCompactor): Strips CLI ANSI noise and progress bar jitter,
   sniffs traceback/error anchors, prunes hundreds of output lines to 25-35 essential lines,
   and archives full untruncated logs to disk.
3. Diagnostic Error Classifier (ErrorClassifier): Pattern and semantic detection of missing modules,
   port conflicts, syntax errors, missing files, permission errors, and network timeouts.
4. Circuit Breaker & Recovery Tracker (SelfCorrectionTracker): 2x identical failure circuit trip,
   3-attempt self-correction recovery budget, and elegant diagnostic root-cause cards.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from constants import get_anara_logs_dir

logger = logging.getLogger("anara.tools.self_correction")

TOOL_LOGS_DIR = get_anara_logs_dir("tool_logs")
TOOL_LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 1. PRE-EXECUTION SENTINEL & LOOP BREAKER
# ==============================================================================

class AnaraLoopBreaker:
    """
    Dynamic execution loop breaker for Anara Autonomous Agent turns.
    Tracks mathematical execution patterns to prevent runaway token exhaustion.
    """

    def __init__(
        self,
        max_identical: int = 4,
        max_consecutive_errors: int = 5,
        window_size: int = 16,
    ):
        self.max_identical = max_identical
        self.max_consecutive_errors = max_consecutive_errors
        self.call_history: deque[str] = deque(maxlen=window_size)
        self.tool_names: deque[str] = deque(maxlen=window_size)
        self.consecutive_errors: int = 0

    def _hash_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Dynamically computes SHA-256 fingerprint of any tool name and arguments."""
        try:
            serialized_args = json.dumps(args, sort_keys=True, default=str, ensure_ascii=False)
        except Exception:
            serialized_args = str(sorted(args.items())) if isinstance(args, dict) else str(args)

        payload = f"{tool_name.strip().lower()}:{serialized_args}"
        return hashlib.sha256(payload.encode("utf-8", errors="replace")).hexdigest()[:16]

    def record_and_check(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Records a tool invocation and checks for repetitive loops.
        Returns: (is_stalled, self_healing_message)
        """
        clean_name = (tool_name or "").strip()
        call_hash = self._hash_call(clean_name, args or {})
        self.call_history.append(call_hash)
        self.tool_names.append(clean_name)

        # 1. Check for trailing identical calls (A -> A -> A -> A)
        if len(self.call_history) >= self.max_identical:
            recent = list(self.call_history)[-self.max_identical:]
            if len(set(recent)) == 1:
                from core.prompt_loader import load_prompt
                msg = load_prompt(
                    "self_correction/loop_breaker_identical",
                    tool_name=clean_name,
                    max_identical=self.max_identical
                ).strip()
                logger.warning(f"[LoopBreaker] Identical call stall detected for tool '{clean_name}' ({self.max_identical}x).")
                return True, msg

        # 2. Check for alternating ping-pong cycles (A -> B -> A -> B -> A -> B)
        if len(self.call_history) >= 6:
            recent_6 = list(self.call_history)[-6:]
            if recent_6[0] == recent_6[2] == recent_6[4] and recent_6[1] == recent_6[3] == recent_6[5] and recent_6[0] != recent_6[1]:
                t1, t2 = list(self.tool_names)[-2], list(self.tool_names)[-1]
                from core.prompt_loader import load_prompt
                msg = load_prompt(
                    "self_correction/loop_breaker_cycle",
                    t1=t1,
                    t2=t2
                ).strip()
                logger.warning(f"[LoopBreaker] Ping-pong cycle detected between '{t1}' and '{t2}'.")
                return True, msg

        return False, None

    def record_result(self, is_error: bool) -> Tuple[bool, Optional[str]]:
        """
        Tracks consecutive error cascades to guide the model when stuck.
        """
        if is_error:
            self.consecutive_errors += 1
            if self.consecutive_errors >= self.max_consecutive_errors:
                from core.prompt_loader import load_prompt
                msg = load_prompt(
                    "self_correction/loop_breaker_cascade",
                    consecutive_errors=self.consecutive_errors
                ).strip()
                logger.warning(f"[LoopBreaker] Consecutive error threshold hit ({self.consecutive_errors}).")
                return True, msg
        else:
            self.consecutive_errors = 0
        return False, None

    def reset(self) -> None:
        """Resets the loop breaker history."""
        self.call_history.clear()
        self.tool_names.clear()
        self.consecutive_errors = 0


# ==============================================================================
# 2. CONTEXT MICRO-COMPACTOR & ANCHOR SNIFFING
# ==============================================================================

class ContextMicroCompactor:
    """
    Pillar A: Compacts massive terminal logs & stack traces to prevent context window overflow.
    Strips progress bar noise, sniffs traceback anchors, and saves raw forensic dumps to disk.
    """

    MAX_OUTPUT_LINES: int = 35
    MAX_OUTPUT_CHARS: int = 3500

    @classmethod
    def clean_terminal_noise(cls, text: str) -> str:
        """Strips ANSI escapes, progress bar overrides, and carriage return noise."""
        if not text:
            return ""

        # Remove ANSI color/formatting escape codes
        s = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)
        # Handle carriage returns from CLI progress updates (keep latest line state)
        if "\r" in s:
            s = re.sub(r"[^\n]*\r", "", s)
        # Strip common progress bar patterns
        s = re.sub(r"(?m)^\s*(?:\[[=> -]+\]|\d+%\s*\|[█▎▌▋▊▉ ]+\|\s*\d+/\d+)[^\n]*\n?", "", s)
        return s

    @classmethod
    def compact_output(
        cls,
        raw_output: str,
        max_lines: int = 35,
        source_label: str = "cli_error",
    ) -> str:
        """
        Compacts huge CLI logs by sniffing traceback/error anchors.
        Returns a clean snippet preserving context around the actual failure.
        """
        if not raw_output:
            return ""

        cleaned = cls.clean_terminal_noise(raw_output).strip()
        lines = [line for line in cleaned.splitlines() if line.strip()]

        if len(lines) <= max_lines and len(cleaned) <= cls.MAX_OUTPUT_CHARS:
            return cleaned

        # 1. Save full untruncated raw dump to disk for offline forensics
        dump_id = uuid.uuid4().hex[:8]
        dump_file = TOOL_LOGS_DIR / f"{source_label}_{dump_id}.log"
        try:
            dump_file.write_text(cleaned, encoding="utf-8", errors="replace")
            log_notice = f"Full log ({len(cleaned):,} chars) saved at: {dump_file}"
        except Exception:
            log_notice = f"Total log characters: {len(cleaned):,}"

        # 2. Sniff error anchors (Traceback, Error, FAILED, Exception)
        error_keywords = ("traceback (most recent call last)", "error:", "failed:", "exception:", "syntaxerror:", "fatal:")
        err_indices = [
            idx for idx, line in enumerate(lines)
            if any(k in line.lower() for k in error_keywords)
        ]

        if err_indices:
            # Anchor at the first significant traceback/error
            anchor = err_indices[0]
            start_idx = max(0, anchor - 3)
            end_idx = min(len(lines), start_idx + max_lines)
            important_slice = lines[start_idx:end_idx]

            head_omitted = start_idx
            tail_omitted = len(lines) - end_idx

            parts = []
            if head_omitted > 0:
                parts.append(f"[... {head_omitted} lines truncated by compactor ...]")
            parts.append("\n".join(important_slice))
            if tail_omitted > 0:
                parts.append(f"[... {tail_omitted} lines omitted. {log_notice} ...]")
            return "\n".join(parts)

        # 3. Fallback: Preserves Head (40%) + Tail (60%)
        head_count = max(1, int(max_lines * 0.4))
        tail_count = max(1, max_lines - head_count)
        head_lines = lines[:head_count]
        tail_lines = lines[-tail_count:]
        omitted = len(lines) - (head_count + tail_count)

        return (
            "\n".join(head_lines)
            + f"\n\n[... {omitted} lines of noise truncated by compactor. {log_notice} ...]\n\n"
            + "\n".join(tail_lines)
        )


# ==============================================================================
# 3. DIAGNOSTIC ERROR CLASSIFIER (PATTERN & SEMANTIC)
# ==============================================================================

class ErrorClassifier:
    """Recognizes common error patterns and execution anomalies for autonomous auto-recovery."""

    PATTERNS: Dict[str, str] = {
        "missing_python_pkg": r"ModuleNotFoundError:\s*No\s+module\s+named\s+['\"]([^'\"]+)['\"]",
        "missing_node_pkg": r"Cannot\s+find\s+module\s+['\"]([^'\"]+)['\"]",
        "port_conflict": r"(?:Address\s+already\s+in\s+use|EADDRINUSE.*?port\s+(\d+)|port\s+(\d+)\s+is\s+occupied)",
        "command_not_found": r"(?:command\s+not\s+found|is\s+not\s+recognized\s+as\s+an\s+internal\s+or\s+external\s+command)",
        "permission_denied": r"(?:Permission\s+denied|Access\s+is\s+denied|EACCES)",
        "syntax_error": r"(?:SyntaxError:\s*(.+)|Parsing\s+error:\s*(.+))",
        "file_not_found": r"(?:FileNotFoundError:\s*\[Errno\s*2\]\s*No\s+such\s+file\s+or\s+directory:\s*['\"]([^'\"]+)['\"]|ENOENT:\s*no\s+such\s+file\s+or\s+directory)",
        "network_timeout": r"(?:ConnectTimeout|ReadTimeout|ETIMEDOUT|ECONNREFUSED|getaddrinfo\s+ENOTFOUND)",
    }

    @classmethod
    def classify(cls, output: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Classifies output against error patterns.
        Returns: (error_type, extracted_detail_or_offending_target)
        """
        if not output:
            return None, None

        for err_type, pattern in cls.PATTERNS.items():
            match = re.search(pattern, output, re.IGNORECASE)
            if match:
                groups = [g for g in match.groups() if g is not None]
                extracted_val = groups[0] if groups else ""
                return err_type, extracted_val

        # Generic traceback detection
        if "traceback (most recent call last)" in output.lower():
            lines = output.strip().splitlines()
            last_line = lines[-1].strip() if lines else "Python Exception"
            return "python_exception", last_line

        return None, None

    @classmethod
    async def classify_semantic(cls, output: str, task_context: str = "") -> Tuple[str, str]:
        """
        Model-driven semantic error classifier for complex or novel stack traces (Zero-Hardcoding).
        Invokes fast auxiliary LLM (< 300ms) to identify error category and key offending entity.
        """
        err_type, detail = cls.classify(output)
        if err_type:
            return err_type, detail or ""

        try:
            from providers import call_universal_chat_model
            from core.capabilities import get_fast_auxiliary_model
            from core.prompt_loader import load_prompt

            snippet = output[:1500]
            sys_p = load_prompt("classifiers/error_classifier").strip()
            user_p = f"Context: {task_context[:100]}\nOutput:\n{snippet}"

            model_id = get_fast_auxiliary_model()
            res = await call_universal_chat_model(
                model_id=model_id,
                user_prompt=user_p,
                system_instruction=sys_p,
                max_tokens=None,
                temperature=0.0,
                read_only=True,
            )
            if isinstance(res, str) and "{" in res and "}" in res:
                from providers.caller import _extract_json_balanced, _robust_parse_json
                for candidate, _, _ in _extract_json_balanced(res):
                    data = _robust_parse_json(candidate)
                    if isinstance(data, dict) and "error_type" in data:
                        return data.get("error_type", "execution_error"), data.get("detail", "")
                parsed = _robust_parse_json(res.strip())
                if isinstance(parsed, dict) and "error_type" in parsed:
                    return parsed.get("error_type", "execution_error"), parsed.get("detail", "")
        except Exception as e:
            logger.debug(f"[ErrorClassifier] Semantic fallback notice: {e}")

        return "execution_error", "Command produced a non-zero exit code or execution failure."


# ==============================================================================
# 4. CIRCUIT BREAKER & SELF-CORRECTION TRACKER (HERMES AGENT PARITY)
# ==============================================================================

# Tools whose "failure" is normal exploratory observation (empty search, missing file, 0 matches)
# These never trip execution circuit breakers because not-found is useful signal for the agent.
def _load_failure_tolerant_tools() -> frozenset:
    try:
        from core.prompt_loader import load_config_yaml
        cfg = load_config_yaml("config/failure_tolerant_tools.yaml", default={})
        tools = cfg.get("failure_tolerant_tools")
        if tools and isinstance(tools, list):
            return frozenset(tools)
    except Exception:
        pass
    return frozenset({
        "read_local_file", "grep_search_code", "glob_find_files",
        "list_directory", "scan_workspace_folder", "web_search", "fetch_webpage",
    })

FAILURE_TOLERANT_TOOL_NAMES = _load_failure_tolerant_tools()
IDEMPOTENT_TOOL_NAMES = FAILURE_TOLERANT_TOOL_NAMES


class SelfCorrectionTracker:
    """
    Pillar B & D: Tracks autonomous retry budget and enforces Circuit Breaker
    based on Hermes Agent standard:
    - Soft Warning on identical attempts >= 2 (provides reflection hints to model).
    - Hard Stop (Diagnostic Card) only on identical attempts >= 5 (prevents true runaway loops).
    - Failure-Tolerant: Exploratory operations (file read / grep 0 match) do not consume system failure quota.
    """

    def __init__(
        self,
        max_retries: int = 5,
        max_identical_failures: int = 5,
        warn_after_exact: int = 2,
        interactive: bool = True,
    ):
        self.max_retries = max_retries
        self.max_identical_failures = max_identical_failures
        self.warn_after_exact = warn_after_exact
        self.interactive = interactive
        self.history: List[Dict[str, Any]] = []

    def is_failure_tolerant(self, tool_name: str) -> bool:
        """
        Dynamically determines if a tool is exploratory/read-only (Hermes Parity).
        Any tool categorized with risk == 'read_only' in the system catalog is universally
        failure-tolerant because inspection operations (read/grep/glob/stat) do not mutate state.
        """
        clean = (tool_name or "").strip().lower()
        if not clean:
            return False
        try:
            from tools.catalog import get_tool_risk
            risk = get_tool_risk(clean)
            if risk == "read_only":
                return True
        except Exception:
            pass
        return clean in FAILURE_TOLERANT_TOOL_NAMES

    def get_signature(self, tool_name: str, command_or_arg: str, err_type: str) -> str:
        """Computes SHA-256 fingerprint of the failure occurrence."""
        clean_target = str(command_or_arg or "")[:120].strip()
        raw = f"{tool_name.strip().lower()}:{clean_target}:{err_type.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:12]

    def register_attempt(
        self,
        tool_name: str,
        command_or_arg: str,
        err_type: str,
        detail: str = "",
    ) -> Dict[str, Any]:
        """
        Registers an error attempt, checks circuit breaker and recovery budget.
        Returns evaluation dict with 'allowed', 'should_warn', 'is_stalled', 'budget_exhausted', 'attempt'.
        """
        sig = self.get_signature(tool_name, command_or_arg, err_type)
        prior_same_signatures = [h for h in self.history if h.get("signature") == sig]

        total_same_count = len(prior_same_signatures) + 1
        should_warn = total_same_count >= self.warn_after_exact
        is_stalled = total_same_count >= self.max_identical_failures

        attempt_record = {
            "signature": sig,
            "tool_name": tool_name,
            "target": command_or_arg,
            "error_type": err_type,
            "detail": detail,
            "timestamp": time.time(),
        }
        self.history.append(attempt_record)

        attempt_count = len(self.history)
        budget_exhausted = is_stalled or (attempt_count >= self.max_retries if not self.interactive else False)
        allowed = (not is_stalled) and (not budget_exhausted)

        return {
            "allowed": allowed,
            "should_warn": should_warn,
            "is_stalled": is_stalled,
            "budget_exhausted": budget_exhausted,
            "attempt": total_same_count,
            "total_failures": attempt_count,
            "max_retries": self.max_retries,
            "signature": sig,
            "error_type": err_type,
            "detail": detail,
        }

    def is_exhausted(self) -> bool:
        return len(self.history) >= self.max_retries

    def reset(self) -> None:
        self.history.clear()


# ==============================================================================
# 5. RECOVERY GUIDANCE & DIAGNOSTIC ROOT-CAUSE PRESENTATION
# ==============================================================================

def format_recovery_guidance(
    err_type: Optional[str] = None,
    detail: Optional[str] = None,
    attempt: int = 1,
    max_retries: int = 5,
    tool_name: str = "tool",
) -> str:
    """
    Action-oriented meta-guidance for recovering from repeated tool failures (Hermes Agent Parity).
    Zero hardcoded canned definitions: loaded from backend/prompts/self_correction/recovery_guidance.md.
    """
    from core.prompt_loader import load_prompt
    diag_line = f"Failure category: {err_type or 'execution_error'}" + (f" ({detail})" if detail else "")
    guidance = load_prompt(
        "self_correction/recovery_guidance",
        attempt=attempt,
        max_retries=max_retries,
        diag_line=diag_line,
        tool_name=tool_name,
        err_type_or_error=err_type or "error"
    ).strip()
    return f"\n\n{guidance}"


async def synthesize_diagnostic_explanation(
    history: List[Dict[str, Any]],
    last_error_text: str,
    original_task: str = "",
) -> str:
    """
    Dynamic Model-Driven Diagnostic Synthesis Pass (Hermes Agent Parity).
    Instead of outputting rigid canned HTML cards, invokes auxiliary LLM to synthesize
    an empathetic, contextual explanation in natural conversational prose.
    """
    try:
        from providers import call_universal_chat_model
        from core.capabilities import get_fast_auxiliary_model
        from core.prompt_loader import load_prompt

        model_id = get_fast_auxiliary_model()
        sys_p = load_prompt("self_correction/diagnostic_synthesis").strip()
        last_item = history[-1] if history else {}
        user_p = (
            f"User Task: {original_task[:150]}\n"
            f"Last Tool: {last_item.get('tool_name')}\n"
            f"Error Category: {last_item.get('error_type')} ({last_item.get('detail')})\n"
            f"Self-Correction Attempts: {len(history)}\n"
            f"Last Error Log:\n{last_error_text[:600]}"
        )
        synth = await call_universal_chat_model(
            model_id=model_id,
            user_prompt=user_p,
            system_instruction=sys_p,
            max_tokens=None,
            temperature=0.3,
            read_only=True,
        )
        if synth and synth.strip():
            return synth.strip()
    except Exception as e:
        logger.debug(f"[DiagnosticSynthesizer] Fallback to structured card: {e}")

    return format_graceful_diagnostic_card(history, last_error_text, original_task)


def format_graceful_diagnostic_card(
    history: List[Dict[str, Any]],
    last_error_text: str,
    original_task: str = "",
) -> str:
    """
    Pilar D: Formulates an elegant, human-readable Diagnostic Root Cause Card
    when self-correction budget is exhausted, preventing raw traceback dumps.
    Template loaded dynamically from backend/prompts/self_correction/diagnostic_card.md.
    """
    from core.prompt_loader import load_prompt

    last_att = history[-1] if history else {}
    err_type = last_att.get("error_type", "Execution Error")
    tool_name = last_att.get("tool_name", "system tool")
    target = last_att.get("target", "")

    steps_attempted = []
    for idx, h in enumerate(history, 1):
        t_n = h.get("tool_name", "action")
        e_t = h.get("error_type", "error")
        steps_attempted.append(f"{idx}. Executed <code>{t_n}</code> (Failed: <i>{e_t}</i>)")

    steps_str = "\n".join(steps_attempted) if steps_attempted else "Multiple self-correction attempts"

    return load_prompt(
        "self_correction/diagnostic_card",
        task_goal=original_task[:120] or "System step execution",
        tool_name=tool_name,
        target=str(target)[:60],
        err_type=err_type,
        steps_str=steps_str
    ).strip()
