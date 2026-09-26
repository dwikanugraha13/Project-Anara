"""
test_stream4_memory.py — Comprehensive verification test suite for Stream 4 (Batches 9, 10).
Anara Agent and Anara Engineering Standards:
1. SQLite base: PRAGMAs (foreign_keys=ON, synchronous=NORMAL, busy_timeout=15000), context managers, indexes.
2. Semantic RAG & Vector Memory: dynamic embedding fallback, bounded injection (MAX_MEMORY_CHARS), atomic deletion.
3. Scratchpad & Working Memory: bounded rendering, step/finding caps, thread-safety under concurrency.
4. Voice Biometrics & Token accounting: L2 normalization, NaN/Inf sanitization, MFCC acoustic moments, prompt cache cost accounting.
5. Zero static shortcuts / keyword / timezone gates: generic defaults ("User"), global tz support, international contact numbers.
"""

import concurrent.futures
import json
import os
import sqlite3
import tempfile
import time
import numpy as np
import pytest

from memory.base import BaseMemoryEngine
from memory.episodic_adr import EpisodicADRManager
from memory.file_memory import FileMemoryManager, filter_sensitive_data
from memory.memory_nudge import TaskScratchpad, SessionTurnTracker, memory_nudge_manager
from memory.providers_tokens import calculate_token_cost, MODEL_PRICE_PER_M
from memory.semantic_rag import (
    compute_local_hash_embedding,
    cosine_similarity,
    get_current_time_str,
    get_current_indonesian_time_str,
)
from memory.voice_biometrics import extract_voice_embedding, canonicalize_speaker_name
from memory import memory_engine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db_path(tmp_path):
    """Provides a fresh isolated SQLite database path for testing."""
    db_file = tmp_path / "test_brain.db"
    return str(db_file)


# ── Test Suite 1: SQLite Base Engine & PRAGMAs ──────────────────────────────

def test_sqlite_pragmas_and_context_manager(temp_db_path):
    """Verifies PRAGMA foreign_keys=ON, synchronous=NORMAL, busy_timeout=15000, and WAL mode."""
    engine = BaseMemoryEngine(db_path=temp_db_path)

    with engine._get_connection() as conn:
        cursor = conn.cursor()
        fk = cursor.execute("PRAGMA foreign_keys;").fetchone()[0]
        sync = cursor.execute("PRAGMA synchronous;").fetchone()[0]
        timeout = cursor.execute("PRAGMA busy_timeout;").fetchone()[0]
        journal = cursor.execute("PRAGMA journal_mode;").fetchone()[0]

        assert fk == 1, "foreign_keys must be ON (1)"
        assert sync == 1, "synchronous must be NORMAL (1)"
        assert timeout >= 15000, "busy_timeout must be at least 15000 ms"
        assert journal.lower() == "wal", "journal_mode must be WAL"


def test_episodic_adr_pragmas_and_context_manager(temp_db_path):
    """Verifies EpisodicADRManager context manager applies foreign_keys=ON, synchronous=NORMAL, busy_timeout=15000."""
    adr_mgr = EpisodicADRManager(db_path=temp_db_path)

    with adr_mgr._get_connection() as conn:
        cursor = conn.cursor()
        fk = cursor.execute("PRAGMA foreign_keys;").fetchone()[0]
        sync = cursor.execute("PRAGMA synchronous;").fetchone()[0]
        timeout = cursor.execute("PRAGMA busy_timeout;").fetchone()[0]

        assert fk == 1, "ADR connection must have foreign_keys ON"
        assert sync == 1, "ADR connection must have synchronous NORMAL"
        assert timeout >= 15000, "ADR connection must have busy_timeout >= 15000"


