import logging

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import MONITORING_INTERVAL_HOURS, MONITORING_SOURCES
from app.core.exceptions import LLMUnavailableError
from app.db.session import async_session_factory
from app.models.matrix import CompetencyMatrix, MatrixStatus
from app.providers.base import CurrentCategory, CurrentSubItem, MatrixMonitoringContext, SourceContent
from app.providers.factory import get_llm_provider
from app.services import matrix_service

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _fetch_source(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.text


async def _get_current_matrix_state(db: AsyncSession) -> CompetencyMatrix | None:
    result = await db.execute(
        select(CompetencyMatrix).where(CompetencyMatrix.status == MatrixStatus.APPROVED).limit(1)
    )
    matrix = result.scalar_one_or_none()
    if matrix:
        await db.refresh(matrix, ["categories"])
        for cat in matrix.categories:
            await db.refresh(cat, ["sub_items"])
    return matrix


async def _process_source(
    db: AsyncSession, source: dict[str, str], matrix: CompetencyMatrix | None
) -> int:
    name = source["name"]
    url = source["url"]
    try:
        full_content = await _fetch_source(url)
    except Exception:
        logger.warning("monitoring: fetch failed for source %r — skipping", name)
        return 0

    current_categories = []
    matrix_id = None
    if matrix:
        matrix_id = matrix.id
        for cat in matrix.categories:
            current_categories.append(
                CurrentCategory(
                    name=cat.name,
                    sub_items=[
                        CurrentSubItem(name=s.name, description=s.description)
                        for s in cat.sub_items
                    ],
                )
            )

    # Simple chunking logic: split by 8000 chars for now to respect LLM context
    # but keep them as separate batches to avoid missing data.
    chunk_size = 8000
    chunks = [full_content[i : i + chunk_size] for i in range(0, len(full_content), chunk_size)]
    
    total_proposals = 0
    for chunk in chunks[:3]:  # Limit to first 3 chunks for safety/costs
        context = MatrixMonitoringContext(
            source=SourceContent(name=name, url=url, content=chunk),
            current_categories=current_categories,
        )
        try:
            provider = get_llm_provider()
            drafts = await provider.propose_matrix_updates(context)
            
            for draft in drafts:
                draft.matrix_id = matrix_id
                if await matrix_service.save_proposal(db, draft):
                    total_proposals += 1
        except (LLMUnavailableError, Exception):
            logger.exception("monitoring: LLM call failed for source %r (chunk)", name)
            continue

    if total_proposals:
        await db.commit()
    return total_proposals


async def run_monitoring_job() -> None:
    try:
        async with async_session_factory() as db:
            matrix = await _get_current_matrix_state(db)
            total = 0
            for source in MONITORING_SOURCES:
                total += await _process_source(db, source, matrix)
            logger.info(
                "monitoring_job: created %d proposals across %d sources",
                total,
                len(MONITORING_SOURCES),
            )
    except Exception:
        logger.exception("monitoring_job: top-level failure — scheduler will retry on next interval")


def setup_scheduler() -> None:
    _scheduler.add_job(
        run_monitoring_job,
        trigger="interval",
        hours=MONITORING_INTERVAL_HOURS,
        id="matrix_monitoring",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started — matrix monitoring every %d hours", MONITORING_INTERVAL_HOURS)


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
