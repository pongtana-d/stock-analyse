"""Candlestick pattern detection using TA-Lib.

Scans the last 5 bars for 19 common patterns across single, two, and
three-candle formations.  TA-Lib returns per-bar integers:
    0   → no pattern
    +100 → bullish
    -100 → bearish

Results are sorted most-recent-first so AI consumers see the latest
signals without scanning the whole list.
"""

from __future__ import annotations

import talib
import pandas as pd

from app.models.schemas import CandlestickData, CandlestickPattern
from app.indicators import format_indicator_date

# ── Pattern definitions ──────────────────────────────────────────────
# Each entry: (display_name, ta-lib_function)
_PATTERNS: list[tuple[str, object]] = [
    # Single-candle
    ("Doji", talib.CDLDOJI),
    ("Dragonfly Doji", talib.CDLDRAGONFLYDOJI),
    ("Gravestone Doji", talib.CDLGRAVESTONEDOJI),
    ("Hammer", talib.CDLHAMMER),
    ("Hanging Man", talib.CDLHANGINGMAN),
    ("Inverted Hammer", talib.CDLINVERTEDHAMMER),
    ("Shooting Star", talib.CDLSHOOTINGSTAR),
    ("Spinning Top", talib.CDLSPINNINGTOP),
    ("Marubozu", talib.CDLMARUBOZU),
    # Two-candle
    ("Engulfing", talib.CDLENGULFING),
    ("Harami", talib.CDLHARAMI),
    ("Piercing Line", talib.CDLPIERCING),
    ("Dark Cloud Cover", talib.CDLDARKCLOUDCOVER),
    # Three-candle
    ("Morning Star", talib.CDLMORNINGSTAR),
    ("Evening Star", talib.CDLEVENINGSTAR),
    ("Three White Soldiers", talib.CDL3WHITESOLDIERS),
    ("Three Black Crows", talib.CDL3BLACKCROWS),
    ("Three Inside", talib.CDL3INSIDE),
    ("Three Outside", talib.CDL3OUTSIDE),
]

# How many recent bars to scan (keeps output compact & relevant)
_SCAN_WINDOW = 5


def calculate_candlestick(df: pd.DataFrame) -> CandlestickData:
    """Detect candlestick patterns in the most recent bars."""
    o = df["Open"].values.astype(float)
    h = df["High"].values.astype(float)
    l = df["Low"].values.astype(float)
    c = df["Close"].values.astype(float)
    dates = df.index

    if len(c) < 10:
        return CandlestickData()

    detected: list[CandlestickPattern] = []

    for name, func in _PATTERNS:
        try:
            result = func(o, h, l, c)
        except Exception:
            continue

        scan_start = max(0, len(result) - _SCAN_WINDOW)
        for i in range(scan_start, len(result)):
            val = int(result[i])
            if val == 0:
                continue

            direction = "bullish" if val > 0 else "bearish"
            bars_ago = len(result) - 1 - i

            detected.append(
                CandlestickPattern(
                    name=name,
                    date=format_indicator_date(dates[i]),
                    direction=direction,
                    barsAgo=bars_ago,
                )
            )

    # Most recent first; bearish alerts before bullish at same age
    detected.sort(key=lambda p: (p.barsAgo, 0 if p.direction == "bearish" else 1))

    return CandlestickData(patterns=detected)
