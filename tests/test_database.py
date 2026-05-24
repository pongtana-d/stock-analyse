"""Tests for the SQLite database + repositories."""

from __future__ import annotations

import pytest

from app.database import init_db
from app.repositories import analysis_repo, config_repo, portfolio_repo


@pytest.mark.asyncio
async def test_portfolio_repo_crud(isolated_db):
    await init_db()
    assert await portfolio_repo.get_all() == []

    await portfolio_repo.add("CPF.BK")
    await portfolio_repo.add("PTT.BK")
    assert set(await portfolio_repo.get_all()) == {"CPF.BK", "PTT.BK"}

    # Idempotent insert
    await portfolio_repo.add("CPF.BK")
    assert len(await portfolio_repo.get_all()) == 2

    assert await portfolio_repo.get_by_ticker("CPF.BK") == "CPF.BK"
    assert await portfolio_repo.remove("CPF.BK") is True
    assert await portfolio_repo.remove("CPF.BK") is False


@pytest.mark.asyncio
async def test_config_repo_defaults_and_set(isolated_db, monkeypatch):
    # Clear env overrides so test runs with clean defaults
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_URL", raising=False)

    await init_db()
    retention = await config_repo.get_config("history_retention_days")
    assert retention == "90"

    await config_repo.set_config("ai_model", "anthropic/claude-3-5-sonnet")
    assert (await config_repo.get_config("ai_model")) == "anthropic/claude-3-5-sonnet"

    all_cfg = await config_repo.get_all_config()
    assert all_cfg["ai_model"] == "anthropic/claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_analysis_repo_save_and_query(isolated_db):
    await init_db()
    row = await analysis_repo.save_analysis(
        ticker="CPF.BK",
        ai_model="openai/gpt-4o",
        system_prompt="prompt",
        indicator_data={"daily": {"rsi": 55}},
        ai_response="SIGNAL: BUY | Confidence: High",
        signal="BUY",
        confidence="High",
    )
    assert row["id"] > 0
    assert row["indicator_data"] == {"daily": {"rsi": 55}}

    history = await analysis_repo.get_analysis(ticker="CPF.BK")
    assert len(history) == 1

    latest = await analysis_repo.get_latest_analysis("CPF.BK")
    assert latest is not None and latest["signal"] == "BUY"


@pytest.mark.asyncio
async def test_delete_old_analysis(isolated_db):
    await init_db()
    await analysis_repo.save_analysis(
        ticker="CPF.BK",
        ai_model="m",
        system_prompt=None,
        indicator_data={},
        ai_response="x",
        signal=None,
        confidence=None,
        analysis_date="2000-01-01T00:00:00+00:00",
    )
    deleted = await analysis_repo.delete_old_analysis(1)
    assert deleted == 1


@pytest.mark.asyncio
async def test_migration_from_legacy_list_json(tmp_path, monkeypatch):
    legacy = tmp_path / "portfolio.json"
    legacy.write_text('["AAA.BK", "BBB.BK"]', encoding="utf-8")
    db_file = tmp_path / "stock.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))

    from app import database

    monkeypatch.setattr(database, "LEGACY_PORTFOLIO_JSON", legacy)

    await init_db()
    tickers = await portfolio_repo.get_all()
    assert set(tickers) == {"AAA.BK", "BBB.BK"}


@pytest.mark.asyncio
async def test_migration_from_legacy_dict_json(tmp_path, monkeypatch):
    legacy = tmp_path / "portfolio.json"
    legacy.write_text(
        '{"stocks":[{"ticker":"CPF.BK","name":"x"},{"ticker":"PTT.BK"}]}',
        encoding="utf-8",
    )
    db_file = tmp_path / "stock.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_file))

    from app import database

    monkeypatch.setattr(database, "LEGACY_PORTFOLIO_JSON", legacy)

    await init_db()
    tickers = await portfolio_repo.get_all()
    assert set(tickers) == {"CPF.BK", "PTT.BK"}
