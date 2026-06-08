# 프로젝트 네이밍 컨벤션 & 구조 가이드

> WhaleScope 프로젝트의 파일명, 폴더명, 코드 내 식별자 작성 규칙을 정의합니다.
> 새 파일·기능을 추가할 때 이 문서를 기준으로 통일합니다.

---

## 1. 폴더 구조

### 현재 구조

```
whale-project/
├── backend/          # FastAPI 서버 (API 엔드포인트, WebSocket, 인증, AI 서빙)
├── frontend/         # 단일 HTML/CSS/JS 앱 (SPA)
├── collector/        # 업비트 WebSocket 수집기 (AWS EC2)
├── analyzer/         # 피처 엔지니어링 및 ML 모델 학습
├── data/             # PostgreSQL 볼륨 및 학습 데이터 (Git 제외)
├── docs/             # 기술 문서, 다이어그램, 목업
├── tests/            # 단위·통합 테스트
└── models/           # 학습된 ML 모델 파일 (.pkl)
```

---

## 2. 파일 네이밍 규칙

### Python (`.py`)

- **규칙**: `snake_case` (소문자 + 언더스코어)
- 역할이 명확하게 드러나는 이름 사용. 폴더명과 중복 금지.

```
✅ collector_aws.py        ← 역할 명시
✅ feature_engineering.py
✅ server_optimized.py
✅ train_model.py

❌ main.py                 ← 역할 불명확
❌ analyzer.py             ← 폴더명(analyzer/)과 중복
```

### HTML / CSS / JS (`.html`, `.css`, `.js`)

- **규칙**: `kebab-case` (소문자 + 하이픈)

```
✅ index.html
✅ whale-chart.js
✅ main-style.css

❌ whaleChart.js
❌ MainStyle.css
```

### 설정·문서 파일

- **규칙**: `kebab-case` + 소문자 확장자

```
✅ docker-compose.yml
✅ tech-stack.md
✅ api-spec.md
✅ .env, .gitignore

❌ TechStack.txt        ← PascalCase 금지
❌ AgileProcess_6팀.xlsx ← 한글 파일명은 docs/ 내에서만 허용
```

### PEM / 키 파일

- **규칙**: `kebab-case`, 특수문자 금지, `.gitignore`에 반드시 등록

```
✅ whale-collector-key.pem
❌ Whale-Collector(KEY).pem   ← 대문자, 괄호 금지
```

---

## 3. Python 코드 내부 규칙

| 대상                | 규칙                        | 예시                               |
| ------------------- | --------------------------- | ---------------------------------- |
| 변수                | `snake_case`                | `open_price`, `trade_id`           |
| 함수                | `snake_case`                | `get_daily_whale_log()`            |
| 클래스              | `PascalCase`                | `UserRegister`, `TradeEvent`       |
| 상수                | `SCREAMING_SNAKE_CASE`      | `DB_CONFIG`, `WHALE_THRESHOLD`, `KST`  |
| Private 함수/변수   | `_leading_underscore`       | `_db()`, `_hash()`, `_verify()`    |
| FastAPI 라우터 함수 | `snake_case` + 동사 or 명사 | `get_hourly_whale()`, `register()` |

```python
# ✅ 올바른 예시
DB_CONFIG = {"host": "localhost"}         # 상수
KST = timezone(timedelta(hours=9))        # 상수

class UserRegister(BaseModel):            # PascalCase
    username: str

def _verify(plain: str, hashed: str):    # private 함수
    ...

def get_daily_whale_log(coin: str):       # public 함수 (동사+명사)
    open_price = 0                        # snake_case 변수
```

---

## 4. JavaScript 코드 내부 규칙

| 대상           | 규칙                    | 예시                                |
| -------------- | ----------------------- | ----------------------------------- |
| 변수           | `camelCase`             | `openPrice`, `exchangeRate`         |
| 함수           | `camelCase` + 동사 시작 | `showPage()`, `loadWhaleAnalysis()` |
| 상수           | `SCREAMING_SNAKE_CASE`  | `API_BASE`                          |
| 클래스 생성자  | `PascalCase`            | `LightweightCharts`                 |
| 전역 상태 변수 | `camelCase`             | `whaleHourlyData`, `wsStarted`      |