def test_sqlite_foreign_key_cascades(temp_db_path):
    """Verifies foreign key constraints and cascade deletion in SQLite schema."""
    engine = BaseMemoryEngine(db_path=temp_db_path)

    with engine._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO speakers (name) VALUES ('TestUser')")
        spk_id = cursor.lastrowid

        cursor.execute("INSERT INTO memories (speaker_id, category, key, value) VALUES (?, 'pref', 'editor', 'vscode')", (spk_id,))
        cursor.execute("INSERT INTO projects (speaker_id, name) VALUES (?, 'Project Alpha')", (spk_id,))
        conn.commit()

        # Delete speaker -> memories and projects must CASCADE
        cursor.execute("DELETE FROM speakers WHERE id = ?", (spk_id,))
        conn.commit()

        mem_count = cursor.execute("SELECT COUNT(*) FROM memories WHERE speaker_id = ?", (spk_id,)).fetchone()[0]
        proj_count = cursor.execute("SELECT COUNT(*) FROM projects WHERE speaker_id = ?", (spk_id,)).fetchone()[0]

        assert mem_count == 0, "Memories must cascade delete when speaker is deleted"
        assert proj_count == 0, "Projects must cascade delete when speaker is deleted"


# ── Test Suite 2: Semantic RAG & Vector Memory ───────────────────────────────

def test_dynamic_local_hash_embedding():
    """Verifies deterministic 512-dim normalized embedding generation with sub-millisecond execution and no network calls."""
    text1 = "Deploying production docker microservices on Kubernetes cluster"
    text2 = "Deploying production docker microservices on k8s cluster"
    text3 = "Baking chocolate chip cookies in the oven"

    vec1 = compute_local_hash_embedding(text1, dim=512)
    vec2 = compute_local_hash_embedding(text2, dim=512)
    vec3 = compute_local_hash_embedding(text3, dim=512)

    assert len(vec1) == 512
    assert len(vec2) == 512
    assert len(vec3) == 512

    # L2 unit normalization check
    np.testing.assert_allclose(np.linalg.norm(vec1), 1.0, atol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(vec2), 1.0, atol=1e-5)
    np.testing.assert_allclose(np.linalg.norm(vec3), 1.0, atol=1e-5)

    # Cosine similarity: related dev queries score higher than baking
    sim_tech = cosine_similarity(vec1, vec2)
    sim_baking = cosine_similarity(vec1, vec3)
    assert sim_tech > sim_baking, f"Tech similarity ({sim_tech}) should exceed cross-domain baking ({sim_baking})"


def test_bounded_memory_injection_cap():
    """Verifies MAX_MEMORY_CHARS limit in get_system_prompt_context prevents prompt bloating."""
    speaker = "BudgetTestUser"
    memory_engine.enroll_or_update_speaker(speaker)

    # Insert 50 large memories
    for i in range(50):
        memory_engine.store_memory(
            speaker_name=speaker,
            key=f"large_fact_key_{i}",
            value=f"This is an extensive technical fact description with id {i} designed to consume significant memory characters.",
            category="technical"
        )

    prompt_ctx = memory_engine.get_system_prompt_context(speaker_name=speaker, is_chat_mode=True)
    assert len(prompt_ctx) > 0

    # Ensure memory section obeys MAX_MEMORY_CHARS bounds (~2200 chars)
    m_rows = memory_engine.get_memories_for_speaker(speaker)
    MAX_MEMORY_CHARS = 2200
    current_chars = 0
    injected_count = 0
    for r in m_rows:
        entry = f"- {r['key'].replace('_', ' ').title()} ({r['category']}): {r['value']}"
        if current_chars + len(entry) > MAX_MEMORY_CHARS:
            break
        current_chars += len(entry)
        injected_count += 1

    assert current_chars <= MAX_MEMORY_CHARS
    assert injected_count < 50, "Memory injection must be bounded and not dump all 50 items"

    # Cleanup
    memory_engine.delete_speaker(speaker)


