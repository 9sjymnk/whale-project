"""
고래 거래 신호의 시간 경과에 따른 예측력 분석
고래 거래 발생 후 Δ분이 지났을 때, 그 신호가 얼마나 유효한지 측정
"""
import os, sys, psycopg2
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from dotenv import load_dotenv
from datetime import timedelta
from collections import defaultdict

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

DB_CONFIG = {
    "host":     os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user":     os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port":     int(os.getenv("DB_PORT", 5432)),
}

COIN           = "KRW-BTC"
WHALE_THRESH   = 100_000_000
DELAYS_MIN     = [0, 5, 10, 15, 20, 25, 30, 40, 50, 60]
HORIZONS_MIN   = [1, 5, 30]
LOOKBACK_DAYS  = 30

def get_price_near(cur, coin, ts, tolerance_sec=30):
    """ts 시점에서 가장 가까운 체결 가격 반환 (±tolerance_sec 이내)"""
    cur.execute("""
        SELECT price
        FROM trades
        WHERE code = %s
          AND timestamp BETWEEN %s AND %s
        ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp - %s)))
        LIMIT 1
    """, (coin, ts - timedelta(seconds=tolerance_sec),
                ts + timedelta(seconds=tolerance_sec), ts))
    row = cur.fetchone()
    return float(row[0]) if row else None

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()

    # 고래 거래 전체 조회
    cur.execute("""
        SELECT timestamp, price, side, total_amount
        FROM trades
        WHERE code = %s
          AND total_amount >= %s
          AND timestamp >= NOW() - INTERVAL '%s days'
        ORDER BY timestamp ASC
    """, (COIN, WHALE_THRESH, LOOKBACK_DAYS))
    whales = cur.fetchall()
    print(f"분석 대상 고래 거래: {len(whales)}건 (최근 {LOOKBACK_DAYS}일, {COIN})")

    # delay × horizon 별로 (맞춘 수, 전체 수) 집계
    results = defaultdict(lambda: [0, 0])  # key=(delay, horizon)

    for idx, (ts, w_price, w_side, w_amt) in enumerate(whales):
        if idx % 50 == 0:
            print(f"  처리 중... {idx}/{len(whales)}")

        # 고래 거래 직후 기준 가격 (t+0 근방 실제 체결가)
        base_price = get_price_near(cur, COIN, ts, tolerance_sec=60)
        if base_price is None:
            continue

        # 신호 방향: BID → UP(1), ASK → DOWN(-1)
        signal = 1 if w_side == "BID" else -1

        for delay in DELAYS_MIN:
            query_ts = ts + timedelta(minutes=delay)
            query_price = get_price_near(cur, COIN, query_ts, tolerance_sec=60)
            if query_price is None:
                continue

            for horizon in HORIZONS_MIN:
                future_ts    = query_ts + timedelta(minutes=horizon)
                future_price = get_price_near(cur, COIN, future_ts, tolerance_sec=60)
                if future_price is None:
                    continue

                actual_dir = 1 if future_price > query_price else -1
                correct    = 1 if actual_dir == signal else 0

                key = (delay, horizon)
                results[key][0] += correct
                results[key][1] += 1

    cur.close(); conn.close()

    # 결과 출력
    print("\n" + "="*65)
    print(f"{'고래 신호 유효성 분석':^65}")
    print("="*65)
    print(f"{'경과시간':>8}", end="")
    for h in HORIZONS_MIN:
        print(f"  {h}m예측정확도", end="")
    print(f"  {'샘플수':>6}")
    print("-"*65)

    for delay in DELAYS_MIN:
        print(f"  {delay:>3}분후", end="")
        sample_counts = []
        for h in HORIZONS_MIN:
            key = (delay, h)
            correct, total = results[key]
            acc = correct / total * 100 if total > 0 else 0
            sample_counts.append(total)
            bar = "█" * int(acc / 5)
            print(f"  {acc:5.1f}% {bar:<16}", end="")
        print(f"  {min(sample_counts):>6}")

    print("="*65)
    print("\n* 정확도 50% = 완전 랜덤 (신호 없음)")
    print("* 감쇠 기준 제안: 정확도가 55% 아래로 떨어지는 시점 = 컷오프")

    # 감쇠 계수 제안
    print("\n[신뢰도 감쇠 계수 제안 (1m 기준)]")
    baseline = None
    for delay in DELAYS_MIN:
        key = (delay, 1)
        correct, total = results[key]
        if total == 0:
            continue
        acc = correct / total * 100
        if baseline is None:
            baseline = acc
        decay = (acc - 50) / (baseline - 50) if baseline > 50 else 0
        decay = max(0.0, decay)
        print(f"  {delay:>3}분 경과: 정확도 {acc:5.1f}%  →  감쇠 계수 {decay:.2f}")

if __name__ == "__main__":
    main()
