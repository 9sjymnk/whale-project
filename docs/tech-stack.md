# 기술 스택 설명

## ① Upbit Exchange

외부 데이터 소스로, WebSocket 프로토콜로 실시간 데이터를 수신하고 REST API로 기준가를 보정합니다.

---

## ② Collector 레이어

**Backend (로컬)**
Python `asyncio` + `websockets` 라이브러리로 업비트에 비동기 WebSocket 연결을 유지합니다.
체결 데이터를 받는 즉시 PostgreSQL에 저장하면서 동시에 프론트엔드로 스트리밍합니다.
대시보드가 실시간으로 동작하는 핵심 경로입니다.

**Collector (AWS EC2)**
동일하게 Python `asyncio` + `websockets`로 수신하되, `kafka-python` 라이브러리의 Producer를 사용해
Kafka 토픽에 데이터를 발행합니다. AWS EC2에서 24시간 독립적으로 실행되며,
대시보드와 무관하게 분석용 데이터를 꾸준히 쌓는 파이프라인입니다.

---

## ③ 로컬 인프라 (Docker Compose)

**PostgreSQL**
`psycopg2` 라이브러리로 Python에서 연결하며, 로컬 Docker 컨테이너로 운영합니다.

**Kafka (Docker Compose)**
Apache Kafka + Zookeeper를 Docker Compose로 로컬에서 구동합니다.
Kafka는 메시지 브로커 역할로 EC2의 수집기(Producer)와 향후 Consumer를 느슨하게 연결하는 구조입니다.
Kafka UI(Port 8081)로 토픽과 메시지를 웹 브라우저에서 모니터링할 수 있습니다.
현재는 Producer만 구현된 상태이며, Sprint 5에서 `feature_engineering.py`가
Kafka Consumer 역할을 맡아 피처를 추출한 뒤 PostgreSQL에 저장할 예정입니다.

---

## ④ FastAPI Server

FastAPI 프레임워크의 WebSocket 기능으로 실시간 스트리밍을 구현했고,
`psycopg2`로 PostgreSQL과 연결합니다. DB 접속 정보는 `python-dotenv`로 환경 변수로 관리합니다.

---

## ⑤ Dashboard

Vanilla JS로 구현했고 금융 차트는 TradingView 오픈소스인 Lightweight Charts를 사용했습니다.
백엔드와 WebSocket으로 연결해 실시간 데이터를 받아 화면에 렌더링합니다.