```javascript
// ✅ 올바른 예시
const API_BASE = 'http://localhost:8001';    // 상수

let whaleLogExpanded = false;               // 상태 변수 (camelCase)
let whaleHourlyData  = [];

function loadWhaleAnalysis() { ... }        // 동사로 시작
function renderHourlyChart(data) { ... }    // render + 명사
function toggleWhaleLog() { ... }           // toggle + 명사
```

---

## 5. HTML ID / CSS 클래스 규칙

| 대상                  | 규칙                          | 예시                                        |
| --------------------- | ----------------------------- | ------------------------------------------- |
| HTML ID               | `snake_case`                  | `page_whale`, `log_body`, `nav_whale_btn`   |
| CSS 클래스            | `kebab-case`                  | `log-section`, `hour-col`, `nav-link`       |
| JS에서 getElementById | ID는 `snake_case` 그대로 사용 | `document.getElementById('whale_log_body')` |

```html
<!-- ✅ 올바른 예시 -->
<div id="page_whale" class="log-section hour-col">
  <button id="nav_whale_btn" class="nav-link">고래 분석</button>
</div>

<!-- ❌ 금지 -->
<div id="pageWhale" ...>
  <!-- ID에 camelCase 금지 -->
  <div class="logSection"><!-- 클래스에 camelCase 금지 --></div>
</div>
```

---

## 6. API 엔드포인트 규칙

- **규칙**: 소문자 `kebab-case`, 명사 중심, 계층 구조 반영

```
✅ GET  /whale/hourly/{coin}
✅ GET  /whale/dates/{coin}
✅ GET  /whale/daily-log/{coin}/{date}
✅ POST /auth/login
✅ POST /auth/register
✅ GET  /auth/me
✅ GET  /daily/{coin}

규칙 요약:
- 동사 금지: /getWhaleData ❌  →  /whale/hourly ✅
- 복수형: 목록 반환 시 복수 (/dates, /trades)
- 그룹 prefix: /whale/*, /auth/*
```

---

## 7. Git 브랜치 & 커밋 메시지 규칙

### 브랜치명

```
feature/backlog-8-hourly-chart    # 새 기능
fix/whale-page-scroll             # 버그 수정
docs/add-conventions              # 문서 작업
refactor/server-cleanup           # 리팩토링
```

### 커밋 메시지

- **언어**: 한글 또는 영어 중 하나로 통일 (현재 혼용 → 한글 권장)
- **형식**: `타입: 내용 (50자 이내)`

| 타입       | 사용 시                         |
| ---------- | ------------------------------- |
| `feat`     | 새 기능 추가                    |
| `fix`      | 버그 수정                       |
| `docs`     | 문서 수정                       |
| `refactor` | 코드 구조 개선 (기능 변화 없음) |
| `style`    | 포맷팅, 들여쓰기 등             |
| `test`     | 테스트 코드 추가·수정           |
| `chore`    | 빌드 설정, 패키지 관리          |

```bash
# ✅ 올바른 예시
feat: 시간대별 고래 활동 통계 차트 추가 (백로그 8)
fix: 고래 분석 페이지 스크롤 불가 문제 수정
docs: 네이밍 컨벤션 문서 작성
refactor: WebSocket 재연결 로직 분리

# ❌ 금지
Feat: 실시간 데이터 수집    ← 대문자 시작 혼용
update stuff               ← 내용 불명확
```

---

## 8. 파일명 변경 이력

| 이전                         | 이후                            | 비고    |
| ---------------------------- | ------------------------------- | ------- |
| `collector/main_aws.py`      | `collector/collector_aws.py`    | ✅ 완료 |
| `tech-stack-description.txt` | `docs/tech-stack.md`            | ✅ 완료 |
| `tech-stack-diagram.html`    | `docs/tech-stack-diagram.html`  | ✅ 완료 |
| `AgileProcess_6팀.xlsx`      | `docs/AgileProcess_6팀.xlsx`    | ✅ 완료 |
| `Whale-Collector(KEY).pem`   | `whale-collector-key.pem`       | ✅ 완료 |
| `backend/server.py`          | `backend/server_legacy.py`      | ✅ 완료 |
| `frontend/index.html`        | `frontend/index_legacy.html`    | ✅ 완료 |
