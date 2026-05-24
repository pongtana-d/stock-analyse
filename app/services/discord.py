"""Discord Bot DM via REST API (httpx, no discord.py dependency)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"


def _config() -> tuple[str | None, str | None]:
    token = os.getenv("DISCORD_BOT_TOKEN")
    user_id = os.getenv("DISCORD_USER_ID")
    return token, user_id


def is_configured() -> bool:
    token, user_id = _config()
    return bool(token and user_id)


async def send_dm(embed: dict[str, Any], content: str | None = None) -> bool:
    """Send a DM to the configured user. Returns True on success."""
    token, user_id = _config()
    if not token or not user_id:
        logger.warning("Discord bot not configured; skipping DM send")
        return False

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "set-analyze/0.2 (+https://github.com/mono-tong/stock)",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{DISCORD_API}/users/@me/channels",
                headers=headers,
                json={"recipient_id": user_id},
            )
            resp.raise_for_status()
            channel_id = resp.json()["id"]

            payload: dict[str, Any] = {"embeds": [embed]}
            if content:
                payload["content"] = content

            resp = await client.post(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("Discord DM failed: %s", exc)
            return False
