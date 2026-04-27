from fastapi import HTTPException, status

from app.db.session import get_db_session  # re-exported for routes

__all__ = ["get_db_session", "get_current_user", "require_role"]


async def get_current_user():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication is implemented in Story 1.2",
    )


def require_role(*roles: str):
    async def dependency():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Role-based access control is implemented in Story 1.3",
        )

    return dependency
