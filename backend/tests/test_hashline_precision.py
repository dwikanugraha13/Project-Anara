"""
test_hashline_precision.py — Verification Suite for Hashline Precision & Polymorphic Editing.
Ensures line-anchored mutations, snapshot 4-hex tags, stale detection, and register capture.
"""

import os
import tempfile
import pytest

from tools.hashline_engine import (
    compute_file_tag,
    format_hashline_content,
    is_hashline_syntax,
    apply_hashline_patch,
    _SESSION_REGISTERS,
)
from tools.fs_tools import _tool_read_local_file, _tool_edit_file


def test_hashline_tag_computation_and_determinism():
    sample_text = "def hello():\n    print('Hello World')\n"
    tag1 = compute_file_tag(sample_text)
    tag2 = compute_file_tag(sample_text)
    assert tag1 == tag2
    assert len(tag1) == 4
    assert tag1.isalnum()

    # CRLF and trailing spaces normalization
    crlf_text = "def hello():  \r\n    print('Hello World')\r\n"
    tag_crlf = compute_file_tag(crlf_text)
    assert tag1 == tag_crlf


def test_hashline_syntax_detection():
    assert is_hashline_syntax("[src/app.py#1A2B]\nPUT 2.=3:\n+pass") is True
    assert is_hashline_syntax("PUT 4.=5:\n+const a = 1;") is True
    assert is_hashline_syntax("CUT 10.=12") is True
    assert is_hashline_syntax("SWAP 1.=1:\n+x = 2") is True
    assert is_hashline_syntax("*** Begin Patch\nPUT <1:\n+first\n*** End Patch") is True
    assert is_hashline_syntax("simple string replace") is False


def test_hashline_apply_put_range():
    original = "line 1\nline 2\nline 3\nline 4\nline 5\n"
    tag = compute_file_tag(original)

    patch = f"""[{'test.txt'}#{tag}]
PUT 2.=3:
+new line 2
+new line 3
"""
    new_content, err, stats = apply_hashline_patch(original, patch)
    assert err is None
    assert new_content == "line 1\nnew line 2\nnew line 3\nline 4\nline 5\n"
    assert stats["tag_verified"] is True
    assert stats["deleted_lines"] == 2
    assert stats["added_lines"] == 2


def test_hashline_apply_insert_before_and_after():
    original = "line 1\nline 2\nline 3\n"
    tag = compute_file_tag(original)

    patch = f"""[test.txt#{tag}]
PUT <1:
+header
PUT >3:
+footer
"""
    new_content, err, stats = apply_hashline_patch(original, patch)
    assert err is None
    expected = "header\nline 1\nline 2\nline 3\nfooter\n"
    assert new_content == expected


def test_hashline_apply_cut_and_named_registers():
    original = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    tag = compute_file_tag(original)

    patch = f"""[test.txt#{tag}]
CUT 1.=2 @fn_foo
PUT >$ @fn_foo
"""
    regs = {}
    new_content, err, stats = apply_hashline_patch(original, patch, registers=regs)
    assert err is None
    assert new_content is not None
    assert "@fn_foo" in regs or "fn_foo" in regs
    assert "def foo():\n    return 1\n" in new_content


def test_hashline_stale_anchor_rejection():
    original = "const x = 1;\nconst y = 2;\n"
    wrong_tag = "FFFF"
    actual_tag = compute_file_tag(original)
    if actual_tag == "FFFF":
        wrong_tag = "0000"

    patch = f"""[app.ts#{wrong_tag}]
PUT 1.=1:
+const x = 100;
"""
    new_content, err, stats = apply_hashline_patch(original, patch)
    assert new_content is None
    assert err is not None
    assert "Stale snapshot tag mismatch" in err


