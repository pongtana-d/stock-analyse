"""Config key-value repository."""

from __future__ import annotations

import os

from app.database import get_db

DEFAULTS: dict[str, str] = {
    "history_retention_days": "90",
    "ai_model": "openai/gpt-4o",
}

# Keys sourced from env vars — read-only in UI, never stored in DB
ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "ai_model": ("LITELLM_MODEL", ""),
    "ai_api_key": ("AI_API_KEY", ""),
    "ai_api_url": ("AI_API_URL", ""),
}


async def get_config(key: str) -> str | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = await cursor.fetchone()
        await cursor.close()
    if row:
        return row["value"]
    return DEFAULTS.get(key)


async def set_config(key: str, value: str) -> None:
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO config(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = datetime('now')
            """,
            (key, value),
        )
        await db.commit()


def _resolve_env_overrides() -> dict[str, str]:
    """Read env-sourced config values with mask for secrets."""
    result = {}
    for key, (env_var, _) in ENV_OVERRIDES.items():
        val = os.getenv(env_var)
        if val:
            result[key] = val
    return result


async def get_all_config() -> dict[str, str]:
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM config")
        rows = await cursor.fetchall()
        await cursor.close()
    result = dict(DEFAULTS)
    for row in rows:
        result[row["key"]] = row["value"]
    # Overlay env overrides (take precedence)
    result.update(_resolve_env_overrides())
    return result
