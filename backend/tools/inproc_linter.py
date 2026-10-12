"""
inproc_linter.py — In-Process Post-Write Syntax Lint Gate for Project Anara.
Parity with Hermes Agent tools/file_operations_lint.py (Nous Research).

Executes microsecond in-process syntax checks on newly written or edited files (.py, .json, .toml, .yaml).
Surfaces syntax errors immediately in tool observations so the agent can self-correct in the next turn
rather than breaking the workspace or failing downstream test suites.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import tomllib
from typing import Any, Dict, Optional

logger = logging.getLogger("anara.tools.inproc_linter")


def lint_code_syntax(
    file_path: str,
    content: str,
    pre_content: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Performs fast in-process syntax verification with Differential Lint Delta Filtering
    (Hermes Agent tools/file_operations_lint.py Parity).
    
    If pre_content is provided, pre-existing syntax errors in legacy files are filtered out
    so the agent is never trapped in a phantom self-correction loop for errors it didn't introduce.
    
    Returns:
        None if code syntax is valid or if the error is pre-existing legacy error.
        Dict with error details if a NEW syntax error was introduced by the edit.
    """
    if not file_path or not content:
        return None

    post_err = _lint_single_content(file_path, content)
    if not post_err:
        return None

    # Differential Lint Delta: Check if the file was already broken before this edit
    if pre_content is not None and pre_content.strip():
        pre_err = _lint_single_content(file_path, pre_content)
        if pre_err:
            # If the error type and error details match, this is a pre-existing legacy issue
            is_same_error = (
                pre_err.get("error_type") == post_err.get("error_type")
                and (
                    pre_err.get("message") == post_err.get("message")
                    or pre_err.get("line") == post_err.get("line")
                )
            )
            if is_same_error:
                logger.debug(
                    f"[InprocLinter] Pre-existing syntax error in '{file_path}' filtered out: {post_err.get('message')}"
                )
                return None

    return post_err


def _lint_single_content(file_path: str, content: str) -> Optional[Dict[str, Any]]:
    """Performs single-pass AST / syntax verification on given content."""
    ext = os.path.splitext(file_path)[1].lower()

    # 1. Python Syntax Validation via AST
    if ext == ".py":
        try:
            ast.parse(content, filename=os.path.basename(file_path))
            return None
        except SyntaxError as e:
            return {
                "valid": False,
                "language": "python",
                "error_type": "SyntaxError",
                "line": e.lineno,
                "offset": e.offset,
                "line_text": e.text.strip() if e.text else "",
                "message": f"Python SyntaxError at line {e.lineno}: {e.msg}",
            }
        except Exception as e:
            return {
                "valid": False,
                "language": "python",
                "error_type": "ParseException",
                "message": f"Python Parse error: {str(e)}",
            }

    # 2. JSON Syntax Validation
    elif ext == ".json":
        try:
            json.loads(content)
            return None
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "language": "json",
                "error_type": "JSONDecodeError",
                "line": e.lineno,
                "column": e.colno,
                "message": f"JSON SyntaxError at line {e.lineno}, column {e.colno}: {e.msg}",
            }

    # 3. TOML Syntax Validation
    elif ext == ".toml":
        try:
            tomllib.loads(content)
            return None
        except Exception as e:
            return {
                "valid": False,
                "language": "toml",
                "error_type": "TOMLDecodeError",
                "message": f"TOML SyntaxError: {str(e)}",
            }

    # 4. YAML Syntax Validation (if PyYAML is installed)
    elif ext in (".yaml", ".yml"):
        try:
            import yaml
            list(yaml.safe_load_all(content))
            return None
        except Exception as e:
            err_name = type(e).__name__
            err_msg = str(e)
            if "ConstructorError" in err_name or "could not determine a constructor" in err_msg:
                # Custom app tags are syntactically valid YAML
                return None
            return {
                "valid": False,
                "language": "yaml",
                "error_type": "YAMLError",
                "message": f"YAML SyntaxError: {err_msg}",
            }

    return None
