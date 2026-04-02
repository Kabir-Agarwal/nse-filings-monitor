import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from dotenv import load_dotenv
load_dotenv()

import requests
import json
import time
import os
import shutil
import schedule
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from google import genai
import pdfplumber
from supabase import create_client

# ============================================================
# CONFIGURATION
# ============================================================
GEMINI_KEYS = [
    os.environ.get("GEMINI_KEY_1", ""),
    os.environ.get("GEMINI_KEY_2", ""),
    os.environ.get("GEMINI_KEY_3", ""),
]
GEMINI_KEYS = [k for k in GEMINI_KEYS if k]  # Remove empty keys
gemini_key_index = 0
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
BASE_FOLDER = r"C:\Users\LENOVO\Desktop\linkdin projects"
SUBSCRIBERS_FILE = os.path.join(BASE_FOLDER, "subscribers.txt")
FILINGS_FOLDER = os.path.join(BASE_FOLDER, "Filings")
SEEN_FILINGS_FILE = os.path.join(BASE_FOLDER, "seen_filings.json")
WATCHLIST_FILE = os.path.join(BASE_FOLDER, "watchlist.json")

# Price movement tracking: {symbol: {"price": float, "time": datetime}}
price_tracker = {}

# Schema flags — detected at startup
HAS_EXCHANGE_COL = False
HAS_CONFIDENCE_PCT_COL = False
HAS_EVIDENCE_COL = False
HAS_ACTION_WINDOW_COL = False

# ============================================================
# GEMINI SETUP
# ============================================================
gemini_client = genai.Client(api_key=GEMINI_KEYS[0])

def rotate_gemini_key():
    global gemini_key_index, gemini_client
    gemini_key_index = (gemini_key_index + 1) % len(GEMINI_KEYS)
    gemini_client = genai.Client(api_key=GEMINI_KEYS[gemini_key_index])
    print(f"   Rotated to Gemini key #{gemini_key_index + 1}")

# ============================================================
# SUPABASE SETUP
# ============================================================
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def detect_schema():
    """Check which optional columns exist in Supabase."""
    global HAS_EXCHANGE_COL, HAS_CONFIDENCE_PCT_COL, HAS_EVIDENCE_COL, HAS_ACTION_WINDOW_COL
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    for col, flag_name in [
        ("exchange", "HAS_EXCHANGE_COL"),
        ("confidence_pct", "HAS_CONFIDENCE_PCT_COL"),
        ("evidence", "HAS_EVIDENCE_COL"),
        ("action_window", "HAS_ACTION_WINDOW_COL"),
    ]:
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/nse_filings?select={col}&limit=1",
                headers=headers, timeout=10
            )
            globals()[flag_name] = (r.status_code == 200)
        except Exception:
            globals()[flag_name] = False
    print(f"   Schema: exchange={HAS_EXCHANGE_COL}, confidence_pct={HAS_CONFIDENCE_PCT_COL}, evidence={HAS_EVIDENCE_COL}, action_window={HAS_ACTION_WINDOW_COL}")
    if not all([HAS_EXCHANGE_COL, HAS_CONFIDENCE_PCT_COL, HAS_EVIDENCE_COL, HAS_ACTION_WINDOW_COL]):
        print("   ⚠️  Some columns missing. Run: python migrate_db.py")

# ============================================================
# GLOBAL SESSIONS
# ============================================================
nse_session = None
bse_session = None

# ============================================================
# FOLDER SETUP
# ============================================================
def setup():
    os.makedirs(FILINGS_FOLDER, exist_ok=True)
    detect_schema()
    print("   ✅ Supabase connected.")

# ============================================================
# CLASSIFY FILINGS
# ============================================================
def classify_filing(subject, pdf_text=""):
    combined = (subject + " " + pdf_text[:500]).lower()
    high_impact = [
        "acquisition", "merger", "demerger", "amalgamation", "scheme of arrangement",
        "scheme", "fund rais", "fundrais", "joint venture", "product launch",
        "new order", "new project", "recognition", "disinvestment", "diversification",
        "operational update", "commencement", "commercial production", "agreement",
        "partnership", "nvidia", "wins", "awarded", "secures", "bags",
        "signs mou", "launches", "expands", "enters agreement", "strategic",
        "order win", "contract win", "letter of intent", "loi", "mou signed",
        "jv", "takeover", "buyback", "delisting"
    ]
    moderate = [
        "board meeting", "results", "financial results", "press release",
        "general updates", "update", "credit rating", "change in management",
        "appointment", "resignation", "insider trading", "bulk deal", "block deal",
        "investor presentation", "analysts meet", "institutional investor",
        "con. call", "trading window", "allotment"
    ]
    for k in high_impact:
        if k in combined:
            return "HIGH"
    for k in moderate:
        if k in combined:
            return "MODERATE"
    return "ROUTINE"

