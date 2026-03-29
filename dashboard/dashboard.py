import streamlit as st
import pandas as pd
import psycopg2
import requests
import plotly.graph_objects as go
from datetime import datetime

# --- 1. DB 설정 (본인 비번 필수 수정!) ---
DB_CONFIG = {
    "host": "3.35.207.98", 
    "database": "whale_db",
    "user": "postgres",
    "password": "7124", 
    "port": 5432
}

st.set_page_config(page_title="Whale Watcher Intelligence", layout="wide")

# [핵심] 깜빡임 방지 및 로딩 아이콘 숨기기 CSS
st.markdown("""
    <style>
    .main { background-color: #0b0e11; color: #eaecef; }
    /* 스트림릿 특유의 새로고침 깜빡임(로딩 애니메이션) 숨기기 */
    [data-testid="stStatusWidget"] { visibility: hidden; }
    .stMetric { background-color: #1e2329; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 26px !important; font-weight: bold !important; }
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-size: 16px !important; font-weight: 600 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. 데이터 엔진 ---
@st.cache_data(ttl=3600)
def get_rate():
    try: return requests.get("https://open.er-api.com/v6/latest/KRW").json()['rates']['USD']
    except: return 0.00075

def fetch_data(coin, threshold):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        w_q = f"SELECT * FROM trades WHERE code='{coin}' AND timestamp >= NOW() - INTERVAL '24 hours' AND (price*volume) >= {threshold} ORDER BY timestamp DESC"
        p_q = f"SELECT date_trunc('minute', timestamp) as ts, AVG(price) as avg_price FROM trades WHERE code='{coin}' AND timestamp >= NOW() - INTERVAL '24 hours' GROUP BY ts ORDER BY ts ASC"
        open_q = f"SELECT price FROM trades WHERE code='{coin}' AND timestamp >= date_trunc('day', now()) ORDER BY timestamp ASC LIMIT 1"
        df_w = pd.read_sql(w_q, conn); df_p = pd.read_sql(p_q, conn); df_open = pd.read_sql(open_q, conn)
        conn.close()
        open_p = df_open['price'].iloc[0] if not df_open.empty else (df_p['avg_price'].iloc[0] if not df_p.empty else 1.0)
        return df_w, df_p, open_p
    except: return pd.DataFrame(), pd.DataFrame(), 1.0

# --- 3. 고정 레이아웃 (이 뼈대는 절대로 변하지 않습니다) ---
st.title("🛡️ Whale Watcher Intelligence")

st.sidebar.title("🐳 Control Panel")
sel_coin = st.sidebar.selectbox("코인 선택", ["KRW-BTC", "KRW-ETH"])
th_slider = st.sidebar.slider("고래 기준(억원)", 0.1, 10.0, 1.0, 0.1)
th_krw = int(th_slider * 100000000)
cur_choice = st.sidebar.radio("통화", ["₩ KRW", "$ USD"], horizontal=True)

# 지표 칸막이 박제
m_col1, m_col2, m_col3 = st.columns(3)
p_place, w_place, s_place = m_col1.empty(), m_col2.empty(), m_col3.empty()

# 차트와 로그 칸막이 박제
chart_place = st.empty()
log_title_place = st.empty()
log_data_place = st.empty()

# --- 4. 실시간 업데이트 프로세스 ---
@st.fragment(run_every=2)
def refresh_dashboard(coin, threshold, currency):
    df_w, df_p, open_price = fetch_data(coin, threshold)
    if df_p.empty: return

    rate = get_rate()
    is_usd = "USD" in currency
    p_sym = "$" if is_usd else "₩"
    def conv(v): return v * rate if is_usd else v

    curr_p = df_p['avg_price'].iloc[-1]
    diff, pct = curr_p - open_price, ((curr_p - open_price)/open_price)*100
    buy_vol = df_w[df_w['side'] == 'BID']['total_amount'].sum()
    strength = (buy_vol / df_w['total_amount'].sum() * 100) if not df_w.empty else 50

    # [1. 지표 박제]
    p_place.metric(label=f"실시간 가격 ({coin})", value=f"{p_sym}{conv(curr_p):,.0f}", delta=f"{pct:+.2f}% ({p_sym}{conv(diff):+,.0f})")
    w_val = f"{p_sym}{conv(buy_vol)/1e8:,.1f}억" if not is_usd else f"{p_sym}{conv(buy_vol):,.0f}"
    w_place.metric("24h 고래 매수액", w_val, delta=f"{len(df_w[df_w['side']=='BID'])}건")
    s_place.metric("고래 매수 강도", f"{strength:.1f}%", delta=f"{strength-50:.1f}%")

    # [2. 차트 박제 - 줌 고정의 핵심]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_p['ts'], y=df_p['avg_price'].apply(conv), name="Price", line=dict(color='#848e9c', width=1.5)))
    fig.add_hline(y=conv(curr_p), line_dash="dot", line_color="#f7931a", annotation_text=f" {p_sym}{conv(curr_p):,.0f}")
    
    if not df_w.empty:
        for side, color, name in [('BID', '#00ff41', 'Buy'), ('ASK', '#ff3b3b', 'Sell')]:
            sub = df_w[df_w['side'] == side]
            if not sub.empty:
                fig.add_trace(go.Scatter(x=sub['timestamp'], y=sub['price'].apply(conv), mode='markers',
                    marker=dict(size=sub['total_amount'].apply(conv)/(2e7*rate if is_usd else 2e7), color=color, opacity=0.6), name=name))

    fig.update_layout(
        template="plotly_dark", height=480, margin=dict(l=0, r=80, t=50, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, bgcolor="rgba(0,0,0,0)"),
        dragmode='pan',
        # uirevision을 상수로 고정하고, key를 코인명으로 주어 상태를 완벽하게 보존
        uirevision='stable_zoom_state', 
        yaxis=dict(side="right", tickformat=",d", autorange=True)
    )
    # key가 고정되어야 스트림릿이 차트를 갈아치우지 않습니다.
    chart_place.plotly_chart(fig, use_container_width=True, key=f"fixed_chart_{coin}", config={'scrollZoom': True, 'displayModeBar': False})

    # [3. 로그 박제]
    log_title_place.subheader("🔔 실시간 고래 활동 로그")
    if not df_w.empty:
        log_df = df_w[['timestamp', 'side', 'price', 'volume', 'total_amount']].copy()
        log_df['total_amount_view'] = log_df['total_amount'].apply(lambda x: f"{p_sym}{conv(x):,.0f}" if is_usd else f"{p_sym}{x/1e8:,.2f}억")
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp']).dt.strftime('%H:%M:%S') # 화면 효율을 위해 시간만 표시
        log_df['side'] = log_df['side'].map({'BID':'매수 🟢','ASK':'매도 🔴'})
        log_df['price'] = log_df['price'].apply(lambda x: f"{p_sym}{conv(x):,.0f}")
        log_df['volume'] = log_df['volume'].apply(lambda x: f"{x:.4f}")
        disp = log_df[['timestamp', 'side', 'price', 'volume', 'total_amount_view']]
        disp.columns = ['시간', '구분', '가격', '수량', '총합']
        log_data_place.dataframe(disp.head(10), use_container_width=True, hide_index=True)

# 실행
refresh_dashboard(sel_coin, th_krw, cur_choice)