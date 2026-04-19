# analyzer/feature_engineering.py
import os
import psycopg2
import pandas as pd
import numpy as np
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

DB_CONFIG = {
    "host":     os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port":     int(os.getenv("DB_PORT", 5432)),
}

WHALE_THRESHOLD = 100_000_000   # 1억원 이상
PRE_WINDOW_MIN  = 10            # 고래 거래 직전 분석 윈도우
LABEL_MINUTES   = [1, 5, 30]   # 예측 타임프레임
FEATURE_COLS = [
    "buy_ratio", "buy_count_ratio", "price_change_pct",
    "trade_count", "total_volume", "whale_amount",
    "whale_side_bid", "hour", "price_volatility",
]


def _extract_features(pre_trades: list, whale: dict) -> dict | None:
    """고래 거래 직전 10분 거래 데이터로 특성 생성"""
    if len(pre_trades) < 3:
        return None

    prices      = [t["price"]        for t in pre_trades]
    buy_amount  = sum(t["amount"]    for t in pre_trades if t["side"] == "BID")
    sell_amount = sum(t["amount"]    for t in pre_trades if t["side"] == "ASK")
    buy_count   = sum(1              for t in pre_trades if t["side"] == "BID")
    total_amt   = buy_amount + sell_amount
    total_cnt   = len(pre_trades)

    price_mean  = np.mean(prices)
    price_std   = np.std(prices)

    return {
        "buy_ratio":        buy_amount / total_amt if total_amt > 0 else 0.5,
        "buy_count_ratio":  buy_count  / total_cnt if total_cnt > 0 else 0.5,
        "price_change_pct": (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] else 0.0,
        "trade_count":      total_cnt,
        "total_volume":     sum(t["volume"] for t in pre_trades),
        "whale_amount":     whale["amount"],
        "whale_side_bid":   1 if whale["side"] == "BID" else 0,
        "hour":             whale["ts"].hour,
        "price_volatility": price_std / price_mean * 100 if price_mean else 0.0,
    }


def build_feature_dataset(coin: str) -> pd.DataFrame:
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    # 고래 거래 전체 조회
    cur.execute("""
        SELECT id, timestamp, price, side, total_amount
        FROM trades
        WHERE code = %s AND total_amount >= %s
        ORDER BY timestamp ASC
    """, (coin, WHALE_THRESHOLD))
    whale_rows = cur.fetchall()
    print(f"[{coin}] 고래 거래: {len(whale_rows)}건")

    records = []
    for row in whale_rows:
        wid, ts, w_price, w_side, w_amt = row
        w_price = float(w_price)
        w_amt   = float(w_amt)
        whale   = {"id": wid, "ts": ts, "price": w_price, "side": w_side, "amount": w_amt}

        # 직전 10분 거래 데이터
        window_start = ts - timedelta(minutes=PRE_WINDOW_MIN)
        cur.execute("""
            SELECT price, side, total_amount, volume
            FROM trades
            WHERE code = %s AND timestamp >= %s AND timestamp < %s
            ORDER BY timestamp ASC
        """, (coin, window_start, ts))
        pre_trades = [
            {"price": float(r[0]), "side": r[1], "amount": float(r[2]), "volume": float(r[3])}
            for r in cur.fetchall()
        ]

        features = _extract_features(pre_trades, whale)
        if features is None:
            continue

        # 타임프레임별 라벨 계산
        labels = {}
        for m in LABEL_MINUTES:
            future_ts = ts + timedelta(minutes=m)
            cur.execute("""
                SELECT price FROM trades
                WHERE code = %s AND timestamp >= %s
                ORDER BY timestamp ASC LIMIT 1
            """, (coin, future_ts))
            r = cur.fetchone()
            labels[f"label_{m}m"] = (1 if float(r[0]) > w_price else 0) if r else None

        if any(v is None for v in labels.values()):
            continue

        records.append({**features, **labels, "coin": coin, "timestamp": ts})

    cur.close()
    conn.close()

    df = pd.DataFrame(records)
    print(f"[{coin}] 생성된 피처 행: {len(df)}")
    return df


if __name__ == "__main__":
    frames = []
    for coin in ["KRW-BTC", "KRW-ETH"]:
        df = build_feature_dataset(coin)
        frames.append(df)

    all_df = pd.concat(frames, ignore_index=True)

    out_dir  = os.path.join(os.path.dirname(__file__), '..', 'data')
    out_path = os.path.join(out_dir, 'features.csv')
    os.makedirs(out_dir, exist_ok=True)
    all_df.to_csv(out_path, index=False)

    print(f"\n✅ 특성 저장 완료: data/features.csv ({len(all_df)}행)")
    print(all_df[FEATURE_COLS + ["label_1m", "label_5m", "label_30m"]].describe().round(3).to_string())
