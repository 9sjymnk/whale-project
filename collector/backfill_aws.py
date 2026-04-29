import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta, timezone
import time

DB_CONFIG = {
    "host": "127.0.0.1",
    "database": "whale_db",
    "user": "postgres",
    "password": "7124",
    "port": 5432
}

KST = timezone(timedelta(hours=9))
CODES = ["KRW-ETH"]
# 오늘(4/25) 기준으로 daysAgo=1~6 → 4/24~4/19
DAYS_AGO_LIST = list(range(2, 7))


def fetch_trades(market, days_ago=None, cursor=None):
    params = {"market": market, "count": 500}
    if days_ago is not None:
        params["daysAgo"] = days_ago
    if cursor:
        params["cursor"] = cursor
    resp = requests.get("https://api.upbit.com/v1/trades/ticks", params=params)
    resp.raise_for_status()
    return resp.json()


def trade_to_row(t, market):
    ts = datetime.fromtimestamp(t["timestamp"] / 1000, tz=timezone.utc).astimezone(KST)
    price = t["trade_price"]
    volume = t["trade_volume"]
    cp = t["change_price"]
    change = "RISE" if cp > 0 else ("FALL" if cp < 0 else "EVEN")
    return (
        ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        market,
        price,
        volume,
        t["ask_bid"],
        price * volume,
        t["prev_closing_price"],
        change,
        t["sequential_id"],
    )


def backfill_day(market, days_ago, conn):
    cur = conn.cursor()
    target = (datetime.now(KST) - timedelta(days=days_ago)).strftime("%Y-%m-%d")
    print(f"  [{market}] {target} 백필 중...")
    cursor = None
    total = 0

    while True:
        try:
            trades = fetch_trades(market, days_ago=days_ago, cursor=cursor)
            if not trades:
                break

            rows = [trade_to_row(t, market) for t in trades]
            execute_values(cur, """
                INSERT INTO trades (timestamp, code, price, volume, side, total_amount, pcp, change, sid)
                VALUES %s
                ON CONFLICT (sid, code) DO NOTHING
            """, rows)
            conn.commit()
            total += len(rows)

            last_ts = trades[-1]["timestamp"]
            last_dt = datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).astimezone(KST)
            print(f"    {total}건 | 마지막: {last_dt.strftime('%H:%M:%S')}")

            cursor = trades[-1]["sequential_id"]
            time.sleep(0.12)

        except Exception as e:
            print(f"    에러: {e}, 5초 후 재시도...")
            time.sleep(5)

    print(f"  ✅ {target} 완료: {total}건")
    return total


for code in CODES:
    print(f"\n▶ 백필 시작: {code}")
    conn = psycopg2.connect(**DB_CONFIG)
    grand_total = 0
    for days_ago in DAYS_AGO_LIST:
        grand_total += backfill_day(code, days_ago, conn)
    conn.close()
    print(f"✅ {code} 전체 완료: {grand_total}건")

print("\n모든 백필 완료!")
