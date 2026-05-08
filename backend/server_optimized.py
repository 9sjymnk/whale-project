# backend/server_optimized.py  ← 데모용 최적화 버전 (포트 8001)
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt
import bcrypt
import asyncio, psycopg2, requests, json, os, websockets, pickle, numpy as np, time
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

class SlackWebhookUpdate(BaseModel):
    webhook_url: str

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
    conn = psycopg2.connect(**DB_CONFIG)
    # naive timestamp 컬럼 + AT TIME ZONE 'Asia/Seoul' → ::date 가
    # 세션 타임존에 의존하므로 KST로 강제. 안 그러면 04-23 같은 날짜가 합쳐지거나 사라짐
    with conn.cursor() as c:
        c.execute("SET TIME ZONE 'Asia/Seoul'")
    conn.commit()
    return conn

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
    cur.execute("SELECT id, username, email, created_at, slack_webhook FROM users WHERE username=%s AND is_active=TRUE", (username,))
    row = cur.fetchone(); cur.close(); conn.close()
    if not row:
        raise exc
    return {"id": row[0], "username": row[1], "email": row[2], "created_at": row[3].isoformat() if row[3] else None, "slack_webhook": row[4]}


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
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_trades_code_ts_id
        ON trades (code, timestamp DESC, id DESC)
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


@app.put("/auth/slack-webhook")
def update_slack_webhook(data: SlackWebhookUpdate, user=Depends(get_current_user)):
    conn = _db(); cur = conn.cursor()
    url = data.webhook_url.strip() or None
    cur.execute("UPDATE users SET slack_webhook = %s WHERE username = %s", (url, user["username"]))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}


class SlackWhaleNotify(BaseModel):
    coin: str
    side: str
    price: float
    amount: float
    volume: float
    date_str: str = ""
    time_str: str

@app.post("/notify/slack-whale")
async def notify_slack_whale_endpoint(data: SlackWhaleNotify, user=Depends(get_current_user)):
    webhook = user.get("slack_webhook")
    if not webhook:
        return {"ok": False}
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_slack, webhook, data.coin, data.side, data.price, data.amount, data.volume, data.date_str, data.time_str)
    return {"ok": True}


# ── WebSocket 연결 관리자 ──
class ConnectionManager:
    def __init__(self):
        self.connections: dict[str, list[WebSocket]] = {}

    def add(self, coin: str, ws: WebSocket):
        self.connections.setdefault(coin, []).append(ws)

    def remove(self, coin: str, ws: WebSocket):
        if coin in self.connections:
            try:
                self.connections[coin].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, coin: str, message: dict):
        for ws in list(self.connections.get(coin, [])):
            try:
                await ws.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()


