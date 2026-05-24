# SET Analyze — SET Stock Technical Analysis

FastAPI service that fetches SET stock OHLCV data via yfinance, computes technical indicators with TA-Lib, then sends them to an AI (LiteLLM) for analysis following the strategy in [AGENTS.md](./AGENTS.md) — includes a Web UI (Jinja2) and auto-sends results via Discord DM.

## Architecture

```
Browser ──HTML──┐
                ├──► FastAPI ──LiteLLM──► LLM (OpenAI/Anthropic/OpenRouter/...)
Cron ──HTTP─────┘     │
                      ├── SQLite (portfolio, analysis_history, config)
                      ├── yfinance + TA-Lib
                      └── Discord REST (httpx)
```

Single container, single process — no Node, no separate frontend build.

## Quick Start

```bash
brew install ta-lib            # macOS (Linux: build from source)
uv sync
cp .env.example .env           # add OPENAI_API_KEY
uv run uvicorn app.main:app --reload    # http://localhost:8000
```

Open browser: `http://localhost:8000`

## Web UI

| Path | Description |
|------|-------------|
| `/` | Dashboard — portfolio size + latest signals + Run Now |
| `/portfolio` | Add/remove tickers |
| `/analysis` | Analysis history + filters + Run / Purge buttons |
| `/config` | AI model, retention settings, Discord status |
| `/docs` | FastAPI auto-generated API docs |

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + yfinance status |
| GET | `/api/stock/{ticker}` | Indicators + OHLCV (`timeframes=weekly,daily,4h,1h`, `period=120`) |
| GET | `/api/portfolio` | List tickers |
| POST | `/api/portfolio` | Add ticker `{"ticker":"CPF.BK"}` |
| DELETE | `/api/portfolio/{ticker}` | Remove ticker |
| POST | `/api/analysis/run` | Run AI analysis for all tickers (409 if not trading day; `?force=true` to skip) |
| POST | `/api/analysis/run/{ticker}` | Single ticker |
| GET | `/api/analysis/history` | Query history (`ticker`, `start_date`, `end_date`, `limit`) |
| DELETE | `/api/analysis/history` | Purge old (`older_than_days`, defaults to config) |
| GET/PUT | `/api/config/{key}` | Runtime config (`ai_model`, `history_retention_days`) |

## AI Pipeline

1. Calendar check (`exchange_calendars` XBKK) — skip non-trading days
2. Fetch OHLCV per ticker → compute indicators → JSON payload
3. LiteLLM `acompletion()` with `AGENTS.md` as system prompt (any model: `openai/gpt-4o`, `anthropic/claude-...`, `openrouter/...`)
4. Parse `SIGNAL` + `Confidence` → save to `analysis_history`
5. Discord DM via REST API if `DISCORD_BOT_TOKEN` configured

Cron example:
```cron
30 10 * * 1-5  curl -sX POST http://localhost:8000/api/analysis/run
```

## Tests

```bash
uv pip install pytest pytest-asyncio
uv run python -m pytest -q
```

## Layout

```
app/
  main.py, database.py, web.py
  templates/       base, dashboard, portfolio, analysis, config (Jinja2)
  static/style.css
  repositories/    portfolio_repo, analysis_repo, config_repo
  routers/         health, stock, portfolio, analysis, config
  services/        yahoo, indicators, calendar, ai_analysis, discord
  indicators/      ema, macd, rsi, bollinger, obv, pivot, fibonacci, candlestick, swing
  models/schemas.py
data/
  portfolio.json   (legacy, auto-migrated to SQLite on first start)
  stock.db
tests/
```

## Environment

```env
AI_API_KEY=sk-...
AI_API_URL=https://api.openai.com/v1
LITELLM_MODEL=openai/gpt-4o
DISCORD_BOT_TOKEN=
DISCORD_USER_ID=
DATABASE_PATH=data/stock.db
```

## Tech Stack

FastAPI · Jinja2 · aiosqlite · TA-Lib · yfinance · LiteLLM · exchange_calendars · httpx · uv
