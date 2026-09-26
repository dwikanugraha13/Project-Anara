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


def _is_verifiable_code_target(target_path: str) -> bool:
    """
    Language-agnostic check determining if a modified target is executable code or configuration.
    Rules are loaded dynamically from verifier_rules.yaml (Zero hardcoding in Python).
    """
    clean_p = target_path.strip().replace("\\", "/")
    if not clean_p:
        return False
    from core.prompt_loader import load_config_yaml
    rules = load_config_yaml("convergence/verifier_rules.yaml", default={})
    non_code_exts = set(rules.get("non_code_extensions") or [])
    non_code_names = set(rules.get("non_code_filenames") or [])

    basename = os.path.basename(clean_p).lower()
    name_no_ext, ext = os.path.splitext(basename)
    if ext in non_code_exts:
        return False
    if not ext and name_no_ext in non_code_names:
        return False
    return True


def _is_verification_command(cmd: str) -> bool:
    """
    Dynamically determines if a shell command is an automated verification or test command.
    Zero hardcoded language runner lists: matches dynamically against detected repo verification
    commands or semantic test execution tokens.
    """
    clean_cmd = (cmd or "").strip().lower()
    if not clean_cmd:
        return False

    # 1. Match against dynamically detected repository test commands
    try:
        from core.agent import anara_agent
        from core.prompt_assembler import PromptAssembler
        root_p = anara_agent.get_project_repo_root()
        if root_p:
            snapshot = PromptAssembler.probe_git_worktree_snapshot(root_p)
            for line in snapshot.splitlines():
                if "- Project Verification Commands:" in line:
                    detected_cmds = [c.strip().lower() for c in line.split(":", 1)[1].split(",") if c.strip()]
                    if any(det in clean_cmd for det in detected_cmds):
                        return True
    except Exception:
        pass

    # 2. Semantic execution intent: check if command invokes a test/check/spec/lint sub-action
    return bool(re.search(r"\b(test|tests|check|spec|specs|lint)\b", clean_cmd))


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
                    # Staleness Tracking (Hermes mark_workspace_edited parity):
                    # Any new verifiable code mutation immediately renders prior test evidence stale!
                    if _is_verifiable_code_target(target):
                        self.last_test_passed = False

            # Check for verification commands dynamically (zero hardcoded runner tuples)
            if t_name in ("execute_cli_command", "terminal", "run_terminal_command"):
                if _is_verification_command(target):
                    self.phase = "VERIFYING"
                    sum_lower = summary.lower()
                    has_explicit_fail = bool(re.search(r"\b([1-9]\d*\s+failed|[1-9]\d*\s+errors?|failures?=[1-9]\d*)\b", sum_lower))
                    has_explicit_pass = bool(re.search(r"\b(passed|ok|success|0\s+failed)\b", sum_lower))

                    if not is_err and (has_explicit_pass or not has_explicit_fail):
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

    def evaluate_final_stop_gate(self, agent_mode: str = "build") -> Optional[str]:
        """
        Negative Verification Stop-Gate (Hermes Parity: turn_stop_gates.py & Claude Code Parity):
        Intercepts attempts to conclude a task with narrative text if code files were modified
        but no passing ground-truth verification test evidence was observed in this session.
        Returns: Synthetic nudge message if verification is missing, else None.
        """
        if self.read_only or agent_mode == "plan":
            return None

        # Check if verifiable code/config files were mutated (Language-Agnostic Negative Blacklist)
        verifiable_mutations = [
            t for t in self.modified_targets
            if _is_verifiable_code_target(t)
        ]

        # If verifiable code was mutated and NO fresh passing verification was observed:
        if verifiable_mutations and (self.test_verified_count == 0 or not self.last_test_passed):
            # Allow maximum 2 stop-gate nudges per turn to avoid indefinite deadlocks
            nudges = getattr(self, "_stop_gate_nudges", 0)
            if nudges >= 2:
                return None
            self._stop_gate_nudges = nudges + 1

            mutated_list = ", ".join(verifiable_mutations[:4])

            # Dynamically resolve project test command suggestion from active repository
            cmd_suggestion = ""
            try:
                from core.prompt_assembler import PromptAssembler
                from core.agent import anara_agent
                root_p = anara_agent.get_project_repo_root()
                if root_p:
                    snapshot = PromptAssembler.probe_git_worktree_snapshot(root_p)
                    for line in snapshot.splitlines():
                        if "- Project Verification Commands:" in line:
                            detected = line.split(":", 1)[1].strip()
                            if detected:
                                cmd_suggestion = f" (detected: {detected})"
                                break
            except Exception:
                pass

            from core.prompt_loader import load_config_yaml
            rules = load_config_yaml("convergence/verifier_rules.yaml", default={})
            nudge_tmpl = rules.get(
                "default_stop_gate_nudge",
                "[VERIFICATION STOP-GATE]: You modified files ({mutated_list}) during this session, "
                "but have not yet executed ground-truth verification tests to confirm they work without regressions. "
                "Please run the project's verification command{cmd_suggestion} "
                "and inspect the real output before delivering your final completion report."
            )
            return nudge_tmpl.format(mutated_list=mutated_list, cmd_suggestion=cmd_suggestion)

        return None