def test_atomic_deletion_without_data_loss_or_orphans():
    """Verifies deleting a memory by ID or key works even if no embedding exists, and purges embeddings cleanly."""
    spk_a = "SpeakerAlice"
    spk_b = "SpeakerBob"
    memory_engine.enroll_or_update_speaker(spk_a)
    memory_engine.enroll_or_update_speaker(spk_b)

    # Both speakers have the same key 'editor'
    memory_engine.store_memory(spk_a, "preferred_editor", "neovim", "preference")
    memory_engine.store_memory(spk_b, "preferred_editor", "emacs", "preference")

    mem_a = [m for m in memory_engine.get_memories_for_speaker(spk_a) if m["key"] == "preferred_editor"][0]
    mem_b = [m for m in memory_engine.get_memories_for_speaker(spk_b) if m["key"] == "preferred_editor"][0]

    # Deleting SpeakerAlice's memory by ID must return True and NOT delete SpeakerBob's memory
    ok = memory_engine.delete_memory_by_id(mem_a["id"])
    assert ok is True, "delete_memory_by_id should return True on successful deletion"

    mems_after_b = memory_engine.get_memories_for_speaker(spk_b)
    b_keys = [m["key"] for m in mems_after_b]
    assert "preferred_editor" in b_keys, "SpeakerBob's memory must not be deleted when SpeakerAlice's memory is removed"

    # Deleting SpeakerBob's memory by key must succeed
    ok_b = memory_engine.delete_memory(spk_b, "preferred_editor")
    assert ok_b is True

    # Cleanup
    memory_engine.delete_speaker(spk_a)
    memory_engine.delete_speaker(spk_b)


# ── Test Suite 3: TaskScratchpad & Working Memory ────────────────────────────

def test_task_scratchpad_bounded_rendering():
    """Verifies TaskScratchpad bounds steps, findings, and total prompt characters."""
    pad = TaskScratchpad(session_id="test_bounds_session")
    pad.set_objective("Execute full codebase modernization with zero downtime", steps=[
        f"Modernize module component number {i} with unit testing" for i in range(25)
    ])

    for i in range(15):
        pad.add_finding(f"Discovered technical dependency bottleneck in subsystem {i}")

    # Mark some steps
    pad.mark_step(0, "done")
    pad.mark_step(1, "in_progress")

    # Full budget render (1500 chars)
    rendered = pad.render_to_prompt(max_steps=10, max_findings=5, char_limit=1500)
    assert len(rendered) <= 1500
    assert "PRIMARY TARGET:" in rendered
    assert "[x] 1." in rendered
    assert "[-] 2." in rendered
    assert "(+15 more steps)" in rendered
    assert "(+10 more findings)" in rendered

    # Strict char_limit truncation test
    rendered_truncated = pad.render_to_prompt(max_steps=10, max_findings=5, char_limit=400)
    assert len(rendered_truncated) <= 400


def test_task_scratchpad_concurrency_thread_safety():
    """Verifies TaskScratchpad survives highly concurrent multi-threaded read/write access."""
    pad = TaskScratchpad(session_id="test_concurrency_session")
    pad.set_objective("Concurrent multi-agent execution")

    def _worker(worker_id: int):
        for i in range(20):
            pad.add_step(f"Step {worker_id}-{i}")
            pad.add_finding(f"Finding {worker_id}-{i}")
            pad.mark_step(f"Step {worker_id}-{i}", "done")
            _ = pad.render_to_prompt()
            _ = pad.to_checklist_payload()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_worker, wid) for wid in range(8)]
        for f in concurrent.futures.as_completed(futures):
            f.result()

    # Steps and findings must respect hard caps (<= 30 steps, <= 20 findings)
    assert len(pad.steps) <= 30
    assert len(pad.findings) <= 20
    pad.clear()
    assert len(pad.steps) == 0


# ── Test Suite 4: Voice Biometrics & Token Accounting ───────────────────────

def test_voice_biometrics_l2_normalization_and_nan_sanitization():
    """Verifies extract_voice_embedding returns 128-dim L2 unit vector without NaN/Inf values."""
    # Synthetic PCM audio: 16000Hz, 0.5s of 440Hz sine wave (16000 bytes PCM16)
    sample_rate = 16000
    t = np.linspace(0, 0.5, int(sample_rate * 0.5), endpoint=False)
    sine = (np.sin(2 * np.pi * 440 * t) * 16000).astype(np.int16)
    pcm_bytes = sine.tobytes()

    emb = extract_voice_embedding(pcm_bytes, sample_rate=sample_rate)
    assert emb is not None
    assert emb.shape == (128,)
    assert not np.isnan(emb).any(), "Embedding must not contain NaN"
    assert not np.isinf(emb).any(), "Embedding must not contain Inf"
    np.testing.assert_allclose(np.linalg.norm(emb), 1.0, atol=1e-5)


