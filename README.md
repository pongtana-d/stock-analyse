# 📈 Automate Stock Analysis (SET)

FastAPI service that fetches SET (Stock Exchange of Thailand) OHLCV data and computes a full technical-indicator stack — designed to power **Set-chan** (เซ็ตจัง), the AI TA agent defined in [AGENTS.md](./AGENTS.md).

## 🚀 Quick Start
```bash
# 1. Install TA-Lib C library (macOS)
brew install ta-lib

# 2. Install Python dependencies
uv sync

# 3. Run dev server
uv run uvicorn app.main:app --reload
```
API docs: <http://localhost:8000/docs>

Run tests:
```bash
uv sync --group dev
uv run python -m pytest -q
```

## 📡 API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service + Yahoo Finance status |
| `GET` | `/api/stock/{ticker}` | Indicators + OHLCV across timeframes |
| `GET` | `/api/portfolio` | Read watchlist |
| `PUT` | `/api/portfolio` | Replace watchlist |

### `GET /api/stock/{ticker}`
Query params:
- `timeframes` — comma-separated, any of `weekly,daily,4h,1h` (default: all four)
- `period` — bars per timeframe (1–500, default `120`)

Per timeframe, the response includes:
- `ema` — EMA 20 / 50 / 200
- `macd` — MACD(12,26,9) line, signal, histogram, crossover (`bullish`/`bearish`)
- `rsi` — RSI(14) latest value + last 30 bars (for divergence detection)
- `bollingerBands` — upper / middle / lower / bandwidth
- `volume` — OBV, OBV trend (`rising`/`falling`/`flat`), `recentVsAvg`
- `pivotPoints` — Classic pivots (PP/R1/R2/S1/S2) from the previous completed bar
- `fibonacci` — 38.2 / 50 / 61.8 retracement levels + swing trend
- `candlestick.patterns` — 19 TA-Lib patterns scanned over the last 5 bars
- `swingPoints` — alternating HH/HL/LH/LL sequence (oldest → newest)
- `ohlc` — last `period` bars of OHLCV

## 🤖 AI Integration
The core of this project is **[AGENTS.md](./AGENTS.md)**, which defines:
- **Persona** — Set-chan (เซ็ตจัง), Technical Analysis specialist
- **Strategy** — Multi-Timeframe Analysis (Weekly → 1H)
- **Signal Rules** — BUY / SELL / HOLD / BUY ON DIP / TAKE PROFIT / REDUCE checklists
- **Response Format** — 3-second verdict + reasons + caveats

## 🛠 Tech Stack
- **Framework**: FastAPI (async)
- **Indicators**: TA-Lib
- **Data**: yfinance + pandas
- **Package manager**: [uv](https://docs.astral.sh/uv/)

## 📂 Layout
```
app/
  main.py            FastAPI app entry
  dependencies.py    Portfolio I/O
  routers/           health, stock, portfolio
  services/
    yahoo.py         yfinance wrapper (rate-limit, retry, 4H resample)
    indicators.py    Aggregator
  indicators/        ema, macd, rsi, bollinger, obv, pivot, fibonacci, candlestick, swing
  models/schemas.py  Pydantic response models
tests/               pytest suite
data/portfolio.json  Watchlist (read/write target of /api/portfolio)
```

---
*Note: SET data on Yahoo Finance is delayed ~15 minutes. Set-chan factors this in when issuing signals.*
