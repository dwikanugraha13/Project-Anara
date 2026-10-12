"""
test_professional_orchestrator_pillars.py — Test Suite for Professional Orchestrator Pillars.
Verifies the 4 Enterprise Pillars inspired by Hermes Agent and Oh My Pi:
1. In-Process Code Execution Loopback Bridge (anara_tools)
2. Time-Traveling Stream Rules Engine (TTSR)
3. Phased Turn Pipeline Architecture (LoopPhaseState & TurnPhasePipeline)
4. Fast Loopback Endpoint Resolution (<100ms)
"""

import asyncio
import os
import sys
import unittest
from pathlib import Path

# Setup paths
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestProfessionalOrchestratorPillars(unittest.TestCase):

    def test_pillar_1_phased_turn_pipeline(self):
        """Pillar 1: Verifies LoopPhaseState initialization and tool partition logic."""
        from providers.turn_pipeline import LoopPhaseState, TurnPhasePipeline

        state = LoopPhaseState(
            step=1,
            max_steps=10,
            read_only=True,
            model_id="ag/gemini-3.8-flash",
            history=[{"role": "user", "content": "test"}]
        )
        self.assertEqual(state.step, 1)
        self.assertTrue(state.read_only)

        calls = [
            {"name": "read_local_file", "risk": "read_only", "args": {}},
            {"name": "grep_search_code", "risk": "read_only", "args": {}},
            {"name": "write_local_file", "risk": "mutating", "args": {}},
        ]
        batch, next_idx, is_ro = TurnPhasePipeline.partition_tool_batch(calls, 0)
        self.assertTrue(is_ro)
        self.assertEqual(len(batch), 2)
        self.assertEqual(next_idx, 2)

        batch2, next_idx2, is_ro2 = TurnPhasePipeline.partition_tool_batch(calls, next_idx)
        self.assertFalse(is_ro2)
        self.assertEqual(len(batch2), 1)
        self.assertEqual(next_idx2, 3)

    def test_pillar_2_time_traveling_stream_rules(self):
        """Pillar 2: Verifies TTSR detects simulated tool roleplay and destructive wipes."""
        from core.stream_rules import TimeTravelingStreamRulesEngine, StreamRuleViolation

        engine = TimeTravelingStreamRulesEngine()

        # Normal text passes through
        violation = engine.feed("Halo bro, berikut analisis kode yang lu minta.")
        self.assertIsNone(violation)

        # Simulated tool roleplay triggers immediate violation
        engine.reset()
        engine.feed("Oke tunggu sebentar ya, ")
        v_sim = engine.feed("*(sedang menjalankan perintah npm test)*")
        self.assertIsNotNone(v_sim)
        assert v_sim is not None
        self.assertEqual(v_sim.rule_name, "no_simulated_tools")

        # Destructive wipe pattern triggers immediate security violation
        engine.reset()
        v_wipe = engine.feed("Untuk membersihkan repository, jalankan `rm -rf /` di terminal")
        self.assertIsNotNone(v_wipe)
        assert v_wipe is not None
        self.assertEqual(v_wipe.rule_name, "no_destructive_wipe")

    def test_pillar_3_in_process_code_execution_bridge(self):
        """Pillar 3: Verifies execute_code can import anara_tools to call tools in-process."""
        from tools.code_execution_tools import _tool_execute_code

        snippet = """
from anara_tools import read_file, search_files
import os

read_res = read_file('run_tests.py', limit=5)
assert read_res.get('status') == 'success'
assert len(read_res.get('content', '')) > 0
print('PILLAR_3_SUCCESS')
"""
        res = asyncio.run(_tool_execute_code(code=snippet, language="python", timeout=15))
        self.assertEqual(res.get("status"), "success")
        self.assertIn("PILLAR_3_SUCCESS", res.get("stdout", ""))

    def test_pillar_4_fast_loopback_resolution(self):
        """Pillar 4: Verifies anara_tools functions execute cleanly without deadlocks."""
        from tools.anara_tools import json_parse, read_file

        # Tolerant JSON parse
        parsed = json_parse("```json\n{\"test\": 123}\n```")
        self.assertEqual(parsed.get("test"), 123)

        # Direct read_file
        res = read_file("run_tests.py", limit=3)
        self.assertEqual(res.get("status"), "success")

    def test_pillar_1b_compiler_self_repair_evaluation(self):
        """Pillar 1B: Verifies compiler self-repair detects syntax regressions and formats guidance."""
        from providers.turn_pipeline import TurnPhasePipeline

        results_by_index = {
            0: {"status": "ok", "message": "File written cleanly"},
            1: {"status": "error", "lint_warning": "IndentationError: unexpected indent", "file_path": "test.py"}
        }
        parsed_calls = [
            {"name": "write_local_file", "args": {"file_path": "clean.py"}},
            {"name": "write_local_file", "args": {"file_path": "test.py"}},
        ]
        has_error, warnings = TurnPhasePipeline.evaluate_compiler_self_repair(results_by_index, parsed_calls)
        self.assertTrue(has_error)
        self.assertEqual(len(warnings), 1)
        self.assertIn("COMPILER SELF-REPAIR GUARD", warnings[0])
        self.assertIn("IndentationError", warnings[0])

    def test_pillar_2b_ttsr_scrub_and_hard_exception(self):
        """Pillar 2B: Verifies TTSR hard-abort exception and in-place scrubbing."""
        from core.stream_rules import TimeTravelingStreamRulesEngine, StreamRuleViolation

        engine = TimeTravelingStreamRulesEngine()
        engine.feed("Halo, sekarang saya ")
        violation = engine.feed("*(sedang menjalankan skrip build.py)*")
        self.assertIsNotNone(violation)
        assert violation is not None

        # Verify stream engine scrubbed the violation from accumulated buffer
        self.assertNotIn("sedang menjalankan", engine.accumulated)

        # Subsequent clean token feeds should not re-trigger the violation
        clean_v = engine.feed(" dan melanjutkan tugas secara normal.")
        self.assertIsNone(clean_v)

    def test_pillar_5_differential_lint_delta_filtering(self):
        """Pillar 5: Verifies Differential Lint Delta filters pre-existing errors and reports new ones."""
        from tools.inproc_linter import lint_code_syntax

        # Case A: Legacy file with existing syntax error, edit doesn't change it
        broken_code = "def broken(:\n    pass\n"
        res_same = lint_code_syntax("broken.py", broken_code, pre_content=broken_code)
        self.assertIsNone(res_same)  # Filtered out because it was pre-existing!

        # Case B: Clean file edited to introduce a syntax error
        clean_code = "def clean():\n    pass\n"
        res_new = lint_code_syntax("clean.py", broken_code, pre_content=clean_code)
        self.assertIsNotNone(res_new)
        assert res_new is not None
        self.assertFalse(res_new.get("valid"))
        self.assertEqual(res_new.get("error_type"), "SyntaxError")

    def test_pillar_6_persistent_interactive_kernel(self):
        """Pillar 6: Verifies stateful execution kernel preserves variables across calls."""
        import asyncio
        from tools.code_execution_tools import _tool_execute_code

        async def _run_steps():
            # Step 1: Set persistent variable
            res1 = await _tool_execute_code(code="session_counter = 100", language="python", reset=True)
            self.assertEqual(res1.get("status"), "success")

            # Step 2: Read and increment variable in subsequent call without re-declaring
            res2 = await _tool_execute_code(code="session_counter += 42\nprint('COUNTER:', session_counter)", language="python", reset=False)
            self.assertEqual(res2.get("status"), "success")
            self.assertIn("COUNTER: 142", res2.get("stdout", ""))

            # Step 3: Reset clears the kernel
            res3 = await _tool_execute_code(code="try:\n    print(session_counter)\nexcept NameError:\n    print('CLEARED')", language="python", reset=True)
            self.assertEqual(res3.get("status"), "success")
            self.assertIn("CLEARED", res3.get("stdout", ""))

        asyncio.run(_run_steps())

    def test_pillar_7_progressive_tool_disclosure(self):
        """Pillar 7: Verifies dynamic tool search and description."""
        import asyncio
        from tools.system_tools import _tool_search, _tool_describe

        async def _test_tools():
            # Search for browser tools
            search_res = await _tool_search(query="browser")
            self.assertEqual(search_res.get("status"), "success")
            self.assertGreater(search_res.get("count", 0), 0)
            tool_names = [t["name"] for t in search_res["tools"]]
            self.assertTrue(any("browser" in n for n in tool_names))

            # Describe the discovered tools
            desc_res = await _tool_describe(names=["browser_navigate"])
            self.assertEqual(desc_res.get("status"), "success")
            self.assertEqual(len(desc_res["schemas"]), 1)
            self.assertEqual(desc_res["schemas"][0]["name"], "browser_navigate")
            self.assertIn("parameters", desc_res["schemas"][0])

        asyncio.run(_test_tools())

    def test_pillar_8_session_rewind_undo(self):
        """Pillar 8: Verifies Hermes Parity session rewind (/undo) soft-deleting conversation turns."""
        from memory import memory_engine

        # Create temporary session
        sess = memory_engine.create_session(title="Test Rewind Session")
        sid = sess["id"]
        try:
            # Log 2 turns
            memory_engine.log_conversation(session_id=sid, user_text="First User Turn", ai_text="First AI Reply")
            memory_engine.log_conversation(session_id=sid, user_text="Second User Turn", ai_text="Second AI Reply")

            msgs_before = memory_engine.get_session_messages(sid)
            self.assertEqual(len(msgs_before), 2)  # 2 conversation turn rows

            # Rewind 1 turn
            res = memory_engine.rewind_turns(sid, n=1)
            self.assertIsNotNone(res)
            assert res is not None
            self.assertEqual(res.get("rewound_count"), 1)
            self.assertEqual(res.get("last_user_text"), "Second User Turn")

            msgs_after = memory_engine.get_session_messages(sid)
            self.assertEqual(len(msgs_after), 1)  # only First Turn remains
            self.assertEqual(msgs_after[0]["user_text"], "First User Turn")
        finally:
            memory_engine.delete_session(sid)


if __name__ == "__main__":
    unittest.main()
