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
   ║    Unified Multi-Channel · Plan/Build Gate · Anara Skills     ║
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


def _find_pid_on_port(port: int) -> Optional[int]:
    import subprocess
    try:
        cmd = f'netstat -aon | findstr ":{port}" | findstr "LISTENING"'
        out = subprocess.check_output(cmd, shell=True, text=True, errors="replace")
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and f":{port}" in parts[1]:
                return int(parts[-1])
    except Exception:
        pass
    return None


async def manage_cli_daemon(action: str = "status"):
    from core.lifecycle import is_pid_alive, get_process_pid, record_process_exit
    import subprocess

    act = (action or "status").strip().lower()

    if act == "status":
        b_pid = get_process_pid("backend")
        f_pid = get_process_pid("frontend")

        b_alive = is_pid_alive(b_pid) if b_pid else False
        f_alive = is_pid_alive(f_pid) if f_pid else False

        port_b = _find_pid_on_port(8000)
        port_f = _find_pid_on_port(3000)

        print(f"\n{BOLD}Project Anara Background Daemon Status:{RESET}")
        print(f"  • Backend FastAPI   : {GREEN}RUNNING{RESET} (PID {b_pid or port_b}, http://localhost:8000)" if (b_alive or port_b) else f"  • Backend FastAPI   : {DIM}STOPPED{RESET} (port 8000)")
        print(f"  • Frontend Next.js  : {GREEN}RUNNING{RESET} (PID {f_pid or port_f}, http://localhost:3000)" if (f_alive or port_f) else f"  • Frontend Next.js  : {DIM}STOPPED{RESET} (port 3000)")

        from constants import get_anara_logs_dir
        print(f"\n  Log Files:")
        print(f"    - Backend Log     : {get_anara_logs_dir() / 'backend.log'}")
        print(f"    - Frontend Log    : {get_anara_logs_dir() / 'frontend.log'}\n")

    elif act == "stop":
        stopped = 0
        b_pid = get_process_pid("backend")
        if b_pid:
            subprocess.run(f"taskkill /F /PID {b_pid}", shell=True, capture_output=True)
            record_process_exit("backend")
            print(f"{GREEN}✓ Backend FastAPI (PID {b_pid}) dihentikan.{RESET}")
            stopped += 1

        port_b_pid = _find_pid_on_port(8000)
        if port_b_pid and port_b_pid != b_pid:
            subprocess.run(f"taskkill /F /PID {port_b_pid}", shell=True, capture_output=True)
            record_process_exit("backend")
            print(f"{GREEN}✓ Backend proses pada port 8000 (PID {port_b_pid}) dihentikan.{RESET}")
            stopped += 1

        f_pid = get_process_pid("frontend")
        if f_pid:
            subprocess.run(f"taskkill /F /PID {f_pid}", shell=True, capture_output=True)
            record_process_exit("frontend")
            print(f"{GREEN}✓ Frontend Next.js (PID {f_pid}) dihentikan.{RESET}")
            stopped += 1

        port_f_pid = _find_pid_on_port(3000)
        if port_f_pid and port_f_pid != f_pid:
            subprocess.run(f"taskkill /F /PID {port_f_pid}", shell=True, capture_output=True)
            record_process_exit("frontend")
            print(f"{GREEN}✓ Frontend proses pada port 3000 (PID {port_f_pid}) dihentikan.{RESET}")
            stopped += 1

        try:
            from core.gateway_manager import stop_tunnel
            if stop_tunnel():
                print(f"{GREEN}✓ Cloudflare Remote Tunnel dihentikan.{RESET}")
                stopped += 1
        except Exception:
            pass

        if stopped == 0:
            print(f"{DIM}Tidak ada proses background Anara yang sedang berjalan.{RESET}")

    elif act in ("start", "start-silent"):
        vbs_path = os.path.join(ROOT_DIR, "START_ANARA_SILENT.vbs")
        if os.path.isfile(vbs_path):
            subprocess.Popen(["wscript.exe", vbs_path], shell=False)
            print(f"{GREEN}✓ Peluncur hening diluncurkan: {vbs_path}{RESET}")
            print(f"{DIM}Server akan aktif di background dalam beberapa detik.{RESET}")
        else:
            print(f"{RED}File launcher {vbs_path} tidak ditemukan!{RESET}")


