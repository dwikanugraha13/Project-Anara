"""
run.py — CLI Entrypoint for Project Anara Empirical Benchmarks.
Usage:
    python evals/run.py
    python evals/run.py --model "ag/gemini-3.8-flash" --reps 3
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure backend and evals root are in sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "backend"
_EVALS_DIR = _REPO_ROOT / "evals"

for d in (_REPO_ROOT, _BACKEND_DIR, _EVALS_DIR):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

# Suppress OpenBLAS thread allocation warnings on Windows
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from evals.runner import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="Project Anara Empirical Coding Evaluation Harness")
    parser.add_argument("--model", type=str, default="ag/gemini-3.8-flash-high", help="Target model identifier")
    parser.add_argument("--reps", type=int, default=1, help="Repetitions per task")
    parser.add_argument("--mode", type=str, default="edit", choices=["edit", "agent"], help="Benchmark mode: 'edit' (mutation benchmark) or 'agent' (live LLM)")
    args = parser.parse_args()

    runner = BenchmarkRunner(model_id=args.model)
    runner.run_benchmark(reps=args.reps, mode=args.mode)


if __name__ == "__main__":
    main()
