import pandas as pd
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.perfume import Perfume
from app.services.recommender import load_perfume_data


def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value)


def perfume_to_response(perfume: Perfume, include_description: bool = False) -> dict:
    result = {
        "perfume_id": perfume.perfume_id,
        "name": perfume.name,
        "brand": perfume.brand,
        "notes": perfume.notes,
        "image_url": perfume.image_url,
    }

    if include_description:
        result["description"] = perfume.description

    return result


def seed_perfumes_from_csv(db: Session) -> int:
    """CSV 행 번호 + 1을 영구 perfume_id로 사용해 앱/DB 간 ID를 고정한다."""
    df = load_perfume_data()
    existing_ids = {
        perfume_id
        for perfume_id, in db.query(Perfume.perfume_id).all()
    }

    records = []
    for row_index, row in df.iterrows():
        perfume_id = int(row_index) + 1
        if perfume_id in existing_ids:
            continue

        records.append(
            {
                "perfume_id": perfume_id,
                "name": clean_value(row["Name"]),
                "brand": clean_value(row["Brand"]),
                "description": clean_value(row["Description"]),
                "notes": clean_value(row["Notes"]),
                "image_url": clean_value(row["Image URL"]),
            }
        )

    if records:
        db.bulk_insert_mappings(Perfume, records)
        db.commit()

    return len(records)


def get_perfume_or_none(db: Session, perfume_id: int) -> dict | None:
    perfume = db.get(Perfume, perfume_id)
    if perfume is None:
        return None
    return perfume_to_response(perfume, include_description=True)


def search_perfumes(db: Session, keyword: str = "", limit: int = 10) -> list[dict]:
    query = db.query(Perfume)

    if keyword:
        search_keyword = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Perfume.name.ilike(search_keyword),
                Perfume.brand.ilike(search_keyword),
            )
        )

    perfumes = query.order_by(Perfume.perfume_id).limit(limit).all()
    return [perfume_to_response(perfume) for perfume in perfumes]


def get_popular_brands(db: Session, limit: int = 10) -> list[dict]:
    rows = (
        db.query(Perfume.brand, func.count(Perfume.perfume_id).label("count"))
        .group_by(Perfume.brand)
        .order_by(func.count(Perfume.perfume_id).desc(), Perfume.brand.asc())
        .limit(limit)
        .all()
    )

    return [{"brand": brand, "count": count} for brand, count in rows]
