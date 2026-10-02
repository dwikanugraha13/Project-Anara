"""
approval_dispatcher.py — Unified Omnichannel Approval Resolution & Callback Dispatcher for Project Anara.
Validates approver authorization, updates FSM state, executes build mode,
dispatches clean responses, and sends generated artifacts across all channels.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("anara.approval_dispatcher")


def resolve_pending_plan_callback(
    plan_id: str,
    action: str,
    user_id: str,
    pending_plans_map: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Resolves an inline callback (e.g. Telegram button click) for a plan."""
    from core.session_manager import session_state_manager, ActionState
    pending_act = session_state_manager.get_pending_by_id(plan_id)
    if pending_act:
        if action == "approve":
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, plan_id, ActionState.EXECUTING)
            for k in list(pending_plans_map.keys()):
                if pending_plans_map[k].get("plan_id") == plan_id:
                    pending_plans_map.pop(k, None)
            return pending_act.to_dict()
        else:
            session_state_manager.resolve_action(pending_act.channel, pending_act.channel_id, plan_id, ActionState.REJECTED)
            for k in list(pending_plans_map.keys()):
                if pending_plans_map[k].get("plan_id") == plan_id:
                    pending_plans_map.pop(k, None)
            return None

    target_key = None
    target_plan = None
    for key, data in list(pending_plans_map.items()):
        if data.get("plan_id") == plan_id or key == plan_id:
            target_key = key
            target_plan = data
            break

    if not target_plan:
        logger.warning(f"[ChannelGateway] Pending plan {plan_id} not found or already consumed.")
        return None

    if action == "approve":
        target_plan["status"] = "executing"
        if target_key:
            pending_plans_map.pop(target_key, None)
        return target_plan
    else:
        if target_key:
            pending_plans_map.pop(target_key, None)
        return None


