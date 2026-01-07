"""Integration test for scan -> findings -> fix pack flow."""

import os
import shutil
import subprocess
import tempfile
import uuid

import pytest
from sqlalchemy import text, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.scan import CoverageSummary, EvidenceSnippet, Finding, FindingInstance, FixPack
from app.models.user import User
from app.models.repository import Repository
from app.services.fix_pack_service import FixPackService
from app.services.scan_service import ScanService


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Set RUN_INTEGRATION_TESTS=1 to enable integration tests",
)
async def test_scan_flow_creates_findings_and_fix_pack():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    schema_name = f"test_{uuid.uuid4().hex[:8]}"
    engine = create_async_engine(database_url, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA {schema_name}"))
        await conn.execute(text(f"SET search_path TO {schema_name}"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    repo_dir = tempfile.mkdtemp(prefix="scan-test-")
    try:
        subprocess.run(["git", "init"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True)
        file_path = os.path.join(repo_dir, "app.py")
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(
                "\n".join(
                    [
                        "import requests",
                        "def handler():",
                        "    requests.get('https://example.com')",
                        "    eval('1+1')",
                        "    query = 'SELECT * FROM users'",
                        "    logger.info('email', user_email)",
                    ]
                )
            )
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "test"], cwd=repo_dir, check=True)
        commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_dir).decode().strip()

        async with session_factory() as db:
            await db.execute(text(f"SET search_path TO {schema_name}"))

            user = User(github_id=123, github_login="tester")
            db.add(user)
            await db.flush()

            repo = Repository(
                user_id=user.id,
                github_repo_id=123,
                github_installation_id=0,
                owner="local",
                name="sample",
                full_name="local/sample",
                private=False,
                default_branch="main",
                index_status="ready",
            )
            db.add(repo)
            await db.commit()
            await db.refresh(repo)

            scan_service = ScanService(db)
            scan_run, _ = await scan_service.create_scan_run(repo, commit_sha, "main", config={})

            async def fake_clone_repo(repo_url: str, branch: str | None = None, token: str | None = None):
                return repo_dir, commit_sha

            scan_service.clone_service.clone_repo = fake_clone_repo  # type: ignore[assignment]
            await scan_service.run_scan(str(scan_run.id), "https://github.com/local/sample.git", "main", None)

            findings = (
                await db.execute(
                    select(Finding).options(
                        selectinload(Finding.instances)
                        .selectinload(FindingInstance.evidence_snippet)
                        .selectinload(EvidenceSnippet.file_snapshot)
                    )
                )
            ).scalars().all()
            assert findings, "Expected findings to be created"
            assert all("coverage_factor" in f.confidence_rationale for f in findings)

            coverage = (await db.execute(select(CoverageSummary))).scalars().first()
            assert coverage is not None
            assert coverage.coverage_percentage >= 0

            scan_run = (await db.execute(select(scan_run.__class__).where(scan_run.__class__.id == scan_run.id))).scalar_one()
            scan_run.repo = repo
            fix_pack_service = FixPackService()
            prompt_pack = fix_pack_service.build_prompt_pack(scan_run, findings[:1], "generic")
            fix_pack = FixPack(
                scan_run_id=scan_run.id,
                title="Fix Pack",
                objective="Resolve finding",
                scope="single_finding",
                finding_ids=[str(findings[0].id)],
                human_explanation=fix_pack_service.build_human_explanation(findings[:1]),
                prompt_pack=prompt_pack,
                verification_checklist=prompt_pack["inputs"]["acceptance_criteria"],
            )
            db.add(fix_pack)
            await db.commit()

            stored_fix_pack = (await db.execute(select(FixPack))).scalars().first()
            assert stored_fix_pack is not None
            assert "prompt" in stored_fix_pack.prompt_pack
    finally:
        shutil.rmtree(repo_dir, ignore_errors=True)
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        await engine.dispose()
