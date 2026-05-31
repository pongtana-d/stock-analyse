"""Analysis endpoints — trigger AI analysis pipeline, query history."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    AnalysisRecord,
    AnalysisRunResponse,
    AnalysisRunSummary,
)
from app.repositories import analysis_repo, config_repo, portfolio_repo
from app.services import ai_analysis, calendar as market_calendar, discord
from app.services.indicators import compile_indicators
from app.services.yahoo import fetch_ohlcv

logger = logging.getLogger(__name__)
router = APIRouter()

TIMEFRAMES = ("weekly", "daily", "4h", "1h")

# Recent OHLCV bars per timeframe handed to the AI for chart-pattern /
# divergence inference and price-action context.
_OHLC_BARS_FOR_AI = 30


def _format_ohlc(df, tf: str) -> list[dict[str, Any]]:
    """Serialize the last N OHLCV bars for the AI payload."""
    recent = df.iloc[-_OHLC_BARS_FOR_AI:]
    intraday = tf in ("4h", "1h")
    bars: list[dict[str, Any]] = []
    for idx, row in recent.iterrows():
        bars.append(
            {
                "date": idx.strftime("%Y-%m-%d %H:%M") if intraday else idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
        )
    return bars


async def _gather_indicators(ticker: str) -> dict[str, Any]:
    """Fetch indicators + recent OHLCV + current price for the AI prompt."""
    payload: dict[str, Any] = {
        "ticker": ticker,
        "currentPrice": None,
        "indicators": {},
        "ohlc": {},
    }

    async def fetch_tf(tf: str):
        try:
            df = await asyncio.to_thread(fetch_ohlcv, ticker, tf, 120)
            if df.empty:
                return tf, None, None
            return tf, compile_indicators(df), df
        except Exception as exc:
            logger.warning("Failed to fetch %s %s: %s", ticker, tf, exc)
            return tf, None, None

    results = await asyncio.gather(*[fetch_tf(tf) for tf in TIMEFRAMES])
    last_closes: dict[str, float] = {}
    for tf, ind, df in results:
        if ind is None or df is None:
            continue
        payload["indicators"][tf] = ind.model_dump()
        payload["ohlc"][tf] = _format_ohlc(df, tf)
        last_closes[tf] = round(float(df["Close"].iloc[-1]), 2)

    # Current price: prefer the most granular timeframe available.
    for tf in ("1h", "4h", "daily", "weekly"):
        if tf in last_closes:
            payload["currentPrice"] = last_closes[tf]
            break
    return payload


async def _analyze_one(
    ticker: str, model: str, prompt: str, send_discord: bool = False
) -> AnalysisRunSummary:
    when = datetime.now(timezone.utc).isoformat()
    try:
        indicators = await _gather_indicators(ticker)
        if not indicators["indicators"]:
            raise RuntimeError("no indicator data available")

        result = await ai_analysis.analyze_stock(
            ticker=ticker,
            indicators_data=indicators,
            model=model,
            system_prompt=prompt,
        )
        signal = result["signal"]
        confidence = result["confidence"]
        content = result["content"]

        await analysis_repo.save_analysis(
            ticker=ticker,
            ai_model=model,
            system_prompt=prompt,
            indicator_data=indicators,
            ai_response=content,
            signal=signal,
            confidence=confidence,
            analysis_date=when,
        )

        if send_discord and discord.is_configured():
            discord_msg = ai_analysis.format_for_discord(
                ticker=ticker,
                content=content,
                signal=signal,
                analysis_date=when,
            )
            await discord.send_dm(discord_msg)

        return AnalysisRunSummary(
            ticker=ticker,
            signal=signal,
            confidence=confidence,
            analysis_date=when,
        )
    except Exception as exc:
        logger.exception("Analysis failed for %s", ticker)
        return AnalysisRunSummary(
            ticker=ticker,
            analysis_date=when,
            error=str(exc),
        )


async def execute_portfolio_run(
    *, force: bool = False, send_discord: bool = True
) -> AnalysisRunResponse:
    """Run AI analysis for every portfolio ticker.

    Shared by the manual API endpoint and the in-app scheduler. When the SET
    is closed and ``force`` is False, returns an empty result with
    ``market_open=False`` instead of raising.
    """
    triggered_at = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date()

    try:
        open_today = market_calendar.is_trading_day(today)
    except Exception as exc:
        logger.warning("calendar check failed: %s", exc)
        open_today = True  # fail open

    if not open_today and not force:
        return AnalysisRunResponse(
            triggered_at=triggered_at, market_open=False, results=[]
        )

    tickers = await portfolio_repo.get_all()
    if not tickers:
        return AnalysisRunResponse(
            triggered_at=triggered_at, market_open=open_today, results=[]
        )

    model = ai_analysis.get_ai_model()
    prompt = ai_analysis.load_system_prompt()

    # Run sequentially to avoid overwhelming AI provider + yfinance
    results: list[AnalysisRunSummary] = []
    for ticker in tickers:
        results.append(await _analyze_one(ticker, model, prompt, send_discord=send_discord))

    return AnalysisRunResponse(
        triggered_at=triggered_at, market_open=open_today, results=results
    )


@router.post("/analysis/run", response_model=AnalysisRunResponse)
async def run_analysis(
    force: bool = Query(default=False, description="Skip trading-day check"),
    send_discord: bool = Query(default=True, description="Send notifications to Discord"),
) -> AnalysisRunResponse:
    today = datetime.now(timezone.utc).date()
    try:
        open_today = market_calendar.is_trading_day(today)
    except Exception as exc:
        logger.warning("calendar check failed: %s", exc)
        open_today = True

    if not open_today and not force:
        raise HTTPException(
            status_code=409,
            detail="SET is not open today; pass force=true to run anyway.",
        )

    return await execute_portfolio_run(force=force, send_discord=send_discord)


@router.post("/analysis/run/{ticker}", response_model=AnalysisRunSummary)
async def run_analysis_single(
    ticker: str,
    send_discord: bool = Query(default=False, description="Send notifications to Discord"),
) -> AnalysisRunSummary:
    ticker = ticker.strip().upper()
    model = ai_analysis.get_ai_model()
    prompt = ai_analysis.load_system_prompt()
    return await _analyze_one(ticker, model, prompt, send_discord=send_discord)


@router.get("/analysis/history", response_model=list[AnalysisRecord])
async def get_history(
    ticker: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[AnalysisRecord]:
    rows = await analysis_repo.get_analysis(
        ticker=ticker.upper() if ticker else None,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return [AnalysisRecord(**row) for row in rows]


@router.delete("/analysis/history")
async def purge_history(
    older_than_days: int | None = Query(default=None, ge=0),
) -> dict[str, int]:
    if older_than_days is None:
        raw = await config_repo.get_config("history_retention_days")
        older_than_days = int(raw) if raw else 90
    deleted = await analysis_repo.delete_old_analysis(older_than_days)
    return {"deleted": deleted, "older_than_days": older_than_days}
