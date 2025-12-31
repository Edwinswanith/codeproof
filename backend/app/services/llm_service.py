"""LLM service for Google Gemini integration."""

import asyncio
import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """Service for Google Gemini LLM operations."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model
        self.embedding_model = settings.gemini_embedding_model

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text completion using Gemini.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt

        Returns:
            Generated text
        """
        try:
            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                system_instruction=system_prompt,
            )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    async def generate_with_usage(
        self,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        system_prompt: str | None = None,
    ) -> tuple[str, dict[str, int]]:
        """Generate text and return usage stats.

        Returns:
            Tuple of (generated_text, usage_dict) where usage_dict contains:
            - input_tokens
            - output_tokens
        """
        try:
            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                system_instruction=system_prompt,
            )

            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=config,
            )

            # Extract usage metadata from response
            usage_metadata = response.usage_metadata
            return (
                response.text or "",
                {
                    "input_tokens": usage_metadata.prompt_token_count if usage_metadata else 0,
                    "output_tokens": usage_metadata.candidates_token_count if usage_metadata else 0,
                },
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    async def create_embedding(self, text: str) -> list[float]:
        """Create embedding vector for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        try:
            response = await asyncio.to_thread(
                self.client.models.embed_content,
                model=self.embedding_model,
                contents=text,
            )
            return list(response.embeddings[0].values)
        except Exception as e:
            logger.error(f"Embedding creation failed: {e}")
            raise

    async def create_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        try:
            response = await asyncio.to_thread(
                self.client.models.embed_content,
                model=self.embedding_model,
                contents=texts,
            )
            return [list(emb.values) for emb in response.embeddings]
        except Exception as e:
            logger.error(f"Batch embedding creation failed: {e}")
            raise
