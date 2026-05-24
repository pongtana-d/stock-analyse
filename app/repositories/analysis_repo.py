"""Analysis history repository."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.database import get_db


def _serialize_row(row) -> dict[str, Any]:
    data = dict(row)
    raw = data.get("indicator_data")
    try:
        data["indicator_data"] = json.loads(raw) if raw else None
    except (TypeError, json.JSONDecodeError):
        data["indicator_data"] = None
    return data


async def save_analysis(
    *,
    ticker: str,
    ai_model: str,
    system_prompt: str | None,
    indicator_data: dict[str, Any],
    ai_response: str,
    signal: str | None,
    confidence: str | None,
    analysis_date: str | None = None,
) -> dict[str, Any]:
    when = analysis_date or datetime.now(timezone.utc).isoformat()
    payload = json.dumps(indicator_data, ensure_ascii=False, default=str)

    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO analysis_history
                (ticker, ai_model, system_prompt, indicator_data,
                 ai_response, signal, confidence, analysis_date)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (ticker, ai_model, system_prompt, payload, ai_response,
             signal, confidence, when),
        )
        await db.commit()
        new_id = cursor.lastrowid
        await cursor.close()

        cursor = await db.execute(
            "SELECT * FROM analysis_history WHERE id = ?", (new_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()

    return _serialize_row(row)


async def get_analysis(
    *,
    ticker: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if ticker:
        clauses.append("ticker = ?")
        params.append(ticker)
    if start_date:
        clauses.append("analysis_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("analysis_date <= ?")
        params.append(end_date)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT * FROM analysis_history
        {where}
        ORDER BY analysis_date DESC
        LIMIT ?
    """
    params.append(limit)

    async with get_db() as db:
        cursor = await db.execute(sql, params)
        rows = await cursor.fetchall()
        await cursor.close()
    return [_serialize_row(r) for r in rows]


async def get_latest_analysis(ticker: str) -> dict[str, Any] | None:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT * FROM analysis_history
            WHERE ticker = ?
            ORDER BY analysis_date DESC
            LIMIT 1
            """,
            (ticker,),
        )
        row = await cursor.fetchone()
        await cursor.close()
    return _serialize_row(row) if row else None


async def delete_old_analysis(older_than_days: int) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """
            DELETE FROM analysis_history
            WHERE analysis_date < datetime('now', ?)
            """,
            (f"-{int(older_than_days)} days",),
        )
        await db.commit()
        count = cursor.rowcount
        await cursor.close()
    return count


async def delete_all_analysis() -> int:
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM analysis_history")
        await db.commit()
        count = cursor.rowcount
        await cursor.close()
    return count
