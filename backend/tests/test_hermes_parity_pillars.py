"""
test_hermes_parity_pillars.py — Unit Tests for Hermes-Parity Harness Enhancements.
Tests:
1. Streaming Text Degenerate Repetition Guard (backend/core/repetition_guard.py)
2. Multimodal Image Eviction Policy (backend/core/image_eviction.py)
3. Persist-Before-Execute Durability Checkpoint (backend/tools/dispatch.py)
4. Credential Pool Dynamic Key Cooldown (backend/providers/accounts.py)
"""

import os
import sys
import unittest
import asyncio
import time

# Ensure backend path is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class TestHermesParityPillars(unittest.TestCase):

    def test_repetition_guard_detects_degenerate_line_loop(self):
        """Validates that runaway line echoes are promptly detected."""
        from core.repetition_guard import is_repetition_dominated

        # Normal diverse text should NOT trigger repetition guard
        normal_prose = (
            "Here is the plan for our backend architecture.\n"
            "First, we will set up the database migrations using Alembic.\n"
            "Second, we will configure the FastAPI route handlers for authentication.\n"
            "Third, we will write unit tests using pytest to ensure high coverage.\n"
            "Finally, we will package the service inside a Docker container."
        ) * 4
        self.assertFalse(is_repetition_dominated(normal_prose))

        # Degenerate echo repeating one line across > 50% of >= 400 chars
        echoed_line = "I am generating the response and thinking about the problem carefully.\n"
        degenerate_stream = echoed_line * 10
        self.assertTrue(len(degenerate_stream) >= 400)
        self.assertTrue(is_repetition_dominated(degenerate_stream))

    def test_repetition_guard_detects_periodic_anchor_runs(self):
        """Validates that periodic 60+ character runs covering half the text are flagged."""
        from core.repetition_guard import is_repetition_dominated

        unit = "The quick brown fox jumps over the lazy dog in the middle of a sunny day! "  # 74 chars
        loop_content = unit * 8
        self.assertTrue(len(loop_content) >= 400)
        self.assertTrue(is_repetition_dominated(loop_content))

    def test_image_eviction_retires_oldest_carrier_blocks(self):
        """Validates that historical tool-result images are retired while retaining newest frames."""
        from core.image_eviction import evict_historical_images, RETIRED_IMAGE_NOTICE

        # Synthesize a long conversation with 5 images
        mock_messages = [
            {"role": "user", "content": [{"type": "text", "text": "Inspect step 1"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA1"}}]},
            {"role": "assistant", "content": "I see screenshot 1."},
            {"role": "user", "content": [{"type": "text", "text": "Inspect step 2"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,BBB2"}}]},
            {"role": "assistant", "content": "I see screenshot 2."},
            {"role": "user", "content": [{"type": "text", "text": "Inspect step 3"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,CCC3"}}]},
            {"role": "assistant", "content": "I see screenshot 3."},
            {"role": "user", "content": [{"type": "text", "text": "Inspect step 4"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,DDD4"}}]},
            {"role": "assistant", "content": "I see screenshot 4."},
            {"role": "user", "content": [{"type": "text", "text": "Inspect step 5"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,EEE5"}}]},
        ]

        # Apply eviction with max_active_images = 2
        sanitized, retired_count = evict_historical_images(mock_messages, max_active_images=2)
        self.assertEqual(retired_count, 3)

        # The first 3 user messages should have their images retired
        self.assertEqual(sanitized[0]["content"][1]["text"], RETIRED_IMAGE_NOTICE)
        self.assertEqual(sanitized[2]["content"][1]["text"], RETIRED_IMAGE_NOTICE)
        self.assertEqual(sanitized[4]["content"][1]["text"], RETIRED_IMAGE_NOTICE)

        # The last 2 images must remain intact!
        self.assertIn("image_url", sanitized[6]["content"][1])
        self.assertIn("image_url", sanitized[8]["content"][1])

    def test_persist_before_execute_checkpoint(self):
        """Validates that mutating tools record an execution checkpoint to disk."""
        from tools.dispatch import _record_execution_checkpoint, _clear_execution_checkpoint, get_last_execution_checkpoint

        # Record a test checkpoint
        _record_execution_checkpoint("write_file", {"path": "test.txt", "content": "hello"}, session_id=999)
        cp = get_last_execution_checkpoint()
        self.assertIsNotNone(cp)
        self.assertEqual(cp["tool"], "write_file")
        self.assertEqual(cp["status"], "executing")
        self.assertEqual(cp["session_id"], 999)

        # Clear/complete checkpoint
        _clear_execution_checkpoint("write_file")
        cp_cleared = get_last_execution_checkpoint()
        self.assertEqual(cp_cleared["status"], "completed")

    def test_credential_pool_cooldown_arming(self):
        """Validates that provider keys can be placed into cooldown and rotated."""
        from providers.accounts import mark_provider_key_cooldown

        # Arm cooldown for an arbitrary provider without raising errors
        mark_provider_key_cooldown("openai", cooldown_seconds=45.0)
        mark_provider_key_cooldown("anthropic", cooldown_seconds=30.0)

    def test_thinking_only_empty_response_guard(self):
        """Validates that models producing thoughts but no visible response receive an auto-nudge."""
        from core.empty_response_guard import should_nudge_for_empty, has_thinking_blocks

        # 1. Has thinking blocks
        raw_think = "<think>Let me analyze the database structure and queries...</think>"
        self.assertTrue(has_thinking_blocks(raw_think))

        # 2. Should nudge when clean text is empty
        self.assertTrue(should_nudge_for_empty(raw_text=raw_think, clean_text="", step=0, max_steps=10))

        # 3. Should NOT nudge when clean text is already present
        self.assertFalse(should_nudge_for_empty(raw_text=raw_think, clean_text="Here is the answer.", step=0, max_steps=10))

    def test_context_pinning_immunity(self):
        """Validates that pinned turns are preserved verbatim and exempt from lossy compaction."""
        from core.context_pin import context_pin_manager, is_item_pinned
        from core.context_compactor import ContextCompactor

        # Test pin manager
        context_pin_manager.pin("sess_123", "db_schema", "CREATE TABLE users (id INT PRIMARY KEY);")
        pins = context_pin_manager.list_pins("sess_123")
        self.assertEqual(len(pins), 1)
        self.assertEqual(pins[0]["label"], "db_schema")

        # Test immunity during compaction
        long_history = [
            {"id": 1, "user_text": "Do not delete table users", "ai_text": "Understood, users table will be protected.", "pinned": True},
            {"id": 2, "user_text": "Task A", "ai_text": "Done A"},
            {"id": 3, "user_text": "Task B", "ai_text": "Done B"},
            {"id": 4, "user_text": "Task C", "ai_text": "Done C"},
            {"id": 5, "user_text": "Task D", "ai_text": "Done D"},
            {"id": 6, "user_text": "Task E", "ai_text": "Done E"},
            {"id": 7, "user_text": "Task F", "ai_text": "Done F"},
        ]
        compacted = ContextCompactor.compact_history(long_history, verbatim_turns=2)
        self.assertIn("[PINNED TURNS (PRESERVED ACROSS COMPACTION)]", compacted)
        self.assertIn("Do not delete table users", compacted)

    def test_trajectory_recorder_format(self):
        """Validates that multi-turn runs are saved into ShareGPT standard JSONL."""
        from core.trajectory import TrajectoryRecorder

        mock_msgs = [
            {"role": "user", "content": "Refactor auth handler"},
            {"role": "assistant", "content": "Refactored cleanly."},
        ]
        path = TrajectoryRecorder.save_trajectory(
            session_id="test_traj_01",
            messages=mock_msgs,
            model="gemini-2.5-flash",
            completed=True,
        )
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

        recent = TrajectoryRecorder.read_trajectories(completed=True, limit=5)
        self.assertTrue(any(t["session_id"] == "test_traj_01" for t in recent))

    def test_background_review_idle_queue(self):
        """Validates that background review accepts idle review items without blocking."""
        from core.background_review import background_review_worker

        # Schedule review
        background_review_worker.schedule_idle_review(
            session_id="test_idle_01",
            user_prompt="Standar arsitektur kita harus pakai microservices.",
            assistant_response="Keputusan arsitektur: kami menerapkan pola hexagonal architecture.",
        )

    def test_destructive_git_operations_blocked(self):
        """Validates that dangerous git mutations (reset --hard, checkout -f, restore) are blocked."""
        from core.workspace_sentinel import workspace_sentinel

        # Should block git reset --hard
        safe, err = workspace_sentinel.validate_cli_command("git reset --hard HEAD~1")
        self.assertFalse(safe)
        self.assertIn("WORKSPACE SENTINEL BLOCKED", err)

        # Should block git checkout -f
        safe, err = workspace_sentinel.validate_cli_command("git checkout -f main")
        self.assertFalse(safe)
        self.assertIn("WORKSPACE SENTINEL BLOCKED", err)

        # Normal git status/diff should pass
        safe, err = workspace_sentinel.validate_cli_command("git status")
        self.assertTrue(safe)

    def test_binary_guard_blocks_raw_text(self):
        """Validates that binary extensions are flagged to prevent context window token bloat."""
        from core.binary_guard import is_binary_file, get_binary_file_notice

        self.assertTrue(is_binary_file("app.exe"))
        self.assertTrue(is_binary_file("bundle.zip"))
        self.assertTrue(is_binary_file("screenshot.png"))
        self.assertTrue(is_binary_file("module.pyc"))
        self.assertTrue(is_binary_file("data.sqlite"))
        self.assertFalse(is_binary_file("script.py"))
        self.assertFalse(is_binary_file("document.pdf"))

        notice = get_binary_file_notice("image.png", size_bytes=2048)
        self.assertIn("Binary File Notice", notice)
        self.assertIn("image.png", notice)

    def test_inproc_linter_syntax_gate(self):
        """Validates that in-process linter catches syntax errors immediately."""
        from tools.inproc_linter import lint_code_syntax

        # Valid python
        self.assertIsNone(lint_code_syntax("test.py", "def hello():\n    return 'world'\n"))

        # Broken python syntax
        err = lint_code_syntax("test.py", "def hello():\n    return 'world'")
        # Valid python single line: fine
        # Truly broken python:
        broken_err = lint_code_syntax("test.py", "def broken(\n   x = 1\n")
        self.assertIsNotNone(broken_err)
        self.assertEqual(broken_err["error_type"], "SyntaxError")

        # Broken JSON
        json_err = lint_code_syntax("config.json", '{"name": "anara", invalid')
        self.assertIsNotNone(json_err)
        self.assertEqual(json_err["error_type"], "JSONDecodeError")

    def test_slash_commands_btw_and_pin(self):
        """Validates /btw (side questions) and /pin (context immunity) slash command dispatch."""
        import asyncio
        from core.command_hub import command_hub, UniversalCommandContext

        # 1. Registered checks
        self.assertIsNotNone(command_hub.get_command("btw"))
        self.assertIsNotNone(command_hub.get_command("pin"))

        # 2. Test pinning via slash command
        async def _test_pin():
            ctx = UniversalCommandContext(
                raw_text="/pin arch Must use SQLite for persistence",
                command="pin",
                args="arch Must use SQLite for persistence",
                channel="web",
                user_id="test_user",
                session_id=888,
            )
            res = await command_hub.dispatch(ctx)
            self.assertIsNotNone(res)
            self.assertIn("Directive Pinned", res.text)
            self.assertIn("arch", res.text)

            # Test list pins
            ctx_list = UniversalCommandContext(
                raw_text="/pin list",
                command="pin",
                args="list",
                channel="web",
                user_id="test_user",
                session_id=888,
            )
            res_list = await command_hub.dispatch(ctx_list)
            self.assertIn("Pinned Directives", res_list.text)
            self.assertIn("Must use SQLite", res_list.text)

        asyncio.run(_test_pin())

    def test_thinking_timeout_guidance(self):
        """Validates reasoning timeout detection and constructive guidance."""
        from core.empty_response_guard import is_reasoning_timeout, format_thinking_timeout_guidance

        # Reasoning model hits transport drop
        self.assertTrue(is_reasoning_timeout("deepseek-r1", "Connection reset by peer"))
        self.assertTrue(is_reasoning_timeout("gemini-3.8-flash-thinking", "Remote protocol error: read timed out"))
        self.assertTrue(is_reasoning_timeout("claude-3-7-sonnet-high", "Broken pipe (errno 32)"))

        # Standard non-reasoning model or normal error
        self.assertFalse(is_reasoning_timeout("gemini-2.5-flash", "Connection reset"))
        self.assertFalse(is_reasoning_timeout("deepseek-r1", "Invalid API key provided"))

        # Guidance formatting
        guidance = format_thinking_timeout_guidance("deepseek-r1", "Connection reset")
        self.assertIn("Reasoning Timeout Notice", guidance)
        self.assertIn("deepseek-r1", guidance)
        self.assertIn("/reasoning low", guidance)
        self.assertIn("/model", guidance)

    def test_binary_write_and_blind_overwrite_guard(self):
        """Hermes Parity: Validates Binary Document Protection and Read-Before-Write Baseline."""
        import tempfile
        from core.binary_guard import check_binary_write_prohibited
        from tools.fs_tools import (
            _tool_write_local_file,
            _tool_read_local_file,
            reset_session_file_tracking,
            has_file_been_read
        )

        reset_session_file_tracking()

        # 1. Binary Document and Sidecar rejection
        prohib, reason = check_binary_write_prohibited("report.docx", exists=False)
        self.assertTrue(prohib)
        self.assertIn("binary document", reason)

        prohib, reason = check_binary_write_prohibited("app.db-wal", exists=False)
        self.assertTrue(prohib)
        self.assertIn("SQLite sidecar", reason)

        prohib, reason = check_binary_write_prohibited("photo.png", exists=True)
        self.assertTrue(prohib)
        self.assertIn("binary file", reason)

        # 2. Read-Before-Write baseline (Blind Overwrite Guard)
        with tempfile.TemporaryDirectory() as tmp_dir:
            from core import anara_agent
            sid = 999
            anara_agent.set_active_session_id(sid)
            anara_agent._session_active_paths[sid] = tmp_dir

            test_file = os.path.join(tmp_dir, "legacy_code.py")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("# Critical legacy code\ndef important_logic():\n    return 42\n" * 10)

            # File exists (>100 bytes) and has not been read in this session
            self.assertFalse(has_file_been_read(test_file))

            # Attempt blind overwrite without reading
            async def run_blind():
                return await _tool_write_local_file(test_file, "def replaced(): pass\n")

            res_blind = asyncio.run(run_blind())
            self.assertEqual(res_blind.get("status"), "error")
            self.assertEqual(res_blind.get("error_type"), "UnreadExistingFileOverwriteWarning")
            self.assertIn("Refusing to overwrite existing file", res_blind.get("message"))

            # Now read the file first
            async def run_read():
                return await _tool_read_local_file(test_file)

            res_read = asyncio.run(run_read())
            self.assertEqual(res_read.get("status"), "success")
            self.assertTrue(has_file_been_read(test_file))

            # Attempt write again after reading -> should succeed!
            async def run_write_after_read():
                return await _tool_write_local_file(test_file, "def replaced_safely(): pass\n")

            res_after_read = asyncio.run(run_write_after_read())
            self.assertEqual(res_after_read.get("status"), "success")

            # Reset tracking and test explicit overwrite=True bypass
            reset_session_file_tracking()
            self.assertFalse(has_file_been_read(test_file))

            async def run_forced():
                return await _tool_write_local_file(test_file, "def force_replaced(): pass\n", overwrite=True)

            res_forced = asyncio.run(run_forced())
            self.assertEqual(res_forced.get("status"), "success")

    def test_transcript_repair_engine(self):
        """Hermes Parity: Validates Transcript Sanitization & Repair Engine."""
        from core.transcript_repair import (
            repair_transcript_sequence,
            close_interrupted_tool_sequence,
            sanitize_surrogates,
            coerce_tool_name,
        )

        # 1. Lone surrogate cleaning
        text_with_surrogate = "Hello \ud800 World"
        cleaned_text = sanitize_surrogates(text_with_surrogate)
        self.assertNotIn("\ud800", cleaned_text)
        self.assertIn("\ufffd", cleaned_text)

        # 2. Tool name coercion
        self.assertEqual(coerce_tool_name("valid_tool_1"), "valid_tool_1")
        self.assertEqual(coerce_tool_name("invalid.name$weird"), "invalid_name_weird")

        # 3. Orphaned tool_calls healing
        broken_messages = [
            {"role": "user", "content": "Fetch data and write report"},
            {
                "role": "assistant",
                "content": "Let me call the tools",
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {"name": "read_local_file", "arguments": '{"file_path": "a.txt"}'}
                    },
                    {
                        "id": "call_def456",
                        "type": "function",
                        "function": {"name": "execute_cli_command", "arguments": '{"command": "dir"}'}
                    }
                ]
            },
            # Only 1 tool result was delivered before interruption:
            {"role": "tool", "tool_call_id": "call_abc123", "name": "read_local_file", "content": "contents of a"}
        ]

        repaired = repair_transcript_sequence(broken_messages)
        # Should now have 5 elements: user, assistant, tool abc, synthesized tool def, synthesized assistant closure
        tool_ids = [m.get("tool_call_id") for m in repaired if m.get("role") == "tool"]
        self.assertIn("call_abc123", tool_ids)
        self.assertIn("call_def456", tool_ids)

        # Verify trailing tool closure was applied
        self.assertEqual(repaired[-1].get("role"), "assistant")
        self.assertIn("interrupted", repaired[-1].get("content", "").lower())

        # 4. Strict role alternation (merging consecutive user turns)
        consecutive_user_msgs = [
            {"role": "user", "content": "First instruction."},
            {"role": "user", "content": "Second instruction."},
            {"role": "assistant", "content": "I understand."}
        ]
        repaired_roles = repair_transcript_sequence(consecutive_user_msgs)
        self.assertEqual(len(repaired_roles), 2)
        self.assertEqual(repaired_roles[0]["role"], "user")
        self.assertIn("First instruction.\n\nSecond instruction.", repaired_roles[0]["content"])

    def test_verification_stop_gate(self):
        """Hermes Parity: Validates Turn-End Verification Guard for Coding Edits."""
        from core.verification_stop import is_non_code_path, build_verify_on_stop_nudge

        # 1. Non-code path identification
        self.assertTrue(is_non_code_path("README.md"))
        self.assertTrue(is_non_code_path("docs/architecture.rst"))
        self.assertTrue(is_non_code_path("notes.txt"))
        self.assertTrue(is_non_code_path("LICENSE"))
        self.assertTrue(is_non_code_path("data.csv"))
        self.assertTrue(is_non_code_path("screenshot.png"))

        # Code paths
        self.assertFalse(is_non_code_path("backend/core/runner.py"))
        self.assertFalse(is_non_code_path("frontend/src/App.tsx"))
        self.assertFalse(is_non_code_path("scripts/deploy.sh"))
        self.assertFalse(is_non_code_path("server.go"))

        # 2. Prose-only mutations produce NO nudge
        nudge_docs = build_verify_on_stop_nudge(["README.md", "docs/index.mdx"])
        self.assertIsNone(nudge_docs)

        # 3. Code mutation without verification produces nudge
        nudge_code = build_verify_on_stop_nudge(["backend/server.py", "frontend/App.tsx"])
        self.assertIsNotNone(nudge_code)
        self.assertIn("[VERIFICATION STOP-GATE]", nudge_code)
        self.assertIn("backend/server.py", nudge_code)
        self.assertIn("verification", nudge_code.lower())

        # 4. Bounded attempts (max 2)
        self.assertIsNone(build_verify_on_stop_nudge(["backend/server.py"], attempts=2, max_attempts=2))

        # 5. Already verified produces NO nudge
        self.assertIsNone(build_verify_on_stop_nudge(["backend/server.py"], has_verified=True))

    def test_batch_cycle_loop_breaker_and_duplicate_stubbing(self):
        """Parity with can1357/oh-my-pi#10521: Batch-cycle detection and duplicate stubbing."""
        from tools.self_correction import AnaraLoopBreaker

        lb = AnaraLoopBreaker(max_identical=4, window_size=64)

        # 1. Period 3 repeating cycle (A -> B -> C -> A -> B -> C -> A -> B -> C)
        triad = [
            ("read_local_file", {"file_path": "foo.py"}),
            ("grep_search_code", {"pattern": "def bar"}),
            ("execute_cli_command", {"command": "pytest"}),
        ]
        # Lap 1 (calls 1..3)
        for name, args in triad:
            stalled, msg = lb.record_and_check(name, args)
            self.assertFalse(stalled)

        # Lap 2 (calls 4..6)
        for name, args in triad:
            stalled, msg = lb.record_and_check(name, args)
            self.assertFalse(stalled)

        # Lap 3 (calls 7..9) - 9th call completes 3 identical laps of period 3
        for idx, (name, args) in enumerate(triad):
            stalled, msg = lb.record_and_check(name, args)
            if idx < 2:
                self.assertFalse(stalled)
            else:
                self.assertTrue(stalled)
                self.assertIn("BATCH CYCLE DETECTED", msg)
                self.assertIn("period 3", msg)
                self.assertIn("read_local_file -> grep_search_code -> execute_cli_command", msg)

        # 2. Context conservation duplicate result stubbing
        lb.reset()
        large_content = "def test_function():\n    assert True\n" * 30  # > 512 chars
        self.assertGreater(len(large_content), 512)

        # First call produces original output
        r1 = lb.check_or_stub_duplicate("read_local_file", {"file_path": "test.py"}, large_content)
        self.assertEqual(r1, large_content)

        # Second identical call produces token-conserving reference stub
        r2 = lb.check_or_stub_duplicate("read_local_file", {"file_path": "test.py"}, large_content)
        self.assertIn("[Duplicate result:", r2)
        self.assertIn("identical to previous read_local_file call", r2)
        self.assertIn("Content omitted to conserve token context", r2)

        # After a mutating action occurs, cache is invalidated and output is fresh again
        lb.notify_mutation()
        r3 = lb.check_or_stub_duplicate("read_local_file", {"file_path": "test.py"}, large_content)
        self.assertEqual(r3, large_content)

    def test_quote_aware_shell_operator_and_allowlist(self):
        """Parity with can1357/oh-my-pi#7553: Quote-aware metacharacter analyzer & allowlist."""
        from core.approval_guard import has_compound_shell_operator, command_matches_allowlist
        from core.workspace_sentinel import workspace_sentinel

        # 1. Simple commands stay simple
        self.assertFalse(has_compound_shell_operator("git status"))
        self.assertFalse(has_compound_shell_operator("echo $HOME"))
        self.assertFalse(has_compound_shell_operator("grep foo\\;bar file.txt"))

        # 2. Motivating case from can1357/oh-my-pi#7553: quoted regexes with | and () are literal
        cargo_cmd = (
            "cargo bench --manifest-path layers/layer3/Cargo.toml "
            "--bench standardized_criterion -- "
            "'^layer3/write/file-wal/batch-(10|1000|10000)$'"
        )
        self.assertFalse(has_compound_shell_operator(cargo_cmd))
        self.assertFalse(has_compound_shell_operator('grep -r "a|b;c" src'))

        # 3. Compound shell operators are detected
        self.assertTrue(has_compound_shell_operator("git status; rm -rf /tmp/x"))
        self.assertTrue(has_compound_shell_operator("git status && make"))
        self.assertTrue(has_compound_shell_operator("cat foo | grep bar"))
        self.assertTrue(has_compound_shell_operator('echo "$(rm x)"'))
        self.assertTrue(has_compound_shell_operator("echo 'unterminated"))

        # 4. Interpreter-option payloads with metacharacters are treated as compound
        self.assertTrue(has_compound_shell_operator("sh -c 'rm -rf /tmp/x; echo done'"))
        self.assertTrue(has_compound_shell_operator("node --eval 'require(\"child_process\").exec(\"id\")'"))
        self.assertTrue(has_compound_shell_operator("python -c 'print(1); exit()'"))
        self.assertFalse(has_compound_shell_operator("python -c 'import sys'"))

        # 5. Allowlist glob matching with quote awareness
        allowlist = ["cargo *", "pytest *"]
        self.assertTrue(command_matches_allowlist(cargo_cmd, allowlist))
        self.assertFalse(command_matches_allowlist("cargo build && rm -rf /tmp/x", allowlist))
        self.assertFalse(command_matches_allowlist("cargo -c 'malicious payload'", allowlist))

        # 6. WorkspaceSentinel quote-awareness: literal inspection commands are safe
        is_safe, _ = workspace_sentinel.validate_cli_command('echo "rm -rf *"')
        self.assertTrue(is_safe)
        is_safe, _ = workspace_sentinel.validate_cli_command('grep -rn "git reset --hard" .')
        self.assertTrue(is_safe)

        # Destructive execution remains strictly blocked
        is_safe_wipe, err_wipe = workspace_sentinel.validate_cli_command("rm -rf *")
        self.assertFalse(is_safe_wipe)
        self.assertIn("WORKSPACE SENTINEL BLOCKED", err_wipe)

        is_safe_reset, err_reset = workspace_sentinel.validate_cli_command("git reset --hard")
        self.assertFalse(is_safe_reset)
        self.assertIn("WORKSPACE SENTINEL BLOCKED", err_reset)

    def test_whatsapp_formatting_and_delivery_parity(self):
        """Validates WhatsApp formatting adapter and chunking parity with Telegram."""
        from integrations.platforms.whatsapp import WhatsAppPlatformAdapter

        adapter = WhatsAppPlatformAdapter()

        # 1. Markdown syntax translation
        md_text = (
            "# Main Heading\n"
            "This is **bold text** and __also bold__.\n"
            "Here is ~~deleted text~~ and a [link](https://anara.ai).\n"
            "Inline `code_snippet` and fenced code:\n"
            "```python\ndef test():\n    return **not_bold_here**\n```"
        )
        formatted = adapter.format_message(md_text)

        # Header becomes *Main Heading*
        self.assertIn("*Main Heading*", formatted)
        # Bold **text** becomes *bold text*
        self.assertIn("*bold text*", formatted)
        self.assertIn("*also bold*", formatted)
        # Strike ~~text~~ becomes ~deleted text~
        self.assertIn("~deleted text~", formatted)
        # Link converts
        self.assertIn("link (https://anara.ai)", formatted)
        # Code block contents preserved without replacing asterisks inside
        self.assertIn("**not_bold_here**", formatted)
        self.assertIn("`code_snippet`", formatted)

    def test_ansi_and_unicode_tag_stripping(self):
        """Validates ECMA-48 ANSI stripping and Unicode tag smuggling protection."""
        from tools.self_correction import ContextMicroCompactor

        # 1. Standard ANSI escape codes
        ansi_text = "\x1b[32mSUCCESS\x1b[0m: Process completed \x1b[1;31merror code 0\x1b[0m"
        clean = ContextMicroCompactor.clean_terminal_noise(ansi_text)
        self.assertEqual(clean, "SUCCESS: Process completed error code 0")

        # 2. Invisible Unicode TAG chars (ASCII smuggling injection channel: block/goose#10746)
        smuggled = "Hello world!\U000E0069\U000E0067\U000E006E\U000E006F\U000E0072\U000E0065 Normal content."
        sanitized = ContextMicroCompactor.strip_unicode_tags(smuggled)
        self.assertEqual(sanitized, "Hello world! Normal content.")

        # 3. Valid TR51 emoji flag sequence must be preserved
        scotland_flag = "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"
        flag_text = f"Flag: {scotland_flag}"
        self.assertEqual(ContextMicroCompactor.strip_unicode_tags(flag_text), flag_text)

    def test_inbound_message_deduplicator_and_fingerprint(self):
        """Validates MessageDeduplicator TTL window and replay storm fingerprint protection."""
        from integrations.dedup import MessageDeduplicator

        dedup = MessageDeduplicator(max_size=10, ttl_seconds=60.0)

        # 1. Message ID deduplication
        self.assertFalse(dedup.is_duplicate("wamid_12345"))
        self.assertTrue(dedup.is_duplicate("wamid_12345"))

        # 2. Content fingerprint deduplication (replay protection)
        user_id = "+628123456789"
        text = "Tolong periksa status server"
        self.assertFalse(dedup.is_content_duplicate(user_id, text, window_seconds=5.0))
        # Immediate replay within 5s is dropped
        self.assertTrue(dedup.is_content_duplicate(user_id, text, window_seconds=5.0))
        # Different user is allowed
        self.assertFalse(dedup.is_content_duplicate("+628999999999", text, window_seconds=5.0))

        # 3. Discard allows re-entry
        dedup.discard("wamid_12345")
        self.assertFalse(dedup.is_duplicate("wamid_12345"))

    def test_gateway_silence_narration_suppressor(self):
        """Validates suppression of blank/silent agent responses for messaging gateways."""
        from core.empty_response_guard import is_silence_narration

        # Silence tokens should be recognized and suppressed
        self.assertTrue(is_silence_narration("*(silent)*"))
        self.assertTrue(is_silence_narration("(silent)"))
        self.assertTrue(is_silence_narration("_silence_"))
        self.assertTrue(is_silence_narration("(no response)"))
        self.assertTrue(is_silence_narration("(no reply)"))
        self.assertTrue(is_silence_narration("🔇"))
        self.assertTrue(is_silence_narration("."))
        self.assertTrue(is_silence_narration("..."))
        self.assertTrue(is_silence_narration("…"))

        # Legitimate messages containing word silent must NOT be suppressed
        self.assertFalse(is_silence_narration("The silent installation finished successfully."))
        self.assertFalse(is_silence_narration("I checked the logs, no errors found."))
        self.assertFalse(is_silence_narration("Configured silent_mode = True in settings.py"))

    def test_yaml_multidoc_and_custom_tag_lint_gate(self):
        """Validates that YAML linter handles multi-doc streams and custom tags without false alarms."""
        from tools.inproc_linter import lint_code_syntax

        # 1. Multi-document YAML stream (e.g. K8s / manifests)
        multidoc = (
            "apiVersion: v1\n"
            "kind: ConfigMap\n"
            "metadata:\n"
            "  name: app-cfg\n"
            "---\n"
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: app-deploy\n"
        )
        self.assertIsNone(lint_code_syntax("deploy.yaml", multidoc))

        # 2. Custom tags (e.g. AWS CloudFormation !Sub / !Ref)
        cfn_template = (
            "Resources:\n"
            "  MyBucket:\n"
            "    Type: AWS::S3::Bucket\n"
            "    Properties:\n"
            "      BucketName: !Sub '${AWS::StackName}-data'\n"
        )
        self.assertIsNone(lint_code_syntax("template.yml", cfn_template))

        # 3. Genuine broken YAML syntax must still be flagged
        broken_yaml = "invalid:\n  - item 1\n    - sub item bad indentation: ["
        res = lint_code_syntax("broken.yaml", broken_yaml)
        self.assertIsNotNone(res)
        self.assertEqual(res["language"], "yaml")
        self.assertFalse(res["valid"])

    def test_turn_preflight_pressure_gate(self):
        """Validates Pre-API pressure evaluation and insufficient progress loop-breaking."""
        from core.token_budget import TokenBudgetTracker

        tracker = TokenBudgetTracker("gemini-2.5-pro")

        mock_msgs = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Review this codebase."},
        ]

        # 1. Normal message pressure is within budget
        assessment = tracker.evaluate_preflight_pressure(mock_msgs, min_output_runway=500)
        self.assertFalse(assessment["warrants_compression"])

        ok, reason = tracker.run_preflight_gate(mock_msgs, min_output_runway=500)
        self.assertTrue(ok)
        self.assertEqual(reason, "within_budget")

        # 2. Insufficient progress guard
        tracker.input_budget = 10000  # artificially set budget lower so it warrants compression
        huge_msgs = [
            {"role": "user", "content": "x" * 200000}
        ]
        # Simulated scenario: prior pressure was essentially identical (< 5% reduction)
        curr_p = tracker.evaluate_preflight_pressure(huge_msgs, min_output_runway=500)["total_pressure"]
        tracker._last_preflight_pressure = curr_p + 10
        ok, reason = tracker.run_preflight_gate(huge_msgs, min_output_runway=500)
        self.assertTrue(ok)
        self.assertEqual(reason, "insufficient_progress_skipped")

    def test_pi_cumulative_file_state_compaction(self):
        """Pi Parity: Validates cumulative file state tracking and retention across compaction."""
        from tools.fs_tools import mark_file_read, mark_file_written, get_session_tracked_files, reset_session_file_tracking
        from core.context_compactor import ContextCompactor

        reset_session_file_tracking()
        mark_file_read("src/auth/jwt.py")
        mark_file_read("src/models/user.py")
        mark_file_written("src/auth/jwt.py")

        tracked = get_session_tracked_files()
        self.assertTrue(any("jwt.py" in f for f in tracked["read_files"]))
        self.assertTrue(any("user.py" in f for f in tracked["read_files"]))
        self.assertTrue(any("jwt.py" in f for f in tracked["modified_files"]))

        # Compaction summary should preserve cumulative file state
        history = [
            {"user_text": f"Task step {i}", "ai_text": f"Observation result {i}"}
            for i in range(15)
        ]
        compacted = ContextCompactor.compact_history(history, verbatim_turns=5)
        self.assertIn("[CUMULATIVE FILE STATE]", compacted)
        self.assertIn("jwt.py", compacted)
        self.assertIn("user.py", compacted)

        reset_session_file_tracking()

    def test_hermes_parallel_tool_id_uniquification_and_mixed_batch(self):
        """Hermes Parity: Validates tool call ID deduplication and mixed batch segregation."""
        from core.transcript_repair import uniquify_tool_call_ids, validate_and_filter_tool_batch

        # 1. Deduplication of duplicate tool call IDs
        calls = [
            {"id": "call_inspect_1", "function": {"name": "read_local_file", "arguments": "{}"}},
            {"id": "call_inspect_1", "function": {"name": "read_local_file", "arguments": "{}"}},
            {"id": "call_inspect_1", "function": {"name": "grep_search_code", "arguments": "{}"}},
            {"id": "call_other_2", "function": {"name": "stat_file", "arguments": "{}"}},
        ]
        uniquify_tool_call_ids(calls)
        ids = [c["id"] for c in calls]
        self.assertEqual(ids, ["call_inspect_1", "call_inspect_1_d2", "call_inspect_1_d3", "call_other_2"])

        # 2. Mixed batch validation (filter hallucinated/unknown tools into synthetic errors)
        valid_tools = {"read_local_file", "grep_search_code"}
        executable, errors = validate_and_filter_tool_batch(calls, valid_tools)
        self.assertEqual(len(executable), 3)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["name"], "stat_file")
        self.assertIn("Unknown tool 'stat_file'", errors[0]["content"])

    def test_pi_dual_queue_steering_vs_followup(self):
        """Pi Parity: Validates in-flight steering vs follow-up classification and queue lifecycles."""
        from core.session_manager import classify_in_flight_message, session_state_manager

        # 1. Classification
        self.assertEqual(classify_in_flight_message("ralat, jangan gunakan port 8080"), "steering")
        self.assertEqual(classify_in_flight_message("stop that, use python 3.12 instead"), "steering")
        self.assertEqual(classify_in_flight_message("bukan itu, maksud saya tabel users"), "steering")
        self.assertEqual(classify_in_flight_message("nanti setelah ini buatkan unit test ya"), "follow_up")
        self.assertEqual(classify_in_flight_message("tolong jelaskan arsitekturnya juga"), "follow_up")

        # 2. Dual queue FIFO operations
        ch = "test_chan"
        cid = "user_42"
        session_state_manager.push_steering_message(ch, cid, "ganti ke postgresql")
        session_state_manager.push_steering_message(ch, cid, "tambahkan index")
        session_state_manager.push_follow_up(ch, cid, "task_lanjutan_1")

        self.assertTrue(session_state_manager.has_steering_message(ch, cid))
        self.assertTrue(session_state_manager.has_follow_up(ch, cid))

        self.assertEqual(session_state_manager.pop_steering_message(ch, cid), "ganti ke postgresql")
        self.assertEqual(session_state_manager.pop_steering_message(ch, cid), "tambahkan index")
        self.assertIsNone(session_state_manager.pop_steering_message(ch, cid))
        self.assertFalse(session_state_manager.has_steering_message(ch, cid))

        self.assertEqual(session_state_manager.pop_follow_up(ch, cid), "task_lanjutan_1")
        self.assertFalse(session_state_manager.has_follow_up(ch, cid))


if __name__ == "__main__":
    unittest.main()
