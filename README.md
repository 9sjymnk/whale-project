# 🐋 WhaleScope

고래(대량 거래) 탐지 기반 암호화폐 가격 예측 플랫폼입니다.
업비트 실시간 체결 데이터를 수집·분석하고, AI 모델로 가격 방향을 예측합니다.

## 🚀 주요 기능

- **실시간 대시보드**: 고래 거래 감지 시 즉각 알림 및 차트 마커 표시
- **고래 분석**: 시간대별·날짜별 고래 활동 통계 시각화
- **AI 가격 예측**: 고래 거래 발생 후 1분·5분·30분 방향 예측 (신뢰도 HIGH/MED/LOW)
- **백테스팅**: AI 예측 vs 실제 결과 정확도 검증
- **신호 신뢰도**: 시간대·조건별 예측 신호 신뢰도 분석
- **Slack 알림**: 고래 거래 발생 시 Webhook으로 즉시 알림

## 🛠 Tech Stack

- **Backend**: Python 3, FastAPI, Uvicorn, psycopg2, python-jose, bcrypt, python-dotenv
- **AI/ML**: XGBoost, scikit-learn, numpy, pandas
- **Frontend**: Vanilla JS, Lightweight Charts (TradingView)
- **Database**: PostgreSQL 15 (로컬 Docker)
- **Infra**: AWS EC2 (수집기), Docker Compose (PostgreSQL)
- **API**: Upbit Open API

## 💻 실행 방법

### 1. 의존성 설치

```bash
pip install fastapi uvicorn psycopg2 requests python-jose bcrypt python-dotenv xgboost scikit-learn numpy pandas
```

### 2. 백엔드 서버 실행

```bash
cd backend
python server_optimized.py
```

### 3. AI 예측 모델 학습 (최초 1회)

```bash
# 피처 데이터 생성 (DB → data/features.csv)
cd analyzer
python feature_engineering.py

# 모델 학습 및 저장 (models/model.pkl)
python train_model.py
```

### 4. 프론트엔드 실행

`frontend/index_optimized.html` 파일을 브라우저에서 열거나 라이브 서버로 실행합니다.

---

## ⚡ AWS EC2 성능 설정 (CPU 크레딧 무제한)

T2/T3 같은 버스터블 인스턴스는 CPU 크레딧이 소진되면 성능이 기준치(20~40%)로 **자동 스로틀링**됩니다.

**설정 방법 (AWS 콘솔)**

> EC2 → 인스턴스 선택 → 작업 → 인스턴스 설정 → **크레딧 사양 변경 → 무제한 체크**

---

## 📐 네이밍 컨벤션 & 프로젝트 구조

파일명, 폴더명, 변수명, API 엔드포인트 등 코드 작성 규칙은 아래 문서를 참고하세요.

→ **[CONVENTIONS.md](./CONVENTIONS.md)**
