from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserOnboarding(Base):
    __tablename__ = "user_onboarding"

    onboarding_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.user_id"),
        unique=True,
        nullable=False,
    )

    current_perfumes: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    preferred_target: Mapped[str | None] = mapped_column(String(20), nullable=True)
    selected_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    avoid_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    focus_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    preferred_brands: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )