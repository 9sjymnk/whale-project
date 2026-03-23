import psycopg2
from tabulate import tabulate

DB_CONFIG = {"host": "localhost", "database": "whale_db", "user": "whale_user", "password": "whale_password", "port": 5432}

def view_raw_data():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # 모든 컬럼(*)을 최신순으로 10개만 가져오기
        cur.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 10;")
        rows = cur.fetchall()
        
        # 컬럼 이름 가져오기
        colnames = [desc[0] for desc in cur.description]

        print("\n" + "="*120)
        print("🗄️ [DB Raw Data] 실제 저장된 데이터 행(Row) 정보")
        print("="*120)
        
        # 표 형태로 출력
        print(tabulate(rows, headers=colnames, tablefmt="psql"))
        
        print("\n💡 Tip: sequential_id(sid)는 업비트의 고유 번호이며, change_rate는 우리가 계산해서 넣은 값입니다.")
        print("="*120 + "\n")

        cur.close(); conn.close()
    except Exception as e:
        print(f"❌ 조회 실패: {e}")

if __name__ == "__main__":
    view_raw_data()