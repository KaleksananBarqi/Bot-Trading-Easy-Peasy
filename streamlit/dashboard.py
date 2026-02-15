
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import sys
import os

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
    return df

df = get_data()

# =============================================================================
# SIDEBAR FILTERS
# =============================================================================
st.sidebar.markdown("## 🔍 Filters")

if not df.empty:
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
expired_trades_count = len(df_filtered[df_filtered['result'] == 'EXPIRED'])

completed_trades_count = len(win_trades) + len(loss_trades)
win_rate = (len(win_trades) / completed_trades_count * 100) if completed_trades_count > 0 else 0

total_pnl = df_filtered['pnl_usdt'].sum()
gross_profit = win_trades['pnl_usdt'].sum()
gross_loss = abs(loss_trades['pnl_usdt'].sum())
profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

avg_win = win_trades['pnl_usdt'].mean() if not win_trades.empty else 0
avg_loss = loss_trades['pnl_usdt'].mean() if not loss_trades.empty else 0

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
        <div class="kpi-sub">{completed_trades_count} selesai</div>
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
        <div class="stat-label">Completed</div>
        <div class="stat-value">{completed_trades_count}</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Cancelled</div>
        <div class="stat-value" style="color: var(--text-muted);">{canceled_trades_count}</div>
    </div>
    <div class="stat-item">
        <div class="stat-label">Expired</div>
        <div class="stat-value" style="color: var(--text-muted);">{expired_trades_count}</div>
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
    color_map = {'WIN': '#10b981', 'LOSS': '#ef4444', 'BREAKEVEN': '#f59e0b', 'CANCELLED': '#64748b', 'EXPIRED': '#475569'}
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
st.markdown("""
<div class="section-header">
    <div class="section-icon">🔬</div>
    <div>
        <h3>Analisis Performa</h3>
        <p class="section-desc">Breakdown PnL berdasarkan koin dan strategi</p>
    </div>
</div>
""", unsafe_allow_html=True)

col_adv1, col_adv2 = st.columns(2)

with col_adv1:
    pnl_by_symbol = df_filtered.groupby('symbol')['pnl_usdt'].sum().reset_index()
    pnl_by_symbol = pnl_by_symbol.sort_values(by='pnl_usdt', ascending=True)
    
    bar_colors = ['#10b981' if v >= 0 else '#ef4444' for v in pnl_by_symbol['pnl_usdt']]
    
    fig_symbol = go.Figure(data=[go.Bar(
        x=pnl_by_symbol['pnl_usdt'], y=pnl_by_symbol['symbol'],
        orientation='h',
        marker=dict(color=bar_colors, line=dict(width=0)),
        hovertemplate='<b>%{y}</b><br>PnL: $%{x:.2f}<extra></extra>',
    )])
    fig_symbol.update_layout(**get_plotly_layout(height=350))
    st.plotly_chart(fig_symbol, use_container_width=True)

with col_adv2:
    pnl_by_strat = df_filtered.groupby('strategy_tag')['pnl_usdt'].sum().reset_index()
    pnl_by_strat = pnl_by_strat.sort_values(by='pnl_usdt', ascending=True)
    
    bar_colors_strat = ['#10b981' if v >= 0 else '#ef4444' for v in pnl_by_strat['pnl_usdt']]
    
    fig_strat = go.Figure(data=[go.Bar(
        x=pnl_by_strat['pnl_usdt'], y=pnl_by_strat['strategy_tag'],
        orientation='h',
        marker=dict(color=bar_colors_strat, line=dict(width=0)),
        hovertemplate='<b>%{y}</b><br>PnL: $%{x:.2f}<extra></extra>',
    )])
    fig_strat.update_layout(**get_plotly_layout(height=350))
    st.plotly_chart(fig_strat, use_container_width=True)


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
# TRADE TECHNICAL DETAILS (NEW)
# =============================================================================
# Check if new columns exist in the data
has_tech_data = 'technical_data' in df_filtered.columns
has_config_snap = 'config_snapshot' in df_filtered.columns

