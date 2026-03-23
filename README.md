# 🐳 실시간 가상자산 고래 탐지 시스템 (Kafka-based)

Upbit WebSocket을 통해 실시간 거래 데이터를 수집하고, Apache Kafka를 거쳐 이상 거래(고래)를 탐지 및 분석하는 파이프라인입니다.

## 🛠 Tech Stack

- **Language**: Python 3.12
- **Message Broker**: Apache Kafka (Docker)
- **Database**: PostgreSQL
- **Key Libraries**: `kafka-python`, `websockets`, `psycopg2`, `nest_asyncio`

## 🚀 주요 업데이트 및 특징 (v1.2)

1. **실시간 타임라인 동기화**
   - 수집기(Producer)와 분석기(Consumer) 양측에 밀리초(ms) 단위 타임스탬프를 적용하여 데이터 흐름을 실시간으로 추적합니다.
2. **거래 방향 시각화 (Buy/Sell)**
   - 업비트 체결 데이터를 분석하여 `매도(ASK) 🔴`와 `매수(BID) 🔵`를 직관적으로 구분하여 출력합니다.
3. **고속 데이터 파이프라인 최적화**
   - `producer.flush()` 및 `group_id` 동적 생성을 통해 지연 시간(Latency)을 최소화하고 뭉텅이 현상을 방지했습니다.
4. **Graceful Shutdown (안전한 종료)**
   - `KeyboardInterrupt` 예외 처리를 통해 종료 시 에러 메시지(Traceback) 없이 깔끔하게 프로세스를 마감합니다.

## 🏃 실행 방법

1. **Infrastructure**: `docker-compose up -d` (Kafka, DB 가동)
2. **Collector**: `python main.py` 실행 (데이터 수집 시작)
3. **Analyzer**: `python analyzer.py` 실행 (실시간 분석 및 DB 저장)
