from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SystemSettings(Base, TimestampMixin):
    __tablename__ = "system_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_system_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promotion_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    default_competency_domain: Mapped[str] = mapped_column(
        String(100), nullable=False, default="DevOps"
    )
