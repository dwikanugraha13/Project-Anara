"""
build_mode_runner.py — Build Mode Execution Runner for Project Anara.
Handles approved plan execution, mutating tool calls, progress streaming,
conversation logging, artifact auto-dispatch, and background self-improvement triggers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional, List, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.channel_adapter import ChannelRequest, ChannelResponse

logger = logging.getLogger("anara.build_mode_runner")


async def execute_build_mode(
    session_id: int,
    user_prompt: str,
    req: Any,
    progress_callback: Optional[Callable[[str], Any]] = None,
    pending_tool_call: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    token_callback: Optional[Callable[[str], Any]] = None,
    **kwargs: Any,
) -> Any:
    """Executes the approved plan in Build Mode with system-reminder mode injection."""
    from core.session_manager import session_state_manager
    from core.channel_adapter import _ACTIVE_CHANNEL_CONTEXT

    current_task = asyncio.current_task()
    if current_task:
        session_state_manager.register_active_task(req.channel, req.channel_id, current_task)
    token_ctx = _ACTIVE_CHANNEL_CONTEXT.set({
        "channel": req.channel,
        "channel_id": req.channel_id,
        "user_id": req.user_id,
        "sender_name": req.sender_name
    })

    try:
        return await execute_build_mode_core(
            session_id=session_id,
            user_prompt=user_prompt,
            req=req,
            progress_callback=progress_callback,
            pending_tool_call=pending_tool_call,
            plan=plan,
            token_callback=token_callback,
            **kwargs
        )
    finally:
        if current_task:
            session_state_manager.unregister_active_task(req.channel, req.channel_id, current_task)
        _ACTIVE_CHANNEL_CONTEXT.reset(token_ctx)


async def execute_build_mode_core(
    session_id: int,
    user_prompt: str,
    req: Any,
    progress_callback: Optional[Callable[[str], Any]] = None,
    pending_tool_call: Optional[Dict[str, Any]] = None,
    plan: Optional[Dict[str, Any]] = None,
    token_callback: Optional[Callable[[str], Any]] = None,
    **kwargs: Any,
) -> Any:
    from core.agent import anara_agent
    anara_agent.set_active_session_id(session_id)
    from tools.artifact_tools import clear_turn_artifacts, get_turn_artifacts
    clear_turn_artifacts()

    from core.session_manager import session_state_manager
    from core.prompt_assembler import PromptAssembler
    from core.context_compactor import ContextCompactor
    from memory import memory_engine
    from core.message_chunker import _format_tool_progress_message
    from core.action_rationale import synthesize_action_rationale
    from core.media_dispatcher import _auto_dispatch_artifacts_to_channel, _extract_and_dispatch_media_tags
    from providers import call_universal_chat_model, get_active_model_id
    from core.channel_adapter import ChannelResponse

    if not pending_tool_call and plan:
        pending_tool_call = plan.get("pending_tool_call")

    resolved_task = str((plan or {}).get("original_prompt") or user_prompt)

    if progress_callback:
        try:
            msg = f"🔨 {resolved_task[:60]}..."
            if asyncio.iscoroutinefunction(progress_callback):
                await progress_callback(msg)
            else:
                progress_callback(msg)
        except Exception:
            pass

    ws_tree = anara_agent.get_workspace_tree_shallow(session_id=session_id)
    sys_prompt = await asyncio.to_thread(PromptAssembler.assemble,
        mode="build",
        speaker_name=req.sender_name,
        workspace_tree=ws_tree,
        is_chat_mode=True,
        session_type="chat",
        user_task=resolved_task,
        channel=req.channel,
        session_id=session_id,
    )

    tools_used: List[str] = []

    def _track_tool(evt: Dict[str, Any]):
        t_name = evt.get("tool_name")
        if t_name and t_name not in tools_used:
            tools_used.append(t_name)
        status = evt.get("status")
        if status == "running" and t_name:
            cid = evt.get("call_id") or f"bld_{uuid.uuid4().hex[:10]}"
            evt["call_id"] = cid
            try:
                session_state_manager.persist_tool_call_start(
                    session_id=session_id,
                    channel=req.channel,
                    channel_id=req.channel_id,
                    tool_name=t_name,
                    tool_args=evt.get("args") or evt.get("tool_args") or {},
                    call_id=cid
                )
            except Exception:
                pass
        elif status == "done" and t_name:
            cid = evt.get("call_id")
            if cid:
                try:
                    session_state_manager.persist_tool_call_result(
                        call_id=cid,
                        result_summary=evt.get("summary") or evt.get("detail") or "",
                        is_error=bool(evt.get("is_error", False))
                    )
                except Exception:
                    pass
        if progress_callback:
            msg = _format_tool_progress_message(evt)
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    asyncio.create_task(progress_callback(msg))
                else:
                    progress_callback(msg)
            except Exception:
                pass

    all_history = memory_engine.get_recent_conversations(
        limit=25,
        speaker_name=req.sender_name,
        session_id=session_id
    )
    dialogue_context = ContextCompactor.compact_history(all_history, verbatim_turns=5)

    t_name = ""
    t_args: Dict[str, Any] = {}

    if pending_tool_call:
        t_name = pending_tool_call.get("tool", "")
        t_args = pending_tool_call.get("arguments", {}) or {}
        from tools import dispatch_tool_call
        cid = session_state_manager.persist_tool_call_start(
            session_id=session_id,
            channel=req.channel,
            channel_id=req.channel_id,
            tool_name=t_name,
            tool_args=t_args,
        )
        if progress_callback:
            msg = _format_tool_progress_message({"tool_name": t_name, "status": "running", "detail": str(t_args)[:80]})
            try:
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(msg)
                else:
                    progress_callback(msg)
            except Exception:
                pass

        tool_res = await dispatch_tool_call(t_name, t_args, read_only=False)
        is_err = isinstance(tool_res, dict) and tool_res.get("status") == "error"
        summary_str = (tool_res.get("message") or tool_res.get("summary") or "") if isinstance(tool_res, dict) else str(tool_res)
        session_state_manager.persist_tool_call_result(
            call_id=cid,
            result_summary=summary_str,
            is_error=is_err
        )
        if t_name not in tools_used:
            tools_used.append(t_name)

        if progress_callback:
            try:
                summary_str = (tool_res.get("message") or tool_res.get("summary") or "")[:120] if isinstance(tool_res, dict) else str(tool_res)[:120]
                msg = _format_tool_progress_message({"tool_name": t_name, "status": "done", "summary": summary_str})
                if asyncio.iscoroutinefunction(progress_callback):
                    await progress_callback(msg)
                else:
                    progress_callback(msg)
            except Exception:
                pass

        from core.prompt_loader import load_prompt
        tool_instruction = load_prompt("channel/tool_summary").strip()
        effective_prompt = (
            f"{dialogue_context}"
            f"Tool '{t_name}' was executed on the host system with the following observation:\n"
            f"```json\n{json.dumps(tool_res, ensure_ascii=False)}\n```\n\n"
            f"User request: \"{resolved_task}\"\n\n"
            f"{tool_instruction}"
        )
    elif dialogue_context:
        effective_prompt = f"{dialogue_context}User: {resolved_task}"
    else:
        effective_prompt = resolved_task

    reply = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=effective_prompt,
        system_instruction=sys_prompt,
        max_tokens=None,
        temperature=0.6,
        read_only=False,
        progress_cb=_track_tool,
        token_cb=token_callback,
        intercept_mutating_tools=False,
        platform=req.channel,
    )

    if isinstance(reply, str):
        from providers.caller import _clean_model_chat_text
        cleaned = _clean_model_chat_text(reply)
        if not cleaned or '"action": "tool_call"' in cleaned or '<tool_call>' in cleaned:
            try:
                user_task_prompt = resolved_task or user_prompt or req.text.strip()
                final_reply = await synthesize_action_rationale(
                    tool_name=t_name if pending_tool_call else "execution",
                    tool_args=t_args if pending_tool_call else {},
                    prompt=user_task_prompt
                )
                final_reply = _clean_model_chat_text(final_reply)
            except Exception:
                final_reply = ""
            if not final_reply:
                final_reply = f"Completed action '{resolved_task}'."
        else:
            final_reply = cleaned
    else:
        final_reply = str(reply) if reply else f"Completed action '{resolved_task}'."

    # Extract native MEDIA: and [[audio_as_voice]] directives (Anara Omnichannel Standard)
    final_reply = await _extract_and_dispatch_media_tags(req.channel, req.channel_id, final_reply)

    memory_engine.log_conversation(
        user_text=resolved_task or user_prompt or req.text.strip(),
        ai_text=final_reply,
        speaker_name=req.sender_name,
        session_id=session_id
    )

    turn_artifacts = get_turn_artifacts()
    if turn_artifacts:
        await _auto_dispatch_artifacts_to_channel(req.channel, req.channel_id, turn_artifacts)

    # Spawn background self-improvement review (Anara Native Omnichannel)
    try:
        from core.self_improvement import self_improvement_reviewer
        async def _build_receipt_cb(receipt_text: str):
            try:
                from integrations.manager import channel_manager
                await channel_manager.send_message(channel=req.channel, target_id=req.channel_id, text=f"<i>{receipt_text}</i>")
            except Exception:
                pass

        asyncio.create_task(
            self_improvement_reviewer.run_review_async(
                user_prompt=resolved_task or user_prompt or req.text.strip(),
                ai_response=final_reply,
                tools_used=tools_used,
                channel=req.channel,
                channel_id=req.channel_id,
                summary_callback=_build_receipt_cb,
            )
        )
    except Exception as e_si:
        logger.debug(f"[ChannelGateway] Self-improvement trigger error: {e_si}")

    return ChannelResponse(
        text=final_reply,
        session_id=session_id,
        mode="build",
        plan_pending=False,
        tools_used=tools_used,
        attachments=turn_artifacts,
        status="success"
    )
