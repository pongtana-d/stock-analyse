"""Tests for indicator calculations."""

import numpy as np
import pandas as pd
import pytest

from app.indicators.bollinger import calculate_bollinger
from app.indicators.candlestick import calculate_candlestick
from app.indicators.ema import calculate_ema
from app.indicators.fibonacci import calculate_fibonacci
from app.indicators.macd import calculate_macd
from app.indicators.obv import calculate_obv
from app.indicators.pivot import calculate_pivot
from app.indicators.rsi import calculate_rsi
from app.indicators.swing import calculate_swing_points

import re


def _make_df(n: int = 200) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", periods=n, freq="D")
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    open_ = close + np.random.randn(n) * 0.5
    volume = np.random.randint(100_000, 1_000_000, n)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )


class TestEMA:
    def test_all_emas_with_enough_data(self):
        df = _make_df(200)
        result = calculate_ema(df)
        assert result.ema20 is not None
        assert result.ema50 is not None
        assert result.ema200 is not None

    def test_short_data(self):
        df = _make_df(10)
        result = calculate_ema(df)
        assert result.ema20 is None
        assert result.ema50 is None
        assert result.ema200 is None


class TestMACD:
    def test_macd_values(self):
        df = _make_df(100)
        result = calculate_macd(df)
        assert result.macd is not None
        assert result.signal is not None
        assert result.histogram is not None

    def test_short_data(self):
        df = _make_df(10)
        result = calculate_macd(df)
        assert result.macd is None


class TestRSI:
    def test_rsi_range(self):
        df = _make_df(100)
        result = calculate_rsi(df)
        assert result.value is not None
        assert 0 <= result.value <= 100

    def test_short_data(self):
        df = _make_df(5)
        result = calculate_rsi(df)
        assert result.value is None


class TestBollinger:
    def test_bands(self):
        df = _make_df(100)
        result = calculate_bollinger(df)
        assert result.upper is not None
        assert result.middle is not None
        assert result.lower is not None
        assert result.upper > result.middle > result.lower
        assert result.bandwidth is not None and result.bandwidth > 0


class TestOBV:
    def test_obv_trend(self):
        df = _make_df(100)
        result = calculate_obv(df)
        assert result.obv is not None
        assert result.obvTrend in ("rising", "falling", "flat")
        assert result.recentVsAvg is not None


class TestPivot:
    def test_pivot_levels(self):
        df = _make_df(10)
        result = calculate_pivot(df)
        assert result.pp is not None
        assert result.r1 > result.pp > result.s1
        assert result.r2 > result.r1
        assert result.s2 < result.s1


class TestFibonacci:
    def test_fib_levels(self):
        df = _make_df(50)
        result = calculate_fibonacci(df)
        assert result.level_382 is not None
        assert result.level_50 is not None
        assert result.level_618 is not None
        # 38.2% retracement should be higher than 61.8%
        assert result.level_382 > result.level_50 > result.level_618


class TestRSISeries:
    def test_series_length(self):
        df = _make_df(200)
        result = calculate_rsi(df)
        assert len(result.series) > 0, "RSI series should have entries for 200 bars of data"
        assert len(result.series) <= 30, "RSI series should have ~30 entries (warmup may reduce count)"

    def test_series_values(self):
        df = _make_df(200)
        result = calculate_rsi(df)
        for point in result.series:
            assert 0 <= point.value <= 100, f"RSI value {point.value} should be between 0 and 100"

    def test_series_has_dates(self):
        df = _make_df(200)
        result = calculate_rsi(df)
        for point in result.series:
            assert isinstance(point.date, str) and len(point.date) > 0, "RSI date should be non-empty string"

    def test_series_empty_on_short_data(self):
        df = _make_df(5)
        result = calculate_rsi(df)
        assert result.value is None, "RSI value should be None for short data"
        assert len(result.series) == 0, "RSI series should be empty for short data"


class TestSwingPoints:
    def test_finds_swing_points(self):
        df = _make_df(200)
        result = calculate_swing_points(df)
        assert len(result.points) > 0, "Should find some swing points with 200 bars"

    def test_swing_point_types(self):
        df = _make_df(200)
        result = calculate_swing_points(df)
        for point in result.points:
            assert point.type in ("high", "low"), f"Swing point type should be 'high' or 'low', got '{point.type}'"

    def test_swing_point_prices(self):
        df = _make_df(200)
        result = calculate_swing_points(df)
        for point in result.points:
            assert point.price > 0, f"Swing point price should be positive, got {point.price}"

    def test_swing_ordering(self):
        df = _make_df(200)
        result = calculate_swing_points(df)
        dates = [point.date for point in result.points]
        assert dates == sorted(dates), "Swing points should be sorted oldest to newest"

    def test_empty_on_short_data(self):
        df = _make_df(5)
        result = calculate_swing_points(df)
        assert len(result.points) == 0, "Should return empty points list for short data"


class TestCandlestickDates:
    def test_patterns_have_dates(self):
        df = _make_df(50)
        result = calculate_candlestick(df)
        for pattern in result.patterns:
            assert isinstance(pattern.date, str) and len(pattern.date) > 0, "Pattern date should be non-empty string"

    def test_pattern_dates_format(self):
        df = _make_df(50)
        result = calculate_candlestick(df)
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")
        for pattern in result.patterns:
            assert date_pattern.match(pattern.date), f"Pattern date '{pattern.date}' should match YYYY-MM-DD or YYYY-MM-DD HH:MM format"


class TestFibonacciTrend:
    def test_trend_is_set(self):
        df = _make_df(200)
        result = calculate_fibonacci(df)
        assert result.trend in ("bullish", "bearish"), "Fibonacci trend should be 'bullish' or 'bearish'"

    def test_trend_consistency(self):
        df = _make_df(200)
        result = calculate_fibonacci(df)
        if result.trend == "bullish":
            # Bullish: measured down from swing_high → shallow (38.2%) > deep (61.8%)
            assert result.level_382 > result.level_618, "In bullish trend, 38.2% should be higher than 61.8%"
        elif result.trend == "bearish":
            # Bearish: measured up from swing_low → shallow (38.2%) < deep (61.8%)
            assert result.level_382 < result.level_618, "In bearish trend, 38.2% should be lower than 61.8%"
