import psycopg2

DB_CONFIG = {
    "host": "localhost", "database": "whale_db",
    "user": "whale_user", "password": "whale_password", "port": 5432
}

def check():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # 1. 전체 데이터 개수 확인
    cur.execute("SELECT COUNT(*) FROM trades;")
    total_count = cur.fetchone()[0]
    
    # 2. 최근 5개 데이터 확인
    cur.execute("SELECT timestamp, code, price, total_amount FROM trades ORDER BY id DESC LIMIT 5;")
    rows = cur.fetchall()
    
    print(f"📊 현재 DB에 저장된 총 데이터 수: {total_count}개")
    print("\n🕒 최근 저장된 5개 데이터:")
    for r in rows:
        print(f"[{r[0]}] {r[1]} | {r[2]:,.0f}원 | 거래액: {r[3]:,.0f}원")

    cur.close()
    conn.close()

if __name__ == "__main__":
    check()