@pytest.mark.anyio
async def test_fs_tools_polymorphic_read_and_edit():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "service.py")
        initial_code = "import os\n\ndef run():\n    return 'initial'\n"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(initial_code)

        # 1. Read file with hashline snapshot
        read_res = await _tool_read_local_file(test_file)
        assert read_res["status"] == "success"
        assert "file_tag" in read_res
        tag = read_res["file_tag"]
        assert f"#{tag}]" in read_res["content"]

        # 2. Edit using Hashline syntax
        hashline_payload = f"""[{os.path.basename(test_file)}#{tag}]
PUT 4.=4:
+    return 'updated_via_hashline'
"""
        edit_res1 = await _tool_edit_file(
            file_path=test_file,
            old_string=hashline_payload
        )
        assert edit_res1["status"] == "success"
        with open(test_file, "r", encoding="utf-8") as f:
            content_after1 = f.read()
        assert "updated_via_hashline" in content_after1

        # 3. Edit using Standard Fuzzy Replace on same file
        edit_res2 = await _tool_edit_file(
            file_path=test_file,
            old_string="return 'updated_via_hashline'",
            new_string="return 'updated_via_fuzzy'"
        )
        assert edit_res2["status"] == "success"
        with open(test_file, "r", encoding="utf-8") as f:
            content_after2 = f.read()
        assert "updated_via_fuzzy" in content_after2


@pytest.mark.anyio
async def test_inner_loop_syntax_regression_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "broken.py")
        valid_code = "def add(a, b):\n    return a + b\n"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(valid_code)

        # 1. Edit that introduces syntax error (unexpected indent / syntax violation)
        broken_res = await _tool_edit_file(
            file_path=test_file,
            old_string="return a + b",
            new_string="return (a + b"  # unclosed parenthesis
        )
        assert broken_res["status"] == "success"
        assert broken_res.get("lint_warning") is not None
        assert "SyntaxError" in broken_res["lint_warning"]

        # 2. Self-repair edit using hashline
        tag = compute_file_tag("def add(a, b):\n    return (a + b\n")
        repair_patch = f"""[{os.path.basename(test_file)}#{tag}]
PUT 2.=2:
+    return a + b
"""
        repair_res = await _tool_edit_file(
            file_path=test_file,
            old_string=repair_patch
        )
        assert repair_res["status"] == "success"
        assert repair_res.get("lint_warning") is None


def test_apply_from_sketch_mode_resolves_placeholders():
    from tools.fuzzy_match import _perform_fuzzy_replace

    source_code = """def process_order(order):
    if not order:
        return None
    val = order.get_value()
    tax = val * 0.1
    return tax + val
"""

    # Model was lazy and omitted the middle lines using '# ... existing code ...'
    lazy_old = """def process_order(order):
    # ... existing code ...
    tax = val * 0.1"""

    lazy_new = """def process_order(order):
    # ... existing code ...
    tax = (val - 10) * 0.1"""

    new_content, matched, err = _perform_fuzzy_replace(source_code, lazy_old, lazy_new)
    assert err is None
    assert new_content is not None
    assert "val = order.get_value()" in new_content
    assert "tax = (val - 10) * 0.1" in new_content
    assert "return tax + val" in new_content


@pytest.mark.anyio
async def test_ast_outline_directory_on_large_file_read():
    from tools.fs_tools import _tool_read_local_file

    with tempfile.TemporaryDirectory() as tmpdir:
        large_file = os.path.join(tmpdir, "large_module.py")
        # Build file with >260 lines containing classes and functions
        lines = ["# Large Python module header\n"]
        for i in range(25):
            lines.append(f"class Service_{i}:\n")
            lines.append(f"    def do_work_{i}(self):\n")
            lines.append(f"        return {i}\n\n")
            lines.append(f"    def compute_{i}(self, x):\n")
            lines.append(f"        return x * {i}\n\n")
            lines.append(f"    def finish_{i}(self):\n")
            lines.append(f"        pass\n\n")

        with open(large_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        res = await _tool_read_local_file(large_file)
        assert res["status"] == "success"
        assert res["total_lines"] > 250
        content = res["content"]
        assert "[... truncated" in content
        assert "[OUTLINE DIRECTORY (Symbols & Lines)]:" in content
        assert "class Service_0" in content
        assert "def do_work_0" in content


def test_speculative_tool_prefetching():
    from tools.fs_tools import speculative_prefetch_file, _SPECULATIVE_PREFETCH_STORE

    with tempfile.TemporaryDirectory() as tmpdir:
        sample_file = os.path.join(tmpdir, "prefetch_sample.py")
        sample_content = "def fast():\n    return 'cached'\n"
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write(sample_content)

        ok = speculative_prefetch_file(sample_file)
        assert ok is True
        norm_key = os.path.normcase(os.path.abspath(sample_file))
        assert norm_key in _SPECULATIVE_PREFETCH_STORE
        assert _SPECULATIVE_PREFETCH_STORE[norm_key][2] == sample_content




