"""
command_hub.py — Unified System Command Dispatcher for Project Anara (Hermes Parity).
Anara Standard Unified Command Hub:
1. Single Source of Truth for all slash commands across all surfaces
   (Telegram, WhatsApp, Web Studio, Discord, and CLI Terminal).
2. Pure decorator-based registration (@command_hub.register).
3. Decoupled data contracts (UniversalCommandContext, UniversalCommandResponse, CommandButton).
4. Dynamic self-generating /help based on registered command metadata.
5. Seamless zero-friction fallback to agent reasoning loop when input is not a command.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging
import os
import time
import uuid
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple

from memory import memory_engine, file_memory
from core.skill_library import skill_library
from providers.accounts import get_active_model_id, set_active_model_id
from providers.discovery import get_all_dynamic_models

logger = logging.getLogger(__name__)


@dataclass
class CommandButton:
    """Standardized interactive button for platform-agnostic UI presentation."""
    text: str
    callback_data: str


@dataclass
class UniversalCommandContext:
    """Standardized contextual request passed into command handlers."""
    channel: str = "cli"
    channel_id: str = "default"
    user_id: str = "default_user"
    sender_name: str = "User"
    raw_text: str = ""
    command: str = ""
    args: str = ""
    session_id: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UniversalCommandResponse:
    """Standardized response produced by command handlers (decoupled text + buttons)."""
    text: str
    buttons: Optional[List[List[CommandButton]]] = None
    plan_pending: bool = False
    plan_id: Optional[str] = None
    handled_silently: bool = False
    reply_markup: Optional[Dict[str, Any]] = None

    def to_reply_markup(self) -> Optional[Dict[str, Any]]:
        """Converts decoupled buttons into Telegram InlineKeyboardMarkup format."""
        if self.reply_markup:
            return self.reply_markup
        if not self.buttons:
            return None
        return {
            "inline_keyboard": [
                [{"text": btn.text, "callback_data": btn.callback_data} for btn in row]
                for row in self.buttons
            ]
        }


@dataclass
class CommandDefinition:
    """Metadata record for a registered slash command."""
    name: str
    handler: Callable[[UniversalCommandContext], Coroutine[Any, Any, UniversalCommandResponse]]
    description: str = ""
    usage: str = ""
    aliases: List[str] = field(default_factory=list)


class UnifiedCommandHub:
    """
    Central command registry and dispatcher for Project Anara Omnichannel Gateway.
    Allows dynamic registration of system slash commands with decorators.
    """

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}
        self._aliases: Dict[str, str] = {}

    def register(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        description: str = "",
        usage: str = "",
    ):
        """Decorator to register a slash command handler."""
        def decorator(fn: Callable[[UniversalCommandContext], Coroutine[Any, Any, UniversalCommandResponse]]):
            clean_name = name.lower().strip()
            cmd_def = CommandDefinition(
                name=clean_name,
                handler=fn,
                description=description,
                usage=usage or f"/{clean_name}",
                aliases=aliases or [],
            )
            self._commands[clean_name] = cmd_def
            for alias in (aliases or []):
                self._aliases[alias.lower().strip()] = clean_name
            return fn
        return decorator

    def get_command(self, token: str) -> Optional[CommandDefinition]:
        clean = token.lower().strip()
        main_name = self._aliases.get(clean, clean)
        return self._commands.get(main_name)

    def list_commands(self) -> List[CommandDefinition]:
        return list(self._commands.values())

    async def dispatch(self, ctx_or_req: Any) -> Optional[UniversalCommandResponse]:
        """
        Dispatches incoming context or request to the matching command handler.
        Returns None if not a command (seamless fallback to conversation loop).
        """
        ctx = self._normalize_context(ctx_or_req)
        if not ctx.raw_text.startswith("/") or not ctx.command:
            return None

        cmd_def = self.get_command(ctx.command)
        if not cmd_def:
            return None

        logger.info(f"[CommandHub] Routing command '/{ctx.command}' from channel '{ctx.channel}' (user={ctx.user_id})")
        return await cmd_def.handler(ctx)

    def _normalize_context(self, ctx_or_req: Any) -> UniversalCommandContext:
        if isinstance(ctx_or_req, UniversalCommandContext):
            return ctx_or_req
        raw_text = (getattr(ctx_or_req, "text", "") or "").strip()
        tokens = raw_text.split(maxsplit=1)
        cmd = tokens[0][1:].split("@")[0].strip().lower() if raw_text.startswith("/") else ""
        args = tokens[1].strip() if len(tokens) > 1 else ""
        return UniversalCommandContext(
            channel=getattr(ctx_or_req, "channel", "cli") or "cli",
            channel_id=str(getattr(ctx_or_req, "channel_id", "default") or "default"),
            user_id=str(getattr(ctx_or_req, "user_id", "default_user") or "default_user"),
            sender_name=getattr(ctx_or_req, "sender_name", "User") or "User",
            raw_text=raw_text,
            command=cmd,
            args=args,
            session_id=getattr(ctx_or_req, "session_id", 0) or 0,
            metadata=getattr(ctx_or_req, "metadata", {}) or {},
        )


# Global command hub singleton
command_hub = UnifiedCommandHub()


# ── COMMAND HANDLERS (Registered via Decorators) ──

@command_hub.register(
    name="help",
    aliases=["start"],
    description="Show agent command directory",
    usage="/help"
)
async def _handle_cmd_help(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    sender = ctx.sender_name or "User"
    lines = [
        f"👋 <b>Hello {sender}!</b> I am Anara — your General AI Agent.\n",
        "Connected to your host computer and workspace, ready for deep research, "
        "conversations, and autonomous coding with Plan/Build Gate protection.\n",
        "📌 <b>Universal Commands Directory:</b>"
    ]
    for cmd in command_hub.list_commands():
        if cmd.name in ("start",):
            continue
        lines.append(f"• <b>{cmd.usage}</b> — {cmd.description}")

    lines.append(
        "\n🛡️ <b>Anara Guard:</b> Safe inspection commands execute autonomously. "
        "Approval confirmation only appears for high-risk system operations."
    )
    return UniversalCommandResponse(text="\n".join(lines))


@command_hub.register(
    name="status",
    description="Inspect system status, active model, and memory telemetry",
    usage="/status"
)
async def _handle_cmd_status(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    active_m = get_active_model_id()
    stats = memory_engine.get_brain_stats()
    sess_id = ctx.session_id or 0
    channel = ctx.channel or "web"

    header = "📊 <b>ANARA SYSTEM STATUS</b>"
    text = (
        f"{header}\n\n"
        f"• <b>Channel</b>: <code>{channel.upper()}</code>\n"
        f"• <b>Active Session</b>: #{sess_id}\n"
        f"• <b>Active Model</b>: <code>{active_m}</code>\n"
        f"• <b>Conversations</b>: {stats.get('conversations_count', 0):,} turns\n"
        f"• <b>Memories</b>: {stats.get('memories_count', 0)} nodes\n"
        f"• <b>To-Do Items</b>: {stats.get('notes_count', 0)} items\n"
        f"• <b>Skills</b>: {stats.get('skills_count', 0)} skills\n"
        f"• <b>DB Size</b>: {stats.get('db_size_formatted', 'N/A')}\n"
        f"• <b>Core Status</b>: 🟢 <b>ONLINE</b>"
    )
    return UniversalCommandResponse(text=text)


@command_hub.register(
    name="voice",
    aliases=["tts"],
    description="Configure voice reply mode across media channels",
    usage="/voice [text|only|both|auto]"
)
async def _handle_cmd_voice(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    channel = ctx.channel or "telegram"
    channel_id = ctx.channel_id or "default"
    clean_arg = ctx.args.strip().lower()

    mode_aliases = {
        "text": "text",
        "only": "only", "voice": "only",
        "both": "both", "all": "both",
        "auto": "auto", "adaptive": "auto",
    }

    if clean_arg in mode_aliases:
        new_mode = set_chat_voice_mode(channel, channel_id, mode_aliases[clean_arg])
        lbl = VOICE_MODE_LABELS.get(new_mode, new_mode)
        text = (
            f"✅ <b>Voice Mode Updated!</b>\n\n"
            f"Current mode: <b>{lbl}</b>\n\n"
            f"<i>Anara will reply according to this voice setting.</i>"
        )
        return UniversalCommandResponse(text=text)

    cur_mode = get_chat_voice_mode(channel, channel_id)
    cur_lbl = VOICE_MODE_LABELS.get(cur_mode, cur_mode)

    text = (
        f"🎙️ <b>VOICE MODE SETTINGS — {channel.upper()}</b>\n\n"
        f"Status: <b>{cur_lbl}</b>\n\n"
        "Choose how Anara replies in this chat:\n"
        "• <b>text</b>: Reply text only\n"
        "• <b>only</b>: Voice audio only without long text\n"
        "• <b>both</b>: Voice audio AND full text\n"
        "• <b>auto</b>: Adaptive mirror (voice ➔ voice, text ➔ text)\n\n"
        "<i>Type <code>/voice [text|only|both|auto]</code> or tap buttons below:</i>"
    )
    buttons = [
        [
            CommandButton(text="📝 Text Only", callback_data="vmode:text"),
            CommandButton(text="🎙️ Voice Only", callback_data="vmode:only")
        ],
        [
            CommandButton(text="🎧 Voice + Text", callback_data="vmode:both"),
            CommandButton(text="🔄 Adaptive", callback_data="vmode:auto")
        ]
    ]

    return UniversalCommandResponse(text=text, buttons=buttons)


@command_hub.register(
    name="model",
    aliases=["models"],
    description="Select provider & switch active AI model",
    usage="/model [number|id]"
)
async def _handle_cmd_model(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    clean_arg = ctx.args.strip()
    all_models = await get_all_dynamic_models()
    configured = [m for m in all_models if m.get("is_configured")] or all_models[:10]

    if clean_arg:
        target_m = None
        if clean_arg.isdigit() and 1 <= int(clean_arg) <= len(configured):
            target_m = configured[int(clean_arg) - 1]["id"]
        else:
            matched = [
                m["id"] for m in configured
                if clean_arg.lower() in m["id"].lower() or clean_arg.lower() in m.get("name", "").lower()
            ]
            target_m = matched[0] if matched else clean_arg

        set_active_model_id(target_m)
        return UniversalCommandResponse(text=f"✅ <b>Active model updated!</b>\n\nNow using: <code>{target_m}</code>")

    cur_m = get_active_model_id()
    if ctx.channel == "telegram":
        from integrations.telegram.keyboards import send_telegram_provider_selector
        await send_telegram_provider_selector(chat_id=ctx.channel_id)
        return UniversalCommandResponse(text="", handled_silently=True)

    lines = [f"🤖 <b>SELECT AI MODEL (Current: <code>{cur_m}</code>)</b>:\n"]
    for idx, m in enumerate(configured[:12], 1):
        ind = "● (Active)" if m["id"] == cur_m else "○"
        lines.append(f"{idx}. {ind} <b>{m.get('name', m['id'])}</b> [{m.get('provider', '').upper()}]\n   ID: <code>{m['id']}</code>")

    lines.append("\n<i>Type <code>/model &lt;number or ID&gt;</code> to switch.</i>")
    return UniversalCommandResponse(text="\n".join(lines))


@command_hub.register(
    name="skills",
    aliases=[],
    description="View active agent skills catalog",
    usage="/skills"
)
async def _handle_cmd_skills(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    skills = skill_library.list_skills(status_filter="active")
    if not skills:
        return UniversalCommandResponse(text="📚 <b>SKILL LIBRARY ANARA</b>: <i>No active skills registered.</i>")

    header = f"📚 <b>SKILL LIBRARY ANARA ({len(skills)} Active Skills)</b>:\n"
    lines = [header]
    for s in skills[:20]:
        cat = s.get("category", "coding").upper()
        lines.append(f"• <b>{s['name']}</b> [{cat}]: {s.get('description', '')[:70]}...")

    if len(skills) > 20:
        lines.append(f"\n<i>... and {len(skills) - 20} more skills. Use Web Studio to view full catalog.</i>")

    return UniversalCommandResponse(text="\n".join(lines))


@command_hub.register(
    name="memory",
    aliases=["mem"],
    description="View USER.md profile & MEMORY.md facts summary",
    usage="/memory"
)
async def _handle_cmd_memory(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    user_p = file_memory.get_user_profile()
    mem_f = file_memory.get_memory_facts()
    header = "🧠 <b>ANARA PERSISTENT MEMORY</b>"
    text = (
        f"{header}\n\n"
        f"<b>1. User Profile (USER.md):</b>\n"
        f"<blockquote>{user_p[:600]}</blockquote>\n\n"
        f"<b>2. Long-Term Facts (MEMORY.md):</b>\n"
        f"<blockquote>{mem_f[:900]}</blockquote>"
    )
    return UniversalCommandResponse(text=text)


@command_hub.register(
    name="workspace",
    description="Inspect or lock workspace root directory",
    usage="/workspace [path]"
)
async def _handle_cmd_workspace(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    from core.agent import anara_agent
    clean_arg = ctx.args.strip().strip('"\'')

    if not clean_arg:
        ws = anara_agent.get_workspace_tree()
        name = ws.get("workspace_name", "Default Workspace")
        root_p = ws.get("root_path", "(Unset)")
        total_f = ws.get("total_files", 0)
        text = (
            f"📁 <b>WORKSPACE STATUS:</b>\n\n"
            f"• <b>Project Name</b>: <code>{name}</code>\n"
            f"• <b>Physical Path</b>: <code>{root_p}</code>\n"
            f"• <b>Indexed Files</b>: {total_f} files\n\n"
            "<i>To link agent to a specific project directory, use:</i>\n"
            "<code>/workspace C:\\Path\\To\\Folder</code>"
        )
        return UniversalCommandResponse(text=text)

    if not os.path.exists(clean_arg) or not os.path.isdir(clean_arg):
        return UniversalCommandResponse(text=f"❌ <b>Folder Not Found</b>:\nPath <code>{clean_arg}</code> is not a valid directory.")

    res = anara_agent.attach_local_folder(clean_arg)
    name = res.get("name", os.path.basename(clean_arg))
    count = res.get("files_count", 0)
    text = (
        f"✅ <b>Workspace Linked!</b>\n\n"
        f"• <b>Project</b>: <code>{name}</code>\n"
        f"• <b>Path</b>: <code>{clean_arg}</code>\n"
        f"• <b>Indexed Files</b>: {count} files\n\n"
        "Agent is now operating within this project directory."
    )
    return UniversalCommandResponse(text=text)


@command_hub.register(
    name="clear",
    aliases=["reset"],
    description="Clear active turn context and reset conversation session",
    usage="/clear"
)
async def _handle_cmd_clear(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    from core.session_manager import session_state_manager
    session_state_manager.clear_pending(ctx.channel, ctx.channel_id)
    text = (
        "🧹 <b>Session Cleared!</b>\n\n"
        "Active turn history has been reset and pending plans cleared. "
        "Anara is ready for a fresh topic."
    )
    return UniversalCommandResponse(text=text)


@command_hub.register(
    name="stop",
    aliases=["cancel", "abort"],
    description="Halt active agent tasks, browser automations, or running plans",
    usage="/stop"
)
async def _handle_cmd_stop(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    from core.session_manager import session_state_manager
    interrupt_info = await session_state_manager.request_hard_interrupt(
        channel=ctx.channel,
        channel_id=ctx.channel_id,
        reason="user_stop"
    )

    try:
        from tools.browser_tools import _tool_browser_close
        await _tool_browser_close()
    except Exception:
        pass

    details = []
    if interrupt_info.get("task_cancelled"):
        details.append("task cancelled")
    if interrupt_info.get("processes_killed", 0) > 0:
        details.append(f"{interrupt_info['processes_killed']} sub-processes killed")
    if interrupt_info.get("pending_cleared"):
        details.append("pending plans cleared")
    detail_str = f" ({', '.join(details)})" if details else ""
    text = (
        f"🛑 <b>TASK STOPPED</b>{detail_str}\n\n"
        "All running agent tasks, browser automations, terminal sub-processes, and pending plans have been cancelled.\n\n"
        "<i>Anara is ready for your next command.</i>"
    )
    return UniversalCommandResponse(text=text)


@command_hub.register(
    name="plan",
    description="Draft a structured architectural action plan without direct execution",
    usage="/plan [task]"
)
async def _handle_cmd_plan(ctx: UniversalCommandContext) -> UniversalCommandResponse:
    clean_arg = ctx.args.strip()
    if not clean_arg:
        return UniversalCommandResponse(text="⚠️ <b>Please provide a task description for the plan:</b>\nExample: <code>/plan refactor JWT auth module</code>")

    from core.prompt_assembler import PromptAssembler
    from core.prompt_loader import load_prompt
    from providers.caller import call_universal_chat_model

    plan_prompt = load_prompt("channel/plan_command", clean_arg=clean_arg)

    sys_prompt = PromptAssembler.assemble(
        mode="plan",
        speaker_name=ctx.sender_name,
        is_chat_mode=True,
        session_type="chat"
    )

    plan_text = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=plan_prompt,
        system_instruction=sys_prompt,
        max_tokens=None,
        temperature=0.4,
        read_only=True
    )

    plan_id = str(uuid.uuid4())[:8]
    from core.session_manager import session_state_manager, PendingAction
    pending_act = PendingAction(
        plan_id=plan_id,
        session_id=ctx.session_id or 0,
        channel=ctx.channel,
        channel_id=ctx.channel_id,
        tool_name="plan_proposal",
        original_prompt=clean_arg,
        plan_text=plan_text or "",
        user_id=ctx.user_id,
    )
    session_state_manager.store_pending(pending_act)

    buttons = [
        [
            CommandButton(text="✅ Approve", callback_data=f"approve:{plan_id}"),
            CommandButton(text="❌ Cancel", callback_data=f"reject:{plan_id}")
        ]
    ]

    return UniversalCommandResponse(
        text=plan_text or "Action plan successfully drafted.",
        buttons=buttons,
        plan_pending=True,
        plan_id=plan_id,
    )


# ── VOICE HELPERS & PERSISTENCE ──

VOICE_MODE_LABELS = {
    "text": "📝 Text Only (Voice/Text → Replied as Text)",
    "only": "🎙️ Voice Only (Voice Note Only)",
    "both": "🎧 Voice + Text (Both)",
    "auto": "🔄 Adaptive (Voice → Voice, Text → Text)",
}


def get_chat_voice_mode(channel: str, channel_id: str) -> str:
    """Returns the voice response mode ('text', 'only', 'both', 'auto') for a chat."""
    pref_key = f"voice_mode_{str(channel).lower()}_{str(channel_id).strip()}"
    return memory_engine.get_app_setting(pref_key) or "auto"


def set_chat_voice_mode(channel: str, channel_id: str, mode: str) -> str:
    """Persists the voice response mode for a specific chat."""
    target = mode.lower().strip()
    if target not in ("text", "only", "both", "auto"):
        target = "auto"
    pref_key = f"voice_mode_{str(channel).lower()}_{str(channel_id).strip()}"
    memory_engine.set_app_setting(pref_key, target)
    return target


async def handle_channel_command(req: Any) -> Optional[Any]:
    """
    Evaluates whether the incoming channel request is a system slash command.
    Dispatches via UnifiedCommandHub and converts response into ChannelResponse format.
    Returns None if normal conversation (seamless zero-friction fallback).
    """
    resp = await command_hub.dispatch(req)
    if not resp:
        return None
    if resp.handled_silently:
        return None

    from core.channel_adapter import ChannelResponse
    sess_id = getattr(req, "session_id", 0) or 0

    return ChannelResponse(
        text=resp.text,
        session_id=sess_id,
        mode="plan" if resp.plan_pending else "conversational",
        plan_pending=resp.plan_pending,
        plan_id=resp.plan_id,
        status="success",
        reply_markup=resp.to_reply_markup(),
        is_command=True,
    )
