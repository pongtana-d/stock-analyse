"""Fibonacci Retracement levels (38.2%, 50%, 61.8%) from recent swing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.models.schemas import FibonacciData

# Use last N bars to find swing high/low (avoids all-time range)
_SWING_LOOKBACK: int = 50


def _find_swing_high(highs: np.ndarray, order: int = 5) -> tuple[float, int] | None:
    """Find most recent swing high (local max with `order` bars on each side)."""
    for i in range(len(highs) - 1 - order, order - 1, -1):
        if all(highs[i] >= highs[i - order : i]) and all(highs[i] >= highs[i + 1 : i + 1 + order]):
            return float(highs[i]), i
    return None


def _find_swing_low(lows: np.ndarray, order: int = 5) -> tuple[float, int] | None:
    """Find most recent swing low (local min with `order` bars on each side)."""
    for i in range(len(lows) - 1 - order, order - 1, -1):
        if all(lows[i] <= lows[i - order : i]) and all(lows[i] <= lows[i + 1 : i + 1 + order]):
            return float(lows[i]), i
    return None


def calculate_fibonacci(df: pd.DataFrame) -> FibonacciData:
    if len(df) < 10:
        return FibonacciData()

    # Use last N bars for swing detection
    lookback = min(_SWING_LOOKBACK, len(df))
    recent = df.iloc[-lookback:]

    highs = recent["High"].values
    lows = recent["Low"].values

    swing_high_result = _find_swing_high(highs)
    swing_low_result = _find_swing_low(lows)

    # Fallback to simple max/min of lookback window if no swing found
    if swing_high_result is None:
        swing_high_price = float(highs.max())
        swing_high_idx = lookback - 1
    else:
        swing_high_price, swing_high_idx = swing_high_result

    if swing_low_result is None:
        swing_low_price = float(lows.min())
        swing_low_idx = 0
    else:
        swing_low_price, swing_low_idx = swing_low_result

    # Determine trend based on index positions
    # If swing_high comes AFTER swing_low → bullish (uptrend pullback)
    # If swing_low comes AFTER swing_high → bearish (downtrend pullback)
    trend = "bullish" if swing_high_idx > swing_low_idx else "bearish"

    diff = swing_high_price - swing_low_price
    if diff == 0:
        return FibonacciData()

    if trend == "bullish":
        # Uptrend pullback: measure DOWN from swing_high
        # 38.2% = shallow pullback (near high), 61.8% = deep pullback (near low)
        return FibonacciData(
            trend=trend,
            level_382=round(swing_high_price - diff * 0.382, 2),
            level_50=round(swing_high_price - diff * 0.5, 2),
            level_618=round(swing_high_price - diff * 0.618, 2),
        )
    else:
        # Downtrend pullback: measure UP from swing_low
        # 38.2% = shallow bounce (near low), 61.8% = deep bounce (near high)
        return FibonacciData(
            trend=trend,
            level_382=round(swing_low_price + diff * 0.382, 2),
            level_50=round(swing_low_price + diff * 0.5, 2),
            level_618=round(swing_low_price + diff * 0.618, 2),
        )
