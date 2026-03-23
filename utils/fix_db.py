import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "database": "whale_db",
    "user": "whale_user",
    "password": "whale_password",
    "port": 5432
}

def fix_database():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("🛠️ DB 테이블 구조 업데이트 중...")
        
        # 💡 기존 테이블에 부족한 컬럼들을 하나씩 추가합니다.
        # 이미 있다면 에러가 나겠지만, 하나씩 실행해서 안전하게 처리합니다.
        commands = [
            "ALTER TABLE trades ADD COLUMN prev_closing_price NUMERIC;",
            "ALTER TABLE trades ADD COLUMN change_rate NUMERIC;",
            "ALTER TABLE trades ADD COLUMN sequential_id BIGINT;"
        ]
        
        for cmd in commands:
            try:
                cur.execute(cmd)
                conn.commit()
                print(f"✅ 실행 성공: {cmd.split('ADD COLUMN ')[1]}")
            except Exception as e:
                conn.rollback()
                print(f"ℹ️ 참고: {cmd.split('ADD COLUMN ')[1]} (이미 존재하거나 추가할 수 없음)")

        print("\n✨ 모든 컬럼이 준비되었습니다! 이제 analyzer.py를 다시 실행하세요.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")

if __name__ == "__main__":
    fix_database()