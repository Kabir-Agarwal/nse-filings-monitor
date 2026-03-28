# NSE + BSE Corporate Filings Monitor

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.55-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_AI-2.0_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)
![NSE](https://img.shields.io/badge/NSE-India-1F4E79?style=for-the-badge)
![BSE](https://img.shields.io/badge/BSE-India-DC3545?style=for-the-badge)

A real-time intelligence system that monitors **every corporate filing** on both the **National Stock Exchange (NSE)** and **Bombay Stock Exchange (BSE)** of India, classifies impact levels, runs **AI-powered assessments** with structured confidence scores via Google Gemini, and delivers instant **Telegram alerts** with actionable market verdicts.

---

## Features

### Dual Exchange Monitoring (NSE + BSE)
- **NSE**: Fetches from 3 parallel feeds (Equities, SME, Debt) every 30 seconds
- **BSE**: Fetches corporate announcements via BSE India API in parallel
- Deduplication across both exchanges with exchange-prefixed filing IDs
- Exchange-tagged alerts and Supabase logging

### AI-Powered Analysis with Structured Confidence Scores
- **Gemini 2.0 Flash** analyzes HIGH-impact filings and returns structured JSON
- **Confidence score (0-100%)** with progress bar visualization
- **Evidence bullets** — 3-4 specific data points extracted from the filing
- **Risk factors** — specific risks identified per filing
- **Action window** — IMMEDIATE / TODAY / MONITOR classification
- 3 API keys with automatic rotation on rate limits

### Filing Intelligence Chatbot
- **NotebookLM-style chatbot** built into the dashboard
- Queries last 500 HIGH filings with full evidence context
- Loads PDF text from downloaded filings for deeper context
- Responds with **exact citations** like `[HDFC filing Mar 24]`
- Handles complex queries: sector comparisons, risk/reward analysis, trend detection

### Live Dashboard
- **Screener + Moneycontrol style UI** built with Streamlit
- **NSE/BSE/Both filter** in sidebar
- Category filter (HIGH / MODERATE / ROUTINE)
- Confidence % progress bars for HIGH filings
- Evidence bullet points auto-displayed under each HIGH filing
- Auto-refreshes every 30 seconds
- Paginated data loading — fetches ALL filings (no 1000-row limit)

### Telegram Alerts
- Formatted alerts with verdict, confidence %, evidence bullets
- Exchange-tagged (NSE/BSE) in every alert
- Price movement alerts (>2% within 10 min of filing)
- Watchlist alerts for tracked stocks

---

## Architecture

```
              +------------------+     +------------------+
              |   NSE India API  |     |   BSE India API  |
              |  (3 endpoints)   |     |  (announcements) |
              +--------+---------+     +--------+---------+
                       |                        |
              Fetch every 30s (parallel threads)
                       |                        |
              +--------v------------------------v---------+
              |            nse_monitor.py                  |
              |                                           |
              |  - Classify (keyword matching)            |
              |  - Download PDF                           |
              |  - Extract text (pdfplumber)              |
              |  - Gemini AI analysis (structured JSON)   |
              +--------+----------------------------------+
                       |
        +--------------+--------------+
        |              |              |
+-------v----+  +-----v-------+  +---v-----------+
| Gemini AI  |  |  Supabase   |  |  Telegram     |
| Structured |  |  Database   |  |  Bot Alert    |
| JSON + %   |  | (all rows)  |  | (HIGH only)   |
+------------+  +------+------+  +---------------+
                       |
              +--------v---------+
              |  dashboard.py    |
              |  (Streamlit)     |
              |                  |
              |  NSE+BSE filter  |
              |  Confidence bars |
              |  Evidence bullets|
              |  Filing Chatbot  |
              +------------------+
```

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Backend** | Python 3.11+ | Core monitor engine |
| **Data Source** | NSE + BSE India APIs | Corporate announcements feeds |
| **AI Engine** | Google Gemini 2.0 Flash Lite | Filing analysis, chatbot |
| **Database** | Supabase (PostgreSQL) | Filing storage with exchange tagging |
| **Alerts** | Telegram Bot API | Real-time mobile notifications |
| **Dashboard** | Streamlit | Live web-based monitoring UI |
| **PDF Parser** | pdfplumber | Extract filing document text |
| **Scheduler** | schedule | 30-second polling loop |
| **Resilience** | run_forever.bat | Auto-restart on crash with logging |

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/nse-filings-monitor.git
cd nse-filings-monitor
pip install requests schedule pdfplumber google-genai streamlit supabase python-dotenv plotly pandas
```

### 2. Configure API Keys

Create a `.env` file:
```env
GEMINI_KEY_1=your-gemini-key-1
GEMINI_KEY_2=your-gemini-key-2
GEMINI_KEY_3=your-gemini-key-3
TELEGRAM_TOKEN=your-telegram-bot-token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-service-role-key
```

### 3. Database Migration

Run these SQL commands in Supabase SQL Editor to add new columns:
```sql
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS exchange TEXT DEFAULT 'NSE';
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS confidence_pct INTEGER;
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS evidence TEXT;
ALTER TABLE nse_filings ADD COLUMN IF NOT EXISTS action_window TEXT;
```

Or run: `python migrate_db.py` to check column status.

### 4. Run

```bash
# Terminal 1 — Start the monitor
python nse_monitor.py

# Terminal 2 — Start the dashboard
streamlit run dashboard.py
```

### 5. Auto-Restart (Windows)

```bash
run_forever.bat
```

---

## Filing Classification

| Category | Trigger Keywords | Action |
|----------|-----------------|--------|
| **HIGH** | Acquisition, merger, demerger, fund raising, JV, new order, buyback, delisting | Gemini AI analysis (structured JSON) + Telegram alert + Supabase log |
| **MODERATE** | Board meeting, results, credit rating, appointment, investor presentation | Supabase log only |
| **ROUTINE** | Everything else | Supabase log only |

---

## Gemini AI Response Format

HIGH filings are analyzed with structured JSON output:

```json
{
  "summary": "Company announced acquisition of XYZ for Rs 500 Cr",
  "verdict": "BULLISH",
  "confidence_pct": 78,
  "evidence": [
    "Strategic acquisition in high-growth segment",
    "Purchase price at 1.2x book value — reasonable",
    "Company has strong balance sheet to fund deal"
  ],
  "risks": [
    "Integration risk with acquired entity",
    "Regulatory approvals still pending"
  ],
  "action_window": "TODAY",
  "reason": "Value-accretive acquisition at reasonable valuation"
}
```

---

## Chatbot Usage

The Filing Intelligence Chatbot (in the dashboard) can answer questions like:

- "Which HIGH filing today has the best risk/reward?"
- "Why is TATASTEEL bearish?"
- "Show all pharma HIGH filings this week"
- "Compare HDFC and ICICI filings this month"
- "What BSE filings came in today?"

---

## Project Structure

```
nse-filings-monitor/
├── nse_monitor.py          # Core monitor (NSE + BSE)
├── dashboard.py            # Streamlit dashboard + chatbot
├── migrate_db.py           # Database migration helper
├── run_forever.bat         # Auto-restart wrapper
├── seen_filings.json       # Duplicate prevention (exchange-prefixed)
├── subscribers.txt         # Telegram chat IDs
├── watchlist.json          # Watchlist groups
├── .env                    # API keys (not committed)
├── .streamlit/
│   ├── config.toml         # Streamlit theme config
│   └── secrets.toml        # Streamlit secrets (not committed)
├── Filings/                # Downloaded PDFs by symbol
│   ├── RELIANCE/
│   ├── TATASTEEL/
│   └── .../
└── README.md
```

---

## License

MIT

---

<p align="center">
  Built for tracking NSE + BSE corporate actions in real-time.<br>
  <strong>Not financial advice.</strong> Use for research and educational purposes.
</p>
