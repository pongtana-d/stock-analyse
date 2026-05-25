"""Tests for AI analysis helpers (no live LLM call)."""

from __future__ import annotations

import pytest

from app.services import ai_analysis


# --- parse_ai_response: JSON format ---

class TestParseAiResponseJSON:
    def test_valid_buy_signal(self):
        text = '''```json
{
  "signal": "BUY",
  "confidence": "High",
  "horizon": "Swing",
  "entry": 12.40,
  "target": 13.80,
  "stop": 11.90,
  "rr": "1:2.8",
  "supports": [12.20, 11.90],
  "resistances": [12.80, 13.20],
  "catalyst": "RSI bullish divergence"
}
```

### WHY
- EMA20 > EMA50 > EMA200
- RSI bullish divergence at support
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "BUY"
        assert result["confidence"] == "High"
        assert result["verdict"] is not None
        assert result["verdict"]["entry"] == 12.40
        assert result["verdict"]["horizon"] == "Swing"
        assert "### WHY" in result["analysis"]

    def test_hold_signal(self):
        text = '''```json
{
  "signal": "HOLD",
  "confidence": "Medium",
  "horizon": "Swing",
  "watch": 5.50,
  "invalidation": 5.00,
  "supports": [5.20, 5.00],
  "resistances": [5.80, 6.00],
  "catalyst": "TF conflict"
}
```

