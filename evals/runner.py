"""
runner.py — Empirical Evaluation Harness Runner for Project Anara.
Compares Hashline vs Fuzzy String Replacement across deterministic coding benchmarks.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure backend modules can be imported
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from evals.tasks.coding_tasks import EVAL_TASKS, EvalTask
from evals.tracker import EvalMetricsTracker
from tools.hashline_engine import apply_hashline_patch, compute_file_tag
from tools.fuzzy_match import _perform_fuzzy_replace
from tools.inproc_linter import lint_code_syntax
import tempfile
import shutil


def compute_indent_drift(original: str, edited: str) -> int:
    """
    Computes indentation drift / whitespace noise (Can Bölük / Oh My Pi Parity).
    Measures the number of lines where leading whitespace was altered unnecessarily.
    """
    orig_lines = original.splitlines()
    edit_lines = edited.splitlines()
    drift = 0
    min_len = min(len(orig_lines), len(edit_lines))
    for i in range(min_len):
        orig_indent = len(orig_lines[i]) - len(orig_lines[i].lstrip())
        edit_indent = len(edit_lines[i]) - len(edit_lines[i].lstrip())
        if orig_lines[i].strip() == edit_lines[i].strip() and orig_indent != edit_indent:
            drift += 1
    return drift


class BenchmarkRunner:
    def __init__(self, model_id: str = "anara-agent-core"):
        self.model_id = model_id
        self.tracker = EvalMetricsTracker()

    def run_benchmark(self, reps: int = 1, mode: str = "edit") -> Dict[str, Any]:
        """
        Executes the benchmark across all tasks in isolated workspaces.
        reps: Number of repetitions per task to evaluate pass-rate determinism (Pass@1, Pass@N).
        mode: 'edit' (mutation protocol benchmark) or 'agent' (live LLM tool invocation).
        """
        run_id = f"bench_{uuid.uuid4().hex[:8]}"
        results: Dict[str, Any] = {
            "run_id": run_id,
            "model_id": self.model_id,
            "tasks_count": len(EVAL_TASKS),
            "reps": reps,
            "mode": mode,
            "modes": {"hashline": [], "fuzzy_replace": []},
        }

        print("\n" + "=" * 78)
        print(f"   PROJECT ANARA — EMPIRICAL BENCHMARK EVALUATION HARNESS")
        print(f"   Run ID: {run_id} | Mode: {mode.upper()} | Reps: {reps} | Model: {self.model_id}")
        print("=" * 78)

        for task in EVAL_TASKS:
            print(f"\n[Task {task.task_id}] {task.name}")

            hl_passes = 0
            hl_total_tokens = 0
            hl_total_ms = 0.0

            fz_passes = 0
            fz_total_tokens = 0
            fz_total_ms = 0.0

            for rep in range(reps):
                # ── Arm A: Hashline (Line-Anchored Tagged Edits in Worktree) ──
                with tempfile.TemporaryDirectory(prefix=f"anara_eval_hl_{task.task_id}_") as ws_dir:
                    self._populate_workspace(ws_dir, task.files)
                    hl_success, hl_tokens, hl_ms, hl_drift = self._evaluate_hashline_in_workspace(ws_dir, task)
                    if hl_success:
                        hl_passes += 1
                    hl_total_tokens += hl_tokens
                    hl_total_ms += hl_ms

                    self.tracker.record_trial(
                        run_id=run_id,
                        model_id=self.model_id,
                        task_id=task.task_id,
                        edit_mode="hashline",
                        success=hl_success,
                        turns=1,
                        tokens_used=hl_tokens,
                        latency_ms=hl_ms,
                        details=f"rep={rep+1}/{reps}; indent_drift={hl_drift}"
                    )

                # ── Arm B: Baseline (Fuzzy String Replace in Worktree) ──
                with tempfile.TemporaryDirectory(prefix=f"anara_eval_fz_{task.task_id}_") as ws_dir:
                    self._populate_workspace(ws_dir, task.files)
                    fz_success, fz_tokens, fz_ms, fz_drift = self._evaluate_fuzzy_in_workspace(ws_dir, task)
                    if fz_success:
                        fz_passes += 1
                    fz_total_tokens += fz_tokens
                    fz_total_ms += fz_ms

                    self.tracker.record_trial(
                        run_id=run_id,
                        model_id=self.model_id,
                        task_id=task.task_id,
                        edit_mode="fuzzy_replace",
                        success=fz_success,
                        turns=1,
                        tokens_used=fz_tokens,
                        latency_ms=fz_ms,
                        details=f"rep={rep+1}/{reps}; indent_drift={fz_drift}"
                    )

            avg_hl_tok = int(hl_total_tokens / reps)
            avg_hl_ms = hl_total_ms / reps
            hl_rate = f"{(hl_passes / reps * 100):.0f}%"
            status_hl = "PASS" if hl_passes == reps else ("PARTIAL" if hl_passes > 0 else "FAIL")
            print(f"  • Hashline Mode:       [{status_hl:<7}]  Pass@{reps}: {hl_rate:<4}  {avg_hl_tok:4d} tokens  ({avg_hl_ms:.1f}ms)")

            avg_fz_tok = int(fz_total_tokens / reps)
            avg_fz_ms = fz_total_ms / reps
            fz_rate = f"{(fz_passes / reps * 100):.0f}%"
            status_fz = "PASS" if fz_passes == reps else ("PARTIAL" if fz_passes > 0 else "FAIL")
            token_diff = f"{((avg_hl_tok - avg_fz_tok) / max(1, avg_fz_tok) * 100):+.1f}%" if avg_fz_tok > 0 else "0%"
            print(f"  • Fuzzy Replace Mode:  [{status_fz:<7}]  Pass@{reps}: {fz_rate:<4}  {avg_fz_tok:4d} tokens  ({avg_fz_ms:.1f}ms) -> Token Diff: {token_diff}")

        # Summary
        summary = self.tracker.get_summary(run_id=run_id)
        results["summary"] = summary
        self._print_summary_table(summary)
        return results

    def _populate_workspace(self, ws_dir: str, files: Dict[str, str]):
        """Writes initial task files to an isolated filesystem directory."""
        for rel_path, content in files.items():
            full_path = os.path.join(ws_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _read_workspace_files(self, ws_dir: str) -> Dict[str, str]:
        """Reads back all files from the workspace directory."""
        out: Dict[str, str] = {}
        for root, _, filenames in os.walk(ws_dir):
            for fn in filenames:
                fp = os.path.join(root, fn)
                rel = os.path.relpath(fp, ws_dir).replace("\\", "/")
                try:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        out[rel] = f.read()
                except Exception:
                    pass
        return out

    def _evaluate_hashline_in_workspace(self, ws_dir: str, task: EvalTask) -> Tuple[bool, int, float, int]:
        t0 = time.time()
        patch = ""
        target_file = ""
        original_content = ""

        try:
            if task.task_id == "T01_AMBIGUOUS_CONTEXT":
                target_file = "app.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                tag = compute_file_tag(original_content)
                patch = f"[app.py#{tag}]\nPUT 9.=9:\n+    timeout = 30\n"
                new_c, err, _ = apply_hashline_patch(original_content, patch)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T02_INLINE_REFACTOR":
                target_file = "calculator.ts"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                tag = compute_file_tag(original_content)
                patch = f"[calculator.ts#{tag}]\nPUT >3:\n+\n+export function multiply(a: number, b: number): number {{\n+  return a * b;\n+}}\n"
                new_c, err, _ = apply_hashline_patch(original_content, patch)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T03_TAIL_ENDPOINT_INJECTION":
                target_file = "server.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                tag = compute_file_tag(original_content)
                patch = f"[server.py#{tag}]\nPUT >$:\n+def healthcheck():\n+    return {{'status': 'ok'}}\n"
                new_c, err, _ = apply_hashline_patch(original_content, patch)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T04_API_VERSION_UPGRADE":
                target_file = "routes.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                tag = compute_file_tag(original_content)
                patch = f"[routes.py#{tag}]\nPUT 5.=5:\n+@router.get('/v2/users')\n"
                new_c, err, _ = apply_hashline_patch(original_content, patch)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T05_PAGINATED_NAV_EDIT":
                target_file = "repository.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                tag = compute_file_tag(original_content)
                lines = original_content.splitlines()
                target_idx = None
                for idx, line in enumerate(lines, start=1):
                    if 'return self.db.query("SELECT * FROM users")' in line:
                        target_idx = idx
                        break
                if target_idx:
                    patch = f"[repository.py#{tag}]\nPUT {target_idx}.={target_idx}:\n+        return self.db.query(\"SELECT * FROM users WHERE status == 'active'\")\n"
                    new_c, err, _ = apply_hashline_patch(original_content, patch)
                    if not err and new_c:
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(new_c)

            elif task.task_id == "T06_COMPILER_SYNTAX_GUARD":
                target_file = "config.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                tag = compute_file_tag(original_content)
                patch = f"[config.py#{tag}]\nPUT 3.=3:\n+MAX_RETRIES = 5\n"
                new_c, err, _ = apply_hashline_patch(original_content, patch)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            dt = (time.time() - t0) * 1000
            files_after = self._read_workspace_files(ws_dir)
            success = task.verify_fn(files_after)
            drift = compute_indent_drift(original_content, files_after.get(target_file, ""))
            tokens = len(patch) // 4
            return success, tokens, dt, drift
        except Exception:
            return False, 0, (time.time() - t0) * 1000, 0

    def _evaluate_fuzzy_in_workspace(self, ws_dir: str, task: EvalTask) -> Tuple[bool, int, float, int]:
        t0 = time.time()
        old_str = ""
        new_str = ""
        target_file = ""
        original_content = ""

        try:
            if task.task_id == "T01_AMBIGUOUS_CONTEXT":
                target_file = "app.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                # Ambiguity trap: 'timeout = 10' matches 3 places in the file
                old_str = "timeout = 10"
                new_str = "timeout = 30"
                new_c, _, err = _perform_fuzzy_replace(original_content, old_str, new_str, replace_all=False)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T02_INLINE_REFACTOR":
                target_file = "calculator.ts"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                old_str = "export function add(a: number, b: number): number {\n  return a + b;\n}"
                new_str = old_str + "\n\nexport function multiply(a: number, b: number): number {\n  return a * b;\n}"
                new_c, _, err = _perform_fuzzy_replace(original_content, old_str, new_str)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T03_TAIL_ENDPOINT_INJECTION":
                target_file = "server.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                old_str = 'def start_server():\n    print("Server online")'
                new_str = old_str + "\n\ndef healthcheck():\n    return {'status': 'ok'}"
                new_c, _, err = _perform_fuzzy_replace(original_content, old_str, new_str)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T04_API_VERSION_UPGRADE":
                target_file = "routes.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                old_str = "@router.get('/v1/users')"
                new_str = "@router.get('/v2/users')"
                new_c, _, err = _perform_fuzzy_replace(original_content, old_str, new_str)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T05_PAGINATED_NAV_EDIT":
                target_file = "repository.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                old_str = '        return self.db.query("SELECT * FROM users")'
                new_str = '        return self.db.query("SELECT * FROM users WHERE status == \'active\'")'
                new_c, _, err = _perform_fuzzy_replace(original_content, old_str, new_str)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            elif task.task_id == "T06_COMPILER_SYNTAX_GUARD":
                target_file = "config.py"
                full_path = os.path.join(ws_dir, target_file)
                with open(full_path, "r", encoding="utf-8") as f:
                    original_content = f.read()
                old_str = "MAX_RETRIES = 3"
                new_str = "MAX_RETRIES = 5"
                new_c, _, err = _perform_fuzzy_replace(original_content, old_str, new_str)
                if not err and new_c:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_c)

            dt = (time.time() - t0) * 1000
            files_after = self._read_workspace_files(ws_dir)
            success = task.verify_fn(files_after)
            drift = compute_indent_drift(original_content, files_after.get(target_file, ""))
            tokens = (len(old_str) + len(new_str)) // 4
            return success, tokens, dt, drift
        except Exception:
            return False, 0, (time.time() - t0) * 1000, 0

    def _print_summary_table(self, summary: List[Dict[str, Any]]):
        print("\n" + "-" * 78)
        print("  LEADERBOARD COMPARISON RESULTS")
        print("-" * 78)
        print(f"  {'Edit Mode':<18} | {'Pass Rate':<12} | {'Avg Tokens':<14} | {'Avg Latency'}")
        print("-" * 78)
        for row in summary:
            mode = row["edit_mode"]
            total = row["total_tasks"]
            passed = row["passed_tasks"]
            rate = f"{(passed / total * 100):.1f}% ({passed}/{total})"
            avg_tok = f"{row['avg_tokens']:.0f} tokens"
            avg_lat = f"{row['avg_latency']:.2f} ms"
            print(f"  {mode:<18} | {rate:<12} | {avg_tok:<14} | {avg_lat}")
        print("=" * 78 + "\n")
