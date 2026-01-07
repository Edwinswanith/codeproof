"""Repo intelligence scan task."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.services.scan_service import ScanService

logger = logging.getLogger(__name__)
settings = get_settings()


def get_async_session() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(
        settings.database_url,
        pool_size=5,
        pool_pre_ping=True,
    )
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def scan_repository_async(
    scan_run_id: str,
    repo_url: str,
    ref: str | None = None,
    token: str | None = None,
) -> None:
    session_factory = get_async_session()
    async with session_factory() as db:
        service = ScanService(db)
        await service.run_scan(scan_run_id, repo_url, ref, token)


@celery_app.task(bind=True, max_retries=2)
def scan_repository(self, scan_run_id: str, repo_url: str, ref: str | None = None) -> None:
    """Celery task entrypoint for scans."""
    try:
        asyncio.run(scan_repository_async(scan_run_id, repo_url, ref, settings.github_token))
    except Exception as exc:
        logger.error("Scan task failed: %s", exc)
        raise self.retry(exc=exc, countdown=10)
