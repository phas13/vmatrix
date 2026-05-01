from __future__ import annotations

import enum
from uuid import UUID

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MatrixStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"


class CompetencyMatrix(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "competency_matrices"

    specialist_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True, unique=True
    )
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[MatrixStatus] = mapped_column(
        SAEnum(
            MatrixStatus,
            native_enum=False,
            length=30,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=MatrixStatus.PENDING_REVIEW,
    )
    categories: Mapped[list["CompetencyCategory"]] = relationship(
        back_populates="matrix", order_by="CompetencyCategory.order", cascade="all, delete-orphan"
    )


class CompetencyCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "competency_categories"

    matrix_id: Mapped[UUID] = mapped_column(
        ForeignKey("competency_matrices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matrix: Mapped["CompetencyMatrix"] = relationship(back_populates="categories")
    sub_items: Mapped[list["CompetencySubItem"]] = relationship(
        back_populates="category", order_by="CompetencySubItem.order", cascade="all, delete-orphan"
    )


class CompetencySubItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "competency_sub_items"

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("competency_categories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_flagged: Mapped[bool] = mapped_column(nullable=False, default=False)
    flag_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped["CompetencyCategory"] = relationship(back_populates="sub_items")
