"""GET/PUT /api/portfolio — manage stock portfolio."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from app.dependencies import read_portfolio, write_portfolio
from app.models.schemas import Portfolio

router = APIRouter()


@router.get("/portfolio", response_model=Portfolio)
async def get_portfolio():
    data = read_portfolio()
    return data


@router.put("/portfolio", response_model=Portfolio)
async def update_portfolio(portfolio: Portfolio):
    portfolio.updatedAt = datetime.now(timezone.utc).isoformat()
    data = portfolio.model_dump()
    write_portfolio(data)
    return data
