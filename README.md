# SET Analyze

FastAPI service that fetches SET stock OHLCV data via yfinance, computes technical indicators with TA-Lib, and runs AI analysis (via LiteLLM) using the technical strategy in [system-prompt.md](./data/system-prompt.md). Includes a secure Web UI (Jinja2) and auto-delivery of results to Discord.

This application was built with assistance from Claude Opus 4.7 and Gemini 3.5 Flash.

## Features

- **Multi-TF Analysis**: Confluence across Weekly, Daily, 4H, and 1H timeframes.
- **Indicators**: EMA, MACD, RSI, Bollinger Bands, OBV, Pivot Points, Fibonacci levels, Candlestick patterns, and Swing Points.
- **AI Agent**: Analyzes stock data using Set-chan's personality and rules (via LiteLLM).
- **Auto Scheduler**: Built-in scheduler (APScheduler, Asia/Bangkok / UTC+7) runs analysis automatically during SET trading hours — no external cron needed. Enable/disable and pick a frequency (market hours, 30 min, 1 h, 2 h) from the Config page.
- **Web UI & API**: Manage portfolio, query analysis history, update configs, and manually trigger runs. Protected by optional authentication (`APP_PASSWORD` and `API_KEY`).
- **Discord Delivery**: Automatically sends verdicts and markdown reports to Discord DM.

## Tech Stack

FastAPI · Jinja2 · aiosqlite · TA-Lib · yfinance · LiteLLM · APScheduler · exchange_calendars · pytest

## Quick Start

1. **Install TA-Lib & dependencies**:
   ```bash
   # macOS
   brew install ta-lib
   uv sync
   ```
2. **Setup environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your keys (AI_API_KEY, LITELLM_MODEL, etc.)
   ```
3. **Run application**:
   ```bash
   uv run uvicorn app.main:app --reload
   # Access UI at http://localhost:8000
   ```
4. **Run tests**:
   ```bash
   uv run python -m pytest
   ```

## Project Structure

- `app/`
  - `main.py`: FastAPI app entrypoint.
  - `web.py`: Web UI router (Jinja2 templates in `templates/`).
  - `indicators/`: Technical indicator calculation scripts.
  - `services/`: yfinance, calendar, AI analysis, and Discord integration.
  - `repositories/`: Database repositories.
- `data/`: Database storage.
- `tests/`: Integration & unit tests.

