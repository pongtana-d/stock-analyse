"""yfinance wrapper — fetch & normalize OHLCV data per timeframe."""

from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

# yfinance interval mapping
_INTERVAL_MAP: dict[str, str] = {
    "weekly": "1wk",
    "daily": "1d",
    "4h": "1h",  # derive 4H from 1H data
    "1h": "1h",
}

# yfinance max period for each interval
_PERIOD_MAP: dict[str, str] = {
    "1wk": "5y",
    "1d": "1y",
    "1h": "730d",  # yfinance max for intraday
}

# Rate limiting — minimum seconds between yfinance requests
_FETCH_DELAY: float = 0.5
_last_fetch_time: float = 0.0

# Retry config
_MAX_RETRIES: int = 3
_RETRY_BACKOFF: float = 1.0  # seconds, doubles each retry
_FETCH_TIMEOUT: float = 30.0  # seconds


def _rate_limit() -> None:
    """Enforce minimum delay between yfinance requests."""
    global _last_fetch_time
    elapsed = time.monotonic() - _last_fetch_time
    if elapsed < _FETCH_DELAY:
        time.sleep(_FETCH_DELAY - elapsed)
    _last_fetch_time = time.monotonic()


def fetch_ohlcv(ticker: str, timeframe: str, period: int = 120) -> pd.DataFrame:
    """Fetch OHLCV data from yfinance and normalize columns.

    Returns DataFrame with columns: Open, High, Low, Close, Volume
    Index is DatetimeIndex.
    Includes rate limiting, retry with backoff, and timeout.
    """
    interval = _INTERVAL_MAP.get(timeframe)
    if interval is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    yf_period = _PERIOD_MAP[interval]

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            _rate_limit()
            tk = yf.Ticker(ticker)
            df = tk.history(period=yf_period, interval=interval, timeout=_FETCH_TIMEOUT)
            break
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))
    else:
        raise RuntimeError(
            f"Failed to fetch {ticker} ({timeframe}) after {_MAX_RETRIES} retries: {last_error}"
        )

    if df.empty:
        return df

    # Normalize column names
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()

    # Derive 4H bars from 1H data by resampling
    if timeframe == "4h":
        df = _resample_to_4h(df)

    # Trim to requested number of bars
    if len(df) > period:
        df = df.iloc[-period:]

    return df


def _resample_to_4h(df: pd.DataFrame) -> pd.DataFrame:
    """Resample 1H OHLCV data to 4H bars aligned with SET market hours (10:00 open)."""
    # Anchor origin to 10:00 so bins start at 10:00, 14:00, 18:00... covering SET session
    origin_ts = df.index[0].normalize() + pd.Timedelta(hours=10)
    resampled = df.resample("4h", origin=origin_ts).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    return resampled.dropna()


def validate_ticker(ticker: str) -> bool:
    """Validate if the ticker exists and has recent history on yfinance."""
    try:
        _rate_limit()
        tk = yf.Ticker(ticker)
        df = tk.history(period="1d", timeout=10.0)
        return not df.empty
    except Exception:
        return False
