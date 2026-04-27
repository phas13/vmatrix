from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


async def get_db(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    yield session


async def get_current_user():
    # Full implementation in Story 1.2
    raise NotImplementedError("Implemented in Story 1.2")


def require_role(*roles: str):
    # Full implementation in Story 1.3
    async def dependency():
        raise NotImplementedError("Implemented in Story 1.3")

    return dependency
