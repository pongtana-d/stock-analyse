"""Shared test fixtures."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point each test at a fresh SQLite file + isolate legacy migration."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    
    # Isolate from local environment credentials
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    # Block legacy portfolio.json migration during tests
    from app import database

    monkeypatch.setattr(database, "LEGACY_PORTFOLIO_JSON", tmp_path / "missing.json")

    yield db_path


@pytest_asyncio.fixture
async def init_test_db(isolated_db):
    from app.database import init_db
    await init_db()
    yield isolated_db
