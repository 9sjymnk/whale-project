import asyncio
import websockets
import json
import nest_asyncio
import sys
from datetime import datetime, timedelta, timezone
from kafka import KafkaProducer

nest_asyncio.apply()
KST = timezone(timedelta(hours=9))
CODES = ["KRW-BTC", "KRW-ETH"]
KAFKA_TOPIC = 'upbit-trades'
KAFKA_SERVER = 'localhost:9092'

# 1. Producer 설정 (기존 유지)
try:
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_SERVER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks=1, linger_ms=0, batch_size=0
    )
    print(f"✅ [수집기] 카프카 서버 연결 성공!")
except Exception as e:
    print(f"❌ 연결 실패: {e}"); sys.exit(1)

async def upbit_to_kafka_collector():
    uri = "wss://api.upbit.com/websocket/v1"
    try:
        async with websockets.connect(uri) as websocket:
            sub_fmt = [{"ticket":"test"}, {"type":"trade","codes":CODES, "isOnlyRealtime":True}, {"format":"SIMPLE"}]
            await websocket.send(json.dumps(sub_fmt))
            print("🚀 실시간 수집 시작... (중단하려면 Ctrl+C)")
            
            while True:
                # 💡 데이터를 기다리는 동안 중단될 수 있으므로 내부에서도 예외 처리
                recv_data = await websocket.recv()
                data = json.loads(recv_data)
                now_kst = datetime.now(KST)
                timestamp = now_kst.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                
                payload = {
                    'timestamp': timestamp,
                    'code': data.get('cd'), 
                    'price': data.get('tp'), 
                    'volume': data.get('tv'),
                    'side': data.get('ab')
                }

                producer.send(KAFKA_TOPIC, value=payload)
                producer.flush() 

                # 타임스탬프가 포함된 실시간 로그
                print(f"[{timestamp}] 📡 [전송] {payload['code']} | {payload['price']:,.0f}원", flush=True)

    except asyncio.CancelledError:
        # 💡 강제 종료 시 발생하는 비동기 예외를 잡아서 조용히 넘깁니다.
        pass
    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    try:
        # 비동기 루프 실행
        asyncio.run(upbit_to_kafka_collector())
    except KeyboardInterrupt:
        # 💡 [핵심] Ctrl+C 입력 시 에러 메시지 대신 출력할 문구
        print("\n\n👋 [알림] 사용자가 수집을 중단했습니다.")
    finally:
        # 🧹 종료 전 데이터 정리 및 Kafka 닫기
        print("🧹 남은 데이터를 정리하고 Kafka 연결을 해제합니다...")
        producer.flush()
        producer.close()
        print("✅ 수집기 종료 완료.")
        sys.exit(0) # 프로세스를 깔끔하게 종료