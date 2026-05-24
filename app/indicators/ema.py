"""EMA 20/50/200 calculation."""

from __future__ import annotations

import math
import talib
import pandas as pd

from app.models.schemas import EMAData


def calculate_ema(df: pd.DataFrame) -> EMAData:
    close = df["Close"].values
    result = EMAData()

    if len(close) >= 20:
        ema20 = talib.EMA(close, timeperiod=20)
        val = float(ema20[-1])
        if not math.isnan(val):
            result.ema20 = round(val, 2)

    if len(close) >= 50:
        ema50 = talib.EMA(close, timeperiod=50)
        val = float(ema50[-1])
        if not math.isnan(val):
            result.ema50 = round(val, 2)

    if len(close) >= 200:
        ema200 = talib.EMA(close, timeperiod=200)
        val = float(ema200[-1])
        if not math.isnan(val):
            result.ema200 = round(val, 2)

    return result
