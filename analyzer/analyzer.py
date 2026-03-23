import json, psycopg2, sys, random
from kafka import KafkaConsumer

DB_CONFIG = {"host": "localhost",
            "database": "whale_db",
            "user": "whale_user",
            "password": "whale_password", 
            "port": 5432}

def main():
    # 카프카 컨슈머 (새 group_id로 옛날 데이터 무시)
    new_group = f"whale-v2-{random.randint(100, 999)}"
    consumer = KafkaConsumer(
        'upbit-trades',
        bootstrap_servers=['localhost:9092'],
        value_deserializer=lambda v: json.loads(v.decode('utf-8')),
        auto_offset_reset='latest', # 💡 실행 시점부터의 데이터만 받음
        group_id=new_group
    )
    
    conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
    print(f"🚀 [분석기] 시작! (Group: {new_group})")

    try:
        for msg in consumer:
            d = msg.value
            
            # 💡 KeyError 방어: 옛날 데이터면 pcp를 현재가와 같게 설정 (수익률 0%)
            tp = float(d.get('price', 0))
            pcp = float(d.get('pcp', tp)) 
            
            rate = ((tp - pcp) / pcp * 100) if pcp != 0 else 0
            sign = "▲" if rate > 0 else "▼" if rate < 0 else "-"
            amt = tp * float(d.get('volume', 0))
            side_txt = "🔴 매도" if d.get('side') == "ASK" else "🔵 매수"

            # 1. 화면 출력 (수익률 포함)
            print(f"📥 [{d['timestamp']}] {d['code']} | {side_txt} | {sign}{abs(rate):.2f}% | {amt:,.0f}원")

            # 2. DB 저장 (모든 변수 기록)
            cur.execute("""
                INSERT INTO trades (timestamp, code, price, volume, side, total_amount, prev_closing_price, change_rate, sequential_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (d['timestamp'], d['code'], tp, d.get('volume'), d.get('side'), amt, pcp, rate, d.get('sid')))
            conn.commit()

            if amt >= 100000000:
                print(f"\n🐳 [고래!!] {d['code']} {side_txt} {amt:,.0f}원 포착!\n")

    except KeyboardInterrupt: print("\n👋 종료")
    finally: cur.close(); conn.close()

if __name__ == "__main__":
    main()