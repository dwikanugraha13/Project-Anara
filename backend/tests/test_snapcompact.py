"""
test_snapcompact.py — Verification Suite for SnapCompact Lossless Bitmap Context Compression.
"""

import os
import tempfile
import pytest

from core.snapcompact import (
    is_snapcompact_supported,
    render_text_to_bitmap_frame,
    render_conversation_to_snapcompact_frames,
    get_snapcompact_summary_block,
    FRAME_WIDTH,
    FRAME_HEIGHT,
)


def test_snapcompact_support():
    assert is_snapcompact_supported() is True


def test_render_bitmap_frame_dimensions():
    sample_text = "\n".join([f"line {i}: const value_{i} = {i * 10};" for i in range(20)])
    frame = render_text_to_bitmap_frame(
        text=sample_text,
        page_index=1,
        total_pages=1,
        session_title="Unit Test"
    )
    assert frame is not None
    assert frame.size == (FRAME_WIDTH, FRAME_HEIGHT)


def test_render_conversation_to_frames_creates_valid_png():
    long_conversation = "\n".join([
        f"User: Can you check file_{i}.ts?\nAnara: Checked file_{i}.ts, exported function run_{i}."
        for i in range(120)
    ])

    with tempfile.TemporaryDirectory() as tmpdir:
        frame_paths = render_conversation_to_snapcompact_frames(
            conversation_text=long_conversation,
            session_id="test_session_123",
            output_dir=tmpdir
        )

        assert len(frame_paths) >= 2
        for p in frame_paths:
            assert os.path.exists(p)
            assert p.endswith(".png")
            assert os.path.getsize(p) > 1000  # Valid non-empty PNG

        summary = get_snapcompact_summary_block(frame_paths, total_lines=240)
        assert "[SNAPCOMPACT ARCHIVE:" in summary
        assert "BITMAP FRAME" in summary
