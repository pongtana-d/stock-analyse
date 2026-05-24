"""Portfolio repository — SQLite-backed ticker watchlist."""

from __future__ import annotations

from app.database import get_db


async def get_all() -> list[str]:
    async with get_db() as db:
        cursor = await db.execute("SELECT ticker FROM portfolio ORDER BY ticker ASC")
        rows = await cursor.fetchall()
        await cursor.close()
    return [row["ticker"] for row in rows]


async def get_by_ticker(ticker: str) -> str | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT ticker FROM portfolio WHERE ticker = ?", (ticker,)
        )
        row = await cursor.fetchone()
        await cursor.close()
    return row["ticker"] if row else None


async def add(ticker: str) -> str:
    async with get_db() as db:
        await db.execute(
            "INSERT OR IGNORE INTO portfolio(ticker) VALUES(?)", (ticker,)
        )
        await db.commit()
    return ticker


async def remove(ticker: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM portfolio WHERE ticker = ?", (ticker,)
        )
        await db.commit()
        deleted = cursor.rowcount > 0
        await cursor.close()
    return deleted
