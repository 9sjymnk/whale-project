import json
import psycopg2
from kafka import KafkaConsumer

# 1. 접속 정보 설정
DB_CONFIG = {
    "host": "localhost",
    "database": "whale_db",
    "user": "whale_user",
    "password": "whale_password",
    "port": 5432
}
KAFKA_TOPIC = 'upbit-trades'
KAFKA_SERVER = 'localhost:9092'

def init_db():
    """DB에 데이터를 담을 테이블(선반)이 없으면 만드는 함수"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP,
                code TEXT,
                price NUMERIC,
                volume NUMERIC,
                side TEXT,
                total_amount NUMERIC
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("✅ DB 테이블 준비 완료! (trades 테이블 확인됨)")
    except Exception as e:
        print(f"❌ DB 초기화 실패: {e}")
        exit()

def main():
    # DB 테이블 생성 확인
    init_db()
    
    # Kafka 소비자(Consumer) 설정
    # group_id를 지정하면 내가 어디까지 읽었는지 기억해서 중복/누락을 방지합니다.
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_SERVER],
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        auto_offset_reset='earliest',  # 처음 실행 시 과거 데이터부터 싹 훑음
        group_id='whale-analyzer-group-v1' 
    )
    
    # DB 연결 유지
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print(f"🚀 분석기 가동 시작! [{KAFKA_TOPIC}] 데이터를 실시간으로 DB에 저장합니다.")

    try:
        for message in consumer:
            data = message.value
            total_amount = float(data['price']) * float(data['volume'])
            
            # DB에 데이터 삽입
            cur.execute("""
                INSERT INTO trades (timestamp, code, price, volume, side, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                data['timestamp'], data['code'], data['price'], 
                data['volume'], data['side'], total_amount
            ))
            
            # 즉시 반영 (Commit)
            conn.commit()
            
            # --- 실시간 저장 로그 (모든 거래) ---
            print(f"📥 저장 중: {data['code']} | {data['price']:,.0f}원 | {total_amount:,.0f}원")

            # --- 고래 알림 (1억 원 이상) ---
            if total_amount >= 100000000:
                print(f"🐳 [고래 발견!] {data['code']} | {total_amount:,.0f}원 | {data['side']}")

    except KeyboardInterrupt:
        print("\n👋 분석기를 안전하게 종료합니다.")
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()