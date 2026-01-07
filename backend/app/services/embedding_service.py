"""Service for generating and searching code embeddings."""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Optional
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CodeChunk:
    """A chunk of code for embedding."""
    id: str
    file_path: str
    line_start: int
    line_end: int
    symbol_name: Optional[str]
    symbol_type: Optional[str]
    content: str
    embedding: Optional[list[float]] = None


class EmbeddingService:
    """Service for generating and searching code embeddings."""

    CHUNK_MAX_TOKENS = 500
    EMBEDDING_DIMENSIONS = 768  # Gemini embedding dimension
    BATCH_SIZE = 20  # Embed this many chunks at once

    def __init__(self, llm_service=None):
        """Initialize embedding service."""
        self.llm_service = llm_service
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initialize Gemini client for embeddings."""
        try:
            from google import genai
            if settings.gemini_api_key:
                self.client = genai.Client(api_key=settings.gemini_api_key)
                logger.info("Initialized Gemini embedding client")
            else:
                logger.warning("GEMINI_API_KEY not set, embeddings disabled")
        except ImportError:
            logger.warning("google-genai not installed, embeddings disabled")

    def chunk_code(
        self,
        symbols: list,  # list of Symbol from parser_service
        repo_path: str
    ) -> list[CodeChunk]:
        """Create chunks from symbols. Each symbol = one chunk."""
        chunks = []

        for symbol in symbols:
            # Skip symbols without bodies (just declarations)
            if not symbol.body and not symbol.docstring:
                continue

            # Build content for embedding
            content_parts = []
            
            # Add context
            content_parts.append(f"# File: {symbol.file_path}")
            content_parts.append(f"# Type: {symbol.type}")
            if symbol.parent:
                content_parts.append(f"# Parent: {symbol.parent}")
            
            # Add signature if available
            if symbol.signature:
                content_parts.append(symbol.signature)
            
            # Add docstring if available
            if symbol.docstring:
                content_parts.append(f'"""{symbol.docstring}"""')
            
            # Add body or truncate if too long
            if symbol.body:
                body = symbol.body
                # Rough token estimate (4 chars per token)
                if len(body) > self.CHUNK_MAX_TOKENS * 4:
                    body = body[:self.CHUNK_MAX_TOKENS * 4] + "\n# ... truncated ..."
                content_parts.append(body)

            content = "\n".join(content_parts)
            
            # Generate unique ID
            chunk_id = hashlib.md5(
                f"{symbol.file_path}:{symbol.qualified_name}".encode()
            ).hexdigest()[:12]

            chunks.append(CodeChunk(
                id=chunk_id,
                file_path=symbol.file_path,
                line_start=symbol.line_start,
                line_end=symbol.line_end,
                symbol_name=symbol.name,
                symbol_type=symbol.type,
                content=content,
                embedding=None,
            ))

        logger.info(f"Created {len(chunks)} chunks from {len(symbols)} symbols")
        return chunks

    async def generate_embeddings(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Generate embeddings for chunks using Gemini."""
        if not self.client:
            logger.warning("Embedding client not initialized, skipping embeddings")
            return chunks

        total = len(chunks)
        processed = 0

        # Process in batches
        for i in range(0, len(chunks), self.BATCH_SIZE):
            batch = chunks[i:i + self.BATCH_SIZE]
            texts = [chunk.content for chunk in batch]

            try:
                # Use Gemini's embedding API
                embeddings = await self._embed_batch(texts)
                
                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = embedding
                
                processed += len(batch)
                logger.info(f"Generated embeddings: {processed}/{total}")

            except Exception as e:
                logger.error(f"Failed to generate embeddings for batch: {e}")
                # Continue with other batches

        embedded_count = sum(1 for c in chunks if c.embedding is not None)
        logger.info(f"Embedded {embedded_count}/{total} chunks")
        return chunks

    async def _embed_batch(self, texts: list[str], max_retries: int = 3) -> list[list[float]]:
        """Generate embeddings for a batch of texts with retry logic."""
        last_error = None

        for attempt in range(max_retries):
            try:
                # Use Gemini embedding model
                result = await asyncio.to_thread(
                    self.client.models.embed_content,
                    model=settings.gemini_embedding_model,
                    contents=texts,
                )

                # Extract embeddings from result
                if hasattr(result, 'embeddings'):
                    return [e.values for e in result.embeddings]
                else:
                    logger.warning(f"Unexpected embedding result format: {type(result)}")
                    return [None] * len(texts)

            except Exception as e:
                last_error = e
                logger.warning(f"Embedding API error (attempt {attempt + 1}/{max_retries}): {e}")

                # Check if retryable (500 errors, rate limits)
                error_str = str(e).lower()
                is_retryable = any(x in error_str for x in ["500", "503", "429", "rate", "internal", "overloaded"])

                if is_retryable and attempt < max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                elif not is_retryable:
                    raise

        logger.error(f"Embedding failed after {max_retries} retries: {last_error}")
        raise last_error

    async def embed_query(self, query: str) -> Optional[list[float]]:
        """Generate embedding for a search query."""
        if not self.client:
            return None

        try:
            result = await asyncio.to_thread(
                self.client.models.embed_content,
                model=settings.gemini_embedding_model,
                contents=[query],
            )
            
            if hasattr(result, 'embeddings') and result.embeddings:
                return result.embeddings[0].values
            return None
            
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return None

    def search(
        self,
        query: str,
        chunks: list[CodeChunk],
        top_k: int = 10,
        query_embedding: Optional[list[float]] = None
    ) -> list[tuple[CodeChunk, float]]:
        """
        Search chunks by semantic similarity.
        Returns (chunk, score) pairs sorted by score descending.
        """
        if query_embedding is None:
            # Fall back to keyword search
            return self._keyword_search(query, chunks, top_k)

        # Filter chunks with embeddings
        embedded_chunks = [c for c in chunks if c.embedding is not None]
        if not embedded_chunks:
            return self._keyword_search(query, chunks, top_k)

        # Calculate cosine similarity
        scores = []
        query_vec = np.array(query_embedding)
        query_norm = np.linalg.norm(query_vec)

        for chunk in embedded_chunks:
            chunk_vec = np.array(chunk.embedding)
            chunk_norm = np.linalg.norm(chunk_vec)
            
            if query_norm > 0 and chunk_norm > 0:
                similarity = np.dot(query_vec, chunk_vec) / (query_norm * chunk_norm)
            else:
                similarity = 0.0
            
            scores.append((chunk, float(similarity)))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    async def search_repo(
        self,
        repo_id: str,
        question: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search embeddings by repo/question. Placeholder for vector store."""
        logger.warning(
            "Vector search is not configured for repo_id=%s; returning no results.",
            repo_id,
        )
        _ = question, limit
        return []

    def _keyword_search(
        self,
        query: str,
        chunks: list[CodeChunk],
        top_k: int
    ) -> list[tuple[CodeChunk, float]]:
        """Fallback keyword-based search."""
        query_words = set(query.lower().split())
        scores = []

        for chunk in chunks:
            content_lower = chunk.content.lower()
            
            # Simple scoring: count matching words
            matches = sum(1 for word in query_words if word in content_lower)
            
            # Boost if symbol name matches
            if chunk.symbol_name and any(
                word in chunk.symbol_name.lower() for word in query_words
            ):
                matches += 2

            if matches > 0:
                score = matches / len(query_words)
                scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    async def search_async(
        self,
        query: str,
        chunks: list[CodeChunk],
        top_k: int = 10
    ) -> list[tuple[CodeChunk, float]]:
        """Async search with query embedding."""
        query_embedding = await self.embed_query(query)
        return self.search(query, chunks, top_k, query_embedding)

    def get_similar_chunks(
        self,
        chunk: CodeChunk,
        all_chunks: list[CodeChunk],
        top_k: int = 5
    ) -> list[tuple[CodeChunk, float]]:
        """Find chunks similar to a given chunk."""
        if not chunk.embedding:
            return []

        return self.search("", all_chunks, top_k, chunk.embedding)
