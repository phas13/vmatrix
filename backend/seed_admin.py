"""One-off local bootstrap: create an initial ADMIN user.

There is no admin in a fresh database, and `POST /admin/users` itself requires an
ADMIN, so the very first admin must be seeded directly. Idempotent: re-running it
leaves an existing admin untouched.

Usage (inside the backend container):
    python seed_admin.py
Credentials and overrides via env vars:
    SEED_ADMIN_EMAIL (default admin@vmatrix.local)
    SEED_ADMIN_PASSWORD (default ChangeMe123!)
    SEED_ADMIN_NAME (default "Platform Admin")
"""

import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.user import User, UserRole

EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@vmatrix.app")
PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")
FULL_NAME = os.environ.get("SEED_ADMIN_NAME", "Platform Admin")


async def main() -> None:
    async with async_session_factory() as db:
        existing = await db.execute(
            select(User).where(User.email == EMAIL.lower().strip())
        )
        if existing.scalar_one_or_none() is not None:
            print(f"[seed] admin already exists: {EMAIL} (no change)")
            return

        admin = User(
            email=EMAIL.lower().strip(),
            full_name=FULL_NAME,
            role=UserRole.ADMIN,
            hashed_password=hash_password(PASSWORD),
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print(f"[seed] created ADMIN  email={EMAIL}  password={PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
