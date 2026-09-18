"""
command_hub.py — Unified System Command Dispatcher for Project Anara.
Anara Standard Unified Command Hub:
1. Serves as the Single Source of Truth for all slash commands across all surfaces
   (Telegram, WhatsApp, Web Studio, and CLI Terminal).
2. Completely eliminates code duplication across channel handlers.
3. Provides uniform execution for /help, /status, /model, /skills, /memory, /workspace,
   /clear, /stop, and /plan.
"""

from __future__ import annotations

import asyncio
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


async def _handle_cmd_help(req: Any, args: str) -> Dict[str, Any]:
    sender = req.sender_name or "Pengguna"
    text = (
        f"👋 <b>Halo {sender}! Saya Anara — General AI Agent Anda.</b>\n\n"
        "Saya terhubung dengan komputer host dan ruang kerja lokal Anda, siap membantu percakapan, riset mendalam, "
        "maupun otomasi koding dengan perlindungan Plan/Build Gate otomatis.\n\n"
        "📌 <b>Daftar Perintah Universal:</b>\n"
        "• <b>/plan [tugas]</b> — Tulis rencana implementasi arsitektur terstruktur tanpa eksekusi langsung\n"
        "• <b>/stop</b> — Hentikan tugas agen, peramban browser otomatis, atau rencana yang sedang berjalan\n"
        "• <b>/model [id]</b> — Pilih provider & ganti model AI aktif secara interaktif\n"
        "• <b>/workspace [path]</b> — Lihat atau kunci agen ke folder proyek lokal PC\n"
        "• <b>/status</b> — Periksa status bot, model aktif, dan statistik memori sistem\n"
        "• <b>/memory</b> — Lihat ringkasan profil USER.md & fakta MEMORY.md\n"
        "• <b>/skills</b> — Lihat daftar keahlian aktif (agentskills.io)\n"
        "• <b>/clear</b> — Bersihkan konteks giliran aktif dan mulai percakapan baru\n"
        "• <b>/help</b> — Tampilkan panduan bantuan ini\n\n"
        "🛡️ <b>Anara Standard Guard:</b> Seluruh perintah inspeksi dan bacaan dieksekusi secara otonom tanpa hambatan. "
        "Konfirmasi persetujuan hanya muncul jika perintah berisiko tinggi terhadap sistem."
    )
    return {"text": text}


async def _handle_cmd_status(req: Any, args: str) -> Dict[str, Any]:
    active_m = get_active_model_id()
    stats = memory_engine.get_brain_stats()
    sess_id = getattr(req, "session_id", None) or 0
    channel = req.channel or "web"

    text = (
        f"📊 <b>STATUS SISTEM ANARA</b>\n\n"
        f"• <b>Channel</b>: <code>{channel.upper()}</code>\n"
        f"• <b>Sesi Aktif</b>: #{sess_id}\n"
        f"• <b>Model AI Aktif</b>: <code>{active_m}</code>\n"
        f"• <b>Total Percakapan</b>: {stats.get('conversations_count', 0):,} giliran\n"
        f"• <b>Memori Fakta</b>: {stats.get('memories_count', 0)} node\n"
        f"• <b>Catatan / To-Do</b>: {stats.get('notes_count', 0)} item\n"
        f"• <b>Keahlian Agen</b>: {stats.get('skills_count', 0)} skills aktif\n"
        f"• <b>Ukuran Database</b>: {stats.get('db_size_formatted', 'N/A')}\n"
        f"• <b>Status Core</b>: 🟢 <b>ONLINE</b> (Optimal & Siap Melayani)"
    )
    return {"text": text}


async def _handle_cmd_memory(req: Any, args: str) -> Dict[str, Any]:
    user_p = file_memory.get_user_profile()
    mem_f = file_memory.get_memory_facts()
    text = (
        f"🧠 <b>MEMORI PERSISTEN ANARA</b>\n\n"
        f"<b>1. Profil Pengguna (USER.md):</b>\n"
        f"<blockquote>{user_p[:600]}</blockquote>\n\n"
        f"<b>2. Fakta Jangka Panjang (MEMORY.md):</b>\n"
        f"<blockquote>{mem_f[:900]}</blockquote>"
    )
    return {"text": text}


