"""Compile all indicators for a given OHLCV DataFrame."""

from __future__ import annotations

import pandas as pd

from app.indicators.bollinger import calculate_bollinger
from app.indicators.candlestick import calculate_candlestick
from app.indicators.ema import calculate_ema
from app.indicators.fibonacci import calculate_fibonacci
from app.indicators.macd import calculate_macd
from app.indicators.obv import calculate_obv
from app.indicators.pivot import calculate_pivot
from app.indicators.rsi import calculate_rsi
from app.indicators.swing import calculate_swing_points
from app.models.schemas import TimeframeIndicators


def compile_indicators(df: pd.DataFrame) -> TimeframeIndicators:
    """Run all indicator calculations on the given DataFrame."""
    return TimeframeIndicators(
        ema=calculate_ema(df),
        macd=calculate_macd(df),
        rsi=calculate_rsi(df),
        bollingerBands=calculate_bollinger(df),
        volume=calculate_obv(df),
        pivotPoints=calculate_pivot(df),
        fibonacci=calculate_fibonacci(df),
        candlestick=calculate_candlestick(df),
        swingPoints=calculate_swing_points(df),
    )
