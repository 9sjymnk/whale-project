# backend/server.py
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt
import bcrypt
import asyncio, psycopg2, requests, json, os, websockets
from datetime import datetime, timezone, timedelta

# 1. 환경 변수 로드
load_dotenv()

app = FastAPI()

# ── AUTH 설정 ──
SECRET_KEY = os.getenv("SECRET_KEY", "whale-dev-secret-DO-NOT-USE-IN-PROD")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str

# 2. CORS 설정 (기존 유지)
app.add_middleware(
    CORSMiddleware, 
    allow_origins=["*"], 
    allow_methods=["*"], 
    allow_headers=["*"]
)

# 3. DB 설정 (기존 유지)
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASS"),
    "port": int(os.getenv("DB_PORT", 5432))
}

# ── AUTH 헬퍼 함수 ──
def _db():
    return psycopg2.connect(**DB_CONFIG)

def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def _verify(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def _make_token(username: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 정보가 유효하지 않습니다.", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT id, username, email, created_at FROM users WHERE username=%s AND is_active=TRUE", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        raise exc
    return {"id": row[0], "username": row[1], "email": row[2], "created_at": row[3].isoformat() if row[3] else None}


# ── AUTH 엔드포인트 ──
@app.on_event("startup")
def create_users_table():
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE,
            slack_webhook TEXT,
            kakao_token TEXT
        )
    """)
    conn.commit(); cur.close(); conn.close()


@app.post("/auth/register")
def register(data: UserRegister):
    if len(data.username) < 3:
        raise HTTPException(status_code=400, detail="아이디는 3자 이상이어야 합니다.")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=%s OR email=%s", (data.username, data.email))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(status_code=400, detail="이미 사용 중인 아이디 또는 이메일입니다.")
    cur.execute(
        "INSERT INTO users (username, email, hashed_password) VALUES (%s, %s, %s)",
        (data.username, data.email, _hash(data.password))
    )
    conn.commit(); cur.close(); conn.close()
    return {"access_token": _make_token(data.username), "token_type": "bearer", "username": data.username}


@app.post("/auth/login")
def login(data: UserLogin):
    conn = _db(); cur = conn.cursor()
    cur.execute("SELECT username, hashed_password FROM users WHERE username=%s AND is_active=TRUE", (data.username,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row or not _verify(data.password, row[1]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    return {"access_token": _make_token(row[0]), "token_type": "bearer", "username": row[0]}


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return user


# 4. 기준가 가져오기 함수 (업비트 UI와 일치하도록 ticker API로 수정)
def get_official_open_price(market):
    try:
        # 업비트 웹 UI의 등락률 기준인 '전일 종가(prev_closing_price)'를 가져옵니다.
        url = f"https://api.upbit.com/v1/ticker?markets={market}"
        res = requests.get(url, timeout=2).json()
        return float(res[0]['prev_closing_price'])
    except Exception as e:
        print(f"API Fetch Error: {e}")
        return 1.0

@app.websocket("/ws/{coin}")
async def websocket_endpoint(websocket: WebSocket, coin: str):
    await websocket.accept()
    
    conn = None # 자원 해제를 위해 미리 선언
    
    try:
        # [기존 기능 유지] 초기 기준가 및 날짜 설정
        open_price = get_official_open_price(coin)
        last_update_date = datetime.now(timezone(timedelta(hours=9))).date()

        # [기존 기능 유지] 초기 히스토리 데이터 로드
        conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
        cur.execute(f"SELECT price, total_amount, side, timestamp, id FROM trades WHERE code='{coin}' ORDER BY timestamp ASC, id ASC")
        history = cur.fetchall()
        
        history_list = []
        for h in history:
            history_list.append({
                "price": float(h[0]), 
                "amount": float(h[1]), 
                "side": h[2], 
                "time": int(h[3].timestamp()) + 32400, # KST 보정 유지
                "id": h[4]
            })
        
        # 클라이언트에 초기 데이터 전송
        await websocket.send_json({"type": "history", "data": history_list, "open_price": open_price})
        
        cur.close(); conn.close()
        conn = None

        # 업비트 WebSocket 직접 연결하여 실시간 스트리밍
        upbit_uri = "wss://api.upbit.com/websocket/v1"
        async with websockets.connect(upbit_uri, ping_interval=20, ping_timeout=30) as upbit_ws:
            sub = [{"ticket": "whale-watcher"}, {"type": "trade", "codes": [coin], "isOnlyRealtime": True}, {"format": "SIMPLE"}]
            await upbit_ws.send(json.dumps(sub))

            while True:
                now_kst = datetime.now(timezone(timedelta(hours=9)))

                # 오전 9시 기준 날짜 변경 시 기준가 갱신 로직 유지
                if now_kst.date() != last_update_date and now_kst.hour >= 9:
                    open_price = get_official_open_price(coin)
                    last_update_date = now_kst.date()

                try:
                    raw = await asyncio.wait_for(upbit_ws.recv(), timeout=15)
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "heartbeat"})
                    continue
                data = json.loads(raw)

                price      = float(data.get('tp', 0))
                volume     = float(data.get('tv', 0))
                side       = data.get('ab', '')
                amount     = price * volume
                pcp        = float(data.get('pcp', price))
                change_dir = data.get('c', '')
                sid        = data.get('sid')
                ts         = datetime.now(timezone(timedelta(hours=9)))

                # DB에 저장 (기존 기능 유지 - 히스토리 누적)
                trade_id = None
                try:
                    conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO trades (timestamp, code, price, volume, side, total_amount, pcp, change, sid)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (timestamp, code) DO NOTHING
                        RETURNING id
                    """, (ts, coin, price, volume, side, amount, pcp, change_dir, sid))
                    row = cur.fetchone()
                    if row:
                        trade_id = row[0]
                    conn.commit(); cur.close(); conn.close(); conn = None
                except Exception as db_err:
                    print(f"DB insert error: {db_err}")
                    if conn: conn.close(); conn = None

                # 실시간 틱 데이터 전송
                await websocket.send_json({
                    "type": "tick",
                    "price": price,
                    "amount": amount,
                    "side": side,
                    "time": int(ts.timestamp()) + 32400,  # KST 보정 유지
                    "id": trade_id,
                    "open_price": open_price
                })

    except WebSocketDisconnect:
        print(f"INFO: WebSocket for {coin} closed by client.")

    except asyncio.CancelledError:
        pass  # 서버 정상 종료 시 발생 — 무시

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        if conn:
            conn.close()


