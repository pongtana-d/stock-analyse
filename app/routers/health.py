import asyncio
from datetime import datetime, timezone

import yfinance as yf
from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter()


def _check_yfinance() -> str:
    try:
        ticker = yf.Ticker("^SET.BK")
        hist = ticker.history(period="1d")
        if hist.empty:
            return "error"
        return "ok"
    except Exception:
        return "error"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    yf_status = await asyncio.to_thread(_check_yfinance)

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        yfinance=yf_status,
    )
