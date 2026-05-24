"""Tests for /api/analysis with mocked AI + market services."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories import portfolio_repo


@pytest.fixture
def client(init_test_db):
    with TestClient(app) as c:
        yield c


def _fake_df() -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=80, freq="D")
    return pd.DataFrame(
        {
            "Open": [10.0] * 80,
            "High": [11.0] * 80,
            "Low": [9.5] * 80,
            "Close": [10.5 + (i * 0.01) for i in range(80)],
            "Volume": [1_000_000] * 80,
        },
        index=idx,
    )


class TestAnalysisRun:
    def test_run_empty_portfolio_returns_empty(self, client):
        with patch(
            "app.services.calendar.is_trading_day", return_value=True
        ):
            resp = client.post("/api/analysis/run")
            assert resp.status_code == 200
            assert resp.json()["results"] == []

    def test_run_closed_market_409_without_force(self, client):
        with patch("app.services.calendar.is_trading_day", return_value=False):
            resp = client.post("/api/analysis/run")
            assert resp.status_code == 409

    def test_run_closed_market_force_runs(self, client):
        # Seed portfolio
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            portfolio_repo.add("CPF.BK")
        )

        with patch("app.services.calendar.is_trading_day", return_value=False), \
             patch("app.routers.analysis.fetch_ohlcv", return_value=_fake_df()), \
             patch(
                 "app.services.ai_analysis.analyze_stock",
                 new=AsyncMock(return_value="SIGNAL: BUY | Confidence: High"),
             ), \
             patch(
                 "app.services.discord.is_configured", return_value=False
             ):
            resp = client.post("/api/analysis/run", params={"force": "true"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["signal"] == "BUY"


    def test_run_discord_parameter(self, client):
        import asyncio
        # Clean portfolio and add KBANK
        asyncio.get_event_loop().run_until_complete(portfolio_repo.remove("CPF.BK"))
        asyncio.get_event_loop().run_until_complete(portfolio_repo.add("KBANK.BK"))

        with patch("app.services.calendar.is_trading_day", return_value=True), \
             patch("app.routers.analysis.fetch_ohlcv", return_value=_fake_df()), \
             patch(
                 "app.services.ai_analysis.analyze_stock",
                 new=AsyncMock(return_value="SIGNAL: BUY | Confidence: High"),
             ), \
             patch("app.services.discord.is_configured", return_value=True), \
             patch("app.services.discord.send_dm", new=AsyncMock(return_value=True)) as mock_send_dm:
            
            # 1. By default, run_analysis sends discord notifications (send_discord=True)
            resp = client.post("/api/analysis/run")
            assert resp.status_code == 200
            assert mock_send_dm.call_count == 1
            
            mock_send_dm.reset_mock()
            
            # 2. If send_discord=false is passed, run_analysis does not send notifications
            resp = client.post("/api/analysis/run", params={"send_discord": "false"})
            assert resp.status_code == 200
            assert mock_send_dm.call_count == 0
            
            mock_send_dm.reset_mock()
            
            # 3. For single ticker run, send_discord defaults to False
            resp = client.post("/api/analysis/run/KBANK.BK")
            assert resp.status_code == 200
            assert mock_send_dm.call_count == 0
            
            # 4. For single ticker run, send_discord can be explicitly enabled
            resp = client.post("/api/analysis/run/KBANK.BK", params={"send_discord": "true"})
            assert resp.status_code == 200
            assert mock_send_dm.call_count == 1


class TestAnalysisHistory:
    def test_history_empty(self, client):
        resp = client.get("/api/analysis/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_purge_old(self, client):
        resp = client.delete("/api/analysis/history", params={"older_than_days": 0})
        assert resp.status_code == 200
        assert "deleted" in resp.json()
