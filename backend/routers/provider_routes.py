"""
AI Providers, Dynamic Models, API Keys, Tokens, and Codex OAuth Routes for Project Anara.
"""
import asyncio
import base64
import hashlib
import json
import logging
import secrets
import time
import urllib.parse
from typing import Optional, List, Dict, Any, Tuple
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from memory import memory_engine
from core import ModelCapabilityRegistry
from providers import (
    get_all_dynamic_models,
    get_active_model_id,
    set_active_model_id,
    get_providers_status_list_async,
    add_provider_account,
    toggle_provider_account,
    delete_provider_account,
    save_provider_api_key,
    disconnect_provider_api_key,
    call_universal_chat_model,
    _DYNAMIC_CACHE,
)
from shared_state import (
    active_sessions,
    chat_diagnostics,
    get_shared_http_client,
)

logger = logging.getLogger("anara.routers.providers")

router = APIRouter(tags=["Providers & Models"])

class TestModelRequest(BaseModel):
    model_id: str
    user_prompt: Optional[str] = "Reply with exactly the word: pong"

class ModelActiveRequest(BaseModel):
    model_id: str

class ProviderKeyRequest(BaseModel):
    provider: str
    api_key: str
    account_label: Optional[str] = None

class ProviderAccountAddRequest(BaseModel):
    account_label: str
    api_key: str

class CustomProviderCreateRequest(BaseModel):
    name: str
    prefix: str
    api_type: str = "chat_completions"
    base_url: str
    api_key: str
    default_model: str = ""

class CustomProviderCheckRequest(BaseModel):
    base_url: str
    api_key: str
    api_type: str = "chat_completions"

class ModelHideRequest(BaseModel):
    model_id: str
    provider: Optional[str] = None

class OAuthExchangeRequest(BaseModel):
    code: str
    state: Optional[str] = None
    code_verifier: Optional[str] = None
    redirect_uri: Optional[str] = None

# ── Diagnostics ──

@router.get("/api/diagnostics/chat")
async def chat_diagnostics_endpoint():
    """Read-only status for diagnosing stalled text chat requests."""
    return {
        **chat_diagnostics,
        "active_websocket_sessions": len(active_sessions),
        "active_model": get_active_model_id(),
    }

@router.get("/api/diagnostics/active-model")
async def active_model_diagnostics():
    """Returns active model plus its voice/text capabilities from the metadata cache."""
    mid = get_active_model_id()
    return {
        "active_model": mid,
        "supports_voice": ModelCapabilityRegistry.supports_voice(mid),
        "supports_text": ModelCapabilityRegistry.supports_text(mid),
        "supports_vision": ModelCapabilityRegistry.supports_vision(mid),
    }

@router.post("/api/diagnostics/test-model")
async def test_model_endpoint(req: TestModelRequest):
    """Pings a model with a minimal prompt to verify it's working."""
    t0 = time.time()
    try:
        res = await asyncio.wait_for(
            call_universal_chat_model(
                model_id=req.model_id,
                user_prompt=req.user_prompt or "pong",
                system_instruction="Reply with 1 short sentence.",
                max_tokens=None,
                temperature=0.1
            ),
            timeout=12.0
        )
        dt = round(time.time() - t0, 2)
        return {"status": "ok", "latency_sec": dt, "model": req.model_id, "response": (res or "").strip()}
    except Exception as e:
        return {"status": "error", "model": req.model_id, "error": str(e)}

@router.get("/api/models/supported")
async def supported_models_endpoint(mode: Optional[str] = None):
    """Returns models filtered by capability for the requested mode (voice/text)."""
    await ModelCapabilityRegistry.refresh()
    cached = ModelCapabilityRegistry._cache
    if mode == "voice":
        items = [
            {"id": mid, **info}
            for mid, info in cached.items()
            if info.get("supports_voice")
        ]
    elif mode == "text":
        items = [
            {"id": mid, **info}
            for mid, info in cached.items()
            if info.get("output_modalities") and "text" in info["output_modalities"]
        ]
    else:
        items = [{"id": mid, **info} for mid, info in cached.items()]
    return {"mode": mode or "all", "count": len(items), "models": items}

