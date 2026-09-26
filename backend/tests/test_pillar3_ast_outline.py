"""
test_pillar3_ast_outline.py — Verification test suite for Pillar 3: AST Outline & Code Navigation Tool.
Anara Engineering Standards:
1. Token-efficient structural AST analysis for Python (classes, methods, docstrings, lines).
2. Symbolic navigation for TypeScript, JavaScript, Markdown.
3. Central tool registry dispatch and error handling.
"""

import asyncio
import os
import tempfile
import pytest

from tools.fs_tools import _tool_extract_code_outline
from tools.catalog import registry


def test_extract_code_outline_python_ast():
    """Verifies that Python AST outline extracts classes, async methods, and line ranges."""
    code = '''"""Module docstring."""

class PaymentGateway:
    """Handles credit card settlements."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def charge_card(self, amount: int, currency: str = "USD") -> bool:
        """Charges specified amount to card."""
        return True

async def standalone_utility(x: int) -> int:
    """Helper utility function."""
    return x * 2
'''
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        res = asyncio.run(_tool_extract_code_outline(temp_path))
        assert res["status"] == "success"
        assert res["total_lines"] == len(code.splitlines())
        assert res["total_symbols"] >= 2

        outline = res["outline"]
        assert "class PaymentGateway" in outline
        assert "Handles credit card settlements" in outline
        assert "charge_card" in outline
        assert "async def standalone_utility" in outline
        assert "lines" in outline
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_extract_code_outline_markdown():
    """Verifies that Markdown files extract section headers."""
    md = """# Project Overview
Some introductory text.

## Architecture
Details about architecture.

### Storage
SQLite WAL database.
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write(md)
        temp_path = f.name

    try:
        res = asyncio.run(_tool_extract_code_outline(temp_path))
        assert res["status"] == "success"
        outline = res["outline"]
        assert "# Project Overview" in outline
        assert "## Architecture" in outline
        assert "### Storage" in outline
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_extract_code_outline_via_registry_dispatch():
    """Verifies that extract_code_outline is dispatchable via the central tool registry."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write("def compute_hash():\n    return 42\n")
        temp_path = f.name

    try:
        res = asyncio.run(registry.dispatch("extract_code_outline", {"file_path": temp_path}))
        assert res["status"] == "success"
        assert "compute_hash" in res["outline"]
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
