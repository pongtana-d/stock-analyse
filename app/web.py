"""Web UI router — Jinja2 templates for browser users."""

from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Form, Query, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.repositories import analysis_repo, config_repo, portfolio_repo
from app.routers.analysis import _analyze_one
from app.services import ai_analysis, calendar as market_calendar, discord
from app.services.yahoo import validate_ticker
from app.dependencies import verify_web_auth, get_app_password

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

ENG_MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def format_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        clean_val = value.strip().replace(" ", "T")
        dt = datetime.fromisoformat(clean_val)
    except Exception:
        try:
            dt = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return value
    month_name = ENG_MONTHS[dt.month]
    return f"{dt.day} {month_name} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"

templates.env.filters["format_datetime"] = format_datetime

# Public router does not enforce auth (for login/logout routes)
public_router = APIRouter(include_in_schema=False)

# Protected router enforces auth
router = APIRouter(include_in_schema=False, dependencies=[Depends(verify_web_auth)])


def _ctx(request: Request, **extra) -> dict:
    app_pw = get_app_password()
    auth_enabled = bool(app_pw)
    logged_in = False
    if auth_enabled:
        session_cookie = request.cookies.get("set_chan_session")
        expected_hash = hashlib.sha256(app_pw.encode()).hexdigest()
        logged_in = (session_cookie == expected_hash)

    return {
        "active": extra.pop("active", ""),
        "discord_configured": discord.is_configured(),
        "auth_enabled": auth_enabled,
        "logged_in": logged_in,
        **extra,
    }


# ---------- Authentication ----------

@public_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str | None = None):
    app_pw = get_app_password()
    if app_pw:
        session_cookie = request.cookies.get("set_chan_session")
        expected_hash = hashlib.sha256(app_pw.encode()).hexdigest()
        if session_cookie == expected_hash:
            return RedirectResponse("/", status_code=303)
            
    return templates.TemplateResponse(
        request,
        "login.html",
        _ctx(request, active="login", error=error),
    )


@public_router.post("/login")
async def login(request: Request, password: str = Form(...)):
    app_pw = get_app_password()
    if not app_pw:
        return RedirectResponse("/", status_code=303)
        
    if password == app_pw:
        response = RedirectResponse("/", status_code=303)
        expected_hash = hashlib.sha256(app_pw.encode()).hexdigest()
        response.set_cookie(
            key="set_chan_session",
            value=expected_hash,
            max_age=7 * 24 * 60 * 60,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
        )
        return response
    else:
        return RedirectResponse("/login?error=Incorrect+password", status_code=303)


@public_router.get("/logout")
@public_router.post("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key="set_chan_session")
    return response


# ---------- Dashboard ----------

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    tickers = await portfolio_repo.get_all()
    history = await analysis_repo.get_analysis(limit=5)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(request, active="dashboard", tickers=tickers, history=history),
    )


# ---------- Portfolio ----------

@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
):
    tickers = await portfolio_repo.get_all()
    return templates.TemplateResponse(
        request,
        "portfolio.html",
        _ctx(request, active="portfolio", tickers=tickers, message=message, error=error),
    )


@router.post("/portfolio/add")
async def portfolio_add(ticker: str = Form(...)):
    ticker = ticker.strip().upper()
    if not ticker:
        return RedirectResponse("/portfolio?error=Ticker+is+required", status_code=303)
    if not ticker.endswith(".BK"):
        ticker = f"{ticker}.BK"

    # Validate ticker with Yahoo Finance
    is_valid = await asyncio.to_thread(validate_ticker, ticker)
    if not is_valid:
        return RedirectResponse(f"/portfolio?error=Ticker+{ticker}+is+invalid+or+has+no+data+on+Yahoo+Finance", status_code=303)

    if await portfolio_repo.get_by_ticker(ticker):
        return RedirectResponse(f"/portfolio?error={ticker}+already+exists", status_code=303)
    await portfolio_repo.add(ticker)
    return RedirectResponse(f"/portfolio?message=Added+{ticker}", status_code=303)


