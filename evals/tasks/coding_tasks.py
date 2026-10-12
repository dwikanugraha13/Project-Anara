"""
coding_tasks.py — Benchmark Tasks for Empirical Code Mutation & Precision Evaluation.
Defines real-world code editing challenges to compare Hashline vs String Replacement.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass
class EvalTask:
    task_id: str
    name: str
    description: str
    files: Dict[str, str]
    instruction: str
    verify_fn: Callable[[Dict[str, str]], bool]


def _verify_t01(files: Dict[str, str]) -> bool:
    app_py = files.get("app.py", "")
    return "timeout = 30" in app_py and "timeout = 10" in app_py and "def connect_db():" in app_py


def _verify_t02(files: Dict[str, str]) -> bool:
    calc_ts = files.get("calculator.ts", "")
    return "return a * b;" in calc_ts and "return a + b;" in calc_ts


def _verify_t03(files: Dict[str, str]) -> bool:
    server_py = files.get("server.py", "")
    return "def healthcheck():" in server_py and "status" in server_py and "ok" in server_py


def _verify_t04(files: Dict[str, str]) -> bool:
    routes_py = files.get("routes.py", "")
    return "@router.get('/v2/users')" in routes_py and "@router.get('/v1/users')" not in routes_py


def _verify_t05(files: Dict[str, str]) -> bool:
    repo_py = files.get("repository.py", "")
    return "def get_active_users(self):" in repo_py and "status == 'active'" in repo_py and len(repo_py.splitlines()) >= 260


def _verify_t06(files: Dict[str, str]) -> bool:
    config_py = files.get("config.py", "")
    from tools.inproc_linter import lint_code_syntax
    err = lint_code_syntax("config.py", config_py)
    return "MAX_RETRIES = 5" in config_py and err is None


EVAL_TASKS: List[EvalTask] = [
    EvalTask(
        task_id="T01_AMBIGUOUS_CONTEXT",
        name="Ambiguous String Disambiguation",
        description="File has multiple identical lines ('timeout = 10'). Must only update the database connection timeout to 30.",
        files={
            "app.py": """# Configuration
timeout = 10

def connect_cache():
    timeout = 10
    return f"cache_timeout_{timeout}"

def connect_db():
    timeout = 10
    return f"db_timeout_{timeout}"
"""
        },
        instruction="Update the database connection timeout in connect_db() to 30 without modifying cache or global timeouts.",
        verify_fn=_verify_t01,
    ),
    EvalTask(
        task_id="T02_INLINE_REFACTOR",
        name="TypeScript Function Multiply Addition",
        description="Add multiply function into calculator TypeScript file.",
        files={
            "calculator.ts": """export function add(a: number, b: number): number {
  return a + b;
}

export function subtract(a: number, b: number): number {
  return a - b;
}
"""
        },
        instruction="Add 'export function multiply(a: number, b: number): number { return a * b; }' right after add().",
        verify_fn=_verify_t02,
    ),
    EvalTask(
        task_id="T03_TAIL_ENDPOINT_INJECTION",
        name="Tail Endpoint Injection",
        description="Insert new healthcheck endpoint at the bottom of the server file.",
        files={
            "server.py": """import os
import sys

def start_server():
    print("Server online")
"""
        },
        instruction="Append def healthcheck(): return {'status': 'ok'} at the end of server.py.",
        verify_fn=_verify_t03,
    ),
    EvalTask(
        task_id="T04_API_VERSION_UPGRADE",
        name="API Route Version Bump",
        description="Replace /v1/users route with /v2/users.",
        files={
            "routes.py": """from fastapi import APIRouter

router = APIRouter()

@router.get('/v1/users')
def list_users():
    return []
"""
        },
        instruction="Upgrade route from /v1/users to /v2/users.",
        verify_fn=_verify_t04,
    ),
    EvalTask(
        task_id="T05_PAGINATED_NAV_EDIT",
        name="Paginated Large File Navigation & Targeted Edit",
        description="File has 270+ lines of repository methods. Update get_active_users to filter by active status without altering surrounding methods.",
        files={
            "repository.py": "\n".join([f"# Repository Header Line {i}" for i in range(1, 120)]) + """
class UserRepository:
    def __init__(self, db):
        self.db = db

    def get_active_users(self):
        # Target to update
        return self.db.query("SELECT * FROM users")

    def count_users(self):
        return 42
""" + "\n" + "\n".join([f"# Repository Tail Line {i}" for i in range(1, 140)])
        },
        instruction="In repository.py, update UserRepository.get_active_users to return self.db.query(\"SELECT * FROM users WHERE status == 'active'\").",
        verify_fn=_verify_t05,
    ),
    EvalTask(
        task_id="T06_COMPILER_SYNTAX_GUARD",
        name="Compiler Self-Repair & Syntax Guard",
        description="Update MAX_RETRIES to 5 in config.py while ensuring valid Python syntax.",
        files={
            "config.py": """# Application Configuration
TIMEOUT = 30
MAX_RETRIES = 3
DEBUG = False
"""
        },
        instruction="Update MAX_RETRIES to 5 in config.py.",
        verify_fn=_verify_t06,
    ),
]
