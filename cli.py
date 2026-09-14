#!/usr/bin/env python3
"""
cli.py — Anara General-Purpose AI Agent: Interactive CLI Runner.
Implements FR-8, FR-9, FR-10 from prd-general-agent.md.

Run:
  python cli.py
  python cli.py --mode explicit_plan_build
  python cli.py "Tolong buatkan script backup database"
"""
import asyncio
import os
import sys
import argparse
from typing import Optional

# Ensure UTF-8 output in Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Configure environment & path
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from memory import memory_engine, file_memory
from core import (
    ChannelRequest,
    process_channel_request,
    needs_plan,
    is_explicit_plan_approval,
    skill_library,
)
from core.channel_adapter import _execute_build_mode, _PENDING_PLANS
from providers import get_active_model_id

# ANSI terminal colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner(session_mode: str, model_id: str):
    print(f"""{CYAN}{BOLD}
   ╔═══════════════════════════════════════════════════════════════╗
   ║            ANARA GENERAL AI AGENT — CLI RUNNER                ║
   ║    Unified Multi-Channel · Plan/Build Gate · Hermes Skills    ║
   ╚═══════════════════════════════════════════════════════════════╝{RESET}
{DIM}• Channel      :{RESET} cli (Terminal Interactive)
{DIM}• Mode Sesi    :{RESET} {BOLD}{session_mode}{RESET}
{DIM}• Model AI     :{RESET} {CYAN}{model_id}{RESET}
{DIM}• Perintah     :{RESET} /model, /mode, /status, /memory, /skills, /exit
""")


