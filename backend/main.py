import asyncio
from contextlib import asynccontextmanager
import logging
import os
import socket
import sys
from typing import Optional

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Prevent OpenBLAS / OMP multithreading memory errors on Windows
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from memory import memory_engine, get_current_indonesian_time_str
from core import ModelCapabilityRegistry, require_gateway_auth
from tools import register_agent_event_listener
from shared_state import (
    broadcast_agent_event,
    broadcast_brain_sync,
    close_shared_http_client,
    set_main_event_loop,
)

# Import Modular Routers (Anara Desktop Standard)
from routers.brain_routes import router as brain_router
from routers.provider_routes import router as provider_router
from routers.workspace_routes import router as workspace_router
from routers.integration_routes import router as integration_router
from routers.session_routes import router as session_router
from routers.gateway_routes import router as gateway_router
from routers.telemetry_routes import router as telemetry_router
from routers.terminal_routes import router as terminal_router
from websocket.handler import router as websocket_router

from core.logger import setup_anara_logging

from constants import load_universal_env
load_universal_env()

# Initialize enterprise rotating file & console logger (Anara Standard)
setup_anara_logging()

logger = logging.getLogger("anara.main")
ANARA_BUILD = "2026-09-12-modular-architecture-v2"
_background_tasks = set()

# Register real-time cross-service event listeners
register_agent_event_listener(broadcast_agent_event)
memory_engine.register_mutation_listener(broadcast_brain_sync)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts background services, initializes provider keys, and manages graceful shutdown."""
    logger.info(f"[Anara] Backend code loaded — build {ANARA_BUILD}")
    loop = asyncio.get_running_loop()
    set_main_event_loop(loop)
    _install_signal_handlers()
    try:
        from core.lifecycle import record_process_start, record_process_exit
        record_process_start("backend", os.getpid())
    except Exception:
        pass
    try:
        seeded = ModelCapabilityRegistry.seed_live_voice_from_key_manager()
        if seeded:
            logger.info(f"[Startup] Seeded {seeded} Live Voice model(s) from key pool.")
    except Exception as e:
        logger.warning(f"[Startup] Live Voice seed skipped: {e}")
    try:
        t_refresh = asyncio.create_task(ModelCapabilityRegistry.refresh())
        _background_tasks.add(t_refresh)
        t_refresh.add_done_callback(_background_tasks.discard)
    except Exception as e:
        logger.warning(f"[Startup] Capability warmup skipped: {e}")

    # Universal .env to SQLite accounts synchronization (Anara Standard)
    try:
        from providers.accounts import sync_env_to_accounts
        sync_env_to_accounts()
    except Exception as e:
        logger.warning(f"[Startup] Env-to-accounts synchronization error: {e}")

    # Seed 9Router Proxy automatically if not configured
    try:
        nodes = memory_engine.get_custom_providers()
        has_9router = any(n.get("prefix") == "9router" for n in nodes)
        if not has_9router:
            memory_engine.save_custom_provider(
                name="9Router Proxy",
                prefix="9router",
                base_url="http://localhost:20128/v1",
                api_key="",
                default_model="ag/gemini-3.8-flash-high",
                api_type="openai",
                is_active=True
            )
            memory_engine.set_app_setting("active_ai_model", "9router/ag/gemini-3.8-flash-high")
            logger.info("[Startup] Auto-seeded 9Router Proxy provider.")
    except Exception as e:
        logger.warning(f"[Startup] Provider seed check: {e}")

    # Synchronize bundled in-tree skills to active user runtime skills (Anara Standard)
    try:
        from core.skills_sync import sync_bundled_skills
        from core.skill_library import skill_library
        sync_bundled_skills()
        skill_library.sync_from_database()
    except Exception as e:
        logger.warning(f"[Startup] Skill library sync skipped: {e}")

    # Start Telegram background daemon if bot token is configured
    try:
        from integrations.telegram import start_telegram_polling_daemon, stop_telegram_polling_daemon, get_stored_telegram_token
        if get_stored_telegram_token():
            start_telegram_polling_daemon()
    except Exception as e:
        logger.warning(f"[Startup] Telegram daemon init error: {e}")

    # Start Autonomous Task Scheduler & Event Trigger (Fase 5)
    try:
        from core.autonomous_engine import autonomous_engine
        autonomous_engine.start()
    except Exception as e:
        logger.warning(f"[Startup] Autonomous engine init error: {e}")

    # Start WhatsApp local bridge daemon
    try:
        from integrations.whatsapp import start_whatsapp_bridge, stop_whatsapp_bridge
        start_whatsapp_bridge()
    except Exception as e:
        logger.warning(f"[Startup] WhatsApp bridge start skipped: {e}")

    # Ensure native CUA driver daemon is active on startup (Anara Standard)
    try:
        from tools.computer_use.driver import ensure_cua_driver_daemon_running
        ensure_cua_driver_daemon_running()
    except Exception as e:
        logger.debug(f"[Startup] CUA driver daemon init note: {e}")

    # Discover and connect to configured native Model Context Protocol (MCP) servers (Anara Standard)
    try:
        from integrations.mcp import mcp_manager
        t_mcp = asyncio.create_task(mcp_manager.connect_all_servers())
        _background_tasks.add(t_mcp)
        t_mcp.add_done_callback(_background_tasks.discard)
    except Exception as e:
        logger.debug(f"[Startup] MCP discovery task launch note: {e}")

    # Ensure Windows background autostart & global 'anara' CLI are registered (Anara Standard)
    try:
        from core.windows_service import windows_autostart
        from core.global_cli import global_cli_installer
        def _bg_sys_init():
            windows_autostart.ensure_autostart_registered()
            global_cli_installer.install()
        asyncio.get_running_loop().run_in_executor(None, _bg_sys_init)
    except Exception as e:
        logger.debug(f"[Startup] Windows system registration note: {e}")

    yield

    # 1. Cleanly close active WebSocket connections (Anara Standard)
    from shared_state import active_websockets
    for ws in list(active_websockets):
        try:
            await ws.close(code=1001, reason="Server shutting down")
        except Exception:
            pass
    active_websockets.clear()

    # 2. Stop Cloudflare Quick Tunnel if running
    try:
        from core.tunnel_manager import stop_tunnel
        stop_tunnel()
    except Exception:
        pass

    # 3. Stop background process registry daemons
    try:
        from core.process_registry import process_registry
        for p in process_registry.list_processes():
            if p.get("process_id"):
                process_registry.stop_process(p["process_id"])
    except Exception:
        pass

    # 4. Stop platform bridges and autonomous scheduler
    try:
        from integrations.whatsapp import stop_whatsapp_bridge
        stop_whatsapp_bridge()
    except Exception:
        pass

    try:
        from core.autonomous_engine import autonomous_engine
        autonomous_engine.stop()
    except Exception:
        pass

    try:
        from integrations.telegram import stop_telegram_polling_daemon
        stop_telegram_polling_daemon()
    except Exception:
        pass

    # Stop native MCP server connections
    try:
        from integrations.mcp import mcp_manager
        await mcp_manager.shutdown()
    except Exception:
        pass

    # 5. Flush SQLite WAL Checkpoint (Non-blocking with timeout)
    try:
        def _flush_wal():
            with memory_engine._get_connection() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        await asyncio.wait_for(asyncio.to_thread(_flush_wal), timeout=5.0)
        logger.info("[Shutdown] SQLite WAL checkpoint flushed.")
    except Exception as e:
        logger.debug(f"[Shutdown] WAL checkpoint note: {e}")

    # 6. Scavenge sentinels & record exit
    try:
        from core.lifecycle import record_process_exit, cleanup_stale_processes
        record_process_exit("backend")
        cleanup_stale_processes(prune_dead=True)
    except Exception:
        pass

    await close_shared_http_client()

# FastAPI application instance
app = FastAPI(
    title="Anara 3D Voice & Visual AI API",
    description="Modular real-time voice & text AI assistant with 3D avatar, code IDE, and holographic HUD",
    version="3.0.0",
    lifespan=lifespan
)

# ── Enterprise Security & Sandbox Middlewares (Anara Enterprise Architecture) ──
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# Pure ASGI middleware — avoids BaseHTTPMiddleware deadlock with WebSocket connections
# (Starlette issue #1012: BaseHTTPMiddleware starves thread pool when WS are active)
class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            # Let WebSocket and lifespan pass through untouched
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = dict(message.get("headers", []))
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-xss-protection", b"1; mode=block"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                ]
                path = scope.get("path", "")
                if path.startswith("/api/"):
                    extra.append((b"cache-control", b"no-store, no-cache, must-revalidate"))
                message = {
                    **message,
                    "headers": list(message.get("headers", [])) + extra,
                }
            await send(message)

        await self.app(scope, receive, send_with_headers)

app.add_middleware(SecurityHeadersMiddleware)

# CORS Configuration (Restricted explicit origins with dynamic tunnel matching)
raw_origins = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()] or [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https?://([a-zA-Z0-9-]+\.)?(trycloudflare\.com|anara\.my\.id)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Session-Token",
        "X-Client-Version",
        "X-Client-Platform",
        "Accept",
        "X-Requested-With",
        "Cache-Control",
        "Origin",
    ],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import uuid
    from fastapi.responses import JSONResponse
    error_id = f"err_{uuid.uuid4().hex[:8]}"
    logger.error(f"[UnhandledException] ID: {error_id} — {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error_id": error_id,
            "message": "Internal server error occurred.",
            "path": request.url.path
        }
    )

# Health check & system overview endpoint
@app.get("/")
async def health_check():
    """Health check & minimal status endpoint."""
    time_info = get_current_indonesian_time_str()
    return {
        "status": "ok",
        "service": "Project Anara",
        "version": "3.0.0",
        "build": ANARA_BUILD,
        "time": time_info
    }

# ── Mount Modular APIRouters (Anara Security Architecture: Per-Route Gateway Auth) ──
# Public gateway router (for login and remote status check)
app.include_router(gateway_router)

# Protected endpoints (local origin auto-permitted, remote requires session token)
app.include_router(brain_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(provider_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(workspace_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(integration_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(session_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(telemetry_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(terminal_router, dependencies=[Depends(require_gateway_auth)])
app.include_router(websocket_router, dependencies=[Depends(require_gateway_auth)])

def _assert_port_free(port: int):
    """Startup guard: checks if port is free before starting."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError:
        owner_pid = "???"
        try:
            import subprocess
            cmd = f'powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess"'
            out = subprocess.check_output(cmd, shell=True, text=True, timeout=5).strip()
            if out:
                owner_pid = out.split()[0]
        except Exception:
            pass
        logger.error(
            f"[Anara] PORT {port} is still in use by another process (PID {owner_pid})! "
            f"Stop it first with: Stop-Process -Id {owner_pid} -Force"
        )
        raise SystemExit(1)
    finally:
        try:
            sock.close()
        except Exception:
            pass

