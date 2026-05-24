"""Config CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import ConfigItem, ConfigUpdate
from app.repositories import config_repo

router = APIRouter()


@router.get("/config", response_model=list[ConfigItem])
async def list_config() -> list[ConfigItem]:
    data = await config_repo.get_all_config()
    return [ConfigItem(key=k, value=v) for k, v in sorted(data.items())]


ALLOWED_KEYS = {"history_retention_days"}


@router.get("/config/{key}", response_model=ConfigItem)
async def get_config(key: str) -> ConfigItem:
    if key not in ALLOWED_KEYS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Config key '{key}' is not allowed.")
    value = await config_repo.get_config(key)
    return ConfigItem(key=key, value=value or "")


@router.put("/config/{key}", response_model=ConfigItem)
async def put_config(key: str, body: ConfigUpdate) -> ConfigItem:
    if key not in ALLOWED_KEYS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Config key '{key}' is not allowed.")
    await config_repo.set_config(key, body.value)
    return ConfigItem(key=key, value=body.value)
