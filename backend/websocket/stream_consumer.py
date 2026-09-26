"""
agent_runner.py — Autonomous WebSocket Agent Runner for Project Anara.
Hermes Agent Parity:
Delegates multi-step ReAct turn execution directly to AnaraExecutionRunner,
streaming TurnEvents (chunks, thoughts, tool progress, approval prompts)
directly over WebSocket to the Web Studio & 3D Avatar frontend.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time as _time
from typing import Any, Callable, Dict, List, Optional
from fastapi import WebSocket

from memory import memory_engine
from core import (
    key_manager,
    ModelCapabilityRegistry,
    anara_agent,
    needs_plan,
    is_explicit_plan_approval,
)
from core.runner import AnaraExecutionRunner, TurnEvent
from providers import get_active_model_id
from cognition import (
    generate_visual_projection,
    EmotionEngine,
    get_soul_prompt,
)
import shared_state
from shared_state import chat_diagnostics

logger = logging.getLogger("anara.websocket.agent")


class AgentRunner:
    """Manages conversational WebSocket turns and bridges frontend to AnaraExecutionRunner."""

    def __init__(
        self,
        websocket: WebSocket,
        emotion_engine: EmotionEngine,
        get_current_speaker: Callable[[], str],
        get_active_session_id: Callable[[], Optional[int]],
        set_active_session_id: Callable[[int], None],
        ensure_session: Callable[[], int],
        log_turn: Callable[..., int],
        push_emotion: Callable[[str, str, float], Any],
        dance_blocked: Callable[[], bool],
        activate_dance_llm_turn: Callable[[str], Any],
    ):
        self.websocket = websocket
        self.emotion_engine = emotion_engine
        self.get_current_speaker = get_current_speaker
        self.get_active_session_id = get_active_session_id
        self.set_active_session_id = set_active_session_id
        self.ensure_session = ensure_session
        self.log_turn = log_turn
        self.push_emotion = push_emotion
        self.dance_blocked = dance_blocked
        self.activate_dance_llm_turn = activate_dance_llm_turn

        self.current_turn_user_text = ""
        self.agent_mode = "plan"
        self.last_visual_projection_ts = 0.0
        self.last_visual_image_count = 0
        self.visual_projected_this_turn = False
        self.prev_turn_user_text = ""
        self.prev_turn_ai_reply = ""

    async def run_text_chat_turn(self, data: Dict[str, Any]):
        try:
            text = data.get("text", "")
            req_agent_mode = data.get("agent_mode", "plan")
            req_interaction_mode = data.get("interaction_mode", "chat")

            if req_interaction_mode == "voice":
                sel_model_for_check = data.get("model_id") or get_active_model_id()
                if not ModelCapabilityRegistry.supports_voice(sel_model_for_check):
                    err_msg = (
                        f"Model '{sel_model_for_check}' does not support real-time audio input/output. "
                        "Please select a live-preview model in Voice Mode."
                    )
                    logger.warning(f"[Chat] {err_msg}")
                    chat_diagnostics["last_error"] = err_msg
                    chat_diagnostics["last_stage"] = "voice_capability_missing"
                    await self.websocket.send_json({"type": "error", "data": err_msg})
                    return

            if text and re.match(r'^\s*\{.*"type"\s*:', text):
                return

            if not text:
                return

            self.current_turn_user_text = text
            logger.info(f"[Text Chat Turn] Received: {text!r} from speaker {self.get_current_speaker()!r}")

            # 1. Sync session ID
            req_sid = data.get("sessionId")
            if req_sid:
                try:
                    parsed_sid = int(req_sid)
                    if parsed_sid > 0:
                        self.set_active_session_id(parsed_sid)
                        anara_agent.set_active_session_id(parsed_sid)
                except (TypeError, ValueError):
                    pass

            sid = self.ensure_session()
            await self.websocket.send_json({
                "type": "session_id_sync",
                "sessionId": sid
            })

            # 2. Resolve session context & mode (Hermes Model-Driven Parity: Zero Pre-Turn Keyword Guessing)
            session_obj = memory_engine.get_session(sid) if sid else None
            session_type = (session_obj.get("session_type") or "chat") if session_obj else "chat"
            session_mode = (session_obj.get("session_mode") or ("explicit_plan_build" if session_type == "code" else "conversational")) if session_obj else "conversational"

            # Check if there is an active pending action awaiting approval
            from core.session_manager import session_state_manager
            active_pending = session_state_manager.get_pending("web_studio", str(sid))
            is_approved = False
            if active_pending:
                norm_text = text.lower().strip()
                is_approved = is_explicit_plan_approval(norm_text)

            if session_mode == "explicit_plan_build":
                if is_approved:
                    agent_mode = "build"
                    logger.info("[Agent Mode] Pending plan approved in Code Studio -> Switch to BUILD MODE")
                else:
                    agent_mode = req_agent_mode if req_agent_mode in ("plan", "build") else "plan"
            else:
                if is_approved:
                    agent_mode = "build"
                    logger.info("[Agent Mode] Pending action approved in Conversational Mode -> Switch to BUILD MODE")
                elif needs_plan(text, session_mode="conversational"):
                    agent_mode = "plan"
                    logger.info("[Agent Mode] Complex/mutating request in Conversational Mode -> Switch to PLAN MODE")
                else:
                    agent_mode = "build"

            # 4. Core ReAct Turn Execution via AnaraExecutionRunner (Hermes Parity)
            reply_text = ""
            runner = AnaraExecutionRunner(
                session_id=sid,
                speaker_name=self.get_current_speaker(),
                platform="web_studio",
            )

            tools_used: List[str] = []
            selected_model = data.get("model_id") or get_active_model_id()
            chat_diagnostics["active_requests"] += 1
            chat_diagnostics["last_stage"] = f"generating with {selected_model}"
            chat_diagnostics["last_updated"] = _time.time()
            chat_diagnostics["last_error"] = None
            accumulated_chunks: List[str] = []

            try:
                async for event in runner.execute_turn_stream(
                    user_message=text,
                    requested_mode=agent_mode,
                    model_id=selected_model,
                    interaction_mode=req_interaction_mode,
                ):
                    if event.type == "chunk" and event.content:
                        accumulated_chunks.append(event.content)
                        await self.websocket.send_json({
                            "type": "transcript_partial",
                            "speaker": "output",
                            "delta": event.content,
                            "text": "".join(accumulated_chunks),
                            "is_final": False,
                        })
                    elif event.type == "thought" and (event.thought or event.content):
                        await self.websocket.send_json({
                            "type": "agent_thinking",
                            "text": event.thought or event.content,
                        })
                    elif event.type == "tool_start":
                        t_name = event.tool_name or "tool"
                        if t_name not in tools_used:
                            tools_used.append(t_name)
                        await self.websocket.send_json({
                            "type": "tool_progress",
                            "tool_name": t_name,
                            "status": "running",
                            "summary": f"Executing {t_name}...",
                            "icon": "terminal" if "command" in t_name or "shell" in t_name else "file",
                        })
                    elif event.type == "tool_result":
                        t_name = event.tool_name or "tool"
                        if t_name not in tools_used:
                            tools_used.append(t_name)
                        await self.websocket.send_json({
                            "type": "tool_progress",
                            "tool_name": t_name,
                            "status": "done",
                            "summary": str(event.tool_result)[:160] if event.tool_result else "Done",
                            "icon": "terminal" if "command" in t_name or "shell" in t_name else "file",
                        })
                    elif event.type == "need_approval":
                        await self.websocket.send_json({
                            "type": "plan_pending",
                            "plan_id": event.plan_id or "plan_pending",
                            "tool_name": event.tool_name,
                            "tool_args": event.tool_args or {},
                            "text": event.content or "Action plan requires confirmation before execution.",
                            "action_metadata": event.metadata,
                        })
                    elif event.type == "final_text":
                        reply_text = event.content or ""
                        await self.websocket.send_json({
                            "type": "transcript",
                            "data": reply_text,
                            "speaker": "output",
                            "is_final": True,
                        })
                    elif event.type == "error":
                        await self.websocket.send_json({
                            "type": "error",
                            "data": event.content,
                        })

                chat_diagnostics["active_requests"] = max(0, chat_diagnostics["active_requests"] - 1)
                chat_diagnostics["last_stage"] = "completed"

                if not reply_text and accumulated_chunks:
                    reply_text = "".join(accumulated_chunks).strip()

                if reply_text:
                    self.prev_turn_user_text = text
                    self.prev_turn_ai_reply = reply_text
                    try:
                        em = self.emotion_engine.analyze(reply_text, allow_dance=False)
                        if em:
                            await self.push_emotion(em["emotion"], em["gesture"], em["intensity"])
                    except Exception as em_err:
                        logger.debug(f"[Emotion] analyze error: {em_err}")

                try:
                    await self.websocket.send_json({"type": "turn_complete"})
                except Exception:
                    pass
                return

            except Exception as turn_err:
                logger.error(f"[AgentRunner] Turn stream execution error: {turn_err}", exc_info=True)
                chat_diagnostics["active_requests"] = max(0, chat_diagnostics["active_requests"] - 1)
                chat_diagnostics["last_error"] = str(turn_err)
                chat_diagnostics["last_stage"] = "error"
                try:
                    await self.websocket.send_json({"type": "error", "data": str(turn_err)})
                    await self.websocket.send_json({"type": "turn_complete"})
                except Exception:
                    pass
                return

        except asyncio.CancelledError:
            logger.info("[Text Chat] Turn cancelled by client interrupt.")
            chat_diagnostics["active_requests"] = max(0, chat_diagnostics["active_requests"] - 1)
            chat_diagnostics["last_stage"] = "interrupted"
            try:
                await self.websocket.send_json({"type": "turn_complete"})
            except Exception:
                pass
        except Exception as e_err:
            logger.error(f"[Text Chat Turn Error]: {e_err}", exc_info=True)
            chat_diagnostics["active_requests"] = max(0, chat_diagnostics["active_requests"] - 1)
            chat_diagnostics["last_error"] = str(e_err)
            chat_diagnostics["last_stage"] = "error"
            try:
                await self.websocket.send_json({"type": "error", "data": f"Error: {str(e_err)}"})
                await self.websocket.send_json({"type": "turn_complete"})
            except Exception:
                pass
