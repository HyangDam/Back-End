from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserPerfume(Base):
    __tablename__ = "user_perfumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
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
    status: Mapped[str] = mapped_column(String(20), default="owned", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "perfume_id", name="uq_user_perfumes_user_perfume"),
    )
