import re
import threading
from typing import Any, Dict, List, Optional, Tuple

# Single source of truth for native OpenAI-compatible endpoints
NATIVE_OPEN_ENDPOINTS: Dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com",
    "xai": "https://api.x.ai/v1",
}

# Provider Metadata Definition
PROVIDER_METADATA: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "id": "gemini",
        "name": "Google AI Studio",
        "badge": "Gemini Live AI",
        "icon": "gemini",
        "description": "Primary provider for bidirectional real-time audio (Gemini Live) and Google multimodal models.",
        "auth_type": "api_key",
        "signup_url": "https://aistudio.google.com/app/apikey",
        "signup_label": "Create Free Key at Google AI Studio ↗",
        "key_placeholder": "AIzaSy... or AQ.Ab8...",
        "help_text": "Supports multi-account with auto-failover when hitting quota limits.",
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude Direct",
        "badge": "Claude AI Official",
        "icon": "anthropic",
        "description": "Direct official API access to Anthropic Console for Claude 3.7 Sonnet, Claude 3.5 Sonnet, and Haiku models.",
        "auth_type": "api_key_or_google",
        "signup_url": "https://console.anthropic.com/",
        "signup_label": "Google Login at Anthropic Console ↗",
        "key_placeholder": "sk-ant-...",
        "help_text": "Use API key from console.anthropic.com (can sign in with Google account).",
    },
    "codex": {
        "id": "codex",
        "name": "OpenAI Codex",
        "badge": "OAuth PKCE",
        "icon": "openai",
        "description": "Access to OpenAI coding reasoning models (o3-mini, o1, GPT-4o) via ChatGPT account login (OAuth PKCE) or API key.",
        "auth_type": "oauth_or_key",
        "signup_url": "https://chatgpt.com/codex",
        "signup_label": "Portal ChatGPT Codex ↗",
        "key_placeholder": "sk-proj-... or Access Token",
        "help_text": "Supports direct login with OpenAI account via OAuth PKCE or API key.",
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI Official",
        "badge": "OpenAI API",
        "icon": "openai",
        "description": "Direct platform API access to OpenAI models (o3, o1, GPT-4o, GPT-4o-mini).",
        "auth_type": "api_key",
        "signup_url": "https://platform.openai.com/api-keys",
        "signup_label": "OpenAI Platform ↗",
        "key_placeholder": "sk-proj-...",
        "help_text": "Multi-account pool for direct OpenAI API access.",
    },
    "openrouter": {
        "id": "openrouter",
        "name": "OpenRouter",
        "badge": "Unified Gateway",
        "icon": "custom",
        "description": "Universal multi-provider gateway supporting Claude, GPT-4o, Gemini, and DeepSeek.",
        "auth_type": "api_key",
        "signup_url": "https://openrouter.ai/keys",
        "signup_label": "OpenRouter Keys ↗",
        "key_placeholder": "sk-or-v1-...",
        "help_text": "Universal gateway routing with competitive model pricing.",
    },
    "groq": {
        "id": "groq",
        "name": "Groq Cloud",
        "badge": "LPU Ultra-Fast",
        "icon": "custom",
        "description": "Ultra-low latency inference for Llama 3, Mixtral, and Gemma models.",
        "auth_type": "api_key",
        "signup_url": "https://console.groq.com/keys",
        "signup_label": "Groq Console ↗",
        "key_placeholder": "gsk_...",
        "help_text": "High-throughput inference for fast agentic reasoning loops.",
    },
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek Official",
        "badge": "Deep Reasoning",
        "icon": "custom",
        "description": "Official API for DeepSeek-R1 reasoning and DeepSeek-V3 chat models.",
        "auth_type": "api_key",
        "signup_url": "https://platform.deepseek.com/api_keys",
        "signup_label": "DeepSeek Platform ↗",
        "key_placeholder": "sk-...",
        "help_text": "Deep reasoning and high code efficiency at low token cost.",
    },
    "xai": {
        "id": "xai",
        "name": "xAI Grok",
        "badge": "Grok AI",
        "icon": "custom",
        "description": "Access to Grok 2 and Grok Beta models with real-time understanding.",
        "auth_type": "api_key",
        "signup_url": "https://console.x.ai/",
        "signup_label": "xAI Console ↗",
        "key_placeholder": "xai-...",
        "help_text": "Direct access to xAI Grok models.",
    },
}

