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

### 1. 백엔드 서버 실행

먼저 필요한 라이브러리를 설치한 후 서버를 구동합니다.

```bash
pip install fastapi uvicorn psycopg2 requests
cd backend
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```
