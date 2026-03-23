import psycopg2

DB_CONFIG = {
    "host": "localhost", "database": "whale_db",
    "user": "whale_user", "password": "whale_password", "port": 5432
}

def get_top_whales():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # 오늘 저장된 데이터 중 거래 금액(total_amount)이 큰 순서대로 5개 조회
    query = """
        SELECT timestamp, code, price, total_amount, side
        FROM trades
        ORDER BY total_amount DESC
        LIMIT 5;
    """
    cur.execute(query)
    rows = cur.fetchall()
    
    print("\n🏆 [오늘의 고래 랭킹 TOP 5]")
    print("-" * 60)
    for i, r in enumerate(rows, 1):
        side_kor = "매수" if r[4] == "BID" else "매도"
        print(f"{i}위 | {r[3]:,.0f}원 | {r[1]} | {r[2]:,.0f}원 ({side_kor})")
    print("-" * 60)

    cur.close()
    conn.close()

if __name__ == "__main__":
    get_top_whales()