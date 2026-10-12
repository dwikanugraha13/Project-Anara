"""
test_sharpshooter.py — Verification Suite for Sharpshooter Friction-Gated Project Memory.
Parity with Oh My Pi (sharpshooter/types.ts).
"""

import pytest
from core.sharpshooter import detect_friction, maybe_record_friction_decision
from memory.episodic_adr import episodic_adr_manager


def test_detect_friction_corrective():
    res = detect_friction("jangan pakai garis vertikal border-l-[3px] lagi")
    assert res is not None
    assert res["kind"] == "correction"
    assert res["friction"]["corrective"] is True
    assert "border-l-[3px]" in res["statement"]


def test_detect_friction_regression():
    res = detect_friction("kemarin jalan kok sekarang error lagi pas di-klik")
    assert res is not None
    assert res["kind"] == "regression"
    assert res["friction"]["regression"] is True


def test_detect_friction_architecture_decision():
    res = detect_friction("kita sepakat: wajib gunakan tema Liquid Glass obsidian")
    assert res is not None
    assert res["kind"] == "architecture_decision"
    assert "Liquid Glass" in res["statement"]


def test_detect_friction_non_friction_chat():
    # Routine chatter, questions, and instructions without friction are NOT admitted
    assert detect_friction("halo bro apa kabar?") is None
    assert detect_friction("baca file package.json dong") is None
    assert detect_friction("terima kasih ya") is None


def test_maybe_record_friction_decision():
    prompt = "jangan gunakan library moment.js, pakai date-fns saja"
    res = maybe_record_friction_decision(prompt, session_id="test_sharpshooter_sess")
    assert res is not None
    assert res["admitted"] is True
    assert res["kind"] == "correction"

    # Verify that ADR was recorded into SQLite
    adrs = episodic_adr_manager.get_recent_project_adrs(limit=5, session_id="test_sharpshooter_sess")
    matching = [a for a in adrs if "moment" in a.get("architecture_decision", "")]
    assert len(matching) > 0
