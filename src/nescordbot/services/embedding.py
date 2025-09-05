"""
EmbeddingService for Gemini API integration.

Provides text embedding functionality using Google's Gemini API
with caching, batch processing, and error handling capabilities.
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import BotConfig
from ..logger import get_logger


@dataclass
class EmbeddingResult:
    """Result of an embedding operation."""

    text: str
    embedding: List[float]
    model: str
    timestamp: float
    cached: bool = False


@dataclass
class EmbeddingCacheEntry:
    """Cache entry for embeddings."""

    text_hash: str
    embedding: List[float]
    model: str
    timestamp: float
    access_count: int = 0


class EmbeddingServiceError(Exception):
    """Base exception for EmbeddingService."""

    pass


class EmbeddingAPIError(EmbeddingServiceError):
    """API-related errors."""

    pass


class EmbeddingRateLimitError(EmbeddingServiceError):
    """Rate limit exceeded."""

    pass


class EmbeddingService:
    """
    Service for generating text embeddings using Gemini API.

    Features:
    - Text embedding generation using Gemini models
    - Local caching for efficiency
    - Batch processing support
    - Rate limiting and error handling
    - Usage monitoring
    """

    def __init__(self, config: BotConfig):
        """Initialize EmbeddingService.

        Args:
            config: Bot configuration containing API settings
        """
        self.config = config
        self.logger = get_logger(__name__)

        # Gemini API setup
        self._setup_gemini_client()

        # Model configuration
        self.model_name = "models/text-embedding-004"
        self.embedding_dimension = config.embedding_dimension

        # Caching
        self._cache: Dict[str, EmbeddingCacheEntry] = {}
        self._max_cache_size = 1000

        # Usage tracking
        self._request_count = 0
        self._token_usage = 0
        self._last_request_time = 0.0

        # Rate limiting (requests per minute)
        self._requests_per_minute = config.gemini_requests_per_minute
        self._request_times: List[float] = []

        self.logger.info("EmbeddingService initialized")

    def _setup_gemini_client(self) -> None:
        """Setup Gemini API client."""
        try:
            if not self.config.gemini_api_key:
                self.logger.warning("Gemini API key not configured")
                self._gemini_available = False
                return

            genai.configure(api_key=self.config.gemini_api_key)
            self._gemini_available = True

            self.logger.info("Gemini API client configured successfully")

        except Exception as e:
            self.logger.error(f"Failed to setup Gemini client: {e}")
            self._gemini_available = False

    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        return self._gemini_available

    def _get_text_hash(self, text: str) -> str:
        """Generate hash for text caching."""
        return hashlib.md5(f"{text}:{self.model_name}".encode()).hexdigest()

    def _get_cached_embedding(self, text: str) -> Optional[EmbeddingResult]:
        """Get cached embedding if available."""
        text_hash = self._get_text_hash(text)

        if text_hash in self._cache:
            entry = self._cache[text_hash]
            entry.access_count += 1

            return EmbeddingResult(
                text=text,
                embedding=entry.embedding,
                model=entry.model,
                timestamp=entry.timestamp,
                cached=True,
            )

        return None

    def _cache_embedding(self, text: str, embedding: List[float]) -> None:
        """Cache embedding result."""
        text_hash = self._get_text_hash(text)

        # Clean cache if needed
        if len(self._cache) >= self._max_cache_size:
            self._cleanup_cache()

        self._cache[text_hash] = EmbeddingCacheEntry(
            text_hash=text_hash, embedding=embedding, model=self.model_name, timestamp=time.time()
        )

    def _cleanup_cache(self) -> None:
        """Clean up cache by removing oldest entries."""
        # Sort by timestamp and remove oldest 20%
        entries = list(self._cache.items())
        entries.sort(key=lambda x: x[1].timestamp)

        remove_count = len(entries) // 5
        for i in range(remove_count):
            del self._cache[entries[i][0]]

        self.logger.debug(f"Cleaned up {remove_count} cache entries")

    def _check_rate_limit(self) -> None:
        """Check and enforce rate limits."""
        current_time = time.time()

        # Clean old request times (older than 1 minute)
        self._request_times = [t for t in self._request_times if current_time - t < 60]

        # Check if rate limit exceeded
        if len(self._request_times) >= self._requests_per_minute:
            wait_time = 60 - (current_time - self._request_times[0])
            if wait_time > 0:
                raise EmbeddingRateLimitError(f"Rate limit exceeded. Wait {wait_time:.1f} seconds.")

        # Record current request
        self._request_times.append(current_time)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((EmbeddingAPIError,)),
        reraise=True,
    )
    async def _generate_embedding_api(self, text: str) -> List[float]:
        """Generate embedding using Gemini API with retry logic."""
        try:
            self._check_rate_limit()

            # Generate embedding
            response = genai.embed_content(
                model=self.model_name, content=text, task_type="RETRIEVAL_DOCUMENT"
            )

            if not response.get("embedding"):
                raise EmbeddingAPIError("Empty embedding received")

            embedding = response["embedding"]

            # Update usage tracking
            self._request_count += 1
            self._token_usage += len(text.split())  # Rough token estimate
            self._last_request_time = time.time()

            return embedding  # type: ignore[no-any-return]

        except Exception as e:
            if "rate_limit" in str(e).lower() or "quota" in str(e).lower():
                raise EmbeddingRateLimitError(f"Gemini API rate limit: {e}")
            else:
                raise EmbeddingAPIError(f"Gemini API error: {e}")

    async def generate_embedding(self, text: str) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            EmbeddingResult with embedding vector

        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        if not text or not text.strip():
            raise EmbeddingServiceError("Empty text provided")

        if not self.is_available():
            raise EmbeddingServiceError("Gemini API not available")

        text = text.strip()

        # Check cache first
        cached_result = self._get_cached_embedding(text)
        if cached_result:
            self.logger.debug(f"Using cached embedding for text: {text[:50]}...")
            return cached_result

        try:
            # Generate new embedding
            self.logger.debug(f"Generating embedding for text: {text[:50]}...")

            embedding = await self._generate_embedding_api(text)

            # Cache result
            self._cache_embedding(text, embedding)

            result = EmbeddingResult(
                text=text,
                embedding=embedding,
                model=self.model_name,
                timestamp=time.time(),
                cached=False,
            )

            self.logger.debug(f"Generated embedding (dim={len(embedding)})")
            return result

        except Exception as e:
            self.logger.error(f"Failed to generate embedding: {e}")
            raise

    async def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 10
    ) -> List[EmbeddingResult]:
        """
        Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process per batch

        Returns:
            List of EmbeddingResult objects
        """
        if not texts:
            return []

        if not self.is_available():
            raise EmbeddingServiceError("Gemini API not available")

        results = []

        # Process in batches to avoid rate limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            self.logger.debug(f"Processing batch {i//batch_size + 1}: {len(batch)} texts")

            # Process batch items concurrently but with limit
            batch_tasks = [self.generate_embedding(text) for text in batch]

            try:
                batch_results = await asyncio.gather(*batch_tasks)
                results.extend(batch_results)

                # Small delay between batches
                if i + batch_size < len(texts):
                    await asyncio.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Batch processing failed at batch {i//batch_size + 1}: {e}")
                raise

        self.logger.info(f"Generated embeddings for {len(results)} texts")
        return results

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "api_available": self.is_available(),
            "request_count": self._request_count,
            "token_usage": self._token_usage,
            "cache_size": len(self._cache),
            "cache_hit_ratio": self._calculate_cache_hit_ratio(),
            "last_request_time": self._last_request_time,
            "rate_limit_rpm": self._requests_per_minute,
            "current_rpm": len([t for t in self._request_times if time.time() - t < 60]),
        }

    def _calculate_cache_hit_ratio(self) -> float:
        """Calculate cache hit ratio."""
        total_accesses = sum(entry.access_count for entry in self._cache.values())
        if total_accesses == 0:
            return 0.0

        cache_hits = sum(entry.access_count - 1 for entry in self._cache.values())
        return cache_hits / total_accesses

    def clear_cache(self) -> None:
        """Clear embedding cache."""
        self._cache.clear()
        self.logger.info("Embedding cache cleared")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        health_status = {
            "service": "EmbeddingService",
            "status": "healthy",
            "timestamp": time.time(),
            "api_available": self.is_available(),
        }

        if self.is_available():
            try:
                # Test embedding generation
                test_result = await self.generate_embedding("Health check test")
                health_status.update(
                    {
                        "api_test": "success",
                        "embedding_dimension": len(test_result.embedding),
                        "response_time": time.time() - test_result.timestamp,
                    }
                )
            except Exception as e:
                health_status.update({"status": "degraded", "api_test": "failed", "error": str(e)})
        else:
            health_status["status"] = "unavailable"

        health_status.update(self.get_usage_stats())
        return health_status
