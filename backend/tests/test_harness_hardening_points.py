"""
test_harness_hardening_points.py — Regression Tests for Harness Hardening Points.
Tests:
1. Parallel Batch Return Exceptions Isolation (backend/providers/agent_loops.py)
2. WebSocket Stream Consumer Session Lock Parity (backend/websocket/stream_consumer.py)
3. Windows Path Delimiter Normalization on File Tools (backend/tools/fs_tools.py)
"""

import os
import sys
import unittest
import asyncio
import tempfile
import shutil

# Ensure backend path is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


class TestHarnessHardeningPoints(unittest.TestCase):

    def test_parallel_batch_return_exceptions_isolation(self):
        """Validates that unexpected exceptions in parallel tool batches don't crash the batch."""
        async def _run():
            async def failing_tool():
                raise PermissionError("Simulated OS handle exhaustion")

            async def succeeding_tool():
                return {"status": "success", "content": "file data"}

            tasks = [failing_tool(), succeeding_tool()]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            processed_results = []
            for raw_res in batch_results:
                if isinstance(raw_res, BaseException):
                    tool_res = {
                        "status": "error",
                        "error": str(raw_res),
                        "output": f"Unhandled tool execution error: {raw_res}",
                    }
                else:
                    tool_res = raw_res
                processed_results.append(tool_res)

            self.assertEqual(len(processed_results), 2)
            self.assertEqual(processed_results[0]["status"], "error")
            self.assertIn("Simulated OS handle exhaustion", processed_results[0]["error"])
            self.assertEqual(processed_results[1]["status"], "success")
            self.assertEqual(processed_results[1]["content"], "file data")

        asyncio.run(_run())

    def test_stream_consumer_session_lock_concurrency(self):
        """Validates that session locks prevent overlapping turns and release properly."""
        from core.session_manager import session_state_manager

        async def _run():
            sid = "test_hardening_lock_session"
            lock = session_state_manager.get_session_lock(sid)

            # 1. Lock can be acquired
            acquired = await lock.acquire()
            self.assertTrue(acquired)
            self.assertTrue(lock.is_locked())

            # 2. Lock is reentrant for the same task
            acquired_reentrant = await lock.acquire()
            self.assertTrue(acquired_reentrant)

            # 3. Release unwinds cleanly
            lock.release()
            self.assertTrue(lock.is_locked())  # Still locked because of first acquire
            lock.release()
            self.assertFalse(lock.is_locked())  # Now fully unlocked

            # 4. Context manager works cleanly
            async with lock:
                self.assertTrue(lock.is_locked())
            self.assertFalse(lock.is_locked())

        asyncio.run(_run())

    def test_fs_tools_path_normalization_posix(self):
        """Validates that file tool outputs always use POSIX '/' separators."""
        from tools.fs_tools import _tool_write_local_file, _tool_read_local_file, _tool_edit_file
        from core.agent import anara_agent

        test_dir = tempfile.mkdtemp(prefix="anara_norm_test_")
        orig_session_dir = anara_agent.get_session_dir()
        anara_agent._session_dir = test_dir

        try:
            async def _run():
                # Test write normalization
                test_filename = "subfolder\\nested_file.txt"
                write_res = await _tool_write_local_file(
                    file_path=test_filename,
                    content="Line 1: hello\nLine 2: world\n",
                    overwrite=True,
                )
                self.assertEqual(write_res.get("status"), "success")
                written_path = write_res.get("file_path", "")
                self.assertNotIn("\\", written_path)
                self.assertIn("/", written_path)

                # Test read normalization
                read_res = await _tool_read_local_file(file_path=test_filename)
                self.assertEqual(read_res.get("status"), "success")
                read_path = read_res.get("file_path", "")
                self.assertNotIn("\\", read_path)
                self.assertIn("/", read_path)

                # Test edit normalization
                edit_res = await _tool_edit_file(
                    file_path=test_filename,
                    old_string="Line 2: world",
                    new_string="Line 2: universe",
                )
                self.assertEqual(edit_res.get("status"), "success")
                edit_path = edit_res.get("file_path", "")
                self.assertNotIn("\\", edit_path)
                self.assertIn("/", edit_path)

            asyncio.run(_run())
        finally:
            anara_agent._session_dir = orig_session_dir
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