_signal_handlers_installed: bool = False

def _install_signal_handlers():
    """Installs native signal and Windows console control handlers (Anara Enterprise Architecture)."""
    global _signal_handlers_installed
    if _signal_handlers_installed:
        return
    _signal_handlers_installed = True

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

            def _console_ctrl_handler(ctrl_type: int) -> bool:
                CTRL_C_EVENT = 0
                CTRL_BREAK_EVENT = 1
                CTRL_CLOSE_EVENT = 2
                CTRL_LOGOFF_EVENT = 5
                CTRL_SHUTDOWN_EVENT = 6

                if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT, CTRL_SHUTDOWN_EVENT):
                    logger.info(f"[Lifecycle] Windows Console Ctrl Event {ctrl_type} caught. Initiating clean exit...")
                    import _thread
                    _thread.interrupt_main()
                    return True
                return False

            global _global_ctrl_handler_ref
            _global_ctrl_handler_ref = HandlerRoutine(_console_ctrl_handler)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(_global_ctrl_handler_ref, True)
            logger.debug("[Lifecycle] Native Win32 SetConsoleCtrlHandler registered.")
        except Exception as e:
            logger.debug(f"[Lifecycle] Win32 ConsoleCtrlHandler registration note: {e}")
    else:
        import signal
        def _posix_handler(sig, frame):
            logger.info(f"[Lifecycle] POSIX Signal {sig} caught. Initiating clean exit...")
            raise KeyboardInterrupt
        try:
            signal.signal(signal.SIGINT, _posix_handler)
            signal.signal(signal.SIGTERM, _posix_handler)
        except Exception:
            pass


if __name__ == "__main__":
    _install_signal_handlers()
    port = int(os.getenv("PORT", os.getenv("ANARA_PORT", "8000")))
    _assert_port_free(port)
    dev_reload = os.getenv("ANARA_RELOAD", "false").lower() in ("true", "1", "yes")
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            log_level="info",
            reload=dev_reload
        )
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("[Anara] Backend server shut down safely.")
        sys.exit(0)
