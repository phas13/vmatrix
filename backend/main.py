from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.exceptions import ProblemHTTPException
from app.db.session import engine
from app.services.monitoring_service import setup_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_scheduler()
    yield
    shutdown_scheduler()
    await engine.dispose()


app = FastAPI(title="VMatrix API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(ProblemHTTPException)
async def problem_exception_handler(request: Request, exc: ProblemHTTPException):
    headers = dict(exc.headers) if exc.headers else {}
    if exc.status_code == 401:
        headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail,
        media_type="application/problem+json",
        headers=headers,
    )


app.include_router(v1_router, prefix="/api/v1")