# ── Dynamic Models & Providers ──

@router.get("/api/models")
async def list_models_endpoint(refresh: bool = False):
    """Returns the full catalog of AI models and live key configuration status."""
    models = await get_all_dynamic_models(force_refresh=refresh)
    return {
        "active_model_id": get_active_model_id(),
        "models": models,
    }

@router.get("/api/providers")
async def list_providers_endpoint(refresh: bool = False):
    """Returns all AI providers with live connection status, accounts list, and pulled models."""
    providers = await get_providers_status_list_async(force_refresh=refresh)
    return {
        "providers": providers,
        "active_model_id": get_active_model_id(),
    }

@router.post("/api/providers/{provider_name}/accounts")
async def add_provider_account_endpoint(provider_name: str, req: ProviderAccountAddRequest):
    """Adds a new account with custom label into the multi-account pool."""
    acc = add_provider_account(provider_name, req.account_label, req.api_key)
    if not acc:
        raise HTTPException(status_code=400, detail="Gagal menambahkan akun API key")
    providers = await get_providers_status_list_async(force_refresh=True)
    return {
        "status": "success",
        "account": acc,
        "providers": providers,
    }

@router.patch("/api/providers/{provider_name}/accounts/{account_id}/toggle")
async def toggle_provider_account_endpoint(provider_name: str, account_id: int):
    """Toggles active/disabled state of an account in the pool."""
    new_state = toggle_provider_account(provider_name, account_id)
    if new_state is None:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    providers = await get_providers_status_list_async(force_refresh=True)
    return {
        "status": "success",
        "account_id": account_id,
        "is_enabled": new_state,
        "providers": providers,
    }

