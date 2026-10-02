"""
self_improvement.py — Autonomous Lifelong Learning & Background Review Engine for Project Anara.

Spawns an asynchronous background review task after conversation turns to evaluate:
1. User Profile updates (USER.md): Persona, preferences, communication style, explicit expectations.
2. Environment Facts (MEMORY.md): Durable tool quirks, project paths, platform configurations.
3. Skill Evolution (SKILL.md): Creating reusable procedures or patching existing skills in-place.

Emits clean '💾 Self-improvement review: ...' receipt upon successful mutation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """You are Anara's Autonomous Background Self-Improvement Reviewer.
Your role is to inspect the completed conversation turn and determine if any durable user preference, environment fact, or procedural skill must be learned, updated, or patched.

### TARGET 1: MEMORY SYSTEM
Pick the right store for each fact:
• USER.md (target='user'): Who the user is — persona, preferences, communication/work style (e.g. 'gaul santai, kasual, lu-gue'), personal details, and behavioral expectations.
• MEMORY.md (target='memory'): Facts about the ENVIRONMENT — tool quirks, project conventions, config gotchas, ports, and paths.

One fact goes to ONE store, never both.

### TARGET 2: SKILL SYSTEM
A skill is the procedure for doing a class of task the most efficient way to THIS user's specifications:
• Steps in order with concrete tools/commands.
• Pitfalls: generalizable rule + one clause of WHY.
• If a skill already exists that covers the topic, PATCH it in-place rather than creating a duplicate.
• If a new class of task was solved, CREATE a new skill.

### WHAT NOT TO CAPTURE
• Environment-dependent transient glitches (network timeout, temporary connection refusal).
• Negative tool claims ('tool X does not work').
• One-off casual chatter without durable technical or preference value.

