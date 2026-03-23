import asyncio, websockets, json, nest_asyncio, sys
from datetime import datetime, timedelta, timezone
from kafka import KafkaProducer

nest_asyncio.apply()
KST = timezone(timedelta(hours=9))
CODES = ["KRW-BTC", "KRW-ETH"]
KAFKA_TOPIC = 'upbit-trades'
KAFKA_SERVER = 'localhost:9092'

try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_SERVER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks=1, linger_ms=0, batch_size=0
    )
    print("✅ [수집기] 카프카 연결 성공!")
except Exception as e:
    print(f"❌ 연결 실패: {e}"); sys.exit(1)

async def upbit_to_kafka_collector():
    uri = "wss://api.upbit.com/websocket/v1"
    try:
        async with websockets.connect(uri) as websocket:
            sub_fmt = [{"ticket":"test"}, {"type":"trade","codes":CODES, "isOnlyRealtime":True}, {"format":"SIMPLE"}]
            await websocket.send(json.dumps(sub_fmt))
            print("🚀 실시간 수집 시작... (중단: Ctrl+C)")
            
            while True:
                data = json.loads(await websocket.recv())
                now_kst = datetime.now(KST)
                timestamp = now_kst.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                # 💡 예측 모델을 위한 필수 변수 3종(pcp, c, sid) 추가
                payload = {
                    'timestamp': timestamp,
                    'code': data.get('cd'), 
                    'price': data.get('tp'),      # 현재가
                    'volume': data.get('tv'),     # 체결량
                    'side': data.get('ab'),       # ASK/BID
                    'pcp': data.get('pcp'),       # 전일 종가 (수익률 기준점)
                    'change': data.get('c'),      # RISE/FALL/EVEN (시장 상태)
                    'sid': data.get('sid')        # 체결 고유 번호 (중복 방지)
                }

                producer.send(KAFKA_TOPIC, value=payload)
                producer.flush() 

                print(f"[{timestamp}] 📡 [전송] {payload['code']} | {payload['price']:,.0f}원", flush=True)

    except asyncio.CancelledError: pass
    except Exception as e: print(f"❌ 에러: {e}")

if __name__ == "__main__":
    try: asyncio.run(upbit_to_kafka_collector())
    except KeyboardInterrupt: print("\n👋 수집 중단.")
    finally: producer.close(); sys.exit(0)