"""
run_tests.py — Built-in Standard Test Runner for Project Anara.
Runs all test modules in backend/tests/ using pure Python stdlib unittest & assertion runner.
"""

import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Ensure hermetic environment
os.environ["ANARA_HOME"] = str(_REPO_ROOT / ".test_home")
os.environ["ANARA_TESTING"] = "1"

import backend.tests.test_subsystems as ts

print("\n" + "=" * 65)
print("   PROJECT ANARA — ENTERPRISE REGRESSION TEST HARNESS")
print("=" * 65 + "\n")

tests = [
    ("Context Compactor Pruning", ts.test_context_compactor_pruning),
    ("Context Compactor Protected Head/Tail", ts.test_context_compactor_protected_head_and_tail),
    ("Message Deduplicator Sliding Window", ts.test_message_deduplicator_sliding_window),
    ("Reasoning Effort Clamping", ts.test_reasoning_effort_clamping),
    ("Model Capabilities Universal Matrix", ts.test_model_capabilities_universal),
    ("Process Lifecycle Sentinel Ledger", lambda: ts.test_process_lifecycle_ledger(_REPO_ROOT / ".test_home")),
    ("Smart Output Truncation & Compaction", ts.test_smart_output_truncation),
    ("Anara Platform Tool Registry", ts.test_anara_platform_tool_registry),
    ("Anara Autonomous Memory Nudge", ts.test_anara_autonomous_memory_nudge),
    ("Anara Task Scratchpad Working State", ts.test_anara_task_scratchpad),
    ("Anara Telemetry Event Bus", ts.test_anara_telemetry_event_bus),
    ("Anara Tool Execution Tracer", ts.test_anara_tool_tracer),
    ("Anara Dynamic Loop Breaker", ts.test_anara_loop_breaker),
    ("Anara Unified Command Hub", ts.test_unified_command_hub),
    ("Anara Tool Decorator & Schema Extraction", ts.test_anara_tool_decorator_and_schema_extraction),
    ("Anara Vision & Video Analysis Tools", ts.test_anara_vision_and_video_tools),
    ("Multi-Tool Parsing & Parallel Execution", ts.test_multi_tool_parsing_and_parallelism),
    ("Autonomous Self-Correction Retrier", ts.test_autonomous_inner_verification_self_correction),
    ("Anara Execution Runner & Lifecycle", ts.test_anara_execution_runner_lifecycle),
    ("Universal Channel Presenter Registry", ts.test_universal_channel_adapter_presenters),
    ("Dynamic Contextual Rationale (Zero Canned)", ts.test_dynamic_action_rationale_zero_canned),
    ("Zero Memory Pollution & UI Decoupling", ts.test_zero_memory_pollution_and_decoupling),
    ("Hermes Anti-Leak Sanitizer on Lead Text", ts.test_hermes_anti_leak_sanitizer_on_lead_narration),
    ("Voice Channel Presenter & TTS Audio Filter", ts.test_voice_channel_presenter_and_tts_filter),
    ("Voice Spoken Approval Pass-Through", ts.test_voice_approval_pass_through_and_intents),
    ("Safe Inspection Commands Zero Interruption", ts.test_safe_inspection_commands_zero_interruption),
    ("Omnichannel /voice Command & 4 Modes", ts.test_omnichannel_voice_command_and_modes),
    ("Hermes Hard Interrupt & Process Reaper", ts.test_hermes_hard_interrupt_and_process_reaper),
    ("Slash Commands Text-Only UI Delivery", ts.test_slash_commands_never_trigger_voice),
    ("State-Machine PendingAction Lifecycle", ts.test_state_machine_pending_action_lifecycle),
    ("Context Micro-Compactor & Anchor Sniffing", ts.test_subsystem_4_context_micro_compactor),
    ("Error Classifier & Recovery Guidance", ts.test_subsystem_4_error_classifier_and_recovery_guidance),
    ("Self-Correction Circuit Breaker & Card", ts.test_subsystem_4_self_correction_circuit_breaker_and_card),
    ("Live Worktree Snapshot & Ground Truth", ts.test_subsystem_4_workspace_ground_truth_snapshot),
    ("Targeted Delete & Repo Protection", ts.test_subsystem_4_targeted_delete_and_repo_protection),
    ("Screen Metrics & Chronological Context", ts.test_subsystem_2_screen_metrics_and_chronological_context),
    ("Universal Computer Use (CUA)", ts.test_subsystem_2_computer_use_multiversal),
    ("Workspace Sentinel & Ground Truth", ts.test_subsystem_5_workspace_sentinel_and_ground_truth),
    ("Sub-Agent Delegation Engine", ts.test_pilar_1_subagent_delegation_engine),
    ("Omnichannel Approval Dispatcher", ts.test_subsystem_3_universal_channel_approval_dispatch),
    ("Live Telemetry & Visual HUD Events", ts.test_pillar_2_telemetry_hud_visual_events),
    ("Episodic ADR Project Memory", ts.test_pillar_3_episodic_adr_project_memory),
    ("Telegram Semantic Chunking & Tag Balance", ts.test_telegram_semantic_chunking_and_tag_balancing),
]

passed = 0
failed = 0

for name, test_fn in tests:
    t0 = time.time()
    try:
        test_fn()
        dt = (time.time() - t0) * 1000
        print(f"  [PASS] {name:42} ({dt:.1f}ms)")
        passed += 1
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc().strip().splitlines()[-1]
        print(f"  [FAIL] {name:42} -> {err_detail}")
        failed += 1

print("\n" + "-" * 65)
print(f"  Results: {passed} passed, {failed} failed.")
print("=" * 65 + "\n")

if failed > 0:
    sys.exit(1)
