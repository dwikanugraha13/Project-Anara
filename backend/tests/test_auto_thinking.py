"""
test_auto_thinking.py — Verification Suite for Auto-Thinking Dynamic Classifier.
Parity with Oh My Pi (classifier.ts).
"""

import pytest
from core.auto_thinking import classify_prompt_difficulty, resolve_auto_thinking_effort


def test_classify_trivial_greetings_and_pings():
    assert classify_prompt_difficulty("halo") == "trivial"
    assert classify_prompt_difficulty("p") == "trivial"
    assert classify_prompt_difficulty("ping") == "trivial"
    assert classify_prompt_difficulty("test") == "trivial"


def test_classify_trivial_inspect_and_read():
    assert classify_prompt_difficulty("baca file package.json") == "trivial"
    assert classify_prompt_difficulty("cek isi file config.py") == "trivial"
    assert classify_prompt_difficulty("show status") == "trivial"


def test_classify_hard_architectural_tasks():
    assert classify_prompt_difficulty("kombinasikan arsitektur Hermes dan OMP di Anara") == "hard"
    assert classify_prompt_difficulty("refactor state machine approval dan perbaiki race condition") == "hard"
    assert classify_prompt_difficulty("selidiki memory leak pada subagent swarm fanout") == "hard"


def test_classify_moderate_general_tasks():
    assert classify_prompt_difficulty("tambahkan tombol refresh di halaman dashboard") == "moderate"
    assert classify_prompt_difficulty("perbaiki format tanggal pada tabel transaksi") == "moderate"


def test_resolve_auto_thinking_effort():
    allowed = ["none", "low", "medium", "high"]

    # Trivial -> none (or low)
    eff_trivial = resolve_auto_thinking_effort("halo bro", requested_effort="auto", allowed_efforts=allowed)
    assert eff_trivial == "none"

    # Hard -> high
    eff_hard = resolve_auto_thinking_effort("desain arsitektur state machine baru untuk runner", requested_effort="auto", allowed_efforts=allowed)
    assert eff_hard == "high"

    # Moderate -> medium
    eff_mod = resolve_auto_thinking_effort("ubah warna tombol jadi biru", requested_effort="auto", allowed_efforts=allowed)
    assert eff_mod == "medium"

    # Explicit user selection overrides auto
    eff_explicit = resolve_auto_thinking_effort("halo bro", requested_effort="high", allowed_efforts=allowed)
    assert eff_explicit == "high"