# ============================================================
# SEEN FILINGS (with exchange prefix)
# ============================================================
def load_seen():
    if os.path.exists(SEEN_FILINGS_FILE):
        with open(SEEN_FILINGS_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILINGS_FILE, "w") as f:
        json.dump(list(seen), f)

# ============================================================
# WATCHLIST
# ============================================================
def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return {}

def is_watchlisted(symbol):
    watchlist = load_watchlist()
    for group, symbols in watchlist.items():
        if symbol in symbols:
            return True, group
    return False, None

# ============================================================
# PRICE MOVEMENT TRACKER
# ============================================================
def track_price(symbol, price):
    """Store baseline CMP at time of filing for later comparison."""
    try:
        base_price = float(str(price).replace(",", ""))
        price_tracker[symbol] = {
            "price": base_price,
            "time": datetime.now(),
        }
        print(f"   Tracking {symbol} baseline: Rs {base_price}")
    except (ValueError, TypeError):
        pass

def check_price_movements():
    """Check if tracked HIGH filing stocks moved >2% within 10 min."""
    if not price_tracker:
        return
    session = get_nse_session()
    now = datetime.now()
    expired = []
    for symbol, data in list(price_tracker.items()):
        elapsed = (now - data["time"]).total_seconds()
        if elapsed < 600:  # Not yet 10 minutes
            continue
        expired.append(symbol)
        try:
            current_price, _ = get_nse_price(session, symbol)
            if current_price == "N/A":
                continue
            current = float(str(current_price).replace(",", ""))
            baseline = data["price"]
            if baseline <= 0:
                continue
            pct_change = ((current - baseline) / baseline) * 100
            if abs(pct_change) >= 2.0:
                direction = "+" if pct_change > 0 else ""
                print(f"   PRICE ALERT: {symbol} moved {direction}{pct_change:.1f}% since filing!")
                send_price_alert(symbol, baseline, current, pct_change)
        except Exception as e:
            print(f"   Price check error for {symbol}: {e}")
    for sym in expired:
        del price_tracker[sym]

def send_price_alert(symbol, baseline, current, pct_change):
    """Send follow-up Telegram alert for significant price movement."""
    direction = "+" if pct_change > 0 else ""
    arrow = "\U0001f4c8" if pct_change > 0 else "\U0001f4c9"
    message = f"""{arrow} PRICE MOVING: {symbol} {direction}{pct_change:.1f}%
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f4b0 CMP at Filing: Rs {baseline:.2f}
\U0001f4b0 Current CMP: Rs {current:.2f}
\U0001f4ca Movement: {direction}{pct_change:.1f}%
\u23f0 Within 10 min of filing
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u26a1 Post-filing price action detected"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chat_ids = get_matching_subscribers("HIGH", symbol, "price alert")
    for chat_id in chat_ids:
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        except Exception as e:
            print(f"   Price alert Telegram error: {e}")

# ============================================================
# TELEGRAM SUBSCRIBERS
# ============================================================
def load_subscribers():
    """Load fallback subscribers from local file."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        with open(SUBSCRIBERS_FILE, "w") as f:
            f.write("1281388903\n")
    with open(SUBSCRIBERS_FILE, "r") as f:
        ids = [line.strip() for line in f.readlines() if line.strip()]
    return ids


def get_all_active_subscribers():
    """Return chat_ids for all active Supabase subscribers. Falls back to file."""
    try:
        r = supabase.table("subscribers").select("chat_id").eq("is_active", True).execute()
        if r.data:
            return [row["chat_id"] for row in r.data]
    except Exception as e:
        print(f"   Subscriber fetch error: {e}")
    return load_subscribers()


