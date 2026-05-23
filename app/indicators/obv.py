"""OBV + trend direction + volume vs moving average."""

from __future__ import annotations

import talib
import numpy as np
import pandas as pd

from app.models.schemas import VolumeData


def calculate_obv(df: pd.DataFrame) -> VolumeData:
    close = df["Close"].values
    volume = df["Volume"].values.astype(float)

    if len(close) < 2:
        return VolumeData()

    obv = talib.OBV(close, volume)
    obv_val = float(obv[-1])

    # OBV trend: compare OBV EMA(20) slope over last 5 bars
    obv_trend = "flat"
    if len(obv) >= 20:
        obv_ema = talib.EMA(obv, timeperiod=20)
        if len(obv_ema) >= 5:
            recent = obv_ema[-5:]
            slope = float(recent[-1] - recent[0])
            if slope > 0:
                obv_trend = "rising"
            elif slope < 0:
                obv_trend = "falling"

    # Recent volume vs 20-period average
    recent_vs_avg = None
    if len(volume) >= 20:
        vol_ma = float(np.mean(volume[-20:]))
        if vol_ma > 0:
            recent_vs_avg = round(float(volume[-1]) / vol_ma, 2)

    return VolumeData(
        obv=round(obv_val, 0),
        obvTrend=obv_trend,
        recentVsAvg=recent_vs_avg,
    )
