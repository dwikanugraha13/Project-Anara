"""
stream_rules.py — Time-Traveling Stream Rules (TTSR) Engine for Project Anara.
Parity with Oh My Pi (can1357/oh-my-pi TTSR Architecture).
Dormant rules monitor the live token stream with zero context cost.
If the model drifts off-script, matches a forbidden pattern, or roleplays tool execution,
the stream is aborted mid-token, the offending text is scrubbed, and a targeted
intervention rule is injected into the turn for immediate course-correction.
"""

import logging
import re
from typing import Dict, List, NamedTuple, Optional, Tuple

logger = logging.getLogger(__name__)


class StreamRule(NamedTuple):
    name: str
    pattern: re.Pattern
    intervention_message: str
    min_chars: int = 15


class StreamRuleViolation(Exception):
    def __init__(self, rule_name: str, message: str, matched_text: str):
        super().__init__(f"[TTSR Violation: {rule_name}] {message}")
        self.rule_name = rule_name
        self.message = message
        self.matched_text = matched_text


class TimeTravelingStreamRulesEngine:
    """
    Evaluates dormant rules on streaming token accumulators.
    Zero token cost on normal turns; triggers instantaneous course correction on drift.
    """

    def __init__(self):
        self.accumulated = ""
        self._rules: List[StreamRule] = [
            # 1. Simulated Tool Roleplay (Model describing actions in prose instead of calling tools)
            StreamRule(
                name="no_simulated_tools",
                pattern=re.compile(
                    r"\*(?:\((?:sedang |mulai |mencoba )?(?:menjalankan|mengeksekusi|eksekusi|executing|running)\s+(?:perintah|command|tool|skrip|script)[^\)]*\)|\b(?:menjalankan|mengeksekusi|eksekusi|executing|running)\s+(?:perintah|command|tool|skrip|script)\b[^\*]+)\*",
                    re.IGNORECASE
                ),
                intervention_message=(
                    "[STREAM RULE INTERVENTION]: You roleplayed or simulated tool execution in text. "
                    "You MUST invoke the actual native tool call instead of writing execution prose."
                ),
                min_chars=12
            ),
            # 2. Destructive Mass Wipe Injection
            StreamRule(
                name="no_destructive_wipe",
                pattern=re.compile(
                    r"(?:\brm\s+-(?:[a-z]*r[a-z]*\s+-[a-z]*f[a-z]*|[a-z]*f[a-z]*\s+-[a-z]*r[a-z]*|[rf]{1,2})\s+[/~]|\b(?:rmdir|del)\s+/[sS]\s+[/~]|\bRemove-Item\s+-Recurse\s+-Force\s+\*|\bgit\s+reset\s+--hard\s+HEAD~)",
                    re.IGNORECASE
                ),
                intervention_message=(
                    "[STREAM RULE INTERVENTION - SECURITY]: Destructive workspace wipe command pattern intercepted mid-stream. "
                    "All destructive wiping is strictly forbidden."
                ),
                min_chars=10
            ),
            # 3. Autoregressive Stutter Loop Degeneration (Identical phrase repeated 4+ times)
            StreamRule(
                name="no_stutter_loop",
                pattern=re.compile(
                    r"(.{15,60}?)(?:\s*\1){3,}",
                    re.DOTALL
                ),
                intervention_message=(
                    "[STREAM RULE INTERVENTION]: Autoregressive repetition loop detected mid-stream. "
                    "Break the repetition and output your synthesized conclusion directly."
                ),
                min_chars=60
            ),
        ]

    def reset(self) -> None:
        self.accumulated = ""

    def feed(self, delta: str) -> Optional[StreamRuleViolation]:
        """
        Feeds a streaming delta. If a dormant rule triggers, returns a StreamRuleViolation.
        Immediately scrubs the offending pattern to prevent repetitive cascade matches.
        """
        if not delta:
            return None
        self.accumulated += delta
        if len(self.accumulated) < 15:
            return None

        # Check rules
        for rule in self._rules:
            if len(self.accumulated) >= rule.min_chars:
                m = rule.pattern.search(self.accumulated)
                if m:
                    matched = m.group(0)
                    logger.warning(f"[TTSR] Rule '{rule.name}' triggered on token stream: '{matched[:60]}'")
                    # Time-traveling scrub: remove the matched offending snippet immediately
                    self.accumulated = self.accumulated.replace(matched, "").strip()
                    return StreamRuleViolation(
                        rule_name=rule.name,
                        message=rule.intervention_message,
                        matched_text=matched
                    )
        return None

    def scrub(self, violation: StreamRuleViolation) -> str:
        """Removes the matched violation from the accumulated text."""
        if violation.matched_text and violation.matched_text in self.accumulated:
            return self.accumulated.replace(violation.matched_text, "").strip()
        return self.accumulated.strip()
