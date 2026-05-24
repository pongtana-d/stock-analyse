"""GET/POST/DELETE /api/portfolio — SQLite-backed watchlist."""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException

from app.models.schemas import PortfolioItem, PortfolioList
from app.repositories import portfolio_repo
from app.services.yahoo import validate_ticker

router = APIRouter()


@router.get("/portfolio", response_model=PortfolioList)
async def list_portfolio() -> PortfolioList:
    tickers = await portfolio_repo.get_all()
    return PortfolioList(tickers=tickers)


@router.post("/portfolio", response_model=PortfolioItem, status_code=201)
async def add_portfolio(item: PortfolioItem) -> PortfolioItem:
    ticker = item.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    if not ticker.endswith(".BK"):
        ticker = f"{ticker}.BK"

    # Validate ticker with Yahoo Finance
    is_valid = await asyncio.to_thread(validate_ticker, ticker)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"ticker '{ticker}' is invalid or has no data on Yahoo Finance")

    existing = await portfolio_repo.get_by_ticker(ticker)
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} already exists")
    await portfolio_repo.add(ticker)
    return PortfolioItem(ticker=ticker)


@router.delete("/portfolio/{ticker}", status_code=204)
async def remove_portfolio(ticker: str) -> None:
    t = ticker.strip().upper()
    if not t.endswith(".BK"):
        t = f"{t}.BK"
    deleted = await portfolio_repo.remove(t)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"{ticker} not found")
    return None
