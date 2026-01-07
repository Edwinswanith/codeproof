"""LLM service for Google Gemini integration with resilience patterns."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking."""

    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = "closed"  # closed, open, half-open
    # Thresholds
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds before trying again
    half_open_max_calls: int = 1
    half_open_call_count: int = 0


class LLMServiceError(Exception):
    """Base exception for LLM service errors."""

    pass


class LLMRateLimitError(LLMServiceError):
    """Rate limit exceeded."""

    pass


class LLMCircuitOpenError(LLMServiceError):
    """Circuit breaker is open."""

    pass


class LLMService:
    """Service for Google Gemini LLM operations with resilience patterns.

    Implements:
    - Exponential backoff retry for transient failures
    - Hard timeouts to prevent hanging requests
    - Circuit breaker to stop hammering a degraded provider
    """

    # Retry configuration
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds
    MAX_DELAY = 30.0  # seconds
    TIMEOUT_SECONDS = 60.0  # hard timeout per request

    # Retryable error patterns
    RETRYABLE_ERRORS = (
        "rate limit",
        "quota exceeded",
        "503",
        "429",
        "temporarily unavailable",
        "overloaded",
        "timeout",
    )

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model
        self.embedding_model = settings.gemini_embedding_model
        self._circuit = CircuitBreakerState()

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable (transient)."""
        error_str = str(error).lower()
        return any(pattern in error_str for pattern in self.RETRYABLE_ERRORS)

    def _check_circuit(self) -> None:
        """Check circuit breaker state and raise if open."""
        now = time.time()

        if self._circuit.state == "open":
            # Check if recovery timeout has passed
            if now - self._circuit.last_failure_time >= self._circuit.recovery_timeout:
                logger.info("Circuit breaker transitioning to half-open")
                self._circuit.state = "half-open"
                self._circuit.half_open_call_count = 0
            else:
                raise LLMCircuitOpenError(
                    f"Circuit breaker is open. Retry after "
                    f"{self._circuit.recovery_timeout - (now - self._circuit.last_failure_time):.1f}s"
                )

        if self._circuit.state == "half-open":
            if self._circuit.half_open_call_count >= self._circuit.half_open_max_calls:
                raise LLMCircuitOpenError("Circuit breaker is half-open, max test calls reached")
            self._circuit.half_open_call_count += 1

    def _record_success(self) -> None:
        """Record successful call, potentially closing circuit."""
        if self._circuit.state == "half-open":
            logger.info("Circuit breaker closing after successful half-open call")
            self._circuit.state = "closed"
        self._circuit.failure_count = 0

    def _record_failure(self) -> None:
        """Record failed call, potentially opening circuit."""
        self._circuit.failure_count += 1
        self._circuit.last_failure_time = time.time()

        if self._circuit.state == "half-open":
            logger.warning("Circuit breaker re-opening after failed half-open call")
            self._circuit.state = "open"
        elif self._circuit.failure_count >= self._circuit.failure_threshold:
            logger.warning(
                f"Circuit breaker opening after {self._circuit.failure_count} consecutive failures"
            )
            self._circuit.state = "open"

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text completion using Gemini with retry and circuit breaker.

        Args:
            prompt: User prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_prompt: Optional system prompt

        Returns:
            Generated text

        Raises:
            LLMCircuitOpenError: If circuit breaker is open
            LLMServiceError: If all retries exhausted
        """
        self._check_circuit()

        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                config = types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    system_instruction=system_prompt,
                )

                # Wrap in timeout
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=self.TIMEOUT_SECONDS,
                )
                self._record_success()
                return response.text or ""

            except asyncio.TimeoutError:
                last_error = LLMServiceError(f"Request timed out after {self.TIMEOUT_SECONDS}s")
                logger.warning(f"LLM request timeout on attempt {attempt + 1}")
                self._record_failure()

            except Exception as e:
                last_error = e
                logger.warning(f"LLM generation failed on attempt {attempt + 1}: {e}")

                if not self._is_retryable_error(e):
                    self._record_failure()
                    raise LLMServiceError(f"Non-retryable error: {e}") from e

                self._record_failure()

            # Exponential backoff before retry
            if attempt < self.MAX_RETRIES - 1:
                delay = min(self.BASE_DELAY * (2**attempt), self.MAX_DELAY)
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        raise LLMServiceError(f"All {self.MAX_RETRIES} retries exhausted. Last error: {last_error}")

    async def generate_with_usage(
        self,
        prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        system_prompt: str | None = None,
    ) -> tuple[str, dict[str, int]]:
        """Generate text and return usage stats with retry and circuit breaker.

        Returns:
            Tuple of (generated_text, usage_dict) where usage_dict contains:
            - input_tokens
            - output_tokens

        Raises:
            LLMCircuitOpenError: If circuit breaker is open
            LLMServiceError: If all retries exhausted
        """
        self._check_circuit()

        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                config = types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    system_instruction=system_prompt,
                )

                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config=config,
                    ),
                    timeout=self.TIMEOUT_SECONDS,
                )

                self._record_success()

                # Extract usage metadata from response
                usage_metadata = response.usage_metadata
                return (
                    response.text or "",
                    {
                        "input_tokens": usage_metadata.prompt_token_count if usage_metadata else 0,
                        "output_tokens": (
                            usage_metadata.candidates_token_count if usage_metadata else 0
                        ),
                    },
                )

            except asyncio.TimeoutError:
                last_error = LLMServiceError(f"Request timed out after {self.TIMEOUT_SECONDS}s")
                logger.warning(f"LLM request timeout on attempt {attempt + 1}")
                self._record_failure()

            except Exception as e:
                last_error = e
                logger.warning(f"LLM generation failed on attempt {attempt + 1}: {e}")

                if not self._is_retryable_error(e):
                    self._record_failure()
                    raise LLMServiceError(f"Non-retryable error: {e}") from e

                self._record_failure()

            # Exponential backoff before retry
            if attempt < self.MAX_RETRIES - 1:
                delay = min(self.BASE_DELAY * (2**attempt), self.MAX_DELAY)
                logger.info(f"Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)

        raise LLMServiceError(f"All {self.MAX_RETRIES} retries exhausted. Last error: {last_error}")

    async def create_embedding(self, text: str) -> list[float]:
        """Create embedding vector for text with retry.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            LLMServiceError: If all retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.embed_content,
                        model=self.embedding_model,
                        contents=text,
                    ),
                    timeout=self.TIMEOUT_SECONDS,
                )
                return list(response.embeddings[0].values)

            except asyncio.TimeoutError:
                last_error = LLMServiceError(f"Embedding timed out after {self.TIMEOUT_SECONDS}s")
                logger.warning(f"Embedding timeout on attempt {attempt + 1}")

            except Exception as e:
                last_error = e
                logger.warning(f"Embedding creation failed on attempt {attempt + 1}: {e}")

                if not self._is_retryable_error(e):
                    raise LLMServiceError(f"Non-retryable error: {e}") from e

            if attempt < self.MAX_RETRIES - 1:
                delay = min(self.BASE_DELAY * (2**attempt), self.MAX_DELAY)
                await asyncio.sleep(delay)

        raise LLMServiceError(f"Embedding failed after {self.MAX_RETRIES} retries: {last_error}")

    async def create_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Create embeddings for multiple texts with retry.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors

        Raises:
            LLMServiceError: If all retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.embed_content,
                        model=self.embedding_model,
                        contents=texts,
                    ),
                    timeout=self.TIMEOUT_SECONDS * 2,  # Longer timeout for batch
                )
                return [list(emb.values) for emb in response.embeddings]

            except asyncio.TimeoutError:
                last_error = LLMServiceError("Batch embedding timed out")
                logger.warning(f"Batch embedding timeout on attempt {attempt + 1}")

            except Exception as e:
                last_error = e
                logger.warning(f"Batch embedding failed on attempt {attempt + 1}: {e}")

                if not self._is_retryable_error(e):
                    raise LLMServiceError(f"Non-retryable error: {e}") from e

            if attempt < self.MAX_RETRIES - 1:
                delay = min(self.BASE_DELAY * (2**attempt), self.MAX_DELAY)
                await asyncio.sleep(delay)

        raise LLMServiceError(f"Batch embedding failed after {self.MAX_RETRIES} retries: {last_error}")
