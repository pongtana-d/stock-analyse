"""Tests for AI analysis helpers (no live LLM call)."""

from __future__ import annotations

import pytest

from app.services import ai_analysis


@pytest.mark.parametrize("text, signal, confidence", [
    ("SIGNAL: BUY | Confidence: High", "BUY", "High"),
    ("SIGNAL: BUY ON DIP\nConfidence: Medium", "BUY ON DIP", "Medium"),
    ("signal: sell  confidence: low", "SELL", "Low"),
    ("no signal here", None, None),
])
def test_parse_signal(text, signal, confidence):
    s, c = ai_analysis.parse_signal(text)
    assert s == signal
    assert c == confidence


def test_format_for_discord_truncates_and_sets_color():
    embed = ai_analysis.format_for_discord(
        ticker="CPF.BK",
        ai_response="x" * 5000,
        signal="BUY",
        confidence="High",
    )
    assert embed["title"].startswith("CPF.BK")
    assert embed["color"] == 0x2ECC71
    assert len(embed["description"]) <= 4000


def test_format_for_discord_unknown_signal_default_color():
    embed = ai_analysis.format_for_discord(
        ticker="X.BK", ai_response="hi", signal=None, confidence=None
    )
    assert embed["color"] == 0x3498DB
