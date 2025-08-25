"""
Tests for EmbeddingService.
"""

import asyncio
import os
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.embedding import (
    EmbeddingAPIError,
    EmbeddingRateLimitError,
    EmbeddingResult,
    EmbeddingService,
    EmbeddingServiceError,
)


class TestEmbeddingService:
    """Test cases for EmbeddingService."""

    # Test constants
    TEST_DISCORD_TOKEN = "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234"
    TEST_OPENAI_API_KEY = "sk-test1234567890abcdef1234567890abcdef1234567890ab"
    TEST_GEMINI_API_KEY = "AIza-test1234567890abcdef1234567890abcdef12345678"

    @pytest.fixture
    def config_with_gemini(self):
        """Create config with Gemini API key."""
        return BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
            gemini_api_key=self.TEST_GEMINI_API_KEY,
            gemini_requests_per_minute=15,
            embedding_dimension=768,
        )

    @pytest.fixture
    def config_no_gemini(self):
        """Create config without Gemini API key."""
        return BotConfig(
            discord_token=self.TEST_DISCORD_TOKEN,
            openai_api_key=self.TEST_OPENAI_API_KEY,
        )

    @pytest.fixture
    def service_with_api(self, config_with_gemini):
        """Create service with mocked Gemini API."""
        with patch("google.generativeai.configure"):
            service = EmbeddingService(config_with_gemini)
            service._gemini_available = True
            return service

    @pytest.fixture
    def service_no_api(self, config_no_gemini):
        """Create service without API key."""
        service = EmbeddingService(config_no_gemini)
        return service

    def test_init_with_gemini_api_key(self, config_with_gemini):
        """Test initialization with Gemini API key."""
        with patch("google.generativeai.configure") as mock_configure:
            service = EmbeddingService(config_with_gemini)
            mock_configure.assert_called_once_with(api_key=self.TEST_GEMINI_API_KEY)
            assert service.is_available()

    def test_init_without_gemini_api_key(self, config_no_gemini):
        """Test initialization without Gemini API key."""
        service = EmbeddingService(config_no_gemini)
        assert not service.is_available()

    def test_text_hash_generation(self, service_with_api):
        """Test text hash generation for caching."""
        text1 = "Hello world"
        text2 = "Hello world"
        text3 = "Different text"

        hash1 = service_with_api._get_text_hash(text1)
        hash2 = service_with_api._get_text_hash(text2)
        hash3 = service_with_api._get_text_hash(text3)

        assert hash1 == hash2  # Same text should have same hash
        assert hash1 != hash3  # Different text should have different hash
        assert len(hash1) == 32  # MD5 hash length

    def test_cache_operations(self, service_with_api):
        """Test embedding caching operations."""
        text = "Test text for caching"
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Initially no cache
        cached_result = service_with_api._get_cached_embedding(text)
        assert cached_result is None

        # Cache embedding
        service_with_api._cache_embedding(text, embedding)

        # Should be cached now
        cached_result = service_with_api._get_cached_embedding(text)
        assert cached_result is not None
        assert cached_result.text == text
        assert cached_result.embedding == embedding
        assert cached_result.cached is True

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, service_with_api):
        """Test successful embedding generation."""
        test_text = "This is a test text for embedding"
        expected_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

        # Mock Gemini API
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = expected_embedding
        mock_response.get.return_value = expected_embedding

        with patch("google.generativeai.embed_content", return_value=mock_response):
            result = await service_with_api.generate_embedding(test_text)

            assert isinstance(result, EmbeddingResult)
            assert result.text == test_text
            assert result.embedding == expected_embedding
            assert result.model == service_with_api.model_name
            assert not result.cached

    @pytest.mark.asyncio
    async def test_generate_embedding_cached(self, service_with_api):
        """Test embedding generation with cache hit."""
        test_text = "Cached text"
        expected_embedding = [0.1, 0.2, 0.3]

        # Pre-populate cache
        service_with_api._cache_embedding(test_text, expected_embedding)

        result = await service_with_api.generate_embedding(test_text)

        assert result.text == test_text
        assert result.embedding == expected_embedding
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_generate_embedding_no_api(self, service_no_api):
        """Test embedding generation without API."""
        with pytest.raises(EmbeddingServiceError) as exc_info:
            await service_no_api.generate_embedding("test text")

        assert "not available" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self, service_with_api):
        """Test embedding generation with empty text."""
        with pytest.raises(EmbeddingServiceError) as exc_info:
            await service_with_api.generate_embedding("")

        assert "Empty text" in str(exc_info.value)

        with pytest.raises(EmbeddingServiceError) as exc_info:
            await service_with_api.generate_embedding("   ")

        assert "Empty text" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embedding_api_error(self, service_with_api):
        """Test API error handling."""
        with patch("google.generativeai.embed_content", side_effect=Exception("API Error")):
            with pytest.raises(EmbeddingAPIError) as exc_info:
                await service_with_api.generate_embedding("test text")

            assert "Gemini API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit(self, service_with_api):
        """Test rate limit error handling."""
        with patch(
            "google.generativeai.embed_content", side_effect=Exception("rate_limit_exceeded")
        ):
            with pytest.raises(EmbeddingRateLimitError) as exc_info:
                await service_with_api.generate_embedding("test text")

            assert "rate limit" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch(self, service_with_api):
        """Test batch embedding generation."""
        texts = ["Text 1", "Text 2", "Text 3"]
        expected_embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]

        mock_responses = [MagicMock() for _ in texts]
        for i, response in enumerate(mock_responses):
            response.__getitem__.return_value = expected_embeddings[i]
            response.get.return_value = expected_embeddings[i]

        with patch("google.generativeai.embed_content", side_effect=mock_responses):
            results = await service_with_api.generate_embeddings_batch(texts)

            assert len(results) == len(texts)
            for i, result in enumerate(results):
                assert result.text == texts[i]
                assert result.embedding == expected_embeddings[i]

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self, service_with_api):
        """Test batch embedding with empty list."""
        results = await service_with_api.generate_embeddings_batch([])
        assert results == []

    def test_rate_limiting(self, service_with_api):
        """Test rate limiting functionality."""
        # Set low rate limit for testing
        service_with_api._requests_per_minute = 2

        # First request should pass
        service_with_api._check_rate_limit()

        # Second request should pass
        service_with_api._check_rate_limit()

        # Third request should raise rate limit error
        with pytest.raises(EmbeddingRateLimitError):
            service_with_api._check_rate_limit()

    def test_cache_cleanup(self, service_with_api):
        """Test cache cleanup functionality."""
        # Set small cache size for testing
        service_with_api._max_cache_size = 5

        # Fill cache beyond limit
        for i in range(7):
            text = f"Text {i}"
            embedding = [float(i)] * 3
            service_with_api._cache_embedding(text, embedding)

        # Cache should be cleaned up
        assert len(service_with_api._cache) <= service_with_api._max_cache_size

    def test_usage_stats(self, service_with_api):
        """Test usage statistics."""
        # Generate some usage
        service_with_api._request_count = 5
        service_with_api._token_usage = 100

        stats = service_with_api.get_usage_stats()

        assert stats["api_available"] is True
        assert stats["request_count"] == 5
        assert stats["token_usage"] == 100
        assert "cache_size" in stats
        assert "cache_hit_ratio" in stats

    def test_clear_cache(self, service_with_api):
        """Test cache clearing."""
        # Add some cache entries
        service_with_api._cache_embedding("text1", [0.1, 0.2])
        service_with_api._cache_embedding("text2", [0.3, 0.4])

        assert len(service_with_api._cache) == 2

        # Clear cache
        service_with_api.clear_cache()

        assert len(service_with_api._cache) == 0

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, service_with_api):
        """Test health check when service is healthy."""
        expected_embedding = [0.1, 0.2, 0.3]
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = expected_embedding
        mock_response.get.return_value = expected_embedding

        with patch("google.generativeai.embed_content", return_value=mock_response):
            health = await service_with_api.health_check()

            assert health["service"] == "EmbeddingService"
            assert health["status"] == "healthy"
            assert health["api_available"] is True
            assert health["api_test"] == "success"

    @pytest.mark.asyncio
    async def test_health_check_degraded(self, service_with_api):
        """Test health check when API is failing."""
        with patch("google.generativeai.embed_content", side_effect=Exception("API Error")):
            health = await service_with_api.health_check()

            assert health["service"] == "EmbeddingService"
            assert health["status"] == "degraded"
            assert health["api_test"] == "failed"

    @pytest.mark.asyncio
    async def test_health_check_unavailable(self, service_no_api):
        """Test health check when service is unavailable."""
        health = await service_no_api.health_check()

        assert health["service"] == "EmbeddingService"
        assert health["status"] == "unavailable"
        assert health["api_available"] is False

    def teardown_method(self):
        """Clean up test environment."""
        # Clear any environment variables that might affect tests
        test_vars = [
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ]
        for var in test_vars:
            if var in os.environ:
                del os.environ[var]
