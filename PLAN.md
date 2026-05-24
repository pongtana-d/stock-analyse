# Plan: SET Stock Analysis Phase 2

## TL;DR
ต่อยอด FastAPI backend เดิมด้วย SQLite database, Reflex frontend, AI analysis pipeline (litellm), Discord Bot DM ส่งผล (REST API + httpx), external cron + trigger endpoint สำหรับรัน analysis

---

## Phase 1: SQLite Database + Data Migration

### 1.1 เพิ่ม dependencies
- `aiosqlite` — async SQLite driver
- `exchange-calendars` — ตรวจ SET market calendar
- `litellm` — AI model call (รองรับ OpenAI/Anthropic/Google/OpenRouter/ฯลฯ)
- `apscheduler` — ไว้สำรอง แต่หลักใช้ external cron

### 1.2 สร้าง `app/database.py`
- SQLite connection management (async with aiosqlite)
- DB path: `data/stock.db`
- Table schemas:
  - **portfolio** — `id, ticker, created_at` (เก็บแค่ symbol, ไม่มี name/notes)
  - **analysis_history** — `id, ticker, ai_model, system_prompt, indicator_data (JSON), ai_response, signal, confidence, analysis_date, created_at`
  - **config** — `id, key, value, updated_at` (key-value store: `history_retention_days`, `ai_model`, `discord_bot_token`, `discord_user_id`)
- Schema migration with `CREATE TABLE IF NOT EXISTS`
- Helper functions: `init_db()`, `get_db()`

### 1.3 สร้าง `app/repositories/portfolio_repo.py`
- `get_all()` → list[str] (list of tickers)
- `get_by_ticker(ticker)` → str | None
- `add(ticker)` → str
- `remove(ticker)` → bool
- Migrate existing `portfolio.json` data on init (extract tickers only)

### 1.4 สร้าง `app/repositories/analysis_repo.py`
- `save_analysis(...)` → AnalysisRecord
- `get_analysis(ticker, date_range)` → list[AnalysisRecord]
- `delete_old_analysis(older_than_days)` → int (count deleted)
- `get_latest_analysis(ticker)` → AnalysisRecord | None

### 1.5 สร้าง `app/repositories/config_repo.py`
- `get_config(key)` → str | None
- `set_config(key, value)` → void
- Default values: `history_retention_days=90`, `ai_model=openai/gpt-4o`
- Sensitive values (`discord_bot_token`) อ่านจาก `.env` เป็นหลัก, config DB เก็บแค่ non-sensitive settings

### 1.6 อัพเดท `app/main.py`
- `lifespan` event: `init_db()`, migrate portfolio.json → SQLite (extract tickers only)
- Startup log

### 1.7 Update `.env.example`
```
# AI Configuration (LiteLLM — supports OpenAI, Anthropic, Google, OpenRouter, etc.)
OPENAI_API_KEY=sk-...
LITELLM_MODEL=openai/gpt-4o

# Discord Bot (REST API — no discord.py dependency)
DISCORD_BOT_TOKEN=bot-token-here
DISCORD_USER_ID=your-discord-user-id

# Database
DATABASE_PATH=data/stock.db
```

---

## Phase 2: Market Calendar + Analysis Pipeline

### 2.1 สร้าง `app/services/calendar.py`
- `is_market_open(date)` → bool — ใช้ `exchange_calendars` Thai exchange (XTSE)
- `get_next_trading_day(date)` → date
- `is_trading_day(date)` → bool

### 2.2 สร้าง `app/services/ai_analysis.py`
- `analyze_stock(ticker, indicators_data, system_prompt)` → str
  - ใช้ `litellm.completion()` ส่ง indicator data + AGENTS.md system prompt
  - Read AGENTS.md ใน `system` message
 - Config: model from config_repo, API key from .env
- `format_for_discord(ticker, ai_response, signal_info)` → Discord embed dict

### 2.3 สร้าง `app/services/discord.py`
- ใช้ Discord REST API + `httpx` (ไม่ต้องติดตั้ง `discord.py`)
- `send_dm(user_id, embed_data)` → bool
  - Step 1: `POST /users/@me/channels` with `recipient_id` → ได้ DM channel
  - Step 2: `POST /channels/{channel_id}/messages` with embed → ส่งข้อความ
  - Auth header: `Authorization: Bot {token}`
  - Error handling + logging
- Config: token + user_id จาก `.env`

### 2.4 สร้าง `app/routers/analysis.py`
- `POST /api/analysis/run` — trigger analysis pipeline
  - ตรวจ `is_trading_day(today)` → ถ้าไม่ใช่ return 409
  - ดึง portfolio tickers จาก DB
  - Loop: fetch indicators → AI analyze → save to DB → send Discord
  - Return summary: [{ticker, signal, confidence, timestamp}]
- `POST /api/analysis/run/{ticker}` — run single stock
- `GET /api/analysis/history` — query history by date range, ticker
- `DELETE /api/analysis/history` — purge old records (by config retention days or manual)

### 2.5 อัพเดท `app/routers/portfolio.py`
- เปลี่ยนจาก JSON file → SQLite (ใช้ portfolio_repo)
- Endpoints: GET list, POST add, DELETE remove (ไม่มี PUT เพราะเก็บแค่ ticker)

---

## Phase 3: Reflex Frontend

### 3.1 Setup Reflex app ใน `frontend/`
- `frontend/` directory แยกจาก FastAPI
- Reflex init + config ให้ base API = FastAPI backend
- Tailwind theming: dark mode stock theme (dark navy/green accents)

