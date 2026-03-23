import json
import psycopg2
import sys
from datetime import datetime
from kafka import KafkaConsumer

DB_CONFIG = {"host": "localhost", "database": "whale_db", "user": "whale_user", "password": "whale_password", "port": 5432}
KAFKA_TOPIC = 'upbit-trades'
KAFKA_SERVER = 'localhost:9092'

def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS trades (id SERIAL PRIMARY KEY, timestamp TIMESTAMP, code TEXT, price NUMERIC, volume NUMERIC, side TEXT, total_amount NUMERIC);")
    conn.commit(); cur.close(); conn.close()
    print("✅ [분석기] DB 준비 완료!")

def main():
    init_db()
    
    import random
    new_group_id = f"whale-group-{random.randint(1000, 9999)}"
    
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_SERVER],
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        auto_offset_reset='earliest',
        group_id=new_group_id,
        fetch_min_bytes=1,
        max_poll_records=1
    )
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    print(f"🚀 [분석기] 실시간 감시 시작... (Group: {new_group_id})")

    try:
        for message in consumer:
            data = message.value
            total_amount = float(data['price']) * float(data['volume'])
            
            # 💡 매수/매도 텍스트 처리 (ASK: 매도🔴, BID: 매수🔵)
            side_display = "🔴 매도" if data.get('side') == "ASK" else "🔵 매수"
            
            # 1️⃣ 타임스탬프와 매수/매도가 포함된 화면 출력
            print(f"📥 [{data['timestamp']}] {data['code']} | {side_display} | {total_amount:,.0f}원", flush=True)

            # 2️⃣ DB 저장
            cur.execute("""
                INSERT INTO trades (timestamp, code, price, volume, side, total_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (data['timestamp'], data['code'], data['price'], data['volume'], data['side'], total_amount))
            conn.commit()

            # 3️⃣ 고래 알림 (기존 형식 유지)
            if total_amount >= 100000000:
                print(f"\n🐳 [고래!] {data['code']} {side_display} {total_amount:,.0f}원 포착!\n", flush=True)

    except KeyboardInterrupt:
        print("\n👋 종료")
    finally:
        cur.close(); conn.close()

if __name__ == "__main__":
    main()