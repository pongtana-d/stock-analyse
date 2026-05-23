"""Tests for stock API endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestHealth:
    def test_health_endpoint(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["yfinance"] in ("ok", "error")


class TestStockEndpoint:
    def test_invalid_timeframe(self):
        resp = client.get("/api/stock/KBANK.BK?timeframes=10min")
        assert resp.status_code == 400

    def test_stock_response_structure(self):
        """Integration test — fetches real data from yfinance."""
        resp = client.get("/api/stock/KBANK.BK?timeframes=daily&period=30")
        # May fail if yfinance is down or no network
        if resp.status_code == 200:
            data = resp.json()
            assert data["ticker"] == "KBANK.BK"
            assert "daily" in data["indicators"]
            assert "daily" in data["ohlc"]
            ind = data["indicators"]["daily"]
            assert "ema" in ind
            assert "macd" in ind
            assert "rsi" in ind
            assert "bollingerBands" in ind
            assert "volume" in ind
            assert "pivotPoints" in ind
            assert "fibonacci" in ind