def get_matching_subscribers(category: str, symbol: str, filing_type: str):
    """
    Return chat_ids of active subscribers whose preferences match this filing.
    Matching rules:
      - category must be in subscriber's categories list
      - if subscriber watchlist is non-empty, symbol must be in it
      - if subscriber filing_types is non-empty, filing_type must contain one of them
    Falls back to subscribers.txt if Supabase table is empty or unreachable.
    """
    try:
        r = supabase.table("subscribers").select("*").eq("is_active", True).execute()
        if not r.data:
            return load_subscribers()

        symbol_up = symbol.upper()
        ft_lower = filing_type.lower()
        matching = []
        for sub in r.data:
            # Category filter
            sub_cats = sub.get("categories") or ["HIGH"]
            if category not in sub_cats and "ALL" not in sub_cats:
                continue

            # Watchlist filter (empty = all symbols)
            watchlist = [s.upper() for s in (sub.get("watchlist") or [])]
            if watchlist and symbol_up not in watchlist:
                continue

            # Filing type filter (empty = all types)
            sub_fts = [ft.lower() for ft in (sub.get("filing_types") or [])]
            if sub_fts and not any(ft in ft_lower for ft in sub_fts):
                continue

            matching.append(sub["chat_id"])

        # If no personalized subscribers match, fall back to file so alerts are never silent
        return matching if matching else load_subscribers()

    except Exception as e:
        print(f"   Subscriber query error: {e}")
        return load_subscribers()

# ============================================================
# NSE SESSION
# ============================================================
def create_nse_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    })
    try:
        print("   Warming up NSE session...")
        session.get("https://www.nseindia.com", timeout=15)
        time.sleep(5)
        session.get("https://www.nseindia.com/market-data/live-equity-market", timeout=10)
        time.sleep(5)
        session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/market-data/live-equity-market",
            "X-Requested-With": "XMLHttpRequest"
        })
        print("   ✅ NSE session ready.")
    except Exception as e:
        print(f"   Session setup warning: {e}")
    return session

def get_nse_session():
    global nse_session
    if nse_session is None:
        nse_session = create_nse_session()
    return nse_session

def reset_nse_session():
    global nse_session
    print("   Resetting NSE session...")
    nse_session = None

# ============================================================
# BSE SESSION
# ============================================================
def create_bse_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.bseindia.com/corporates/ann.html",
        "Origin": "https://www.bseindia.com",
    })
    try:
        print("   Warming up BSE session...")
        session.get("https://www.bseindia.com", timeout=15)
        time.sleep(2)
        print("   ✅ BSE session ready.")
    except Exception as e:
        print(f"   BSE session setup warning: {e}")
    return session

def get_bse_session():
    global bse_session
    if bse_session is None:
        bse_session = create_bse_session()
    return bse_session

def reset_bse_session():
    global bse_session
    print("   Resetting BSE session...")
    bse_session = None

# ============================================================
# FETCH NSE FILINGS (3 PARALLEL CALLS)
# ============================================================
def fetch_nse_filings(session):
    today = datetime.now().strftime("%d-%m-%Y")
    urls = {
        "equities": f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={today}&to_date={today}",
        "sme": f"https://www.nseindia.com/api/corporate-announcements?index=sme&from_date={today}&to_date={today}",
        "debt": f"https://www.nseindia.com/api/corporate-announcements?index=debt&from_date={today}&to_date={today}",
    }
    headers = dict(session.headers)
    headers.pop("Accept-Encoding", None)

    counts = {}

    def fetch_one(name_url):
        name, url = name_url
        try:
            response = session.get(url, timeout=15, headers=headers)
            if response.status_code == 200 and len(response.text) > 100:
                data = response.json()
                counts[name] = len(data)
                return data
        except Exception as e:
            print(f"   Error fetching NSE {name}: {e}")
        counts[name] = 0
        return []

    combined = []
    seen_ids = set()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch_one, urls.items()))
    for filings in results:
        for f in filings:
            fid = f"{f.get('symbol', '')}_{f.get('seqNo', '')}_{f.get('an_dt', '')}"
            if fid not in seen_ids:
                seen_ids.add(fid)
                combined.append(f)

    eq = counts.get("equities", 0)
    sm = counts.get("sme", 0)
    dt = counts.get("debt", 0)
    print(f"   ✅ NSE: {len(combined)} filings (equities: {eq}, sme: {sm}, debt: {dt})")
    return combined

# ============================================================
# FETCH BSE FILINGS
# ============================================================
def fetch_bse_filings(session):
    """Fetch corporate announcements from BSE India API."""
    today = datetime.now().strftime("%d/%m/%Y")
    url = (
        f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
        f"?strCat=-1&strPrevDate={today}&strScrip=&strSearch=&Is498=&strType=C"
    )
    try:
        response = session.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            table = data.get("Table", [])
            print(f"   ✅ BSE: {len(table)} filings fetched")
            return table
    except Exception as e:
        print(f"   Error fetching BSE: {e}")
    return []

