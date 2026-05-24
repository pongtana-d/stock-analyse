"""SET market calendar utilities (exchange_calendars XBKK)."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache

import pandas as pd

try:  # exchange_calendars is optional at runtime; tests may stub it
    import exchange_calendars as xcals
except ImportError:  # pragma: no cover
    xcals = None  # type: ignore[assignment]


@lru_cache(maxsize=1)
def _calendar():
    if xcals is None:
        raise RuntimeError("exchange_calendars is not installed")
    return xcals.get_calendar("XBKK")


def _to_ts(value: date | datetime | str) -> pd.Timestamp:
    if isinstance(value, pd.Timestamp):
        ts = value
    else:
        ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.normalize()


def is_trading_day(value: date | datetime | str) -> bool:
    cal = _calendar()
    return bool(cal.is_session(_to_ts(value)))


def is_market_open(at: datetime | None = None) -> bool:
    """True if the SET is currently open at the given UTC timestamp (default: now)."""
    cal = _calendar()
    ts = pd.Timestamp(at) if at else pd.Timestamp.utcnow()
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return bool(cal.is_open_on_minute(ts))


def get_next_trading_day(value: date | datetime | str) -> pd.Timestamp:
    cal = _calendar()
    ts = _to_ts(value)
    # Find the next session strictly after ts using sessions_in_range
    end = ts + pd.Timedelta(days=14)
    sessions = cal.sessions_in_range(ts + pd.Timedelta(days=1), end)
    if len(sessions) == 0:
        return cal.next_session(ts) if cal.is_session(ts) else ts  # pragma: no cover
    return sessions[0]
