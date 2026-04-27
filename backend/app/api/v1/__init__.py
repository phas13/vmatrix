from fastapi import APIRouter

from app.api.v1 import admin, auth, cm, health, hr, matrix, sessions, users

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(matrix.router, prefix="/matrix", tags=["matrix"])
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
router.include_router(cm.router, prefix="/cm", tags=["cm"])
router.include_router(hr.router, prefix="/hr", tags=["hr"])
