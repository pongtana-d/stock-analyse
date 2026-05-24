"""Tests for web helper functions, including date/time formatting."""

from __future__ import annotations

from app.web import format_datetime


def test_format_datetime_utc_to_bangkok():
    # UTC time: 2026-05-24T07:20:00+00:00 (which is 14:20:00+07:00)
    utc_str = "2026-05-24T07:20:00+00:00"
    formatted = format_datetime(utc_str)
    assert formatted == "24 May 2026, 14:20"

    # UTC time with Z: 2026-05-24T07:20:00Z (which is 14:20:00+07:00)
    utc_z_str = "2026-05-24T07:20:00Z"
    formatted_z = format_datetime(utc_z_str)
    assert formatted_z == "24 May 2026, 14:20"

    # Naive UTC string: 2026-05-24 07:20:00 -> assumed UTC, converts to 14:20
    naive_str = "2026-05-24 07:20:00"
    formatted_naive = format_datetime(naive_str)
    assert formatted_naive == "24 May 2026, 14:20"


def test_format_datetime_empty_and_invalid():
    assert format_datetime("") == ""
    assert format_datetime(None) == ""
    assert format_datetime("not-a-date") == "not-a-date"
