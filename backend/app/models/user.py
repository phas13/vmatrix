import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    SPECIALIST = "specialist"
    CM = "cm"
    HR = "hr"
    ADMIN = "admin"


class SpecialistLevel(str, enum.Enum):
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Native Postgres enum already created by migration a1b2c3d4e5f6; use values_callable
    # so SQLAlchemy serializes UserRole.ADMIN as "admin" (not "ADMIN").
    role: Mapped[UserRole] = mapped_column(
        SAEnum(
            UserRole,
            name="userrole",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Migration stores specialist_level as VARCHAR(50); native_enum=False keeps SQLAlchemy
    # in lock-step (validates values without touching the DB type).
    specialist_level: Mapped[SpecialistLevel | None] = mapped_column(
        SAEnum(
            SpecialistLevel,
            native_enum=False,
            length=50,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )
    cm_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    cm: Mapped["User | None"] = relationship("User", remote_side="User.id", foreign_keys="User.cm_id")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Store SHA-256 hex digest only — never store raw token
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Identifies the token family — all rotated descendants share the same family_id.
    # Presenting a revoked token triggers revocation of all non-revoked family members.
    family_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
