"""
keyboards.py — Telegram Inline Keyboards & Interactive Wizards for Project Anara.
Handles multi-provider model selection, plan approvals, and interactive questionnaires.
"""

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

from .client import send_telegram_message, edit_telegram_message, delete_telegram_message

logger = logging.getLogger(__name__)

_MODEL_ID_SHORTMAP: Dict[str, str] = {}
_PENDING_TELEGRAM_QUESTIONS: Dict[str, Dict[str, Any]] = {}


def _make_model_callback_data(model_id: str) -> str:
    """Generates a safe <= 64-byte callback_data string for Telegram inline buttons."""
    if len(model_id) <= 50:
        return f"setm:{model_id}"
    short_hash = hashlib.md5(model_id.encode("utf-8")).hexdigest()[:12]
    _MODEL_ID_SHORTMAP[short_hash] = model_id
    return f"setms:{short_hash}"


async def send_telegram_provider_selector(chat_id: str, message_id: Optional[int] = None):
    """Step 1: Displays the multi-provider menu via inline keyboard."""
    from providers import get_active_model_id
    from memory import memory_engine

    active_id = get_active_model_id()
    custom_nodes = memory_engine.get_custom_providers()
    accounts = memory_engine.get_ai_accounts()

    has_gemini = any(a.get("provider") == "gemini" for a in accounts) or os.getenv("GEMINI_API_KEY")
    has_openai = any(a.get("provider") in ["openai", "codex"] for a in accounts) or os.getenv("OPENAI_API_KEY")
    has_anthropic = any(a.get("provider") == "anthropic" for a in accounts) or os.getenv("ANTHROPIC_API_KEY")

    buttons = []
    if has_gemini:
        buttons.append([{"text": "💎 Google Gemini (Native SDK)", "callback_data": "prov:gemini"}])

    for node in custom_nodes:
        if node.get("is_active", 1):
            prefix = node.get("prefix", "custom")
            name = node.get("name", prefix)
            icon = "🌐 " if "9router" in prefix.lower() or "proxy" in name.lower() else "⚡ "
            buttons.append([{"text": f"{icon}{name}", "callback_data": f"prov:{prefix}"}])

    if has_anthropic:
        buttons.append([{"text": "🟣 Anthropic Claude", "callback_data": "prov:anthropic"}])
    if has_openai:
        buttons.append([{"text": "🟢 OpenAI / Codex", "callback_data": "prov:openai"}])

    if not buttons:
        buttons = [
            [{"text": "💎 Google Gemini", "callback_data": "prov:gemini"}],
            [{"text": "🌐 9Router Proxy", "callback_data": "prov:9router"}],
        ]

    keyboard = {"inline_keyboard": buttons}
    msg_text = (
        f"🤖 <b>AI MODEL PROVIDER SELECTION</b>\n\n"
        f"Active model:\n<code>{active_id}</code>\n\n"
        f"<i>Select a provider below to view available models:</i>"
    )
    if message_id:
        return await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=msg_text, reply_markup=keyboard)
    return await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)


async def send_telegram_models_for_provider(chat_id: str, provider_prefix: str, message_id: Optional[int] = None):
    """Step 2: Displays curated top models under the selected provider."""
    from providers.discovery import get_all_dynamic_models
    from providers import get_active_model_id

    active_id = get_active_model_id()
    all_models = await get_all_dynamic_models()

    prefix_lower = provider_prefix.lower()
    matching_models = []

    if prefix_lower == "gemini":
        matching_models = [m for m in all_models if m.get("provider") == "gemini"]
    else:
        matching_models = [
            m for m in all_models
            if m.get("provider") == prefix_lower or m["id"].startswith(f"{prefix_lower}/")
        ]

    if not matching_models:
        matching_models = [
            m for m in all_models
            if prefix_lower in m["id"].lower() or prefix_lower in m.get("name", "").lower()
        ]

    buttons = []
    for m in matching_models[:8]:
        m_id = m["id"]
        is_cur = (m_id == active_id)
        icon = "🔘 " if is_cur else "🔹 "
        name = m.get("name", m_id)
        clean_name = name.replace(f"({provider_prefix})", "").replace(f"({prefix_lower})", "").strip()
        btn_text = f"{icon}{clean_name}"

        cb_val = _make_model_callback_data(m_id)
        buttons.append([{"text": btn_text, "callback_data": cb_val}])

    buttons.append([{"text": "⬅️ Back to Providers", "callback_data": "prov:menu"}])

    prov_title = provider_prefix.upper()
    keyboard = {"inline_keyboard": buttons}
    msg_text = (
        f"💎 <b>MODEL CATALOG [{prov_title}]</b>\n\n"
        f"Active model:\n<code>{active_id}</code>\n\n"
        f"<i>Tap a model below to activate immediately:</i>"
    )
    if message_id:
        return await edit_telegram_message(chat_id=chat_id, message_id=message_id, text=msg_text, reply_markup=keyboard)
    return await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)