### WHY
- Weekly bullish but Daily bearish
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "HOLD"
        assert result["confidence"] == "Medium"
        assert result["verdict"]["watch"] == 5.50

    def test_buy_on_dip(self):
        text = '''```json
{"signal": "BUY ON DIP", "confidence": "Low", "horizon": "Positional", "entry": 100, "target": 120, "stop": 95, "rr": "1:4", "supports": [100], "resistances": [120], "catalyst": "test"}
```

analysis here
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "BUY ON DIP"
        assert result["confidence"] == "Low"

    def test_take_profit(self):
        text = '''```json
{"signal": "TAKE PROFIT", "confidence": "High", "horizon": "Swing", "entry": 50, "target": 60, "stop": 48, "rr": "1:5", "supports": [], "resistances": [], "catalyst": "hit target"}
```
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "TAKE PROFIT"

    def test_reduce_signal(self):
        text = '''```json
{"signal": "REDUCE", "confidence": "Medium", "horizon": "Swing", "entry": 30, "target": 35, "stop": 28, "rr": "1:2.5", "supports": [28], "resistances": [35], "catalyst": "weakening momentum"}
```
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "REDUCE"

    def test_invalid_signal_value(self):
        text = '''```json
{"signal": "YOLO", "confidence": "High", "horizon": "Swing"}
```
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] is None
        assert result["confidence"] == "High"

    def test_invalid_confidence_value(self):
        text = '''```json
{"signal": "BUY", "confidence": "Super High", "horizon": "Swing"}
```
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "BUY"
        assert result["confidence"] is None

    def test_malformed_json(self):
        text = '''```json
{signal: BUY, confidence: High}
```
'''
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] is None
        assert result["confidence"] is None
        assert result["analysis"] == text  # fallback to full text

    def test_no_json_block(self):
        text = "This is just plain text without any JSON block"
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] is None
        assert result["confidence"] is None
        assert result["analysis"] == text


# --- parse_ai_response: legacy regex fallback ---

class TestParseAiResponseLegacy:
    def test_bold_markdown_format(self):
        text = "**SIGNAL**: HOLD | **Confidence**: High | **Horizon**: Swing"
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "HOLD"
        assert result["confidence"] == "High"
        assert result["verdict"] is None  # no JSON block

    def test_plain_text_format(self):
        text = "SIGNAL: BUY ON DIP\nConfidence: Medium"
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "BUY ON DIP"
        assert result["confidence"] == "Medium"

    def test_lowercase_format(self):
        text = "signal: sell  confidence: low"
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] == "SELL"
        assert result["confidence"] == "Low"

    def test_no_match(self):
        text = "no signal here"
        result = ai_analysis.parse_ai_response(text)
        assert result["signal"] is None
        assert result["confidence"] is None


# --- format_readable_content ---

class TestFormatReadableContent:
    def test_buy_verdict_with_analysis(self):
        verdict = {
            "signal": "BUY",
            "confidence": "High",
            "horizon": "Swing",
            "entry": 12.4,
            "target": 13.8,
            "stop": 11.9,
            "rr": "1:2.8",
            "supports": [12.2, 11.9],
            "resistances": [12.8, 13.2],
            "catalyst": "RSI bullish divergence",
        }
        analysis = "### WHY\n- EMA bullish\n- Volume spike"
        result = ai_analysis.format_readable_content(verdict, analysis)
        assert "**SIGNAL: BUY | Confidence: High**" in result
        assert "Horizon: Swing" in result
        assert "R:R 1:2.8" in result
        assert "Entry: 12.4" in result
        assert "Target: 13.8" in result
        assert "Stop: 11.9" in result
        assert "Supports: 12.2, 11.9" in result
        assert "Resistances: 12.8, 13.2" in result
        assert "Catalyst: RSI bullish divergence" in result
        assert "### WHY" in result
        assert "- EMA bullish" in result

    def test_hold_verdict_with_watch(self):
        verdict = {
            "signal": "HOLD",
            "confidence": "Medium",
            "horizon": "Swing",
            "watch": 5.50,
            "invalidation": 5.00,
            "supports": [5.20],
            "resistances": [5.80],
            "catalyst": "TF conflict",
        }
        result = ai_analysis.format_readable_content(verdict, "")
        assert "Watch: 5.5" in result
        assert "Invalidation: 5.0" in result
        assert "Entry" not in result

    def test_no_verdict_returns_analysis_only(self):
        result = ai_analysis.format_readable_content(None, "just analysis")
        assert result == "just analysis"

    def test_empty_verdict_and_analysis(self):
        result = ai_analysis.format_readable_content(None, "")
        assert result == ""

    def test_verdict_without_optional_fields(self):
        verdict = {"signal": "SELL", "confidence": "Low"}
        result = ai_analysis.format_readable_content(verdict, "")
        assert "**SIGNAL: SELL | Confidence: Low**" in result
        assert "Entry" not in result
        assert "Supports" not in result


# --- format_for_discord ---

def test_format_for_discord_truncates():
    msg = ai_analysis.format_for_discord(
        ticker="CPF.BK",
        content="x" * 5000,
        signal="BUY",
    )
    assert msg.startswith("## CPF.BK")
    assert len(msg) <= 2000


def test_format_for_discord_uses_content_directly():
    content = "**SIGNAL: SELL | Confidence: Medium**\nHorizon: Swing\n\n### WHY\n- test"
    msg = ai_analysis.format_for_discord(
        ticker="PTT.BK",
        content=content,
        signal="SELL",
    )
    assert "SIGNAL: SELL" in msg
    assert "Confidence: Medium" in msg
    # Content is used directly, not wrapped again
    assert msg.count("SIGNAL: SELL") == 1


def test_format_for_discord_includes_date_in_title():
    msg = ai_analysis.format_for_discord(
        ticker="KBANK.BK",
        content="analysis content",
        signal="BUY",
        analysis_date="2026-05-25T02:40:00Z"
    )
    # 2026-05-25T02:40:00Z in UTC -> 25 May 2026, 09:40 in Bangkok (UTC+7)
    assert "KBANK.BK — SET Analyze (25 May 2026, 09:40)" in msg




# --- analyze_stock parameters ---

@pytest.mark.asyncio
async def test_analyze_stock_adds_reasoning_split_for_minimax():
    from unittest.mock import AsyncMock, patch
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\"signal\": \"BUY\", \"confidence\": \"High\"}\n```\n### WHY\n- test"
                }
            }
        ]
    }
    
    with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)) as mock_acompletion:
        await ai_analysis.analyze_stock(
            ticker="CPF.BK",
            indicators_data={},
            model="Minimax-M2.7",
            system_prompt="test prompt"
        )
        args, kwargs = mock_acompletion.call_args
        assert kwargs.get("extra_body") == {"reasoning_split": True}
        assert kwargs.get("model") == "Minimax-M2.7"


@pytest.mark.asyncio
async def test_analyze_stock_no_reasoning_split_for_non_minimax(monkeypatch):
    from unittest.mock import AsyncMock, patch
    
    # Isolate from global environment
    monkeypatch.delenv("AI_API_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\"signal\": \"BUY\", \"confidence\": \"High\"}\n```\n### WHY\n- test"
                }
            }
        ]
    }
    
    with patch("litellm.acompletion", new=AsyncMock(return_value=mock_response)) as mock_acompletion:
        await ai_analysis.analyze_stock(
            ticker="CPF.BK",
            indicators_data={},
            model="openai/gpt-4o",
            system_prompt="test prompt"
        )
        args, kwargs = mock_acompletion.call_args
        assert "extra_body" not in kwargs or "reasoning_split" not in kwargs.get("extra_body", {})
