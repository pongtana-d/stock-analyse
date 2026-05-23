from datetime import datetime, timezone

import yfinance as yf
from fastapi import APIRouter

from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    yf_status = "ok"
    try:
        ticker = yf.Ticker("^SET.BK")
        hist = ticker.history(period="1d")
        if hist.empty:
            yf_status = "error"
    except Exception:
        yf_status = "error"

    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        yfinance=yf_status,
    )