async def _handle_cmd_skills(req: Any, args: str) -> Dict[str, Any]:
    skills = skill_library.list_skills(status_filter="active")
    if not skills:
        return {"text": "📚 Belum ada keahlian aktif yang terdaftar di Skill Library."}

    lines = [f"📚 <b>SKILL LIBRARY ANARA ({len(skills)} Keahlian Aktif)</b>:\n"]
    for s in skills[:20]:
        cat = s.get("category", "coding").upper()
        lines.append(f"• <b>{s['name']}</b> [{cat}]: {s.get('description', '')[:70]}...")

    if len(skills) > 20:
        lines.append(f"\n<i>... dan {len(skills) - 20} keahlian lainnya. Gunakan Web Studio untuk melihat katalog lengkap.</i>")

    return {"text": "\n".join(lines)}


async def _handle_cmd_workspace(req: Any, args: str) -> Dict[str, Any]:
    from core.agent import anara_agent
    clean_arg = (args or "").strip().strip('"\'')

    if not clean_arg:
        # Query active workspace
        ws = anara_agent.get_workspace_tree()
        name = ws.get("workspace_name", "Workspace Default")
        root_p = ws.get("root_path", "(Belum diatur)")
        total_f = ws.get("total_files", 0)
        text = (
            f"📁 <b>STATUS WORKSPACE PROYEK:</b>\n\n"
            f"• <b>Nama Proyek</b>: <code>{name}</code>\n"
            f"• <b>Lokasi Fisik</b>: <code>{root_p}</code>\n"
            f"• <b>Total Berkas</b>: {total_f} berkas\n\n"
            "<i>Untuk mengunci agen ke folder proyek lokal tertentu, gunakan:</i>\n"
            "<code>/workspace C:\\Path\\Ke\\Folder\\Proyek</code>"
        )
        return {"text": text}

    if not os.path.exists(clean_arg) or not os.path.isdir(clean_arg):
        return {"text": f"❌ <b>Folder tidak ditemukan</b>:\nPath <code>{clean_arg}</code> tidak valid atau bukan sebuah direktori."}

    res = anara_agent.attach_local_folder(clean_arg)
    name = res.get("name", os.path.basename(clean_arg))
    count = res.get("files_count", 0)
    text = (
        f"✅ <b>Workspace Berhasil Ditautkan!</b>\n\n"
        f"• <b>Proyek</b>: <code>{name}</code>\n"
        f"• <b>Path</b>: <code>{clean_arg}</code>\n"
        f"• <b>Berkas Terindeks</b>: {count} berkas\n\n"
        "Agen sekarang beroperasi terfokus di dalam folder proyek ini."
    )
    return {"text": text}


async def _handle_cmd_clear(req: Any, args: str) -> Dict[str, Any]:
    from core.session_manager import session_state_manager
    session_state_manager.clear_pending(req.channel, req.channel_id)
    text = (
        "🧹 <b>Konteks Sesi Dibersihkan!</b>\n\n"
        "Riwayat aktif giliran telah di-reset dan rencana tertahan telah dibersihkan. "
        "Anara siap memulai topik baru yang segar."
    )
    return {"text": text}


async def _handle_cmd_stop(req: Any, args: str) -> Dict[str, Any]:
    from core.session_manager import session_state_manager
    from tools.events import resolve_question_response
    interrupted = False

    # Clear pending state
    cleared = session_state_manager.clear_pending(req.channel, req.channel_id)
    if cleared:
        interrupted = True

    # Close browser if open
    try:
        from tools.browser_tools import _tool_browser_close
        await _tool_browser_close()
        interrupted = True
    except Exception:
        pass

    text = (
        "🛑 <b>TUGAS BERHASIL DIHENTIKAN!</b>\n\n"
        "Seluruh proses kerja agen, peramban browser otomatis, dan rencana yang tertahan telah dibatalkan dengan aman.\n\n"
        "<i>Anara siap menerima perintah baru Anda.</i>"
    )
    return {"text": text}


async def _handle_cmd_model(req: Any, args: str) -> Dict[str, Any]:
    clean_arg = (args or "").strip()
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
        return {"text": f"✅ <b>Model AI aktif berhasil diubah!</b>\n\nSekarang menggunakan: <code>{target_m}</code>"}

    cur_m = get_active_model_id()
    if req.channel == "telegram":
        from integrations.telegram.keyboards import send_telegram_provider_selector
        await send_telegram_provider_selector(chat_id=req.channel_id)
        return {"handled_silently": True}

    # For CLI, WhatsApp, or Web Text:
    lines = [f"🤖 <b>PILIH MODEL AI (Saat Ini: <code>{cur_m}</code>)</b>:\n"]
    for idx, m in enumerate(configured[:12], 1):
        ind = "● (Aktif)" if m["id"] == cur_m else "○"
        lines.append(f"{idx}. {ind} <b>{m.get('name', m['id'])}</b> [{m.get('provider', '').upper()}]\n   ID: <code>{m['id']}</code>")

    lines.append("\n<i>Ketik <code>/model &lt;nomor atau ID&gt;</code> untuk mengganti model.</i>")
    return {"text": "\n".join(lines)}