def map_bse_filing(item):
    """Map BSE API fields to our standard schema."""
    # BSE fields: SCRIP_CD, SLONGNAME, NEWSSUB, NEWS_DT, ATTACHMENTNAME, NSURL,
    #             DT_TM, HEADLINE, CATEGORYNAME, SUBCATNAME, NSEID
    symbol = (item.get("NSEID") or item.get("SCRIP_CD", "")).strip().upper()
    company = (item.get("SLONGNAME") or symbol).strip()
    subject = (item.get("NEWSSUB") or item.get("HEADLINE") or "").strip()
    news_dt = item.get("NEWS_DT", "")
    news_id = item.get("NEWSID") or item.get("ANNOESSION_ID") or item.get("NEWS_DT", "")
    attach = item.get("ATTACHMENTNAME", "")
    nsurl = item.get("NSURL", "")

    # Build attachment URL
    attach_url = ""
    if attach:
        attach_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{attach}"
    elif nsurl:
        attach_url = nsurl

    return {
        "symbol": symbol,
        "company": company,
        "desc": subject,
        "subject": subject,
        "attchmntFile": attach_url,
        "an_dt": news_dt,
        "seqNo": str(news_id),
        "_bse_raw": item,
    }

# ============================================================
# GET LIVE STOCK PRICE (NSE)
# ============================================================
def get_nse_price(session, symbol):
    try:
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            price_info = data.get("priceInfo", {})
            price = price_info.get("lastPrice", "N/A")
            change_pct = price_info.get("pChange", "N/A")
            return price, change_pct
    except Exception as e:
        print(f"   NSE price fetch error for {symbol}: {e}")
    return "N/A", "N/A"

# ============================================================
# GET LIVE STOCK PRICE (BSE)
# ============================================================
def get_bse_price(session, scrip_code):
    """Get live price from BSE. Falls back to N/A if unavailable."""
    try:
        url = f"https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/w?Ession=&scripcode={scrip_code}"
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            header = data.get("Header", {})
            price = header.get("LTP") or header.get("CurrRate") or "N/A"
            change_pct = header.get("ChgPer") or header.get("Chg") or "N/A"
            return price, change_pct
    except Exception as e:
        print(f"   BSE price fetch error for {scrip_code}: {e}")
    return "N/A", "N/A"

# ============================================================
# DOWNLOAD PDF
# ============================================================
def download_pdf(session, filing, symbol, exchange="NSE"):
    try:
        attach_url = filing.get("attchmntFile", "") or filing.get("attachment", "")
        if not attach_url:
            return None
        if not attach_url.startswith("http"):
            if exchange == "BSE":
                attach_url = "https://www.bseindia.com" + attach_url
            else:
                attach_url = "https://www.nseindia.com" + attach_url

        company_folder = os.path.join(FILINGS_FOLDER, symbol)
        os.makedirs(company_folder, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        subject_clean = (filing.get("desc", "") or filing.get("subject", "filing"))[:40]
        subject_clean = "".join(c for c in subject_clean if c.isalnum() or c in " -_").strip()
        filename = f"{exchange}_{date_str}_{subject_clean}.pdf"
        filepath = os.path.join(company_folder, filename)

        pdf_session = requests.Session()
        pdf_session.headers.update(session.headers)
        pdf_session.cookies.update(session.cookies)
        response = pdf_session.get(attach_url, timeout=20)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(response.content)
            print(f"   PDF saved: {filename}")
            return filepath
    except Exception as e:
        print(f"   PDF download error: {e}")
    return None

# ============================================================
# EXTRACT TEXT FROM PDF
# ============================================================
def extract_pdf_text(pdf_path):
    try:
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:5]:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text[:4000]
    except Exception as e:
        print(f"   PDF text extraction error: {e}")
    return ""

