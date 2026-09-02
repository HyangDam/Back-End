from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.like import Like
from app.models.perfume import Perfume
from app.services.recommender import CATEGORY_KEYWORDS, load_perfume_data


def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value)


def _matches_keyword(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()


def get_perfume_categories(perfume: Perfume) -> list[str]:
    searchable_text = f"{perfume.name} {perfume.notes} {perfume.description}"
    categories = [
        category
        for category, keywords in CATEGORY_KEYWORDS.items()
        if any(_matches_keyword(searchable_text, keyword) for keyword in keywords)
    ]
    return categories


def perfume_to_response(
    perfume: Perfume,
    include_description: bool = False,
    like_count: int = 0,
    weekly_like_count: int | None = None,
) -> dict:
    categories = get_perfume_categories(perfume)
    result = {
        "perfume_id": perfume.perfume_id,
        "name": perfume.name,
        "brand": perfume.brand,
        "notes": perfume.notes,
        "image_url": perfume.image_url,
        "like_count": like_count,
        "category": categories[0] if categories else None,
        "categories": categories,
    }

    if weekly_like_count is not None:
        result["weekly_like_count"] = weekly_like_count

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
    row = (
        db.query(
            Perfume,
            func.count(Like.id).label("like_count"),
        )
        .outerjoin(Like, Like.perfume_id == Perfume.perfume_id)
        .filter(Perfume.perfume_id == perfume_id)
        .group_by(Perfume.perfume_id)
        .first()
    )
    if row is None:
        return None
    perfume, like_count = row
    return perfume_to_response(
        perfume,
        include_description=True,
        like_count=int(like_count),
    )


def normalize_categories(raw_categories: list[str] | None) -> list[str]:
    if not raw_categories:
        return []

    categories = []
    for raw_category in raw_categories:
        categories.extend(
            category.strip().lower()
            for category in raw_category.split(",")
            if category.strip()
        )

    unknown_categories = sorted(set(categories) - set(CATEGORY_KEYWORDS))
    if unknown_categories:
        raise ValueError(f"Unsupported category: {', '.join(unknown_categories)}")

    return list(dict.fromkeys(categories))


def search_perfumes(
    db: Session,
    keyword: str = "",
    categories: list[str] | None = None,
    sort: str = "popular",
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict], int]:
    normalized_categories = normalize_categories(categories)
    like_counts = (
        db.query(
            Like.perfume_id.label("perfume_id"),
            func.count(Like.id).label("like_count"),
        )
        .group_by(Like.perfume_id)
        .subquery()
    )
    like_count = func.coalesce(like_counts.c.like_count, 0).label("like_count")
    weekly_like_counts = (
        db.query(
            Like.perfume_id.label("perfume_id"),
            func.count(Like.id).label("weekly_like_count"),
        )
        .filter(Like.created_at >= datetime.utcnow() - timedelta(days=7))
        .group_by(Like.perfume_id)
        .subquery()
    )
    weekly_like_count = func.coalesce(
        weekly_like_counts.c.weekly_like_count,
        0,
    ).label("weekly_like_count")
    query = db.query(Perfume, like_count).outerjoin(
        like_counts,
        like_counts.c.perfume_id == Perfume.perfume_id,
    )
    query = query.add_columns(weekly_like_count).outerjoin(
        weekly_like_counts,
        weekly_like_counts.c.perfume_id == Perfume.perfume_id,
    )

    if keyword:
        search_keyword = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Perfume.name.ilike(search_keyword),
                Perfume.brand.ilike(search_keyword),
            )
        )

    for category in normalized_categories:
        category_conditions = [
            or_(
                Perfume.name.ilike(f"%{term}%"),
                Perfume.notes.ilike(f"%{term}%"),
                Perfume.description.ilike(f"%{term}%"),
            )
            for term in CATEGORY_KEYWORDS[category]
        ]
        query = query.filter(or_(*category_conditions))

    total = query.order_by(None).count()

    if sort == "popular":
        query = query.order_by(like_count.desc(), Perfume.perfume_id.asc())
    elif sort == "weekly_popular":
        query = query.order_by(
            weekly_like_count.desc(),
            like_count.desc(),
            Perfume.perfume_id.asc(),
        )
    elif sort == "name":
        query = query.order_by(Perfume.name.asc(), Perfume.perfume_id.asc())
    else:
        raise ValueError(
            "Unsupported sort. Available values: popular, weekly_popular, name"
        )

    rows = query.offset((page - 1) * size).limit(size).all()
    return (
        [
            perfume_to_response(
                perfume,
                like_count=int(total_count),
                weekly_like_count=int(weekly_count),
            )
            for perfume, total_count, weekly_count in rows
        ],
        total,
    )


def get_popular_brands(db: Session, limit: int = 10) -> list[dict]:
    rows = (
        db.query(Perfume.brand, func.count(Perfume.perfume_id).label("count"))
        .group_by(Perfume.brand)
        .order_by(func.count(Perfume.perfume_id).desc(), Perfume.brand.asc())
        .limit(limit)
        .all()
    )

    return [{"brand": brand, "count": count} for brand, count in rows]