async def _handle_cmd_plan(req: Any, args: str) -> Dict[str, Any]:
    clean_arg = (args or "").strip()
    if not clean_arg:
        return {"text": "⚠️ Mohon sertakan deskripsi tugas untuk rencana kerja.\nContoh: <code>/plan refactor modul autentikasi JWT</code>"}

    from core.prompt_assembler import PromptAssembler
    from providers.caller import call_universal_chat_model

    plan_prompt = (
        f"[INSTRUKSI SISTEM: EKSPLORASI PLAN MODE]\n"
        f"Pengguna meminta rencana kerja: \"{clean_arg}\"\n"
        "Susun rencana kerja arsitektur yang ringkas, terstruktur dalam 3-5 langkah konkret, "
        "jelaskan dependensi dan risikonya, lalu minta persetujuan pengguna untuk mengeksekusinya."
    )

    sys_prompt = PromptAssembler.assemble(
        mode="plan",
        speaker_name=req.sender_name,
        is_chat_mode=True,
        session_type="chat"
    )

    plan_text = await call_universal_chat_model(
        model_id=get_active_model_id(),
        user_prompt=plan_prompt,
        system_instruction=sys_prompt,
        max_tokens=800,
        temperature=0.4,
        read_only=True
    )

    plan_id = str(uuid.uuid4())[:8]
    from core.session_manager import session_state_manager, PendingAction
    pending_act = PendingAction(
        plan_id=plan_id,
        session_id=req.metadata.get("session_id", 0) if hasattr(req, "metadata") else 0,
        channel=req.channel,
        channel_id=req.channel_id,
        tool_name="plan_proposal",
        original_prompt=clean_arg,
        plan_text=plan_text or "",
        user_id=req.user_id,
    )
    session_state_manager.store_pending(pending_act)

    return {
        "text": plan_text or "Rencana kerja berhasil disusun.",
        "plan_pending": True,
        "plan_id": plan_id,
    }


COMMAND_REGISTRY: Dict[str, Callable[[Any, str], Coroutine[Any, Any, Dict[str, Any]]]] = {
    "start": _handle_cmd_help,
    "help": _handle_cmd_help,
    "bantuan": _handle_cmd_help,
    "status": _handle_cmd_status,
    "model": _handle_cmd_model,
    "models": _handle_cmd_model,
    "skills": _handle_cmd_skills,
    "keahlian": _handle_cmd_skills,
    "memory": _handle_cmd_memory,
    "memori": _handle_cmd_memory,
    "workspace": _handle_cmd_workspace,
    "clear": _handle_cmd_clear,
    "reset": _handle_cmd_clear,
    "stop": _handle_cmd_stop,
    "cancel": _handle_cmd_stop,
    "abort": _handle_cmd_stop,
    "batal": _handle_cmd_stop,
    "plan": _handle_cmd_plan,
}


async def handle_channel_command(req: Any) -> Optional[Any]:
    """
    Evaluates whether the incoming channel request is a system slash command.
    Returns a populated ChannelResponse if handled, or None if normal conversation.
    """
    raw_text = (getattr(req, "text", "") or "").strip()
    if not raw_text.startswith("/"):
        return None

    tokens = raw_text.split(maxsplit=1)
    cmd_token = tokens[0][1:].split("@")[0].strip().lower()
    cmd_args = tokens[1].strip() if len(tokens) > 1 else ""

    handler = COMMAND_REGISTRY.get(cmd_token)
    if not handler:
        return None

    logger.info(f"[CommandHub] Routing command '/{cmd_token}' from channel '{req.channel}' (user={req.user_id})")

    res_dict = await handler(req, cmd_args)
    if res_dict.get("handled_silently"):
        return None

    from core.channel_adapter import ChannelResponse
    sess_id = getattr(req, "session_id", 0) or 0

    return ChannelResponse(
        text=res_dict.get("text", "Perintah berhasil diproses."),
        session_id=sess_id,
        mode="plan" if res_dict.get("plan_pending") else "conversational",
        plan_pending=bool(res_dict.get("plan_pending")),
        plan_id=res_dict.get("plan_id"),
        status="success",
        reply_markup=res_dict.get("reply_markup"),
    )
