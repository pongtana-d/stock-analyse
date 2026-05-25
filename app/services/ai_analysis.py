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

# Regex to extract fenced JSON code block from AI response
_JSON_BLOCK_RE = re.compile(r"```json\s*\n(\{.*?\})\s*\n```", re.DOTALL)

# Legacy regex fallback for old-format responses
_SIGNAL_RE = re.compile(
    r"SIGNAL[\s\*]*[:\-][\s\*]*(BUY ON DIP|TAKE PROFIT|REDUCE|BUY|SELL|HOLD)",
    re.IGNORECASE,
)
_CONFIDENCE_RE = re.compile(
    r"Confidence[\s\*]*[:\-][\s\*]*(High|Medium|Low)",
    re.IGNORECASE,
)

_VALID_SIGNALS = {"BUY", "SELL", "HOLD", "BUY ON DIP", "TAKE PROFIT", "REDUCE"}
_VALID_CONFIDENCES = {"High", "Medium", "Low"}


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


def parse_ai_response(text: str) -> dict[str, Any]:
    """Parse AI response into structured metadata dict + analysis markdown.

    Returns dict with keys:
        - signal: str | None
        - confidence: str | None
        - verdict: dict | None  (full JSON verdict block)
        - analysis: str  (markdown content after JSON block)
    """
    result: dict[str, Any] = {
        "signal": None,
        "confidence": None,
        "verdict": None,
        "analysis": text,  # fallback: entire text
    }

    # Try to extract JSON block
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            verdict = json.loads(m.group(1))
            result["verdict"] = verdict

            # Extract and validate signal
            raw_signal = str(verdict.get("signal", "")).upper().strip()
            if raw_signal in _VALID_SIGNALS:
                result["signal"] = raw_signal

            # Extract and validate confidence
            raw_conf = str(verdict.get("confidence", "")).strip().capitalize()
            if raw_conf in _VALID_CONFIDENCES:
                result["confidence"] = raw_conf

            # Extract analysis markdown (everything after the JSON block)
            after_json = text[m.end():].strip()
            result["analysis"] = after_json if after_json else text

        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse JSON verdict block: %s", exc)
    else:
        # Legacy fallback: try regex parsing for old-format responses
        logger.info("No JSON block found in AI response, falling back to regex")
        sig_m = _SIGNAL_RE.search(text)
        if sig_m:
            result["signal"] = sig_m.group(1).upper()
        conf_m = _CONFIDENCE_RE.search(text)
        if conf_m:
            result["confidence"] = conf_m.group(1).capitalize()

    return result


def format_readable_content(verdict: dict[str, Any] | None, analysis: str) -> str:
    """Combine verdict data + analysis markdown into human-readable content.

    This is what gets stored in DB (ai_response) and sent to Discord.
    No raw JSON block — just readable text.
    """
    parts: list[str] = []

    if verdict:
        signal = verdict.get("signal", "")
        confidence = verdict.get("confidence", "")
        horizon = verdict.get("horizon", "")

        # Header line
        if signal:
            parts.append(f"**SIGNAL: {signal}**")
        if confidence:
            parts.append(f"**Confidence: {confidence}**")

        # Details line
        details: list[str] = []
        if horizon:
            details.append(f"Horizon: {horizon}")
        rr = verdict.get("rr")
        if rr:
            details.append(f"R:R {rr}")
        if details:
            parts.append(" | ".join(details))

        # Entry/Target/Stop or Watch/Invalidation
        if "entry" in verdict:
            entry_line = []
            if verdict.get("entry") is not None:
                entry_line.append(f"Entry: {verdict['entry']}")
            if verdict.get("target") is not None:
                entry_line.append(f"Target: {verdict['target']}")
            if verdict.get("stop") is not None:
                entry_line.append(f"Stop: {verdict['stop']}")
            if entry_line:
                parts.append(" | ".join(entry_line))
        elif "watch" in verdict:
            watch_line = []
            if verdict.get("watch") is not None:
                watch_line.append(f"Watch: {verdict['watch']}")
            if verdict.get("invalidation") is not None:
                watch_line.append(f"Invalidation: {verdict['invalidation']}")
            if watch_line:
                parts.append(" | ".join(watch_line))

        # Supports / Resistances
        supports = verdict.get("supports")
        if supports:
            parts.append(f"Supports: {', '.join(str(s) for s in supports)}")
        resistances = verdict.get("resistances")
        if resistances:
            parts.append(f"Resistances: {', '.join(str(r) for r in resistances)}")

        # Catalyst
        catalyst = verdict.get("catalyst")
        if catalyst:
            parts.append(f"Catalyst: {catalyst}")

    # Join verdict lines with markdown hard line break (2 spaces + \n)
    # so each line renders separately in the browser
    verdict_text = "  \n".join(parts) if parts else ""

    # Add analysis markdown with blank line separator
    if analysis and analysis.strip():
        if verdict_text:
            return verdict_text + "\n\n" + analysis.strip()
        return analysis.strip()

    return verdict_text