# ============================================================
# GEMINI ANALYSIS (HIGH FILINGS ONLY) — STRUCTURED JSON
# ============================================================
def analyze_with_gemini(filing_text, subject, symbol, price, change_pct, exchange="NSE"):
    prompt = f"""You are a senior Indian equity analyst. Analyze this {exchange} corporate filing and give a sharp market impact assessment.

COMPANY: {symbol}
EXCHANGE: {exchange}
FILING TYPE: {subject}
CURRENT PRICE: Rs {price}
TODAY'S CHANGE: {change_pct}%

FILING CONTENT:
{filing_text if filing_text else "[Full PDF not available — assess based on filing type and subject only]"}

ASSESSMENT RULES:
- Acquisition: Bullish if strategic fit, Bearish if overpriced or debt-funded
- Fund Raising (QIP/Rights/NCD): Mildly Bearish (dilution) unless strong growth story
- Merger/Demerger: Usually Bullish if value unlocking, check terms
- Joint Venture: Bullish if strong partner or new market
- New Order/Project: Bullish — bigger order = stronger signal
- Product Launch: Bullish if large addressable market
- Business/Operational Update: Depends on content — read carefully
- Disinvestment: Bullish if monetizing non-core assets
- If stock already up more than 5% today — likely priced in, reduce confidence
- If stock is flat today — genuine surprise, increase confidence

Respond ONLY with valid JSON (no markdown, no backticks). Use this exact structure:
{{
  "summary": "3 lines max, plain English, what the company actually announced",
  "verdict": "BULLISH or BEARISH or NEUTRAL",
  "confidence_pct": 75,
  "evidence": [
    "Specific evidence point 1 from the filing",
    "Specific evidence point 2 with data/numbers",
    "Market context point 3"
  ],
  "risks": [
    "Primary risk factor",
    "Secondary risk to watch"
  ],
  "action_window": "IMMEDIATE or TODAY or MONITOR",
  "reason": "One sentence summary of why this verdict"
}}

Rules for confidence_pct (0-100):
- 80-100: Clear catalyst with specific numbers, strong strategic fit
- 60-79: Good signal but some ambiguity in details
- 40-59: Mixed signals, could go either way
- 20-39: Weak signal, mostly noise
- 0-19: No meaningful market impact"""

    for attempt in range(len(GEMINI_KEYS)):
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "429" in error_str and attempt < len(GEMINI_KEYS) - 1:
                print(f"   Gemini key #{gemini_key_index + 1} rate limited. Rotating...")
                rotate_gemini_key()
            else:
                print(f"   Gemini error: {e}")
                break
    return json.dumps({
        "summary": subject,
        "verdict": "NEUTRAL",
        "confidence_pct": 20,
        "evidence": ["Analysis unavailable"],
        "risks": ["Review manually"],
        "action_window": "MONITOR",
        "reason": "Analysis unavailable"
    })

# ============================================================
# PARSE GEMINI RESPONSE (JSON)
# ============================================================
def parse_gemini(text):
    result = {
        "summary": "See filing",
        "verdict": "NEUTRAL",
        "confidence": "LOW",
        "confidence_pct": 30,
        "reason": "N/A",
        "risk": "Review manually",
        "evidence": "[]",
        "action_window": "MONITOR",
    }

    # Try JSON parse first
    try:
        # Strip markdown code fences if present
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()

        data = json.loads(clean)
        result["summary"] = data.get("summary", result["summary"])
        result["verdict"] = data.get("verdict", result["verdict"]).upper()
        result["confidence_pct"] = int(data.get("confidence_pct", 30))
        result["reason"] = data.get("reason", result["reason"])
        result["action_window"] = data.get("action_window", "MONITOR")

        # Map confidence_pct to HIGH/MEDIUM/LOW
        pct = result["confidence_pct"]
        if pct >= 65:
            result["confidence"] = "HIGH"
        elif pct >= 40:
            result["confidence"] = "MEDIUM"
        else:
            result["confidence"] = "LOW"

        # Evidence as JSON string for Supabase storage
        evidence = data.get("evidence", [])
        if isinstance(evidence, list):
            result["evidence"] = json.dumps(evidence)
        else:
            result["evidence"] = json.dumps([str(evidence)])

        # Risk — combine risks list into single string
        risks = data.get("risks", [])
        if isinstance(risks, list) and risks:
            result["risk"] = " | ".join(risks)
        elif isinstance(risks, str):
            result["risk"] = risks

        return result
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: parse old-style text format
    for line in text.strip().split("\n"):
        if line.startswith("SUMMARY:"):
            result["summary"] = line.replace("SUMMARY:", "").strip()
        elif line.startswith("VERDICT:"):
            result["verdict"] = line.replace("VERDICT:", "").strip().upper()
        elif line.startswith("CONFIDENCE:"):
            conf = line.replace("CONFIDENCE:", "").strip().upper()
            result["confidence"] = conf
            if conf == "HIGH":
                result["confidence_pct"] = 75
            elif conf == "MEDIUM":
                result["confidence_pct"] = 50
            else:
                result["confidence_pct"] = 25
        elif line.startswith("REASON:"):
            result["reason"] = line.replace("REASON:", "").strip()
        elif line.startswith("RISK:"):
            result["risk"] = line.replace("RISK:", "").strip()
    return result

