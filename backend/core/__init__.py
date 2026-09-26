"""
backend.core — Modular Package Root & Facade.
PEP 562 Lazy Loading Architecture (Anara Enterprise Architecture).
Eliminates circular imports, guarantees 100% export synchronization, and provides instant startup.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

# Explicit 1:1 Mapping of Public Symbols to Submodules
_EXPORTS: dict[str, str] = {
    # key_manager
    "GeminiKeyManager": ".key_manager",
    "key_manager": ".key_manager",
    # capabilities
    "ModelCapabilityRegistry": ".capabilities",
    # live_service
    "GeminiLiveService": ".live_service",
    "SYSTEM_PROMPT": ".live_service",
    # agent
    "AnaraAgent": ".agent",
    "anara_agent": ".agent",
    # subagent
    "SubAgentManager": ".subagent",
    "subagent_manager": ".subagent",
    "SubAgentTask": ".subagent",
    # prompt_assembler
    "PromptAssembler": ".prompt_assembler",
    # context_compactor
    "ContextCompactor": ".context_compactor",
    "prune_tool_output": ".context_compactor",
    # skill_extractor
    "SkillExtractor": ".skill_extractor",
    # skill_library
    "SkillLibraryManager": ".skill_library",
    "skill_library": ".skill_library",
    "slugify": ".skill_library",
    # skills_hub
    "search_skills": ".skills_hub",
    "install_skill_from_hub": ".skills_hub",
    "uninstall_skill": ".skills_hub",
    "load_index": ".skills_hub",
    "get_available_sources": ".skills_hub",
    # skills_sync
    "sync_bundled_skills": ".skills_sync",
    # process_registry
    "ProcessRegistry": ".process_registry",
    "process_registry": ".process_registry",
    # tunnel_manager / gateway_manager
    "start_quick_tunnel": ".tunnel_manager",
    "stop_tunnel": ".tunnel_manager",
    "get_tunnel_status": ".tunnel_manager",
    "ensure_cloudflared_installed": ".tunnel_manager",
    "get_cloudflared_path": ".tunnel_manager",
    # reasoning_effort
    "clamp_effort": ".reasoning_effort",
    "to_openai_reasoning": ".reasoning_effort",
    "to_anthropic_thinking": ".reasoning_effort",
    "to_gemini_thinking": ".reasoning_effort",
    "EFFORT_LADDER": ".reasoning_effort",
    # sandbox
    "CommandSandbox": ".sandbox",
    "command_sandbox": ".sandbox",
    "get_sanitized_environment": ".sandbox",
    "check_command_safety": ".sandbox",
    # security
    "check_prompt_injection": ".security",
    "is_authorized_approver": ".security",
    "require_gateway_auth": ".security",
    "is_request_local": ".security",
    "verify_gateway_session_token": ".security",
    # session_manager
    "ActionState": ".session_manager",
    "PendingAction": ".session_manager",
    "session_state_manager": ".session_manager",
    # autonomous_engine
    "AutonomousEngine": ".autonomous_engine",
    "autonomous_engine": ".autonomous_engine",
    "evaluate_trust_approval": ".autonomous_engine",
    # channel_adapter
    "ChannelRequest": ".channel_adapter",
    "ChannelResponse": ".channel_adapter",
    "process_channel_request": ".channel_adapter",
    "resolve_pending_plan_callback": ".channel_adapter",
    "dispatch_channel_approval_resolution": ".channel_adapter",
    "UniversalChannelAdapter": ".channel_adapter",
    "BaseChannelPresenter": ".channel_adapter",
    "generate_dynamic_action_rationale": ".channel_adapter",
    "synthesize_action_rationale": ".channel_adapter",
    # plan_detector
    "needs_plan": ".plan_detector",
    "is_explicit_plan_approval": ".plan_detector",
    "classify_approval_intent": ".plan_detector",
    "smart_evaluate_command_safety": ".plan_detector",
    "detect_tools_from_text": ".plan_detector",
    "get_highest_risk": ".plan_detector",
    # command_hub
    "handle_channel_command": ".command_hub",
    "get_chat_voice_mode": ".command_hub",
    "set_chat_voice_mode": ".command_hub",
    "command_hub": ".command_hub",
    "CommandButton": ".command_hub",
    "UniversalCommandContext": ".command_hub",
    "UniversalCommandResponse": ".command_hub",
    "UnifiedCommandHub": ".command_hub",
    # runner
    "AnaraExecutionRunner": ".runner",
    "TurnEvent": ".runner",
    "AgentTurnResult": ".runner",
    # workspace_sentinel
    "WorkspaceSentinel": ".workspace_sentinel",
    "workspace_sentinel": ".workspace_sentinel",
    # convergence
    "ConvergenceDetector": ".convergence",
    "ConvergenceStatus": ".convergence",
    # prompt_loader
    "load_prompt": ".prompt_loader",
    "load_config_yaml": ".prompt_loader",
    # logger
    "setup_anara_logging": ".logger",
    "redact_sensitive_text": ".logger",
    "strip_ansi": ".logger",
    # lifecycle
    "record_process_start": ".lifecycle",
    "record_process_exit": ".lifecycle",
    "is_pid_alive": ".lifecycle",
    "get_process_pid": ".lifecycle",
    "get_process_start_time": ".lifecycle",
    "get_process_metadata": ".lifecycle",
    "cleanup_stale_processes": ".lifecycle",
    # token_budget
    "count_tokens": ".token_budget",
    "save_context_length": ".token_budget",
    "get_model_context_window": ".token_budget",
    "get_input_budget": ".token_budget",
    "parse_context_limit_from_error": ".token_budget",
    "budget_aware_slot_assembly": ".token_budget",
    "TokenBudgetTracker": ".token_budget",
}

__all__ = sorted(_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    """Dynamically loads requested symbols on first access (PEP 562)."""
    submodule = _EXPORTS.get(name)
    if submodule is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod = import_module(submodule, __name__)
    val = getattr(mod, name)
    globals()[name] = val
    return val


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + __all__)