async def send_telegram_model_search(chat_id: str, query: str):
    """Searches across all models and renders inline results."""
    from providers.discovery import get_all_dynamic_models
    from providers import get_active_model_id

    active_id = get_active_model_id()
    all_models = await get_all_dynamic_models()
    q_low = query.lower().strip()

    matches = [m for m in all_models if q_low in m["id"].lower() or q_low in m.get("name", "").lower()]
    if not matches:
        return await send_telegram_message(
            text=f"❌ No models found matching <code>{query}</code>.\n\nUse <code>/model</code> to view provider menu.",
            chat_id=chat_id
        )

    buttons = []
    for m in matches[:8]:
        m_id = m["id"]
        icon = "🔘 " if m_id == active_id else "🔹 "
        cb_val = _make_model_callback_data(m_id)
        buttons.append([{"text": f"{icon}{m.get('name', m_id)}", "callback_data": cb_val}])

    buttons.append([{"text": "⬅️ Provider Menu", "callback_data": "prov:menu"}])
    keyboard = {"inline_keyboard": buttons}
    msg_text = (
        f"🔍 <b>MODEL SEARCH: \"{query}\"</b>\n\n"
        f"Active model:\n<code>{active_id}</code>\n\n"
        f"<i>Tap a model below to activate:</i>"
    )
    return await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)


async def send_telegram_model_selector(chat_id: str):
    """Compatibility alias to show provider selector menu."""
    return await send_telegram_provider_selector(chat_id)


async def send_telegram_plan_proposal(
    chat_id: str,
    plan_text: str,
    plan_id: str,
) -> Dict[str, Any]:
    """Sends a formatted Plan Proposal with inline Approve / Cancel buttons via UniversalChannelAdapter."""
    from .client import send_telegram_message
    from core.channel_adapter import UniversalChannelAdapter
    from core.session_manager import session_state_manager
    p = session_state_manager.get_pending_by_id(plan_id)
    if p:
        rendered = UniversalChannelAdapter.render_approval_payload("telegram", plan_text, p)
        return await send_telegram_message(
            text=rendered.get("text") or plan_text,
            chat_id=chat_id,
            parse_mode=rendered.get("parse_mode", "HTML"),
            reply_markup=rendered.get("reply_markup")
        )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approve:{plan_id}"},
                {"text": "❌ Deny", "callback_data": f"reject:{plan_id}"}
            ]
        ]
    }
    return await send_telegram_message(
        text=plan_text,
        chat_id=chat_id,
        parse_mode="HTML",
        reply_markup=keyboard
    )


async def start_telegram_interactive_question(chat_id: str, question_data: Dict[str, Any]):
    """Registers and initiates an interactive multi-question wizard."""
    q_id = question_data.get("question_id")
    questions = question_data.get("questions") or []
    if not q_id or not questions:
        return

    _PENDING_TELEGRAM_QUESTIONS[q_id] = {
        "chat_id": str(chat_id),
        "question_id": q_id,
        "questions": questions,
        "current_index": 0,
        "answers": [],
        "message_id": None,
    }
    await render_telegram_question(q_id)


async def render_telegram_question(q_id: str):
    """Renders the current question step with choice buttons."""
    state = _PENDING_TELEGRAM_QUESTIONS.get(q_id)
    if not state:
        return

    chat_id = state["chat_id"]
    idx = state["current_index"]
    questions = state["questions"]

    if idx >= len(questions):
        await finish_telegram_interactive_question(q_id)
        return

    q = questions[idx]
    q_text = q.get("question", "")
    header = q.get("header", f"Question {idx+1}")
    options = q.get("options") or []

    buttons = []
    for opt_idx, opt in enumerate(options):
        lbl = opt.get("label", str(opt)) if isinstance(opt, dict) else str(opt)
        buttons.append([{"text": lbl, "callback_data": f"qans:{q_id}:{opt_idx}"}])

    # Universal language presentation for questionnaire interface (Hermes Parity)
    dismiss_label = "✖ Dismiss"
    clarification_title = f"📋 <b>CLARIFICATION ({idx+1}/{len(questions)})</b>"
    action_hint = "<i>Tap an option below or type your answer:</i>"

    buttons.append([{"text": dismiss_label, "callback_data": f"qdis:{q_id}"}])
    keyboard = {"inline_keyboard": buttons}

    msg_text = (
        f"{clarification_title}\n"
        f"<b>{header}</b>\n\n"
        f"{q_text}\n\n"
        f"{action_hint}"
    )

    if state.get("message_id"):
        await edit_telegram_message(chat_id=chat_id, message_id=state["message_id"], text=msg_text, reply_markup=keyboard)
    else:
        res = await send_telegram_message(text=msg_text, chat_id=chat_id, reply_markup=keyboard)
        if isinstance(res, dict) and res.get("result"):
            state["message_id"] = res["result"].get("message_id")


async def finish_telegram_interactive_question(q_id: str, dismissed: bool = False):
    """Finalizes questionnaire and injects answers into agent."""
    state = _PENDING_TELEGRAM_QUESTIONS.pop(q_id, None)
    if not state:
        return

    chat_id = state["chat_id"]
    msg_id = state.get("message_id")
    if msg_id:
        if dismissed:
            await edit_telegram_message(chat_id=chat_id, message_id=msg_id, text="<i>[Clarification dismissed by user]</i>", reply_markup=None)
        else:
            ans_summary = "\n".join([f"• <b>{a.get('header') or 'Item'}:</b> {a.get('answer')}" for a in state["answers"]])
            await edit_telegram_message(chat_id=chat_id, message_id=msg_id, text=f"✅ <b>Clarification Complete:</b>\n{ans_summary}\n\n<i>Continuing task execution...</i>", reply_markup=None)

    from tools.events import resolve_interactive_question
    resolve_interactive_question(q_id, state["answers"], dismissed=dismissed)
