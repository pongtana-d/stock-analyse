"""Swing point sequence detection for market structure analysis (HH/HL/LH/LL).

Scans the last N bars and returns an ordered list of swing highs and lows
so the AI agent can infer trend structure without scanning raw OHLCV.

Output is sorted oldest → newest so the agent reads left-to-right like a chart.
"""

from __future__ import annotations

import pandas as pd

from app.models.schemas import SwingData, SwingPoint

_LOOKBACK: int = 100   # bars to scan for swings
_ORDER: int = 5        # bars on each side required to qualify as a swing
_MAX_POINTS: int = 10  # max swing points returned (keep context window small)


def _format_date(ts) -> str:
    if hasattr(ts, "hour") and ts.hour != 0:
        return ts.strftime("%Y-%m-%d %H:%M")
    return ts.strftime("%Y-%m-%d")


def calculate_swing_points(df: pd.DataFrame) -> SwingData:
    """Detect alternating swing highs and lows, return oldest-to-newest."""
    min_bars = _ORDER * 2 + 1
    if len(df) < min_bars:
        return SwingData()

    lookback = min(_LOOKBACK, len(df))
    recent = df.iloc[-lookback:]

    highs = recent["High"].values
    lows = recent["Low"].values
    dates = recent.index

    raw: list[tuple[int, SwingPoint]] = []

    # Detect all swing highs
    for i in range(_ORDER, len(highs) - _ORDER):
        if all(highs[i] >= highs[i - _ORDER : i]) and all(
            highs[i] >= highs[i + 1 : i + 1 + _ORDER]
        ):
            raw.append(
                (i, SwingPoint(
                    date=_format_date(dates[i]),
                    price=round(float(highs[i]), 2),
                    type="high",
                ))
            )

    # Detect all swing lows
    for i in range(_ORDER, len(lows) - _ORDER):
        if all(lows[i] <= lows[i - _ORDER : i]) and all(
            lows[i] <= lows[i + 1 : i + 1 + _ORDER]
        ):
            raw.append(
                (i, SwingPoint(
                    date=_format_date(dates[i]),
                    price=round(float(lows[i]), 2),
                    type="low",
                ))
            )

    # Sort by original index (oldest first) to avoid string format mixed issues
    raw.sort(key=lambda item: item[0])
    points = [item[1] for item in raw]
    
    return SwingData(points=points[-_MAX_POINTS:])
