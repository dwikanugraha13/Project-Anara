"""
verification_stop.py — Turn-End Verification Guard for Coding Edits (Hermes Parity).

Policy-only evidence gate: intercepts the agent turn when code has been modified
but no ground-truth verification tests or runtime checks have been observed.
Prevents models from prematurely reporting completion without testing their work.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Iterable, List, Optional

logger = logging.getLogger("anara.verification_stop")

_NON_CODE_EXTENSIONS = frozenset({
    ".md", ".markdown", ".mdx", ".rst", ".txt", ".text", ".adoc", ".asciidoc",
    ".log", ".csv", ".tsv", ".doc", ".docx", ".pdf", ".png", ".jpg", ".jpeg",
    ".svg", ".webp", ".gif", ".ico", ".lock",
})

_NON_CODE_FILENAMES = frozenset({
    "license", "licence", "notice", "authors", "contributors", "changelog",
    "codeowners", ".gitignore", ".gitattributes", ".env.example", ".editorconfig",
    "dockerignore",
})


def is_non_code_path(raw: str) -> bool:
    """True when a changed path is documentation, prose, or asset with no runtime behavior to test."""
    if not raw:
        return True
    try:
        p = Path(str(raw))
    except Exception:
        return False
    suffix = p.suffix.lower()
    if suffix in _NON_CODE_EXTENSIONS:
        return True
    if not suffix and p.name.lower() in _NON_CODE_FILENAMES:
        return True
    return False


def detect_project_verification_commands(project_root: Optional[str] = None) -> List[str]:
    """Detects standard test and verification commands available in the workspace."""
    root = project_root or os.getcwd()
    cmds: List[str] = []

    try:
        # Python test runners
        if os.path.isfile(os.path.join(root, "run_tests.py")):
            cmds.append("python run_tests.py")
        elif os.path.isfile(os.path.join(root, "pytest.ini")) or os.path.isdir(os.path.join(root, "tests")):
            cmds.append("pytest")
        elif os.path.isfile(os.path.join(root, "manage.py")):
            cmds.append("python manage.py test")

        # Node / JS / TS test runners
        pkg_json = os.path.join(root, "package.json")
        if os.path.isfile(pkg_json):
            try:
                import json
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    if "test" in scripts and "no test specified" not in scripts.get("test", ""):
                        cmds.append("npm test")
            except Exception:
                pass

        # Rust / Go
        if os.path.isfile(os.path.join(root, "Cargo.toml")):
            cmds.append("cargo test")
        if os.path.isfile(os.path.join(root, "go.mod")):
            cmds.append("go test ./...")
    except Exception as e:
        logger.debug(f"[VerificationStop] Error detecting test commands: {e}")

    return cmds


def build_verify_on_stop_nudge(
    changed_paths: Iterable[str],
    project_root: Optional[str] = None,
    attempts: int = 0,
    max_attempts: int = 2,
    has_verified: bool = False,
) -> Optional[str]:
    """
    Returns a synthetic verification nudge if code was modified without verification evidence.
    Bounded by max_attempts to prevent infinite deadlocks.
    """
    if has_verified or attempts >= max_attempts:
        return None

    # Filter out prose, docs, and non-code assets
    code_paths = [str(p) for p in changed_paths if p and not is_non_code_path(p)]
    if not code_paths:
        return None

    disp_paths = ", ".join(f"`{p}`" for p in code_paths[:5])
    if len(code_paths) > 5:
        disp_paths += f" and {len(code_paths) - 5} more"

    detected_cmds = detect_project_verification_commands(project_root)
    if detected_cmds:
        cmd_hint = ", ".join(f"`{c}`" for c in detected_cmds[:2])
        instruction = f"Run the relevant verification command now ({cmd_hint}), inspect the real output, repair any failure, and summarize what passed."
    else:
        instruction = "Run a verification command or execute a focused test/syntax check on the modified behavior to confirm there are no runtime regressions before delivering your final report."

    return (
        f"[VERIFICATION STOP-GATE]: You edited code in this turn ({disp_paths}), "
        f"but have not yet executed ground-truth verification evidence confirming the changes. "
        f"{instruction}"
    )