async def run_cli_interactive(initial_mode: str = "conversational", single_prompt: Optional[str] = None):
    session_mode = initial_mode
    model_id = get_active_model_id()
    terminal_id = f"cli_{os.getpid()}"

    print_banner(session_mode, model_id)

    # Initial session
    session_id = memory_engine.create_session(
        speaker_name="Agnan",
        title="Anara CLI Session",
        session_type="code" if session_mode == "explicit_plan_build" else "chat",
        channel="cli",
        session_mode=session_mode
    )["id"]

    async def _handle_input(user_text: str):
        nonlocal session_mode, session_id

        cmd = user_text.strip()
        if not cmd:
            return True

        if cmd.lower() in ["/exit", "exit", "quit", ":q"]:
            print(f"\n{CYAN}Sampai jumpa lagi, Agnan! Anara siap kapan pun dibutuhkan.{RESET}")
            return False

        if cmd.lower().startswith("/model") or cmd.lower().startswith("/models"):
            from providers.discovery import get_all_dynamic_models
            from providers.accounts import set_active_model_id
            parts = cmd.split(maxsplit=1)
            all_m = await get_all_dynamic_models()
            configured = [m for m in all_m if m.get("is_configured")] or all_m[:8]

            if len(parts) > 1:
                arg = parts[1].strip()
                target_m = None
                if arg.isdigit() and 1 <= int(arg) <= len(configured):
                    target_m = configured[int(arg) - 1]["id"]
                else:
                    matched = [m["id"] for m in configured if arg.lower() in m["id"].lower() or arg.lower() in m.get("name", "").lower()]
                    target_m = matched[0] if matched else arg
                set_active_model_id(target_m)
                print(f"\n{GREEN}✓ Model AI aktif diubah ke: {BOLD}{target_m}{RESET}\n")
            else:
                cur_m = get_active_model_id()
                print(f"\n{CYAN}{BOLD}=== PILIH MODEL AI (Model Saat Ini: {cur_m}) ==={RESET}")
                for idx, m in enumerate(configured[:12], 1):
                    indicator = f"{GREEN}● (Aktif){RESET}" if m["id"] == cur_m else f"{DIM}○{RESET}"
                    print(f" {idx:2d}. {indicator} {BOLD}{m.get('name', m['id'])}{RESET} [{m.get('provider', '').upper()}]")
                    print(f"     {DIM}ID: {m['id']}{RESET}")
                print(f"\n{YELLOW}Gunakan: /model <nomor_atau_id> untuk mengganti model.{RESET}\n")
            return True

        if cmd.lower() == "/status":
            cur_m = get_active_model_id()
            stats = memory_engine.get_brain_stats()
            print(f"\n{CYAN}{BOLD}=== STATUS SISTEM ANARA ==={RESET}")
            print(f"• Channel        : cli (Terminal)")
            print(f"• Mode Sesi      : {session_mode}")
            print(f"• Model AI Aktif : {cur_m}")
            print(f"• Memori Fakta   : {stats.get('memories_count', 0)} node")
            print(f"• Catatan/Tugas  : {stats.get('notes_count', 0)} item")
            print(f"• Keahlian Agen  : {stats.get('skills_count', 0)} skills")
            print(f"• Kondisi Core   : OPTIMAL & Siap beroperasi.\n")
            return True

        if cmd.lower() == "/mode":
            session_mode = "explicit_plan_build" if session_mode == "conversational" else "conversational"
            print(f"\n{YELLOW}Mode beralih ke: {BOLD}{session_mode}{RESET}")
            return True

        if cmd.lower() == "/memory":
            print(f"\n{CYAN}{BOLD}=== USER.md (PROFIL) ==={RESET}")
            print(file_memory.get_user_profile())
            print(f"\n{CYAN}{BOLD}=== MEMORY.md (FAKTA) ==={RESET}")
            print(file_memory.get_memory_facts())
            return True

        if cmd.lower() == "/skills":
            skills = skill_library.list_skills()
            print(f"\n{CYAN}{BOLD}=== SKILL LIBRARY ({len(skills)} Terdaftar) ==={RESET}")
            for s in skills:
                status_color = GREEN if s["status"] == "active" else YELLOW
                print(f" • {s['name']} ({s['category']}) [{status_color}{s['status']}{RESET}]: {s['description']}")
            return True

        # Process standard request
        req = ChannelRequest(
            text=cmd,
            channel="cli",
            channel_id=terminal_id,
            user_id="agnan",
            sender_name="Agnan",
            trigger_type="interactive"
        )

        def _prog_cb(msg: str):
            print(f"{DIM}  {msg}{RESET}")

        print()
        res = await process_channel_request(req, progress_callback=_prog_cb)

        if res.plan_pending and res.plan_id:
            # Plan Mode Gate triggered
            print(f"{YELLOW}{BOLD}📋 RENCANA TINDAKAN DISUSUN:{RESET}")
            print(f"{YELLOW}{res.text}{RESET}\n")

            try:
                choice = input(f"{BOLD}Setujui rencana di atas untuk dieksekusi? [Y/n]: {RESET}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                choice = "n"

            if choice in ["y", "yes", "ya", "sikat", "gas", "ok", ""]:
                print(f"\n{GREEN}Eksekusi Build Mode dimulai...{RESET}")
                build_res = await _execute_build_mode(
                    session_id=res.session_id,
                    user_prompt=f"Eksekusi rencana: {cmd}",
                    req=req,
                    progress_callback=_prog_cb
                )
                print(f"\n{CYAN}{BOLD}Anara:{RESET}\n{build_res.text}\n")
            else:
                print(f"\n{RED}Rencana dibatalkan. Tidak ada perubahan yang dilakukan.{RESET}\n")
        else:
            print(f"{CYAN}{BOLD}Anara:{RESET}\n{res.text}\n")

        return True

    # Single prompt mode
    if single_prompt:
        await _handle_input(single_prompt)
        return

    # REPL interactive loop
    while True:
        try:
            prompt_symbol = f"{GREEN}Agnan{RESET} ({DIM}{session_mode}{RESET}) > "
            user_input = input(prompt_symbol)
            should_continue = await _handle_input(user_input)
            if not should_continue:
                break
        except (KeyboardInterrupt, EOFError):
            print(f"\n{CYAN}Keluar dari CLI Runner.{RESET}")
            break


def main():
    parser = argparse.ArgumentParser(description="Anara General-Purpose AI Agent — CLI Runner")
    parser.add_argument("prompt", nargs="?", help="Eksekusi satu perintah langsung tanpa masuk ke loop REPL")
    parser.add_argument("--mode", choices=["conversational", "explicit_plan_build"], default="conversational", help="Pilih mode awal")
    args = parser.parse_args()

    asyncio.run(run_cli_interactive(initial_mode=args.mode, single_prompt=args.prompt))


if __name__ == "__main__":
    main()
