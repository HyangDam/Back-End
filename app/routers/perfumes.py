from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.perfume_catalog import (
    get_popular_brands as get_popular_brands_from_db,
    search_perfumes as search_perfumes_from_db,
)

router = APIRouter(
    prefix="/api/v1",
    tags=["Perfumes"],
)


@router.get("/perfumes/search")
def search_perfumes(
    keyword: str = Query(default=""),
    category: list[str] | None = Query(
        default=None,
        description="향 계열. category=floral&category=citrus 또는 category=floral,citrus",
    ),
    sort: str = Query(default="popular", pattern="^(popular|name)$"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=50),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=50,
        deprecated=True,
        description="기존 검색 API 호환용. 새 연동에서는 size 사용 권장.",
    ),
    db: Session = Depends(get_db),
):
    effective_size = limit or size

    try:
        results, total = search_perfumes_from_db(
            db=db,
            keyword=keyword,
            categories=category,
            sort=sort,
            page=page,
            size=effective_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "keyword": keyword,
        "categories": category or [],
        "sort": sort,
        "page": page,
        "size": effective_size,
        "total": total,
        "has_next": page * effective_size < total,
        "results": results,
    }


@router.get("/brands/popular")
def get_popular_brands(
    limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return {
        "brands": get_popular_brands_from_db(db=db, limit=limit)
    }
