from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="VMatrix API", version="1.0.0", lifespan=lifespan)

app.include_router(v1_router, prefix="/api/v1")
