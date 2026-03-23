import asyncio
import websockets
import json
import nest_asyncio
from datetime import datetime, timedelta, timezone
from kafka import KafkaProducer

# 1. 환경 설정
nest_asyncio.apply()
KST = timezone(timedelta(hours=9))
CODES = ["KRW-BTC", "KRW-ETH"]

# Kafka 설정 (도커 내부가 아닌 내 PC에서 접속하는 주소)
KAFKA_TOPIC = 'upbit-trades'
KAFKA_SERVER = 'localhost:9092'

# 2. Kafka Producer 초기화
try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_SERVER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks=0  # 전송 속도를 극대화하기 위해 확인 절차 생략
    )
    print(f"✅ Kafka Producer 연결 성공! (Server: {KAFKA_SERVER})")
except Exception as e:
    print(f"❌ Kafka 연결 실패: {e}")
    exit()

async def upbit_to_kafka_collector():
    uri = "wss://api.upbit.com/websocket/v1"

    try:
        async with websockets.connect(uri) as websocket:
            # SIMPLE 포맷 구독 신청 (데이터가 가볍고 빠름)
            subscribe_fmt = [
                {"ticket": "whale-local-collector"},
                {"type": "trade", "codes": CODES, "isOnlyRealtime": True},
                {"format": "SIMPLE"}
            ]
            await websocket.send(json.dumps(subscribe_fmt))
            
            print(f"🚀 실시간 수집 시작! 데이터를 Kafka [{KAFKA_TOPIC}]로 쏘는 중...")
            print(f"🛑 중단하려면 Ctrl+C를 누르세요.")

            while True:
                recv_data = await websocket.recv()
                data = json.loads(recv_data)
                # ------------------------------------------
                print(f"📡 데이터 수집 중: {data.get('cd')} {data.get('tp'):,.0f}원") 
                # ------------------------------------------
                now_kst = datetime.now(KST)
                
                # Kafka로 보낼 예쁜 데이터 패키지 만들기
                payload = {
                    'timestamp': now_kst.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'code': data.get('cd'),
                    'price': data.get('tp'),
                    'volume': data.get('tv'),
                    'side': data.get('ab'),
                    'pcp': data.get('pcp'),
                    'change': data.get('c'),
                    'change_price': data.get('cp'),
                    'sid': data.get('sid'),
                    'ttms': data.get('ttms')
                }

                # 3. Kafka로 데이터 슛!
                producer.send(KAFKA_TOPIC, value=payload)

                # 고래 알림 (1억 원 이상 단일 체결 시 터미널 출력)
                total_amount = data.get('tp') * data.get('tv')
                if total_amount >= 100000000:
                    print(f"🐳 [고래!] {data.get('cd')} | {total_amount:,.0f}원 | {data.get('ab')}")

    except Exception as e:
        print(f"❌ 에러 발생: {e}. 3초 후 재연결을 시도합니다...")
        await asyncio.sleep(3)
        await upbit_to_kafka_collector()

if __name__ == "__main__":
    try:
        asyncio.run(upbit_to_kafka_collector())
    except KeyboardInterrupt:
        print("\n👋 수집 중단. 남은 데이터를 전송하고 안전하게 종료합니다.")
        producer.flush()
        producer.close()