### 3.2 สร้าง shared state/API client
- `frontend/states/base.py` — shared config, API client
- Config API base URL (default: localhost:8000)

### 3.3 หน้า Portfolio Management
- State: `frontend/states/portfolio.py`
- Page: `frontend/pages/portfolio.py`
- Features:
  - ดู list หุ้นทั้งหมด (simple list/card, แสดง symbol เท่านั้น)
  - เพิ่มหุ้นใหม่ (กรอกแค่ symbol เช่น CPF.BK)
  - ลบหุ้น
- API calls: GET/POST/DELETE `/api/portfolio`

### 3.4 หน้า Analysis History
- State: `frontend/states/analysis.py`
- Page: `frontend/pages/analysis.py`
- Features:
  - Date picker เลือกช่วงวัน
  - Filter by ticker
  - แสดงผลเป็น timeline/card — แบ่งตามเวลา (เช้า/บ่าย/ทั้งวัน)
  - แสดง signal badge (BUY/SELL/HOLD สีต่างกัน)
  - คลิกดูรายละเอียด AI response เต็ม
- API calls: GET `/api/analysis/history`

### 3.5 หน้า Config
- State: `frontend/states/config.py`
- Page: `frontend/pages/config.py`
- Features:
  - ตั้งค่า history retention (จำนวนวัน) + button ลบเก่า
  - แสดง model ที่ใช้ analysis อยู่
  - แสดง Discord Bot status (configured / not configured)
  - Manual trigger "Run Analysis Now" button
- API calls: GET/PUT config, DELETE history, POST analysis/run

### 3.6 หน้า Dashboard (Home)
- Page: `frontend/pages/dashboard.py`
- Quick overview:
  - จำนวนหุ้นใน portfolio
  - Latest analysis summary (signal counts)
  - Quick link run analysis
  - Link ไปหน้าอื่น

---

## Phase 4: Testing + Security + Polish

### 4.1 Testing
- Unit tests: database repos, calendar service, AI analysis formatting
- Integration tests: analysis pipeline (mock litellm + discord)
- API tests: new endpoints (analysis, updated portfolio)
- Test migration: portfolio.json → SQLite

### 4.2 Security
- `.env` for secrets (API keys, webhook URLs) — never committed
- Input validation on all endpoints (Pydantic models)
- Rate limiting consideration for external analysis trigger
- SQL parameterized queries (aiosqlite handles this)

### 4.3 Code Quality
- Type hints throughout
- Error handling + logging
- Consistent response format

---

## File Structure (New/Modified)

```
stock/
├── .env.example                    # UPDATE — add AI, Discord, DB configs
├── pyproject.toml                  # UPDATE — add new deps
├── AGENTS.md                       # KEEP — used as system prompt
├── data/
│   ├── portfolio.json              # KEEP (legacy, migrated on first run) — format: `["CPF.BK", "MINT.BK"]`
│   └── stock.db                    # NEW — SQLite database
├── app/
│   ├── __init__.py
│   ├── main.py                     # UPDATE — lifespan, new routers
│   ├── dependencies.py             # UPDATE — add DB dependency
│   ├── database.py                 # NEW — SQLite setup + connection
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # UPDATE — add Analysis, Config models
│   ├── repositories/
│   │   ├── __init__.py            # NEW
│   │   ├── portfolio_repo.py      # NEW
│   │   ├── analysis_repo.py       # NEW
│   │   └── config_repo.py         # NEW
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py              # KEEP
│   │   ├── portfolio.py           # UPDATE — SQLite CRUD
│   │   ├── stock.py               # KEEP
│   │   └── analysis.py            # NEW — analysis endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── indicators.py          # KEEP
│   │   ├── yahoo.py               # KEEP
│   │   ├── calendar.py            # NEW — market calendar
│   │   ├── ai_analysis.py         # NEW — litellm integration
│   │   └── discord.py             # NEW — Bot DM via REST API (httpx)
│   └── indicators/                # KEEP — all indicator modules
├── frontend/                       # NEW — Reflex app
│   ├── rxconfig.py
│   ├── requirements.txt
│   ├── states/
│   │   ├── base.py
│   │   ├── portfolio.py
│   │   ├── analysis.py
│   │   └── config.py
│   └── pages/
│       ├── dashboard.py
│       ├── portfolio.py
│       ├── analysis.py
│       └── config.py
└── tests/
    ├── test_indicators.py          # KEEP
    ├── test_stock_api.py           # KEEP
    ├── test_portfolio_api.py       # UPDATE — for SQLite
    ├── test_analysis_api.py        # NEW
    ├── test_database.py            # NEW
    ├── test_calendar.py            # NEW
    └── test_ai_analysis.py         # NEW
```

---

## Dependencies to Add (pyproject.toml)

```toml
dependencies = [
    # ... existing ...
    "aiosqlite>=0.21.0",
    "exchange-calendars>=4.6",
    "litellm>=1.60",
]
```

---

## Execution Order

1. **Phase 1** (DB + Migration) → foundation ทุกอย่างต่อจากนี้
2. **Phase 2** (Pipeline) → depends on Phase 1
3. **Phase 3** (UI) → depends on Phase 2 APIs พร้อมใช้
4. **Phase 4** (Testing) → parallel with Phase 2-3, finalize at end

Phase 1 → Phase 2 สามารถทำต่อเนื่องได้เลย
Phase 3 ต้องรอ Phase 2 endpoints เสร็จ
Phase 4 tests สามารถเขียนไปพร้อมกับทุก phase
