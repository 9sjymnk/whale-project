# 🐳 실시간 가상화폐 이상 징후 탐지 시스템 (Whale Detector)

카프카(Kafka)를 활용하여 업비트(Upbit)의 실시간 거래 데이터를 수집하고, 1억 원 이상의 대형 거래(고래)를 탐지하여 데이터베이스에 저장하는 프로젝트입니다.

## 🛠️ Tech Stack

- **Language:** Python 3.12
- **Message Broker:** Apache Kafka (Confluent 7.5.0)
- **Database:** PostgreSQL 15
- **Container:** Docker, Docker Compose
- **Library:** `kafka-python`, `psycopg2-binary`, `requests`

## 🏗️ System Architecture

1. **Producer (`main.py`)**: 업비트 WebSocket/Rest API를 통해 실시간 체결 데이터를 수집하여 Kafka Topic(`upbit-trades`)으로 전송합니다.
2. **Kafka**: 분산 메시지 브로커로서 대량의 데이터를 안정적으로 중계합니다.
3. **Consumer (`analyzer.py`)**: Kafka에서 데이터를 소비(Consume)하여 실시간으로 고래 거래를 탐지하고 PostgreSQL에 저장합니다.

## 🚀 How to Run

### 1. 인프라 실행 (Docker)

```bash
docker-compose up -d
```

### 2. 수집기 및 분석기 실행

# 터미널 1 (수집기)

python collector/main.py

# 터미널 2 (분석기)

python collector/analyzer.py
