
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import sys
import os
import calendar
import html
from datetime import datetime, timedelta

# Robustly add project root to sys.path so 'config' can be imported by src modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from src.modules.journal import TradeJournal
from src.utils.helper import get_coin_leverage
from src.utils.pnl_generator import CryptoPnLGenerator


# Page Config
st.set_page_config(
    page_title="Bot Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# DESIGN SYSTEM — CSS
# =============================================================================
st.markdown("""
<style>
    /* ── Import Google Font ───────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* ── Design Tokens ───────────────────────────────────────────────── */
    :root {
        --bg-primary: #0a0e17;
        --bg-card: rgba(17, 24, 39, 0.7);
        --bg-card-solid: #111827;
        --bg-card-hover: #1a2332;
        --border-color: rgba(59, 130, 246, 0.15);
        --border-subtle: rgba(255, 255, 255, 0.06);
        --accent-green: #10b981;
        --accent-green-glow: rgba(16, 185, 129, 0.15);
        --accent-red: #ef4444;
        --accent-red-glow: rgba(239, 68, 68, 0.15);
        --accent-blue: #3b82f6;
        --accent-blue-glow: rgba(59, 130, 246, 0.12);
        --accent-purple: #8b5cf6;
        --accent-amber: #f59e0b;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --radius-lg: 16px;
        --radius-md: 12px;
        --radius-sm: 8px;
    }

    /* ── Global Overrides ────────────────────────────────────────────── */
    .stApp {
        background: linear-gradient(135deg, #0a0e17 0%, #0f172a 50%, #0a0e17 100%) !important;
        font-family: 'Inter', sans-serif !important;
    }

    .stApp > header { background: transparent !important; }
    
    /* Main block container padding */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1400px !important;
    }

    /* ── Sidebar ─────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #111827 100%) !important;
        border-right: 1px solid var(--border-subtle) !important;
    }
    section[data-testid="stSidebar"] .stMarkdown h2 {
        color: var(--accent-blue) !important;
        font-size: 0.85rem !important;
        text-transform: uppercase !important;
        letter-spacing: 1.5px !important;
        font-weight: 700 !important;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border-subtle);
        margin-bottom: 1rem;
    }
    
    /* ── Hide default Streamlit branding ──────────────────────────── */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* ── Dashboard Header ─────────────────────────────────────────── */
    .dashboard-header {
        background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(139,92,246,0.08) 50%, rgba(16,185,129,0.05) 100%);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-lg);
        padding: 1.8rem 2.2rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .dashboard-header::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple), var(--accent-green));
    }
    .dashboard-header h1 {
        font-size: 1.75rem;
        font-weight: 800;
        background: linear-gradient(135deg, #f1f5f9, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 0.3rem 0;
        letter-spacing: -0.5px;
    }
    .dashboard-header .subtitle {
        color: var(--text-muted);
        font-size: 0.85rem;
        font-weight: 400;
        margin: 0;
    }
    .header-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(16,185,129,0.1);
        border: 1px solid rgba(16,185,129,0.2);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.72rem;
        color: var(--accent-green);
        font-weight: 600;
        margin-top: 0.6rem;
    }
    .header-status .dot {
        width: 6px; height: 6px;
        background: var(--accent-green);
        border-radius: 50%;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* ── KPI Card ─────────────────────────────────────────────────── */
    .kpi-card {
        background: var(--bg-card);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 1.2rem 1.4rem;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .kpi-card:hover {
        border-color: var(--border-color);
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }
    .kpi-card .kpi-label {
        color: var(--text-muted);
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .kpi-card .kpi-value {
        font-size: 1.65rem;
        font-weight: 800;
        color: var(--text-primary);
        line-height: 1.2;
        font-family: 'JetBrains Mono', monospace;
    }
    .kpi-card .kpi-sub {
        color: var(--text-secondary);
        font-size: 0.78rem;
        margin-top: 0.35rem;
        font-weight: 500;
    }
    .kpi-card .kpi-icon {
        position: absolute;
        top: 1rem;
        right: 1rem;
        font-size: 1.3rem;
        opacity: 0.35;
    }

    /* Accent variants */
    .kpi-card.green .kpi-value { color: var(--accent-green); }
    .kpi-card.green { border-bottom: 2px solid var(--accent-green); }
    .kpi-card.red .kpi-value { color: var(--accent-red); }
    .kpi-card.red { border-bottom: 2px solid var(--accent-red); }
    .kpi-card.blue .kpi-value { color: var(--accent-blue); }
    .kpi-card.blue { border-bottom: 2px solid var(--accent-blue); }
    .kpi-card.purple .kpi-value { color: var(--accent-purple); }
    .kpi-card.purple { border-bottom: 2px solid var(--accent-purple); }
    .kpi-card.amber .kpi-value { color: var(--accent-amber); }
    .kpi-card.amber { border-bottom: 2px solid var(--accent-amber); }

    /* ── Stats Bar ────────────────────────────────────────────────── */
    .stats-bar {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 0.9rem 1.6rem;
        margin-top: 0.8rem;
    }
    .stats-bar .stat-item {
        text-align: center;
        flex: 1;
    }
    .stats-bar .stat-item:not(:last-child) {
        border-right: 1px solid var(--border-subtle);
    }
    .stats-bar .stat-label {
        color: var(--text-muted);
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .stats-bar .stat-value {
        color: var(--text-primary);
        font-size: 1.15rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        margin-top: 2px;
    }

    /* ── Section Header ───────────────────────────────────────────── */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-subtle);
    }
    .section-header .section-icon {
        width: 36px; height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--accent-blue-glow);
        border-radius: var(--radius-sm);
        font-size: 1.1rem;
        flex-shrink: 0;
    }
    .section-header h3 {
        color: var(--text-primary);
        font-size: 1.05rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.3px;
    }
    .section-header .section-desc {
        color: var(--text-muted);
        font-size: 0.75rem;
        margin: 2px 0 0 0;
        font-weight: 400;
    }

    /* ── Card Container ───────────────────────────────────────────── */
    .card-container {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    .card-container .card-title {
        color: var(--text-secondary);
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.8rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid var(--border-subtle);
    }

    /* ── Footer ───────────────────────────────────────────────────── */
    .dashboard-footer {
        margin-top: 3rem;
        padding: 1.2rem 0;
        border-top: 1px solid var(--border-subtle);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .dashboard-footer .footer-brand {
        color: var(--text-muted);
        font-size: 0.72rem;
        font-weight: 500;
    }
    .dashboard-footer .footer-version {
        color: var(--text-muted);
        font-size: 0.68rem;
        font-family: 'JetBrains Mono', monospace;
        background: rgba(255,255,255,0.04);
        padding: 3px 10px;
        border-radius: 4px;
    }

    /* ── Streamlit widget overrides ────────────────────────────────── */
    .stSelectbox > div > div,
    .stDateInput > div > div {
        background-color: var(--bg-card-solid) !important;
        border-color: var(--border-subtle) !important;
        border-radius: var(--radius-sm) !important;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)) !important;
        border: none !important;
        border-radius: var(--radius-sm) !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    .stDownloadButton > button:hover {
        box-shadow: 0 4px 15px rgba(59,130,246,0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Calendar Grid ────────────────────────────────────────────── */
    .calendar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1.5rem;
        background: var(--bg-card);
        padding: 1rem;
        border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);
    }
    .calendar-header h3 {
        margin: 0;
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--text-primary);
    }
    .calendar-nav-btn {
        background: var(--bg-card-hover);
        border: 1px solid var(--border-subtle);
        color: var(--text-primary);
        padding: 0.4rem 0.8rem;
        border-radius: var(--radius-sm);
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 600;
    }
    .calendar-nav-btn:hover {
        background: var(--accent-blue);
        border-color: var(--accent-blue);
        color: white;
    }

    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 0.8rem;
    }
    
    .day-header {
        text-align: center;
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-muted);
        text-transform: uppercase;
        padding-bottom: 0.5rem;
    }

    .day-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: var(--radius-md);
        padding: 0.8rem;
        min-height: 100px;
        position: relative;
        transition: all 0.2s;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        align-items: center;
    }
    .day-card:hover {
        border-color: var(--border-color);
        transform: translateY(-2px);
    }
    .day-card.empty {
        background: transparent;
        border: none;
    }
    
    .day-date {
        font-size: 0.9rem;
        font-weight: 700;
        color: var(--text-secondary);
        margin-bottom: 0.4rem;
    }
    
    .day-pnl {
        font-size: 0.85rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .day-card.positive {
        background: rgba(16, 185, 129, 0.05);
        border-color: rgba(16, 185, 129, 0.2);
    }
    .day-card.positive .day-pnl { color: var(--accent-green); }
    
    .day-card.negative {
        background: rgba(239, 68, 68, 0.05);
        border-color: rgba(239, 68, 68, 0.2);
    }
    .day-card.negative .day-pnl { color: var(--accent-red); }
    
    .day-card.neutral {
        opacity: 0.6;
    }
    .day-card.neutral .day-pnl { color: var(--text-muted); }

    /* ── Responsive ────────────────────────────────────────────────── */
    @media (max-width: 768px) {
        .dashboard-header { padding: 1.2rem 1rem; }
        .dashboard-header h1 { font-size: 1.3rem; }
        .dashboard-header .subtitle { font-size: 0.75rem; }
        
        /* KPI Cards Stacking/Grid */
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 auto !important;
            min-width: 100% !important;
            margin-bottom: 1rem;
        }
        
        /* KPI Value Size Adjustment */
        .kpi-card .kpi-value { font-size: 1.4rem; }
        
        /* Stats Bar Stacking */
        .stats-bar { flex-direction: column; gap: 0.5rem; }
        .stats-bar .stat-item { border-right: none !important; border-bottom: 1px solid var(--border-subtle); padding-bottom: 0.5rem; }
        .stats-bar .stat-item:last-child { border-bottom: none; }
        
        /* Chart Containers */
        .js-plotly-plot { margin-bottom: 1rem; }
        
        /* Calendar Mobile */
        .calendar-grid { grid-template-columns: repeat(7, 1fr); gap: 4px; }
        .day-card { min-height: 60px; padding: 4px; }
        .day-date { font-size: 0.75rem; }
        .day-pnl { font-size: 0.65rem; }
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# PLOTLY THEME HELPER
# =============================================================================
def get_plotly_layout(**overrides):
    """Return a consistent dark-theme Plotly layout dict."""
    base = dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(17,24,39,0.5)',
        font=dict(color='#94a3b8', family='Inter, sans-serif', size=12),
        margin=dict(l=40, r=20, t=30, b=40),
        xaxis=dict(
            gridcolor='rgba(255,255,255,0.04)',
            zerolinecolor='rgba(255,255,255,0.08)',
            linecolor='rgba(255,255,255,0.06)',
        ),
        yaxis=dict(
            gridcolor='rgba(255,255,255,0.04)',
            zerolinecolor='rgba(255,255,255,0.08)',
            linecolor='rgba(255,255,255,0.06)',
        ),
        hoverlabel=dict(
            bgcolor='#1e293b',
            bordercolor='#334155',
            font=dict(color='#f1f5f9', family='Inter'),
        ),
        legend=dict(
            bgcolor='rgba(0,0,0,0)',
            borderwidth=0,
            font=dict(color='#94a3b8'),
        ),
        title="",
    )
    base.update(overrides)
    return base


# =============================================================================
# DATA LOADING
# =============================================================================
@st.cache_data(ttl=60)
def get_data():
    journal = TradeJournal()
    df = journal.load_trades()
    
    # Convert Timestamp to WIB (UTC+7)
    if not df.empty and 'timestamp' in df.columns:
        # 1. Ensure datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 2. Localize/Convert
        # Asumsi data di save as Naive/UTC by journal module
        # Force UTC first if naive, then convert to Asia/Jakarta
        df['timestamp'] = df['timestamp'].dt.tz_localize('UTC').dt.tz_convert('Asia/Jakarta')
        
        # 3. Remove tz info for cleaner display in some widgets (optional, but requested for display)
        # But Streamlit/Pandas handles tz-aware well usually. 
        # Let's keep it tz-aware 'Asia/Jakarta' so date extraction works correctly as local date.
    
    return df

df = get_data()

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================
st.sidebar.markdown("## 🔍 Filters")

if not df.empty:
    # Data is already converted to WIB in get_data()
    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    
    date_range = st.sidebar.date_input(
        "📅 Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    all_symbols = ['All'] + list(df['symbol'].unique())
    selected_symbol = st.sidebar.selectbox("🪙 Symbol", all_symbols)
    
    all_strategies = ['All'] + list(df['strategy_tag'].unique())
    selected_strategy = st.sidebar.selectbox("🧠 Strategy", all_strategies)

    # Apply Filters
    df_filtered = df.copy()
    
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df_filtered[
            (df_filtered['timestamp'].dt.date >= start_date) & 
            (df_filtered['timestamp'].dt.date <= end_date)
        ]
    
    if selected_symbol != 'All':
        df_filtered = df_filtered[df_filtered['symbol'] == selected_symbol]
    if selected_strategy != 'All':
        df_filtered = df_filtered[df_filtered['strategy_tag'] == selected_strategy]
else:
    st.sidebar.warning("No Data Available")
    df_filtered = pd.DataFrame()


# Sidebar footer
st.sidebar.markdown("---")
st.sidebar.markdown(
    '<p style="color:#64748b; font-size:0.7rem; text-align:center;">Bot Trading Dashboard v3.0</p>',
    unsafe_allow_html=True,
)


# =============================================================================
# HEADER
# =============================================================================
st.markdown("""
<div class="dashboard-header">
    <h1>⚡ Bot Trading Easy Peasy</h1>
    <p class="subtitle">Performance Analytics Dashboard — Analisis otomatis untuk performa trading Anda.</p>
    <div class="header-status">
        <div class="dot"></div>
        LIVE · Auto-refresh setiap 60 detik
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# EMPTY STATE GUARD
# =============================================================================
if df.empty:
    st.markdown("""
    <div class="card-container" style="text-align:center; padding: 3rem;">
        <p style="font-size: 2rem; margin-bottom: 0.5rem;">👋</p>
        <p style="color: var(--text-secondary); font-size: 1rem;">Belum ada data trading.</p>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Jalankan bot untuk mulai merekam trade.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if df_filtered.empty:
    st.markdown("""
    <div class="card-container" style="text-align:center; padding: 3rem;">
        <p style="font-size: 2rem; margin-bottom: 0.5rem;">⚠️</p>
        <p style="color: var(--text-secondary); font-size: 1rem;">Tidak ada data yang cocok dengan filter.</p>
        <p style="color: var(--text-muted); font-size: 0.85rem;">Coba ubah filter di sidebar.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# =============================================================================
# CALCULATIONS
# =============================================================================
total_trades = len(df_filtered)
win_trades = df_filtered[df_filtered['result'] == 'WIN']
loss_trades = df_filtered[df_filtered['result'] == 'LOSS']
canceled_trades_count = len(df_filtered[df_filtered['result'] == 'CANCELLED'])
timeout_trades_count = len(df_filtered[df_filtered['result'] == 'TIMEOUT'])

completed_trades_count = len(win_trades) + len(loss_trades)
win_rate = (len(win_trades) / completed_trades_count * 100) if completed_trades_count > 0 else 0

total_pnl = df_filtered['pnl_usdt'].sum()
gross_profit = win_trades['pnl_usdt'].sum()
gross_loss = abs(loss_trades['pnl_usdt'].sum())
profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

avg_win = win_trades['pnl_usdt'].mean() if not win_trades.empty else 0
avg_loss = loss_trades['pnl_usdt'].mean() if not loss_trades.empty else 0


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def calculate_streaks(df):
    if df.empty:
        return 0, 0, 0
    
    # Sort by time just in case
    df_sorted = df.sort_values('timestamp')
    
    current_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    
    streak_counter = 0
    
    for idx, row in df_sorted.iterrows():
        pnl = row['pnl_usdt']
        res = row.get('result', '')
        
        # Skip cancelled trades for streak calculation to preserve streak
        if res in ['CANCELLED', 'TIMEOUT']:
            continue 
            
        if pnl > 0:
            if streak_counter >= 0:
                streak_counter += 1
            else:
                streak_counter = 1
        elif pnl < 0:
            if streak_counter <= 0:
                streak_counter -= 1
            else:
                streak_counter = -1
        else:
            streak_counter = 0
            
        if streak_counter > max_win_streak: max_win_streak = streak_counter
        if streak_counter < max_loss_streak: max_loss_streak = streak_counter
    
    current_streak = streak_counter
    return current_streak, max_win_streak, abs(max_loss_streak)

# Extract Model Info from Config Snapshot
def extract_model_info(row):
    cfg = row.get('config_snapshot', '{}')
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except:
            cfg = {}
    elif not isinstance(cfg, dict):
        cfg = {}
        
    return pd.Series([
        cfg.get('ai_model', 'Unknown'), 
        cfg.get('vision_model', '-'),
        cfg.get('sentiment_model', '-')
    ])

if not df_filtered.empty:
    df_filtered[['ai_model', 'vision_model', 'sentiment_model']] = df_filtered.apply(extract_model_info, axis=1)

    # Extract Technical & Additional Config Features
    def extract_features(row):
        tech = {}
        try:
            tech = json.loads(row.get('technical_data', '{}'))
        except:
            pass
            
        cfg = {}
        try:
            cfg = json.loads(row.get('config_snapshot', '{}'))
        except:
            pass
            
        return pd.Series([
            float(tech.get('rsi', 0) or 0),
            float(tech.get('atr', 0) or 0),
            float(tech.get('adx', 0) or 0),
            float(cfg.get('leverage', 0) or 0),
            1 if row['pnl_usdt'] > 0 else 0
        ])

    df_filtered[['rsi', 'atr', 'adx', 'leverage', 'is_win']] = df_filtered.apply(extract_features, axis=1)
    
    # Time features
    df_filtered['hour'] = df_filtered['timestamp'].dt.hour
    df_filtered['day_name'] = df_filtered['timestamp'].dt.day_name()

    # -------------------------------------------------------------------------
    # FIX: Force strict numeric types for Plotly to avoid ValueError
    # -------------------------------------------------------------------------
    numeric_cols = ['pnl_usdt', 'roi_percent', 'leverage', 'rsi', 'atr', 'adx', 'entry_price', 'size_usdt']
    for col in numeric_cols:
        if col in df_filtered.columns:
            # Coerce errors (strings/bad data) to NaN, then fill with 0.0 to keep it safe
            df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0.0)


# Stats Calculation
current_streak, max_win, max_loss = calculate_streaks(df_filtered)

pnl_sign = "+" if total_pnl >= 0 else ""
pnl_color_class = "green" if total_pnl >= 0 else "red"
wr_color_class = "green" if win_rate >= 50 else ("amber" if win_rate >= 40 else "red")


# =============================================================================
# KPI CARDS
# =============================================================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="kpi-card blue">
        <div class="kpi-icon">📊</div>
        <div class="kpi-label">Total Trades</div>
        <div class="kpi-value">{total_trades}</div>
        <div class="kpi-sub">{completed_trades_count} done · {canceled_trades_count} cnl · {timeout_trades_count} t/o</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card {wr_color_class}">
        <div class="kpi-icon">🎯</div>
        <div class="kpi-label">Win Rate</div>
        <div class="kpi-value">{win_rate:.1f}%</div>
        <div class="kpi-sub">{len(win_trades)}W · {len(loss_trades)}L</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card {pnl_color_class}">
        <div class="kpi-icon">💰</div>
        <div class="kpi-label">Net PnL (USDT)</div>
        <div class="kpi-value">{pnl_sign}${total_pnl:.2f}</div>
        <div class="kpi-sub">Profit Factor: {profit_factor:.2f}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    pf_class = "green" if profit_factor >= 1.5 else ("amber" if profit_factor >= 1.0 else "red")
    st.markdown(f"""
    <div class="kpi-card purple">
        <div class="kpi-icon">📈</div>
        <div class="kpi-label">Avg Win / Loss</div>
        <div class="kpi-value">${avg_win:.2f}</div>
        <div class="kpi-sub" style="color: var(--accent-red);">${avg_loss:.2f} avg loss</div>
    </div>
    """, unsafe_allow_html=True)


# Additional Stats Bar
st.markdown(f"""
<div class="stats-bar">
    <div class="stat-item">
        <div class="stat-label">Streak (Curr/Max)</div>
        <div class="stat-value">{current_streak} / +{max_win}</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Max Drawdown Streak</div>
        <div class="stat-value" style="color: var(--accent-red);">{max_loss}L</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Gross Profit</div>
        <div class="stat-value" style="color: var(--accent-green);">+${gross_profit:.2f}</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Gross Loss</div>
        <div class="stat-value" style="color: var(--accent-red);">-${gross_loss:.2f}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# CHARTS ROW 1 — Equity Curve + Win/Loss Pie
# =============================================================================
st.markdown("""
<div class="section-header">
    <div class="section-icon">📈</div>
    <div>
        <h3>Equity Curve & Distribution</h3>
        <p class="section-desc">Pertumbuhan akumulatif PnL dan distribusi hasil trading</p>
    </div>
</div>
""", unsafe_allow_html=True)

col_chart1, col_chart2 = st.columns([2, 1])

with col_chart1:
    df_sorted = df_filtered.sort_values(by='timestamp')
    df_sorted['cumulative_pnl'] = df_sorted['pnl_usdt'].cumsum()
    
    fig_equity = go.Figure()
    
    # Fill area
    fig_equity.add_trace(go.Scatter(
        x=df_sorted['timestamp'], y=df_sorted['cumulative_pnl'],
        mode='lines+markers',
        line=dict(color='#3b82f6', width=2.5),
        marker=dict(size=5, color='#3b82f6', line=dict(width=1, color='#1e293b')),
        fill='tozeroy',
        fillcolor='rgba(59,130,246,0.08)',
        name='Cumulative PnL',
        hovertemplate='<b>%{x|%d/%m %H:%M}</b><br>PnL: $%{y:.2f}<extra></extra>',
    ))
    
    fig_equity.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.15)", line_width=1)
    fig_equity.update_layout(**get_plotly_layout(height=380))
    st.plotly_chart(fig_equity, use_container_width=True)

with col_chart2:
    color_map = {'WIN': '#10b981', 'LOSS': '#ef4444', 'BREAKEVEN': '#f59e0b', 'CANCELLED': '#94a3b8', 'TIMEOUT': '#64748b'}
    result_counts = df_filtered['result'].value_counts()
    
    fig_pie = go.Figure(data=[go.Pie(
        labels=result_counts.index,
        values=result_counts.values,
        marker=dict(colors=[color_map.get(r, '#64748b') for r in result_counts.index],
                    line=dict(color='#0a0e17', width=2)),
        textfont=dict(color='#f1f5f9', size=12),
        hole=0.55,
        hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>',
    )])
    
    fig_pie.update_layout(**get_plotly_layout(
        height=380,
        showlegend=True,
        legend=dict(
            orientation='h', yanchor='bottom', y=-0.15,
            xanchor='center', x=0.5,
            font=dict(color='#94a3b8', size=11),
        ),
        annotations=[dict(
            text=f'<b>{win_rate:.0f}%</b><br><span style="font-size:10px;color:#94a3b8">Win Rate</span>',
            x=0.5, y=0.5, font=dict(size=20, color='#f1f5f9'),
            showarrow=False,
        )],
    ))
    st.plotly_chart(fig_pie, use_container_width=True)


# =============================================================================
# CHARTS ROW 2 — PnL by Symbol + PnL by Strategy
# =============================================================================
# =============================================================================
# CHARTS ROW 2 — ADVANCED ANALYTICS (TABS)
# =============================================================================
st.markdown("""
<div class="section-header">
    <div class="section-icon">🔬</div>
    <div>
        <h3>Analisis Performa Mendalam</h3>
        <p class="section-desc">Breakdown berdasarkan Koin, Strategi, dan Model AI</p>
    </div>
</div>
""", unsafe_allow_html=True)

tab_symbol, tab_strat, tab_model, tab_correlation, tab_daily, tab_calendar, tab_drawdown, tab_dist = st.tabs([
    "🪙 Symbol", "🧠 Strategy", "🤖 Model", "🔍 Correlation", "📅 Daily PnL", "🗓️ Calendar", "📉 Drawdown", "📊 Distribution"
])

with tab_symbol:
    # Prepare Data
    pnl_by_symbol = df_filtered.groupby('symbol').agg(
        Total_PnL=('pnl_usdt', 'sum'),
        Win_Rate=('result', lambda x: (x == 'WIN').mean() * 100),
        Count=('result', 'count')
    ).reset_index()
    
    pnl_by_symbol = pnl_by_symbol.sort_values(by='Total_PnL', ascending=True)
    
    col_sym1, col_sym2 = st.columns(2)
    
    with col_sym1:
        # Chart PnL
        bar_colors = ['#10b981' if v >= 0 else '#ef4444' for v in pnl_by_symbol['Total_PnL']]
        fig_symbol = go.Figure(data=[go.Bar(
            x=pnl_by_symbol['Total_PnL'], y=pnl_by_symbol['symbol'],
            orientation='h',
            marker=dict(color=bar_colors, line=dict(width=0)),
            hovertemplate='<b>%{y}</b><br>PnL: $%{x:.2f}<extra></extra>',
        )])
        fig_symbol.update_layout(**get_plotly_layout(height=400, title="Net PnL per Symbol"))
        st.plotly_chart(fig_symbol, use_container_width=True)
        
    with col_sym2:
        # Chart Win Rate
        fig_wr = go.Figure(data=[go.Bar(
            x=pnl_by_symbol['Win_Rate'], y=pnl_by_symbol['symbol'],
            orientation='h',
            marker=dict(color='#3b82f6', line=dict(width=0)),
            hovertemplate='<b>%{y}</b><br>Win Rate: %{x:.1f}%<br>Trades: %{customdata}',
            customdata=pnl_by_symbol['Count']
        )])
        fig_wr.update_layout(**get_plotly_layout(height=400, title="Win Rate per Symbol (%)"))
        fig_wr.update_xaxes(range=[0, 100])
        st.plotly_chart(fig_wr, use_container_width=True)

with tab_strat:
    pnl_by_strat = df_filtered.groupby('strategy_tag')['pnl_usdt'].sum().reset_index()
    pnl_by_strat = pnl_by_strat.sort_values(by='pnl_usdt', ascending=True)
    
    bar_colors_strat = ['#10b981' if v >= 0 else '#ef4444' for v in pnl_by_strat['pnl_usdt']]
    
    fig_strat = go.Figure(data=[go.Bar(
        x=pnl_by_strat['pnl_usdt'], y=pnl_by_strat['strategy_tag'],
        orientation='h',
        marker=dict(color=bar_colors_strat, line=dict(width=0)),
        hovertemplate='<b>%{y}</b><br>PnL: $%{x:.2f}<extra></extra>',
    )])
    fig_strat.update_layout(**get_plotly_layout(height=400, title="Net PnL by Strategy"))
    st.plotly_chart(fig_strat, use_container_width=True)

with tab_model:
    if 'ai_model' in df_filtered.columns:
        pnl_by_model = df_filtered.groupby('ai_model')['pnl_usdt'].sum().reset_index()
        pnl_by_model = pnl_by_model.sort_values(by='pnl_usdt', ascending=True)
        
        # Color based on value
        colors_model = ['#8b5cf6' if v >= 0 else '#ef4444' for v in pnl_by_model['pnl_usdt']]
        
        fig_model = go.Figure(data=[go.Bar(
            x=pnl_by_model['pnl_usdt'], y=pnl_by_model['ai_model'],
            orientation='h',
            marker=dict(color=colors_model, line=dict(width=0)),
            text=pnl_by_model['pnl_usdt'].apply(lambda x: f"${x:.2f}"),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>PnL: $%{x:.2f}<extra></extra>',
        )])
        fig_model.update_layout(**get_plotly_layout(height=400, title="AI Model Performance"))
        st.plotly_chart(fig_model, use_container_width=True)
    else:
        st.info("Data AI Model belum tersedia.")

with tab_correlation:
    st.markdown("#### 🔗 Analisis Korelasi & Faktor Penentu Win Rate")
    
    # 1. Correlation Matrix Heatmap
    st.markdown("##### 1. Korelasi Variabel Numerik")
    st.caption("Seberapa kuat hubungan antar variabel? (1.0 = Sangat Kuat Positif, -1.0 = Sangat Kuat Negatif)")
    
    corr_cols = ['pnl_usdt', 'roi_percent', 'leverage', 'rsi', 'atr', 'adx', 'entry_price', 'size_usdt']
    # Filter columns that exist
    available_corr_cols = [c for c in corr_cols if c in df_filtered.columns]
    
    # Strictly for Heatmap, we might still want variance > 0 to avoid messy charts, 
    # but for Scatter we want at least existence.
    heat_corr_cols = [c for c in available_corr_cols if df_filtered[c].var() > 0] if len(df_filtered) > 1 else []

    if len(heat_corr_cols) > 1:
        corr_matrix = df_filtered[heat_corr_cols].corr()

        
        fig_corr = px.imshow(
            corr_matrix,
            text_auto='.2f',
            aspect="auto",
            color_continuous_scale='RdBu_r',
            zmin=-1, zmax=1
        )
        fig_corr.update_layout(**get_plotly_layout(height=500, title="Correlation Matrix"))
        st.plotly_chart(fig_corr, use_container_width=True)
    else:
        st.info("Data tidak cukup variatif untuk membuat matriks korelasi.")
        
    st.divider()

    # 2. AI Model Performance Details
    st.markdown("##### 2. Performa Berdasarkan Model AI")
    
    col_ai1, col_ai2 = st.columns(2)
    
    with col_ai1:
        # Win Rate per Model
        if 'ai_model' in df_filtered.columns:
            wr_model = df_filtered.groupby('ai_model').agg(
                Win_Rate=('is_win', 'mean'),
                Count=('is_win', 'count')
            ).reset_index()
            wr_model['Win_Rate'] *= 100
            
            fig_ai_wr = go.Figure(data=[go.Bar(
                x=wr_model['Win_Rate'], y=wr_model['ai_model'],
                orientation='h',
                marker=dict(color='#3b82f6'),
                text=wr_model['Win_Rate'].apply(lambda x: f"{x:.1f}%"),
                textposition='auto'
            )])
            fig_ai_wr.update_layout(**get_plotly_layout(height=350, title="Win Rate per AI Model"))
            fig_ai_wr.update_xaxes(range=[0, 100])
            st.plotly_chart(fig_ai_wr, use_container_width=True)
            
    with col_ai2:
        # PnL Distribution per Model (Box Plot)
        if 'ai_model' in df_filtered.columns:
            fig_ai_box = px.box(
                df_filtered, x="pnl_usdt", y="ai_model",
                color="ai_model",
                points="all" # Show all points
            )
            fig_ai_box.update_layout(**get_plotly_layout(height=350, title="Distribusi PnL per AI Model"))
            st.plotly_chart(fig_ai_box, use_container_width=True)
            
    st.divider()
    
    # 3. Interactive Scatter Plot
    st.markdown("##### 3. Deep Dive Scatter Plot")
    
    sc_col1, sc_col2, sc_col3 = st.columns(3)
    with sc_col1:
        x_axis = st.selectbox("Sumbu X", available_corr_cols, index=available_corr_cols.index('rsi') if 'rsi' in available_corr_cols else 0)
    with sc_col2:
        y_axis = st.selectbox("Sumbu Y", available_corr_cols, index=available_corr_cols.index('pnl_usdt') if 'pnl_usdt' in available_corr_cols else 0)
    with sc_col3:
        color_dim = st.selectbox("Warna", ['result', 'ai_model', 'strategy_tag'])

    if available_corr_cols:
        fig_scatter = px.scatter(
            df_filtered, x=x_axis, y=y_axis,
            color=color_dim,
            hover_data=['symbol', 'timestamp'],
            color_discrete_map={'WIN': '#10b981', 'LOSS': '#ef4444', 'CANCELLED': '#94a3b8', 'TIMEOUT': '#64748b'}
        )
        fig_scatter.update_layout(**get_plotly_layout(height=500, title=f"{x_axis} vs {y_axis}"))
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Data tidak mencukupi untuk membuat scatter plot.")


with tab_daily:
    # Aggregating PnL by Day
    df_daily = df_filtered.copy()
    df_daily['date'] = df_daily['timestamp'].dt.date
    daily_stats = df_daily.groupby('date')['pnl_usdt'].sum().reset_index()
    
    colors_daily = ['#10b981' if v >= 0 else '#ef4444' for v in daily_stats['pnl_usdt']]
    
    fig_daily = go.Figure(data=[go.Bar(
        x=daily_stats['date'], y=daily_stats['pnl_usdt'],
        marker=dict(color=colors_daily),
        hovertemplate='<b>%{x}</b><br>PnL: $%{y:.2f}<extra></extra>'
    )])
    fig_daily.update_layout(**get_plotly_layout(height=400, title="Daily PnL Performance"))
    st.plotly_chart(fig_daily, use_container_width=True)

with tab_calendar:
    # PnL Calendar View (Custom Grid)
    
    # 1. Initialize Session State for Calendar Navigation
    if 'cal_year' not in st.session_state:
        st.session_state.cal_year = datetime.now().year
    if 'cal_month' not in st.session_state:
        st.session_state.cal_month = datetime.now().month

    # 2. Navigation Functions
    def prev_month():
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1

    def next_month():
        if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
        else:
            st.session_state.cal_month += 1

    # 3. Prepare Data for Selected Month
    current_year = st.session_state.cal_year
    current_month = st.session_state.cal_month
    
    # Filter data for this specific month
    df_cal = df_filtered.copy()
    df_cal['date'] = df_cal['timestamp'].dt.date
    month_data = df_cal[
        (df_cal['timestamp'].dt.year == current_year) & 
        (df_cal['timestamp'].dt.month == current_month)
    ]
    
    # Aggregate PnL by day
    daily_pnl = month_data.groupby('date')['pnl_usdt'].sum().to_dict()
    
    # 4. Calendar Header (Navigation)
    month_name = calendar.month_name[current_month]
    
    col_prev, col_title, col_next = st.columns([1, 4, 1])
    with col_prev:
        st.button("◀ Prev", on_click=prev_month, key="btn_prev_month", use_container_width=True)
    with col_title:
        st.markdown(
            f"<h3 style='text-align: center; margin: 0; padding-top: 5px;'>{month_name} {current_year}</h3>", 
            unsafe_allow_html=True
        )
    with col_next:
        st.button("Next ▶", on_click=next_month, key="btn_next_month", use_container_width=True)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Calendar Grid Rendering
    # Day Headers
    cols = st.columns(7)
    days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] # Sunday first for standard view? 
    # Python calendar.monthcalendar uses Monday (0) to Sunday (6).
    # Let's align with standard Python calendar: Mon-Sun
    days_header = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    for i, day in enumerate(days_header):
        cols[i].markdown(f"<div class='day-header'>{day}</div>", unsafe_allow_html=True)
        
    # Get weeks matrix (0 means date belongs to prev/next month)
    cal = calendar.monthcalendar(current_year, current_month)
    
    for week in cal:
        cols = st.columns(7)
        for i, day_num in enumerate(week):
            if day_num == 0:
                # Empty cell
                cols[i].markdown("<div class='day-card empty'></div>", unsafe_allow_html=True)
            else:
                # Actual date cell
                date_obj = datetime(current_year, current_month, day_num).date()
                pnl = daily_pnl.get(date_obj, 0.0)
                
                # Determine styling
                card_class = "neutral"
                pnl_text = f"{pnl:.2f}"
                
                if pnl > 0:
                    card_class = "positive"
                    pnl_text = f"+{pnl:.2f}"
                elif pnl < 0:
                    card_class = "negative"
                    pnl_text = f"{pnl:.2f}"
                elif pnl == 0 and date_obj in daily_pnl:
                     # Explicit 0 PnL trades
                    card_class = "neutral"
                    pnl_text = "0.00"
                else:
                    # No trades
                    card_class = "neutral"
                    pnl_text = "-"

                cols[i].markdown(f"""
                <div class='day-card {card_class}'>
                    <div class='day-date'>{html.escape(str(day_num))}</div>
                    <div class='day-pnl'>{html.escape(pnl_text)}</div>
                </div>
                """, unsafe_allow_html=True)


with tab_drawdown:
    # Calculate Drawdown
    df_dd = df_filtered.sort_values(by='timestamp')
    df_dd['cumulative'] = df_dd['pnl_usdt'].cumsum()
    df_dd['high_water_mark'] = df_dd['cumulative'].cummax()
    df_dd['drawdown'] = df_dd['cumulative'] - df_dd['high_water_mark']
    
    # Drawdown Percentage (approx if capital known, using absolute $ here as requested "Area chart")
    # If we want %, we need starting capital. We'll stick to $ Drawdown for now.
    
    fig_dd = go.Figure()
    fig_dd.add_trace(go.Scatter(
        x=df_dd['timestamp'], y=df_dd['drawdown'],
        fill='tozeroy',
        fillcolor='rgba(239,68,68,0.2)',
        line=dict(color='#ef4444', width=1.5),
        name='Drawdown ($)'
    ))
    fig_dd.update_layout(**get_plotly_layout(height=400, title="Equity Drawdown ($)"))
    st.plotly_chart(fig_dd, use_container_width=True)

with tab_dist:
    # PnL Distribution
    fig_dist = px.histogram(
        df_filtered, x="pnl_usdt", nbins=30,
        color_discrete_sequence=['#3b82f6'],
        title="PnL Distribution (Histogram)"
    )
    fig_dist.update_layout(**get_plotly_layout(height=400))
    fig_dist.update_traces(marker_line_width=1, marker_line_color="#1e293b")
    st.plotly_chart(fig_dist, use_container_width=True)


# =============================================================================
# HEATMAP
# =============================================================================
st.markdown("""
<div class="section-header">
    <div class="section-icon">🔥</div>
    <div>
        <h3>Trading Activity Heatmap</h3>
        <p class="section-desc">Pola waktu trading paling aktif selama seminggu</p>
    </div>
</div>
""", unsafe_allow_html=True)

df_heat = df_filtered.copy()
df_heat['hour'] = df_heat['timestamp'].dt.hour
df_heat['day'] = df_heat['timestamp'].dt.day_name()

days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
df_heat['day'] = pd.Categorical(df_heat['day'], categories=days_order, ordered=True)

heatmap_data = df_heat.groupby(['day', 'hour']).size().reset_index(name='count')

fig_heat = go.Figure(data=go.Heatmap(
    z=heatmap_data['count'],
    x=heatmap_data['hour'],
    y=heatmap_data['day'],
    colorscale=[
        [0, 'rgba(17,24,39,0.8)'],
        [0.25, 'rgba(59,130,246,0.2)'],
        [0.5, 'rgba(59,130,246,0.4)'],
        [0.75, 'rgba(139,92,246,0.6)'],
        [1, 'rgba(139,92,246,0.9)'],
    ],
    hovertemplate='<b>%{y}</b> %{x}:00<br>Trades: %{z}<extra></extra>',
    showscale=False,
))
fig_heat.update_layout(**get_plotly_layout(height=300))
fig_heat.update_xaxes(dtick=1, title=None)
fig_heat.update_yaxes(title=None)
st.plotly_chart(fig_heat, use_container_width=True)


# =============================================================================
# TRADE HISTORY TABLE
# =============================================================================
st.markdown("""
<div class="section-header">
    <div class="section-icon">📋</div>
    <div>
        <h3>Trade History & AI Insights</h3>
        <p class="section-desc">Riwayat lengkap semua trade beserta analisis AI</p>
    </div>
</div>
""", unsafe_allow_html=True)

display_cols = ['timestamp', 'symbol', 'side', 'type', 'entry_price', 'exit_price', 'pnl_usdt', 'roi_percent', 'strategy_tag', 'prompt', 'reason', 'setup_at', 'filled_at', 'technical_data', 'config_snapshot']
for col in ['setup_at', 'filled_at', 'technical_data', 'config_snapshot']:
    if col not in df_filtered.columns:
        df_filtered[col] = None

df_display = df_filtered[display_cols].copy()


def calc_duration(start, end):
    if pd.isna(start) or pd.isna(end) or start == '' or end == '':
        return None
    try:
        s = pd.to_datetime(start)
        e = pd.to_datetime(end)
        diff = e - s
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0:
            return None
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours}j {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except:
        return None


df_display['Setup->Fill'] = df_display.apply(lambda x: calc_duration(x['setup_at'], x['filled_at']), axis=1)
df_display['Trade Duration'] = df_display.apply(lambda x: calc_duration(x['filled_at'], x['timestamp']), axis=1)

df_display = df_display.sort_values(by='timestamp', ascending=False)
df_display = df_display.drop(columns=['setup_at', 'filled_at'])

st.dataframe(
    df_display,
    column_config={
        "timestamp": st.column_config.DatetimeColumn("Time", format="DD/MM/YYYY HH:mm"),
        "pnl_usdt": st.column_config.NumberColumn("PnL ($)", format="$%.2f"),
        "roi_percent": st.column_config.NumberColumn("ROI (%)", format="%.2f%%"),
        "strategy_tag": st.column_config.Column("Strategy"),
        "symbol": st.column_config.Column("Symbol"),
        "side": st.column_config.Column("Side"),
        "type": st.column_config.Column("Type"),
        "entry_price": st.column_config.NumberColumn("Entry Price", format="$%.4f"),
        "exit_price": st.column_config.NumberColumn("Exit Price", format="$%.4f"),
        "prompt": st.column_config.TextColumn("AI Prompt", width="medium"),
        "reason": st.column_config.TextColumn("AI Reason", width="medium"),
        "Setup->Fill": st.column_config.Column("Setup ➝ Fill"),
        "Trade Duration": st.column_config.Column("Duration"),
        "technical_data": st.column_config.TextColumn("Technical Snapshot", width="large"),
        "config_snapshot": st.column_config.TextColumn("Config Snapshot", width="large"),
    },
    use_container_width=True,
    hide_index=True,
    height=500
)


# =============================================================================
# TRADE ANALYSIS & SHARING (COMBINED)
# =============================================================================
st.markdown("""
<div class="section-header">
    <div class="section-icon">🔍</div>
    <div>
        <h3>Analisis Trade & Share PnA</h3>
        <p class="section-desc">Detail teknikal lengkap dan kartu PnL untuk dibagikan</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Filter for completed trades (WIN/LOSS/BREAKEVEN) with safe check
if 'result' in df_filtered.columns:
    completed_df = df_filtered[df_filtered['result'].isin(['WIN', 'LOSS', 'BREAKEVEN'])].sort_values('timestamp', ascending=False)
else:
    completed_df = pd.DataFrame()

if not completed_df.empty:
    # 1. Trade Selector
    trade_choices = {}
    for idx, row in completed_df.iterrows():
        sym = row.get('symbol', '?')
        pnl_val = row.get('pnl_usdt', 0)
        res = row.get('result', '?')
        ts = row['timestamp'].strftime('%d/%m %H:%M') if pd.notna(row['timestamp']) else '?'
        label = f"{ts} — {sym} ({res}) ${pnl_val:.2f}"
        trade_choices[label] = row

    selected_trade_label = st.selectbox("Pilih Trade untuk Dianalisis:", list(trade_choices.keys()), key="combined_trade_select")

    if selected_trade_label:
        trade_row = trade_choices[selected_trade_label]
        
        # =================================================================
        # SECTION A: PNL CARD (TOP)
        # =================================================================
        st.markdown("#### 📸 Share PnL Card")
        
        trade_data = {
            'symbol': trade_row.get('symbol', 'UNKNOWN'),
            'side': trade_row.get('side', 'LONG'),
            'entry_price': float(trade_row.get('entry_price', 0)) if pd.notna(trade_row.get('entry_price')) else 0.0,
            'exit_price': float(trade_row.get('exit_price', 0)) if pd.notna(trade_row.get('exit_price')) else 0.0,
            'pnl_usdt': float(trade_row.get('pnl_usdt', 0)) if pd.notna(trade_row.get('pnl_usdt')) else 0.0,
            'roi_percent': float(trade_row.get('roi_percent', 0)) if pd.notna(trade_row.get('roi_percent')) else 0.0,
            'timestamp': trade_row['timestamp'],
            'leverage': get_coin_leverage(trade_row.get('symbol', 'UNKNOWN')),
            'strategy': trade_row.get('strategy_tag', '-')
        }

        try:
            pnl_gen = CryptoPnLGenerator()
            img_buffer = pnl_gen.generate_card(trade_data)
            
            col_preview, col_dl = st.columns([1, 1])
            with col_preview:
                 st.image(img_buffer, caption="Preview Kartu PnL", use_container_width=True)
            
            with col_dl:
                st.info("Kartu PnL ini siap dibagikan ke media sosial Anda.")
                outcome = "WIN" if trade_data['roi_percent'] >= 0 else "LOSS"
                file_name = f"PnL_{outcome}_{trade_data['symbol'].replace('/', '')}_{trade_data['timestamp'].strftime('%Y%m%d')}.png"
                
                st.download_button(
                    label="⬇️ Download Image",
                    data=img_buffer,
                    file_name=file_name,
                    mime="image/png",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Gagal membuat kartu PnL: {str(e)}")

        st.divider()

        # =================================================================
        # SECTION B: TECHNICAL & CONFIG DETAILS (BOTTOM)
        # =================================================================
        st.markdown("#### 🔧 Detail Teknikal & Konfigurasi")

        # Parse JSON safely
        def safe_parse_json(val):
            if pd.isna(val) or val == '' or val is None:
                return {}
            if isinstance(val, dict):
                return val
            try:
                return json.loads(str(val))
            except (json.JSONDecodeError, TypeError):
                return {}

        technical_data_col = 'technical_data'
        config_col = 'config_snapshot'
        
        tech_info = safe_parse_json(trade_row.get(technical_data_col, '{}')) if technical_data_col in trade_row else {}
        config_info = safe_parse_json(trade_row.get(config_col, '{}')) if config_col in trade_row else {}

        col_tech, col_cfg = st.columns([1, 1])
        
        with col_tech:
            st.markdown("""
            <div class="card-container">
                <div class="card-title">📊 Technical Snapshot</div>
            </div>
            """, unsafe_allow_html=True)

            if tech_info:
                # Indicators
                t1, t2, t3 = st.columns(3)
                t1.metric("RSI", f"{tech_info.get('rsi', 0):.1f}")
                t2.metric("ATR", f"{tech_info.get('atr', 0):.2f}")
                t3.metric("ADX", f"{tech_info.get('adx', 0):.1f}")
                
                st.markdown("---")
                
                # Signals
                t4, t5 = st.columns(2)
                t4.markdown(f"**Price:** ${tech_info.get('price', 0):,.2f}")
                t4.markdown(f"**EMA Trend:** {tech_info.get('price_vs_ema', '-')}")
                
                t5.markdown(f"**BTC Trend:** {tech_info.get('btc_trend', '-')}")
                t5.markdown(f"**Corr:** {tech_info.get('btc_correlation', '-')}")
                
                with st.expander("Full Technical Data"):
                    st.json(tech_info)
            else:
                st.info("Data teknikal tidak tersedia untuk trade ini.")

        with col_cfg:
            st.markdown("""
            <div class="card-container">
                <div class="card-title">⚙️ Config Snapshot</div>
            </div>
            """, unsafe_allow_html=True)

            if config_info:
                # Key Params
                c1, c2 = st.columns(2)
                c1.metric("Leverage", f"{config_info.get('leverage', '-')}")
                c1.metric("Risk %", f"{config_info.get('risk_percent', '-')}%")
                
                c2.markdown(f"**AI Model:** {config_info.get('ai_model', '-')}")
                c2.markdown(f"**Sentiment:** {config_info.get('sentiment_model', '-')}")
                
                with st.expander("Full Configuration"):
                    st.json(config_info)
            else:
                st.info("Data konfigurasi tidak tersedia.")

else:
    st.info("Belum ada trade yang selesai (WIN/LOSS/BREAKEVEN) untuk ditampilkan.")


# =============================================================================
# FOOTER
# =============================================================================
st.markdown("""
<div class="dashboard-footer">
    <div class="footer-brand">Bot Trading Easy Peasy — Performance Dashboard</div>
    <div class="footer-version">v3.0</div>
</div>
""", unsafe_allow_html=True)
