"""Tests for portfolio API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


from unittest.mock import patch

@pytest.fixture
def client(init_test_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def mock_validate_ticker():
    with patch("app.services.yahoo.validate_ticker", return_value=True) as m:
        yield m


class TestPortfolio:
    def test_list_empty(self, client):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        assert resp.json() == {"tickers": []}

    def test_add_and_list(self, client):
        resp = client.post("/api/portfolio", json={"ticker": "kbank.bk"})
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "KBANK.BK"

        resp = client.get("/api/portfolio")
        assert resp.json()["tickers"] == ["KBANK.BK"]

    def test_add_without_suffix_appends_bk(self, client):
        resp = client.post("/api/portfolio", json={"ticker": "KBANK"})
        assert resp.status_code == 201
        assert resp.json()["ticker"] == "KBANK.BK"

        resp = client.get("/api/portfolio")
        assert resp.json()["tickers"] == ["KBANK.BK"]

    def test_add_invalid_ticker_returns_400(self, client):
        with patch("app.services.yahoo.validate_ticker", return_value=False):
            resp = client.post("/api/portfolio", json={"ticker": "INVALID"})
            assert resp.status_code == 400
            assert "invalid or has no data" in resp.json()["detail"]

    def test_duplicate_returns_409(self, client):
        client.post("/api/portfolio", json={"ticker": "PTT.BK"})
        resp = client.post("/api/portfolio", json={"ticker": "PTT.BK"})
        assert resp.status_code == 409

    def test_remove(self, client):
        client.post("/api/portfolio", json={"ticker": "PTT.BK"})
        resp = client.delete("/api/portfolio/PTT.BK")
        assert resp.status_code == 204

        resp = client.get("/api/portfolio")
        assert resp.json()["tickers"] == []

    def test_remove_without_suffix(self, client):
        client.post("/api/portfolio", json={"ticker": "PTT.BK"})
        resp = client.delete("/api/portfolio/PTT")
        assert resp.status_code == 204

        resp = client.get("/api/portfolio")
        assert resp.json()["tickers"] == []

    def test_remove_missing_404(self, client):
        resp = client.delete("/api/portfolio/NOPE.BK")
        assert resp.status_code == 404
