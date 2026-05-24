"""Tests for SET calendar wrapper."""

from __future__ import annotations

import pytest

from app.services import calendar as market_calendar


@pytest.mark.parametrize("d, expected", [
    ("2025-01-01", False),  # New Year holiday
    ("2025-01-02", True),   # Trading day
    ("2025-01-04", False),  # Saturday
])
def test_is_trading_day(d, expected):
    assert market_calendar.is_trading_day(d) is expected


def test_next_trading_day_skips_weekend():
    ts = market_calendar.get_next_trading_day("2025-01-04")  # Saturday
    assert ts.weekday() < 5
