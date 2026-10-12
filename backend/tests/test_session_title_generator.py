"""
Tests for Session Title Generator, Provenance Authority, and Lineage Deduplication (Anara Standard).
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from core.title_generator import (
    strip_control_wrappers,
    is_titleable_user_message,
    derive_title,
    is_provisional_greeting_title,
    is_prompt_example_echo,
    clean_title,
    apply_instant_title,
    generate_title_llm,
    auto_title_session_async,
    maybe_auto_title,
    MAX_DERIVED_TITLE_CHARS,
    MAX_TITLE_WORDS,
)
from memory import memory_engine


def test_strip_control_wrappers():
    raw = "<command-message><command-name>git</command-name>git status</command-message> Tolong cek branch ini"
    stripped = strip_control_wrappers(raw)
    assert "Tolong cek branch ini" in stripped


def test_is_titleable_user_message():
    assert is_titleable_user_message("Bantu bikin REST API") is True
    assert is_titleable_user_message("") is False
    assert is_titleable_user_message("   ") is False
    assert is_titleable_user_message("[SYSTEM] Context compaction initiated") is False
    assert is_titleable_user_message("[RUNTIME NOTE: Switched model]") is False


def test_derive_instant_title():
    # 1. Normal short prompt
    short_prompt = "Bantu refactor modul auth"
    derived = derive_title(short_prompt)
    assert derived == "Bantu refactor modul auth"

    # 2. Multi-line prompt - takes first line
    multiline = "Perbaiki error database connection pool\nDetail error: connection timeout on port 5432"
    derived_multi = derive_title(multiline)
    assert derived_multi == "Perbaiki error database connection pool"

    # 3. Long prompt - trimmed to word boundary <= 48 chars
    long_prompt = "Tolong investigasi dan perbaiki bug login button yang tidak responsive pada layar mobile view"
    derived_long = derive_title(long_prompt)
    assert len(derived_long) <= MAX_DERIVED_TITLE_CHARS + 1  # room for ellipsis
    assert derived_long.endswith("…")


def test_provisional_greeting_and_echo_guard():
    assert is_provisional_greeting_title("Friendly greeting") is True
    assert is_provisional_greeting_title("friendly greeting in chat") is True
    assert is_provisional_greeting_title("Halo") is True
    assert is_provisional_greeting_title("Perbaiki bug auth") is False

    assert is_prompt_example_echo("Fix login button on mobile") is True
    assert is_prompt_example_echo("Postgres connection pool exhaustion") is True
    assert is_prompt_example_echo("Code changes") is True
    assert is_prompt_example_echo("Kustom judul proyek") is False


def test_clean_title_and_word_guard():
    assert clean_title('Title: "Refactor Database"') == "Refactor Database"
    assert clean_title("Topic: Analisis Sentimen Twitter.") == "Analisis Sentimen Twitter"


def test_provenance_authority_ranking():
    sess = memory_engine.create_session(title="New Chat")
    sid = sess["id"]

    try:
        # Step 1: Stage 1 sets 'derived'
        ok1 = memory_engine.set_auto_title(sid, "Instant derived title", source="derived")
        assert ok1 is True
        s1 = memory_engine.get_session(sid)
        assert s1["title"] == "Instant derived title"
        assert s1["title_source"] == "derived"

        # Step 2: Stage 2 upgrades 'derived' to 'llm'
        ok2 = memory_engine.set_auto_title(sid, "Upgraded Semantic Title", source="llm")
        assert ok2 is True
        s2 = memory_engine.get_session(sid)
        assert s2["title"] == "Upgraded Semantic Title"
        assert s2["title_source"] == "llm"

        # Step 3: 'derived' cannot overwrite 'llm'
        ok3 = memory_engine.set_auto_title(sid, "Late derived title", source="derived")
        assert ok3 is False
        s3 = memory_engine.get_session(sid)
        assert s3["title"] == "Upgraded Semantic Title"  # untouched

        # Step 4: User manual rename sets 'user' authority
        ok4 = memory_engine.rename_session(sid, "Manual User Chosen Title")
        assert ok4 is True
        s4 = memory_engine.get_session(sid)
        assert s4["title"] == "Manual User Chosen Title"
        assert s4["title_source"] == "user"

        # Step 5: Neither 'derived' nor 'llm' can overwrite 'user'
        ok5 = memory_engine.set_auto_title(sid, "Attempted LLM overwrite", source="llm")
        assert ok5 is False
        ok6 = memory_engine.set_auto_title(sid, "Attempted derived overwrite", source="derived")
        assert ok6 is False
        s5 = memory_engine.get_session(sid)
        assert s5["title"] == "Manual User Chosen Title"
        assert s5["title_source"] == "user"
    finally:
        memory_engine.delete_session(sid)


def test_lineage_collision_deduplication():
    sess1 = memory_engine.create_session(title="Duplicate Subject")
    sess2 = memory_engine.create_session(title="New Chat")
    sid1 = sess1["id"]
    sid2 = sess2["id"]

    try:
        # Setting title for sess2 that collides with sess1
        ok = memory_engine.set_auto_title(sid2, "Duplicate Subject", source="llm")
        assert ok is True
        s2 = memory_engine.get_session(sid2)
        assert s2["title"] == "Duplicate Subject #2"

        # Next collision becomes #3
        sess3 = memory_engine.create_session(title="New Chat")
        sid3 = sess3["id"]
        try:
            ok3 = memory_engine.set_auto_title(sid3, "Duplicate Subject", source="llm")
            assert ok3 is True
            s3 = memory_engine.get_session(sid3)
            assert s3["title"] == "Duplicate Subject #3"
        finally:
            memory_engine.delete_session(sid3)
    finally:
        memory_engine.delete_session(sid1)
        memory_engine.delete_session(sid2)


@pytest.mark.anyio
async def test_llm_guards_and_provisional():
    # 1. Answer shaped output guard (> 12 words)
    with patch("providers.caller.call_universal_chat_model", return_value="Here is an exhaustive explanation of how to configure postgres connection pools with high concurrency"):
        res = await generate_title_llm("Postgres config")
        assert res is None  # rejected due to > 12 words

    # 2. Echo guard
    with patch("providers.caller.call_universal_chat_model", return_value='{"title": "Fix login button on mobile"}'):
        res = await generate_title_llm("Tombol login rusak")
        assert res is None  # rejected because it echoes prompt example

    # 3. Successful title
    with patch("providers.caller.call_universal_chat_model", return_value='{"title": "Setup PostgreSQL Pool"}'):
        res = await generate_title_llm("Postgres config")
        assert res == "Setup PostgreSQL Pool"


@pytest.mark.anyio
async def test_prologue_instant_and_model_upgrade():
    sess = memory_engine.create_session(title="New Chat")
    sid = sess["id"]

    try:
        with patch("providers.caller.call_universal_chat_model", return_value='{"title": "Audit Security Gateways"}'):
            # Calling maybe_auto_title in prologue
            task = maybe_auto_title(sid, "Audit semua security gateway di backend")
            assert task is not None

            # Instant title already persisted
            s_instant = memory_engine.get_session(sid)
            assert s_instant["title"] == "Audit semua security gateway di backend"
            assert s_instant["title_source"] == "derived"

            # Wait for background upgrade
            await task

            # Title upgraded to LLM semantic title
            s_upgraded = memory_engine.get_session(sid)
            assert s_upgraded["title"] == "Audit Security Gateways"
            assert s_upgraded["title_source"] == "llm"
    finally:
        memory_engine.delete_session(sid)
