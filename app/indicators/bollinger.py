"""Bollinger Bands (20,2) + bandwidth."""

from __future__ import annotations

import math
import talib
import pandas as pd

from app.models.schemas import BollingerData


def calculate_bollinger(df: pd.DataFrame) -> BollingerData:
    close = df["Close"].values

    if len(close) < 20:
        return BollingerData()
    upper, middle, lower = talib.BBANDS(
        close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0
    )

    upper_val = float(upper[-1])
    middle_val = float(middle[-1])
    lower_val = float(lower[-1])

    if math.isnan(upper_val) or math.isnan(middle_val) or math.isnan(lower_val):
        return BollingerData()

    bandwidth = (upper_val - lower_val) / middle_val if middle_val != 0 else 0

    return BollingerData(
        upper=round(upper_val, 2),
        middle=round(middle_val, 2),
        lower=round(lower_val, 2),
        bandwidth=round(bandwidth, 4),
    )
