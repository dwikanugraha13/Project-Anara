"""
test_hybrid_session_identity.py — Test suite for Hybrid Dual-Identity Session Engine.
Anara Enterprise Architecture:
1. Canonical collision-free session key generation (YYYYMMDD_HHMMSS_<hex>).
2. Dual-Identity session creation with SQLite numeric ID + canonical session_key.
3. Transparent lookup parity by numeric ID or string session_key.
4. PromptAssembler metadata injection formatting (#<id> (<session_key>)).
"""
import pytest
from datetime import datetime
from core.session_ids import new_session_key, is_valid_session_key
from memory import memory_engine
from core.prompt_assembler import PromptAssembler


def test_session_key_format():
    key = new_session_key()
    assert is_valid_session_key(key) is True
    assert len(key) == 22  # 8 (date) + 1 (_) + 6 (time) + 1 (_) + 6 (hex)
    assert key[8] == "_"
    assert key[15] == "_"


def test_create_and_lookup_hybrid_session():
    # Create test session
    sess = memory_engine.create_session(
        speaker_name="AgnanTest",
        title="Hybrid Test Session",
        session_type="chat",
        channel="cli"
    )
    sid = sess["id"]
    skey = sess["session_key"]

    assert isinstance(sid, int)
    assert is_valid_session_key(skey) is True

    # Lookup by integer id
    by_int = memory_engine.get_session(sid)
    assert by_int is not None
    assert by_int["id"] == sid
    assert by_int["session_key"] == skey

    # Lookup by string representation of integer id
    by_str_id = memory_engine.get_session(str(sid))
    assert by_str_id is not None
    assert by_str_id["id"] == sid

    # Lookup by canonical session_key
    by_key = memory_engine.get_session(skey)
    assert by_key is not None
    assert by_key["id"] == sid
    assert by_key["session_key"] == skey

    # Cleanup test session
    with memory_engine._get_connection() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
        conn.commit()


def test_prompt_assembler_hybrid_session_rendering():
    sess = memory_engine.create_session(
        speaker_name="AgnanTest",
        title="Prompt Render Test",
        session_type="chat",
        channel="cli"
    )
    sid = sess["id"]
    skey = sess["session_key"]

    try:
        rendered = PromptAssembler.assemble(
            mode="conversational",
            speaker_name="AgnanTest",
            is_chat_mode=True,
            session_type="chat",
            channel="cli",
            session_id=sid
        )

        expected_tag = f"Current Session: #{sid} ({skey})"
        assert expected_tag in rendered
        assert "[ACTIVE RUNTIME & SESSION METADATA]" in rendered
    finally:
        with memory_engine._get_connection() as conn:
            conn.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
            conn.commit()
