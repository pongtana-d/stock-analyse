"""FastAPI app entry — SET Analyze backend."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app import web
from app.database import init_db
from app.routers import analysis, config, health, portfolio, stock
from app.dependencies import verify_api_auth, NeedLoginException

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    logger.info("Database initialized; SET Analyze backend ready.")
    yield


app = FastAPI(
    title="Stock Analysis API",
    description="Technical indicator + AI analysis API for SET stocks — powers SET Analyze",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS")
if cors_origins_raw:
    origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]
else:
    origins = ["http://localhost:8000", "http://127.0.0.1:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def csrf_referer_check(request: Request, call_next):
    # Only verify POST, PUT, DELETE requests that are browser-based (non-API)
    # API endpoints under /api/ are protected by X-API-Key/Bearer token and don't use cookies,
    # so they are safe from CSRF.
    if request.method in ("POST", "PUT", "DELETE") and not request.url.path.startswith("/api/"):
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        base_url_str = str(request.base_url)

        if origin:
            if not base_url_str.startswith(origin):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF Protect: Origin header mismatch."}
                )
        elif referer:
            if not referer.startswith(base_url_str):
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF Protect: Referer header mismatch."}
                )
        else:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF Protect: Missing Origin/Referer header."}
            )

    return await call_next(request)

# Exception handler for web login redirect
@app.exception_handler(NeedLoginException)
async def login_redirect_handler(request: Request, exc: NeedLoginException):
    return RedirectResponse("/login", status_code=303)


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(stock.router, prefix="/api", tags=["stock"], dependencies=[Depends(verify_api_auth)])
app.include_router(portfolio.router, prefix="/api", tags=["portfolio"], dependencies=[Depends(verify_api_auth)])
app.include_router(analysis.router, prefix="/api", tags=["analysis"], dependencies=[Depends(verify_api_auth)])
app.include_router(config.router, prefix="/api", tags=["config"], dependencies=[Depends(verify_api_auth)])

# Browser UI (Jinja2 templates)
from pathlib import Path

_STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Mount public first, then protected
app.include_router(web.public_router)
app.include_router(web.router)
