"""LiteLLM-powered AI analysis pipeline."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

AGENTS_MD_PATH = Path(__file__).resolve().parent.parent.parent / "AGENTS.md"

_SIGNAL_RE = re.compile(
    r"SIGNAL\s*[:\-]\s*(BUY ON DIP|TAKE PROFIT|REDUCE|BUY|SELL|HOLD)",
    re.IGNORECASE,
)
_CONFIDENCE_RE = re.compile(r"Confidence\s*[:\-]\s*(High|Medium|Low)", re.IGNORECASE)


def get_ai_model() -> str:
    """Resolve the AI model from env or default."""
    return os.getenv("LITELLM_MODEL") or "openai/gpt-4o"


def get_ai_api_url() -> str | None:
    return os.getenv("AI_API_URL") or None


def get_ai_api_key() -> str | None:
    return (
        os.getenv("AI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LITELLM_API_KEY")
    ) or None


def load_system_prompt() -> str:
    """Load AGENTS.md as the system prompt for the AI."""
    if AGENTS_MD_PATH.exists():
        return AGENTS_MD_PATH.read_text(encoding="utf-8")
    return "You are เซ็ตจัง (Set-chan), a SET stock technical analyst."


def parse_signal(text: str) -> tuple[str | None, str | None]:
    """Extract SIGNAL + Confidence from AI response text."""
    signal = None
    confidence = None
    m = _SIGNAL_RE.search(text)
    if m:
        signal = m.group(1).upper()
    m = _CONFIDENCE_RE.search(text)
    if m:
        confidence = m.group(1).capitalize()
    return signal, confidence


async def analyze_stock(
    *,
    ticker: str,
    indicators_data: dict[str, Any],
    model: str,
    system_prompt: str | None = None,
) -> str:
    """Call LiteLLM with the indicator payload and return the AI's text response."""
    from litellm import acompletion  # local import to keep startup light

    prompt = system_prompt or load_system_prompt()
    user_content = (
        f"วิเคราะห์หุ้น {ticker} จากข้อมูล technical indicators ต่อไปนี้ "
        f"(JSON):\n\n```json\n"
        f"{json.dumps(indicators_data, ensure_ascii=False, default=str)}\n```\n\n"
        f"ตอบในรูปแบบที่กำหนดใน AGENTS.md (VERDICT + WHY + CAVEATS) เป็นภาษาไทย."
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]

    extra: dict[str, Any] = {}
    api_key = (
        os.getenv("AI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LITELLM_API_KEY")
    )
    if api_key:
        extra["api_key"] = api_key
    api_base = os.getenv("AI_API_URL")
    if api_base:
        extra["api_base"] = api_base
        # Custom base URL = OpenAI-compatible endpoint
        extra["custom_llm_provider"] = "openai"

    response = await acompletion(model=model, messages=messages, **extra)
    try:
        return response["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, TypeError, IndexError) as exc:
        logger.error("Unexpected litellm response shape: %s", exc)
        return str(response)


def format_for_discord(
    *,
    ticker: str,
    ai_response: str,
    signal: str | None,
    confidence: str | None,
) -> dict[str, Any]:
    """Build a Discord embed dict from the AI verdict."""
    color_map = {
        "BUY": 0x2ECC71,
        "BUY ON DIP": 0x27AE60,
        "SELL": 0xE74C3C,
        "TAKE PROFIT": 0xF1C40F,
        "REDUCE": 0xE67E22,
        "HOLD": 0x95A5A6,
    }
    color = color_map.get(signal or "", 0x3498DB)

    description = ai_response.strip()
    if len(description) > 4000:
        description = description[:3997] + "..."

    return {
        "title": f"{ticker} — SET Analyze",
        "description": description,
        "color": color,
    }