@app.get("/daily/{coin}")
def get_daily(coin: str):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT
            (timestamp AT TIME ZONE 'Asia/Seoul')::date AS trade_date,
            (array_agg(price ORDER BY timestamp ASC))[1]  AS open_price,
            MAX(price)                                     AS high_price,
            MIN(price)                                     AS low_price,
            (array_agg(price ORDER BY timestamp DESC))[1] AS close_price,
            SUM(volume)                                    AS total_volume
        FROM trades
        WHERE code = %s
        GROUP BY (timestamp AT TIME ZONE 'Asia/Seoul')::date
        ORDER BY trade_date DESC
        LIMIT 41
    """, (coin,))
    rows = cur.fetchall(); cur.close(); conn.close()
    result = []
    for i, r in enumerate(rows):
        prev_close = float(rows[i + 1][4]) if i + 1 < len(rows) else None
        close = float(r[4])
        change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
        result.append({
            "date":       str(r[0]),
            "open":       float(r[1]),
            "high":       float(r[2]),
            "low":        float(r[3]),
            "close":      close,
            "volume":     float(r[5]),
            "change_pct": change_pct,
        })
    return result[:40]


@app.get("/whale/hourly/{coin}")
def get_hourly_whale(coin: str, threshold: float = 100000000, days: int = 7):
    conn = _db(); cur = conn.cursor()
    cur.execute(f"""
        SELECT
            EXTRACT(HOUR FROM timestamp AT TIME ZONE 'Asia/Seoul') AS hour,
            COUNT(*) AS cnt,
            SUM(total_amount) AS total,
            SUM(CASE WHEN side = 'BID' THEN total_amount ELSE 0 END) AS buy_total,
            SUM(CASE WHEN side = 'ASK'  THEN total_amount ELSE 0 END) AS sell_total,
            SUM(CASE WHEN side = 'BID' THEN 1 ELSE 0 END) AS buy_cnt,
            SUM(CASE WHEN side = 'ASK'  THEN 1 ELSE 0 END) AS sell_cnt
        FROM trades
        WHERE code = %s
          AND total_amount >= %s
          AND timestamp >= NOW() - INTERVAL '{int(days)} days'
        GROUP BY hour
        ORDER BY hour
    """, (coin, threshold))
    rows = cur.fetchall(); cur.close(); conn.close()
    lookup = {int(r[0]): {"cnt": int(r[1]), "total": float(r[2]), "buy_total": float(r[3]),
                           "sell_total": float(r[4]), "buy_cnt": int(r[5]), "sell_cnt": int(r[6])}
              for r in rows}
    empty = {"cnt": 0, "total": 0.0, "buy_total": 0.0, "sell_total": 0.0, "buy_cnt": 0, "sell_cnt": 0}
    return [{"hour": h, **lookup.get(h, empty)} for h in range(24)]


@app.get("/whale/dates/{coin}")
def get_whale_dates(coin: str, threshold: float = 100000000):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT (timestamp AT TIME ZONE 'Asia/Seoul')::date AS trade_date
        FROM trades
        WHERE code = %s AND total_amount >= %s
        ORDER BY trade_date DESC
        LIMIT 60
    """, (coin, threshold))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [str(r[0]) for r in rows]


@app.get("/whale/daily-log/{coin}/{date}")
def get_daily_whale_log(coin: str, date: str, threshold: float = 100000000):
    conn = _db(); cur = conn.cursor()
    cur.execute("""
        SELECT price, total_amount, side, timestamp, volume
        FROM trades
        WHERE code = %s
          AND total_amount >= %s
          AND (timestamp AT TIME ZONE 'Asia/Seoul')::date = %s::date
        ORDER BY timestamp DESC
    """, (coin, threshold, date))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [{"price": float(r[0]), "amount": float(r[1]), "side": r[2],
             "time": int(r[3].timestamp()) + 32400, "volume": float(r[4])} for r in rows]