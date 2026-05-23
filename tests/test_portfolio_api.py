"""Tests for portfolio API endpoint."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def tmp_portfolio(tmp_path):
    portfolio_file = tmp_path / "portfolio.json"
    portfolio_file.write_text(
        json.dumps(
            {
                "stocks": [
                    {"ticker": "KBANK.BK", "name": "KBANK", "notes": "test"},
                ],
                "updatedAt": None,
            }
        )
    )
    with patch("app.dependencies.PORTFOLIO_PATH", portfolio_file):
        yield portfolio_file


class TestGetPortfolio:
    def test_get_portfolio(self, tmp_portfolio):
        resp = client.get("/api/portfolio")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stocks"]) == 1
        assert data["stocks"][0]["ticker"] == "KBANK.BK"


class TestPutPortfolio:
    def test_update_portfolio(self, tmp_portfolio):
        new_data = {
            "stocks": [
                {"ticker": "KBANK.BK", "name": "KBANK", "notes": "updated"},
                {"ticker": "PTT.BK", "name": "PTT", "notes": "new"},
            ],
        }
        resp = client.put("/api/portfolio", json=new_data)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stocks"]) == 2
        assert data["updatedAt"] is not None

        # Verify file was written
        saved = json.loads(tmp_portfolio.read_text())
        assert len(saved["stocks"]) == 2
