"""MACD (12,26,9) + crossover detection."""

from __future__ import annotations

import math
import talib
import pandas as pd

from app.models.schemas import MACDData


def calculate_macd(df: pd.DataFrame) -> MACDData:
    close = df["Close"].values

    if len(close) < 26:
        return MACDData()

    macd, signal, histogram = talib.MACD(
        close, fastperiod=12, slowperiod=26, signalperiod=9
    )

    macd_val = float(macd[-1])
    signal_val = float(signal[-1])
    hist_val = float(histogram[-1])

    if math.isnan(macd_val) or math.isnan(signal_val) or math.isnan(hist_val):
        return MACDData()

    # Crossover detection: compare last 2 bars
    crossover = None
    if len(histogram) >= 2:
        prev_hist = float(histogram[-2])
        if prev_hist <= 0 < hist_val:
            crossover = "bullish"
        elif prev_hist >= 0 > hist_val:
            crossover = "bearish"

    return MACDData(
        macd=round(macd_val, 4),
        signal=round(signal_val, 4),
        histogram=round(hist_val, 4),
        crossover=crossover,
    )
