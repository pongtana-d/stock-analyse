"""RSI (14) — last value + series for divergence detection."""

from __future__ import annotations

import math

import talib
import pandas as pd

from app.models.schemas import RSIData, RSIPoint

_SERIES_BARS: int = 30  # bars of RSI history to expose for divergence reading


def _format_date(ts) -> str:
    if hasattr(ts, "hour") and ts.hour != 0:
        return ts.strftime("%Y-%m-%d %H:%M")
    return ts.strftime("%Y-%m-%d")


def calculate_rsi(df: pd.DataFrame) -> RSIData:
    close = df["Close"].values

    if len(close) < 14:
        return RSIData()

    rsi = talib.RSI(close, timeperiod=14)
    val = float(rsi[-1])

    if math.isnan(val):
        return RSIData()

    # Build series (skip leading NaN bars from RSI warm-up)
    dates = df.index
    start = max(0, len(rsi) - _SERIES_BARS)
    series: list[RSIPoint] = []
    for i in range(start, len(rsi)):
        v = float(rsi[i])
        if not math.isnan(v):
            series.append(RSIPoint(date=_format_date(dates[i]), value=round(v, 2)))

    return RSIData(value=round(val, 2), series=series)