# In-Memory Cache for dynamically discovered models with thread synchronization
_DYNAMIC_CACHE: Dict[str, Dict[str, Any]] = {}
_DYNAMIC_CACHE_LOCK = threading.RLock()
_CACHE_TTL_SECONDS = 600  # 10 minutes cache TTL

# Comprehensive 9Router and multi-tier proxy codename mappings
ROUTER_CODENAME_MAP: Dict[str, str] = {
    "ag": "Antigravity",
    "cl": "Claudeflare",
    "cf": "Cloudflare",
    "cx": "Cortex",
    "kr": "K-Router",
    "xkiro": "Xkiro",
    "crfcode": "CraftCode",
    "gcli": "Grok CLI",
    "nvidia": "NVIDIA NIM",
    "ollama": "Ollama",
    "openrouter": "OpenRouter",
    "atr": "Atria",
    "kgw": "Kilo Gateway",
    "kc": "Kilo Cloud",
}


def extract_model_route(model_id: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts the pure upstream router codename (e.g. 'ag', 'cx', 'cl', 'yz')
    from a model slug like '9router/ag/gemini-3.8-flash-high' or 'ag/gemini-3.8-flash-high'.
    Preserves raw provider route codes without artificial naming overrides (Hermes standard).
    """
    if not model_id:
        return None, None
    s = str(model_id).strip()
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 2 and parts[0].lower() == "9router":
        code = parts[1].lower()
        if code.startswith("comboantigravity") or code == "antigravity":
            return "ag", "ag"
        if code.startswith("comboopenrouter") or code == "openrouter":
            return "openrouter", "openrouter"
        return code, code
    elif len(parts) >= 2:
        code = parts[0].lower()
        return code, code
    return None, None


def extract_model_tier(model_id: Optional[str]) -> Optional[str]:
    """
    Extracts inherent reasoning tier embedded in model ID (e.g. '-high', '-medium', '-low', '-thinking').
    """
    if not model_id:
        return None
    m = re.search(r'[-_](high|medium|low|thinking|thought|reasoning)(?::[a-z]+)?$', str(model_id).strip(), re.I)
    if not m:
        return None
    val = m.group(1).lower()
    if val in ("high", "medium", "low"):
        return val
    return "thinking"


def format_model_display_name(raw: Optional[str], include_tier: bool = False) -> str:
    """
    Transforms raw provider slugs, multi-tier router paths, and proxy labels into
    clean, elegant, human-readable model titles.
    """
    if not raw:
        return "Model AI"
    s = str(raw).strip()
    tier = extract_model_tier(s)
    s = re.sub(r'\s*\([^)]*(?:proxy|custom|compatible)[^)]*\)', '', s, flags=re.I)
    segments = [p for p in s.split('/') if p]
    slug = segments[-1] if segments else s
    if len(segments) >= 2:
        parent = segments[-2].lower()
        if parent in ("ag", "kr", "cl", "cx", "atr", "openrouter", "custom"):
            slug = segments[-1]
        elif parent in ("perplexity", "cohere", "meta-llama", "qwen", "mistralai", "google", "openai", "anthropic"):
            slug = f"{segments[-2]} {segments[-1]}"
    slug = re.sub(r':(?:batch|free)$', '', slug, flags=re.I)
    lower = slug.lower()

    def get_base() -> str:
        # ── Gemini Family ──
        if "gemini-3.8-flash" in lower: return "Gemini 3.8 Flash"
        if "gemini-3.7-flash" in lower: return "Gemini 3.7 Flash"
        if "gemini-3.6-flash" in lower: return "Gemini 3.6 Flash"
        if "gemini-3.5-flash" in lower: return "Gemini 3.5 Flash"
        if "gemini-3.1-flash-live" in lower: return "Gemini 3.1 Live Audio"
        if "gemini-3.1-pro" in lower: return "Gemini 3.1 Pro"
        if "gemini-2.5-flash-live" in lower: return "Gemini 2.5 Live Audio"
        if "gemini-2.5-pro" in lower: return "Gemini 2.5 Pro"
        if "gemini-2.5-flash" in lower: return "Gemini 2.5 Flash"
        if "gemini-2.0-flash-live" in lower: return "Gemini 2.0 Live Audio"
        if "gemini-2.0-flash" in lower: return "Gemini 2.0 Flash"
        if "gemini-pro-latest" in lower or lower == "gemini-pro-agent": return "Gemini Pro"
        if "gemma-2-27b" in lower: return "Gemma 2 27B"
        if "gemma-2" in lower: return "Gemma 2"

        # ── Claude Family ──
        if "claude-sonnet-4.5" in lower: return "Claude Sonnet 4.5"
        if "claude-sonnet-4" in lower: return "Claude Sonnet 4"
        if "claude-opus-4" in lower: return "Claude Opus 4"
        if "claude-haiku-4.5" in lower: return "Claude Haiku 4.5"
        if "claude-fable-5.1" in lower: return "Claude Fable 5.1"
        if "claude-3-7-sonnet" in lower or "claude-3.7-sonnet" in lower: return "Claude 3.7 Sonnet"
        if "claude-3-5-sonnet" in lower or "claude-3.5-sonnet" in lower: return "Claude 3.5 Sonnet"
        if "claude-3-5-haiku" in lower or "claude-3.5-haiku" in lower: return "Claude 3.5 Haiku"
        if "claude-3-opus" in lower: return "Claude 3 Opus"

        # ── OpenAI Family ──
        if "gpt-6-astra" in lower: return "GPT-6 Astra"
        if "gpt-6-sol" in lower: return "GPT-6 Sol"
        if "gpt-6-luna" in lower: return "GPT-6 Luna"
        if "gpt-5.6-sol" in lower: return "GPT-5.6 Sol"
        if "gpt-5.6-terra" in lower: return "GPT-5.6 Terra"
        if "gpt-5.6-luna" in lower: return "GPT-5.6 Luna"
        if "gpt-5.5" in lower: return "GPT-5.5"
        if "gpt-5.4-mini" in lower: return "GPT-5.4 Mini"
        if "gpt-5.4" in lower: return "GPT-5.4"
        if "gpt-5.3-codex-spark" in lower: return "GPT-5.3 Codex Spark"
        if "codex-auto-review" in lower: return "Codex Auto Review"
        if "o3-mini" in lower: return "OpenAI o3-mini"
        if "o1-mini" in lower: return "OpenAI o1-mini"
        if "o1-preview" in lower or lower == "o1": return "OpenAI o1"
        if "gpt-4o-mini" in lower: return "GPT-4o Mini"
        if "gpt-4o" in lower: return "GPT-4o"
        if "gpt-4-turbo" in lower: return "GPT-4 Turbo"
        if "gpt-3.5-turbo" in lower: return "GPT-3.5 Turbo"

        # ── DeepSeek Family ──
        if "deepseek-r1" in lower: return "DeepSeek R1"
        if "deepseek-3.2" in lower: return "DeepSeek 3.2"
        if "deepseek-v4" in lower: return "DeepSeek V4"
        if "deepseek-v3" in lower or "deepseek-chat" in lower: return "DeepSeek V3"

        # ── MiniMax & GLM ──
        if "minimax-m2.5" in lower: return "MiniMax M2.5"
        if "minimax-m2.1" in lower: return "MiniMax M2.1"
        if "minimax3" in lower or "minimax-3" in lower: return "MiniMax 3"
        if "glm-5.3" in lower: return "GLM 5.3"
        if "glm-5" in lower: return "GLM 5"

        # ── Meta Llama Family ──
        if "llama-3.3-70b" in lower: return "Llama 3.3 70B"
        if "llama-3.2-3b" in lower: return "Llama 3.2 3B"
        if "llama-3.2-1b" in lower: return "Llama 3.2 1B"
        if "llama-3.1-405b" in lower: return "Llama 3.1 405B"
        if "llama-3.1-70b" in lower: return "Llama 3.1 70B"
        if "llama-3.1-8b" in lower: return "Llama 3.1 8B"

        # ── Qwen Family ──
        if "qwen-2.5-coder" in lower: return "Qwen 2.5 Coder"
        if "qwen-2.5-72b" in lower: return "Qwen 2.5 72B"
        if "qwen-2.5-7b" in lower: return "Qwen 2.5 7B"

        # ── Mistral & Cohere ──
        if "mistral-large" in lower: return "Mistral Large"
        if "mistral-nemo" in lower: return "Mistral Nemo"
        if "mixtral-8x22b" in lower: return "Mixtral 8x22B"
        if "command-r-plus" in lower: return "Command R+"
        if "command-r" in lower: return "Command R"
        if "command-a" in lower: return "Command A"

        # ── Perplexity & Antigravity ──
        if "sonar-reasoning-pro" in lower: return "Perplexity Sonar Pro"
        if "sonar-pro" in lower: return "Sonar Pro"
        if "comboantigravity-opus" in lower: return "Antigravity Opus"
        if "antigravity-preview" in lower: return "Antigravity Agent"

        # ── Generic Fallback ──
        cleaned = re.sub(r'-(?:thinking|agentic|high|medium|low|review|preview|latest)$', '', slug, flags=re.I)
        cleaned = re.sub(r'-(?:thinking|agentic|high|medium|low|review|preview|latest)-', '-', cleaned, flags=re.I)
        cleaned = re.sub(r'[._/-]', ' ', cleaned).strip()
        if not cleaned or cleaned.lower() in ("reasoning", "thinking"):
            cleaned = re.sub(r'[._/-]', ' ', slug).strip()
        return " ".join(w.upper() if len(w) <= 3 else w.capitalize() for w in cleaned.split())

    base_name = get_base()
    if include_tier and tier:
        tier_label = "Thinking" if tier == "thinking" else tier.capitalize()
        return f"{base_name} ({tier_label})"
    return base_name


def get_model_grounding_metadata(model_id: Optional[str], reasoning_effort: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns complete, authoritative model origin, gateway, and route grounding metadata
    for prompt assembly and agent self-identification.
    Accurately reflects active reasoning/thinking effort (Off, Low, Medium, High, Max, Ultra).
    """
    if not model_id:
        return {
            "model_id": "",
            "clean_name": "Model AI",
            "gateway": "Standard System",
            "route_name": "Universal",
            "route_code": None,
            "tier": None,
            "tier_display": "Off (Thinking Disabled / Standard Generation)",
            "serving_origin": "Universal AI Engine",
        }
    mid = str(model_id).strip()
    r_code, r_name = extract_model_route(mid)
    tier = extract_model_tier(mid)
    clean_name = format_model_display_name(mid, include_tier=False)

    # Determine exact active thinking / reasoning effort
    eff_clean = str(reasoning_effort).strip().lower() if reasoning_effort else None
    if eff_clean in ("off", "none", "0", "disabled", "false"):
        tier_display = "Off (Thinking Disabled / Standard Generation)"
    elif eff_clean:
        from core.reasoning_effort import clamp_effort
        # Model specific ceiling: frontier models support max/ultra, standard models capped at high
        allowed = ["low", "medium", "high", "max", "ultra"] if any(k in mid.lower() for k in ("astra", "gpt-6", "ultra", "opus-4", "sonnet-4")) else ["low", "medium", "high"]
        clamped = clamp_effort(eff_clean, allowed)
        tier_display = f"{clamped.capitalize()} Reasoning Effort"
    elif tier:
        tier_display = f"{tier.capitalize()} Reasoning Effort"
    else:
        # Check if model has inherent reasoning capability
        is_reasoning_model = any(k in mid.lower() for k in ("think", "reason", "r1", "qwq", "o1", "o3", "o4", "astra", "gemini-2.5", "gemini-3"))
        if is_reasoning_model:
            tier_display = "Active (Standard Reasoning Depth)"
        else:
            tier_display = "Off (Thinking Disabled / Standard Generation)"

    if mid.lower().startswith("9router/") or r_name:
        gateway = "9Router Proxy"
        route_display = r_name or "Custom Route"
        serving_origin = f"{route_display} via 9Router Proxy"
    elif mid.lower().startswith("anthropic/") or "claude" in mid.lower():
        gateway = "Anthropic Console Direct"
        route_display = "Anthropic"
        serving_origin = "Anthropic Official API"
    elif mid.lower().startswith("openai/") or mid.lower().startswith("codex/") or any(k in mid.lower() for k in ("gpt", "o1", "o3", "o4", "astra")):
        gateway = "OpenAI Direct"
        route_display = "OpenAI"
        serving_origin = "OpenAI Platform API"
    elif mid.lower().startswith("deepseek/") or "deepseek" in mid.lower():
        gateway = "DeepSeek Platform"
        route_display = "DeepSeek"
        serving_origin = "DeepSeek API"
    elif "gemini" in mid.lower():
        gateway = "Google AI Studio Direct"
        route_display = "Google AI Studio"
        serving_origin = "Google AI Studio (Gemini Developer API)"
    else:
        gateway = "Universal AI Engine"
        route_display = "Universal"
        serving_origin = "Universal AI Engine"

    return {
        "model_id": mid,
        "clean_name": clean_name,
        "gateway": gateway,
        "route_name": route_display,
        "route_code": r_code,
        "tier": tier,
        "tier_display": tier_display,
        "serving_origin": serving_origin,
    }


def _infer_model_badge_and_category(model_id: str, name: str, provider: str) -> Tuple[str, str, str]:
    """Generates appropriate badge, category, and icon based on model properties and router codenames."""
    m_lower = f"{model_id} {name}".lower()
    prov_icon = provider if provider not in ("openai_compatible", "custom") else "custom"

    # Check 9Router / router route codenames first for accurate badge & icon
    r_code, r_name = extract_model_route(model_id)

    if re.search(r'\b(live-preview|realtime|audio|voice)\b', m_lower) or ("live" in m_lower and "gemini" in m_lower):
        badge = r_name if r_name else "Live Audio"
        return badge, "voice_native", "gemini" if "gemini" in m_lower else prov_icon
    if re.search(r'\b(claude-4|claude-3[-.]7)\b', m_lower):
        badge = r_name if r_name else "Hybrid Reasoning"
        return badge, "deep_reasoning", "anthropic"
    if re.search(r'\b(claude-3[-.]5|claude.*(?:sonnet|opus))\b', m_lower):
        badge = r_name if r_name else "Advanced Logic"
        return badge, "deep_reasoning", "anthropic"
    if re.search(r'\b(gpt-4o-mini|gpt-4-mini|flash-lite)\b', m_lower):
        badge = r_name if r_name else "Fast General"
        return badge, "fast_general", "openai" if "gpt" in m_lower else prov_icon
    if re.search(r'\b(gpt-5|o[3-9]|o[3-9]-mini)\b', m_lower):
        badge = r_name if r_name else "High Reasoning"
        return badge, "deep_reasoning", "openai"
    if re.search(r'\b(o1|o1-mini|o1-preview)\b', m_lower):
        badge = r_name if r_name else "Deep Reasoning"
        return badge, "reasoning", "openai"
    if re.search(r'\b(deepseek-r1|deepseek/.*r1)\b', m_lower) or (provider == "deepseek" and "r1" in m_lower):
        badge = r_name if r_name else "Deep Reasoning"
        return badge, "reasoning", "deepseek"
    if re.search(r'\b(gpt-4o|gpt-4\.5|chatgpt)\b', m_lower):
        badge = r_name if r_name else "Omnimodal"
        return badge, "deep_reasoning", "openai"
    if re.search(r'\bcodex\b', m_lower):
        badge = r_name if r_name else "Code & Logic"
        return badge, "agentic", "openai"
    if "gemini" in m_lower and "flash-lite" in m_lower:
        badge = r_name if r_name else "Ultra Fast"
        return badge, "fast_general", "gemini"
    if "gemini" in m_lower and "flash" in m_lower:
        badge = r_name if r_name else "Multimodal"
        return badge, "reasoning", "gemini"
    if "gemini" in m_lower and ("pro" in m_lower or "ultra" in m_lower):
        badge = r_name if r_name else "Deep Reasoning"
        return badge, "deep_reasoning", "gemini"
    if re.search(r'\bgemma\b', m_lower):
        badge = r_name if r_name else "Lightweight"
        return badge, "fast_general", "gemini"
    if re.search(r'\b(r1|reasoner|reasoning|thinking|qwq)\b', m_lower):
        badge = r_name if r_name else "Deep Reasoning"
        return badge, "deep_reasoning", prov_icon

    badge = r_name if r_name else "General AI"
    return badge, "fast_general", prov_icon
