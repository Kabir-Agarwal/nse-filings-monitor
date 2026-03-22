# NSE Corporate Filings Monitor

## Project Purpose
Real-time NSE (National Stock Exchange of India) corporate filings monitor that:
- Fetches ALL corporate announcements from NSE every 30 seconds
- Classifies them as HIGH / MODERATE / ROUTINE impact
- Runs Gemini AI analysis on HIGH impact filings
- Sends Telegram alerts for HIGH impact filings
- Logs everything to a color-coded Excel file
- Displays a live Streamlit dashboard for monitoring

## System Status
- **Monitor**: Running (confirmed PID 20156)
- **Auto-restart**: run_forever.bat logs crashes to `crashes.log` with timestamps and exit codes
- **Windows Startup**: Shortcut created at `Startup/NSE_Monitor.lnk` — auto-launches on reboot (minimized)
- **All systems operational**

## Files

### Core
- **nse_monitor.py** — Main monitor script (runs continuously)
  - Fetches filings from 3 NSE APIs in parallel (equities, SME, debt)
  - Keyword-based classification (HIGH/MODERATE/ROUTINE)
  - Downloads filing PDFs to `Filings/<SYMBOL>/` folders
  - Gemini 2.0 Flash Lite analysis for HIGH filings (3 API keys with rotation)
  - Telegram alerts for HIGH filings
  - Atomic Excel writes: saves to `_temp.xlsx`, backs up to `_backup.xlsx`, then replaces main file
  - Runs on 30-second schedule via `schedule` library

- **dashboard.py** — Streamlit dashboard (dark Bloomberg-style terminal UI)
  - Auto-refreshes every 30s via `@st.fragment(run_every=30)`
  - Dark theme with custom CSS, monospace fonts, terminal aesthetic
  - Live ticker bar showing most recent filing
  - Pulsing green "SYSTEM LIVE" indicator
  - Color-coded rows: GREEN (#00B050) for HIGH, YELLOW (#FFD700) for MODERATE
  - Stats badges, sidebar filters, market open/closed indicator
  - Category breakdown bar chart
  - Reads Excel via temp file copy; falls back to `_backup.xlsx` on BadZipFile
  - Display columns: Time, Symbol, Company, Filing Type, Category, Verdict, Confidence, CMP at Filing, Day Change %
  - Hidden columns: Date, Summary, Reason, Risk, PDF Path

- **run_forever.bat** — Auto-restart wrapper with crash logging
  - Restarts nse_monitor.py after 10s on crash
  - Logs start/stop times, exit codes, and crash reasons to `crashes.log`
  - Windows Startup shortcut ensures auto-launch on reboot

### Data Files
- **NSE_Filings_Log.xlsx** — Main Excel log (13 columns: Date, Time, Symbol, Company, Filing Type, Category, Summary, Verdict, Confidence, Reason, Risk, CMP at Filing, Day Change %)
- **NSE_Filings_Log_backup.xlsx** — Auto-backup created before each write
- **crashes.log** — Monitor crash/restart history with timestamps
- **seen_filings.json** — Tracks processed filing IDs to avoid duplicates (format: `SYMBOL_seqNo_date`)
- **subscribers.txt** — Telegram chat IDs for alerts (currently: 1281388903)
- **credentials.json** — Google API credentials

### Folders
- **Filings/** — Downloaded PDF filings organized by symbol subfolder

## External Services
- **Gemini AI** — 3 API keys with auto-rotation on 429 rate limits, model: `gemini-2.0-flash-lite`
- **Telegram Bot** — Token in nse_monitor.py, sends formatted alerts with verdict/confidence/price
- **NSE APIs** — Session-based with cookie warmup (hits nseindia.com first, then API endpoints)

## How to Run
```bash
# Monitor (keeps running, auto-restarts on crash)
run_forever.bat

# Or directly
python nse_monitor.py

# Dashboard (separate terminal)
streamlit run dashboard.py
```

## Excel Structure
Row colors applied via openpyxl:
- HIGH: Green fill (#00B050)
- MODERATE: Yellow fill (#FFFF00)
- ROUTINE: No fill

Headers styled with dark blue (#1F4E79) background, white bold font.

## Classification Keywords
- **HIGH**: acquisition, merger, demerger, scheme, fund raising, joint venture, new order, product launch, partnership, order win, buyback, delisting, etc.
- **MODERATE**: board meeting, results, press release, credit rating, appointment, resignation, investor presentation, allotment, etc.
- **ROUTINE**: Everything else

## Known Behaviors
- NSE sessions expire periodically — session resets automatically when no data is returned
- Excel file can get locked if opened in Excel desktop app — monitor retries 3 times with 2s delay
- The `~$NSE_Filings_Log.xlsx` lock file indicates Excel has the file open
- Atomic write pattern (temp -> backup -> replace) prevents corruption from simultaneous dashboard reads

## Dependencies
```
requests, schedule, openpyxl, pdfplumber, google-genai, streamlit, pyngrok
```
