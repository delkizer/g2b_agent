# 나라장터 마켓 인텔리전스

나라장터(G2B) 공공조달 공고를 자동 수집·분석하여 SPOTV가 입찰 가능한 사업을 식별하는 마켓 인텔리전스 플랫폼.

## 아키텍처

```
[로컬 WSL — 수집 에이전트]                    [AWS EC2 — 웹 서비스]
┌─────────────────────────────┐         ┌─────────────────────────────────┐
│  Collector                  │         │  FastAPI Server                 │
│  ├── 나라장터 API 수집       │         │  ├── REST API (공고 CRUD)        │
│  ├── APScheduler (크론)     │         │  ├── PostgreSQL                 │
│  └── 키워드 1차 필터링       │         │  ├── Notion 연동                 │
│                             │         │  └── 인증 (API Key)              │
│  Analyzer                   │  HTTP   │                                 │
│  ├── Claude API 분석/분류    │ ──────→ │  Vue.js 3 Frontend              │
│  ├── SPOTV 적합성 평가       │  결과   │  ├── 대시보드                    │
│  └── 분석 결과 구조화        │  전송   │  ├── 필터/검색                   │
│                             │         │  └── Tailwind CSS               │
└─────────────────────────────┘         └─────────────────────────────────┘
```

## 기술 스택

| 영역 | 기술 |
|------|------|
| 수집 에이전트 | Python 3.11, APScheduler, httpx |
| LLM 분석 | Claude API (Anthropic) |
| 웹 서버 | Python 3.11, FastAPI, SQLAlchemy, PostgreSQL |
| 프론트엔드 | Vue.js 3, TypeScript, Tailwind CSS, Vite |
| 연동 | Notion API |
| 인프라 | 로컬 WSL (에이전트), AWS EC2 (서버) |

## 프로젝트 구조

```
nara-market/
├── agent/                # 로컬 수집 에이전트 (Python)
│   ├── config/           # 에이전트 설정
│   ├── collector/        # 나라장터 API 수집 + 키워드 필터
│   ├── analyzer/         # Claude API 분석 + EC2 전송
│   └── prompts/          # 프롬프트 템플릿 (.md)
├── server/               # EC2 웹서비스 (FastAPI)
│   ├── apps/             # API 라우터
│   ├── services/         # 비즈니스 로직
│   ├── models/           # SQLAlchemy 모델
│   └── database/         # DB 연결
├── frontend/             # Vue.js 3 대시보드
│   └── src/
├── shared/               # 공유 스키마 정의
├── docs/                 # 설계 문서
└── scripts/              # 유틸리티 스크립트
```

## 시작하기

### 사전 요구사항

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- 공공데이터포털 API 키 ([data.go.kr](https://data.go.kr))
- Claude API 키 ([console.anthropic.com](https://console.anthropic.com))

### 에이전트 (로컬 WSL)

```bash
cd agent
cp .env.example .env
# .env 파일에 API 키 설정

pip install -r requirements.txt
python main.py
```

### 서버 (AWS EC2)

```bash
cd server
cp .env.example .env
# .env 파일에 DB, Notion 설정

pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

## 환경변수

### Agent

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `G2B_API_KEY` | 공공데이터포털 API 키 | (필수) |
| `CLAUDE_API_KEY` | Claude API 키 | (필수) |
| `CLAUDE_MODEL` | Claude 모델명 | `claude-sonnet-4-20250514` |
| `SCHEDULE_INTERVAL` | 수집 주기 (분) | `60` |
| `EC2_API_URL` | EC2 웹서비스 URL | `http://localhost:8000` |
| `EC2_API_KEY` | EC2 내부 API 키 | (필수) |

### Server

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql://localhost:5432/nara_market` |
| `INTERNAL_API_KEY` | 에이전트 인증용 API 키 | (필수) |
| `NOTION_API_KEY` | Notion Integration 토큰 | (필수) |
| `NOTION_DATABASE_ID` | Notion 데이터베이스 ID | (필수) |
| `NOTION_MIN_SCORE` | Notion 등록 최소 점수 | `60` |

## 데이터 흐름

1. **수집**: APScheduler 크론 → 나라장터 API 호출 → 원본 공고 수집
2. **필터링**: 키워드 1차 필터 (스포츠, 데이터, AI, 영상, 분석, 플랫폼)
3. **분석**: Claude API → 카테고리 분류, 적합성 점수(0-100), 사업 요약
4. **전송**: 분석 결과를 EC2 REST API로 일괄 전송
5. **저장**: PostgreSQL 저장 + Notion 자동 등록 (점수 60+)
6. **조회**: Vue.js 대시보드에서 필터/검색/리포트

## 적합성 점수 기준

| 점수 | 의미 | 표시 |
|------|------|------|
| 80-100 | 매우 적합 (즉시 검토) | ������ |
| 60-79 | 적합 가능 (검토 필요) | ������ |
| 40-59 | 부분 관련 | ������ |
| 0-39 | 관련도 낮음 | ⚪ |

## 설계 문서

상세 설계는 `docs/` 디렉토리를 참조하세요.

| 도메인 | 문서 |
|--------|------|
| 전체 | [CLAUDE.md](CLAUDE.md) |
| 수집 | [docs/collector/01-collector-overview.md](docs/collector/01-collector-overview.md) |
| 분석 | [docs/analyzer/01-analyzer-overview.md](docs/analyzer/01-analyzer-overview.md) |
| 서버 | [docs/server/01-server-overview.md](docs/server/01-server-overview.md) |
| 프론트엔드 | [docs/frontend/01-frontend-overview.md](docs/frontend/01-frontend-overview.md) |
| 설정 | [docs/config/01-config-overview.md](docs/config/01-config-overview.md) |
| 스키마 | [docs/shared/01-data-schema.md](docs/shared/01-data-schema.md) |

## 라이선스

Private — SPOTV 내부 프로젝트