@router.delete("/api/providers/{provider_name}/accounts/{account_id}")
async def delete_provider_account_endpoint(provider_name: str, account_id: int):
    """Deletes a specific account from the pool."""
    ok = delete_provider_account(provider_name, account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Akun tidak ditemukan")
    providers = await get_providers_status_list_async(force_refresh=True)
    return {
        "status": "success",
        "deleted_id": account_id,
        "providers": providers,
    }

@router.post("/api/providers/{provider_name}/connect")
async def connect_provider_endpoint(provider_name: str, req: ProviderKeyRequest):
    """Saves key/account and connects a provider, pulling its supported models in real-time."""
    label = req.account_label if req.account_label else f"{provider_name.capitalize()} Account"
    acc = add_provider_account(provider_name, label, req.api_key)
    providers = await get_providers_status_list_async(force_refresh=True)
    return {
        "status": "success",
        "provider": provider_name,
        "account": acc,
        "providers": providers,
    }

@router.post("/api/providers/{provider_name}/refresh")
async def refresh_provider_endpoint(provider_name: str):
    """Forces real-time re-fetching of models for all or a specific provider."""
    providers = await get_providers_status_list_async(force_refresh=True)
    return {"status": "success", "provider": provider_name, "providers": providers}

@router.post("/api/providers/{provider_name}/disconnect")
async def disconnect_provider_endpoint(provider_name: str):
    """Explicitly disconnects a provider, deleting all its accounts."""
    ok = disconnect_provider_api_key(provider_name)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Provider '{provider_name}' tidak dikenali")
    providers = await get_providers_status_list_async(force_refresh=True)
    return {"status": "success", "provider": provider_name, "providers": providers}

# ── Custom OpenAI/Anthropic Compatible Providers ──

@router.get("/api/providers/custom")
async def list_custom_providers_endpoint():
    """Lists all registered custom providers."""
    return {"custom_providers": memory_engine.get_custom_providers()}

@router.post("/api/providers/custom")
async def create_custom_provider_endpoint(req: CustomProviderCreateRequest):
    """Registers or updates an OpenAI/Anthropic-compatible custom provider."""
    pid = memory_engine.add_custom_provider(
        name=req.name,
        prefix=req.prefix,
        api_type=req.api_type,
        base_url=req.base_url,
        api_key=req.api_key,
        default_model=req.default_model,
    )
    _DYNAMIC_CACHE.pop("custom_providers", None)
    clean_pfx = req.prefix.strip().lower()
    _DYNAMIC_CACHE.pop(clean_pfx, None)
    providers = await get_providers_status_list_async(force_refresh=True)
    return {"status": "success", "provider": pid, "providers": providers}

@router.delete("/api/providers/custom/{provider_id}")
async def delete_custom_provider_endpoint(provider_id: int):
    """Deletes a custom provider and cleans its models."""
    ok = memory_engine.delete_custom_provider(provider_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Custom provider tidak ditemukan")
    _DYNAMIC_CACHE.pop("custom_providers", None)
    providers = await get_providers_status_list_async(force_refresh=True)
    return {"status": "success", "deleted_id": provider_id, "providers": providers}

@router.patch("/api/providers/custom/{provider_id}/toggle")
async def toggle_custom_provider_endpoint(provider_id: int):
    """Toggles a custom provider on/off directly."""
    new_state = memory_engine.toggle_custom_provider(provider_id)
    if new_state is None:
        raise HTTPException(status_code=404, detail="Custom provider tidak ditemukan")
    _DYNAMIC_CACHE.pop("custom_providers", None)
    providers = await get_providers_status_list_async(force_refresh=True)
    return {"status": "success", "provider_id": provider_id, "is_active": new_state, "providers": providers}

@router.post("/api/providers/custom/check")
async def check_custom_provider_endpoint(req: CustomProviderCheckRequest):
    """Pings a custom OpenAI/Anthropic endpoint to test connection."""
    client = get_shared_http_client()
    url = f"{req.base_url.rstrip('/')}/models"
    headers = {"Authorization": f"Bearer {req.api_key}"} if req.api_key else {}
    try:
        r = await client.get(url, headers=headers, timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            m_list = data.get("data", []) or data.get("models", [])
            return {
                "status": "ok",
                "message": f"Koneksi sukses! Ditemukan {len(m_list)} model di endpoint /models.",
                "models_count": len(m_list),
                "sample_models": [m.get("id", "") for m in m_list[:10]],
            }
        else:
            return {"status": "error", "message": f"Server merespon HTTP {r.status_code}: {r.text[:100]}"}
    except Exception as e:
        return {"status": "error", "message": f"Gagal terhubung: {str(e)}"}

# ── Hidden Models Management ──

@router.get("/api/models/hidden")
async def list_hidden_models_endpoint():
    """Lists all user-pruned/hidden model IDs."""
    return {"hidden_models": memory_engine.get_hidden_models()}

@router.post("/api/models/hide")
async def hide_model_endpoint(req: ModelHideRequest):
    """Prunes an unused model from the catalog and active selections."""
    ok = memory_engine.hide_model(req.model_id, req.provider)
    models = await get_all_dynamic_models(force_refresh=False)
    return {"status": "success" if ok else "error", "hidden_model_id": req.model_id, "models": models}

@router.delete("/api/models/hide/{model_id:path}")
async def unhide_model_endpoint(model_id: str):
    """Restores a previously hidden model."""
    ok = memory_engine.unhide_model(model_id)
    models = await get_all_dynamic_models(force_refresh=False)
    return {"status": "success" if ok else "error", "unhidden_model_id": model_id, "models": models}

@router.post("/api/models/hidden/restore-all")
async def restore_all_hidden_models_endpoint(provider: Optional[str] = None):
    """Restores all hidden models."""
    count = memory_engine.restore_all_hidden_models(provider)
    models = await get_all_dynamic_models(force_refresh=False)
    return {"status": "success", "restored_count": count, "models": models}

# ── Token Usage ──

@router.get("/api/tokens/summary")
async def get_token_summary_endpoint():
    """Returns aggregate usage statistics and provider credit overview."""
    summary = memory_engine.get_token_usage_summary()
    return summary

@router.get("/api/tokens/history")
async def get_token_history_endpoint(limit: int = 50):
    """Returns recent individual token usage logs."""
    logs = memory_engine.get_recent_token_logs(limit=limit)
    return {"count": len(logs), "logs": logs}

# ── Active Model & Keys ──

@router.post("/api/models/active")
async def set_active_model_endpoint(req: ModelActiveRequest):
    """Switches the active model ID."""
    ok = set_active_model_id(req.model_id)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Model '{req.model_id}' tidak valid")
    return {"status": "success", "active_model_id": req.model_id}

@router.post("/api/models/keys")
async def save_model_key_endpoint(req: ProviderKeyRequest):
    """Saves an API key for a specific AI provider."""
    ok = save_provider_api_key(req.provider, req.api_key)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Provider '{req.provider}' tidak dikenali")
    return {"status": "success", "provider": req.provider}

# ── OpenAI Codex CLI OAuth PKCE Engine ──

OPENAI_CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_CODEX_REDIRECT_URI = "http://localhost:1455/auth/callback"
OPENAI_CODEX_AUTH_URL = "https://auth.openai.com/oauth/authorize"
OPENAI_CODEX_TOKEN_URL = "https://auth.openai.com/oauth/token"
OPENAI_CODEX_SCOPE = "openid profile email offline_access"

_CODEX_OAUTH_SESSIONS: Dict[str, Dict[str, Any]] = {}

def _generate_codex_pkce() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge

def _extract_email_from_jwt(jwt_token: str) -> Optional[str]:
    try:
        parts = jwt_token.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
            if "email" in payload and payload["email"]:
                return payload["email"]
            profile = payload.get("https://api.openai.com/profile", {})
            if isinstance(profile, dict) and profile.get("email"):
                return profile["email"]
    except Exception:
        pass
    return None

class CodexOAuthPort1455Server:
    server: Optional[asyncio.AbstractServer] = None
    stop_timer: Optional[asyncio.TimerHandle] = None

    @classmethod
    async def start(cls):
        if cls.server is not None:
            return
        try:
            cls.server = await asyncio.start_server(cls._handle_client, "127.0.0.1", 1455)
            logger.info("[CodexOAuth] Temporary callback listener started on http://127.0.0.1:1455/auth/callback")
            loop = asyncio.get_running_loop()
            if cls.stop_timer:
                cls.stop_timer.cancel()
            cls.stop_timer = loop.call_later(300.0, lambda: asyncio.create_task(cls.stop()))
        except Exception as e:
            logger.warning(f"[CodexOAuth] Could not bind to port 1455: {e}")

    @classmethod
    async def stop(cls):
        if cls.server is not None:
            try:
                cls.server.close()
                await cls.server.wait_closed()
            except Exception:
                pass
            cls.server = None
            logger.info("[CodexOAuth] Port 1455 listener stopped.")

    @classmethod
    async def _handle_client(cls, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            req_data = await asyncio.wait_for(reader.read(8192), timeout=5.0)
            req_text = req_data.decode("utf-8", errors="ignore")
            first_line = req_text.split("\r\n")[0] if req_text else ""
            parts = first_line.split(" ")
            path = parts[1] if len(parts) > 1 else ""

            parsed = urllib.parse.urlparse(path)
            if parsed.path == "/auth/callback":
                qs = urllib.parse.parse_qs(parsed.query)
                code = qs.get("code", [""])[0].strip()
                state = qs.get("state", [""])[0].strip()
                error = qs.get("error", [""])[0].strip()
                error_desc = qs.get("error_description", [error])[0].strip()

                if error:
                    if state in _CODEX_OAUTH_SESSIONS:
                        _CODEX_OAUTH_SESSIONS[state]["status"] = "error"
                        _CODEX_OAUTH_SESSIONS[state]["error"] = error_desc
                    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Login Gagal</title></head>
                    <body style="font-family:system-ui,sans-serif;background:#090d16;color:#f87171;text-align:center;padding:50px;">
                      <h2>Otorisasi Ditolak</h2><p>{error_desc}</p>
                      <button onclick="window.close()" style="margin-top:20px;padding:10px 24px;border-radius:8px;background:#1e293b;color:white;border:1px solid #334155;cursor:pointer;">Tutup</button>
                    </body></html>"""
                elif code and state in _CODEX_OAUTH_SESSIONS:
                    session = _CODEX_OAUTH_SESSIONS[state]
                    verifier = session.get("code_verifier", "")
                    success, acc_or_err = await cls._exchange_tokens(code, verifier, state)
                    if success:
                        session["status"] = "success"
                        session["account"] = acc_or_err
                        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Login Berhasil</title>
                        <script>
                          if(window.opener){{try{{window.opener.postMessage({{type:'CODEX_OAUTH_SUCCESS',state:'{state}'}},'*');}}catch(e){{}}}}
                          setTimeout(function(){{window.close();}}, 1500);
                        </script></head>
                        <body style="font-family:system-ui,sans-serif;background:#090d16;color:#34d399;text-align:center;padding:50px;">
                          <div style="font-size:48px;margin-bottom:12px;">✓</div>
                          <h2 style="color:#ffffff;margin:0 0 10px 0;">Login OpenAI Codex Berhasil!</h2>
                          <p style="color:#94a3b8;font-size:14px;">Akun telah terhubung ke Anara. Jendela ini akan tertutup otomatis...</p>
                        </body></html>"""
                    else:
                        session["status"] = "error"
                        session["error"] = acc_or_err
                        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Pertukaran Token Gagal</title></head>
                        <body style="font-family:system-ui,sans-serif;background:#090d16;color:#f87171;text-align:center;padding:50px;">
                          <h2>Pertukaran Token Gagal</h2><p>{acc_or_err}</p>
                          <button onclick="window.close()" style="margin-top:20px;padding:10px 24px;border-radius:8px;background:#1e293b;color:white;border:1px solid #334155;cursor:pointer;">Tutup</button>
                        </body></html>"""
                else:
                    html = """<!DOCTYPE html><html><body><h3>Parameter callback tidak lengkap.</h3></body></html>"""

                resp_bytes = html.encode("utf-8")
                writer.write(f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(resp_bytes)}\r\nConnection: close\r\n\r\n".encode("ascii") + resp_bytes)
                await writer.drain()
            else:
                writer.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                await writer.drain()
        except Exception as e:
            logger.debug(f"[CodexOAuth] Client handler error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    @classmethod
    async def _exchange_tokens(cls, code: str, code_verifier: str, state: str) -> Tuple[bool, Any]:
        payload = {
            "grant_type": "authorization_code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": OPENAI_CODEX_REDIRECT_URI,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(OPENAI_CODEX_TOKEN_URL, data=payload, headers=headers)
                if res.status_code == 200:
                    token_data = res.json()
                    access_token = token_data.get("access_token", "")
                    refresh_token = token_data.get("refresh_token", "")
                    id_token = token_data.get("id_token", "")

                    email = _extract_email_from_jwt(id_token) or _extract_email_from_jwt(access_token)
                    label = f"OpenAI Codex ({email})" if email else "OpenAI Codex OAuth"

                    acc = add_provider_account("codex", label, access_token)
                    acc_id = acc.get("id") if isinstance(acc, dict) else None

                    if refresh_token and acc_id:
                        memory_engine.set_app_setting(f"codex_refresh_token_{acc_id}", refresh_token)
                    if refresh_token:
                        memory_engine.set_app_setting("codex_latest_refresh_token", refresh_token)

                    logger.info(f"[CodexOAuth] Successfully connected Codex account: {label}")
                    return True, {"label": label, "email": email, "account_id": acc_id}
                else:
                    err_msg = f"HTTP {res.status_code}: {res.text}"
                    logger.warning(f"[CodexOAuth] Token exchange failed: {err_msg}")
                    return False, err_msg
        except Exception as e:
            logger.warning(f"[CodexOAuth] Exchange exception: {e}")
            return False, str(e)

@router.get("/api/auth/{provider}/authorize-url")
async def oauth_authorize_url_endpoint(provider: str):
    prov = provider.strip().lower()
    if prov in ["codex", "openai"]:
        await CodexOAuthPort1455Server.start()
        verifier, challenge = _generate_codex_pkce()
        state = secrets.token_urlsafe(32)

        _CODEX_OAUTH_SESSIONS[state] = {
            "code_verifier": verifier,
            "code_challenge": challenge,
            "timestamp": time.time(),
            "status": "pending",
        }

        query_params = {
            "response_type": "code",
            "client_id": OPENAI_CODEX_CLIENT_ID,
            "redirect_uri": OPENAI_CODEX_REDIRECT_URI,
            "scope": OPENAI_CODEX_SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "codex_cli_rs",
            "state": state,
        }
        encoded_query = urllib.parse.urlencode(query_params)
        auth_url = f"{OPENAI_CODEX_AUTH_URL}?{encoded_query}"

        return {
            "status": "success",
            "provider": "codex",
            "authorize_url": auth_url,
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": OPENAI_CODEX_REDIRECT_URI,
            "oauth_flow": "pkce_codex_cli",
            "message": "Login langsung menggunakan akun OpenAI Anda via OAuth resmi Codex CLI."
        }
    elif prov == "anthropic":
        return {
            "status": "success",
            "provider": "anthropic",
            "authorize_url": "https://console.anthropic.com/",
            "oauth_flow": "google_login",
            "message": "Buka Anthropic Console untuk login via akun Google."
        }
    raise HTTPException(status_code=400, detail=f"OAuth authorize URL tidak didukung untuk '{prov}'")

@router.get("/api/auth/{provider}/status")
async def oauth_status_endpoint(provider: str, state: str):
    prov = provider.strip().lower()
    if prov in ["codex", "openai"]:
        session = _CODEX_OAUTH_SESSIONS.get(state)
        if not session:
            return {"status": "not_found"}
        res = {
            "status": session.get("status", "pending"),
            "account": session.get("account"),
            "error": session.get("error"),
        }
        if res["status"] == "success":
            providers = await get_providers_status_list_async(force_refresh=True)
            res["providers"] = providers
        return res
    return {"status": "unsupported"}

@router.post("/api/auth/{provider}/exchange")
async def oauth_exchange_endpoint(provider: str, req: OAuthExchangeRequest):
    prov = provider.strip().lower()
    if prov in ["codex", "openai"]:
        raw_code = req.code.strip()
        if not raw_code:
            raise HTTPException(status_code=400, detail="Token / Authorization code kosong")

        clean_code = raw_code
        state = req.state or ""

        if "code=" in raw_code:
            try:
                parsed = urllib.parse.urlparse(raw_code if "://" in raw_code else f"http://dummy?{raw_code}")
                qs = urllib.parse.parse_qs(parsed.query)
                clean_code = qs.get("code", [raw_code])[0].strip()
                if not state:
                    state = qs.get("state", [""])[0].strip()
            except Exception:
                pass

        if clean_code.startswith("eyJ") or clean_code.startswith("sk-"):
            email = _extract_email_from_jwt(clean_code) if clean_code.startswith("eyJ") else None
            label = f"OpenAI Codex ({email})" if email else "OpenAI Codex OAuth"
            add_provider_account("codex", label, clean_code)
            providers = await get_providers_status_list_async(force_refresh=True)
            return {"status": "success", "provider": "codex", "providers": providers}

        session = _CODEX_OAUTH_SESSIONS.get(state) if state else None
        verifier = req.code_verifier or (session.get("code_verifier", "") if session else "")
        if not verifier and _CODEX_OAUTH_SESSIONS:
            latest_state = list(_CODEX_OAUTH_SESSIONS.keys())[-1]
            verifier = _CODEX_OAUTH_SESSIONS[latest_state].get("code_verifier", "")

        if not verifier:
            raise HTTPException(status_code=400, detail="code_verifier tidak ditemukan. Silakan ulangi klik Login OAuth.")

        success, acc_or_err = await CodexOAuthPort1455Server._exchange_tokens(clean_code, verifier, state)
        if not success:
            raise HTTPException(status_code=400, detail=f"Pertukaran token gagal: {acc_or_err}")

        if state and state in _CODEX_OAUTH_SESSIONS:
            _CODEX_OAUTH_SESSIONS[state]["status"] = "success"
            _CODEX_OAUTH_SESSIONS[state]["account"] = acc_or_err

        providers = await get_providers_status_list_async(force_refresh=True)
        return {"status": "success", "provider": "codex", "account": acc_or_err, "providers": providers}

    elif prov == "google":
        memory_engine.set_app_setting("google_oauth_token", req.code)
        return {"status": "success", "provider": "google"}
    raise HTTPException(status_code=400, detail=f"OAuth tidak didukung untuk '{prov}'")
