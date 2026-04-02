# NSE + BSE Corporate Filings Monitor

## Project Purpose
Real-time NSE + BSE corporate filings monitor that:
- Fetches ALL corporate announcements from NSE + BSE every 30 seconds
- Classifies them as HIGH / MODERATE / ROUTINE impact
- Runs Gemini AI analysis on HIGH impact filings (verdict, confidence score, evidence, action window)
- Sends personalized Telegram alerts to multiple subscribers based on their preferences
- Logs everything to Supabase (primary) and a color-coded Excel file
- Displays a live Streamlit dashboard (Screener/Moneycontrol-style professional UI)
- Tracks post-filing price movements for HIGH filings (alerts if stock moves >2% within 10 min)

## Architecture
```
nse_monitor.py      ← Continuous monitor (NSE + BSE feeds, Gemini, Supabase, Telegram)
dashboard.py        ← Streamlit dashboard (reads from Supabase)
telegram_bot.py     ← Multi-subscriber Telegram bot (polling, manages subscribers table)
migrate_db.py       ← One-time DB schema migration (adds columns, creates subscribers table)
run_forever.bat     ← Auto-restart wrapper for nse_monitor.py
run_bot_forever.bat ← Auto-restart wrapper for telegram_bot.py
```

## Files

### Core Scripts
- **nse_monitor.py** — Main monitor (runs continuously)
  - Fetches from 3 NSE APIs in parallel (equities, SME, debt) + BSE API
  - Session-based with cookie warmup for both NSE and BSE
  - Keyword-based classification (HIGH / MODERATE / ROUTINE)
  - Downloads filing PDFs to `Filings/<SYMBOL>/` folders
  - Gemini 2.0 Flash Lite analysis for HIGH filings: verdict, confidence %, evidence, action window
  - 3 Gemini API keys with auto-rotation on 429 rate limits
  - Writes to Supabase `nse_filings` table (primary store)
  - Writes to Excel `NSE_Filings_Log.xlsx` (atomic: temp → backup → replace)
  - Sends Telegram alerts to all active subscribers (filtered by their preferences)
  - Price movement tracker: stores CMP at filing time, checks 10 min later, alerts if >2% move
  - Schema detection at startup: checks optional columns (exchange, confidence_pct, evidence, action_window)
  - `seen_filings.json` deduplication (format: `NSE_SYMBOL_seqNo_date` / `BSE_SYMBOL_seqNo_date`)

- **dashboard.py** — Streamlit dashboard (professional financial UI)
  - Reads live data from Supabase
  - Auto-refreshes every 30s via `@st.fragment(run_every=30)`
  - Professional Inter-font Screener/Moneycontrol-style CSS (navy, orange, green theme)
  - Supports `.streamlit/secrets.toml` or `.env` for credentials
  - Display columns: Exchange, Time, Symbol, Company, Filing Type, Category, Verdict, Confidence, CMP at Filing, Day Change %
  - Hidden columns: Reason, Risk, Summary, Date, PDF Path
  - Stats badges, sidebar filters, market open/closed indicator
  - Category breakdown bar chart (Plotly)
  - Watchlist group tagging (reads `watchlist.json`)
  - Live ticker bar showing most recent filing

- **telegram_bot.py** — Multi-subscriber personalized Telegram bot
  - Reads credentials from `.env` (TELEGRAM_TOKEN, SUPABASE_URL, SUPABASE_KEY)
  - Commands: `/start`, `/subscribe`, `/watchlist`, `/settings`, `/pause`, `/resume`, `/stop`, `/help`
  - 3-step subscription wizard (categories → symbols → filing types)
  - Per-subscriber preferences stored in Supabase `subscribers` table:
    - `categories`: list (HIGH / MODERATE / ROUTINE / ALL)
    - `watchlist`: list of NSE/BSE symbols (empty = all companies)
    - `filing_types`: list of filing type filters (empty = all types)
    - `is_active`: bool (pause/resume without losing settings)
  - Inline keyboard menus for all actions
  - Full unsubscribe deletes row from DB

- **migrate_db.py** — One-time Supabase schema migration
  - Checks nse_filings for 4 optional columns: exchange, confidence_pct, evidence, action_window
  - Checks/creates `subscribers` table
  - Auto-migrates via Supabase Management API if `SUPABASE_PAT` is in `.env`
  - Prints SQL to run manually if PAT not available
  - **Run once**: `python migrate_db.py` — confirmed all schema items exist

- **run_forever.bat** — Auto-restart wrapper for nse_monitor.py
  - Restarts after 10s on crash
  - Logs start/stop times, exit codes to `crashes.log`
  - Windows Startup shortcut at `Startup/NSE_Monitor.lnk`

