from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PerfumeReview(Base):
    __tablename__ = "perfume_reviews"

    review_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id"),
        nullable=False,
    )
    perfume_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("perfumes.perfume_id"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_perfume_reviews_rating"),
        UniqueConstraint("user_id", "perfume_id", name="uq_reviews_user_perfume"),
    )
