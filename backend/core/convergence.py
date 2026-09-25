"""
convergence.py — Mission-Level Cognitive Convergence & Stagnation Detector (Hermes & Claude Code Parity).

Monitors agent trajectory across turns to detect:
1. Goal Satisfaction: File modified + ground-truth tests verified -> conclude immediately without wandering.
2. Information Saturation: Redundant inspections of already-explored targets with 0 new discoveries.
3. Multi-Tool N-Cycles: Repeating loops of 2-4 tool patterns (e.g. A -> B -> C -> A -> B -> C).
4. Inspection Budget Exhaustion: Prevents indefinite exploration in Plan/Read-Only modes.
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class ActionRecord:
    step: int
    tool_name: str
    target: str
    risk: str
    is_error: bool
    summary: str


@dataclass
class ConvergenceStatus:
    is_converged: bool = False
    should_nudge: bool = False
    guidance: Optional[str] = None
    reason: str = "progressing"
    phase: str = "EXPLORING"


class ConvergenceDetector:
    """
    Evaluates trajectory convergence to prevent infinite loops, cyclic wandering,
    and post-verification stagnation in autonomous agent execution loops.
    """

    def __init__(self, read_only: bool = False):
        self.read_only = read_only
        self.history: List[ActionRecord] = []
        self.inspected_targets: Set[str] = set()
        self.modified_targets: Set[str] = set()
        self.phase: str = "EXPLORING"
        self.mutations_count: int = 0
        self.test_verified_count: int = 0
        self.last_test_passed: bool = False
        self.redundant_inspections: int = 0

    def extract_canonical_target(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Extracts normalized entity target from tool arguments."""
        if not isinstance(args, dict):
            return ""

        if tool_name in ("read_local_file", "edit_file", "write_local_file", "delete_local_file"):
            fp = args.get("file_path") or args.get("path") or ""
            return os.path.normpath(str(fp).strip().replace("\\", "/")).lower()

        if tool_name in ("glob_find_files", "grep_search_code"):
            patt = args.get("pattern") or ""
            p = args.get("path") or "."
            return f"{p}:{patt}".strip().lower()

        if tool_name in ("execute_cli_command", "terminal", "run_terminal_command"):
            cmd = str(args.get("command") or "").strip().lower()
            # Normalize whitespace
            return re.sub(r"\s+", " ", cmd)

        if tool_name in ("web_search", "session_search"):
            return str(args.get("query") or "").strip().lower()

        for k in ("query", "url", "task", "title", "name"):
            if k in args:
                return str(args[k]).strip().lower()

        return ""

    def record_turn_actions(
        self,
        step: int,
        executed_calls: List[Dict[str, Any]],
    ) -> ConvergenceStatus:
        """
        Records all tool actions executed in a single turn and evaluates trajectory convergence.
        Each item in executed_calls must have:
        - tool_name: str
        - args: Dict[str, Any]
        - risk: str ('read_only', 'action', 'mutating', 'ask')
        - is_error: bool
        - summary: str
        """
        for item in executed_calls:
            t_name = item.get("tool_name", "")
            t_args = item.get("args") or {}
            risk = item.get("risk", "read_only")
            is_err = bool(item.get("is_error", False))
            summary = str(item.get("summary", ""))

            target = self.extract_canonical_target(t_name, t_args)

            record = ActionRecord(
                step=step,
                tool_name=t_name,
                target=target,
                risk=risk,
                is_error=is_err,
                summary=summary,
            )
            self.history.append(record)

            # Update lifecycle state
            if risk in ("mutating", "ask") and not is_err:
                self.mutations_count += 1
                self.phase = "MUTATING"
                if target:
                    self.modified_targets.add(target)

            # Check for verification commands
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                cmd = target.lower()
                if any(k in cmd for k in ("pytest", "npm test", "run_tests", "python -m unittest")):
                    self.phase = "VERIFYING"
                    if not is_err and "failed" not in summary.lower() and "error" not in summary.lower():
                        self.test_verified_count += 1
                        self.last_test_passed = True
                    else:
                        self.last_test_passed = False

            # Track read-only target saturation
            if risk == "read_only" and target:
                if target in self.inspected_targets:
                    self.redundant_inspections += 1
                else:
                    self.inspected_targets.add(target)
                    # Reset saturation streak on fresh target discovery
                    self.redundant_inspections = max(0, self.redundant_inspections - 1)

        return self.evaluate(step)

    def detect_multi_tool_cycles(self) -> Optional[int]:
        """
        Detects repeating N-cycles of length 2, 3, or 4 in the action history.
        Returns the cycle length if a repeating pattern is found, or None.
        """
        if len(self.history) < 6:
            return None

        # Signatures of recent actions: (tool_name, target)
        sigs = [(a.tool_name, a.target) for a in self.history]

        for cycle_len in (2, 3, 4):
            if len(sigs) < cycle_len * 2:
                continue

            last_cycle = sigs[-cycle_len:]
            prev_cycle = sigs[-cycle_len * 2 : -cycle_len]

            if last_cycle == prev_cycle:
                # Found exact repeating sequence! Check if it repeated 3 times
                if len(sigs) >= cycle_len * 3:
                    third_cycle = sigs[-cycle_len * 3 : -cycle_len * 2]
                    if prev_cycle == third_cycle:
                        return cycle_len  # 3 repetitions: hard stall
                return cycle_len  # 2 repetitions: soft warning

        return None

    def evaluate(self, current_step: int) -> ConvergenceStatus:
        """Evaluates convergence across all 4 heuristics (Hermes & Claude Code Parity)."""
        from core.prompt_loader import load_config_yaml
        g_cfg = load_config_yaml("convergence/guidance.yaml", default={})

        # 1. Goal Satisfaction: Modifications made AND verification tests passed
        if self.mutations_count > 0 and self.last_test_passed and self.test_verified_count >= 1:
            # Check if current action is a wandering inspection post-verification
            if self.history and self.history[-1].risk == "read_only":
                logger.info("[Convergence] Goal satisfaction detected: modifications verified by tests. Triggering convergence.")
                default_goal = (
                    "[MISSION CONVERGED]: You have applied the required modifications and verified correctness with physical tests. "
                    "Do not run further exploration tools. Deliver your complete, helpful report to the user now."
                )
                return ConvergenceStatus(
                    is_converged=True,
                    should_nudge=True,
                    guidance=g_cfg.get("goal_satisfaction", default_goal),
                    reason="verified_complete",
                    phase="CONVERGED"
                )

        # 2. Multi-Tool Cycle Detection (N-cycles)
        cycle_len = self.detect_multi_tool_cycles()
        if cycle_len:
            # Check repetition count
            sigs = [(a.tool_name, a.target) for a in self.history]
            if len(sigs) >= cycle_len * 3 and sigs[-cycle_len:] == sigs[-cycle_len * 2 : -cycle_len] == sigs[-cycle_len * 3 : -cycle_len * 2]:
                logger.warning(f"[Convergence] Hard cyclic stall detected ({cycle_len}-tool loop repeated 3x). Triggering convergence.")
                default_stag = (
                    f"[STAGNATION NOTICE]: A repeating {cycle_len}-step cycle was detected without progress. "
                    "Stop calling inspection tools and conclude your task with your best assessment or report."
                )
                template_stag = g_cfg.get("stagnation_notice", default_stag)
                try:
                    stag_guidance = template_stag.format(cycle_len=cycle_len)
                except Exception:
                    stag_guidance = default_stag

                return ConvergenceStatus(
                    is_converged=True,
                    should_nudge=True,
                    guidance=stag_guidance,
                    reason="cyclic_stall",
                    phase=self.phase
                )
            else:
                logger.info(f"[Convergence] Soft cyclic pattern detected ({cycle_len}-tool loop). Nudging model.")
                tool_seq = ', '.join(a[0] for a in sigs[-cycle_len:])
                default_warn = (
                    f"[CYCLE WARNING]: You appear to be repeating a {cycle_len}-step sequence ({tool_seq}). "
                    "Shift your approach or synthesize your conclusions instead of repeating actions."
                )
                template_warn = g_cfg.get("cycle_warning", default_warn)
                try:
                    warn_guidance = template_warn.format(cycle_len=cycle_len, tool_seq=tool_seq)
                except Exception:
                    warn_guidance = default_warn

                return ConvergenceStatus(
                    is_converged=False,
                    should_nudge=True,
                    guidance=warn_guidance,
                    reason="cyclic_pattern",
                    phase=self.phase
                )

        # 3. Information Saturation (repeated inspection of already-inspected entities)
        if self.redundant_inspections >= 4:
            logger.info(f"[Convergence] Information saturation detected ({self.redundant_inspections} redundant inspections). Triggering convergence.")
            default_sat = (
                "[INFORMATION SATURATION]: You have repeatedly examined the same workspace targets without uncovering new data. "
                "Conclude your turn now and deliver your complete findings or solution to the user."
            )
            return ConvergenceStatus(
                is_converged=True,
                should_nudge=True,
                guidance=g_cfg.get("information_saturation", default_sat),
                reason="information_saturated",
                phase=self.phase
            )
        elif self.redundant_inspections >= 2:
            default_sat_n = (
                "[SATURATION NOTICE]: You are inspecting files or targets you have already reviewed. "
                "Proceed to implement your changes or synthesize your response."
            )
            return ConvergenceStatus(
                is_converged=False,
                should_nudge=True,
                guidance=g_cfg.get("saturation_notice", default_sat_n),
                reason="diminishing_returns",
                phase=self.phase
            )

        # 4. Plan Mode / Read-Only Exploration Budget
        if self.read_only or self.phase == "EXPLORING":
            if current_step >= 8:
                default_exh = (
                    "[INSPECTION BUDGET EXHAUSTION]: You have conducted extensive exploration across 8+ steps. "
                    "Synthesize all gathered context and formulate your complete plan or response now."
                )
                return ConvergenceStatus(
                    is_converged=True,
                    should_nudge=True,
                    guidance=g_cfg.get("inspection_budget_exhaustion", default_exh),
                    reason="inspection_budget_exhausted",
                    phase=self.phase
                )
            elif current_step >= 5:
                default_exp = (
                    "[EXPLORATION GUIDANCE]: You have inspected multiple targets. Ensure you are ready to "
                    "synthesize your conclusions rather than continuing open-ended searches."
                )
                return ConvergenceStatus(
                    is_converged=False,
                    should_nudge=True,
                    guidance=g_cfg.get("exploration_guidance", default_exp),
                    reason="inspection_sufficient",
                    phase=self.phase
                )

        return ConvergenceStatus(
            is_converged=False,
            should_nudge=False,
            guidance=None,
            reason="progressing",
            phase=self.phase
        )