@router.post("/portfolio/remove")
async def portfolio_remove(ticker: str = Form(...)):
    t = ticker.strip().upper()
    if not t.endswith(".BK"):
        t = f"{t}.BK"
    deleted = await portfolio_repo.remove(t)
    if deleted:
        return RedirectResponse(f"/portfolio?message=Removed+{t}", status_code=303)
    return RedirectResponse(f"/portfolio?error={t}+not+found", status_code=303)


# ---------- Analysis ----------

@router.get("/analysis", response_class=HTMLResponse)
async def analysis_page(
    request: Request,
    ticker: str | None = Query(default=None),
    message: str | None = None,
    error: str | None = None,
):
    record = None
    if ticker:
        record = await analysis_repo.get_latest_analysis(ticker.strip().upper())
        if not record and not error:
            error = f"No analysis found for {ticker.strip().upper()}."

    return templates.TemplateResponse(
        request,
        "analysis.html",
        _ctx(
            request,
            active="analysis",
            record=record,
            ticker=ticker or "",
            message=message,
            error=error,
        ),
    )


@router.post("/analysis/run")
async def analysis_run_web(
    ticker: str = Form(...),
):
    t = ticker.strip().upper()
    if not t:
        return RedirectResponse("/analysis?error=Ticker+is+required", status_code=303)
    if not t.endswith(".BK"):
        t = f"{t}.BK"

    model = ai_analysis.get_ai_model()
    prompt = ai_analysis.load_system_prompt()

    result = await _analyze_one(t, model, prompt, send_discord=False)
    if result.error:
        return RedirectResponse(
            f"/analysis?ticker={t}&error=Analysis+failed:+{result.error}",
            status_code=303,
        )

    return RedirectResponse(
        f"/analysis?ticker={t}&message=Analysis+completed+for+{t}",
        status_code=303,
    )


# ---------- History ----------

@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    ticker: str | None = Query(default=None),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    message: str | None = None,
    error: str | None = None,
):
    records = await analysis_repo.get_analysis(
        ticker=ticker.upper() if ticker else None,
        start_date=start_date or None,
        end_date=end_date or None,
        limit=100,
    )
    return templates.TemplateResponse(
        request,
        "history.html",
        _ctx(
            request,
            active="history",
            records=records,
            filter_ticker=ticker or "",
            start_date=start_date or "",
            end_date=end_date or "",
            message=message,
            error=error,
        ),
    )


@router.post("/history/purge")
async def history_purge():
    raw = await config_repo.get_config("history_retention_days")
    try:
        days = int(raw) if raw else 90
    except ValueError:
        days = 90
    deleted = await analysis_repo.delete_old_analysis(days)
    return RedirectResponse(
        f"/history?message=Deleted+{deleted}+records+older+than+{days}+days",
        status_code=303,
    )


@router.post("/history/clear_all")
async def history_clear_all():
    deleted = await analysis_repo.delete_all_analysis()
    return RedirectResponse(
        f"/history?message=Cleared+all+{deleted}+history+records",
        status_code=303,
    )


# ---------- Config ----------

@router.get("/config", response_class=HTMLResponse)
async def config_page(
    request: Request,
    message: str | None = None,
    error: str | None = None,
):
    cfg = await config_repo.get_all_config()
    ai_key = ai_analysis.get_ai_api_key()
    return templates.TemplateResponse(
        request,
        "config.html",
        _ctx(
            request,
            active="config",
            config=cfg,
            ai_model=ai_analysis.get_ai_model(),
            ai_api_url=ai_analysis.get_ai_api_url() or "(default)",
            ai_api_key_set=bool(ai_key),
            message=message,
            error=error,
        ),
    )


@router.post("/config/save")
async def config_save(
    history_retention_days: str = Form(...),
):
    await config_repo.set_config("history_retention_days", history_retention_days.strip())
    return RedirectResponse("/config?message=Saved", status_code=303)
