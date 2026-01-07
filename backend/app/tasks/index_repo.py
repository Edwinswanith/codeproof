"""Repository indexing Celery task."""

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, FilterSelector, Filter, FieldCondition, MatchValue
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery_app
from app.config import get_settings
from app.models.file import File
from app.models.repository import Repository
from app.models.symbol import Symbol as SymbolModel
from app.services.clone_service import CloneService
from app.services.embedding_service import EmbeddingService
from app.services.parser_service import ParserService, Symbol

logger = logging.getLogger(__name__)
settings = get_settings()


def get_async_session() -> async_sessionmaker[AsyncSession]:
    """Create async session factory for use in tasks."""
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


def get_qdrant_client() -> QdrantClient:
    """Get Qdrant client instance."""
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
    )


async def ensure_qdrant_collection(client: QdrantClient, collection_name: str) -> None:
    """Ensure Qdrant collection exists with correct configuration."""
    collections = client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)

    if not exists:
        logger.info(f"Creating Qdrant collection: {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=EmbeddingService.EMBEDDING_DIMENSIONS,
                distance=Distance.COSINE,
            ),
        )


async def index_repository_async(repo_id: str) -> dict[str, Any]:
    """Async implementation of repository indexing."""
    session_factory = get_async_session()
    clone_service = CloneService()
    parser_service = ParserService()
    embedding_service = EmbeddingService()
    qdrant_client = get_qdrant_client()

    clone_path = None

    async with session_factory() as db:
        try:
            # 1. Get repository
            result = await db.execute(
                select(Repository).where(Repository.id == uuid.UUID(repo_id))
            )
            repo = result.scalar_one_or_none()

            if not repo:
                raise ValueError(f"Repository not found: {repo_id}")

            # Update status to indexing
            repo.index_status = "indexing"
            repo.index_error = None
            await db.commit()

            logger.info(f"Starting indexing for {repo.full_name}")

            # 2. Clone repository
            repo_url = f"https://github.com/{repo.full_name}.git"
            clone_path, commit_sha = await clone_service.clone_repo(
                repo_url=repo_url,
                branch=repo.default_branch,
                token=settings.github_token if settings.github_token else None,
            )
            logger.info(f"Cloned {repo.full_name} at {commit_sha[:8]}")

            # 3. Delete existing files and symbols for this repo
            await db.execute(delete(SymbolModel).where(SymbolModel.repo_id == repo.id))
            await db.execute(delete(File).where(File.repo_id == repo.id))
            await db.commit()

            # 4. Parse repository
            parse_result = parser_service.parse_repository(clone_path)
            logger.info(
                f"Parsed {parse_result.files_parsed} files, "
                f"{len(parse_result.symbols)} symbols"
            )

            # 5. Create File records and track file_id mapping
            file_id_map: dict[str, uuid.UUID] = {}
            files_created = 0

            # Get unique file paths from symbols
            file_paths = set(s.file_path for s in parse_result.symbols)

            for file_path in file_paths:
                full_path = os.path.join(clone_path, file_path)

                # Calculate file SHA
                try:
                    with open(full_path, 'rb') as f:
                        content = f.read()
                    file_sha = hashlib.sha1(content).hexdigest()
                    file_size = len(content)
                except Exception:
                    file_sha = "unknown"
                    file_size = 0

                # Detect language from extension
                ext = os.path.splitext(file_path)[1].lower()
                language = parser_service.SUPPORTED_LANGUAGES.get(ext, None)

                file_record = File(
                    repo_id=repo.id,
                    path=file_path,
                    sha=file_sha,
                    language=language,
                    size_bytes=file_size,
                )
                db.add(file_record)
                await db.flush()  # Get the ID
                file_id_map[file_path] = file_record.id
                files_created += 1

            await db.commit()
            logger.info(f"Created {files_created} file records")

            # 6. Create Symbol records
            symbol_id_map: dict[str, uuid.UUID] = {}
            symbols_created = 0

            for symbol in parse_result.symbols:
                file_id = file_id_map.get(symbol.file_path)
                if not file_id:
                    continue

                # Map symbol type
                kind = symbol.type
                if kind == "function":
                    kind = "function"
                elif kind == "method":
                    kind = "method"
                elif kind == "class":
                    kind = "class"
                else:
                    kind = symbol.type

                # Build search text
                search_parts = [symbol.name]
                if symbol.signature:
                    search_parts.append(symbol.signature)
                if symbol.docstring:
                    search_parts.append(symbol.docstring)
                search_text = " ".join(search_parts)

                symbol_record = SymbolModel(
                    repo_id=repo.id,
                    file_id=file_id,
                    name=symbol.name,
                    qualified_name=symbol.qualified_name,
                    kind=kind,
                    file_path=symbol.file_path,
                    start_line=symbol.line_start,
                    end_line=symbol.line_end,
                    signature=symbol.signature,
                    docstring=symbol.docstring,
                    visibility=symbol.visibility,
                    search_text=search_text,
                )
                db.add(symbol_record)
                await db.flush()
                symbol_id_map[symbol.qualified_name] = symbol_record.id
                symbols_created += 1

            await db.commit()
            logger.info(f"Created {symbols_created} symbol records")

            # 7. Generate embeddings
            chunks = embedding_service.chunk_code(parse_result.symbols, clone_path)
            chunks_with_embeddings = await embedding_service.generate_embeddings(chunks)

            embedded_count = sum(1 for c in chunks_with_embeddings if c.embedding)
            logger.info(f"Generated {embedded_count} embeddings")

            # 8. Store embeddings in Qdrant
            if embedded_count > 0:
                await ensure_qdrant_collection(qdrant_client, settings.qdrant_collection)

                # Delete existing points for this repo
                # Using a filter on repo_id payload field
                try:
                    qdrant_client.delete(
                        collection_name=settings.qdrant_collection,
                        points_selector=FilterSelector(
                            filter=Filter(
                                must=[
                                    FieldCondition(
                                        key="repo_id",
                                        match=MatchValue(value=str(repo.id))
                                    )
                                ]
                            )
                        ),
                    )
                except Exception as e:
                    logger.warning(f"Could not delete existing points: {e}")

                # Insert new points
                points = []
                for chunk in chunks_with_embeddings:
                    if not chunk.embedding:
                        continue

                    # Get symbol_id from our mapping
                    symbol_qname = f"{chunk.file_path}:{chunk.symbol_name}" if chunk.symbol_name else None
                    symbol_db_id = symbol_id_map.get(symbol_qname) if symbol_qname else None

                    # Generate UUID from chunk.id (MD5 hash) for Qdrant
                    # Pad with zeros to make a valid UUID
                    point_uuid = str(uuid.UUID(chunk.id.ljust(32, '0')[:32]))

                    point = PointStruct(
                        id=point_uuid,
                        vector=chunk.embedding,
                        payload={
                            "repo_id": str(repo.id),
                            "file_path": chunk.file_path,
                            "line_start": chunk.line_start,
                            "line_end": chunk.line_end,
                            "symbol_name": chunk.symbol_name,
                            "symbol_type": chunk.symbol_type,
                            "content": chunk.content[:2000],  # Truncate for payload
                            "symbol_id": str(symbol_db_id) if symbol_db_id else None,
                            "chunk_hash": chunk.id,  # Store original hash
                        },
                    )
                    points.append(point)

                # Batch upsert
                batch_size = 100
                for i in range(0, len(points), batch_size):
                    batch = points[i:i + batch_size]
                    qdrant_client.upsert(
                        collection_name=settings.qdrant_collection,
                        points=batch,
                    )

                logger.info(f"Stored {len(points)} embeddings in Qdrant")

            # 9. Update repository status
            repo.index_status = "ready"
            repo.index_error = None
            repo.last_indexed_at = datetime.utcnow()
            repo.last_indexed_commit = commit_sha
            repo.file_count = files_created
            repo.symbol_count = symbols_created
            await db.commit()

            logger.info(f"Indexing complete for {repo.full_name}")

            return {
                "status": "success",
                "repo_id": repo_id,
                "files": files_created,
                "symbols": symbols_created,
                "embeddings": embedded_count,
                "commit": commit_sha,
            }

        except Exception as e:
            logger.error(f"Indexing failed for {repo_id}: {e}")

            # Update status to failed
            try:
                result = await db.execute(
                    select(Repository).where(Repository.id == uuid.UUID(repo_id))
                )
                repo = result.scalar_one_or_none()
                if repo:
                    repo.index_status = "failed"
                    repo.index_error = str(e)[:1000]
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update repo status: {db_error}")

            raise

        finally:
            # Cleanup cloned repo
            if clone_path:
                clone_service.cleanup(clone_path)


@celery_app.task(bind=True, max_retries=3)
def index_repository(self, repo_id: str) -> dict[str, Any]:
    """Celery task to index a repository.

    Args:
        repo_id: UUID of the repository to index

    Returns:
        Dict with indexing results
    """
    try:
        return asyncio.run(index_repository_async(repo_id))
    except Exception as e:
        logger.error(f"Indexing task failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
