from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models.like import Like
from app.models.perfume import Perfume
from app.models.perfume_market import PerfumeMarketMetadata, PerfumeMarketOffer
from app.services.note_visualization import build_note_visualization
from app.services.price_comparison import build_price_comparison
from app.services.recommender import CATEGORY_KEYWORDS, load_perfume_data


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MARKET_METADATA_PATH = DATA_DIR / "perfume_market_metadata.csv"
MARKET_OFFERS_PATH = DATA_DIR / "perfume_market_offers.csv"


def clean_value(value):
    if pd.isna(value):
        return ""
    return str(value)


@lru_cache(maxsize=1)
def _runtime_catalog_records_by_id() -> dict[int, dict]:
    """Cache static CSV display metadata for list and detail responses."""
    data = load_perfume_data()
    return {
        int(row["perfume_id"]): row.to_dict()
        for _, row in data.iterrows()
    }


def get_runtime_catalog_record(perfume_id: int) -> dict | None:
    """Read non-DB display metadata kept alongside the source catalog files."""
    return _runtime_catalog_records_by_id().get(perfume_id)


@lru_cache(maxsize=1)
def _market_date_details_by_id() -> dict[int, dict[str, str]]:
    """Keep audit-only date metadata out of the runtime database schema.

    ``released_at`` is persisted for sorting, while the CSV retains whether the
    date means a product launch or a documented domestic availability event.
    """
    if not MARKET_METADATA_PATH.exists():
        return {}

    details: dict[int, dict[str, str]] = {}
    for row in pd.read_csv(MARKET_METADATA_PATH).to_dict("records"):
        perfume_id = int(row["perfume_id"])
        details[perfume_id] = {
            "market_date_type": _optional_text(row.get("market_date_type")) or "launch",
            "release_source_url": _optional_text(row.get("release_source_url")) or "",
        }
    return details


def _localized_value(record: dict | None, field: str, fallback: str) -> str:
    if record is None:
        return fallback
    value = record.get(field)
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    return text or fallback


@lru_cache(maxsize=256)
def _runtime_keyword_matches(keyword: str) -> list[int]:
    """Find catalog IDs by Korean product, brand, or note labels kept in CSV."""
    normalized_keyword = keyword.strip().casefold()
    if not normalized_keyword:
        return []

    searchable_columns = ["Name KR", "Brand KR", "Notes KR", "Summary KR"]
    matches = []
    for perfume_id, record in _runtime_catalog_records_by_id().items():
        if any(
            normalized_keyword in str(record.get(column, "")).casefold()
            for column in searchable_columns
        ):
            matches.append(perfume_id)
    return matches


def get_perfume_categories(perfume: Perfume) -> list[str]:
    """Return display categories derived from actual perfume notes.

    Situation labels such as ``date`` are recommendation inputs, not perfume
    taxonomy. Reusing the note-visualization accords keeps list filtering and
    detail-page labels consistent.
    """
    visualization = build_note_visualization(perfume.notes)
    return [accord["id"] for accord in visualization["accord_bars"]]


def perfume_to_response(
    perfume: Perfume,
    include_description: bool = False,
    like_count: int = 0,
    weekly_like_count: int | None = None,
    representative_price: int | None = None,
    released_at=None,
) -> dict:
    categories = get_perfume_categories(perfume)
    runtime_record = get_runtime_catalog_record(perfume.perfume_id)
    name_ko = _localized_value(runtime_record, "Name KR", perfume.name)
    brand_ko = _localized_value(runtime_record, "Brand KR", perfume.brand)
    notes_ko = _localized_value(runtime_record, "Notes KR", perfume.notes)
    result = {
        "perfume_id": perfume.perfume_id,
        "name": perfume.name,
        "brand": perfume.brand,
        "notes": perfume.notes,
        "name_ko": name_ko,
        "brand_ko": brand_ko,
        "notes_ko": notes_ko,
        "display_name": name_ko,
        "display_brand": brand_ko,
        "display_notes": notes_ko,
        "image_url": perfume.image_url,
        "like_count": like_count,
        "representative_price": representative_price,
        "released_at": released_at,
        "category": categories[0] if categories else None,
        "categories": categories,
    }

    market_date_details = _market_date_details_by_id().get(perfume.perfume_id)
    if market_date_details:
        result["market_date_type"] = market_date_details["market_date_type"]

    if weekly_like_count is not None:
        result["weekly_like_count"] = weekly_like_count

    if include_description:
        result["description"] = perfume.description
        description_ko = _localized_value(
            runtime_record,
            "Description KR",
            perfume.description,
        )
        result["description_ko"] = description_ko
        result["display_description"] = description_ko
        result["note_visualization"] = build_note_visualization(perfume.notes)

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


