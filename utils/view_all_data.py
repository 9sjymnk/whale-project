import psycopg2
from tabulate import tabulate

DB_CONFIG = {
    "host": "localhost",
    "database": "whale_db",
    "user": "whale_user",
    "password": "whale_password",
    "port": 5432
}

def view_data():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 1️⃣ 전체 거래 개수 조회
        cur.execute("SELECT COUNT(*) FROM trades;")
        total_count = cur.fetchone()[0]

        # 2️⃣ 고래 거래(1억 이상) 개수 조회 💡 [추가됨]
        cur.execute("SELECT COUNT(*) FROM trades WHERE total_amount >= 100000000;")
        whale_count = cur.fetchone()[0]

        # 3️⃣ 최신 거래 20건 조회
        cur.execute("""
            SELECT 
                timestamp, 
                code, 
                CASE WHEN side = 'ASK' THEN '🔴 매도' ELSE '🔵 매수' END as side_display,
                price, 
                volume, 
                total_amount 
            FROM trades 
            ORDER BY id DESC 
            LIMIT 20;
        """)
        rows = cur.fetchall()

        # 4️⃣ 대시보드 출력
        print("\n" + "═"*75)
        print(f"📊 [고래 탐지 시스템] 데이터 적재 및 분석 리포트")
        print("═"*75)
        print(f"✅ 총 누적 거래량: {total_count:,} 건")
        print(f"🐳 총 고래 거래량: {whale_count:,} 건 (전체 대비 {(whale_count/total_count*100):.2f}% )")
        print("-" * 75)
        print("🕒 최신 거래 내역 Preview (최신순 20건):")
        
        headers = ["거래 시간", "코인", "구분", "가격(원)", "수량", "거래대금(원)"]
        formatted_rows = [
            (r[0], r[1], r[2], f"{r[3]:,.0f}", f"{r[4]:.4f}", f"{r[5]:,.0f}") 
            for r in rows
        ]
        
        print(tabulate(formatted_rows, headers=headers, tablefmt="psql"))
        print("═"*75 + "\n")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ DB 조회 실패: {e}")

if __name__ == "__main__":
    view_data()