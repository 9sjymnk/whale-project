# backend/server.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import asyncio, psycopg2, requests, json
from datetime import datetime, timezone, timedelta

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DB_CONFIG = {
    "host": "3.35.207.98", "database": "whale_db",
    "user": "postgres", "password": "7124", "port": 5432
}

def get_official_open_price(market):
    try:
        url = f"https://api.upbit.com/v1/candles/days?market={market}&count=1"
        res = requests.get(url).json()
        return float(res[0]['opening_price'])
    except: return 1.0

@app.websocket("/ws/{coin}")
async def websocket_endpoint(websocket: WebSocket, coin: str):
    await websocket.accept()
    try:
        open_price = get_official_open_price(coin)
        last_update_date = datetime.now(timezone(timedelta(hours=9))).date()

        conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
        cur.execute(f"SELECT price, total_amount, side, timestamp, id FROM trades WHERE code='{coin}' ORDER BY timestamp ASC, id ASC")
        history = cur.fetchall()
        
        history_list = []
        for h in history:
            history_list.append({
                "price": float(h[0]), "amount": float(h[1]), 
                "side": h[2], "time": int(h[3].timestamp()) + 32400, "id": h[4]
            })
        
        await websocket.send_json({"type": "history", "data": history_list, "open_price": open_price})
        last_id = history[-1][4] if history else 0
        cur.close(); conn.close()

        while True:
            now_kst = datetime.now(timezone(timedelta(hours=9)))
            if now_kst.date() != last_update_date and now_kst.hour >= 9:
                open_price = get_official_open_price(coin)
                last_update_date = now_kst.date()

            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
            cur.execute(f"SELECT id, price, total_amount, side, timestamp FROM trades WHERE code='{coin}' AND id > {last_id} ORDER BY id ASC")
            rows = cur.fetchall()
            for r in rows:
                await websocket.send_json({
                    "type": "tick", "price": float(r[1]), "amount": float(r[2]), "side": r[3], 
                    "time": int(r[4].timestamp()) + 32400, "id": r[0], "open_price": open_price
                })
                last_id = r[0]
            cur.close(); conn.close()
            await asyncio.sleep(0.5)
    except Exception as e: print(f"Error: {e}")