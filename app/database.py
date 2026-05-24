"""SQLite database setup + connection management."""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "stock.db"
LEGACY_PORTFOLIO_JSON = Path(__file__).resolve().parent.parent / "data" / "portfolio.json"


def _db_path() -> Path:
    raw = os.getenv("DATABASE_PATH")
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analysis_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    ai_model TEXT NOT NULL,
    system_prompt TEXT,
    indicator_data TEXT NOT NULL,
    ai_response TEXT NOT NULL,
    signal TEXT,
    confidence TEXT,
    analysis_date TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analysis_ticker_date
    ON analysis_history(ticker, analysis_date DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_date
    ON analysis_history(analysis_date DESC);

CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Open a new aiosqlite connection scoped to a single request/operation."""
    db = await aiosqlite.connect(_db_path())
    db.row_factory = aiosqlite.Row
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    """Initialize database schema and migrate legacy data if needed."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()

        # Seed default config (only if missing)
        defaults = {
            "history_retention_days": "90",
            "ai_model": os.getenv("LITELLM_MODEL", "openai/gpt-4o"),
        }
        for key, value in defaults.items():
            await db.execute(
                "INSERT OR IGNORE INTO config(key, value) VALUES(?, ?)",
                (key, value),
            )
        await db.commit()

        # Migrate legacy portfolio.json on first run
        cursor = await db.execute("SELECT COUNT(*) AS c FROM portfolio")
        row = await cursor.fetchone()
        await cursor.close()
        existing = row[0] if row else 0

        if existing == 0 and LEGACY_PORTFOLIO_JSON.exists():
            try:
                raw = json.loads(LEGACY_PORTFOLIO_JSON.read_text(encoding="utf-8"))
                tickers: list[str] = []
                if isinstance(raw, list):
                    tickers = [str(t) for t in raw]
                elif isinstance(raw, dict):
                    for entry in raw.get("stocks", []):
                        if isinstance(entry, dict) and "ticker" in entry:
                            tickers.append(entry["ticker"])
                        elif isinstance(entry, str):
                            tickers.append(entry)
                for t in tickers:
                    await db.execute(
                        "INSERT OR IGNORE INTO portfolio(ticker) VALUES(?)",
                        (t,),
                    )
                await db.commit()
                if tickers:
                    logger.info("Migrated %d tickers from portfolio.json", len(tickers))
            except Exception as exc:  # pragma: no cover — best-effort migration
                logger.warning("Failed to migrate portfolio.json: %s", exc)

        # Backfill signal and confidence for existing analysis records where they are missing
        try:
            async with db.execute(
                "SELECT id, ai_response FROM analysis_history WHERE signal IS NULL OR confidence IS NULL"
            ) as cursor:
                rows = await cursor.fetchall()
            if rows:
                from app.services.ai_analysis import parse_ai_response
                backfilled_count = 0
                for row in rows:
                    row_id, ai_response = row[0], row[1]
                    parsed = parse_ai_response(ai_response)
                    sig, conf = parsed["signal"], parsed["confidence"]
                    if sig or conf:
                        await db.execute(
                            "UPDATE analysis_history SET signal = ?, confidence = ? WHERE id = ?",
                            (sig, conf, row_id),
                        )
                        backfilled_count += 1
                if backfilled_count > 0:
                    await db.commit()
                    logger.info("Backfilled %d historical records with signal/confidence", backfilled_count)
        except Exception as exc:
            logger.warning("Failed to backfill historical records: %s", exc)