if has_tech_data or has_config_snap:
    st.markdown("""
    <div class="section-header">
        <div class="section-icon">🔧</div>
        <div>
            <h3>Detail Teknikal & Konfigurasi</h3>
            <p class="section-desc">Snapshot indikator dan setting yang digunakan saat entry trade</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Build trade selector for detail view (completed trades only)
    completed_df = df_filtered[df_filtered['result'].isin(['WIN', 'LOSS', 'BREAKEVEN'])].sort_values('timestamp', ascending=False)

    if not completed_df.empty:
        detail_choices = {}
        for idx, row in completed_df.iterrows():
            sym = row.get('symbol', '?')
            pnl_val = row.get('pnl_usdt', 0)
            res = row.get('result', '?')
            ts = row['timestamp'].strftime('%d/%m %H:%M') if pd.notna(row['timestamp']) else '?'
            label = f"{ts} — {sym} ({res}) ${pnl_val:.2f}"
            detail_choices[label] = row

        selected_detail = st.selectbox("🔍 Pilih Trade untuk Detail:", list(detail_choices.keys()), key="tech_detail_select")

        if selected_detail:
            detail_row = detail_choices[selected_detail]

            # Parse JSON columns safely
            def safe_parse_json(val):
                if pd.isna(val) or val == '' or val is None:
                    return {}
                if isinstance(val, dict):
                    return val
                try:
                    return json.loads(str(val))
                except (json.JSONDecodeError, TypeError):
                    return {}

            tech_info = safe_parse_json(detail_row.get('technical_data', '{}')) if has_tech_data else {}
            config_info = safe_parse_json(detail_row.get('config_snapshot', '{}')) if has_config_snap else {}

            col_tech, col_cfg = st.columns(2)

            with col_tech:
                st.markdown("""
                <div class="card-container">
                    <div class="card-title">📊 Technical Snapshot</div>
                </div>
                """, unsafe_allow_html=True)

                if tech_info:
                    # Display key indicators
                    t_col1, t_col2, t_col3 = st.columns(3)
                    with t_col1:
                        rsi_val = tech_info.get('rsi', 0)
                        rsi_color = "🟢" if 40 <= rsi_val <= 60 else ("🔴" if rsi_val > 70 else "🟡")
                        st.metric("RSI", f"{rsi_val:.1f}", delta=None)
                        st.metric("ATR", f"{tech_info.get('atr', 0):.4f}")
                    with t_col2:
                        st.metric("ADX", f"{tech_info.get('adx', 0):.1f}")
                        st.metric("Price", f"${tech_info.get('price', 0):.2f}")
                    with t_col3:
                        st.metric("StochRSI K", f"{tech_info.get('stoch_rsi_k', 0):.1f}")
                        st.metric("StochRSI D", f"{tech_info.get('stoch_rsi_d', 0):.1f}")

                    # Additional info
                    st.markdown(f"""
                    <div style="display: flex; gap: 0.8rem; flex-wrap: wrap; margin-top: 0.5rem;">
                        <span style="background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            EMA: <b style="color:#f1f5f9">{tech_info.get('price_vs_ema', '-')}</b>
                        </span>
                        <span style="background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            BTC: <b style="color:#f1f5f9">{tech_info.get('btc_trend', '-')}</b>
                        </span>
                        <span style="background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            Corr: <b style="color:#f1f5f9">{tech_info.get('btc_correlation', 0):.2f}</b>
                        </span>
                        <span style="background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            OB Imb: <b style="color:#f1f5f9">{tech_info.get('order_book_imbalance', 0):.1f}%</b>
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Data teknikal belum tersedia untuk trade ini.")

            with col_cfg:
                st.markdown("""
                <div class="card-container">
                    <div class="card-title">⚙️ Config Snapshot</div>
                </div>
                """, unsafe_allow_html=True)

                if config_info:
                    c_col1, c_col2 = st.columns(2)
                    with c_col1:
                        st.metric("ATR Multiplier TP", f"{config_info.get('atr_multiplier_tp', '-')}")
                        st.metric("SL Multiplier", f"{config_info.get('trap_safety_sl', '-')}")
                        st.metric("Risk %", f"{config_info.get('risk_percent', '-')}%")
                    with c_col2:
                        st.metric("Leverage", f"x{config_info.get('leverage', '-')}")
                        st.metric("AI Confidence", f"{config_info.get('ai_confidence', '-')}%")
                        st.metric("Timeframe", f"{config_info.get('timeframe_exec', '-')}")

                    st.markdown(f"""
                    <div style="display: flex; gap: 0.8rem; flex-wrap: wrap; margin-top: 0.5rem;">
                        <span style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            Strategy: <b style="color:#f1f5f9">{config_info.get('strategy_mode', '-')}</b>
                        </span>
                        <span style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            Exec: <b style="color:#f1f5f9">{config_info.get('exec_mode', '-')}</b>
                        </span>
                        <span style="background: rgba(139,92,246,0.1); border: 1px solid rgba(139,92,246,0.2); border-radius: 6px; padding: 4px 10px; font-size: 0.78rem; color: #94a3b8;">
                            Model: <b style="color:#f1f5f9">{config_info.get('ai_model', '-')}</b>
                        </span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Config snapshot belum tersedia untuk trade ini.")
    else:
        st.info("Belum ada trade yang selesai (WIN/LOSS) untuk dilihat detailnya.")


# =============================================================================
# PNL CARD GENERATOR
# =============================================================================
st.markdown("""
<div class="section-header">
    <div class="section-icon">📸</div>
    <div>
        <h3>Share PnL Card</h3>
        <p class="section-desc">Generate kartu PnL untuk dibagikan ke sosial media</p>
    </div>
</div>
""", unsafe_allow_html=True)

if not df_filtered.empty:
    trade_choices = {}
    for index, row in df_display.iterrows():
        symbol = row.get('symbol', 'UNKNOWN')
        pnl = row.get('pnl_usdt', 0)
        result = "WIN" if pnl >= 0 else "LOSS"
        date_str = row['timestamp'].strftime('%d/%m %H:%M')
        label = f"{date_str} — {symbol} ({result}) ${pnl:.2f}"
        trade_choices[label] = row
        
    selected_label = st.selectbox("Pilih Trade:", list(trade_choices.keys()))
    
    if selected_label:
        trade = trade_choices[selected_label]
        
        trade_data = {
            'symbol': trade.get('symbol', 'UNKNOWN'),
            'side': trade.get('side', 'LONG'),
            'entry_price': float(trade.get('entry_price', 0)),
            'exit_price': float(trade.get('exit_price', 0)),
            'pnl_usdt': float(trade.get('pnl_usdt', 0)),
            'roi_percent': float(trade.get('roi_percent', 0)),
            'timestamp': trade['timestamp'],
            'leverage': get_coin_leverage(trade.get('symbol', 'UNKNOWN')),
            'strategy': trade.get('strategy_tag', '-')
        }

        try:
            pnl_gen = CryptoPnLGenerator()
            img_buffer = pnl_gen.generate_card(trade_data)
            
            col_preview, col_info = st.columns([1, 1])
            with col_preview:
                st.image(img_buffer, caption="Preview Kartu PnL", use_container_width=True)
                
            with col_info:
                st.markdown("""
                <div class="card-container">
                    <div class="card-title">📸 Siap Dibagikan</div>
                    <p style="color: var(--text-secondary); font-size: 0.85rem; margin: 0;">
                        Klik tombol di bawah untuk mengunduh gambar kartu PnL.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
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
            st.error(f"Gagal membuat kartu: {str(e)}")


# =============================================================================
# FOOTER
# =============================================================================
st.markdown("""
<div class="dashboard-footer">
    <div class="footer-brand">Bot Trading Easy Peasy — Performance Dashboard</div>
    <div class="footer-version">v3.0</div>
</div>
""", unsafe_allow_html=True)