# ============================================================
# SEND TELEGRAM
# ============================================================
def send_telegram(filing, symbol, company, analysis, price, change_pct, exchange="NSE"):
    verdict = analysis["verdict"]
    if "BULLISH" in verdict:
        verdict_emoji = "BULLISH \U0001f7e2"
    elif "BEARISH" in verdict:
        verdict_emoji = "BEARISH \U0001f534"
    else:
        verdict_emoji = "NEUTRAL \U0001f7e1"

    conf = analysis["confidence"]
    conf_pct = analysis.get("confidence_pct", "?")
    conf_emoji = "\u2705" if conf == "HIGH" else "\u26a1" if conf == "MEDIUM" else "\u26a0\ufe0f"
    action = analysis.get("action_window", "MONITOR")

    # Parse evidence for display
    evidence_text = ""
    try:
        ev_list = json.loads(analysis.get("evidence", "[]"))
        if ev_list:
            evidence_text = "\n".join(f"  \u2022 {e}" for e in ev_list[:4])
    except (json.JSONDecodeError, TypeError):
        pass

    exchange_icon = "\U0001f1ee\U0001f1f3" if exchange == "NSE" else "\U0001f4b9"
    message = f"""\U0001f514 {exchange} FILING ALERT
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
{exchange_icon} {symbol} | {company} [{exchange}]
\U0001f4cb {filing.get('desc', '') or filing.get('subject', 'Corporate Filing')}
\u23f0 {datetime.now().strftime('%H:%M IST | %d %b %Y')}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f4dd SUMMARY
{analysis['summary']}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f4ca MARKET IMPACT
Verdict: {verdict_emoji}
Confidence: {conf} {conf_emoji} ({conf_pct}%)
Action: {action}
Reason: {analysis['reason']}
\u26a0\ufe0f Risk: {analysis['risk']}"""

    if evidence_text:
        message += f"""
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f50d EVIDENCE
{evidence_text}"""

    message += f"""
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f4c8 PRICE AT FILING
CMP: Rs {price} | Change: {change_pct}%
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"""

    filing_type = filing.get("desc", "") or filing.get("subject", "Corporate Filing")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chat_ids = get_matching_subscribers("HIGH", symbol, filing_type)
    for chat_id in chat_ids:
        try:
            resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
            if resp.status_code == 200:
                print(f"   ✅ Telegram sent to {chat_id}")
            else:
                print(f"   Telegram error for {chat_id}: {resp.text}")
        except Exception as e:
            print(f"   Telegram exception for {chat_id}: {e}")

