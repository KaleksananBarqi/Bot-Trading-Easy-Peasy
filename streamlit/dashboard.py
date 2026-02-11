
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

# Robustly add project root to sys.path so 'config' can be imported by src modules
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from src.modules.journal import TradeJournal
from src.utils.helper import get_coin_leverage


# Page Config
st.set_page_config(
    page_title="Bot Trading Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        text-align: center;
    }
    .win { color: #00FF00 !important; }
    .loss { color: #FF0000 !important; }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🤖 Bot Trading Easy Peasy Performance Dashboard")
st.markdown("---")

# Load Data
@st.cache_data(ttl=60) # Cache 1 minute
def get_data():
    journal = TradeJournal()
    df = journal.load_trades()
    return df

df = get_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("🔍 Filters")

if not df.empty:
    # 1. Date Range Filter
    min_date = df['timestamp'].min().date()
    max_date = df['timestamp'].max().date()
    
    # Default to full range
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    # 2. Symbol Filter
    all_symbols = ['All'] + list(df['symbol'].unique())
    selected_symbol = st.sidebar.selectbox("Symbol", all_symbols)
    
    # 3. Strategy Filter
    all_strategies = ['All'] + list(df['strategy_tag'].unique())
    selected_strategy = st.sidebar.selectbox("Strategy", all_strategies)

    # Apply Filters
    df_filtered = df.copy()
    
    # Filter by Date
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

# --- DASHBOARD CONTENT ---

if df.empty:
    st.info("👋 Belum ada data trading. Jalankan bot untuk mulai merekam trade.")
    st.stop()

if df_filtered.empty:
    st.warning("⚠️ Tidak ada data yang cocok dengan filter.")
    st.stop()

# 1. KPI CARDS
col1, col2, col3, col4 = st.columns(4)

# Calculations
total_trades = len(df_filtered)
win_trades = df_filtered[df_filtered['result'] == 'WIN']
loss_trades = df_filtered[df_filtered['result'] == 'LOSS']
canceled_trades_count = len(df_filtered[df_filtered['result'] == 'CANCELLED'])
expired_trades_count = len(df_filtered[df_filtered['result'] == 'EXPIRED'])

# Win Rate calculated only from WIN and LOSS
completed_trades_count = len(win_trades) + len(loss_trades)
win_rate = (len(win_trades) / completed_trades_count * 100) if completed_trades_count > 0 else 0

total_pnl = df_filtered['pnl_usdt'].sum()
gross_profit = win_trades['pnl_usdt'].sum()
gross_loss = abs(loss_trades['pnl_usdt'].sum())
profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

avg_win = win_trades['pnl_usdt'].mean() if not win_trades.empty else 0
avg_loss = loss_trades['pnl_usdt'].mean() if not loss_trades.empty else 0

# Display Metrics
with col1:
    st.metric("Total Trades", f"{total_trades}")
with col2:
    st.metric("Win Rate", f"{win_rate:.1f}%", f"{len(win_trades)}W - {len(loss_trades)}L")
with col3:
    st.metric("Net PnL (USDT)", f"${total_pnl:.2f}", delta=f"PF: {profit_factor:.2f}")
with col4:
    st.metric("Avg Win / Loss", f"${avg_win:.2f}", f"${avg_loss:.2f}")

# Additional Stats row for Canceled and Expired
st.markdown(f"""
<div style="display: flex; justify-content: space-around; padding: 10px; background-color: #1E1E1E; border-radius: 10px; margin-top: 10px; border: 1px solid #333;">
    <div style="text-align: center;">
        <span style="color: #888; font-size: 0.8rem;">Canceled Trades</span><br>
        <span style="font-size: 1.2rem; font-weight: bold;">{canceled_trades_count}</span>
    </div>
    <div style="text-align: center; border-left: 1px solid #444; padding-left: 20px;">
        <span style="color: #888; font-size: 0.8rem;">Expired Trades</span><br>
        <span style="font-size: 1.2rem; font-weight: bold;">{expired_trades_count}</span>
    </div>
    <div style="text-align: center; border-left: 1px solid #444; padding-left: 20px;">
        <span style="color: #888; font-size: 0.8rem;">Completed Trades (W+L)</span><br>
        <span style="font-size: 1.2rem; font-weight: bold;">{completed_trades_count}</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# 2. CHARTS ROW 1
col_chart1, col_chart2 = st.columns([2, 1])

with col_chart1:
    st.subheader("📈 Equity Curve (Cumulative PnL)")
    # Cumulative Sum
    df_sorted = df_filtered.sort_values(by='timestamp')
    df_sorted['cumulative_pnl'] = df_sorted['pnl_usdt'].cumsum()
    
    fig_equity = px.line(df_sorted, x='timestamp', y='cumulative_pnl', 
                         markers=True, title="Growth of Account (USDT)")
    # Add Zero Line
    fig_equity.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_equity, use_container_width=True)

with col_chart2:
    st.subheader("📊 Win vs Loss Distribution")
    fig_pie = px.pie(df_filtered, names='result', title="Win/Loss Ratio",
                     color='result',
                     color_discrete_map={'WIN': '#00CC96', 'LOSS': '#EF553B', 'BREAKEVEN': '#FFA15A'})
    st.plotly_chart(fig_pie, use_container_width=True)

# 3. CHARTS ROW 2 (Advanced Analysis)
col_adv1, col_adv2 = st.columns(2)

with col_adv1:
    st.subheader("💰 PnL by Symbol")
    pnl_by_symbol = df_filtered.groupby('symbol')['pnl_usdt'].sum().reset_index()
    pnl_by_symbol = pnl_by_symbol.sort_values(by='pnl_usdt', ascending=False)
    
    fig_symbol = px.bar(pnl_by_symbol, x='pnl_usdt', y='symbol', orientation='h',
                        color='pnl_usdt', 
                        color_continuous_scale=['#EF553B', '#00CC96'],
                        title="Performa per Koin (USDT)")
    st.plotly_chart(fig_symbol, use_container_width=True)

with col_adv2:
    st.subheader("🧠 PnL by Strategy")
    pnl_by_strat = df_filtered.groupby('strategy_tag')['pnl_usdt'].sum().reset_index()
    pnl_by_strat = pnl_by_strat.sort_values(by='pnl_usdt', ascending=False)
    
    fig_strat = px.bar(pnl_by_strat, x='strategy_tag', y='pnl_usdt',
                       color='pnl_usdt',
                       color_continuous_scale=['#EF553B', '#00CC96'],
                       title="Performa Strategi (USDT)")
    st.plotly_chart(fig_strat, use_container_width=True)

# 4. HOURLY HEATMAP
st.subheader("🔥 Trading Activity Heatmap")
df_heat = df_filtered.copy()
df_heat['hour'] = df_heat['timestamp'].dt.hour
df_heat['day'] = df_heat['timestamp'].dt.day_name()

# Urutkan hari Senin-Minggu
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
df_heat['day'] = pd.Categorical(df_heat['day'], categories=days_order, ordered=True)

heatmap_data = df_heat.groupby(['day', 'hour']).size().reset_index(name='count')
fig_heat = px.density_heatmap(heatmap_data, x='hour', y='day', z='count', 
                              nbinsx=24, nbinsy=7, 
                              color_continuous_scale='Viridis',
                              title="Waktu Trading Paling Aktif")
st.plotly_chart(fig_heat, use_container_width=True)

# 5. DETAILED TABLE WITH AI INSIGHTS
st.subheader("📝 Trade History & AI Audits")

# Formatting for Table
display_cols = ['timestamp', 'symbol', 'side', 'type', 'entry_price', 'exit_price', 'pnl_usdt', 'roi_percent', 'strategy_tag', 'prompt', 'reason', 'setup_at', 'filled_at']
# Ensure columns exist (for old CSV compatibility)
for col in ['setup_at', 'filled_at']:
    if col not in df_filtered.columns:
        df_filtered[col] = None

df_display = df_filtered[display_cols].copy()

# Calculate Durations
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

# Sort by newest
df_display = df_display.sort_values(by='timestamp', ascending=False)

# Remove raw timestamp cols for display
df_display = df_display.drop(columns=['setup_at', 'filled_at'])

# Interactive Table
st.dataframe(
    df_display,
    column_config={
        "timestamp": st.column_config.DatetimeColumn("Time", format="DD/MM/YYYY HH:mm"),
        "pnl_usdt": st.column_config.NumberColumn("PnL ($)", format="$%.2f"),
        "roi_percent": st.column_config.NumberColumn("ROI (%)", format="%.2f%%"),
        "strategy_tag": st.column_config.Column("Strategy"),
        "prompt": st.column_config.TextColumn("AI Prompt", width="small"),
        "reason": st.column_config.TextColumn("AI Reason", width="medium"),
    },
    use_container_width=True,
    hide_index=True
)

# Footer
st.markdown("---")
st.caption("Bot Trading Dashboard v2.0 | Enhanced by Auto-Agent")

# 6. PNL CARD GENERATOR
st.markdown("---")
st.subheader("📸 Share PnL Card")

if not df_filtered.empty:
    # Prepare list of trades for dropdown
    # Format: "BTC/USDT | WIN +$123.45 | 2024-05-20"
    trade_options = []
    
    # We use df_display which is already sorted by newest
    # Access original index to retrieve full row data if needed, or just use iloc
    # df_display has reset index? No, let's check. 
    # st.dataframe(df_display) shows it.
    
    # Let's create a list of indices and labels
    # We iterate over the dataframe to create options
    
    # Need to handle potential missing columns or data safely
    trade_choices = {}
    for index, row in df_display.iterrows():
        symbol = row.get('symbol', 'UNKNOWN')
        pnl = row.get('pnl_usdt', 0)
        result = "WIN" if pnl >= 0 else "LOSS"
        date_str = row['timestamp'].strftime('%d/%m %H:%M')
        
        label = f"{date_str} - {symbol} ({result}) ${pnl:.2f}"
        trade_choices[label] = row
        
    selected_label = st.selectbox("Pilih Trade untuk dibuatkan Kartu:", list(trade_choices.keys()))
    
    if selected_label:
        trade = trade_choices[selected_label]
        
        # Data Preparation
        symbol = trade.get('symbol', 'BTC/USDT')
        side = trade.get('side', 'LONG').capitalize()
        entry_price = float(trade.get('entry_price', 0))
        exit_price = float(trade.get('exit_price', 0))
        roi = float(trade.get('roi_percent', 0))
        leverage = get_coin_leverage(symbol)
        
        # Color coding
        if roi >= 0:
            roi_color = "#00ff88" # Green
            roi_bg = "rgba(0, 255, 136, 0.1)"
            side_color = "#00ff88"
        else:
            roi_color = "#ff4b4b" # Red
            roi_bg = "rgba(255, 75, 75, 0.1)"
            side_color = "#ff4b4b"
            
        # Dynamic leverage text
        leverage_text = f"{leverage}X"
        
        # HTML/CSS Template
        card_html = f"""
        <div style="
            width: 400px;
            background: linear-gradient(145deg, #1a1a1a, #0d0d0d);
            border-radius: 20px;
            padding: 30px;
            font-family: 'Arial', sans-serif;
            color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border: 1px solid #333;
            margin: 0 auto;
            position: relative;
            overflow: hidden;
        ">
            <!-- Background Decoration -->
            <div style="position: absolute; top: -50px; right: -50px; width: 150px; height: 150px; background: {roi_color}; opacity: 0.1; border-radius: 50%; blur: 50px;"></div>
            
            <!-- Header -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.5rem; font-weight: bold; letter-spacing: 1px;">{symbol}</span>
                    <span style="background: #333; color: #ccc; padding: 2px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: bold;">Perpetual</span>
                </div>
                <div style="background: #2a2a2a; border: 1px solid #444; border-radius: 8px; padding: 5px 12px;">
                    <span style="color: white; font-weight: bold;">Bot EzPeasy</span>
                </div>
            </div>
            
            <!-- Side & Leverage -->
            <div style="display: flex; gap: 10px; margin-bottom: 30px;">
                <span style="color: {side_color}; font-weight: bold; font-size: 1.1rem;">{side}</span>
                <span style="color: #888; font-weight: bold; font-size: 1.1rem;">|</span>
                <span style="color: white; font-weight: bold; font-size: 1.1rem;">{leverage_text}</span>
            </div>
            
            <!-- ROI Section -->
            <div style="text-align: left; margin-bottom: 30px;">
                <div style="color: #888; font-size: 1rem; margin-bottom: 5px;">Return on Investment (ROI)</div>
                <div style="font-size: 3.5rem; font-weight: 800; color: {roi_color}; text-shadow: 0 0 20px {roi_bg};">
                    {roi:+.2f}%
                </div>
            </div>
            
            <!-- Prices -->
            <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                <div>
                    <div style="color: #666; font-size: 0.9rem; margin-bottom: 3px;">Entry Price</div>
                    <div style="font-size: 1.2rem; font-weight: bold;">{entry_price:,.4f}</div>
                </div>
                <div style="text-align: right;">
                    <div style="color: #666; font-size: 0.9rem; margin-bottom: 3px;">Exit Price</div>
                    <div style="font-size: 1.2rem; font-weight: bold;">{exit_price:,.4f}</div>
                </div>
            </div>
            
            <!-- Divider -->
            <div style="height: 1px; background: #333; margin: 20px 0;"></div>
            
            <!-- Footer/QR Placeholder -->
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div style="color: #888; font-size: 0.8rem; font-style: italic;">Automated by</div>
                    <div style="font-weight: bold; color: #fff;">Bot Trading Easy Peasy</div>
                    <div style="color: #444; font-size: 0.7rem; margin-top: 5px;">{trade['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}</div>
                </div>
                
                <!-- QR Code Placeholder (Mock visual) -->
                <div style="width: 50px; height: 50px; background: white; padding: 3px; border-radius: 5px;">
                   <img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=BotTradingEasyPeasy" width="100%" height="100%" />
                </div>
            </div>
        </div>
        """
        
        # Display
        col_preview, col_info = st.columns([1, 1])
        with col_preview:
            st.markdown(card_html, unsafe_allow_html=True)
            st.caption("📸 Silakan screenshot kartu di atas untuk dibagikan.")