# ── Slack 고래 알림 ──
def _send_slack(webhook_url: str, coin: str, side: str, price: float, amount: float, volume: float, date_str: str, time_str: str):
    side_label = "🟢 매수" if side == "BID" else "🔴 매도"
    coin_name = coin.replace("KRW-", "")
    date_line = f"날짜: {date_str}\n" if date_str else ""
    text = (
        f"🐋 고래 거래 감지 [{coin_name}]\n"
        f"{side_label}\n"
        f"체결가: ₩{int(price):,}\n"
        f"수량: {volume:.4f} {coin_name}\n"
        f"총액: {amount / 1e8:.2f}억원\n"
        f"{date_line}"
        f"시각: {time_str} (KST)"
    )
    try:
        requests.post(webhook_url, json={"text": text}, timeout=5)
    except Exception as e:
        print(f"슬랙 알림 실패: {e}")


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
    manager.add(coin, websocket)
    
    conn = None # 자원 해제를 위해 미리 선언
    
    try:
        import time as _t
        # 기준가 및 날짜 설정
        _s = _t.monotonic()
        open_price = get_official_open_price(coin)
        print(f"[{coin}] get_open_price: {_t.monotonic()-_s:.2f}s")
        last_update_date = datetime.now(timezone(timedelta(hours=9))).date()

        # ── Phase 1: 최근 500건만 즉시 전송 → 연결 완료 + 차트 즉시 표시 ──
        _s = _t.monotonic()
        conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
        print(f"[{coin}] db connect: {_t.monotonic()-_s:.2f}s")

        # COUNT는 백그라운드로 → Phase 1 안 막음, 결과 도착하면 별도 메시지로 전송
        total_records = 0

        _s = _t.monotonic()
        cur.execute("""
            SELECT price, total_amount, side, timestamp, id
            FROM (
                SELECT price, total_amount, side, timestamp, id
                FROM trades WHERE code = %s
                ORDER BY timestamp DESC, id DESC LIMIT 500
            ) sub ORDER BY timestamp ASC, id ASC
        """, (coin,))
        initial_rows = cur.fetchall()
        print(f"[{coin}] Phase1 SELECT: {_t.monotonic()-_s:.2f}s")
        cur.close(); conn.close(); conn = None

        oldest_ts = initial_rows[0][3] if initial_rows else None
        oldest_id = initial_rows[0][4] if initial_rows else None
        initial_list = [{"price": float(h[0]), "amount": float(h[1]), "side": h[2],
                         "time": int(h[3].timestamp()) + 32400, "id": h[4]} for h in initial_rows]

        await websocket.send_json({
            "type": "history",
            "data": initial_list,
            "open_price": open_price,
            "total_records": total_records,
        })

        # ── Phase 2: 7일치 데이터를 timestamp 기반 페이지네이션으로 백그라운드 전송 ──
        # (id 기반은 직접 백필한 데이터 - 큰 id, 오래된 timestamp - 를 못 잡음)
        async def backfill():
            CHUNK = 5000
            queue = asyncio.Queue(maxsize=4)
            loop  = asyncio.get_running_loop()

            def _run_all():
                # 커넥션 1개로 전체 백필 — 스레드 안에서 실행
                try:
                    c2 = psycopg2.connect(**DB_CONFIG); cu2 = c2.cursor()
                    ts, rid = oldest_ts, oldest_id
                    total = 0; idx = 0
                    while True:
                        if ts is not None:
                            cu2.execute("""
                                SELECT price, total_amount, side, timestamp, id
                                FROM trades
                                WHERE code = %s
                                  AND (timestamp, id) < (%s, %s)
                                  AND timestamp >= NOW() - INTERVAL '7 days'
                                ORDER BY timestamp DESC, id DESC
                                LIMIT %s
                            """, (coin, ts, rid, CHUNK))
                        else:
                            cu2.execute("""
                                SELECT price, total_amount, side, timestamp, id
                                FROM trades
                                WHERE code = %s AND timestamp >= NOW() - INTERVAL '7 days'
                                ORDER BY timestamp DESC, id DESC
                                LIMIT %s
                            """, (coin, CHUNK))
                        rows = cu2.fetchall()
                        if not rows:
                            break
                        ts  = rows[-1][3]
                        rid = rows[-1][4]
                        total += len(rows)
                        idx  += 1
                        data = [{"price": float(r[0]), "amount": float(r[1]), "side": r[2],
                                 "time": int(r[3].timestamp()) + 32400} for r in rows]
                        # 큐가 꽉 차면 전송이 따라올 때까지 블로킹 (백프레셔)
                        asyncio.run_coroutine_threadsafe(queue.put((data, idx, total)), loop).result()
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
                except Exception as e:
                    print(f"Backfill thread error: {e}")
                    asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()
                finally:
                    cu2.close(); c2.close()

            loop.run_in_executor(None, _run_all)

            total_sent = 0
            while True:
                item = await queue.get()
                if item is None:
                    break
                data, chunk_idx, total_sent = item
                try:
                    await websocket.send_json({
                        "type": "history_prepend",
                        "data": data,
                        "chunk": chunk_idx,
                        "total_sent": total_sent,
                    })
                except Exception:
                    return  # 연결 끊기면 조용히 종료

            try:
                await websocket.send_json({"type": "backfill_done", "total": total_sent})
            except Exception:
                pass

        # 백필은 Upbit 연결 기다리지 않고 즉시 시작 (Upbit 실패해도 과거 데이터는 떠야 함)
        backfill_task = asyncio.create_task(backfill())

        # COUNT 백그라운드 — 결과 오면 별도 메시지로 진행률 표시 갱신
        async def _send_count():
            try:
                def _q():
                    c = psycopg2.connect(**DB_CONFIG); cu = c.cursor()
                    cu.execute("SELECT COUNT(*) FROM trades WHERE code = %s AND timestamp >= NOW() - INTERVAL '7 days'", (coin,))
                    n = cu.fetchone()[0]
                    cu.close(); c.close()
                    return n
                n = await asyncio.get_running_loop().run_in_executor(None, _q)
                await websocket.send_json({"type": "total_count", "total_records": n})
            except Exception:
                pass
        asyncio.create_task(_send_count())

        # 업비트 WebSocket — Upbit 끊겨도 클라이언트 연결 유지하며 내부 재연결
        upbit_uri = "wss://api.upbit.com/websocket/v1"
        sub = [{"ticket": "whale-watcher"}, {"type": "trade", "codes": [coin], "isOnlyRealtime": True}, {"format": "SIMPLE"}]

        while True:
            upbit_ws = None
            for attempt in range(5):
                try:
                    upbit_ws = await asyncio.wait_for(
                        websockets.connect(upbit_uri, ping_interval=None, ping_timeout=None, open_timeout=15),
                        timeout=20
                    )
                    break
                except Exception as ue:
                    print(f"[{coin}] Upbit connect attempt {attempt+1} failed: {ue!r}")
                    await asyncio.sleep(3)

            if upbit_ws is None:
                print(f"[{coin}] Upbit 연결 실패 — 15초 후 재시도")
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    return  # 클라이언트도 끊기면 종료
                await asyncio.sleep(15)
                continue

            try:
                async with upbit_ws:
                    await upbit_ws.send(json.dumps(sub))

                    while True:
                        now_kst = datetime.now(timezone(timedelta(hours=9)))
                        if now_kst.date() != last_update_date and now_kst.hour >= 9:
                            open_price = get_official_open_price(coin)
                            last_update_date = now_kst.date()

                        try:
                            raw = await asyncio.wait_for(upbit_ws.recv(), timeout=15)
                        except asyncio.TimeoutError:
                            try:
                                await websocket.send_json({"type": "heartbeat"})
                            except Exception:
                                return
                            continue
                        except Exception:
                            break  # Upbit 끊김 → 내부 루프 탈출 후 재연결

                        data = json.loads(raw)
                        price      = float(data.get('tp', 0))
                        volume     = float(data.get('tv', 0))
                        side       = data.get('ab', '')
                        amount     = price * volume
                        pcp        = float(data.get('pcp', price))
                        change_dir = data.get('c', '')
                        sid        = data.get('sid')
                        ts         = datetime.now(timezone(timedelta(hours=9)))

                        trade_id = None
                        try:
                            conn = psycopg2.connect(**DB_CONFIG); cur = conn.cursor()
                            cur.execute("""
                                INSERT INTO trades (timestamp, code, price, volume, side, total_amount, pcp, change, sid)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (sid, code) DO NOTHING
                                RETURNING id
                            """, (ts, coin, price, volume, side, amount, pcp, change_dir, sid))
                            row = cur.fetchone()
                            if row:
                                trade_id = row[0]
                            conn.commit(); cur.close(); conn.close(); conn = None
                        except Exception as db_err:
                            print(f"DB insert error: {db_err}")
                            if conn: conn.close(); conn = None

                        try:
                            await websocket.send_json({
                                "type": "tick",
                                "price": price,
                                "amount": amount,
                                "side": side,
                                "time": int(ts.timestamp()) + 32400,
                                "id": trade_id,
                                "open_price": open_price
                            })
                        except Exception:
                            return

            except Exception as ue:
                print(f"[{coin}] Upbit dropped: {ue!r} — reconnecting")

            await asyncio.sleep(1)  # 잠깐 후 Upbit 재연결

    except WebSocketDisconnect:
        print(f"INFO: WebSocket for {coin} closed by client.")

    except asyncio.CancelledError:
        pass  # 서버 정상 종료 시 발생 — 무시

    except Exception as e:
        print(f"ERROR: {e}")

    finally:
        manager.remove(coin, websocket)
        if conn:
            conn.close()
        try:
            backfill_task.cancel()
        except Exception:
            pass