# ============================================================
# SEND MODERATE TELEGRAM ALERT
# ============================================================
def send_moderate_alert(filing, symbol, company, price, change_pct, exchange, chat_ids):
    """Send a basic filing alert to subscribers who want MODERATE category."""
    subject = filing.get("desc", "") or filing.get("subject", "Corporate Filing")
    exchange_icon = "\U0001f1ee\U0001f1f3" if exchange == "NSE" else "\U0001f4b9"
    message = f"""\u26a1 {exchange} MODERATE FILING: {symbol}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
{exchange_icon} {symbol} | {company} [{exchange}]
\U0001f4cb {subject}
\u23f0 {datetime.now().strftime('%H:%M IST | %d %b %Y')}
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f4c8 CMP: Rs {price} | Change: {change_pct}%
\U0001f3f7 Category: MODERATE"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    for chat_id in chat_ids:
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        except Exception as e:
            print(f"   Moderate alert error for {chat_id}: {e}")

# ============================================================
# SEND WATCHLIST TELEGRAM ALERT
# ============================================================
def send_watchlist_telegram(filing, symbol, company, category, group, price, change_pct, exchange="NSE"):
    message = f"""\u2b50 WATCHLIST ALERT: {symbol} [{exchange}]
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\U0001f3e2 {symbol} | {company}
\U0001f4c1 Watchlist: {group}
\U0001f4cb {filing.get('desc', '') or filing.get('subject', 'Corporate Filing')}
\U0001f3f7 Category: {category}
\u23f0 {datetime.now().strftime('%H:%M IST | %d %b %Y')}
\U0001f4b0 CMP: Rs {price} | Change: {change_pct}%
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u26a1 Your watchlisted stock filed a corporate announcement"""

    filing_type = filing.get("desc", "") or filing.get("subject", "Corporate Filing")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chat_ids = get_matching_subscribers(category, symbol, filing_type)
    for chat_id in chat_ids:
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        except Exception as e:
            print(f"   Watchlist Telegram error: {e}")

# ============================================================
# LOG TO SUPABASE
# ============================================================
def log_to_supabase(filing, symbol, company, analysis, price, change_pct, category, exchange="NSE"):
    now = datetime.now()
    row = {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "symbol": symbol,
        "company": company,
        "filing_type": filing.get("desc", "") or filing.get("subject", ""),
        "category": category,
        "summary": analysis["summary"],
        "verdict": analysis["verdict"],
        "confidence": analysis["confidence"],
        "reason": analysis["reason"],
        "risk": analysis["risk"],
        "cmp_at_filing": str(price),
        "day_change_pct": f"{float(change_pct):.2f}%" if change_pct != "N/A" else "N/A",
    }
    # Add new columns if they exist
    if HAS_EXCHANGE_COL:
        row["exchange"] = exchange
    if HAS_CONFIDENCE_PCT_COL:
        row["confidence_pct"] = analysis.get("confidence_pct")
    if HAS_EVIDENCE_COL:
        row["evidence"] = analysis.get("evidence", "[]")
    if HAS_ACTION_WINDOW_COL:
        row["action_window"] = analysis.get("action_window", "MONITOR")

    try:
        supabase.table("nse_filings").insert(row).execute()
        print(f"   ✅ Supabase logged: {symbol} [{exchange}] [{category}]")
    except Exception as e:
        print(f"   Supabase error: {e}")
        # Retry without new columns if schema error
        if "does not exist" in str(e):
            for col in ["exchange", "confidence_pct", "evidence", "action_window"]:
                row.pop(col, None)
            try:
                supabase.table("nse_filings").insert(row).execute()
                print(f"   ✅ Supabase logged (fallback): {symbol}")
            except Exception as e2:
                print(f"   Supabase fallback error: {e2}")

# ============================================================
# PROCESS A SINGLE FILING
# ============================================================
def process_filing(filing, session, seen, exchange="NSE"):
    """Process a single filing (NSE or BSE). Returns True if new."""
    symbol = filing.get("symbol", "").upper().strip()
    if not symbol:
        return False

    subject = filing.get("desc", "") or filing.get("subject", "")
    seq = filing.get("seqNo", "")
    an_dt = filing.get("an_dt", "")
    filing_id = f"{exchange}_{symbol}_{seq}_{an_dt}"

    if filing_id in seen:
        return False

    seen.add(filing_id)

    # Step 1: Quick classify
    category = classify_filing(subject)

    # Step 2: Get live price
    if exchange == "NSE":
        nse_sess = get_nse_session()
        price, change_pct = get_nse_price(nse_sess, symbol)
    else:
        bse_sess = get_bse_session()
        scrip_code = filing.get("_bse_raw", {}).get("SCRIP_CD", "")
        price, change_pct = get_bse_price(bse_sess, scrip_code) if scrip_code else ("N/A", "N/A")

    # Step 3: Download PDF
    pdf_path = download_pdf(session, filing, symbol, exchange)
    company = filing.get("company", "") or filing.get("corp_name", symbol)

    # Step 4: For HIGH/MODERATE — extract PDF text and reclassify
    pdf_text = ""
    if category in ("HIGH", "MODERATE") and pdf_path:
        pdf_text = extract_pdf_text(pdf_path)
        category = classify_filing(subject, pdf_text)

    # Step 5: Check watchlist
    watched, watch_group = is_watchlisted(symbol)
    priority_tag = f" [WATCHLIST: {watch_group}]" if watched else ""

    print(f"\n\U0001f195 [{exchange}] {symbol}: {subject} [{category}]{priority_tag}")
    print(f"   Rs {price} | {change_pct}%")

    # Step 6: Gemini analysis only for HIGH
    if category == "HIGH":
        print(f"   Analyzing with Gemini...")
        raw = analyze_with_gemini(pdf_text, subject, symbol, price, change_pct, exchange)
        analysis = parse_gemini(raw)
        print(f"   Verdict: {analysis['verdict']} | Confidence: {analysis['confidence']} ({analysis['confidence_pct']}%)")
        send_telegram(filing, symbol, company, analysis, price, change_pct, exchange)
        track_price(symbol, price)
    else:
        analysis = {
            "summary": "\u2014",
            "verdict": "N/A",
            "confidence": "N/A",
            "confidence_pct": None,
            "reason": "Routine filing - no analysis needed",
            "risk": "N/A",
            "evidence": "[]",
            "action_window": None,
        }

    # Step 6.5: MODERATE alert for subscribers who opted in for MODERATE
    if category == "MODERATE":
        mod_subs = get_matching_subscribers("MODERATE", symbol, subject)
        if mod_subs:
            print(f"   Sending MODERATE alert to {len(mod_subs)} subscriber(s)...")
            send_moderate_alert(filing, symbol, company, price, change_pct, exchange, mod_subs)

    # Step 7: Watchlist alert (triggers for ALL categories)
    if watched and category != "HIGH":
        print(f"   Sending watchlist alert for {symbol}...")
        send_watchlist_telegram(filing, symbol, company, category, watch_group, price, change_pct, exchange)

    # Step 8: Log to Supabase
    log_to_supabase(filing, symbol, company, analysis, price, change_pct, category, exchange)

    time.sleep(1)
    return True

# ============================================================
# MAIN CHECK FUNCTION
# ============================================================
def check_filings():
    print(f"\n{'=' * 50}")
    print(f"\U0001f50d NSE + BSE Check at {datetime.now().strftime('%H:%M:%S on %d %b %Y')}")
    print(f"{'=' * 50}")

    seen = load_seen()
    new_count = 0

    # ── Fetch NSE ──
    nse_sess = get_nse_session()
    nse_filings = fetch_nse_filings(nse_sess)
    nse_filings = [f for f in nse_filings if f is not None]

    if not nse_filings:
        print("⚠️  No data from NSE. Resetting session for next cycle.")
        reset_nse_session()
    else:
        for filing in nse_filings:
            if process_filing(filing, nse_sess, seen, "NSE"):
                new_count += 1

    # ── Fetch BSE ──
    bse_sess = get_bse_session()
    bse_raw = fetch_bse_filings(bse_sess)
    if bse_raw:
        for item in bse_raw:
            filing = map_bse_filing(item)
            if process_filing(filing, bse_sess, seen, "BSE"):
                new_count += 1
    elif bse_raw is not None:
        # Empty list is fine (weekends, holidays)
        pass

    save_seen(seen)

    # Check price movements for tracked HIGH filings
    check_price_movements()

    if new_count == 0:
        print("✅ No new filings this cycle.")
    else:
        print(f"\n✅ {new_count} new filing(s) processed.")

# ============================================================
# STARTUP TELEGRAM MESSAGE
# ============================================================
def send_startup_message():
    message = f"""\U0001f7e2 NSE + BSE MONITOR STARTED
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
\u23f0 {datetime.now().strftime('%H:%M IST | %d %b %Y')}
\U0001f4e1 Watching: ALL NSE + BSE companies
\U0001f3af High Impact Alerts: Telegram + AI Analysis
\U0001f4ca All filings: Supabase
\u23f1 Interval: Every 30 seconds
\U0001f916 AI: Gemini 2.0 Flash (structured JSON)
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chat_ids = get_all_active_subscribers()
    for chat_id in chat_ids:
        try:
            requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
        except Exception as e:
            print(f"   Startup message error for {chat_id}: {e}")

# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    print("\U0001f680 NSE + BSE Corporate Filings Monitor")
    print("   Tracking: ALL NSE + BSE companies")
    print("   Alerts: HIGH impact \u2192 Telegram | ALL \u2192 Supabase")
    print("   Interval: Every 30 seconds\n")

    setup()

    # Verify Telegram connectivity before starting
    print("   Testing Telegram connection...")
    test_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    test_ids = get_all_active_subscribers()
    for cid in test_ids:
        try:
            r = requests.post(test_url, json={
                "chat_id": cid,
                "text": f"\u2705 NSE + BSE Monitor started\n\u23f0 {datetime.now().strftime('%H:%M IST | %d %b %Y')}\n\U0001f4e1 Telegram connection verified"
            }, timeout=10)
            if r.status_code == 200:
                print(f"   \u2705 Telegram test OK (chat {cid})")
            else:
                print(f"   \u26a0\ufe0f Telegram test FAILED for {cid}: {r.text}")
        except Exception as e:
            print(f"   \u26a0\ufe0f Telegram test FAILED: {e}")

    print("   Initializing sessions...")
    nse_session = create_nse_session()
    bse_session = create_bse_session()
    send_startup_message()
    check_filings()

    schedule.every(30).seconds.do(check_filings)

    print("\n\u23f0 Monitor running. Keep this terminal open during market hours.")
    print("   Press Ctrl+C to stop.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\U0001f6d1 Shutdown signal received (Ctrl+C)...")
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        msg = f"\U0001f6d1 NSE + BSE Monitor stopped manually.\n\u23f0 {datetime.now().strftime('%H:%M IST | %d %b %Y')}"
        for cid in get_all_active_subscribers():
            try:
                resp = requests.post(url, json={"chat_id": cid, "text": msg}, timeout=10)
                if resp.status_code == 200:
                    print(f"   \u2705 Shutdown alert sent to {cid}")
                else:
                    print(f"   \u26a0\ufe0f Shutdown alert failed for {cid}: {resp.status_code}")
            except Exception as e:
                print(f"   \u26a0\ufe0f Shutdown alert error: {e}")
        print("   Goodbye.")
        sys.exit(0)
