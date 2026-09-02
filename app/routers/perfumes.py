from fastapi import APIRouter, Depends, Query
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
    limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return {
        "keyword": keyword,
        "results": search_perfumes_from_db(db=db, keyword=keyword, limit=limit),
    }


@router.get("/brands/popular")
def get_popular_brands(
    limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return {
        "brands": get_popular_brands_from_db(db=db, limit=limit)
    }
