"""Embedding service for Qdrant vector storage."""

import logging
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Service for Qdrant vector operations."""

    def __init__(self, llm_service=None):
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self.collection_name = settings.qdrant_collection
        self.llm_service = llm_service  # Optional, for query string embedding

    async def ensure_collection(self, vector_size: int = 1536) -> None:
        """Ensure collection exists with correct configuration.

        Args:
            vector_size: Size of embedding vectors (1536 for text-embedding-3-small)
        """
        collections = await self.client.get_collections()
        collection_names = [c.name for c in collections.collections]

        if self.collection_name not in collection_names:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")

    async def upsert_points(
        self,
        repo_id: str,
        points: list[dict[str, Any]],
    ) -> None:
        """Upsert embedding points for a repository.

        Args:
            repo_id: Repository UUID
            points: List of point dicts with:
                - id: Point ID (str)
                - vector: Embedding vector
                - payload: Metadata (file_path, start_line, end_line, symbol_id, etc.)
        """
        await self.ensure_collection()

        qdrant_points = [
            PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload={
                    "repo_id": repo_id,
                    **point["payload"],
                },
            )
            for point in points
        ]

        await self.client.upsert(
            collection_name=self.collection_name,
            points=qdrant_points,
        )

    async def search(
        self,
        repo_id: str,
        query: str | list[float],
        limit: int = 15,
        score_threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors in a repository.

        Args:
            repo_id: Repository UUID
            query: Query string (will be embedded) or query vector
            limit: Maximum results
            score_threshold: Minimum similarity score

        Returns:
            List of results with:
                - file_path
                - start_line
                - end_line
                - symbol_id (optional)
                - symbol_name (optional)
                - score
        """
        await self.ensure_collection()

        # If query is a string, create embedding
        if isinstance(query, str):
            if not self.llm_service:
                raise ValueError("LLM service required for query string embedding")
            query_vector = await self.llm_service.create_embedding(query)
        else:
            query_vector = query

        results = await self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="repo_id",
                        match=MatchValue(value=repo_id),
                    )
                ]
            ),
            limit=limit,
            score_threshold=score_threshold,
        )

        return [
            {
                "file_path": hit.payload.get("file_path"),
                "start_line": hit.payload.get("start_line"),
                "end_line": hit.payload.get("end_line"),
                "symbol_id": hit.payload.get("symbol_id"),
                "symbol_name": hit.payload.get("symbol_name"),
                "score": hit.score,
            }
            for hit in results
        ]

    async def delete_repository(self, repo_id: str) -> None:
        """Delete all vectors for a repository.

        Args:
            repo_id: Repository UUID
        """
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="repo_id",
                        match=MatchValue(value=repo_id),
                    )
                ]
            ),
        )

