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
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from memory import memory_engine, get_current_indonesian_time_str
from core import ModelCapabilityRegistry
from integrations import start_whatsapp_bridge
from tools import register_agent_event_listener
from shared_state import (
    active_sessions,
    broadcast_agent_event,
    broadcast_brain_sync,
    close_shared_http_client,
)

# Import Modular Routers
from routers.brain_routes import router as brain_router
from routers.provider_routes import router as provider_router
from routers.workspace_routes import router as workspace_router
from routers.integration_routes import router as integration_router
from routers.session_routes import router as session_router
from routers.gateway_routes import router as gateway_router
from routers.telemetry_routes import router as telemetry_router
from websocket.handler import router as websocket_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("ai_service").setLevel(logging.DEBUG)
logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
logging.getLogger("watchfiles").setLevel(logging.WARNING)

logger = logging.getLogger("anara.main")
ANARA_BUILD = "2026-09-12-modular-architecture-v2"

# Register real-time cross-service event listeners
register_agent_event_listener(broadcast_agent_event)
memory_engine.register_mutation_listener(broadcast_brain_sync)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts background services, initializes provider keys, and manages graceful shutdown."""
    logger.info(f"[Anara] Backend code loaded — build {ANARA_BUILD}")
    try:
        start_whatsapp_bridge()
    except Exception as e:
        logger.warning(f"[Startup] WhatsApp bridge start skipped: {e}")
    try:
        seeded = ModelCapabilityRegistry.seed_live_voice_from_key_manager()
        if seeded:
            logger.info(f"[Startup] Seeded {seeded} Live Voice model(s) from key pool.")
    except Exception as e:
        logger.warning(f"[Startup] Live Voice seed skipped: {e}")
    try:
        asyncio.create_task(ModelCapabilityRegistry.refresh())
    except Exception as e:
        logger.warning(f"[Startup] Capability warmup skipped: {e}")

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

    # Seed agentskills.io folder skill library from database if empty
    try:
        from core.skill_library import skill_library
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

    yield

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

    await close_shared_http_client()

# FastAPI application instance
app = FastAPI(
    title="Anara 3D Voice & Visual AI API",
    description="Modular real-time voice & text AI assistant with 3D avatar, code IDE, and holographic HUD",
    version="3.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check & system overview endpoint
@app.get("/")
async def health_check():
    """Health check & status endpoint."""
    time_info = get_current_indonesian_time_str()
    stats = memory_engine.get_brain_stats()
    return {
        "status": "ok",
        "service": "Project Anara",
        "active_sessions": len(active_sessions),
        "brain_stats": stats,
        "time": time_info
    }

# ── Mount Modular APIRouters ──
app.include_router(brain_router)
app.include_router(provider_router)
app.include_router(workspace_router)
app.include_router(integration_router)
app.include_router(session_router)
app.include_router(gateway_router)
app.include_router(telemetry_router)
app.include_router(websocket_router)

def _assert_port_free(port: int):
    """Startup guard: checks if port is free before starting."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("0.0.0.0", port))
        sock.close()
    except OSError:
        sock.close()
        owner_pid = "???"
        try:
            import subprocess
            cmd = f'powershell -NoProfile -Command "(Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue).OwningProcess"'
            out = subprocess.check_output(cmd, shell=True, text=True).strip()
            if out:
                owner_pid = out.split()[0]
        except Exception:
            pass
        logger.error(
            f"[Anara] PORT {port} MASIH DIPAKAI proses lain (PID {owner_pid})! "
            f"Matikan dulu dengan: Stop-Process -Id {owner_pid} -Force"
        )
        raise SystemExit(1)

if __name__ == "__main__":
    _assert_port_free(8000)
    try:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=True
        )
    except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
        logger.info("[Anara] Server backend telah dimatikan dengan aman.")
        sys.exit(0)
