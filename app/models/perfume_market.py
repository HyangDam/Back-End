from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PerfumeMarketMetadata(Base):
    __tablename__ = "perfume_market_metadata"

    perfume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("perfumes.perfume_id", ondelete="CASCADE"),
        primary_key=True,
    )
    released_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    official_product_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class PerfumeMarketOffer(Base):
    __tablename__ = "perfume_market_offers"

    offer_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    perfume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("perfumes.perfume_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    retailer: Mapped[str] = mapped_column(String(100), nullable=False)
    product_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    price_krw: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capacity_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
