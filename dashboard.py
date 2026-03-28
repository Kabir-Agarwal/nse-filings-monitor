import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
from datetime import datetime
from pathlib import Path
from supabase import create_client

# ── Supabase connection ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY", ""))
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Gemini for chatbot ──
GEMINI_KEY = os.environ.get("GEMINI_KEY_1", st.secrets.get("GEMINI_KEY_1", ""))

BASE_DIR = Path(__file__).parent
WATCHLIST_FILE = BASE_DIR / "watchlist.json"
FILINGS_FOLDER = BASE_DIR / "Filings"

DISPLAY_COLUMNS = [
    "Exchange", "Time", "Symbol", "Company", "Filing Type", "Category",
    "Verdict", "Confidence", "CMP at Filing", "Day Change %",
]

HIDE_COLUMNS = ["Reason", "Risk", "Summary", "Date", "PDF Path"]

st.set_page_config(
    page_title="NSE + BSE Filings Monitor",
    page_icon="https://www.nseindia.com/favicon.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Professional financial dashboard CSS ─────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --navy: #0D1B2A;
        --navy-light: #1B2D45;
        --blue: #1B4F8A;
        --blue-light: #2E6DB4;
        --orange: #FF6B35;
        --orange-bg: rgba(255, 107, 53, 0.08);
        --green: #27AE60;
        --green-bg: rgba(39, 174, 96, 0.08);
        --red: #E74C3C;
        --red-bg: rgba(231, 76, 60, 0.08);
        --yellow: #F39C12;
        --yellow-bg: rgba(243, 156, 18, 0.08);
        --bg: #F8F9FA;
        --card: #FFFFFF;
        --border: #E2E8F0;
        --text: #1A202C;
        --text-secondary: #64748B;
        --text-muted: #94A3B8;
    }

    /* Global */
    .stApp { background-color: var(--bg); font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    .block-container { padding-top: 1rem; padding-bottom: 0; max-width: 100%; }

    /* Sidebar - clean filter panel */
    section[data-testid="stSidebar"] {
        background-color: var(--card);
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown label,
    section[data-testid="stSidebar"] .stRadio label {
        color: var(--text) !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
    }
    section[data-testid="stSidebar"] h3 {
        color: var(--navy) !important;
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }

    /* Header bar */
    .header-bar {
        background: linear-gradient(135deg, var(--navy) 0%, var(--navy-light) 100%);
        padding: 14px 24px;
        margin: 0 0 20px 0;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
    }
    .header-left { display: flex; align-items: center; gap: 14px; }
    .header-logo {
        font-family: 'Inter', sans-serif;
        font-size: 1.3rem;
        font-weight: 700;
        color: #FFFFFF;
    }
    .header-logo span { color: var(--orange); }
    .header-subtitle {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.6);
        font-weight: 400;
    }
    .header-right { display: flex; align-items: center; gap: 14px; }
    .header-time {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
        color: rgba(255,255,255,0.8);
        font-weight: 500;
    }
    .market-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 600;
        letter-spacing: 0.3px;
    }
    .market-pill.open { background: rgba(39,174,96,0.2); color: #27AE60; }
    .market-pill.closed { background: rgba(231,76,60,0.15); color: #E74C3C; }
    .market-pill .dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        display: inline-block;
    }
    .market-pill.open .dot { background: #27AE60; }
    .market-pill.closed .dot { background: #E74C3C; }
    .live-pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 4px 10px;
        border-radius: 20px;
        background: rgba(39,174,96,0.15);
        font-size: 0.65rem;
        font-weight: 600;
        color: #27AE60;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    @keyframes blink { 0%,100%{opacity:1;} 50%{opacity:0.3;} }
    .live-pill .dot {
        width: 6px; height: 6px;
        background: #27AE60;
        border-radius: 50%;
        display: inline-block;
        animation: blink 1.5s ease-in-out infinite;
    }
    .exchange-badge {
        display: inline-block;
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.3px;
    }
    .exchange-nse { background: rgba(27,79,138,0.12); color: #1B4F8A; }
    .exchange-bse { background: rgba(220,53,69,0.12); color: #DC3545; }

    /* Latest filing bar */
    .latest-bar {
        background: var(--card);
        border: 1px solid var(--border);
        border-left: 3px solid var(--blue);
        border-radius: 6px;
        padding: 10px 18px;
        margin-bottom: 16px;
        font-size: 0.85rem;
        color: var(--text);
        display: flex;
        align-items: center;
        gap: 8px;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .latest-bar .label {
        color: var(--blue);
        font-weight: 700;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        flex-shrink: 0;
    }
    .latest-bar .sep { color: var(--border); margin: 0 4px; }

    /* Category pills */
    .cat-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 600;
    }
    .cat-high { background: var(--orange-bg); color: var(--orange); border: 1px solid rgba(255,107,53,0.25); }
    .cat-moderate { background: var(--yellow-bg); color: var(--yellow); border: 1px solid rgba(243,156,18,0.25); }
    .cat-routine { background: rgba(100,116,139,0.08); color: var(--text-secondary); border: 1px solid rgba(100,116,139,0.15); }

    /* Metric cards */
    .metric-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 16px 18px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .metric-value {
        font-family: 'Inter', sans-serif;
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.1;
    }
    .metric-label {
        font-size: 0.7rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-top: 4px;
        font-weight: 600;
    }
    .val-total { color: var(--navy); }
    .val-high  { color: var(--orange); }
    .val-mod   { color: var(--yellow); }
    .val-rout  { color: var(--text-muted); }
    .val-comp  { color: var(--blue); }
    .val-wl    { color: #7C3AED; }

    /* Section headers */
    .section-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: var(--navy);
        padding-bottom: 8px;
        margin: 18px 0 10px 0;
        border-bottom: 2px solid var(--border);
    }

    /* Watchlist tag */
    .wl-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        background: rgba(124, 58, 237, 0.08);
        border: 1px solid rgba(124, 58, 237, 0.2);
        color: #7C3AED;
        font-size: 0.72rem;
        font-weight: 600;
    }

    /* Confidence progress bar */
    .conf-bar-outer {
        background: #E2E8F0;
        border-radius: 6px;
        height: 8px;
        width: 100%;
        overflow: hidden;
    }
    .conf-bar-inner {
        height: 100%;
        border-radius: 6px;
        transition: width 0.3s;
    }
    .conf-bar-green { background: #27AE60; }
    .conf-bar-yellow { background: #F39C12; }
    .conf-bar-red { background: #E74C3C; }

    /* Evidence bullets */
    .evidence-box {
        background: rgba(27,79,138,0.04);
        border: 1px solid rgba(27,79,138,0.12);
        border-radius: 6px;
        padding: 8px 12px;
        margin: 4px 0 8px 0;
        font-size: 0.78rem;
        line-height: 1.5;
        color: var(--text);
    }
    .evidence-box ul { margin: 0; padding-left: 16px; }
    .evidence-box li { margin-bottom: 2px; }

    /* Chatbot */
    .chat-msg-user {
        background: var(--navy);
        color: white;
        padding: 10px 14px;
        border-radius: 12px 12px 4px 12px;
        margin: 6px 0;
        font-size: 0.85rem;
        max-width: 80%;
        margin-left: auto;
    }
    .chat-msg-ai {
        background: var(--card);
        border: 1px solid var(--border);
        color: var(--text);
        padding: 10px 14px;
        border-radius: 12px 12px 12px 4px;
        margin: 6px 0;
        font-size: 0.85rem;
        max-width: 90%;
    }
    .chat-citation {
        background: rgba(27,79,138,0.08);
        padding: 1px 6px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--blue);
    }

    /* Dataframe - clean borders */
    .stDataFrame {
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 2px solid var(--border);
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: var(--text-secondary);
        font-family: 'Inter', sans-serif;
        font-size: 0.85rem;
        font-weight: 600;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 10px 20px;
        margin-bottom: -2px;
    }
    .stTabs [aria-selected="true"] {
        background-color: transparent !important;
        color: var(--blue) !important;
        border-bottom: 2px solid var(--blue) !important;
    }

    /* Hide Streamlit chrome */
    #MainMenu { visibility: hidden; }
    header { visibility: hidden; height: 0; min-height: 0; padding: 0; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }

    /* Footer text */
    .footer-text {
        text-align: center;
        font-size: 0.7rem;
        color: var(--text-muted);
        margin-top: 12px;
        padding: 8px 0;
        border-top: 1px solid var(--border);
    }

    /* Mobile */
    @media (max-width: 768px) {
        .header-bar { padding: 10px 14px; flex-direction: column; align-items: flex-start; }
        .header-logo { font-size: 1.1rem; }
        .metric-card { padding: 10px 12px; }
        .metric-value { font-size: 1.3rem; }
        .metric-label { font-size: 0.6rem; }
        .latest-bar { font-size: 0.75rem; padding: 8px 12px; }
        .block-container { padding-left: 0.5rem; padding-right: 0.5rem; }
    }
    @media (max-width: 480px) {
        .header-logo { font-size: 0.95rem; }
        .metric-value { font-size: 1.1rem; }
        .market-pill, .live-pill { font-size: 0.6rem; }
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────
def get_market_status():
    now = datetime.now()
    weekday = now.weekday()
    hour_min = now.hour * 100 + now.minute
    if weekday < 5 and 915 <= hour_min <= 1530:
        return True, "Market Open"
    return False, "Market Closed"


def load_all_data():
    """Paginated fetch — gets ALL filings, not just 1000."""
    all_rows = []
    page_size = 1000
    offset = 0
    try:
        while True:
            response = (
                supabase.table("nse_filings")
                .select("*")
                .order("created_at", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not response.data:
                break
            all_rows.extend(response.data)
            if len(response.data) < page_size:
                break
            offset += page_size
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return pd.DataFrame()

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    col_map = {
        "date": "Date",
        "time": "Time",
        "symbol": "Symbol",
        "company": "Company",
        "filing_type": "Filing Type",
        "category": "Category",
        "summary": "Summary",
        "verdict": "Verdict",
        "confidence": "Confidence",
        "reason": "Reason",
        "risk": "Risk",
        "cmp_at_filing": "CMP at Filing",
        "day_change_pct": "Day Change %",
        "exchange": "Exchange",
        "confidence_pct": "Confidence %",
        "evidence": "Evidence",
        "action_window": "Action Window",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    # Fill exchange default
    if "Exchange" not in df.columns:
        df["Exchange"] = "NSE"
    df["Exchange"] = df["Exchange"].fillna("NSE")

    if "Category" in df.columns:
        df["Category"] = df["Category"].astype(str).str.strip().str.upper()
    return df


def load_watchlist():
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return {}


def get_watchlist_symbols():
    wl = load_watchlist()
    all_symbols = set()
    for symbols in wl.values():
        all_symbols.update(symbols)
    return all_symbols


def style_row(row):
    styles = []
    cat = str(row.get("Category", "")).upper()
    for col in row.index:
        s = ""
        if col == row.index[0]:
            if cat == "HIGH":
                s += "border-left: 3px solid #FF6B35; font-weight: 500; "
            elif cat == "MODERATE":
                s += "border-left: 3px solid #F39C12; "
        if col == "Category":
            if cat == "HIGH":
                s += "background-color: rgba(255,107,53,0.12); color: #FF6B35; font-weight: 600; border-radius: 4px; "
            elif cat == "MODERATE":
                s += "background-color: rgba(243,156,18,0.12); color: #D4850A; font-weight: 600; border-radius: 4px; "
            else:
                s += "background-color: rgba(100,116,139,0.08); color: #64748B; border-radius: 4px; "
        if col == "Verdict":
            v = str(row.get("Verdict", "")).upper()
            if "BULLISH" in v:
                s += "background-color: rgba(39,174,96,0.12); color: #27AE60; font-weight: 600; border-radius: 4px; "
            elif "BEARISH" in v:
                s += "background-color: rgba(231,76,60,0.12); color: #E74C3C; font-weight: 600; border-radius: 4px; "
            elif "NEUTRAL" in v:
                s += "background-color: rgba(100,116,139,0.08); color: #64748B; border-radius: 4px; "
        if col == "Exchange":
            ex = str(row.get("Exchange", "")).upper()
            if ex == "BSE":
                s += "background-color: rgba(220,53,69,0.1); color: #DC3545; font-weight: 600; border-radius: 4px; "
            else:
                s += "background-color: rgba(27,79,138,0.1); color: #1B4F8A; font-weight: 600; border-radius: 4px; "
        styles.append(s)
    return styles


def cat_pill(cat):
    cat = str(cat).upper()
    if cat == "HIGH":
        return '<span class="cat-pill cat-high">HIGH</span>'
    elif cat == "MODERATE":
        return '<span class="cat-pill cat-moderate">MODERATE</span>'
    return '<span class="cat-pill cat-routine">ROUTINE</span>'


def confidence_bar_html(pct):
    """Generate an HTML confidence progress bar."""
    if pct is None or pd.isna(pct):
        return ""
    try:
        pct = int(pct)
    except (ValueError, TypeError):
        return ""
    if pct >= 65:
        color_class = "conf-bar-green"
    elif pct >= 40:
        color_class = "conf-bar-yellow"
    else:
        color_class = "conf-bar-red"
    return (
        f'<div style="display:flex;align-items:center;gap:6px;">'
        f'<div class="conf-bar-outer" style="flex:1;min-width:60px;">'
        f'<div class="conf-bar-inner {color_class}" style="width:{pct}%;"></div>'
        f'</div>'
        f'<span style="font-size:0.75rem;font-weight:600;color:#1A202C;">{pct}%</span>'
        f'</div>'
    )


def evidence_html(evidence_str):
    """Generate HTML for evidence bullets."""
    if not evidence_str or evidence_str == "[]":
        return ""
    try:
        items = json.loads(evidence_str)
        if not items:
            return ""
        bullets = "".join(f"<li>{item}</li>" for item in items[:4])
        return f'<div class="evidence-box"><ul>{bullets}</ul></div>'
    except (json.JSONDecodeError, TypeError):
        return ""


# ── Sidebar ──────────────────────────────────────────────────────────────
st.sidebar.markdown("### Exchange")
exchange_filter = st.sidebar.radio(
    "Exchange",
    ["Both", "NSE", "BSE"],
    index=0,
    label_visibility="collapsed",
)

st.sidebar.markdown("### Filter by Category")
risk_filter = st.sidebar.radio(
    "Category",
    ["ALL", "HIGH", "MODERATE", "ROUTINE"],
    index=0,
)
st.sidebar.markdown("---")
st.sidebar.caption("Auto-refreshes every 30 seconds")
st.sidebar.markdown("---")

watchlist = load_watchlist()
if watchlist:
    st.sidebar.markdown("### Watchlist Groups")
    for group, symbols in watchlist.items():
        st.sidebar.markdown(
            f'<span class="wl-tag">{group}</span> '
            f'<span style="color:#64748B;font-size:0.75rem;">{len(symbols)} stocks</span>',
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("---")

st.sidebar.markdown(
    f'<p style="color:#94A3B8;font-size:0.72rem;">'
    f'{datetime.now().strftime("%d %b %Y")}<br>'
    f'AI: Gemini 2.0 Flash<br>'
    f'Source: NSE + BSE India</p>',
    unsafe_allow_html=True,
)


# ── Header ───────────────────────────────────────────────────────────────
is_open, market_label = get_market_status()
market_class = "open" if is_open else "closed"
now_time = datetime.now().strftime("%H:%M:%S IST")

st.markdown(f"""
<div class="header-bar">
    <div class="header-left">
        <div>
            <div class="header-logo">
                <span class="exchange-badge exchange-nse">NSE</span>
                +
                <span class="exchange-badge exchange-bse">BSE</span>
                &nbsp;<span>Filings</span> Monitor
            </div>
            <div class="header-subtitle">Real-time Corporate Announcements Intelligence &mdash; NSE + BSE India</div>
        </div>
    </div>
    <div class="header-right">
        <div class="live-pill"><span class="dot"></span> Live</div>
        <div class="market-pill {market_class}"><span class="dot"></span> {market_label}</div>
        <div class="header-time">{now_time}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Main fragment ────────────────────────────────────────────────────────
@st.fragment(run_every=30)
def filings_table():
    df = load_all_data()

    if df.empty:
        st.info("No filings data available. Waiting for the monitor to push data...")
        return

    # Sort by time descending
    if "Time" in df.columns:
        sorted_df = df.sort_values("Time", ascending=False)
    else:
        sorted_df = df

    # ── Apply exchange filter ──
    if exchange_filter != "Both" and "Exchange" in sorted_df.columns:
        sorted_df = sorted_df[sorted_df["Exchange"] == exchange_filter].copy()

    if sorted_df.empty:
        st.info(f"No filings for {exchange_filter} exchange.")
        return

    # ── Latest filing bar ──
    latest = sorted_df.iloc[0]
    ticker_symbol = latest.get("Symbol", "---")
    ticker_type = latest.get("Filing Type", "")
    ticker_cat = latest.get("Category", "")
    ticker_time = latest.get("Time", "")
    ticker_exchange = latest.get("Exchange", "NSE")
    ex_badge = f'<span class="exchange-badge exchange-{ticker_exchange.lower()}">{ticker_exchange}</span>'
    st.markdown(
        f'<div class="latest-bar">'
        f'<span class="label">Latest Filing</span>'
        f'<span class="sep">|</span>'
        f'{ex_badge}'
        f'<strong>{ticker_symbol}</strong>'
        f'<span class="sep">|</span>'
        f'{ticker_type}'
        f'<span class="sep">|</span>'
        f'{cat_pill(ticker_cat)}'
        f'<span class="sep">|</span>'
        f'<span style="color:#94A3B8;">{ticker_time}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Stats ──
    high_count = len(sorted_df[sorted_df["Category"] == "HIGH"]) if "Category" in sorted_df.columns else 0
    mod_count = len(sorted_df[sorted_df["Category"] == "MODERATE"]) if "Category" in sorted_df.columns else 0
    routine_count = len(sorted_df[sorted_df["Category"] == "ROUTINE"]) if "Category" in sorted_df.columns else 0
    total = len(sorted_df)
    unique_companies = sorted_df["Symbol"].nunique() if "Symbol" in sorted_df.columns else 0
    wl_symbols = get_watchlist_symbols()
    wl_count = len(sorted_df[sorted_df["Symbol"].isin(wl_symbols)]) if "Symbol" in sorted_df.columns else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-total">{total}</div>'
            f'<div class="metric-label">Total Filings</div></div>',
            unsafe_allow_html=True)
    with c2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-high">{high_count}</div>'
            f'<div class="metric-label">High Impact</div></div>',
            unsafe_allow_html=True)
    with c3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-mod">{mod_count}</div>'
            f'<div class="metric-label">Moderate</div></div>',
            unsafe_allow_html=True)
    with c4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-rout">{routine_count}</div>'
            f'<div class="metric-label">Routine</div></div>',
            unsafe_allow_html=True)
    with c5:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-comp">{unique_companies}</div>'
            f'<div class="metric-label">Companies</div></div>',
            unsafe_allow_html=True)
    with c6:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-wl">{wl_count}</div>'
            f'<div class="metric-label">Watchlist Hits</div></div>',
            unsafe_allow_html=True)

    # ── Category breakdown chart ──
    st.markdown('<div class="section-title">Category Breakdown</div>', unsafe_allow_html=True)
    chart_data = pd.DataFrame({
        "Category": ["HIGH", "MODERATE", "ROUTINE"],
        "Count": [high_count, mod_count, routine_count],
    })
    chart_data = chart_data[chart_data["Count"] > 0]
    if not chart_data.empty:
        fig = px.bar(
            chart_data, x="Count", y="Category", orientation="h",
            color="Category",
            color_discrete_map={"HIGH": "#FF6B35", "MODERATE": "#F39C12", "ROUTINE": "#94A3B8"},
            text="Count",
        )
        fig.update_layout(
            height=140, margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, categoryorder="array", categoryarray=["ROUTINE", "MODERATE", "HIGH"]),
            font=dict(family="Inter, sans-serif", size=13),
        )
        fig.update_traces(textposition="outside", textfont_size=12)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ── Tabs: All Filings + Watchlist + Chatbot ──
    tab_all, tab_watchlist, tab_chatbot = st.tabs(["All Filings", "Watchlist Alerts", "Filing Chatbot"])

    with tab_all:
        st.markdown('<div class="section-title">Live Filings Feed</div>', unsafe_allow_html=True)

        if risk_filter != "ALL" and "Category" in sorted_df.columns:
            filtered = sorted_df[sorted_df["Category"] == risk_filter].copy()
        else:
            filtered = sorted_df.copy()

        show_cols = [c for c in DISPLAY_COLUMNS if c in filtered.columns]
        display_df = filtered[show_cols].reset_index(drop=True)

        if display_df.empty:
            st.info("No filings match the selected filter.")
        else:
            styled = (
                display_df.style
                .apply(style_row, axis=1)
                .set_properties(**{
                    "text-align": "left",
                    "font-size": "0.85rem",
                    "font-family": "Inter, sans-serif",
                    "border-bottom": "1px solid #E2E8F0",
                })
            )
            st.dataframe(styled, use_container_width=True, height=500, hide_index=True)
            st.markdown(
                f'<p style="color:#94A3B8;font-size:0.72rem;text-align:right;margin-top:4px;">'
                f'{len(display_df)} records &middot; Filter: {risk_filter} &middot; Exchange: {exchange_filter} &middot; Refreshes every 30s</p>',
                unsafe_allow_html=True,
            )

        # ── HIGH filings detail: confidence bar + evidence ──
        high_df = filtered[filtered["Category"] == "HIGH"] if "Category" in filtered.columns else pd.DataFrame()
        if not high_df.empty:
            st.markdown('<div class="section-title">HIGH Impact Analysis Details</div>', unsafe_allow_html=True)
            for _, row in high_df.head(20).iterrows():
                symbol = row.get("Symbol", "?")
                exchange = row.get("Exchange", "NSE")
                verdict = str(row.get("Verdict", "")).upper()
                filing_type = row.get("Filing Type", "")
                file_time = row.get("Time", "")
                summary = row.get("Summary", "") if "Summary" in row.index else ""
                conf_pct = row.get("Confidence %") if "Confidence %" in row.index else None
                evidence_str = row.get("Evidence") if "Evidence" in row.index else None

                # Color for verdict
                if "BULLISH" in verdict:
                    v_color = "#27AE60"
                elif "BEARISH" in verdict:
                    v_color = "#E74C3C"
                else:
                    v_color = "#64748B"

                ex_cls = "exchange-bse" if exchange == "BSE" else "exchange-nse"

                with st.container():
                    col_head, col_conf = st.columns([3, 1])
                    with col_head:
                        st.markdown(
                            f'<span class="exchange-badge {ex_cls}">{exchange}</span> '
                            f'<strong>{symbol}</strong> '
                            f'<span style="color:{v_color};font-weight:600;">{verdict}</span> '
                            f'<span style="color:#94A3B8;font-size:0.78rem;">| {filing_type} | {file_time}</span>',
                            unsafe_allow_html=True,
                        )
                    with col_conf:
                        bar_html = confidence_bar_html(conf_pct)
                        if bar_html:
                            st.markdown(bar_html, unsafe_allow_html=True)

                    if summary and summary != "\u2014":
                        st.caption(summary)

                    ev_html = evidence_html(evidence_str)
                    if ev_html:
                        st.markdown(ev_html, unsafe_allow_html=True)

                    st.markdown("---")

    with tab_watchlist:
        st.markdown('<div class="section-title">Watchlist Filings</div>', unsafe_allow_html=True)

        if not wl_symbols:
            st.info("No watchlist configured. Add stocks to watchlist.json to track them here.")
        else:
            wl_df = sorted_df[sorted_df["Symbol"].isin(wl_symbols)].copy() if "Symbol" in sorted_df.columns else pd.DataFrame()

            if wl_df.empty:
                st.info("No filings from watchlisted stocks yet.")
            else:
                wl_map = load_watchlist()
                group_lookup = {}
                for group, syms in wl_map.items():
                    for s in syms:
                        group_lookup[s] = group
                wl_df["Watchlist"] = wl_df["Symbol"].map(group_lookup).fillna("")

                wl_show_cols = [c for c in (["Watchlist"] + DISPLAY_COLUMNS) if c in wl_df.columns]
                wl_display = wl_df[wl_show_cols].reset_index(drop=True)

                styled_wl = (
                    wl_display.style
                    .apply(style_row, axis=1)
                    .set_properties(**{
                        "text-align": "left",
                        "font-size": "0.85rem",
                        "font-family": "Inter, sans-serif",
                        "border-bottom": "1px solid #E2E8F0",
                    })
                )
                st.dataframe(styled_wl, use_container_width=True, height=500, hide_index=True)
                st.markdown(
                    f'<p style="color:#94A3B8;font-size:0.72rem;text-align:right;margin-top:4px;">'
                    f'{len(wl_display)} watchlist filings &middot; {len(wl_symbols)} stocks tracked</p>',
                    unsafe_allow_html=True,
                )

    with tab_chatbot:
        st.markdown('<div class="section-title">Filing Intelligence Chatbot</div>', unsafe_allow_html=True)
        st.caption("Ask anything about filings — powered by Gemini AI with full filing context")

        # Initialize chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Show chat history
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-msg-user">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-msg-ai">{msg["content"]}</div>', unsafe_allow_html=True)

        # Chat input
        user_question = st.chat_input("Ask about any filing, company, or market signal...")

        if user_question:
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            st.markdown(f'<div class="chat-msg-user">{user_question}</div>', unsafe_allow_html=True)

            # Build context from HIGH filings
            context_parts = []
            try:
                high_resp = (
                    supabase.table("nse_filings")
                    .select("*")
                    .eq("category", "HIGH")
                    .order("created_at", desc=True)
                    .limit(500)
                    .execute()
                )
                if high_resp.data:
                    for f in high_resp.data:
                        exchange = f.get("exchange", "NSE") or "NSE"
                        evidence = f.get("evidence", "")
                        entry = (
                            f"[{exchange} {f.get('symbol','')} filing {f.get('date','')} {f.get('time','')}] "
                            f"Type: {f.get('filing_type','')} | "
                            f"Verdict: {f.get('verdict','')} | "
                            f"Confidence: {f.get('confidence','')} ({f.get('confidence_pct','?')}%) | "
                            f"Summary: {f.get('summary','')} | "
                            f"Reason: {f.get('reason','')} | "
                            f"Risk: {f.get('risk','')}"
                        )
                        if evidence and evidence != "[]":
                            entry += f" | Evidence: {evidence}"
                        context_parts.append(entry)
            except Exception as e:
                context_parts.append(f"[Error loading filings: {e}]")

            # Try loading PDF text from Filings folder
            pdf_context = ""
            if FILINGS_FOLDER.exists():
                try:
                    pdf_files = list(FILINGS_FOLDER.glob("**/*.pdf"))[:5]  # Latest 5 PDFs
                    for pf in pdf_files:
                        try:
                            import pdfplumber
                            with pdfplumber.open(pf) as pdf:
                                for page in pdf.pages[:2]:
                                    text = page.extract_text()
                                    if text:
                                        pdf_context += f"\n[PDF: {pf.stem}]\n{text[:500]}\n"
                        except Exception:
                            pass
                except Exception:
                    pass

            context_text = "\n".join(context_parts[:300])  # Limit context size

            # Build Gemini prompt
            chat_prompt = f"""You are a senior Indian stock market analyst chatbot with access to real-time NSE and BSE corporate filing data.

FILING DATABASE (latest HIGH-impact filings):
{context_text}

{f"ADDITIONAL PDF CONTEXT:{pdf_context}" if pdf_context else ""}

USER QUESTION: {user_question}

RULES:
- Answer with specific data from the filings above
- Always cite sources like [HDFC filing 24 Mar] or [Price data 09:14]
- If comparing companies, show side-by-side analysis
- If the question is about sectors, filter relevant filings
- Be concise but thorough — give actionable insights
- If data is not available, say so clearly
- Format your response with clear structure"""

            # Call Gemini
            answer = ""
            if GEMINI_KEY:
                try:
                    from google import genai as genai_chat
                    chat_client = genai_chat.Client(api_key=GEMINI_KEY)
                    response = chat_client.models.generate_content(
                        model="gemini-2.0-flash-lite",
                        contents=chat_prompt,
                    )
                    answer = response.text
                except Exception as e:
                    answer = f"Gemini error: {e}. Please check your API key."
            else:
                answer = "Gemini API key not configured. Add GEMINI_KEY_1 to .env or .streamlit/secrets.toml"

            # Format response for HTML display
            answer_html = answer.replace("\n", "<br>")
            st.session_state.chat_history.append({"role": "assistant", "content": answer_html})
            st.markdown(f'<div class="chat-msg-ai">{answer_html}</div>', unsafe_allow_html=True)

    # ── Footer ──
    st.markdown(
        f'<div class="footer-text">'
        f'Last refresh: {datetime.now().strftime("%H:%M:%S IST")} &middot; '
        f'Powered by Supabase &middot; AI by Gemini &middot; Data from NSE + BSE India</div>',
        unsafe_allow_html=True,
    )


filings_table()
