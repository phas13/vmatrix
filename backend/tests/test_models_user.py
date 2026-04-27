
from sqlalchemy import inspect

from app.models.user import RefreshToken, User, UserRole


def test_user_role_values():
    assert UserRole.SPECIALIST.value == "specialist"
    assert UserRole.CM.value == "cm"
    assert UserRole.HR.value == "hr"
    assert UserRole.ADMIN.value == "admin"


def test_user_model_columns():
    mapper = inspect(User)
    col_names = {c.key for c in mapper.columns}
    assert {"id", "email", "hashed_password", "full_name", "role", "is_active", "created_at", "updated_at"} <= col_names


def test_refresh_token_model_columns():
    mapper = inspect(RefreshToken)
    col_names = {c.key for c in mapper.columns}
    assert {"id", "user_id", "token_hash", "expires_at", "revoked_at", "created_at", "updated_at"} <= col_names


def test_user_tablename():
    assert User.__tablename__ == "users"


def test_refresh_token_tablename():
    assert RefreshToken.__tablename__ == "refresh_tokens"


def test_user_email_unique_constraint():
    args = {a.name for a in User.__table_args__ if hasattr(a, "name")}
    assert "uq_users_email" in args
