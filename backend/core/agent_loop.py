"""
agent_loop.py — Transport-Agnostic Core ReAct Turn Loop for Project Anara.
Anara Standard Core Conversation Loop:
Provides a single, decoupled agent turn execution engine reusable across
WebSocket, CLI REPL, Telegram, WhatsApp, Discord, Slack, and Background Cron tasks.
Delegates to AnaraExecutionRunner as the single unified execution engine.
"""

import logging
from typing import Any, Callable, Dict, Optional

from core.runner import AnaraExecutionRunner, AgentTurnResult

logger = logging.getLogger(__name__)


async def run_agent_turn(
    user_text: str,
    session_id: Optional[int] = None,
    speaker_name: Optional[str] = None,
    requested_mode: str = "plan",
    model_id: Optional[str] = None,
    stream_callback: Optional[Callable[[str], Any]] = None,
    tool_progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    thinking_callback: Optional[Callable[[str], Any]] = None,
    platform: Optional[str] = None,
) -> AgentTurnResult:
    """
    Executes a single unified ReAct conversation turn (Anara Standard).
    Transport-agnostic: Works natively across WebSocket, CLI, Telegram, WhatsApp, Discord, Slack, and Cron.
    """
    runner = AnaraExecutionRunner(
        session_id=session_id,
        speaker_name=speaker_name,
        platform=platform,
    )
    return await runner.execute_turn(
        user_message=user_text,
        requested_mode=requested_mode,
        model_id=model_id,
        stream_callback=stream_callback,
        tool_progress_callback=tool_progress_callback,
        thinking_callback=thinking_callback,
    )

