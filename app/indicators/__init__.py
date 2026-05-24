"""Shared utilities for indicators."""

from __future__ import annotations

def format_indicator_date(ts) -> str:
    """Format pandas Timestamp/datetime for indicator data series."""
    if hasattr(ts, "hour") and ts.hour != 0:
        return ts.strftime("%Y-%m-%d %H:%M")
    return ts.strftime("%Y-%m-%d")
