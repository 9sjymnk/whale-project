# 🐳 Whale Watcher Intelligence Pro (V63)

실시간 업비트 데이터를 기반으로 고래(대량 거래)의 움직임을 추적하고 시각화하는 대시보드입니다.
본 프로젝트는 졸업 작품용으로 제작되었으며, 실시간 기준가 동기화 및 전 시간대 반응형 차트를 지원합니다.

## 🚀 주요 기능

- **실시간 고래 추적**: 1억 원 이상 거래 시 즉각적인 토스트 알림 및 차트 마커 표시
- **업비트 공식 동기화**: 매일 아침 09:00(KST) 기준가 자동 갱신 및 등락률 계산
- **멀티 타임프레임**: 1초/1분/30분/1시간 단위 라인 차트 지원
- **전문가용 UI**: Streamlit 스타일의 블랙 테마 지표 카드 및 정밀 툴팁

## 🛠 Tech Stack

- **Backend**: Python 3.x, FastAPI, Uvicorn, Psycopg2
- **Frontend**: Vanilla JS, Lightweight Charts (by TradingView)
- **Database**: PostgreSQL (AWS RDS)
- **API**: Upbit Open API

## 💻 실행 방법 (How to Run)

### 1. 의존성 설치

```bash
pip install fastapi uvicorn psycopg2 requests python-jose bcrypt python-dotenv xgboost scikit-learn numpy pandas
```

### 2. 백엔드 서버 실행

```bash
cd backend
python server.py
```

### 3. AI 예측 모델 학습 (최초 1회)

```bash
# 특성 데이터 생성 (DB → data/features.csv)
cd analyzer
python feature_engineering.py

# 모델 학습 및 저장 (models/model.pkl)
python train_model.py
```

### 4. 프론트엔드 실행

`frontend/index.html` 파일을 브라우저에서 열거나 라이브 서버로 실행합니다.

---

## 🎬 데모 비교 실행 (연결 속도 최적화 전/후)

터미널 2개를 열어 기존 버전과 최적화 버전을 동시에 실행합니다.

```bash
# 터미널 1 — 기존 버전 (포트 8000)
cd backend
python server.py

# 터미널 2 — 최적화 버전 (포트 8081)
cd backend
python server_optimized.py
```

브라우저 탭 2개를 열어 나란히 비교합니다.

| 탭 | URL | 버전 |
|---|---|---|
| 탭 1 | `frontend/index.html` | 기존 (포트 8000) |
| 탭 2 | `frontend/index_optimized.html` | 최적화 (포트 8081) |

**비교 수치**

| 항목 | 기존 | 최적화 |
|---|---|---|
| 조회 행수 | 163만 행 (전체) | 11만 행 (최근 24h) |
| 초기 연결 대기 | 약 8초 | 약 0.7초 |
| 개선 방법 | — | 24h 범위 제한 + `(code, timestamp)` 복합 인덱스 |

---

## 📐 네이밍 컨벤션 & 프로젝트 구조

파일명, 폴더명, 변수명, API 엔드포인트 등 코드 작성 규칙은 아래 문서를 참고하세요.

→ **[CONVENTIONS.md](./CONVENTIONS.md)**
