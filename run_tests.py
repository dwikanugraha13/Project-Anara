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
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

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
    ("Anara Anti-Leak Sanitizer on Lead Text", ts.test_anti_leak_sanitizer_on_lead_narration),
    ("Voice Channel Presenter & TTS Audio Filter", ts.test_voice_channel_presenter_and_tts_filter),
    ("Voice Spoken Approval Pass-Through", ts.test_voice_approval_pass_through_and_intents),
    ("Safe Inspection Commands Zero Interruption", ts.test_safe_inspection_commands_zero_interruption),
    ("Omnichannel /voice Command & 4 Modes", ts.test_omnichannel_voice_command_and_modes),
    ("Anara Hard Interrupt & Process Reaper", ts.test_hard_interrupt_and_process_reaper),
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
    ("Hermes Parity: Repetition Guard", lambda: _run_hermes_test("test_repetition_guard_detects_degenerate_line_loop")),
    ("Hermes Parity: Periodic Anchor Runs", lambda: _run_hermes_test("test_repetition_guard_detects_periodic_anchor_runs")),
    ("Hermes Parity: Image Eviction Policy", lambda: _run_hermes_test("test_image_eviction_retires_oldest_carrier_blocks")),
    ("Hermes Parity: Persist-Before-Execute", lambda: _run_hermes_test("test_persist_before_execute_checkpoint")),
    ("Hermes Parity: Credential Pool Cooldown", lambda: _run_hermes_test("test_credential_pool_cooldown_arming")),
    ("Hermes Parity: Thinking-Only Auto-Nudge", lambda: _run_hermes_test("test_thinking_only_empty_response_guard")),
    ("Hermes Parity: Context Pinning Immunity", lambda: _run_hermes_test("test_context_pinning_immunity")),
    ("Hermes Parity: Trajectory Recording", lambda: _run_hermes_test("test_trajectory_recorder_format")),
    ("Hermes Parity: Background Review Queue", lambda: _run_hermes_test("test_background_review_idle_queue")),
    ("Hermes Parity: Destructive Git Block", lambda: _run_hermes_test("test_destructive_git_operations_blocked")),
    ("Hermes Parity: Binary Read File Guard", lambda: _run_hermes_test("test_binary_guard_blocks_raw_text")),
    ("Hermes Parity: In-Process Syntax Gate", lambda: _run_hermes_test("test_inproc_linter_syntax_gate")),
    ("Hermes Parity: Slash /btw & /pin Hub", lambda: _run_hermes_test("test_slash_commands_btw_and_pin")),
    ("Hermes Parity: Thinking Timeout Guidance", lambda: _run_hermes_test("test_thinking_timeout_guidance")),
    ("Hermes Parity: Binary Write & Blind Overwrite", lambda: _run_hermes_test("test_binary_write_and_blind_overwrite_guard")),
    ("Hermes Parity: Transcript Repair Engine", lambda: _run_hermes_test("test_transcript_repair_engine")),
    ("Hermes Parity: Verification Stop Gate", lambda: _run_hermes_test("test_verification_stop_gate")),
    ("Hermes Parity: ANSI & Smuggling Strip", lambda: _run_hermes_test("test_ansi_and_unicode_tag_stripping")),
    ("Hermes Parity: Inbound Dedup & Replay", lambda: _run_hermes_test("test_inbound_message_deduplicator_and_fingerprint")),
    ("Hermes Parity: Silence Narration Suppress", lambda: _run_hermes_test("test_gateway_silence_narration_suppressor")),
    ("Hermes Parity: YAML Multi-Doc & Tags", lambda: _run_hermes_test("test_yaml_multidoc_and_custom_tag_lint_gate")),
    ("Hermes Parity: Turn Preflight Gate", lambda: _run_hermes_test("test_turn_preflight_pressure_gate")),
    ("Pi Parity: Cumulative File Compaction", lambda: _run_hermes_test("test_pi_cumulative_file_state_compaction")),
    ("Hermes Parity: Parallel Tool ID Uniquification", lambda: _run_hermes_test("test_hermes_parallel_tool_id_uniquification_and_mixed_batch")),
    ("Pi Parity: Dual Queue Steering vs Follow-Up", lambda: _run_hermes_test("test_pi_dual_queue_steering_vs_followup")),
    ("Micro-Edit: Hashline Precision & Polymorphic", lambda: _run_hashline_tests()),
    ("Lossless Compaction: SnapCompact Bitmaps", lambda: _run_snapcompact_tests()),
    ("Auto-Thinking Dynamic Classifier", lambda: _run_auto_thinking_tests()),
    ("Friction-Gated Memory: Sharpshooter Gate", lambda: _run_sharpshooter_tests()),
    ("Hardening: Parallel Batch Return Exceptions", lambda: _run_hardening_test("test_parallel_batch_return_exceptions_isolation")),
    ("Hardening: Stream Consumer Session Lock", lambda: _run_hardening_test("test_stream_consumer_session_lock_concurrency")),
    ("Hardening: File Tools Posix Normalization", lambda: _run_hardening_test("test_fs_tools_path_normalization_posix")),
    ("Parity Point 1: Tool Secret Redaction", lambda: _run_perfectionist_test("test_secret_redaction_tool_data")),
    ("Parity Point 2: Context Grounding Expansion", lambda: _run_perfectionist_test("test_context_references_parsing_and_expansion")),
    ("Parity Point 3: Real-Time Title Broadcast", lambda: _run_perfectionist_test("test_session_title_broadcast")),
    ("Parity Point 4: Rolling Prompt Cache Plan", lambda: _run_perfectionist_test("test_rolling_prompt_caching")),
    ("Professional Pillar 1: Phased Turn Pipeline", lambda: _run_pillar_tests("test_pillar_1_phased_turn_pipeline")),
    ("Professional Pillar 2: Time-Traveling Stream Rules", lambda: _run_pillar_tests("test_pillar_2_time_traveling_stream_rules")),
    ("Professional Pillar 3: In-Process Tool Execution Bridge", lambda: _run_pillar_tests("test_pillar_3_in_process_code_execution_bridge")),
    ("Professional Pillar 4: Loopback Tool Execution Safety", lambda: _run_pillar_tests("test_pillar_4_fast_loopback_resolution")),
]

