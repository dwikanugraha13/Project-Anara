"""
Unit tests for the 4 Perfectionist Parity Hardening Points:
1. In-Transcript Tool Output Secret Redaction (logger.py & dispatch.py)
2. Pre-Flight File Grounding & Reference Expansion (context_references.py & runner.py)
3. Real-Time Auto Session Title Upgrade Hook (title_generator.py & useWebSocket.ts)
4. Provider-Level Prompt Caching Breakpoints (prompt_caching.py & profile_implementations.py)
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure backend path is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.logger import redact_sensitive_text, redact_tool_data
from core.context_references import (
    ContextReference,
    parse_context_references,
    expand_context_references,
)
from core.prompt_caching import (
    apply_rolling_prompt_cache,
    strip_prompt_cache_markers,
    count_cache_markers_in_payload,
)


class TestPerfectionistParity(unittest.TestCase):

    def test_secret_redaction_tool_data(self):
        """Point 1: In-Transcript Tool Output Secret Redaction recursively scrubs tokens/secrets."""
        raw_output = {
            "status": "success",
            "command": "cat .env",
            "lines": [
                "ANTHROPIC_API_KEY=sk-ant-api03-abcdef12345678901234567890-xyz",
                "GITHUB_TOKEN=ghp_0123456789abcdefghijklmnopqrstuvwxyz",
                "DATABASE_URL=postgres://anara_user:super_secret_db_pass@localhost:5432/anara_db",
                "OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890",
            ],
            "metadata": {
                "token": "ghp_0123456789abcdefghijklmnopqrstuvwxyz",
                "safe_field": 42,
            }
        }

        redacted = redact_tool_data(raw_output)

        # Check raw output was not mutated
        self.assertIn("super_secret_db_pass", raw_output["lines"][2])

        # Check secrets are redacted in output
        redacted_lines = "\n".join(redacted["lines"])
        self.assertNotIn("super_secret_db_pass", redacted_lines)
        self.assertNotIn("sk-ant-api03-abcdef12345678901234567890-xyz", redacted_lines)
        self.assertNotIn("ghp_0123456789abcdefghijklmnopqrstuvwxyz", redacted_lines)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz1234567890", redacted_lines)

        self.assertIn("[REDACTED]", redacted_lines)
        self.assertNotIn("ghp_0123456789abcdefghijklmnopqrstuvwxyz", redacted["metadata"]["token"])
        self.assertEqual(redacted["metadata"]["safe_field"], 42)

    def test_context_references_parsing_and_expansion(self):
        """Point 2: Pre-Flight File Grounding parses @file, @folder, @diff and expands them inline."""
        prompt = "Please inspect @file:test_sample.py:2-3 and check @diff and @folder:test_dir"

        refs = parse_context_references(prompt)
        self.assertEqual(len(refs), 3)

        kinds = {r.kind for r in refs}
        self.assertEqual(kinds, {"file", "diff", "folder"})

        file_ref = next(r for r in refs if r.kind == "file")
        self.assertEqual(file_ref.target, "test_sample.py")
        self.assertEqual(file_ref.line_start, 2)
        self.assertEqual(file_ref.line_end, 3)

        with tempfile.TemporaryDirectory() as tmpdir:
            sample_file = Path(tmpdir) / "test_sample.py"
            sample_file.write_text("line 1\nline 2 target\nline 3 target\nline 4\n", encoding="utf-8")

            dir_path = Path(tmpdir) / "test_dir"
            dir_path.mkdir()
            (dir_path / "hello.txt").write_text("hello", encoding="utf-8")

            expanded_prompt, metadata = expand_context_references(prompt, cwd=tmpdir)

            self.assertIn("[PRE-FLIGHT CONTEXT GROUNDING]", expanded_prompt)
            self.assertIn("line 2 target", expanded_prompt)
            self.assertIn("line 3 target", expanded_prompt)
            self.assertNotIn("line 1\n", expanded_prompt)
            self.assertIn("Directory: test_dir", expanded_prompt)
            self.assertTrue(any(m["type"] == "file" for m in metadata))

    def test_session_title_broadcast(self):
        """Point 3: Real-Time Auto Session Title Upgrade Hook broadcasts event via WebSocket bus."""
        from core.title_generator import apply_instant_title

        with patch("shared_state.broadcast_agent_event") as mock_broadcast, \
             patch("memory.memory_engine.set_auto_title", return_value=True):

            title = apply_instant_title(12345, "Fix the authentication modal on safari mobile")
            self.assertIsNotNone(title)
            self.assertTrue(mock_broadcast.called)
            call_args = mock_broadcast.call_args[0][0]
            self.assertEqual(call_args["type"], "session_title_updated")
            self.assertEqual(call_args["sessionId"], 12345)
            self.assertEqual(call_args["title"], title)

    def test_rolling_prompt_caching(self):
        """Point 4: Provider-Level Prompt Caching Breakpoints distributes up to 4 breakpoints."""
        history = [
            {"role": "user", "content": "Hello Anara"},
            {"role": "assistant", "content": "Hello! How can I help you today?"},
            {"role": "user", "content": "Can you check the repository structure?"},
            {"role": "assistant", "content": "I will examine the directory layout."},
        ]

        decorated = apply_rolling_prompt_cache(history, max_message_markers=2)

        # 4 messages, only the last 2 should have cache_control
        self.assertNotIn("cache_control", str(decorated[0].get("content")))
        self.assertNotIn("cache_control", str(decorated[1].get("content")))

        # Check last 2 messages are decorated
        last_user = decorated[2]["content"]
        last_asst = decorated[3]["content"]

        self.assertIsInstance(last_user, list)
        self.assertEqual(last_user[0]["cache_control"], {"type": "ephemeral"})

        self.assertIsInstance(last_asst, list)
        self.assertEqual(last_asst[0]["cache_control"], {"type": "ephemeral"})

        # Construct full simulated Anthropic payload
        payload = {
            "system": [{"type": "text", "text": "System prompt", "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": "read_file", "cache_control": {"type": "ephemeral"}}],
            "messages": decorated,
        }

        total_markers = count_cache_markers_in_payload(payload)
        self.assertEqual(total_markers, 4, "Total cache_control markers across system, tools, and messages must equal 4")

        # Test stripping markers reverses to original text strings
        stripped = strip_prompt_cache_markers(decorated)
        self.assertEqual(stripped[2]["content"], "Can you check the repository structure?")
        self.assertEqual(stripped[3]["content"], "I will examine the directory layout.")


if __name__ == "__main__":
    unittest.main()