def _optional_text(value) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _optional_date(value):
    text = _optional_text(value)
    if text is None:
        return None
    return pd.to_datetime(text).date()


def _optional_datetime(value):
    text = _optional_text(value)
    if text is None:
        return None
    return pd.to_datetime(text).to_pydatetime()


def _optional_int(value) -> int | None:
    if pd.isna(value):
        return None
    return int(value)


def seed_market_data_from_csv(db: Session) -> dict[str, int]:
    """Upsert manually verified release dates and retail prices from CSV files.

    The source catalog intentionally has no fabricated market data. Only rows
    placed in these files are eligible for latest sorting or price comparison.
    """
    inserted_metadata = 0
    inserted_offers = 0
    perfume_ids = {perfume_id for perfume_id, in db.query(Perfume.perfume_id).all()}

    if MARKET_METADATA_PATH.exists():
        metadata_rows = pd.read_csv(MARKET_METADATA_PATH)
        for row in metadata_rows.to_dict("records"):
            perfume_id = int(row["perfume_id"])
            if perfume_id not in perfume_ids:
                continue

            metadata = db.get(PerfumeMarketMetadata, perfume_id)
            if metadata is None:
                metadata = PerfumeMarketMetadata(perfume_id=perfume_id)
                db.add(metadata)
                inserted_metadata += 1

            metadata.released_at = _optional_date(row.get("released_at"))
            metadata.official_product_url = _optional_text(
                row.get("official_product_url")
            )

    if MARKET_OFFERS_PATH.exists():
        offer_rows = pd.read_csv(MARKET_OFFERS_PATH)
        for row in offer_rows.to_dict("records"):
            perfume_id = int(row["perfume_id"])
            if perfume_id not in perfume_ids:
                continue

            retailer = _optional_text(row.get("retailer"))
            product_url = _optional_text(row.get("product_url"))
            checked_at = _optional_datetime(row.get("checked_at"))
            if retailer is None or product_url is None or checked_at is None:
                continue

            offer = (
                db.query(PerfumeMarketOffer)
                .filter(
                    PerfumeMarketOffer.perfume_id == perfume_id,
                    PerfumeMarketOffer.retailer == retailer,
                    PerfumeMarketOffer.product_url == product_url,
                )
                .first()
            )
            if offer is None:
                offer = PerfumeMarketOffer(
                    perfume_id=perfume_id,
                    retailer=retailer,
                    product_url=product_url,
                    checked_at=checked_at,
                )
                db.add(offer)
                inserted_offers += 1

            offer.price_krw = _optional_int(row.get("price_krw"))
            offer.capacity_ml = _optional_int(row.get("capacity_ml"))
            offer.checked_at = checked_at

    db.commit()
    return {"metadata": inserted_metadata, "offers": inserted_offers}


def get_perfume_or_none(db: Session, perfume_id: int) -> dict | None:
    row = (
        db.query(
            Perfume,
            func.count(Like.id).label("like_count"),
            func.max(PerfumeMarketMetadata.released_at).label("released_at"),
        )
        .outerjoin(Like, Like.perfume_id == Perfume.perfume_id)
        .outerjoin(
            PerfumeMarketMetadata,
            PerfumeMarketMetadata.perfume_id == Perfume.perfume_id,
        )
        .filter(Perfume.perfume_id == perfume_id)
        .group_by(Perfume.perfume_id)
        .first()
    )
    if row is None:
        return None
    perfume, like_count, released_at = row
    return perfume_to_response(
        perfume,
        include_description=True,
        like_count=int(like_count),
        released_at=released_at,
    )


