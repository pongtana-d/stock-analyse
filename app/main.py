from fastapi import FastAPI

from app.routers import health, portfolio, stock

app = FastAPI(
    title="Stock Analysis API",
    description="Technical indicator API for SET stocks — powers Set-chan",
    version="0.1.0",
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(stock.router, prefix="/api", tags=["stock"])
app.include_router(portfolio.router, prefix="/api", tags=["portfolio"])