_daily_cache: dict = {}  # coin → (fetched_at, data)

@app.get("/daily/{coin}")
def get_daily(coin: str):
    import time as _t
    now = _t.time()
    cached = _daily_cache.get(coin)
    if cached and now - cached[0] < 60:
        return cached[1]

    # 업비트 일봉 API (이미 집계된 데이터 — DB 풀스캔 불필요)
    try:
        resp = requests.get(
            f"https://api.upbit.com/v1/candles/days?market={coin}&count=41",
            timeout=3,
        ).json()
        result = []
        for i, r in enumerate(resp):
            prev_close = float(resp[i + 1]["trade_price"]) if i + 1 < len(resp) else None
            close = float(r["trade_price"])
            change_pct = round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            result.append({
                "date":       r["candle_date_time_kst"][:10],
                "open":       float(r["opening_price"]),
                "high":       float(r["high_price"]),
                "low":        float(r["low_price"]),
                "close":      close,
                "volume":     float(r["candle_acc_trade_volume"]),
                "change_pct": change_pct,
            })
        result = result[:40]
        _daily_cache[coin] = (now, result)
        return result
    except Exception:
        pass

    # 폴백: DB 직접 집계
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
        WHERE code = %s AND timestamp >= NOW() - INTERVAL '45 days'
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
    result = result[:40]
    _daily_cache[coin] = (now, result)
    return result


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
          AND timestamp >= NOW() - INTERVAL '60 days'
        ORDER BY trade_date DESC
        LIMIT 60
    """, (coin, threshold))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [str(r[0]) for r in rows]


@app.get("/whale/daily-log/{coin}/{date}")
def get_daily_whale_log(coin: str, date: str, threshold: float = 100000000):
    conn = _db(); cur = conn.cursor()
    # 함수 호출 필터(AT TIME ZONE)는 인덱스 못 씀 → 시간 범위로 변환해서 인덱스 사용
    cur.execute("""
        SELECT price, total_amount, side, timestamp, volume
        FROM trades
        WHERE code = %s
          AND total_amount >= %s
          AND timestamp >= (%s::date)::timestamp AT TIME ZONE 'Asia/Seoul'
          AND timestamp <  ((%s::date) + INTERVAL '1 day')::timestamp AT TIME ZONE 'Asia/Seoul'
        ORDER BY timestamp DESC
    """, (coin, threshold, date, date))
    rows = cur.fetchall(); cur.close(); conn.close()
    return [{"price": float(r[0]), "amount": float(r[1]), "side": r[2],
             "time": int(r[3].timestamp()) + 32400, "volume": float(r[4])} for r in rows]


# ── AI 예측 ──
_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'model.pkl')
_model_bundle: dict | None = None

def _load_model() -> dict:
    global _model_bundle
    if _model_bundle is None:
        if not os.path.exists(_MODEL_PATH):
            raise HTTPException(status_code=503, detail="모델 파일이 없습니다. train_model.py를 먼저 실행하세요.")
        with open(_MODEL_PATH, "rb") as f:
            _model_bundle = pickle.load(f)
    return _model_bundle


def _build_prediction_features(coin: str):
    """최근 고래 거래 직전 10분 데이터로 특성 벡터 생성. (features, seconds_ago) 반환"""
    conn = _db(); cur = conn.cursor()

    # 가장 최근 고래 거래 (시간 제한 없음)
    cur.execute("""
        SELECT timestamp, price, side, total_amount,
               EXTRACT(EPOCH FROM (NOW() - timestamp))::int AS seconds_ago
        FROM trades
        WHERE code = %s AND total_amount >= 100000000
        ORDER BY timestamp DESC LIMIT 1
    """, (coin,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return None

    ts, w_price, w_side, w_amt, seconds_ago = row
    w_price = float(w_price)
    w_amt   = float(w_amt)

    # 직전 10분 거래 데이터
    window_start = ts - timedelta(minutes=10)
    cur.execute("""
        SELECT price, side, total_amount, volume
        FROM trades
        WHERE code = %s AND timestamp >= %s AND timestamp < %s
        ORDER BY timestamp ASC
    """, (coin, window_start, ts))
    pre_rows = cur.fetchall()
    cur.close(); conn.close()

    if len(pre_rows) < 3:
        return None

    prices      = [float(r[0]) for r in pre_rows]
    buy_amount  = sum(float(r[2]) for r in pre_rows if r[1] == "BID")
    sell_amount = sum(float(r[2]) for r in pre_rows if r[1] == "ASK")
    buy_count   = sum(1           for r in pre_rows if r[1] == "BID")
    total_amt   = buy_amount + sell_amount
    total_cnt   = len(pre_rows)
    price_mean  = float(np.mean(prices))
    price_std   = float(np.std(prices))

    X = np.array([[
        buy_amount / total_amt if total_amt > 0 else 0.5,
        buy_count  / total_cnt if total_cnt > 0 else 0.5,
        (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] else 0.0,
        total_cnt,
        sum(float(r[3]) for r in pre_rows),
        w_amt,
        1 if w_side == "BID" else 0,
        ts.hour,
        price_std / price_mean * 100 if price_mean else 0.0,
    ]])
    return (X, int(seconds_ago), ts.strftime('%H:%M:%S'))


def _confidence_label(prob: float) -> str:
    if prob >= 0.70:
        return "HIGH"
    if prob >= 0.55:
        return "MED"
    return "LOW"


@app.get("/predict/price-after-whale")
def predict_price_after_whale(coin: str = "KRW-BTC"):
    bundle = _load_model()
    feat = _build_prediction_features(coin)
    if feat is None:
        raise HTTPException(status_code=422, detail="예측에 필요한 고래 거래 데이터가 부족합니다.")

    X, seconds_ago, whale_time = feat
    result = {"whale_seconds_ago": seconds_ago, "whale_time": whale_time}
    for tf in ["1m", "5m", "30m"]:
        entry  = bundle[tf]
        model  = entry["model"]
        scaler = entry["scaler"]

        X_input = scaler.transform(X) if scaler is not None else X

        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(X_input)[0]
            pred  = int(np.argmax(proba))
            conf  = float(max(proba)) * 100
        else:
            pred = int(model.predict(X_input)[0])
            conf = 0.0

        result[tf] = {
            "direction":  "UP" if pred == 1 else "DOWN",
            "confidence": round(conf, 1),
            "level":      _confidence_label(conf / 100),
        }

    return result


@app.post("/debug/inject-whale")
async def inject_whale(coin: str = "KRW-BTC", side: str = "BID", amount: float = 2_000_000_000):
    """데모용 고래 거래 주입. 나중에 DELETE FROM trades WHERE sid LIKE 'demo_%' 로 정리."""
    try:
        ts = datetime.now(timezone(timedelta(hours=9)))
        price = get_official_open_price(coin)
        volume = amount / price if price else 0
        sid = -int(ts.timestamp() * 1000)
        change_dir = "RISE" if side == "BID" else "FALL"

        conn = _db(); cur = conn.cursor()
        cur.execute("""
            INSERT INTO trades (timestamp, code, price, volume, side, total_amount, pcp, change, sid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (ts, coin, price, volume, side, amount, price, change_dir, sid))
        trade_id = cur.fetchone()[0]
        conn.commit(); cur.close(); conn.close()

        tick = {
            "type": "tick",
            "price": price,
            "amount": amount,
            "side": side,
            "time": int(ts.timestamp()) + 32400,
            "id": trade_id,
            "open_price": price,
        }
        await manager.broadcast(coin, tick)
        return {"ok": True, "sid": sid, "price": price, "amount": amount, "volume": volume}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 시장 외부 지표 캐시 (5분 TTL) ──
