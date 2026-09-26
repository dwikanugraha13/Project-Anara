import re
import threading
from typing import Any, Dict, Tuple

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


def _infer_model_badge_and_category(model_id: str, name: str, provider: str) -> Tuple[str, str, str]:
    """Generates appropriate badge, category, and icon based on model properties without brittle substring collisions."""
    m_lower = f"{model_id} {name}".lower()

    if re.search(r'\b(live-preview|realtime|audio|voice)\b', m_lower) or ("live" in m_lower and "gemini" in m_lower):
        return "Live Audio", "voice_native", provider if provider != "openai_compatible" else "gemini"
    if re.search(r'\bclaude-3[-.]7\b', m_lower):
        return "Hybrid Reasoning", "deep_reasoning", provider
    if re.search(r'\bclaude-3[-.]5\b', m_lower):
        return "Advanced Logic", "deep_reasoning", provider
    if re.search(r'\b(gpt-4o-mini)\b', m_lower):
        return "Fast General", "fast_general", "openai"
    if re.search(r'\b(o[3-9]|o[3-9]-mini)\b', m_lower):
        return "High Reasoning", "deep_reasoning", "openai"
    if re.search(r'\b(o1|o1-mini|o1-preview)\b', m_lower):
        return "Deep Reasoning", "reasoning", "openai"
    if re.search(r'\b(deepseek-r1|r1)\b', m_lower):
        return "Deep Reasoning", "reasoning", "deepseek"
    if re.search(r'\b(gpt-4o|gpt-4\.5|chatgpt)\b', m_lower):
        return "Omnimodal", "deep_reasoning", "openai"
    if re.search(r'\bcodex\b', m_lower):
        return "Code & Logic", "agentic", "openai"
    if re.search(r'\bflash-lite\b', m_lower):
        return "Ultra Fast", "fast_general", "gemini"
    if re.search(r'\bflash\b', m_lower):
        return "Multimodal", "reasoning", "gemini"
    if "gemini" in m_lower and "pro" in m_lower:
        return "Deep Reasoning", "deep_reasoning", "gemini"
    if re.search(r'\bgemma\b', m_lower):
        return "Lightweight", "fast_general", "gemini"

    return "General AI", "fast_general", provider
