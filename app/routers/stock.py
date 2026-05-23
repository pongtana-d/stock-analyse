"""GET /api/stock/{ticker} — technical indicators + OHLCV."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import OHLCVBar, StockResponse
from app.services.indicators import compile_indicators
from app.services.yahoo import fetch_ohlcv

router = APIRouter()

DEFAULT_TIMEFRAMES = "weekly,daily,4h,1h"


@router.get("/stock/{ticker}")
async def get_stock(
    ticker: str,
    timeframes: str = Query(default=DEFAULT_TIMEFRAMES),
    period: int = Query(default=120, ge=1, le=500),
):
    tf_list = [t.strip() for t in timeframes.split(",")]
    valid_tfs = {"weekly", "daily", "4h", "1h"}
    for tf in tf_list:
        if tf not in valid_tfs:
            raise HTTPException(status_code=400, detail=f"Invalid timeframe: {tf}")

    indicators: dict = {}
    ohlc: dict = {}

    async def fetch_tf(tf: str):
        """Fetch and validate OHLCV for a single timeframe."""
        try:
            df = await asyncio.to_thread(fetch_ohlcv, ticker, tf, period=period)
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"Failed to fetch data for {ticker} ({tf}): {e}"
            )
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {ticker} on timeframe {tf}",
            )
        return tf, df

    # Fetch all timeframes concurrently
    results = await asyncio.gather(*[fetch_tf(tf) for tf in tf_list])

    for tf, df in results:
        indicators[tf] = compile_indicators(df)
        ohlc[tf] = [
            OHLCVBar(
                date=idx.strftime("%Y-%m-%d %H:%M") if tf in ("4h", "1h") else idx.strftime("%Y-%m-%d"),
                open=round(float(row["Open"]), 2),
                high=round(float(row["High"]), 2),
                low=round(float(row["Low"]), 2),
                close=round(float(row["Close"]), 2),
                volume=int(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]

    response = StockResponse(
        ticker=ticker,
        timestamp=datetime.now(timezone.utc).isoformat(),
        indicators=indicators,
        ohlc=ohlc,
    )

    return response.model_dump()
