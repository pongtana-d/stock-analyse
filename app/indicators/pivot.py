"""Pivot Points (Classic) calculation."""

from __future__ import annotations

import pandas as pd

from app.models.schemas import PivotData


def calculate_pivot(df: pd.DataFrame) -> PivotData:
    # Classic pivots project the next period's levels from the PREVIOUS
    # completed bar's HLC. The current bar may still be forming.
    if len(df) < 2:
        return PivotData()

    bar = df.iloc[-2]

    high = float(bar["High"])
    low = float(bar["Low"])
    close = float(bar["Close"])

    pp = (high + low + close) / 3
    r1 = 2 * pp - low
    r2 = pp + (high - low)
    s1 = 2 * pp - high
    s2 = pp - (high - low)

    return PivotData(
        pp=round(pp, 2),
        r1=round(r1, 2),
        r2=round(r2, 2),
        s1=round(s1, 2),
        s2=round(s2, 2),
    )
