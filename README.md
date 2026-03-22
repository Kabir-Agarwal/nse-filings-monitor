# NSE Corporate Filings Monitor

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_AI-2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![NSE](https://img.shields.io/badge/NSE-India-1F4E79?style=for-the-badge)

A real-time intelligence system that monitors **every corporate filing** on the National Stock Exchange of India, classifies impact levels using keyword analysis, runs **AI-powered assessments** on high-impact filings via Google Gemini, and delivers instant **Telegram alerts** with actionable market verdicts.

---

## What It Does

- **Monitors 3 NSE feeds in parallel** (Equities, SME, Debt) every 30 seconds, downloading and classifying every corporate announcement as HIGH / MODERATE / ROUTINE impact
- **AI-powered analysis** via Gemini 2.0 Flash on high-impact filings — delivers BULLISH/BEARISH/NEUTRAL verdicts with confidence levels, risk assessments, and price context
- **Live Bloomberg-style dashboard** built with Streamlit — dark terminal UI with real-time ticker, color-coded filings table, category breakdowns, and system health indicators

---

## Architecture

```
                    +------------------+
                    |   NSE India API  |
                    |  (3 endpoints)   |
                    +--------+---------+
                             |
                    Fetch every 30s (parallel)
                             |
                    +--------v---------+
                    |  nse_monitor.py  |
                    |                  |
                    |  - Classify      |
                    |  - Download PDF  |
                    |  - Extract text  |
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v-----------+
     | Gemini AI  |  |   Excel     |  |   Telegram     |
     | Analysis   |  |   Logger    |  |   Bot Alert    |
     | (HIGH only)|  | (all rows)  |  |  (HIGH only)   |
     +------------+  +------+------+  +----------------+
                            |
                   +--------v---------+
                   |  dashboard.py    |
                   |  (Streamlit)     |
                   |                  |
                   |  Dark terminal   |
                   |  Live refresh    |
                   |  Color-coded     |
                   +------------------+
```

---

## Screenshots

| Dashboard - Terminal View | Telegram Alert |
|:---:|:---:|
| ![Dashboard](screenshots/dashboard.png) | ![Telegram](screenshots/telegram.png) |

> *Add screenshots to a `screenshots/` folder*

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Python 3.11+ | Core monitor engine |
| **Data Source** | NSE India API | Corporate announcements feed |
| **AI Engine** | Google Gemini 2.0 Flash Lite | Filing analysis & verdicts |
| **Alerts** | Telegram Bot API | Real-time mobile notifications |
| **Dashboard** | Streamlit | Live web-based monitoring UI |
| **Storage** | OpenPyXL / Excel | Color-coded filing logs |
| **PDF Parser** | pdfplumber | Extract filing document text |
| **Scheduler** | schedule | 30-second polling loop |
| **Resilience** | run_forever.bat | Auto-restart on crash with logging |

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/nse-filings-monitor.git
cd nse-filings-monitor
pip install requests schedule openpyxl pdfplumber google-genai streamlit pyngrok
```

### 2. Configure API Keys

Edit `nse_monitor.py` and set your keys:

```python
GEMINI_KEYS = ["your-gemini-key-1", "your-gemini-key-2"]
TELEGRAM_TOKEN = "your-telegram-bot-token"
```

Add your Telegram chat ID to `subscribers.txt`:
```
your_chat_id
```

### 3. Run

```bash
# Terminal 1 — Start the monitor
python nse_monitor.py

# Terminal 2 — Start the dashboard
streamlit run dashboard.py
```

### 4. Auto-Restart (Windows)

```bash
# Use the included batch file for crash resilience
run_forever.bat
```

To auto-start on boot, place a shortcut to `run_forever.bat` in:
```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

---

## Filing Classification

| Category | Trigger Keywords | Action |
|----------|-----------------|--------|
| **HIGH** | Acquisition, merger, demerger, fund raising, JV, new order, buyback, delisting | Gemini AI analysis + Telegram alert + Excel log |
| **MODERATE** | Board meeting, results, credit rating, appointment, investor presentation | Excel log only |
| **ROUTINE** | Everything else | Excel log only |

---

## Project Structure

```
nse-filings-monitor/
├── nse_monitor.py          # Core monitor engine
├── dashboard.py            # Streamlit terminal dashboard
├── run_forever.bat         # Auto-restart wrapper
├── NSE_Filings_Log.xlsx    # Filing records (auto-created)
├── seen_filings.json       # Duplicate prevention
├── subscribers.txt         # Telegram chat IDs
├── crashes.log             # Crash/restart history
├── credentials.json        # Google API credentials
├── Filings/                # Downloaded PDFs by symbol
│   ├── RELIANCE/
│   ├── TATASTEEL/
│   └── .../
└── README.md
```

---

## How It Works

1. **Session Warmup** — Mimics browser behavior to establish a valid NSE session with cookies
2. **Parallel Fetch** — Hits 3 NSE API endpoints concurrently (equities, SME, debt)
3. **Deduplication** — Tracks seen filings in JSON to process each announcement exactly once
4. **Classification** — Keyword matching against filing subject + PDF content
5. **AI Analysis** — HIGH impact filings sent to Gemini with price context for market verdict
6. **Alert Dispatch** — Formatted Telegram message with verdict, confidence, and risk assessment
7. **Atomic Logging** — Writes to temp file, backs up original, then replaces (prevents corruption)
8. **Dashboard** — Reads Excel via temp copy, renders with dark terminal styling

---

## License

MIT

---

<p align="center">
  Built for tracking NSE corporate actions in real-time.<br>
  <strong>Not financial advice.</strong> Use for research and educational purposes.
</p>