- **run_bot_forever.bat** — Auto-restart wrapper for telegram_bot.py
  - Same pattern as run_forever.bat

### Config Files
- **.env** — All credentials (never committed, see `.env.example`)
  ```
  GEMINI_KEY_1=...
  GEMINI_KEY_2=...
  GEMINI_KEY_3=...
  TELEGRAM_TOKEN=...
  SUPABASE_URL=https://xxx.supabase.co
  SUPABASE_KEY=...
  SUPABASE_PAT=sbp_xxxx   # optional, for migrate_db.py auto-migration
  ```
- **.env.example** — Template for .env (committed)
- **watchlist.json** — Symbol groups for dashboard tagging `{"GROUP": ["SYMBOL1", ...]}`
- **requirements.txt** — Python deps

### Data Files (not committed)
- **NSE_Filings_Log.xlsx** — Excel log (Date, Time, Symbol, Company, Filing Type, Category, Summary, Verdict, Confidence, Reason, Risk, CMP at Filing, Day Change %)
- **NSE_Filings_Log_backup.xlsx** — Auto-backup before each write
- **crashes.log** — Monitor crash/restart history
- **seen_filings.json** — Processed filing IDs (dedup cache)

### Folders
- **Filings/** — Downloaded PDFs organized by symbol

## Supabase Schema

### `nse_filings` table
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| created_at | timestamp | |
| date | text | |
| time | text | |
| symbol | text | |
| company | text | |
| filing_type | text | |
| category | text | HIGH/MODERATE/ROUTINE |
| summary | text | Gemini summary |
| verdict | text | Gemini verdict |
| confidence | text | e.g. "85%" |
| reason | text | Gemini reasoning |
| risk | text | Gemini risk |
| cmp_at_filing | text | Live price at time of filing |
| day_change_pct | text | Day % change at filing |
| exchange | text | NSE or BSE |
| confidence_pct | integer | Numeric confidence score |
| evidence | text | Gemini evidence bullets |
| action_window | text | Gemini suggested action window |

### `subscribers` table
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| chat_id | text UNIQUE | Telegram chat ID |
| username | text | Telegram @username |
| first_name | text | Telegram first name |
| watchlist | text[] | NSE/BSE symbols filter (empty = all) |
| filing_types | text[] | Filing type filter (empty = all) |
| categories | text[] | DEFAULT {"HIGH"} |
| is_active | boolean | DEFAULT true |
| created_at | timestamp | |
| updated_at | timestamp | |

## External Services
- **Gemini AI** — 3 API keys with auto-rotation on 429, model: `gemini-2.0-flash-lite`
- **Telegram Bot** — python-telegram-bot>=20.0, polling mode
- **Supabase** — PostgreSQL DB for filings + subscribers
- **NSE APIs** — Session-based (equities, SME, debt endpoints)
- **BSE API** — Session-based

## How to Run
```powershell
# From project directory (where .env lives):

# Monitor + auto-restart
.\run_forever.bat

# Or directly
python nse_monitor.py

# Telegram bot + auto-restart
.\run_bot_forever.bat

# Or directly
python telegram_bot.py

# Dashboard (separate terminal)
streamlit run dashboard.py

# DB migration (run once)
python migrate_db.py
```

## Classification Keywords
- **HIGH**: acquisition, merger, demerger, amalgamation, scheme, fund raising, joint venture, new order/project, product launch, partnership, order win, agreement, MOU, LOI, buyback, delisting, strategic, wins, awarded, secures, bags, expands, commencement, commercial production, etc.
- **MODERATE**: board meeting, results, financial results, press release, credit rating, appointment, resignation, insider trading, bulk/block deal, investor presentation, analysts meet, trading window, allotment, etc.
- **ROUTINE**: Everything else

## Known Behaviors
- NSE/BSE sessions expire periodically — reset automatically when no data returned
- Excel can get locked if open in Excel desktop — monitor retries 3× with 2s delay
- `~$NSE_Filings_Log.xlsx` lock file = Excel has the file open
- Atomic write: temp → backup → replace prevents dashboard read corruption
- `seen_filings.json` uses exchange-prefixed IDs (`NSE_SYMBOL_seqNo_date`) to dedup across exchanges
- Schema detection at startup warns if optional columns are missing (`python migrate_db.py` to fix)
- `subscribers.txt` (legacy flat file) is no longer used — Supabase `subscribers` table is authoritative

## Dependencies
```
streamlit>=1.55
pandas
openpyxl
python-dotenv
supabase
plotly
google-genai
pdfplumber
requests
schedule
python-telegram-bot>=20.0
```
