#!/usr/bin/env python3
"""Test script to verify the full indexing pipeline with ever-gauzy repo."""

import asyncio
import sys
import uuid
from datetime import datetime

# Add backend to path
sys.path.insert(0, "/Users/edwinswanith/Documents/code_review/backend")

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from qdrant_client import QdrantClient

from app.config import get_settings
from app.models.user import User
from app.models.repository import Repository
from app.models.file import File
from app.models.symbol import Symbol
from app.database import Base

settings = get_settings()


async def setup_test_data(db: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Create test user and repository."""

    # Check if test user exists
    result = await db.execute(
        select(User).where(User.email == "test@codeproof.dev")
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email="test@codeproof.dev",
            github_id=12345678,
            github_login="testuser",
            avatar_url="https://github.com/ghost.png",
        )
        db.add(user)
        await db.flush()
        print(f"Created test user: {user.id}")
    else:
        print(f"Using existing test user: {user.id}")

    # Check if ever-gauzy repo exists
    result = await db.execute(
        select(Repository)
        .where(Repository.user_id == user.id)
        .where(Repository.full_name == "ever-co/ever-gauzy")
    )
    repo = result.scalar_one_or_none()

    if not repo:
        repo = Repository(
            user_id=user.id,
            github_repo_id=123456789,
            github_installation_id=0,  # Not using GitHub App
            owner="ever-co",
            name="ever-gauzy",
            full_name="ever-co/ever-gauzy",
            default_branch="develop",
            private=False,
            detected_framework="typescript",
            index_status="pending",
        )
        db.add(repo)
        await db.flush()
        print(f"Created test repo: {repo.id}")
    else:
        print(f"Using existing repo: {repo.id}")
        # Reset status for re-indexing
        repo.index_status = "pending"
        repo.index_error = None

    await db.commit()
    return user.id, repo.id


async def run_indexing(repo_id: uuid.UUID) -> dict:
    """Run the indexing task directly (without Celery)."""
    from app.tasks.index_repo import index_repository_async

    print(f"\nStarting indexing for repo {repo_id}...")
    print("This may take several minutes for a large repo like ever-gauzy...")

    result = await index_repository_async(str(repo_id))
    return result


async def verify_results(db: AsyncSession, repo_id: uuid.UUID) -> None:
    """Verify indexing results in database and Qdrant."""

    # Check repository status
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id)
    )
    repo = result.scalar_one()

    print(f"\n=== Repository Status ===")
    print(f"Status: {repo.index_status}")
    print(f"Error: {repo.index_error or 'None'}")
    print(f"Last indexed: {repo.last_indexed_at}")
    print(f"Commit: {repo.last_indexed_commit}")
    print(f"Files: {repo.file_count}")
    print(f"Symbols: {repo.symbol_count}")

    # Check files
    result = await db.execute(
        select(File).where(File.repo_id == repo_id).limit(10)
    )
    files = result.scalars().all()

    print(f"\n=== Sample Files (first 10) ===")
    for f in files:
        print(f"  {f.path} ({f.language})")

    # Check symbols
    result = await db.execute(
        select(Symbol).where(Symbol.repo_id == repo_id).limit(10)
    )
    symbols = result.scalars().all()

    print(f"\n=== Sample Symbols (first 10) ===")
    for s in symbols:
        print(f"  [{s.kind}] {s.name} @ {s.file_path}:{s.start_line}")

    # Check Qdrant
    qdrant = QdrantClient(url=settings.qdrant_url)

    try:
        collection_info = qdrant.get_collection(settings.qdrant_collection)
        print(f"\n=== Qdrant Collection ===")
        print(f"Collection: {settings.qdrant_collection}")
        print(f"Points count: {collection_info.points_count}")

        # Search for a sample query
        print(f"\n=== Sample Vector Search ===")

        # Get embedding for a test query
        from app.services.embedding_service import EmbeddingService
        embedding_service = EmbeddingService()

        test_query = "employee service"
        query_embedding = await embedding_service.embed_query(test_query)

        if query_embedding:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            results = qdrant.query_points(
                collection_name=settings.qdrant_collection,
                query=query_embedding,
                query_filter=Filter(
                    must=[
                        FieldCondition(key="repo_id", match=MatchValue(value=str(repo_id)))
                    ]
                ),
                limit=5,
            ).points

            print(f"Query: '{test_query}'")
            print(f"Results:")
            for r in results:
                print(f"  Score: {r.score:.4f}")
                print(f"    File: {r.payload.get('file_path')}")
                print(f"    Symbol: {r.payload.get('symbol_name')}")
                print(f"    Lines: {r.payload.get('line_start')}-{r.payload.get('line_end')}")
        else:
            print("Could not generate query embedding")

    except Exception as e:
        print(f"Qdrant check failed: {e}")


async def main():
    """Main test function."""
    print("=" * 60)
    print("CodeProof Indexing Pipeline Test")
    print("Repository: ever-co/ever-gauzy")
    print("=" * 60)

    # Create engine and session
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        # Setup test data
        user_id, repo_id = await setup_test_data(db)

        # Run indexing
        try:
            result = await run_indexing(repo_id)
            print(f"\n=== Indexing Result ===")
            print(f"Status: {result.get('status')}")
            print(f"Files: {result.get('files')}")
            print(f"Symbols: {result.get('symbols')}")
            print(f"Embeddings: {result.get('embeddings')}")
            print(f"Commit: {result.get('commit')}")
        except Exception as e:
            print(f"\nIndexing failed: {e}")
            import traceback
            traceback.print_exc()

        # Verify results
        await verify_results(db, repo_id)

    await engine.dispose()
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