def _run_pillar_tests(method_name: str):
    import unittest
    import backend.tests.test_professional_orchestrator_pillars as tpop
    suite = unittest.TestSuite()
    suite.addTest(tpop.TestProfessionalOrchestratorPillars(method_name))
    runner = unittest.TextTestRunner(stream=open(os.devnull, "w"))
    result = runner.run(suite)
    if not result.wasSuccessful():
        raise RuntimeError(f"{method_name} failed: {result.errors or result.failures}")

def _run_sharpshooter_tests():
    import backend.tests.test_sharpshooter as tss
    tss.test_detect_friction_corrective()
    tss.test_detect_friction_regression()
    tss.test_detect_friction_architecture_decision()
    tss.test_detect_friction_non_friction_chat()
    tss.test_maybe_record_friction_decision()

def _run_auto_thinking_tests():
    import backend.tests.test_auto_thinking as tat
    tat.test_classify_trivial_greetings_and_pings()
    tat.test_classify_trivial_inspect_and_read()
    tat.test_classify_hard_architectural_tasks()
    tat.test_classify_moderate_general_tasks()
    tat.test_resolve_auto_thinking_effort()

def _run_snapcompact_tests():
    import backend.tests.test_snapcompact as tsc
    tsc.test_snapcompact_support()
    tsc.test_render_bitmap_frame_dimensions()
    tsc.test_render_conversation_to_frames_creates_valid_png()

def _run_hashline_tests():
    import asyncio
    import backend.tests.test_hashline_precision as th
    th.test_hashline_tag_computation_and_determinism()
    th.test_hashline_syntax_detection()
    th.test_hashline_apply_put_range()
    th.test_hashline_apply_insert_before_and_after()
    th.test_hashline_apply_cut_and_named_registers()
    th.test_hashline_stale_anchor_rejection()
    asyncio.run(th.test_fs_tools_polymorphic_read_and_edit())
    asyncio.run(th.test_inner_loop_syntax_regression_detection())
    th.test_apply_from_sketch_mode_resolves_placeholders()
    asyncio.run(th.test_ast_outline_directory_on_large_file_read())
    th.test_speculative_tool_prefetching()

def _run_hermes_test(test_method_name: str):
    from backend.tests.test_hermes_parity_pillars import TestHermesParityPillars
    suite = TestHermesParityPillars()
    getattr(suite, test_method_name)()

def _run_hardening_test(test_method_name: str):
    from backend.tests.test_harness_hardening_points import TestHarnessHardeningPoints
    suite = TestHarnessHardeningPoints()
    getattr(suite, test_method_name)()

def _run_perfectionist_test(test_method_name: str):
    from backend.tests.test_perfectionist_parity import TestPerfectionistParity
    suite = TestPerfectionistParity()
    getattr(suite, test_method_name)()


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