Respond strictly with valid JSON conforming to this schema (or empty arrays if nothing to update):
{
  "memory_actions": [
    {
      "target": "user" | "memory",
      "action": "add" | "replace",
      "content": "Full new fact or entry text",
      "old_text": "Substring to locate entry if replacing"
    }
  ],
  "skill_actions": [
    {
      "action": "patch",
      "name": "Exact skill name or slug to patch",
      "old_string": "Exact text inside SKILL.md to replace",
      "new_string": "Replacement text"
    },
    {
      "action": "create",
      "name": "Concise skill name",
      "category": "devops" | "coding" | "omnichannel" | "system",
      "description": "Trigger description <= 200 chars ending with period.",
      "procedure_steps": ["Step 1", "Step 2"],
      "trigger_keywords": ["keyword1", "keyword2"]
    }
  ]
}
If nothing is worth saving or patching, return:
{"memory_actions": [], "skill_actions": []}
"""


def _extract_review_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = text.strip()
    if cleaned.lower().startswith("json"):
        cleaned = cleaned[4:].strip()

    # If outer object braces were stripped, re-wrap before looking for braces
    if not cleaned.startswith("{") and ("memory_actions" in cleaned or "skill_actions" in cleaned):
        cleaned = "{" + cleaned.rstrip(" ,;}") + "}"
        if cleaned.endswith('"skill_actions":}'):
            cleaned = cleaned[:-1] + " []}"

    start = cleaned.find("{")
    if start == -1:
        return None
    candidate = cleaned[start:].strip()

    # Try standard json parse first
    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Try candidate auto-closing
    if candidate.endswith('"skill_actions":'):
        candidate += " []}"
    elif candidate.count("{") > candidate.count("}"):
        candidate = candidate.rstrip(" ,;") + ("}" * (candidate.count("{") - candidate.count("}")))

    try:
        data = json.loads(candidate)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    from providers.caller import _robust_parse_json, _extract_json_balanced
    for cand, _, _ in _extract_json_balanced(candidate):
        p = _robust_parse_json(cand)
        if isinstance(p, dict):
            return p
    return _robust_parse_json(candidate)


class SelfImprovementReviewer:
    """Orchestrates background self-improvement reviews with native Anara receipts."""

    @staticmethod
    async def run_review_async(
        user_prompt: str,
        ai_response: str,
        tools_used: Optional[List[str]] = None,
        tool_summaries: Optional[List[str]] = None,
        channel: Optional[str] = None,
        channel_id: Optional[str] = None,
        summary_callback: Optional[Callable[[str], Any]] = None,
    ) -> List[str]:
        """
        Executes background review pass for the recent turn.
        Returns a list of action summary strings (e.g. ["Skill 'xyz' patched", "Memory updated"]).
        """
        # Skip trivial or empty turns
        clean_user = (user_prompt or "").strip()
        clean_ai = (ai_response or "").strip()
        if not clean_user or not clean_ai:
            return []

        # Filter out slash commands and raw system notices
        if clean_user.startswith(("/", "\\")) and not any(k in clean_user for k in ("persona", "workspace", "model")):
            return []

        try:
            from core.capabilities import get_fast_auxiliary_model
            from providers.caller import call_universal_chat_model, _robust_parse_json, _extract_json_balanced

            review_input = [
                f"### CONVERSATION TURN TO REVIEW:",
                f"USER: {clean_user[:2000]}",
                f"ANARA: {clean_ai[:3000]}",
            ]
            if tools_used:
                review_input.append(f"TOOLS USED: {', '.join(tools_used)}")
            if tool_summaries:
                review_input.append(f"TOOL OUTPUT HIGHLIGHTS:\n" + "\n".join(f"- {s[:250]}" for s in tool_summaries[:6]))

            eval_prompt = f"{REVIEW_SYSTEM_PROMPT}\n\n" + "\n".join(review_input)

            aux_model = get_fast_auxiliary_model()
            raw_eval = await asyncio.wait_for(
                call_universal_chat_model(
                    model_id=aux_model,
                    user_prompt=eval_prompt,
                    max_tokens=None,
                    temperature=0.2,
                    read_only=True,
                    platform="review",
                ),
                timeout=25.0,
            )

            if not raw_eval or not isinstance(raw_eval, str):
                return []

            data = _extract_review_json(raw_eval)
            if not data:
                return []

            actions_taken: List[str] = []

            # 1. Apply Memory Housekeeping
            from memory.file_memory import FileMemoryManager
            for m_act in data.get("memory_actions") or []:
                if not isinstance(m_act, dict):
                    continue
                act_type = str(m_act.get("action", "add")).lower()
                tgt = str(m_act.get("target", "memory")).lower()
                content = m_act.get("content")
                old_text = m_act.get("old_text")

                if not content:
                    continue

                res = FileMemoryManager.execute_memory_action(
                    action=act_type,
                    target=tgt,
                    content=content,
                    old_text=old_text,
                )
                if isinstance(res, dict) and res.get("status") == "success":
                    lbl = "User profile updated" if tgt in ("user", "profile") else "Memory updated"
                    actions_taken.append(lbl)

            # 2. Apply Skill Housekeeping
            from core.skill_library import skill_library
            for s_act in data.get("skill_actions") or []:
                if not isinstance(s_act, dict):
                    continue
                act_type = str(s_act.get("action", "")).lower()
                name = str(s_act.get("name", "")).strip()
                if not name:
                    continue

                if act_type == "patch":
                    old_str = s_act.get("old_string")
                    new_str = s_act.get("new_string")
                    if old_str and new_str:
                        res = skill_library.patch_skill(
                            name_or_slug=name,
                            old_string=old_str,
                            new_string=new_str,
                        )
                        if isinstance(res, dict) and res.get("ok"):
                            actions_taken.append(f"Skill '{res.get('name', name)}' patched")

                elif act_type == "create":
                    cat = s_act.get("category", "coding")
                    desc = s_act.get("description", f"Procedural workflow for {name}.")
                    steps = s_act.get("procedure_steps") or [f"Execute workflow for {name}."]
                    triggers = s_act.get("trigger_keywords") or [name.lower()]

                    res = skill_library.save_skill(
                        name=name,
                        category=cat,
                        description=desc,
                        procedure_steps=steps,
                        trigger_keywords=triggers,
                        status="active",  # Self-improvement creates active skills immediately
                        learned=True,
                    )
                    if isinstance(res, dict) and res.get("file_path"):
                        actions_taken.append(f"Skill '{res.get('name', name)}' created")

            # 3. Publish receipt if actions were executed
            if actions_taken:
                # Deduplicate actions preserving order
                unique_actions = list(dict.fromkeys(actions_taken))
                summary_text = " · ".join(unique_actions)
                receipt = f"💾 Self-improvement review: {summary_text}"
                logger.info(f"[SelfImprovement] {receipt}")

                if summary_callback:
                    try:
                        r = summary_callback(receipt)
                        if asyncio.iscoroutine(r):
                            await r
                    except Exception as e_cb:
                        logger.debug(f"[SelfImprovement] Callback delivery error: {e_cb}")

                return unique_actions

            return []

        except asyncio.TimeoutError:
            logger.debug("[SelfImprovement] Background review timed out safely.")
            return []
        except Exception as e:
            logger.debug(f"[SelfImprovement] Background review skipped or failed: {e}")
            return []


self_improvement_reviewer = SelfImprovementReviewer()
