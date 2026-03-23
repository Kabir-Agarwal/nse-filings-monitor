import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from pathlib import Path
from supabase import create_client

# ── Supabase connection ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY", ""))
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE_DIR = Path(__file__).parent
WATCHLIST_FILE = BASE_DIR / "watchlist.json"

DISPLAY_COLUMNS = [
    "Time", "Symbol", "Company", "Filing Type", "Category",
    "Verdict", "Confidence", "CMP at Filing", "Day Change %",
]

HIDE_COLUMNS = ["Reason", "Risk", "Summary", "Date", "PDF Path"]

st.set_page_config(
    page_title="NSE Filings Terminal",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark terminal theme + mobile responsive CSS ─────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;600;700&display=swap');

    /* Global dark theme */
    .stApp { background-color: #0a0e17; }
    .block-container { padding-top: 0.5rem; padding-bottom: 0; max-width: 100%; }
    header[data-testid="stHeader"] { background-color: #0a0e17; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0f1420;
        border-right: 1px solid #1a2332;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown label,
    section[data-testid="stSidebar"] .stRadio label {
        color: #8899aa !important;
        font-family: 'Inter', sans-serif;
    }
    section[data-testid="stSidebar"] h2 {
        color: #00e676 !important;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.9rem !important;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    /* Ticker bar */
    .ticker-bar {
        background: linear-gradient(90deg, #0d1a2a 0%, #112240 50%, #0d1a2a 100%);
        border: 1px solid #1a3a5c;
        border-radius: 4px;
        padding: 10px 20px;
        margin-bottom: 12px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #4fc3f7;
        overflow: hidden;
        white-space: nowrap;
        text-overflow: ellipsis;
    }
    .ticker-label {
        color: #ff9800;
        font-weight: 700;
        margin-right: 8px;
    }

    /* Header area */
    .terminal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 0 4px 0;
        border-bottom: 1px solid #1a2332;
        margin-bottom: 14px;
        flex-wrap: wrap;
        gap: 8px;
    }
    .terminal-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.5rem;
        font-weight: 700;
        color: #e0e0e0;
        letter-spacing: 1px;
    }
    .terminal-title span.nse { color: #2196F3; }
    .terminal-title span.dot { color: #ff9800; }

    /* Market status */
    .market-badge {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .market-open {
        background: rgba(0, 230, 118, 0.15);
        color: #00e676;
        border: 1px solid #00e676;
    }
    .market-closed {
        background: rgba(255, 68, 68, 0.15);
        color: #ff4444;
        border: 1px solid #ff4444;
    }

    /* Pulsing live indicator */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
    .live-dot {
        display: inline-block;
        width: 8px; height: 8px;
        background: #00e676;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 1.5s ease-in-out infinite;
        box-shadow: 0 0 8px #00e676;
    }
    .live-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 4px;
        background: rgba(0, 230, 118, 0.1);
        border: 1px solid rgba(0, 230, 118, 0.3);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        font-weight: 600;
        color: #00e676;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #0f1a2e 0%, #132238 100%);
        border: 1px solid #1a2d47;
        border-radius: 8px;
        padding: 14px 18px;
        text-align: center;
    }
    .metric-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2rem;
        font-weight: 700;
        line-height: 1.1;
    }
    .metric-label {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        color: #5a6f8a;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-top: 4px;
        font-weight: 600;
    }
    .val-blue     { color: #4fc3f7; }
    .val-green    { color: #00e676; }
    .val-yellow   { color: #ffd740; }
    .val-grey     { color: #78909c; }
    .val-white    { color: #cfd8dc; }
    .val-cyan     { color: #00bcd4; }
    .val-purple   { color: #bb86fc; }

    /* Section headers */
    .section-header {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        color: #5a6f8a;
        letter-spacing: 2px;
        text-transform: uppercase;
        border-bottom: 1px solid #1a2332;
        padding-bottom: 6px;
        margin: 16px 0 10px 0;
    }

    /* Watchlist badge */
    .watchlist-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 3px;
        background: rgba(187, 134, 252, 0.15);
        border: 1px solid #bb86fc;
        color: #bb86fc;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 1px;
    }

    /* Dataframe overrides */
    .stDataFrame {
        border: 1px solid #1a2d47;
        border-radius: 6px;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid #1a2332;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #0a0e17;
        color: #5a6f8a;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        letter-spacing: 1px;
        border: 1px solid #1a2332;
        border-bottom: none;
        border-radius: 4px 4px 0 0;
        padding: 8px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #132238 !important;
        color: #4fc3f7 !important;
        border-color: #2196F3 !important;
    }

    /* Hide default streamlit elements */
    #MainMenu, footer, .stDeployButton { display: none; }
    .stSubheader { color: #8899aa !important; }

    /* ── Mobile responsive ── */
    @media (max-width: 768px) {
        .block-container { padding-left: 0.5rem; padding-right: 0.5rem; }
        .terminal-title { font-size: 1rem; }
        .terminal-header { flex-direction: column; align-items: flex-start; }
        .metric-card { padding: 8px 10px; }
        .metric-value { font-size: 1.4rem; }
        .metric-label { font-size: 0.6rem; letter-spacing: 1px; }
        .ticker-bar { font-size: 0.7rem; padding: 8px 12px; }
        .section-header { font-size: 0.7rem; }
    }
    @media (max-width: 480px) {
        .terminal-title { font-size: 0.85rem; }
        .metric-value { font-size: 1.1rem; }
        .live-badge { font-size: 0.6rem; padding: 3px 8px; }
        .market-badge { font-size: 0.6rem; padding: 3px 8px; }
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────
def get_market_status():
    now = datetime.now()
    weekday = now.weekday()
    hour_min = now.hour * 100 + now.minute
    if weekday < 5 and 915 <= hour_min <= 1530:
        return True, "MARKET OPEN"
    return False, "MARKET CLOSED"


def load_data():
    try:
        response = supabase.table("nse_filings").select("*").order("created_at", desc=True).limit(5000).execute()
        if not response.data:
            return pd.DataFrame()
        df = pd.DataFrame(response.data)
        # Rename Supabase columns to match dashboard display names
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
        }
        df = df.rename(columns=col_map)
        if "Category" in df.columns:
            df["Category"] = df["Category"].astype(str).str.strip().str.upper()
        return df
    except Exception as e:
        st.error(f"Supabase error: {e}")
        return pd.DataFrame()


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


def color_row(row):
    cat = str(row.get("Category", "")).upper()
    if cat == "HIGH":
        return ["background-color: #00B050; color: white; font-weight: 600"] * len(row)
    elif cat == "MODERATE":
        return ["background-color: #3d3d00; color: #ffd740"] * len(row)
    return ["background-color: #0f1420; color: #8899aa"] * len(row)


def color_row_watchlist(row):
    cat = str(row.get("Category", "")).upper()
    if cat == "HIGH":
        return ["background-color: #00B050; color: white; font-weight: 600"] * len(row)
    elif cat == "MODERATE":
        return ["background-color: #3d3d00; color: #ffd740"] * len(row)
    return ["background-color: #1a1040; color: #bb86fc"] * len(row)


# ── Sidebar ──────────────────────────────────────────────────────────────
st.sidebar.markdown("## // Filters")
risk_filter = st.sidebar.radio(
    "Category",
    ["ALL", "HIGH", "MODERATE", "ROUTINE"],
    index=0,
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    '<div class="live-badge"><span class="live-dot"></span>SYSTEM LIVE</div>',
    unsafe_allow_html=True,
)
st.sidebar.caption("Auto-refresh: 30s cycle")
st.sidebar.markdown("---")

# Show watchlist groups in sidebar
watchlist = load_watchlist()
if watchlist:
    st.sidebar.markdown("## // Watchlist")
    for group, symbols in watchlist.items():
        st.sidebar.markdown(
            f'<span class="watchlist-tag">{group}</span> '
            f'<span style="color:#5a6f8a;font-size:0.7rem;font-family:JetBrains Mono,monospace;">'
            f'{len(symbols)} stocks</span>',
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("---")

st.sidebar.markdown(
    f'<p style="color:#3a4a5c;font-size:0.7rem;font-family:JetBrains Mono,monospace;">'
    f'Session: {datetime.now().strftime("%d %b %Y")}<br>'
    f'Engine: Gemini 2.0 Flash<br>'
    f'Feed: NSE Corp Announcements<br>'
    f'DB: Supabase Cloud</p>',
    unsafe_allow_html=True,
)


# ── Header ───────────────────────────────────────────────────────────────
is_open, market_label = get_market_status()
market_css = "market-open" if is_open else "market-closed"

st.markdown(f"""
<div class="terminal-header">
    <div>
        <span class="terminal-title"><span class="nse">NSE</span><span class="dot">.</span>FILINGS TERMINAL</span>
    </div>
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <div class="live-badge"><span class="live-dot"></span>SYSTEM LIVE</div>
        <div class="market-badge {market_css}">{market_label}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Main fragment ────────────────────────────────────────────────────────
@st.fragment(run_every=30)
def filings_table():
    df = load_data()

    if df.empty:
        st.markdown(
            '<p style="color:#ff4444;font-family:JetBrains Mono,monospace;">'
            '> No data. Waiting for filings feed...</p>',
            unsafe_allow_html=True,
        )
        return

    # Sort by time descending
    if "Time" in df.columns:
        sorted_df = df.sort_values("Time", ascending=False)
    else:
        sorted_df = df

    # ── Ticker bar: most recent filing ──
    latest = sorted_df.iloc[0]
    ticker_symbol = latest.get("Symbol", "---")
    ticker_type = latest.get("Filing Type", "")
    ticker_cat = latest.get("Category", "")
    ticker_time = latest.get("Time", "")
    cat_color = "#00e676" if ticker_cat == "HIGH" else "#ffd740" if ticker_cat == "MODERATE" else "#5a6f8a"
    st.markdown(
        f'<div class="ticker-bar">'
        f'<span class="ticker-label">LATEST</span> '
        f'<span style="color:white;font-weight:700;">{ticker_symbol}</span> '
        f'<span style="color:#5a6f8a;">|</span> '
        f'{ticker_type} '
        f'<span style="color:#5a6f8a;">|</span> '
        f'<span style="color:{cat_color};font-weight:600;">[{ticker_cat}]</span> '
        f'<span style="color:#5a6f8a;">|</span> '
        f'<span style="color:#5a6f8a;">{ticker_time}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Stats ──
    high_count = len(df[df["Category"] == "HIGH"]) if "Category" in df.columns else 0
    mod_count = len(df[df["Category"] == "MODERATE"]) if "Category" in df.columns else 0
    routine_count = len(df[df["Category"] == "ROUTINE"]) if "Category" in df.columns else 0
    total = len(df)
    unique_companies = df["Symbol"].nunique() if "Symbol" in df.columns else 0
    wl_symbols = get_watchlist_symbols()
    wl_count = len(df[df["Symbol"].isin(wl_symbols)]) if "Symbol" in df.columns else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-blue">{total}</div>'
            f'<div class="metric-label">Total Filings</div></div>',
            unsafe_allow_html=True)
    with c2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-green">{high_count}</div>'
            f'<div class="metric-label">High Impact</div></div>',
            unsafe_allow_html=True)
    with c3:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-yellow">{mod_count}</div>'
            f'<div class="metric-label">Moderate</div></div>',
            unsafe_allow_html=True)
    with c4:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-grey">{routine_count}</div>'
            f'<div class="metric-label">Routine</div></div>',
            unsafe_allow_html=True)
    with c5:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-cyan">{unique_companies}</div>'
            f'<div class="metric-label">Companies</div></div>',
            unsafe_allow_html=True)
    with c6:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value val-purple">{wl_count}</div>'
            f'<div class="metric-label">Watchlist Hits</div></div>',
            unsafe_allow_html=True)

    # ── Category breakdown chart ──
    st.markdown('<div class="section-header">// Category Breakdown</div>', unsafe_allow_html=True)
    chart_data = pd.DataFrame({
        "Category": ["HIGH", "MODERATE", "ROUTINE"],
        "Count": [high_count, mod_count, routine_count],
    })
    chart_data = chart_data[chart_data["Count"] > 0]
    if not chart_data.empty:
        st.bar_chart(chart_data.set_index("Category"), color="#2196F3", height=150)

    # ── Tabs: All Filings + Watchlist ──
    tab_all, tab_watchlist = st.tabs(["ALL FILINGS", "WATCHLIST ALERTS"])

    with tab_all:
        st.markdown('<div class="section-header">// Live Filings Feed</div>', unsafe_allow_html=True)

        if risk_filter != "ALL" and "Category" in df.columns:
            filtered = sorted_df[sorted_df["Category"] == risk_filter].copy()
        else:
            filtered = sorted_df.copy()

        show_cols = [c for c in DISPLAY_COLUMNS if c in filtered.columns]
        display_df = filtered[show_cols].reset_index(drop=True)

        if display_df.empty:
            st.markdown(
                '<p style="color:#5a6f8a;font-family:JetBrains Mono,monospace;">'
                '> No filings match filter.</p>',
                unsafe_allow_html=True,
            )
        else:
            styled = (
                display_df.style
                .apply(color_row, axis=1)
                .set_properties(**{
                    "text-align": "left",
                    "font-size": "0.85rem",
                    "font-family": "JetBrains Mono, monospace",
                })
            )
            st.dataframe(styled, use_container_width=True, height=500, hide_index=True)
            st.markdown(
                f'<p style="color:#2a3a4a;font-size:0.65rem;font-family:JetBrains Mono,monospace;text-align:right;margin-top:4px;">'
                f'{len(display_df)} records | Filtered: {risk_filter} | Refresh: 30s</p>',
                unsafe_allow_html=True,
            )

    with tab_watchlist:
        st.markdown('<div class="section-header">// Watchlist Filings</div>', unsafe_allow_html=True)

        if not wl_symbols:
            st.markdown(
                '<p style="color:#5a6f8a;font-family:JetBrains Mono,monospace;">'
                '> No watchlist configured. Edit watchlist.json to add stocks.</p>',
                unsafe_allow_html=True,
            )
        else:
            wl_df = sorted_df[sorted_df["Symbol"].isin(wl_symbols)].copy() if "Symbol" in sorted_df.columns else pd.DataFrame()

            if wl_df.empty:
                st.markdown(
                    '<p style="color:#5a6f8a;font-family:JetBrains Mono,monospace;">'
                    '> No filings from watchlisted stocks yet.</p>',
                    unsafe_allow_html=True,
                )
            else:
                # Show which watchlist group each symbol belongs to
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
                    .apply(color_row_watchlist, axis=1)
                    .set_properties(**{
                        "text-align": "left",
                        "font-size": "0.85rem",
                        "font-family": "JetBrains Mono, monospace",
                    })
                )
                st.dataframe(styled_wl, use_container_width=True, height=500, hide_index=True)
                st.markdown(
                    f'<p style="color:#2a3a4a;font-size:0.65rem;font-family:JetBrains Mono,monospace;text-align:right;margin-top:4px;">'
                    f'{len(wl_display)} watchlist filings | {len(wl_symbols)} stocks tracked</p>',
                    unsafe_allow_html=True,
                )

    # ── Last refresh time ──
    st.markdown(
        f'<p style="color:#1a2a3a;font-size:0.6rem;font-family:JetBrains Mono,monospace;text-align:center;margin-top:8px;">'
        f'Last refresh: {datetime.now().strftime("%H:%M:%S")} | Powered by Supabase</p>',
        unsafe_allow_html=True,
    )


filings_table()
