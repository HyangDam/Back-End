# HyangDam Back-End

> 향을 직접 맡아보기 어려운 온라인 환경에서, 입문자가 자신의 취향에 맞는 향수 후보를 더 쉽게 좁힐 수 있도록 돕는 향수 추천 서비스 **향담**의 백엔드입니다.

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway&logoColor=white)](https://railway.app/)

| Service | URL |
| --- | --- |
| Frontend | [hyangdam.vercel.app](https://hyangdam.vercel.app/) |
| API | [hyangdam.up.railway.app](https://hyangdam.up.railway.app/) |
| Swagger | [API Docs](https://hyangdam.up.railway.app/docs) |
| Health Check | [`/api/v1/health`](https://hyangdam.up.railway.app/api/v1/health) |

## About HyangDam

향수는 시향 전에는 향을 정확히 판단하기 어렵고, 입문자에게는 수많은 제품과 낯선 향조가 선택의 장벽이 됩니다. 향담은 사용자의 상황, 원하는 분위기, 선호·회피 향조를 구조화해 **비슷한 향수 목록이 아닌, 지금의 사용자에게 맞는 후보군**을 제안합니다.

- 온보딩 선택과 자연어 채팅 모두에서 취향을 추출합니다.
- 노트·설명·브랜드 텍스트를 기반으로 향수와 사용자 취향의 유사도를 계산합니다.
- 중점 향조는 가중하고, 피하고 싶은 향조는 감점합니다.
- 추천 결과에는 일치도와 추천 근거를 함께 제공해 결과를 이해할 수 있게 합니다.

## Architecture

```mermaid
flowchart LR
    U[User / Frontend] -->|REST API| F[FastAPI]
    F --> A[JWT & Social Login]
    F --> O[Onboarding & Profile]
    F --> C[Chat Preference Analyzer]
    C --> R[TF-IDF Recommendation Engine]
    O --> R
    R --> D[(MySQL)]
    F --> D
    F --> P[Perfume Search / Detail / Interaction]
    C -. optional .-> L[OpenAI API]
    F --> RW[Railway]
```

## Recommendation Pipeline

```text
Kaggle perfume data + Korean-market perfume data
                |
                v
Notes / description / brand normalization and Korean localization
                |
                v
User onboarding or natural-language preference input
                |
                v
TF-IDF vectorization + cosine similarity
                |
                v
Focus-note weighting and avoid-note penalty
                |
                v
Top-N perfumes + match level and recommendation reasons
```

### Scoring

향수 `p`의 기본 점수는 노트, 설명, 브랜드 텍스트의 코사인 유사도를 결합해 계산합니다.

```math
BaseScore(p) = 0.70 \cdot cos(U_N, P_N)
             + 0.25 \cdot cos(U_D, P_D)
             + 0.05 \cdot cos(U_B, P_B)
```

중점 향조를 선택한 경우 해당 취향을 추가 반영하고, 회피 향조가 포함되면 감점합니다.

```math
FinalScore(p) = 0.70 \cdot BaseScore(p)
              + 0.30 \cdot FocusScore(p)
              - 0.10 \cdot AvoidPenalty(p)
```

## Key Features

### Personalized recommendation

- 온보딩 카테고리 기반 추천: 상황, 무드, 향 계열, 회피·중점 향조를 조합합니다.
- 자연어 기반 추천: 예를 들어 `취준생이라 무난하고 깔끔하면서 조금은 달달한 향을 원해` 같은 요청을 `clean`, `school_work`, `sweet` 취향으로 분석합니다.
- LLM 분석을 선택적으로 사용하며, 키가 없거나 호출에 실패해도 규칙·TF-IDF 분석으로 추천을 이어갑니다.
- `recommendation_match`를 통해 `높음/중간/낮음` 일치도와 최대 세 개의 추천 근거를 전달합니다.

### Perfume discovery

- 키워드, 브랜드, 노트, 카테고리로 향수를 검색합니다.
- 공백과 대소문자 차이를 정규화해 `미스디올`, `입생 로랑`, `BY REDO`처럼 입력해도 검색할 수 있습니다.
- 인기순, 금주 인기순, 이름순, 최신순, 가격순 정렬과 페이지네이션을 제공합니다.
- 향수 상세에서 한국어 표시명·노트, 메인 어코드, 노트 피라미드, 좋아요·보유·리뷰 상태를 제공합니다.
- 가격 데이터가 없는 제품도 네이버 쇼핑 검색 및 공식 판매처 링크를 제공합니다.

### User experience

- 카카오 인가 코드 및 구글 액세스 토큰 기반 소셜 로그인
- Access Token / Refresh Token 기반 인증 및 로그아웃
- 프로필·온보딩 저장과 수정
- 관심 향수 좋아요, 나의 향수장, 보유 향수 기반 리뷰 작성·수정·삭제

## API Map

인증이 필요한 API는 `Authorization: Bearer <access_token>` 헤더를 사용합니다. 전체 스키마와 예시 요청은 [Swagger](https://hyangdam.up.railway.app/docs)에서 확인할 수 있습니다.

| Domain | Endpoint | Description | Auth |
| --- | --- | --- | --- |
| Health | `GET /api/v1/health` | 서버 상태 확인 | No |
| Categories | `GET /api/v1/categories` | 온보딩·무드 선택지 조회 | No |
| Recommendation | `POST /api/v1/recommendations` | 선택 카테고리 기반 추천 | No |
| Recommendation | `POST /api/v1/recommendations/text` | 자연어 취향 기반 추천 | No |
| Chat | `POST /api/v1/chat/recommend` | LLM/규칙 분석 기반 챗봇 추천 | No |
| Search | `GET /api/v1/perfumes/search` | 향수 검색, 필터, 정렬 | No |
| Perfume | `GET /api/v1/perfumes/{perfume_id}` | 향수 상세 및 노트 시각화 데이터 | Optional |
| Price | `GET /api/v1/perfumes/{perfume_id}/price-comparison` | 가격 비교 링크·수집 가격 조회 | No |
| Auth | `POST /api/v1/auth/social-login` | 카카오·구글 소셜 로그인 | No |
| Auth | `POST /api/v1/auth/refresh` | Access Token 재발급 | No |
| Auth | `POST /api/v1/auth/logout` | Refresh Token 폐기 | Yes |
| User | `POST /api/v1/users/me/profile` | 기본 프로필 입력 | Yes |
| User | `GET/PATCH /api/v1/users/me` | 내 프로필 조회·수정 | Yes |
| Onboarding | `POST /api/v1/onboarding/preferences` | 온보딩 취향 저장 | Yes |
| Onboarding | `GET /api/v1/onboarding/me`, `PATCH /api/v1/onboarding/preferences` | 내 온보딩 취향 조회·수정 | Yes |
| Like | `POST/DELETE /api/v1/perfumes/{perfume_id}/likes` | 좋아요 등록·취소 | Yes |
| Collection | `GET/POST /api/v1/users/me/perfumes` | 나의 향수장 조회·추가 | Yes |
| Review | `GET/POST /api/v1/perfumes/{perfume_id}/reviews` | 리뷰 목록·작성 | Mixed |

### Search example

```http
GET /api/v1/perfumes/search?keyword=미스디올&category=floral&sort=popular&page=1&size=20
```

`sort` supports `popular`, `weekly_popular`, `name`, `latest`, `price_asc`, and `price_desc`.

### Chat recommendation example

```json
POST /api/v1/chat/recommend
{
  "message": "나는 취준생이야. 무난하고 깔끔하면서 조금은 달달한 향을 원해",
  "top_n": 5
}
```

```json
{
  "assistant_message": "깨끗하고 부담 없는 향수를 추천했어요.",
  "analysis_source": "rule_tfidf",
  "preferences": {
    "selected_categories": ["clean", "school_work", "sweet"],
    "avoid_categories": ["spicy"],
    "focus_categories": ["school_work"]
  },
  "results": [
    {
      "perfume_id": 1,
      "display_name": "...",
      "recommendation_match": {
        "level": "high",
        "label": "취향과 잘 맞아요",
        "reasons": ["...", "..."]
      }
    }
  ]
}
```

## Data

| Dataset / data | Usage |
| --- | --- |
| Kaggle perfume dataset | 기본 향수명, 브랜드, 노트, 설명 기반 추천 카탈로그 |
| Korean market catalog | 국내 사용자가 실제로 찾는 브랜드·향수 보강 |
| Korean localization files | 향수명, 브랜드명, 설명, 노트의 한국어 표시값 제공 |
| Market metadata / offers | 출시일, 가격 정렬, 공식 판매처·검색 링크 제공 |

노트는 표기 차이와 언어 차이를 줄이기 위해 정규화합니다. 예를 들어 `Sandal Wood`, `sandalwood`처럼 표기가 달라도 같은 노트로 처리하며, 상세 화면용으로는 한국어 표시값을 별도로 제공합니다.

## Tech Stack

| Area | Technologies |
| --- | --- |
| API | Python, FastAPI, Pydantic |
| Database | MySQL, SQLAlchemy, PyMySQL |
| Recommendation | pandas, scikit-learn, TF-IDF, cosine similarity |
| AI | OpenAI Responses API, rule-based fallback |
| Authentication | JWT, Kakao OAuth, Google OAuth |
| Deployment | Railway, Uvicorn |

## Local Setup

### 1. Install dependencies

```bash
git clone https://github.com/HyangDam/Back-End.git
cd Back-End

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

At minimum, set a valid MySQL `DATABASE_URL` and JWT secret values in `.env`.

```env
DATABASE_URL=mysql+pymysql://USER:PASSWORD@HOST:PORT/DATABASE
JWT_SECRET_KEY=replace-with-a-long-random-secret-key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=14
```

For social login and chat analysis, configure the following values as needed. Never commit real keys.

```env
KAKAO_REST_API_KEY=...
KAKAO_CLIENT_SECRET=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna
LLM_ENABLED=true
```

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to test the API interactively.

## Deployment

The API is deployed on Railway. The repository includes `railway.json` and `Procfile` with the production start command below.

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Set `DATABASE_URL` to Railway MySQL's private URL reference in Railway Variables, then configure JWT, Kakao, and OpenAI environment variables. Railway deploys the latest pushed `main` branch automatically when the GitHub integration is connected.

## Project Structure

```text
app/
├── core/                 # JWT security and chat rate limiting
├── data/                 # perfume catalog, Korean localization, market metadata
├── models/               # SQLAlchemy database models
├── routers/              # auth, user, onboarding, perfume APIs
├── schemas/              # request and response validation models
├── services/             # recommendation, search, note visualization, chat analysis
├── scripts/              # data preparation and translation utilities
├── database.py           # database session and engine configuration
└── main.py               # FastAPI application and recommendation endpoints
```

## Backend Contribution

| 최지원 · Backend Lead |
| :---: |
| [@lovekukwithhan](https://github.com/lovekukwithhan) |
| 사용자 취향을 향수 추천으로 연결하는 백엔드 전반을 설계·구현했습니다.<br/>FastAPI·MySQL 기반 API와 소셜 인증, 온보딩·향수 상호작용 기능을 구축하고,<br/>TF-IDF·코사인 유사도 기반 추천 엔진 및 한국어 향수 데이터 보강·배포 환경을 담당했습니다. |

---

<p align="center">Made for perfume beginners by HyangDam</p>