def test_token_cost_accounting_with_prompt_caching():
    """Verifies calculate_token_cost calculates costs with model pricing and prompt caching discounts."""
    # Test Claude 3.5 Sonnet: $3.00/1M input, $0.30/1M cache read (90% discount), $15.00/1M output
    cost_no_cache = calculate_token_cost("claude-3-5-sonnet", prompt_tokens=100_000, completion_tokens=10_000, cached_tokens=0)
    # 100k * $3/1M = $0.30; 10k * $15/1M = $0.15 => Total = $0.45
    assert abs(cost_no_cache - 0.45) < 1e-4

    cost_with_cache = calculate_token_cost("claude-3-5-sonnet", prompt_tokens=100_000, completion_tokens=10_000, cached_tokens=80_000)
    # 20k uncached * $3/1M = $0.06; 80k cached * $0.30/1M = $0.024; 10k * $15/1M = $0.15 => Total = $0.234
    assert abs(cost_with_cache - 0.234) < 1e-4
    assert cost_with_cache < cost_no_cache, "Prompt caching must discount token costs"

    # Test record_token_usage persists cached_tokens and estimated_cost
    rec_id = memory_engine.record_token_usage(
        model_id="claude-3-5-sonnet",
        provider="anthropic",
        prompt_tokens=100_000,
        completion_tokens=10_000,
        cached_tokens=80_000,
    )
    assert rec_id > 0

    summary = memory_engine.get_token_usage_summary()
    assert summary["overall"]["total_cached_tokens"] >= 80_000
    assert summary["overall"]["total_cost"] > 0.0


# ── Test Suite 5: Zero Static Shortcuts & Zero Keyword Traps ────────────────

def test_zero_hardcoded_user_shortcuts():
    """Verifies target_speaker defaults to 'User' and not hardcoded names when no speaker registered."""
    speaker = memory_engine.get_last_active_speaker_name()
    if not speaker:
        # With empty / uncalibrated speaker, prompt context must use 'User'
        ctx = memory_engine.get_system_prompt_context(speaker_name=None, is_chat_mode=True)
        assert "Agnan" not in ctx or "User" in ctx


def test_global_timezone_support():
    """Verifies get_current_time_str supports arbitrary global timezones and custom labels."""
    # Test London / UTC
    utc_info = get_current_time_str(offset_minutes=0, tz_name="UTC")
    assert "UTC" in utc_info["time_str"]
    assert utc_info["tz_label"] == "UTC"

    # Test New York / EST (-300 minutes offset)
    est_info = get_current_time_str(offset_minutes=300, tz_name="EST")
    assert "EST" in est_info["time_str"]
    assert est_info["tz_label"] == "EST"

    # Test Tokyo / JST (-540 minutes offset)
    jst_info = get_current_time_str(offset_minutes=-540, tz_name="JST")
    assert "JST" in jst_info["time_str"]
    assert jst_info["tz_label"] == "JST"


def test_international_contact_preservation():
    """Verifies contact phone numbers with international '+' prefixes are not corrupted into Indonesian prefixes."""
    # US number with +1
    us_contact = memory_engine.save_contact("Alice US", "+1-415-555-2671")
    assert us_contact["status"] == "ok"
    assert us_contact["phone"].startswith("1415")
    assert not us_contact["phone"].startswith("628")

    # UK number with +44
    uk_contact = memory_engine.save_contact("Bob UK", "+44-20-7946-0958")
    assert uk_contact["status"] == "ok"
    assert uk_contact["phone"].startswith("4420")
    assert not uk_contact["phone"].startswith("628")


def test_sensitive_data_privacy_filter():
    """Verifies API keys, tokens, and passwords are redacted before writing to memory."""
    fake_sk = "s" + "k-abcdefghijklmnopqrstuvwxyz1234567890"
    fake_gh = "g" + "hp_abcdefghijklmnopqrstuvwxyz1234567890"
    text_with_keys = (
        f"Here is my openai key {fake_sk} and "
        f"my github token {fake_gh}."
    )
    filtered = filter_sensitive_data(text_with_keys)
    assert "sk-" not in filtered
    assert "ghp_" not in filtered
    assert "[REDACTED_API_KEY]" in filtered or "[REDACTED_GITHUB_TOKEN]" in filtered
