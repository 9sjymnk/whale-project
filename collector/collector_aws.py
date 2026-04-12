import asyncio
import websockets
import json
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta, timezone

# 1. DB 설정
DB_CONFIG = {
    "host": "localhost",
    "database": "whale_db",
    "user": "postgres",
    "password": "1234",
    "port": 5432
}

KST = timezone(timedelta(hours=9))
CODES = ["KRW-BTC", "KRW-ETH"]
data_queue = asyncio.Queue()

async def db_writer():
    """큐에서 데이터를 꺼내 DB에 묶음(Batch)으로 저장하는 일꾼"""
    print("👷 DB 저장 프로세스가 가동되었습니다.")
    while True:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()

            while True:
                batch = []
                try:
                    for _ in range(50):
                        data = await asyncio.wait_for(data_queue.get(), timeout=1.0)
                        batch.append(data)
                except asyncio.TimeoutError:
                    pass

                if batch:
                    execute_values(cur, """
                        INSERT INTO trades (timestamp, code, price, volume, side, total_amount, pcp, change, sid)
                        VALUES %s
                        ON CONFLICT (timestamp, code) DO NOTHING
                    """, batch)
                    conn.commit()
                    for _ in range(len(batch)):
                        data_queue.task_done()

        except Exception as e:
            print(f"❌ DB 에러 발생: {e}. 5초 후 재연결 시도...")
            await asyncio.sleep(5)
        finally:
            if 'conn' in locals() and conn:
                conn.close()

async def upbit_collector():
    """업비트 웹소켓에서 데이터를 수신하여 큐에 전달"""
    uri = "wss://api.upbit.com/websocket/v1"

    while True:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=30) as websocket:
                sub_fmt = [
                    {"ticket":"whale_project"},
                    {"type":"trade", "codes":CODES, "isOnlyRealtime":True},
                    {"format":"SIMPLE"}
                ]
                await websocket.send(json.dumps(sub_fmt))
                print(f"🚀 수집 시작: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

                while True:
                    raw_data = await websocket.recv()
                    data = json.loads(raw_data)

                    now_kst = datetime.now(KST)
                    payload = (
                        now_kst.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                        data.get('cd'),
                        data.get('tp'),
                        data.get('tv'),
                        data.get('ab'),
                        data.get('tp') * data.get('tv'),
                        data.get('pcp'),
                        data.get('c'),
                        data.get('sid')
                    )
                    await data_queue.put(payload)

        except Exception as e:
            print(f"📡 연결 끊김: {e}. 5초 후 재연결 시도...")
            await asyncio.sleep(5)

async def main():
    await asyncio.gather(upbit_collector(), db_writer())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 수집 종료.")
