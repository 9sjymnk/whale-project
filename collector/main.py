import asyncio, websockets, json, nest_asyncio, sys
from datetime import datetime, timedelta, timezone
from kafka import KafkaProducer

nest_asyncio.apply()
KST = timezone(timedelta(hours=9))
CODES = ["KRW-BTC", "KRW-ETH"]
KAFKA_TOPIC = 'upbit-trades'
KAFKA_SERVER = 'localhost:9092'

# 카프카 프로듀서 설정 최적화
try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_SERVER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks=1, 
        linger_ms=10, # 10ms 동안 모아서 보냄 (성능 향상)
        batch_size=16384
    )
    print("✅ [수집기] 카프카 연결 성공!")
except Exception as e:
    print(f"❌ 카프카 연결 실패: {e}"); sys.exit(1)

async def upbit_to_kafka_collector():
    uri = "wss://api.upbit.com/websocket/v1"
    
    while True: # 무한 루프로 재연결 보장
        try:
            # 핑 설정을 추가하여 timeout 에러 방지
            async with websockets.connect(uri, ping_interval=20, ping_timeout=30) as websocket:
                sub_fmt = [{"ticket":"test"}, {"type":"trade","codes":CODES, "isOnlyRealtime":True}, {"format":"SIMPLE"}]
                await websocket.send(json.dumps(sub_fmt))
                print(f"🚀 실시간 수집 시작... ({datetime.now(KST).strftime('%H:%M:%S')})")
                
                while True:
                    raw_data = await websocket.recv()
                    data = json.loads(raw_data)
                    
                    now_kst = datetime.now(KST)
                    timestamp = now_kst.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    
                    payload = {
                        'timestamp': timestamp,
                        'code': data.get('cd'), 
                        'price': data.get('tp'),
                        'volume': data.get('tv'),
                        'side': data.get('ab'),
                        'pcp': data.get('pcp'),
                        'change': data.get('c'),
                        'sid': data.get('sid')
                    }

                    producer.send(KAFKA_TOPIC, value=payload)
                    # producer.flush() 는 성능 저하의 원인이므로 루프 밖에서 관리하거나 제거합니다.

                    print(f"[{timestamp}] 📡 [전송] {payload['code']} | {payload['price']:,.0f}원", flush=True)

        except websockets.ConnectionClosed:
            print("⚠️ 연결이 끊겼습니다. 5초 후 다시 연결합니다...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(upbit_to_kafka_collector())
    except KeyboardInterrupt:
        print("\n👋 수집 중단.")
    finally:
        producer.close()
        sys.exit(0)