async def manage_cli_gateway(action: str = "status", param: Optional[str] = None):
    from core.gateway_manager import get_tunnel_status, start_quick_tunnel, stop_tunnel
    from core.security import verify_gateway_password, set_gateway_password, get_configured_gateway_password_hash

    act = (action or "status").strip().lower()

    if act == "status":
        t_st = get_tunnel_status()
        print(f"\n{CYAN}{BOLD}═══ STATUS ANARA HYBRID REMOTE GATEWAY (3 SURFACES) ═══{RESET}\n")
        print(f"  • Local Web Studio : {GREEN}http://localhost:3000{RESET} (Zero friction)")
        print(f"  • Anara Code IDE   : {GREEN}http://localhost:3000/code{RESET}")
        print(f"  • Backend API      : {GREEN}http://localhost:8000{RESET}")
        print(f"  • Gateway Auth     : {GREEN}AKTIF (Protected by Master Password){RESET}")
        if t_st.get("is_running") and t_st.get("public_url"):
            print(f"  • Remote Web Tunnel: {GREEN}{BOLD}{t_st['public_url']}{RESET}")
            print(f"  • Tunnel PID       : {DIM}{t_st.get('pid')}{RESET}")
        else:
            print(f"  • Remote Web Tunnel: {YELLOW}Nonaktif{RESET} (Jalankan: python cli.py gateway tunnel)")
        print(f"\n{DIM}Default password awal: anara2026 (Ganti dengan: python cli.py gateway set-password <baru>){RESET}\n")

    elif act == "tunnel":
        print(f"\n{CYAN}Menyiapkan Cloudflare Remote Tunnel untuk Anara...{RESET}")
        curr = get_tunnel_status()
        if curr.get("is_running") and curr.get("public_url"):
            print(f"{GREEN}✓ Tunnel sudah aktif!{RESET}")
            print(f"\n  • {BOLD}Remote Web URL{RESET} : {CYAN}{BOLD}{curr['public_url']}{RESET}")
            print(f"  • {BOLD}Anara Code IDE{RESET} : {CYAN}{BOLD}{curr['public_url']}/code{RESET}")
            print(f"\n{DIM}Buka link di atas dari HP atau laptop teman, lalu masukkan password gateway Anda.{RESET}\n")
            return

        res = await start_quick_tunnel(port=3000)
        if res.get("status") == "running" and res.get("public_url"):
            print(f"{GREEN}{BOLD}✓ Cloudflare Remote Tunnel BERHASIL AKTIF!{RESET}")
            print(f"\n  • {BOLD}Remote Web URL{RESET} : {CYAN}{BOLD}{res['public_url']}{RESET}")
            print(f"  • {BOLD}Anara Code IDE{RESET} : {CYAN}{BOLD}{res['public_url']}/code{RESET}")
            print(f"\n{DIM}Buka link di atas dari HP atau laptop teman, lalu masukkan password gateway Anda.{RESET}\n")
        else:
            print(f"{RED}Gagal mengaktifkan tunnel: {res.get('message')}{RESET}\n")

    elif act in ("stop-tunnel", "close-tunnel"):
        if stop_tunnel():
            print(f"\n{GREEN}✓ Cloudflare Remote Tunnel berhasil dihentikan.{RESET}\n")
        else:
            print(f"\n{DIM}Tidak ada tunnel Cloudflare yang sedang berjalan.{RESET}\n")

    elif act == "set-password":
        if not param:
            print(f"{RED}Harap sertakan password baru. Contoh: python cli.py gateway set-password <baru>{RESET}")
            return
        try:
            if set_gateway_password(param):
                print(f"{GREEN}✓ Password Gateway berhasil diperbarui.{RESET}")
            else:
                print(f"{RED}Gagal memperbarui password gateway.{RESET}")
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")


def main():
    parser = argparse.ArgumentParser(description="Anara General-Purpose AI Agent — CLI Runner")
    subparsers = parser.add_subparsers(dest="command")

    # daemon subcommand
    daemon_p = subparsers.add_parser("daemon", help="Kelola daemon latar belakang Anara")
    daemon_p.add_argument("action", choices=["status", "stop", "start"], default="status", nargs="?")

    # gateway subcommand
    gw_p = subparsers.add_parser("gateway", help="Kelola Anara Remote Gateway & Cloudflare Tunnel")
    gw_p.add_argument("action", choices=["status", "tunnel", "stop-tunnel", "set-password"], default="status", nargs="?")
    gw_p.add_argument("param", nargs="?", help="Parameter tambahan (misal password baru)")

    parser.add_argument("prompt", nargs="?", help="Eksekusi satu perintah langsung tanpa masuk ke loop REPL")
    parser.add_argument("--mode", choices=["conversational", "explicit_plan_build"], default="conversational", help="Pilih mode awal")
    args = parser.parse_args()

    if args.command == "daemon":
        asyncio.run(manage_cli_daemon(args.action))
    elif args.command == "gateway":
        asyncio.run(manage_cli_gateway(args.action, args.param))
    else:
        asyncio.run(run_cli_interactive(initial_mode=args.mode, single_prompt=args.prompt))


if __name__ == "__main__":
    main()
