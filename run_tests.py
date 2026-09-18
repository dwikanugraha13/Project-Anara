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
        print(f"  [FAIL] {name:42} -> {e}")
        failed += 1

print("\n" + "-" * 65)
print(f"  Results: {passed} passed, {failed} failed.")
print("=" * 65 + "\n")

if failed > 0:
    sys.exit(1)