async def analyze_stock(
    *,
    ticker: str,
    indicators_data: dict[str, Any],
    model: str,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    """Call LiteLLM and return parsed structured response.

    Returns dict with keys:
        - signal: str | None
        - confidence: str | None
        - verdict: dict | None  (full JSON verdict)
        - analysis: str  (markdown analysis text)
        - raw_response: str  (original AI text)
    """
    from litellm import acompletion  # local import to keep startup light

    prompt = system_prompt or load_system_prompt()
    user_content = (
        f"วิเคราะห์หุ้น {ticker} จากข้อมูล technical indicators ต่อไปนี้ "
        f"(JSON):\n\n```json\n"
        f"{json.dumps(indicators_data, ensure_ascii=False, default=str)}\n```\n\n"
        f"ตอบตามรูปแบบที่กำหนดใน AGENTS.md: "
        f"1) JSON verdict block ใน ```json ... ``` "
        f"2) ตามด้วย markdown analysis (WHY + CAVEATS) เป็นภาษาไทย."
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

    # Pass reasoning_split=True to MiniMax model to separate thoughts into reasoning_details
    if "minimax" in model.lower() or (api_base and "minimax" in api_base.lower()):
        extra["extra_body"] = {"reasoning_split": True}

    response = await acompletion(model=model, messages=messages, **extra)
    try:
        raw_text = response["choices"][0]["message"]["content"]  # type: ignore[index]
    except (KeyError, TypeError, IndexError) as exc:
        logger.error("Unexpected litellm response shape: %s", exc)
        raw_text = str(response)

    parsed = parse_ai_response(raw_text)
    parsed["raw_response"] = raw_text
    parsed["content"] = format_readable_content(
        parsed.get("verdict"), parsed.get("analysis", "")
    )
    return parsed


def format_for_discord(
    *,
    ticker: str,
    content: str,
    signal: str | None,
    analysis_date: str | None = None,
) -> str:
    """Build a Discord plain text message from formatted content."""
    title = f"{ticker} — SET Analyze"
    if analysis_date:
        try:
            from datetime import datetime, timezone, timedelta
            clean_val = analysis_date.strip().replace(" ", "T")
            dt = datetime.fromisoformat(clean_val)
            # Convert to UTC+7 (Asia/Bangkok)
            bangkok_tz = timezone(timedelta(hours=7))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(bangkok_tz)

            months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_name = months[dt.month]
            date_str = f"{dt.day} {month_name} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"
            title = f"{ticker} — SET Analyze ({date_str})"
        except Exception as exc:
            logger.warning("Failed to parse analysis_date for Discord title: %s", exc)

    message = f"## {title}\n\n{content.strip()}"
    if len(message) > 2000:
        message = message[:1997] + "..."

    return message
