"""
Autonomous Agent Runner for Project Anara.
Executes multi-step text chat turns, manages Plan Mode vs Build Mode tool loops,
streams AI responses, and captures token usage telemetry.
"""
import asyncio
import json
import logging
import os
import re
import time as _time
from typing import Optional, Dict, Any, List, Callable
from fastapi import WebSocket

from memory import memory_engine
from core import (
    key_manager,
    ModelCapabilityRegistry,
    anara_agent,
    PromptAssembler,
    ContextCompactor,
    SkillExtractor,
    needs_plan,
    is_explicit_plan_approval,
)
from providers import (
    get_active_model_id,
    call_universal_chat_model,
    stream_universal_chat_model,
)
from cognition import (
    generate_visual_projection,
    generate_daily_briefing,
    is_briefing_request,
    EmotionEngine,
    get_soul_prompt,
)
from tools import generate_text_response_with_tools
import shared_state
from shared_state import chat_diagnostics

logger = logging.getLogger("anara.websocket.agent")

class AgentRunner:
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
                        f"Model '{sel_model_for_check}' tidak mendukung input/output audio real-time. "
                        "Pilih model Live Preview (misal gemini-2.5-flash-live-preview) di Mode Voice."
                    )
                    logger.warning(f"[Chat] {err_msg}")
                    chat_diagnostics["last_error"] = err_msg
                    chat_diagnostics["last_stage"] = "voice_capability_missing"
                    await self.websocket.send_json({"type": "error", "data": err_msg})
                    return

            if text and re.match(r'^\s*\{.*"type"\s*:', text):
                return

            if text:
                current_turn_user_text = text
                logger.info(f"[Text Chat Turn] Received: {text!r} from speaker {self.get_current_speaker()!r}")
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

                # Resolve session context & mode (rancangan-general-agent.md Bab 3 & 5)
                session_obj = memory_engine.get_session(sid) if sid else None
                session_type = (session_obj.get("session_type") or "chat") if session_obj else "chat"
                session_mode = (session_obj.get("session_mode") or ("explicit_plan_build" if session_type == "code" else "conversational")) if session_obj else "conversational"

                norm_text = text.lower().strip()
                is_approved = is_explicit_plan_approval(norm_text)

                if session_mode == "explicit_plan_build":
                    # Anara Code Studio Workstation: Honors user toggle or approval trigger
                    if is_approved:
                        agent_mode = "build"
                        logger.info("[Agent Mode] Plan approved in Code Studio -> Switch to BUILD MODE")
                    else:
                        agent_mode = req_agent_mode if req_agent_mode in ("plan", "build") else "plan"
                else:
                    # Conversational Mode (Anara AI Companion / Messaging / General Chat):
                    # Zero friction for casual chat/read-only tasks.
                    # Automatically activates Plan Mode if user requests mutating/ask or significant actions.
                    if is_approved:
                        agent_mode = "build"
                        logger.info("[Agent Mode] Plan approved in Conversational Mode -> Switch to BUILD MODE")
                    elif needs_plan(text, session_mode="conversational"):
                        agent_mode = "plan"
                        logger.info(f"[Agent Mode] High-risk/mutating intent detected in Conversational Mode -> Auto-activating PLAN MODE for '{text[:40]}...'")
                    else:
                        agent_mode = "build"

                try:
                    memory_engine.log_conversation(
                        user_text=text,
                        ai_text="",
                        speaker_name=self.get_current_speaker(),
                        session_id=sid
                    )
                    # 4-File Memory trigger detection (FR-11)
                    from memory import file_memory
                    mem_note = file_memory.detect_and_record_memory(text, speaker_name=self.get_current_speaker())
                    if mem_note:
                        logger.info(f"[4FileMemory] {mem_note}")
                except Exception as e_opt:
                    logger.warning(f"[ChatSessions] Optimistic save error: {e_opt}")

                if text.startswith("Sistem:"):
                    logger.info(f"[Dance] System speech directive: {text[:60]!r}")
                    await self.activate_dance_llm_turn(text)
                else:
                    logger.info(f"[Chat Mode Input] Processing: {text!r}")
                    if is_briefing_request(text) and not self.dance_blocked():
                        try:
                            brief = await generate_daily_briefing(
                                key_manager.get_client(), memory_engine, self.get_current_speaker()
                            )
                            await self.websocket.send_json({
                                "type": "hud_visual",
                                "data": brief["reply_text"],
                                "visualType": "briefing",
                                "briefingData": brief["briefing_data"],
                                "mediaType": "hud",
                            })
                            await self.websocket.send_json({
                                "type": "transcript", "data": brief["reply_text"],
                                "speaker": "output", "is_final": True,
                            })
                            self.log_turn(
                                user_text=text, ai_text=brief["reply_text"],
                                speaker_name=self.get_current_speaker(),
                            )
                            visual_projected_this_turn = True
                            last_visual_projection_ts = _time.monotonic()
                        except Exception as e_brief:
                            logger.error(f"[Briefing] Failed (text): {e_brief!r}", exc_info=True)
                        return

                    speaker_ctx = memory_engine.get_system_prompt_context(self.get_current_speaker(), is_chat_mode=True)
                    proactive_facts = memory_engine.get_proactive_relevant_facts(text, self.get_current_speaker())
                    proactive_brief = memory_engine.get_proactive_briefing_guidance(self.get_current_speaker())
                    if proactive_facts:
                        speaker_ctx = f"{speaker_ctx}\n{proactive_facts}"
                    if proactive_brief:
                        speaker_ctx = f"{speaker_ctx}\n{proactive_brief}"

                    active_sys_prompt = f"{get_soul_prompt(mode='chat')}\n{speaker_ctx}"

                    vis = {"has_visual": False}
                    clean_text_lower = text.lower()
                    if any(w in clean_text_lower for w in ["foto", "gambar", "lihat", "tampilkan foto", "cuaca"]):
                        is_code_project = any(w in clean_text_lower for w in ["project", "proyek", "web", "website", "login", "html", "css", "js", "code", "coding", "aplikasi", "script", "file", "folder", "auth"])
                        if not is_code_project:
                            try:
                                vis = await asyncio.wait_for(
                                    generate_visual_projection(key_manager.get_client(), text, active_sys_prompt),
                                    timeout=3.0
                                )
                            except Exception:
                                vis = {"has_visual": False}
                    if vis.get("has_visual"):
                        v_type = vis.get("visual_type", "image")
                        reply_text = vis.get("reply_text", "Protokol visual diproyeksikan ke layar HUD.")
                        _n_imgs = len(vis.get("images") or []) or (1 if vis.get("image_url") else 0)
                        visual_projected_this_turn = True
                        last_visual_projection_ts = _time.monotonic()
                        last_visual_image_count = _n_imgs

                        await self.websocket.send_json({
                            "type": "transcript",
                            "data": reply_text,
                            "speaker": "output",
                            "visualType": v_type,
                            "imageUrl": vis.get("image_url"),
                            "imageTitle": vis.get("image_title"),
                            "sourceDomain": vis.get("source_domain"),
                            "sourceUrl": vis.get("source_url"),
                            "weatherData": vis.get("weather_data"),
                            "codeData": vis.get("code_data"),
                            "systemHudData": vis.get("system_hud_data"),
                            "knowledgeCardData": vis.get("knowledge_card_data"),
                            "todoData": vis.get("todo_data"),
                            "images": vis.get("images", []),
                            "mediaType": "image" if v_type == "image" else "hud"
                        })
                        self.log_turn(
                            user_text=text,
                            ai_text=reply_text,
                            speaker_name=self.get_current_speaker(),
                            media_type=v_type,
                            media_url=vis.get("image_url"),
                            visual_data=vis
                        )
                        em = self.emotion_engine.analyze(reply_text, allow_dance=False)
                        if em:
                            await self.push_emotion(em["emotion"], em["gesture"], em["intensity"])
                    else:
                        reply_text = ""
                        all_history = memory_engine.get_recent_conversations(
                            limit=25,
                            speaker_name=self.get_current_speaker(),
                            session_id=self.get_active_session_id(),
                        )
                        # Smart Rolling Context Window Compaction (Claude Code / Anara Standard)
                        dialogue_context = ContextCompactor.compact_history(all_history, verbatim_turns=5)

                        ws_tree = anara_agent.get_workspace_tree(session_id=self.get_active_session_id())
                        ws_context = ""
                        if ws_tree and (ws_tree.get("total_files", 0) > 0 or ws_tree.get("is_custom_folder")):
                            ws_context = (
                                f"\n[INFO WORKSPACE PROYEK AKTIF]:\n"
                                f"- Nama Folder / Project: {ws_tree.get('workspace_name')}\n"
                                f"- Root Path Asli: {ws_tree.get('root_path')}\n"
                                f"- Total Berkas: {ws_tree.get('total_files')} berkas\n"
                                f"- Berkas di Workspace: {', '.join([f['path'] for f in ws_tree.get('files', [])[:20]]) or '(Folder kosong siap dibangun)'}\n\n"
                            )

                        active_skills = memory_engine.get_all_agent_skills(active_only=True)
                        curr_sess = memory_engine.get_session(self.get_active_session_id()) or {}
                        sess_type = curr_sess.get("session_type", "chat")

                        clean_sys_instruction = PromptAssembler.assemble(
                            mode=agent_mode,
                            speaker_name=self.get_current_speaker(),
                            workspace_tree=ws_tree,
                            active_skills=active_skills,
                            is_chat_mode=True,
                            session_type=sess_type
                        )

                        full_user_input = f"{dialogue_context}Pesan User: {text}"
                        selected_model = get_active_model_id()
                        chat_diagnostics["active_requests"] += 1
                        chat_diagnostics["last_stage"] = f"generating with {selected_model}"
                        chat_diagnostics["last_updated"] = _time.time()
                        chat_diagnostics["last_error"] = None
                        t_chat_start = _time.time()
                        try:
                            logger.info(f"[Text Chat Turn] Calling model: {selected_model} (mode={agent_mode})")

                            tools_used: List[str] = []
                            usage_collector: Dict[str, Any] = {}

                            async def _emit_tool_progress(event: Dict[str, Any]):
                                tool_name = event.get("tool_name", "tool")
                                tool_status = event.get("status", "running")
                                summary = (event.get("summary") or "")[:160]
                                if tool_status == "thinking":
                                    try:
                                        await self.websocket.send_json({
                                            "type": "agent_thinking",
                                            "text": summary or ("Menyusun rancangan arsitektur..." if agent_mode == "plan" else "Menganalisis langkah implementasi...")
                                        })
                                    except Exception:
                                        pass
                                    return

                                if tool_name in ["interactive_question", "agent", "tool"]:
                                    return

                                if tool_name not in tools_used:
                                    tools_used.append(tool_name)
                                try:
                                    await self.websocket.send_json({
                                        "type": "tool_progress",
                                        "tool_name": tool_name,
                                        "status": tool_status,
                                        "summary": summary,
                                        "icon": event.get("icon") or ("zip" if "zip" in tool_name else "file" if "write" in tool_name else "terminal" if "shell" in tool_name or "command" in tool_name else "tool"),
                                    })
                                except Exception:
                                    pass

                            # Always enable autonomous ReAct agent tools loop in both Plan Mode and Build Mode (OpenCode standard)
                            is_agent_action_mode = True

                            try:
                                await self.websocket.send_json({
                                    "type": "agent_thinking",
                                    "text": "Menyelidiki struktur proyek & menganalisis kebutuhan..." if agent_mode == "plan" else "Mengeksekusi tahapan konstruksi proyek..."
                                })
                            except Exception:
                                pass

                            has_streamed_live = False

                            async def _handle_live_token(acc_text: str):
                                nonlocal has_streamed_live
                                # Immediately dismiss thinking indicator on first incoming live token
                                if not has_streamed_live:
                                    has_streamed_live = True
                                    try:
                                        await self.websocket.send_json({
                                            "type": "agent_thinking",
                                            "text": "",
                                        })
                                    except Exception:
                                        pass

                                try:
                                    await self.websocket.send_json({
                                        "type": "transcript_partial",
                                        "speaker": "output",
                                        "text": acc_text,
                                        "is_final": False,
                                    })
                                except Exception:
                                    pass

                            if is_agent_action_mode:
                                try:
                                    raw_res = await asyncio.wait_for(
                                        call_universal_chat_model(
                                            model_id=selected_model,
                                            user_prompt=full_user_input,
                                            system_instruction=clean_sys_instruction,
                                            max_tokens=None,
                                            temperature=0.7,
                                            read_only=(agent_mode == "plan"),
                                            progress_cb=_emit_tool_progress,
                                            token_cb=_handle_live_token,
                                            platform="web_studio",
                                            intercept_mutating_tools=(agent_mode == "plan"),
                                        ),
                                        timeout=180.0
                                    )
                                    if isinstance(raw_res, dict) and raw_res.get("intercepted"):
                                        import uuid
                                        from core.session_manager import PendingAction, session_state_manager
                                        from core.channel_adapter import synthesize_action_rationale, UniversalChannelAdapter
                                        t_name = raw_res.get("tool_name", "")
                                        t_args = raw_res.get("tool_args", {})
                                        lead = raw_res.get("lead_text", "")
                                        p_id = f"plan_{uuid.uuid4().hex[:8]}"

                                        lead_narration = lead
                                        if not lead_narration:
                                            lead_narration = await synthesize_action_rationale(
                                                tool_name=t_name,
                                                tool_args=t_args,
                                                prompt=text
                                            )

                                        pending_act = PendingAction(
                                            plan_id=p_id,
                                            session_id=sid,
                                            channel="web_studio",
                                            channel_id=str(sid),
                                            tool_name=t_name,
                                            tool_args=t_args,
                                            original_prompt=text,
                                            plan_text=lead_narration,
                                            lead_narration=lead_narration,
                                            risk_level=raw_res.get("tool_risk") or "mutating",
                                            status="pending",
                                            user_id=self.get_current_speaker(),
                                            pending_tool_call=raw_res.get("raw_call"),
                                        )
                                        session_state_manager.store_pending(pending_act)
                                        reply_text = lead_narration

                                        rendered = UniversalChannelAdapter.render_approval_payload(
                                            channel="web_studio",
                                            narration=lead_narration,
                                            action=pending_act
                                        )

                                        await self.websocket.send_json({
                                            "type": "plan_pending",
                                            "plan_id": p_id,
                                            "tool_name": t_name,
                                            "tool_args": t_args,
                                            "text": lead_narration,
                                            "action_metadata": rendered.get("action_metadata"),
                                        })
                                    elif raw_res and isinstance(raw_res, str):
                                        raw_out = raw_res.strip()
                                        raw_out = re.sub(r"^(?:Language|Response|Output|Anara|Assistant)\s*:\s*[^\n]*\n*", "", raw_out, flags=re.IGNORECASE).strip()
                                        if raw_out:
                                            reply_text = raw_out
                                            # If not already streamed live token-by-token, stream chunk-by-chunk pacing
                                            if not has_streamed_live:
                                                try:
                                                    await self.websocket.send_json({
                                                        "type": "agent_thinking",
                                                        "text": "",
                                                    })
                                                except Exception:
                                                    pass

                                                # Real-time streaming pacing: Stream the narrative response chunk-by-chunk
                                                # so it renders fluidly on the client (OpenCode / Claude Code standard)
                                                words = raw_out.split(" ")
                                                acc_stream = []
                                                step_size = 2
                                                for w_idx in range(0, len(words), step_size):
                                                    acc_stream.extend(words[w_idx:w_idx + step_size])
                                                    try:
                                                        await self.websocket.send_json({
                                                            "type": "transcript_partial",
                                                            "speaker": "output",
                                                            "text": " ".join(acc_stream),
                                                            "is_final": False,
                                                        })
                                                        await asyncio.sleep(0.015)
                                                    except Exception:
                                                        break
                                    if not reply_text:
                                        chat_diagnostics["last_error"] = f"Model '{selected_model}' mengembalikan respon kosong"
                                except Exception as g_err:
                                    err_str = str(g_err).strip() or type(g_err).__name__
                                    logger.warning(f"[Text Chat] Model {selected_model} agent execution exception: {err_str}")
                                    chat_diagnostics["last_error"] = err_str
                            else:
                                accumulated = []
                                try:
                                    stream_iter = stream_universal_chat_model(
                                        model_id=selected_model,
                                        user_prompt=full_user_input,
                                        system_instruction=clean_sys_instruction,
                                        max_tokens=None,
                                        temperature=0.7,
                                        usage_out=usage_collector,
                                    )
                                    async with asyncio.timeout(60):
                                        async for chunk in stream_iter:
                                            if chunk:
                                                parts = re.findall(r'\S+|\s+', chunk)
                                                for p in parts:
                                                    accumulated.append(p)
                                                    try:
                                                        await self.websocket.send_json({
                                                            "type": "transcript_partial",
                                                            "speaker": "output",
                                                            "text": "".join(accumulated),
                                                            "is_final": False,
                                                        })
                                                        if len(parts) > 1:
                                                            await asyncio.sleep(0.012)
                                                    except Exception:
                                                        break
                                except (asyncio.TimeoutError, Exception) as stream_err:
                                    logger.warning(f"[Text Chat] Stream error for {selected_model}: {stream_err}")
                                    chat_diagnostics["last_error"] = str(stream_err)
                                if accumulated:
                                    reply_text = "".join(accumulated).strip()
                                    reply_text = re.sub(r"^(?:Language|Response|Output|Anara|Assistant)\s*:\s*[^\n]*\n*", "", reply_text, flags=re.IGNORECASE).strip()
                        except (asyncio.TimeoutError, Exception) as c_err:
                            err_str = str(c_err).strip() or type(c_err).__name__
                            logger.warning(f"[Text Chat] Model {selected_model} error: {err_str}")
                            if not chat_diagnostics.get("last_error"):
                                chat_diagnostics["last_error"] = err_str

                        if not reply_text:
                            detail_err = chat_diagnostics.get("last_error") or "Gagal mendapatkan respon model"
                            err_lower = detail_err.lower()
                            if "google ai studio belum diatur" in err_lower or "gemini api key" in err_lower:
                                err_msg = (
                                    f"[Google AI Studio Belum Terhubung]: Kunci API Google AI Studio belum dikonfigurasi. "
                                    f"Silakan tambahkan akun di Anara Brain Console (tab Providers) atau pilih model dari provider lain di bilah bawah."
                                )
                            elif "503" in err_lower or "unavailable" in err_lower:
                                err_msg = (
                                    f"⚠️ [Provider Limit / 503]: Model '{selected_model}' sedang kehabisan kuota atau limit di server proxy/provider ({detail_err[:160]}). "
                                    f"Silakan pilih model lain di bilah bawah atau periksa sisa kredit akun provider Anda."
                                )
                            elif "429" in err_lower or "quota" in err_lower or "resource_exhausted" in err_lower:
                                err_msg = (
                                    f"⚠️ [Error 429 - Kuota API Habis]: Model '{selected_model}' mencapai batas kuota request dari provider. "
                                    f"Silakan pilih model lain atau provider cadangan melalui menu model di bilah bawah."
                                )
                            elif "400" in err_lower or "invalid_argument" in err_lower:
                                err_msg = f"⚠️ [Error 400 - Permintaan Tidak Valid]: Model '{selected_model}': {detail_err[:150]}. Silakan coba model lain."
                            else:
                                err_msg = (
                                    f"⚠️ [Info Provider]: Model '{selected_model}' ({detail_err[:140]}). "
                                    f"Silakan pilih model lain di bilah bawah."
                                )
                            logger.warning(f"[Text Chat Notice] {err_msg}")
                            chat_diagnostics["last_error"] = err_msg
                            chat_diagnostics["last_stage"] = "error"
                            chat_diagnostics["active_requests"] = max(0, chat_diagnostics["active_requests"] - 1)

                            await self.websocket.send_json({
                                "type": "error",
                                "data": err_msg,
                            })
                            await self.websocket.send_json({
                                "type": "transcript",
                                "data": err_msg,
                                "speaker": "output",
                                "is_final": True
                            })
                            await self.websocket.send_json({"type": "turn_complete"})
                            return

                        chat_diagnostics["active_requests"] = max(0, chat_diagnostics["active_requests"] - 1)
                        chat_diagnostics["last_stage"] = "reply ready"
                        chat_diagnostics["last_updated"] = _time.time()

                        duration_sec = max(1, round(_time.time() - t_chat_start))
                        if duration_sec < 60:
                            duration_text = f"{duration_sec}dtk"
                        else:
                            mins = duration_sec // 60
                            secs = duration_sec % 60
                            duration_text = f"{mins}mnt {secs}dtk" if secs > 0 else f"{mins}mnt"

                        # Resolve real token usage from provider if captured by stream/agent, else calculate estimate
                        context_limit = 128000
                        model_lower = selected_model.lower()
                        if "gemini" in model_lower or "gemma" in model_lower:
                            context_limit = 1000000
                        elif "claude" in model_lower:
                            context_limit = 200000
                        elif "o1" in model_lower or "o3" in model_lower or "codex" in model_lower:
                            context_limit = 200000

                        has_actual_usage = bool(usage_collector.get("total_tokens"))
                        if has_actual_usage:
                            p_tok = int(usage_collector.get("prompt_tokens", 0))
                            c_tok = int(usage_collector.get("completion_tokens", 0))
                            t_tok = int(usage_collector.get("total_tokens", p_tok + c_tok))
                            usage_src = "actual"
                        else:
                            p_tok = max(1, round(len(f"{clean_sys_instruction}\n{full_user_input}") / 4))
                            c_tok = max(1, round(len(reply_text) / 4))
                            t_tok = p_tok + c_tok
                            usage_src = "estimated"

                        context_remaining = max(0, context_limit - t_tok)
                        token_usage_payload = {
                            "model_id": selected_model,
                            "provider": selected_model.split("/", 1)[0] if "/" in selected_model else "gemini",
                            "prompt_tokens": p_tok,
                            "completion_tokens": c_tok,
                            "total_tokens": t_tok,
                            "context_limit": context_limit,
                            "context_remaining": context_remaining,
                            "source": usage_src,
                            "tools_used": tools_used,
                        }
                        try:
                            await self.websocket.send_json({"type": "token_usage", **token_usage_payload})
                        except Exception:
                            pass

                        await self.websocket.send_json({
                            "type": "transcript",
                            "data": reply_text,
                            "speaker": "output",
                            "is_final": True,
                            "agent_mode": agent_mode,
                            "model": selected_model,
                            "duration_text": duration_text,
                            "token_usage": token_usage_payload,
                            "tools_used": tools_used,
                            "visualType": None,
                            "planData": None,
                        })

                        v_data = {
                            "agent_mode": agent_mode,
                            "model": selected_model,
                            "duration_text": duration_text,
                            "token_usage": token_usage_payload,
                            "tools_used": tools_used,
                        }

                        try:
                            self.log_turn(
                                user_text=text,
                                ai_text=reply_text,
                                speaker_name=self.get_current_speaker(),
                                media_type="chat",
                                visual_data=v_data
                            )
                            logger.info(f"[Text Chat Turn Completed] Saved turn for session #{self.get_active_session_id()}: {text[:40]!r} -> {reply_text[:40]!r}")

                            # Anara Lifelong Learning: Auto-extract skill if constructive tools were used in Build Mode
                            if agent_mode == "build" and tools_used:
                                try:
                                    loop = asyncio.get_running_loop()
                                    ws_name = ws_tree.get("workspace_name") if ws_tree else None
                                    loop.create_task(
                                        SkillExtractor.extract_and_save_skill_async(
                                            user_prompt=text,
                                            tools_used=tools_used,
                                            final_summary=reply_text,
                                            workspace_name=ws_name
                                        )
                                    )
                                except Exception as sk_err:
                                    logger.debug(f"[Anara Skill Extractor] background task error: {sk_err}")
                        except Exception as log_err:
                            logger.error(f"[Text Chat Turn] Error logging turn: {log_err}")
                        shared_state.last_active_visual_payload = None

                        try:
                            em = self.emotion_engine.analyze(reply_text, allow_dance=False)
                            if em:
                                await self.push_emotion(em["emotion"], em["gesture"], em["intensity"])
                        except Exception as em_err:
                            logger.debug(f"[Emotion] analyze error: {em_err}")

                        await self.websocket.send_json({"type": "turn_complete"})
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
