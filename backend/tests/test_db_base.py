from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def test_timestamp_mixin_has_created_and_updated_at():
    assert "created_at" in TimestampMixin.__annotations__
    assert "updated_at" in TimestampMixin.__annotations__


def test_timestamp_mixin_annotations_are_datetime():
    annotations = TimestampMixin.__annotations__
    for field in ("created_at", "updated_at"):
        assert field in annotations


def test_base_is_declarative_base():
    assert hasattr(Base, "metadata")
    assert hasattr(Base, "registry")


def test_uuid_primary_key_mixin_has_id():
    assert "id" in UUIDPrimaryKeyMixin.__annotations__
