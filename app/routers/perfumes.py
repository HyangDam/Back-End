from fastapi import APIRouter, Query

from app.services.recommender import load_perfume_data

router = APIRouter(
    prefix="/api/v1",
    tags=["Perfumes"],
)

df = load_perfume_data()


def row_to_perfume(row_index, row):
    return {
        "perfume_id": int(row_index) + 1,
        "name": row["Name"],
        "brand": row["Brand"],
        "notes": row["Notes"],
        "image_url": row["Image URL"],
    }


@router.get("/perfumes/search")
def search_perfumes(
    keyword: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=30),
):
    data = df.copy()

    if keyword:
        keyword_lower = keyword.lower()
        mask = (
            data["Name"].str.lower().str.contains(keyword_lower, na=False, regex=False)
            | data["Brand"].str.lower().str.contains(keyword_lower, na=False, regex=False)
        )
        data = data[mask]

    return {
        "keyword": keyword,
        "results": [
            row_to_perfume(index, row)
            for index, row in data.head(limit).iterrows()
        ],
    }


@router.get("/brands/popular")
def get_popular_brands(
    limit: int = Query(default=10, ge=1, le=30),
):
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