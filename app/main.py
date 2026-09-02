from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import Base, SessionLocal, engine
from app.models import auth
from app.models import onboarding
from app.models import perfume
from app.models import user
from app.routers import auth as auth_router
from app.routers import onboarding as onboarding_router
from app.routers import users
from app.services.preference_extractor import extract_preferences_from_text
from app.services.recommender import AVOID_KEYWORDS, CATEGORY_KEYWORDS, PerfumeRecommender
from app.routers import perfumes
from app.models import perfume_interaction
from app.routers import perfume_interactions
from app.services.perfume_catalog import seed_perfumes_from_csv

app = FastAPI(
    title="HyangDam API",
    description="HyangDam perfume recommendation backend",
    version="0.1.0",
)

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    seed_perfumes_from_csv(db)

app.include_router(users.router)
app.include_router(onboarding_router.router)
app.include_router(perfumes.router)
app.include_router(perfume_interactions.router)
app.include_router(auth_router.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://front-end-psi-ashen.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

recommender = PerfumeRecommender()


class RecommendationRequest(BaseModel):
    selected_categories: list[str]
    avoid_categories: list[str] = Field(default_factory=list)
    focus_categories: list[str] = Field(default_factory=list)
    top_n: int = Field(default=5, ge=1, le=20)


class TextPreferenceRequest(BaseModel):
    text: str = Field(..., min_length=1)


class TextRecommendationRequest(TextPreferenceRequest):
    top_n: int = Field(default=5, ge=1, le=20)


CATEGORY_GROUPS: dict[str, list[dict[str, Any]]] = {
    "situation": [
        {"id": "date", "label": "데이트/약속", "sub_label": "달달하고 부드러운 향"},
        {"id": "school_work", "label": "학교/출근", "sub_label": "부담 없는 데일리 향"},
        {"id": "summer", "label": "여름/산뜻함", "sub_label": "가볍고 시원한 향"},
        {"id": "winter", "label": "겨울/포근함", "sub_label": "따뜻하고 안정적인 향"},
    ],
    "mood": [
        {"id": "clean", "label": "깨끗한 느낌", "sub_label": "비누, 머스크, 파우더"},
        {"id": "sweet", "label": "달달한 느낌", "sub_label": "바닐라, 과일, 디저트"},
        {"id": "elegant", "label": "우아한 느낌", "sub_label": "격식 있고 차분한 향"},
    ],
        "note_family": [
        {"id": "floral", "label": "플로럴", "sub_label": "장미, 자스민, 튜베로즈"},
        {"id": "woody", "label": "우디", "sub_label": "샌달우드, 시더, 베티버"},
        {"id": "musk", "label": "머스키", "sub_label": "머스크, 화이트 머스크"},
        {"id": "citrus", "label": "시트러스", "sub_label": "베르가못, 레몬, 오렌지"},
        {"id": "oriental", "label": "오리엔탈", "sub_label": "앰버, 바닐라, 인센스"},
        {"id": "aquatic", "label": "아쿠아틱", "sub_label": "바다, 물, 마린"},
        {"id": "green", "label": "그린", "sub_label": "풀잎, 허브, 민트"},
        {"id": "spicy", "label": "스파이시", "sub_label": "후추, 시나몬, 클로브"},
        {"id": "powdery", "label": "파우더리", "sub_label": "아이리스, 바이올렛, 파우더"},
        {"id": "gourmand", "label": "구르망", "sub_label": "바닐라, 캐러멜, 초콜릿"},
        {"id": "fresh", "label": "프레시", "sub_label": "상쾌하고 가벼운 향"},
        {"id": "earthy", "label": "어시", "sub_label": "패출리, 오크모스, 흙내음"},
    ],
    "avoid": [
        {"id": "powdery", "label": "파우더리한 향", "sub_label": "분가루처럼 텁텁한 향"},
        {"id": "musk", "label": "머스크 향", "sub_label": "답답하거나 무겁게 느껴질 수 있는 향"},
        {"id": "woody", "label": "나무향/오드", "sub_label": "깊고 묵직한 우디 계열"},
        {"id": "spicy", "label": "스파이시한 향", "sub_label": "후추, 향신료처럼 자극적인 향"},
        {"id": "sweet", "label": "너무 단 향", "sub_label": "바닐라, 캐러멜, 구르망"},
    ],
}


def perfume_results_to_response(results):
    return [
        {
            "rank": rank,
            "name": row["Name"],
            "brand": row["Brand"],
            "score": round(float(row["score"]), 4),
            "notes": row["Notes"],
            "description": row["Description"],
            "image_url": row["Image URL"],
        }
        for rank, (_, row) in enumerate(results.iterrows(), start=1)
    ]


@app.get("/api/v1/health")
def health_check():
    return {
        "status": "ok",
        "service": "hyangdam-backend",
    }


@app.get("/api/v1")
def api_root():
    return {
        "service": "hyangdam-backend",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/categories")
def get_categories():
    categories = {}

    for group, items in CATEGORY_GROUPS.items():
        categories[group] = [
            {
                **item,
                "keywords": (
                    AVOID_KEYWORDS.get(item["id"], [])
                    if group == "avoid"
                    else CATEGORY_KEYWORDS.get(item["id"], [])
                ),
            }
            for item in items
        ]

    return {"categories": categories}


@app.post("/api/v1/preferences/extract")
def extract_preferences(request: TextPreferenceRequest):
    extracted = extract_preferences_from_text(request.text)

    return {
        "input_text": request.text,
        "selected_categories": extracted["selected_categories"],
        "avoid_categories": extracted["avoid_categories"],
        "selected_scores": extracted["selected_scores"],
        "avoid_scores": extracted["avoid_scores"],
    }


@app.post("/api/v1/recommendations")
def recommend_perfumes(request: RecommendationRequest):
    if not request.selected_categories:
        raise HTTPException(
            status_code=400,
            detail="selected_categories must contain at least one category.",
        )

    results = recommender.recommend(
        selected_categories=request.selected_categories,
        avoid_categories=request.avoid_categories,
        focus_categories=request.focus_categories,
        top_n=request.top_n,
    )

    return {
        "selected_categories": request.selected_categories,
        "avoid_categories": request.avoid_categories,
        "focus_categories": request.focus_categories,
        "top_n": request.top_n,
        "results": perfume_results_to_response(results),
    }


@app.post("/api/v1/recommendations/text")
def recommend_perfumes_by_text(request: TextRecommendationRequest):
    extracted = extract_preferences_from_text(request.text)
    selected_categories = extracted["selected_categories"] or ["clean"]
    avoid_categories = extracted["avoid_categories"]
    focus_categories = selected_categories[:1]

    results = recommender.recommend(
        selected_categories=selected_categories,
        avoid_categories=avoid_categories,
        focus_categories=focus_categories,
        top_n=request.top_n,
    )

    return {
        "input_text": request.text,
        "extracted_preferences": {
            "selected_categories": selected_categories,
            "avoid_categories": avoid_categories,
            "focus_categories": focus_categories,
            "selected_scores": extracted["selected_scores"],
            "avoid_scores": extracted["avoid_scores"],
        },
        "top_n": request.top_n,
        "results": perfume_results_to_response(results),
    }