async def dispatch_channel_approval_resolution(
    channel: str,
    channel_id: str,
    plan_id: str,
    action: str,  # 'approve' | 'reject'
    user_id: str,
    sender_name: str = "User",
    message_id: Optional[str] = None,
    progress_callback: Optional[Callable[[str], Any]] = None,
    pending_plans_map: Optional[Dict[str, Any]] = None,
    execute_build_mode_fn: Optional[Callable[..., Any]] = None,
) -> Dict[str, Any]:
    """
    Unified Omnichannel Approval Dispatcher (Anara Standard).
    Centrally validates approver authorization, updates FSM state, executes build mode,
    dispatches clean responses, and sends generated artifacts.
    Shared across Telegram, WhatsApp, Discord, Slack, and Web Studio (Zero Code Duplication).
    """
    from core.session_manager import session_state_manager, ActionState
    from core.security import is_authorized_approver
    from core.action_rationale import synthesize_channel_notice
    from integrations.manager import channel_manager
    from integrations.platform_registry import platform_registry

    if pending_plans_map is None:
        from core.channel_adapter import _PENDING_PLANS
        pending_plans_map = _PENDING_PLANS

    if execute_build_mode_fn is None:
        from core.channel_adapter import _execute_build_mode
        execute_build_mode_fn = _execute_build_mode

    clean_chan = (channel or "telegram").lower().strip()
    clean_action = (action or "").strip()

    # Dynamic model-driven intent classification (zero static keyword gates)
    if clean_action.lower() in ("approve", "1", "yes", "y"):
        norm_action = "approve"
    elif clean_action.lower() in ("reject", "deny", "cancel", "0", "n", "no"):
        norm_action = "reject"
    else:
        from core.plan_detector import is_explicit_plan_approval
        norm_action = "approve" if is_explicit_plan_approval(clean_action) else "reject"

    pending_act = session_state_manager.get_pending_by_id(plan_id)
    plan_dict = pending_act.to_dict() if pending_act else pending_plans_map.get(f"{clean_chan}_{channel_id}")

    if not pending_act and not plan_dict:
        logger.warning(f"[OmnichannelGateway] Action #{plan_id} on {clean_chan} not found or expired.")
        exp_text = await synthesize_channel_notice("expired", channel=clean_chan)
        rendered = platform_registry.render_notice_payload(clean_chan, "expired", exp_text)
        if clean_chan == "telegram" and message_id:
            try:
                from integrations.telegram.client import edit_telegram_message
                await edit_telegram_message(chat_id=channel_id, message_id=int(message_id), text=rendered.get("text", exp_text), reply_markup=None)
            except Exception as e:
                logger.debug(f"[OmnichannelGateway] Telegram message edit failed: {e}. Falling back to send_message.")
                await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", exp_text))
        else:
            await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", exp_text))
        return {"status": "expired", "message": exp_text}

    target_user = plan_dict.get("user_id") if plan_dict else (pending_act.user_id if pending_act else user_id)
    session_id = plan_dict.get("session_id", 0) if plan_dict else (pending_act.session_id if pending_act else 0)

    # 1. Reject flow
    if norm_action != "approve":
        logger.info(f"[OmnichannelGateway] User rejected action #{plan_id} on {clean_chan}.")
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.REJECTED)
        session_state_manager.clear_pending(clean_chan, channel_id)
        pending_plans_map.pop(f"{clean_chan}_{channel_id}", None)

        task_desc = (plan_dict.get("original_prompt") or plan_dict.get("tool_name") or "") if plan_dict else ""
        cancel_msg = await synthesize_channel_notice("rejected", channel=clean_chan, task_description=task_desc)
        rendered = platform_registry.render_notice_payload(clean_chan, "rejected", cancel_msg)
        if clean_chan == "telegram" and message_id:
            try:
                from integrations.telegram.client import edit_telegram_message
                await edit_telegram_message(chat_id=channel_id, message_id=int(message_id), text=rendered.get("text", cancel_msg), reply_markup=None)
            except Exception as e:
                logger.debug(f"[OmnichannelGateway] Telegram message edit failed: {e}. Falling back to send_message.")
                await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", cancel_msg))
        else:
            await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", cancel_msg))
        return {"status": "rejected", "message": cancel_msg}

    # 2. Approve flow - Verify authorization
    if not is_authorized_approver(user_id=user_id, plan_owner_id=target_user or user_id, channel=clean_chan):
        logger.warning(f"[OmnichannelGateway] User {user_id} unauthorized to approve #{plan_id} on {clean_chan}.")
        denied_msg = await synthesize_channel_notice("unauthorized", channel=clean_chan, user_id=user_id)
        rendered = platform_registry.render_notice_payload(clean_chan, "unauthorized", denied_msg)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", denied_msg))
        return {"status": "denied", "message": denied_msg}

    # 3. Transition to EXECUTING
    session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.EXECUTING)
    pending_plans_map.pop(f"{clean_chan}_{channel_id}", None)

    if clean_chan == "telegram" and message_id:
        try:
            from integrations.telegram.client import edit_telegram_message
            raw_plan = (plan_dict.get("lead_narration") if plan_dict else None) or (plan_dict.get("plan_text", "") if plan_dict else "") or ""
            plan_disp = re.sub(r"\n\s*<i>[^<]+</i>\s*$", "", raw_plan).strip() or raw_plan.strip()
            exec_rendered = platform_registry.render_notice_payload(clean_chan, "executing", f"{plan_disp}\n\n[Executing on host...]")
            await edit_telegram_message(
                chat_id=channel_id,
                message_id=int(message_id),
                text=exec_rendered.get("text", plan_disp),
                reply_markup=None,
            )
        except Exception:
            pass

    # 4. Execute Build Mode
    target_action = (plan_dict.get('original_prompt') if plan_dict else None) or (plan_dict.get('tool_name', 'action') if plan_dict else 'action')
    from core.channel_adapter import ChannelRequest
    req = ChannelRequest(
        text=target_action,
        channel=clean_chan,
        channel_id=channel_id,
        user_id=user_id,
        sender_name=sender_name,
    )

    try:
        pending_tool = plan_dict.get("pending_tool_call") if plan_dict else None
        build_res = await execute_build_mode_fn(
            session_id=session_id,
            user_prompt=req.text,
            req=req,
            progress_callback=progress_callback,
            pending_tool_call=pending_tool,
            plan=plan_dict,
        )
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.EXECUTED)
        try:
            from core.autonomous_engine import autonomous_engine
            with autonomous_engine._get_conn() as a_conn:
                a_conn.execute("""
                    UPDATE autonomous_tasks SET
                        status = 'idle',
                        pending_plan_id = NULL,
                        last_run = CURRENT_TIMESTAMP
                    WHERE pending_plan_id = ?
                """, (plan_id,))
                a_conn.commit()
        except Exception:
            pass
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=build_res.text)
        return {"status": "success", "result": build_res.text}

    except asyncio.CancelledError:
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.CANCELLED)
        logger.info(f"[OmnichannelGateway] Action #{plan_id} execution on {clean_chan} was stopped.")
        stop_msg = await synthesize_channel_notice("stopped", channel=clean_chan)
        rendered = platform_registry.render_notice_payload(clean_chan, "stopped", stop_msg)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", stop_msg))
        return {"status": "cancelled", "message": stop_msg}

    except Exception as exec_err:
        session_state_manager.resolve_action(clean_chan, channel_id, plan_id, ActionState.FAILED)
        logger.error(f"[OmnichannelGateway] Action #{plan_id} execution error: {exec_err}", exc_info=True)
        err_msg = await synthesize_channel_notice("error", channel=clean_chan, error_detail=str(exec_err))
        rendered = platform_registry.render_notice_payload(clean_chan, "error", err_msg)
        await channel_manager.send_message(channel=clean_chan, target_id=channel_id, text=rendered.get("text", err_msg))
        return {"status": "error", "message": err_msg}

    finally:
        session_state_manager.clear_pending(clean_chan, channel_id)
