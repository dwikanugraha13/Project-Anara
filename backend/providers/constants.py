from typing import Any, Dict

# Provider Metadata Definition
PROVIDER_METADATA: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "id": "gemini",
        "name": "Google AI Studio",
        "badge": "Gemini Live AI",
        "icon": "gemini",
        "description": "Provider utama untuk suara audio dua arah real-time (Gemini Live) dan model multimodal Google.",
        "auth_type": "api_key",
        "signup_url": "https://aistudio.google.com/app/apikey",
        "signup_label": "Buat Key Gratis di Google AI Studio ↗",
        "key_placeholder": "AIzaSy... atau AQ.Ab8...",
        "help_text": "Mendukung multi-akun dengan auto-failover saat terkena limit kuota.",
    },
    "anthropic": {
        "id": "anthropic",
        "name": "Anthropic Claude Direct",
        "badge": "Claude AI Official",
        "icon": "anthropic",
        "description": "Akses API resmi langsung ke Anthropic Console untuk model Claude 3.7 Sonnet, Claude 3.5 Sonnet, dan Haiku.",
        "auth_type": "api_key_or_google",
        "signup_url": "https://console.anthropic.com/",
        "signup_label": "Login Google di Anthropic Console ↗",
        "key_placeholder": "sk-ant-api03-...",
        "help_text": "Gunakan API key dari console.anthropic.com (bisa masuk dengan akun Google).",
    },
    "codex": {
        "id": "codex",
        "name": "OpenAI Codex",
        "badge": "OAuth PKCE",
        "icon": "openai",
        "description": "Akses resmi model penalaran koding OpenAI (o3-mini, o1, GPT-4o, Codex 5.3) via login akun ChatGPT (OAuth PKCE) atau API key.",
        "auth_type": "oauth_or_key",
        "signup_url": "https://chatgpt.com/codex",
        "signup_label": "Portal ChatGPT Codex ↗",
        "key_placeholder": "sk-proj-... atau Access Token",
        "help_text": "Mendukung login langsung dengan akun OpenAI via OAuth PKCE atau API key.",
    },
}

# In-Memory Cache for dynamically discovered models
_DYNAMIC_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 600  # 10 minutes cache TTL


def _infer_model_badge_and_category(model_id: str, name: str, provider: str) -> tuple[str, str, str]:
    """Generates appropriate badge, category, and icon based on model properties."""
    m_lower = f"{model_id} {name}".lower()
    
    if "live" in m_lower or "audio" in m_lower or model_id == "gemini-3.1-flash-live-preview":
        return "Live Audio", "voice_native", "gemini"
    if "claude-3-7" in m_lower or "claude-3.7" in m_lower:
        return "Hybrid Reasoning", "deep_reasoning", provider
    if "claude-3-5" in m_lower or "claude-3.5" in m_lower:
        return "Advanced Logic", "deep_reasoning", provider
    if "o3-mini" in m_lower or "o3" in m_lower:
        return "High Reasoning", "deep_reasoning", "openai"
    if "o1" in m_lower:
        return "Deep Reasoning", "reasoning", "openai"
    if "gpt-4o-mini" in m_lower:
        return "Fast General", "fast_general", "openai"
    if "gpt-4o" in m_lower or "gpt-4.5" in m_lower or "chatgpt" in m_lower:
        return "Omnimodal", "deep_reasoning", "openai"
    if "codex" in m_lower:
        return "Code & Logic", "agentic", "openai"
    if "flash-lite" in m_lower:
        return "Ultra Fast", "fast_general", "gemini"
    if "flash" in m_lower:
        return "Multimodal", "reasoning", "gemini"
    if "pro" in m_lower:
        return "Deep Reasoning", "deep_reasoning", "gemini"
    if "gemma" in m_lower:
        return "Lightweight", "fast_general", "gemini"
    
    return "General AI", "fast_general", provider