_market_cache: dict = {}
_MARKET_TTL = 300

def _mcache_get(key):
    entry = _market_cache.get(key)
    if entry and time.time() < entry[1]:
        return entry[0]
    return None

def _mcache_set(key, data):
    _market_cache[key] = (data, time.time() + _MARKET_TTL)


@app.get("/market/fear-greed")
def get_fear_greed():
    cached = _mcache_get("fear_greed")
    if cached:
        return cached
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=2", timeout=5).json()
        data_list = res["data"]
        today = data_list[0]
        yesterday = data_list[1] if len(data_list) > 1 else None
        result = {
            "value": int(today["value"]),
            "classification": today["value_classification"],
            "yesterday": int(yesterday["value"]) if yesterday else None,
        }
        _mcache_set("fear_greed", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"공포탐욕 API 오류: {e}")


@app.get("/market/dominance")
def get_dominance():
    cached = _mcache_get("dominance")
    if cached:
        return cached
    try:
        res = requests.get("https://api.coingecko.com/api/v3/global", timeout=5).json()
        mcp = res["data"]["market_cap_percentage"]
        result = {
            "btc": round(mcp.get("btc", 0), 2),
            "eth": round(mcp.get("eth", 0), 2),
            "others": round(100 - mcp.get("btc", 0) - mcp.get("eth", 0), 2),
        }
        _mcache_set("dominance", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"도미넌스 API 오류: {e}")


@app.get("/market/kimchi-premium")
def get_kimchi_premium():
    cached = _mcache_get("kimchi")
    if cached:
        return cached
    try:
        conn = _db(); cur = conn.cursor()
        cur.execute("SELECT price FROM trades WHERE code='KRW-BTC' ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone(); cur.close(); conn.close()
        upbit_price = float(row[0]) if row else None

        binance_res = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5).json()
        btc_usd = float(binance_res["price"])

        rate_res = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=5).json()
        usd_krw = float(rate_res["rates"]["KRW"])

        binance_krw = btc_usd * usd_krw
        premium = round((upbit_price / binance_krw - 1) * 100, 2) if upbit_price else None

        result = {
            "upbit_price": upbit_price,
            "binance_krw": round(binance_krw),
            "usd_krw": round(usd_krw),
            "premium_pct": premium,
        }
        _mcache_set("kimchi", result)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"김치 프리미엄 API 오류: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8081, ws_ping_interval=None)