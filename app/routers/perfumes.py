from fastapi import APIRouter, Query

from app.services.perfume_catalog import search_perfumes_from_csv

router = APIRouter(
    prefix="/api/v1",
    tags=["Perfumes"],
)


@router.get("/perfumes/search")
def search_perfumes(
    keyword: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=30),
):
    return {
        "keyword": keyword,
        "results": search_perfumes_from_csv(keyword=keyword, limit=limit),
    }


@router.get("/brands/popular")
def get_popular_brands(
    limit: int = Query(default=10, ge=1, le=30),
):
    from app.services.perfume_catalog import get_perfume_data

    df = get_perfume_data()

    brand_counts = (
        df["Brand"]
        .dropna()
        .astype(str)
        .str.strip()
        .value_counts()
        .head(limit)
    )

    return {
        "brands": [
            {
                "brand": brand,
                "count": int(count),
            }
            for brand, count in brand_counts.items()
        ]
    }