#!/usr/bin/env python3
"""
cli.py — Anara General-Purpose AI Agent: Interactive CLI Runner.
Implements FR-8, FR-9, FR-10 from prd-general-agent.md.

Run:
  python cli.py
  python cli.py --mode explicit_plan_build
  python cli.py "Please create a database backup script"
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
{DIM}• Session Mode :{RESET} {BOLD}{session_mode}{RESET}
{DIM}• Model AI     :{RESET} {CYAN}{model_id}{RESET}
{DIM}• Commands     :{RESET} /model, /mode, /status, /memory, /skills, /exit
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
            print(f"\n{CYAN}Goodbye, Agnan! Anara is ready whenever you need.{RESET}")
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
                print(f"\n{GREEN}✓ Active AI model switched to: {BOLD}{target_m}{RESET}\n")
            else:
                cur_m = get_active_model_id()
                print(f"\n{CYAN}{BOLD}=== SELECT AI MODEL (Current: {cur_m}) ==={RESET}")
                for idx, m in enumerate(configured[:12], 1):
                    indicator = f"{GREEN}● (Active){RESET}" if m["id"] == cur_m else f"{DIM}○{RESET}"
                    print(f" {idx:2d}. {indicator} {BOLD}{m.get('name', m['id'])}{RESET} [{m.get('provider', '').upper()}]")
                    print(f"     {DIM}ID: {m['id']}{RESET}")
                print(f"\n{YELLOW}Usage: /model <number_or_id> to switch model.{RESET}\n")
            return True

        if cmd.lower() == "/status":
            cur_m = get_active_model_id()
            stats = memory_engine.get_brain_stats()
            print(f"\n{CYAN}{BOLD}=== ANARA SYSTEM STATUS ==={RESET}")
            print(f"• Channel        : cli (Terminal)")
            print(f"• Session Mode   : {session_mode}")
            print(f"• Active AI Model : {cur_m}")
            print(f"• Fact Memories  : {stats.get('memories_count', 0)} nodes")
            print(f"• Notes/Tasks    : {stats.get('notes_count', 0)} items")
            print(f"• Agent Skills   : {stats.get('skills_count', 0)} skills")
            print(f"• Core Status    : OPTIMAL & Ready to operate.\n")
            return True

        if cmd.lower() == "/mode":
            session_mode = "explicit_plan_build" if session_mode == "conversational" else "conversational"
            print(f"\n{YELLOW}Mode switched to: {BOLD}{session_mode}{RESET}")
            return True

        if cmd.lower() == "/memory":
            print(f"\n{CYAN}{BOLD}=== USER.md (PROFILE) ==={RESET}")
            print(file_memory.get_user_profile())
            print(f"\n{CYAN}{BOLD}=== MEMORY.md (FACTS) ==={RESET}")
            print(file_memory.get_memory_facts())
            return True

        if cmd.lower() == "/skills":
            skills = skill_library.list_skills()
            print(f"\n{CYAN}{BOLD}=== SKILL LIBRARY ({len(skills)} Registered) ==={RESET}")
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
            print(f"{YELLOW}{BOLD}📋 ACTION PLAN COMPOSED:{RESET}")
            print(f"{YELLOW}{res.text}{RESET}\n")

            try:
                choice = input(f"{BOLD}Approve the plan above for execution? [Y/n]: {RESET}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                choice = "n"

            if choice in ["y", "yes", "ok", ""]:
                print(f"\n{GREEN}Build Mode execution starting...{RESET}")
                build_res = await _execute_build_mode(
                    session_id=res.session_id,
                    user_prompt=f"Execute plan: {cmd}",
                    req=req,
                    progress_callback=_prog_cb
                )
                print(f"\n{CYAN}{BOLD}Anara:{RESET}\n{build_res.text}\n")
            else:
                print(f"\n{RED}Plan cancelled. No changes were made.{RESET}\n")
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
            print(f"\n{CYAN}Exiting CLI Runner.{RESET}")
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
            subprocess.run(f"taskkill /F /T /PID {b_pid}", shell=True, capture_output=True)
            record_process_exit("backend")
            print(f"{GREEN}✓ Backend FastAPI (PID {b_pid}) stopped.{RESET}")
            stopped += 1

        port_b_pid = _find_pid_on_port(8000)
        if port_b_pid and port_b_pid != b_pid:
            subprocess.run(f"taskkill /F /T /PID {port_b_pid}", shell=True, capture_output=True)
            record_process_exit("backend")
            print(f"{GREEN}✓ Backend process on port 8000 (PID {port_b_pid}) stopped.{RESET}")
            stopped += 1

        f_pid = get_process_pid("frontend")
        if f_pid:
            subprocess.run(f"taskkill /F /T /PID {f_pid}", shell=True, capture_output=True)
            record_process_exit("frontend")
            print(f"{GREEN}✓ Frontend Next.js (PID {f_pid}) stopped.{RESET}")
            stopped += 1

        port_f_pid = _find_pid_on_port(3000)
        if port_f_pid and port_f_pid != f_pid:
            subprocess.run(f"taskkill /F /T /PID {port_f_pid}", shell=True, capture_output=True)
            record_process_exit("frontend")
            print(f"{GREEN}✓ Frontend process on port 3000 (PID {port_f_pid}) stopped.{RESET}")
            stopped += 1

        try:
            from core.tunnel_manager import stop_tunnel
            if stop_tunnel():
                print(f"{GREEN}✓ Cloudflare Remote Tunnel stopped.{RESET}")
                stopped += 1
        except Exception:
            pass

        if stopped == 0:
            print(f"{DIM}No background Anara processes are currently running.{RESET}")

    elif act in ("start", "start-silent"):
        vbs_path = os.path.join(ROOT_DIR, "START_ANARA_SILENT.vbs")
        if os.path.isfile(vbs_path):
            subprocess.Popen(["wscript.exe", vbs_path], shell=False)
            print(f"{GREEN}✓ Silent launcher started: {vbs_path}{RESET}")
            print(f"{DIM}Server will be active in background in a few seconds.{RESET}")
        else:
            print(f"{RED}Launcher file {vbs_path} not found!{RESET}")


async def manage_cli_gateway(action: str = "status", param: Optional[str] = None):
    from core.tunnel_manager import get_tunnel_status, start_quick_tunnel, stop_tunnel
    from core.security import verify_gateway_password, set_gateway_password, get_configured_gateway_password_hash

    act = (action or "status").strip().lower()

    if act == "status":
        t_st = get_tunnel_status()
        print(f"\n{CYAN}{BOLD}═══ STATUS ANARA HYBRID REMOTE GATEWAY (3 SURFACES) ═══{RESET}\n")
        print(f"  • Local Web Studio : {GREEN}http://localhost:3000{RESET} (Zero friction)")
        print(f"  • Anara Code IDE   : {GREEN}http://localhost:3000/code{RESET}")
        print(f"  • Backend API      : {GREEN}http://localhost:8000{RESET}")
        print(f"  • Gateway Auth     : {GREEN}ACTIVE (Protected by Master Password){RESET}")
        if t_st.get("is_running") and t_st.get("public_url"):
            print(f"  • Remote Web Tunnel: {GREEN}{BOLD}{t_st['public_url']}{RESET}")
            print(f"  • Tunnel PID       : {DIM}{t_st.get('pid')}{RESET}")
        else:
            print(f"  • Remote Web Tunnel: {YELLOW}Inactive{RESET} (Run: python cli.py gateway tunnel)")
        print(f"\n{DIM}Default initial password: anara2026 (Change with: python cli.py gateway set-password <new>){RESET}\n")

    elif act == "tunnel":
        print(f"\n{CYAN}Setting up Cloudflare Remote Tunnel for Anara...{RESET}")
        curr = get_tunnel_status()
        if curr.get("is_running") and curr.get("public_url"):
            print(f"{GREEN}✓ Tunnel already active!{RESET}")
            print(f"\n  • {BOLD}Remote Web URL{RESET} : {CYAN}{BOLD}{curr['public_url']}{RESET}")
            print(f"  • {BOLD}Anara Code IDE{RESET} : {CYAN}{BOLD}{curr['public_url']}/code{RESET}")
            print(f"\n{DIM}Open the link above from your phone or another device, then enter your gateway password.{RESET}\n")
            return

        res = await start_quick_tunnel(port=3000)
        if res.get("status") == "running" and res.get("public_url"):
            print(f"{GREEN}{BOLD}✓ Cloudflare Remote Tunnel SUCCESSFULLY ACTIVE!{RESET}")
            print(f"\n  • {BOLD}Remote Web URL{RESET} : {CYAN}{BOLD}{res['public_url']}{RESET}")
            print(f"  • {BOLD}Anara Code IDE{RESET} : {CYAN}{BOLD}{res['public_url']}/code{RESET}")
            print(f"\n{DIM}Open the link above from your phone or another device, then enter your gateway password.{RESET}\n")
        else:
            print(f"{RED}Failed to activate tunnel: {res.get('message')}{RESET}\n")

    elif act in ("stop-tunnel", "close-tunnel"):
        if stop_tunnel():
            print(f"\n{GREEN}✓ Cloudflare Remote Tunnel successfully stopped.{RESET}\n")
        else:
            print(f"\n{DIM}No Cloudflare tunnel is currently running.{RESET}\n")

    elif act == "set-password":
        if not param:
            print(f"{RED}Please provide a new password. Example: python cli.py gateway set-password <new>{RESET}")
            return
        try:
            if set_gateway_password(param):
                print(f"{GREEN}✓ Gateway password successfully updated.{RESET}")
            else:
                print(f"{RED}Failed to update gateway password.{RESET}")
        except Exception as e:
            print(f"{RED}Error: {e}{RESET}")


def manage_cli_computer_use(action: str = "status"):
    from tools.computer_use.driver import is_cua_driver_available, resolve_cua_driver_cmd, install_cua_driver
    from tools.computer_use.executor import _get_screen_metrics

    act = (action or "status").strip().lower()
    if act == "status":
        print(f"\n{CYAN}{BOLD}═══ ANARA COMPUTER USE & CUA-DRIVER STATUS ═══{RESET}\n")
        available = is_cua_driver_available()
        path = resolve_cua_driver_cmd()
        if available:
            print(f"  • Cua Driver Status: {GREEN}AVAILABLE / READY{RESET}")
            print(f"  • Driver Binary    : {CYAN}{path}{RESET}")
            vx, vy, sw, sh = _get_screen_metrics()
            print(f"  • Screen Resolution: {sw}x{sh} px")
        else:
            print(f"  • Cua Driver Status: {YELLOW}NOT INSTALLED{RESET}")
            print(f"  • Install Command  : {DIM}python cli.py computer-use install{RESET}")
        print()
    elif act == "install":
        print(f"\n{CYAN}Installing official cua-driver upstream package...{RESET}")
        ok = install_cua_driver(upgrade=True)
        if ok:
            print(f"{GREEN}{BOLD}✓ cua-driver installed successfully!{RESET}\n")
        else:
            print(f"{RED}Failed to install cua-driver automatically. Install via PowerShell:{RESET}")
            print("  irm https://raw.githubusercontent.com/trycua/cua/main/libs/cua-driver/scripts/install.ps1 | iex\n")


def manage_cli_skills(
    action: str = "list",
    target: Optional[str] = None,
    source: str = "all",
    limit: int = 15,
    show_all: bool = False,
):
    from core.skills_sync import sync_bundled_skills
    from core.skill_library import skill_library
    from core.skills_hub import (
        search_skills,
        install_skill_from_hub,
        uninstall_skill as hub_uninstall,
        get_available_sources,
    )
    from constants import get_anara_skills_dir, get_bundled_skills_dir

    act = (action or "list").strip().lower()

    if act == "sync":
        print(f"\n{CYAN}Synchronizing bundled in-tree skills to active user runtime (Hermes Parity)...{RESET}")
        res = sync_bundled_skills()
        print(f"  • Source Directory : {DIM}{get_bundled_skills_dir()}{RESET}")
        print(f"  • Active Runtime   : {CYAN}{get_anara_skills_dir()}{RESET}")
        print(f"  • Seeded New       : {GREEN}{res['seeded']}{RESET}")
        print(f"  • Updated Upstream : {YELLOW}{res['updated']}{RESET}")
        print(f"  • User Preserved   : {GREEN}{res['preserved']}{RESET}")
        print(f"  • Unchanged        : {DIM}{res['unchanged']}{RESET}")
        print(f"  • Total Active     : {BOLD}{res['total_runtime']}{RESET}\n")

    elif act == "sources":
        sources = get_available_sources()
        print(f"\n{CYAN}{BOLD}═══ ANARA SKILLS HUB SOURCES (100k+ Catalog) ═══{RESET}\n")
        for s in sources:
            print(f"  • {BOLD}{s['name']}{RESET} ({s['id']}): {GREEN}{s['count']:,}{RESET} skills — {DIM}{s['description']}{RESET}")
        print()

    elif act == "search":
        if not target:
            print(f"\n{RED}Please provide a search query. Example: python cli.py skills search crypto{RESET}\n")
            return
        print(f"\n{CYAN}Searching 100k+ Skills Hub for: {BOLD}'{target}'{RESET} (source={source})...\n")
        res = search_skills(query=target, source=source, limit=limit)
        print(f"Found {BOLD}{res['total']}{RESET} matching skills (showing top {len(res['results'])}):\n")
        for s in res["results"]:
            status_tag = f"{GREEN}[INSTALLED]{RESET}" if s.get("is_installed") else f"{DIM}[AVAILABLE]{RESET}"
            source_tag = f"{YELLOW}[{s.get('source')}]{RESET}"
            print(f"  • {BOLD}{s.get('name')}{RESET} {source_tag} {status_tag}")
            print(f"    {DIM}Identifier: {s.get('identifier')}{RESET}")
            desc = str(s.get('description', '')).replace('\n', ' ').strip()
            if len(desc) > 95:
                desc = desc[:92] + "..."
            print(f"    {desc}")
        print(f"\n{DIM}Tip: Install with: python cli.py skills install <identifier>{RESET}\n")

    elif act == "install":
        if not target:
            print(f"\n{RED}Please specify skill identifier to install. Example: python cli.py skills install official/security/1password{RESET}\n")
            return
        print(f"\n{CYAN}Installing skill '{target}' from Skills Hub...{RESET}")
        try:
            res = install_skill_from_hub(target)
            if res.get("ok"):
                print(f"{GREEN}{BOLD}✓ Skill '{res['name']}' ({res['slug']}) successfully installed!{RESET}")
                print(f"  • Path   : {res['file_path']}")
                print(f"  • Status : {GREEN}ACTIVE{RESET}\n")
            else:
                print(f"{RED}Failed to install skill: {res}{RESET}\n")
        except Exception as e:
            print(f"{RED}Installation error: {e}{RESET}\n")

    elif act == "enable":
        if not target:
            print(f"\n{RED}Please specify skill slug to enable. Example: python cli.py skills enable docx{RESET}\n")
            return
        res = skill_library.toggle_skill(target, enabled=True)
        if res:
            print(f"\n{GREEN}{BOLD}✓ Skill '{res['name']}' ({res['slug']}) is now ENABLED (Active in prompt & tools).{RESET}\n")
        else:
            print(f"\n{RED}Skill '{target}' not found in runtime skills.{RESET}\n")

    elif act == "disable":
        if not target:
            print(f"\n{RED}Please specify skill slug to disable. Example: python cli.py skills disable docx{RESET}\n")
            return
        res = skill_library.toggle_skill(target, enabled=False)
        if res:
            print(f"\n{YELLOW}{BOLD}✓ Skill '{res['name']}' ({res['slug']}) is now DISABLED (Preserved on disk, hidden from prompt).{RESET}\n")
        else:
            print(f"\n{RED}Skill '{target}' not found in runtime skills.{RESET}\n")

    elif act in ("uninstall", "remove"):
        if not target:
            print(f"\n{RED}Please specify skill slug to uninstall. Example: python cli.py skills uninstall crypto{RESET}\n")
            return
        ok = hub_uninstall(target) or skill_library.reject_skill(target, delete_folder=True)
        if ok:
            print(f"\n{GREEN}{BOLD}✓ Skill '{target}' successfully uninstalled from runtime.{RESET}\n")
        else:
            print(f"\n{RED}Skill '{target}' not found.{RESET}\n")

    else:
        # Default: list skills
        status_filter = None if show_all else "active"
        skills = skill_library.list_skills(status_filter=status_filter)
        title = "ALL INSTALLED SKILLS" if show_all else "ACTIVE AGENT SKILLS"
        print(f"\n{CYAN}{BOLD}═══ {title} ({len(skills)} Installed) ═══{RESET}\n")
        print(f"  Runtime Directory: {DIM}{get_anara_skills_dir()}{RESET}\n")
        for s in skills[:35]:
            status_text = f"{GREEN}[ACTIVE]{RESET}" if s.get("status") == "active" else f"{YELLOW}[DISABLED]{RESET}"
            print(f"  • {BOLD}{s['name']}{RESET} ({s['slug']}) {status_text}: {s['description']}")
        if len(skills) > 35:
            print(f"\n  {DIM}... and {len(skills) - 35} more skills.{RESET}")
        print(f"\n{DIM}Tip: Run 'python cli.py skills list --all' to see disabled skills, or 'python cli.py skills search <query>' to browse 100k Hub.{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Anara General-Purpose AI Agent — CLI Runner")
    subparsers = parser.add_subparsers(dest="command")

    # daemon subcommand
    daemon_p = subparsers.add_parser("daemon", help="Manage Anara background daemons")
    daemon_p.add_argument("action", choices=["status", "stop", "start"], default="status", nargs="?")

    # gateway subcommand
    gw_p = subparsers.add_parser("gateway", help="Manage Anara Remote Gateway & Cloudflare Tunnel")
    gw_p.add_argument("action", choices=["status", "tunnel", "stop-tunnel", "set-password"], default="status", nargs="?")
    gw_p.add_argument("param", nargs="?", help="Additional parameter (e.g. new password)")

    # computer-use subcommand (Hermes Parity)
    cu_p = subparsers.add_parser("computer-use", help="Manage Cua Desktop Driver for computer_use tool")
    cu_p.add_argument("action", choices=["status", "install"], default="status", nargs="?")

    # skills subcommand (Hermes Parity & 100k Skills Hub)
    sk_p = subparsers.add_parser("skills", help="Manage, search, install, and toggle agent skills (100k+ Hub)")
    sk_p.add_argument("action", choices=["list", "sync", "search", "install", "enable", "disable", "uninstall", "remove", "sources"], default="list", nargs="?")
    sk_p.add_argument("target", nargs="?", help="Skill identifier, slug, or search query")
    sk_p.add_argument("--source", default="all", help="Filter hub search by source (official, github, skills.sh, clawhub, lobehub, browse-sh)")
    sk_p.add_argument("--limit", type=int, default=15, help="Max results for search")
    sk_p.add_argument("--all", action="store_true", help="List all skills including disabled ones")

    parser.add_argument("prompt", nargs="?", help="Execute a single command directly without entering the REPL loop")
    parser.add_argument("--mode", choices=["conversational", "explicit_plan_build"], default="conversational", help="Select initial mode")
    args = parser.parse_args()

    if args.command == "daemon":
        asyncio.run(manage_cli_daemon(args.action))
    elif args.command == "gateway":
        asyncio.run(manage_cli_gateway(args.action, args.param))
    elif args.command == "computer-use":
        manage_cli_computer_use(args.action)
    elif args.command == "skills":
        manage_cli_skills(
            action=args.action,
            target=args.target,
            source=getattr(args, "source", "all"),
            limit=getattr(args, "limit", 15),
            show_all=getattr(args, "all", False),
        )
    else:
        asyncio.run(run_cli_interactive(initial_mode=args.mode, single_prompt=args.prompt))


if __name__ == "__main__":
    main()