def get_price_comparison(db: Session, perfume_id: int) -> dict | None:
    perfume = get_perfume_or_none(db, perfume_id)
    if perfume is None:
        return None

    runtime_record = get_runtime_catalog_record(perfume_id)
    source_url = str(runtime_record.get("Source URL", "")) if runtime_record else ""
    metadata = db.get(PerfumeMarketMetadata, perfume_id)
    if metadata and metadata.official_product_url:
        source_url = metadata.official_product_url

    offer_rows = (
        db.query(PerfumeMarketOffer)
        .filter(PerfumeMarketOffer.perfume_id == perfume_id)
        .order_by(
            case((PerfumeMarketOffer.price_krw.is_(None), 1), else_=0),
            PerfumeMarketOffer.price_krw.asc(),
        )
        .all()
    )
    offers = [
        {
            "retailer": offer.retailer,
            "price_krw": offer.price_krw,
            "capacity_ml": offer.capacity_ml,
            "url": offer.product_url,
            "checked_at": offer.checked_at,
        }
        for offer in offer_rows
    ]
    return build_price_comparison(perfume, source_url=source_url, offers=offers)


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
    minimum_prices = (
        db.query(
            PerfumeMarketOffer.perfume_id.label("perfume_id"),
            func.min(PerfumeMarketOffer.price_krw).label("representative_price"),
        )
        .filter(PerfumeMarketOffer.price_krw.is_not(None))
        .group_by(PerfumeMarketOffer.perfume_id)
        .subquery()
    )
    representative_price = minimum_prices.c.representative_price.label(
        "representative_price"
    )
    query = db.query(Perfume, like_count).outerjoin(
        like_counts,
        like_counts.c.perfume_id == Perfume.perfume_id,
    )
    query = query.add_columns(weekly_like_count).outerjoin(
        weekly_like_counts,
        weekly_like_counts.c.perfume_id == Perfume.perfume_id,
    )
    query = query.add_columns(representative_price).outerjoin(
        minimum_prices,
        minimum_prices.c.perfume_id == Perfume.perfume_id,
    )
    query = query.add_columns(PerfumeMarketMetadata.released_at).outerjoin(
        PerfumeMarketMetadata,
        PerfumeMarketMetadata.perfume_id == Perfume.perfume_id,
    )

    if keyword:
        search_keyword = f"%{keyword.strip()}%"
        localized_ids = _runtime_keyword_matches(keyword)
        keyword_conditions = [
            Perfume.name.ilike(search_keyword),
            Perfume.brand.ilike(search_keyword),
        ]
        if localized_ids:
            keyword_conditions.append(Perfume.perfume_id.in_(localized_ids))
        query = query.filter(
            or_(*keyword_conditions)
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

    # "신규 출시"는 실제 출시일이 검증되어 적재된 제품만 보여준다.
    if sort == "latest":
        query = query.filter(PerfumeMarketMetadata.released_at.is_not(None))

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
    elif sort == "latest":
        query = query.order_by(
            case((PerfumeMarketMetadata.released_at.is_(None), 1), else_=0),
            PerfumeMarketMetadata.released_at.desc(),
            Perfume.perfume_id.asc(),
        )
    elif sort == "price_asc":
        query = query.order_by(
            case((representative_price.is_(None), 1), else_=0),
            representative_price.asc(),
            Perfume.perfume_id.asc(),
        )
    elif sort == "price_desc":
        query = query.order_by(
            case((representative_price.is_(None), 1), else_=0),
            representative_price.desc(),
            Perfume.perfume_id.asc(),
        )
    else:
        raise ValueError(
            "Unsupported sort. Available values: popular, weekly_popular, name, latest, price_asc, price_desc"
        )

    rows = query.offset((page - 1) * size).limit(size).all()
    return (
        [
                perfume_to_response(
                    perfume,
                    like_count=int(total_count),
                    weekly_like_count=int(weekly_count),
                    representative_price=int(price) if price is not None else None,
                    released_at=released_at,
                )
            for perfume, total_count, weekly_count, price, released_at in rows
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

    localized_brands = {}
    for record in _runtime_catalog_records_by_id().values():
        brand = str(record.get("Brand", "")).strip()
        if brand and brand not in localized_brands:
            localized_brands[brand] = _localized_value(record, "Brand KR", brand)

    return [
        {
            "brand": brand,
            "brand_ko": localized_brands.get(brand, brand),
            "display_brand": localized_brands.get(brand, brand),
            "count": count,
        }
        for brand, count in rows
    ]
