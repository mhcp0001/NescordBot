"""Tests for GitHub service."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from pydantic import ValidationError

from nescordbot.config import BotConfig
from nescordbot.services.github import GitHubService, RateLimitInfo


class TestRateLimitInfo:
    """Test RateLimitInfo model."""

    def test_rate_limit_not_exceeded(self):
        """Test rate limit when not exceeded."""
        rate_limit = RateLimitInfo(
            limit=5000,
            remaining=4000,
            reset=datetime.now(timezone.utc) + timedelta(hours=1),
            used=1000,
        )
        assert not rate_limit.is_exceeded
        assert rate_limit.wait_seconds == 0

    def test_rate_limit_exceeded(self):
        """Test rate limit when exceeded."""
        future_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        rate_limit = RateLimitInfo(
            limit=5000,
            remaining=0,
            reset=future_time,
            used=5000,
        )
        assert rate_limit.is_exceeded
        assert rate_limit.wait_seconds > 0
        assert rate_limit.wait_seconds <= 1800  # 30 minutes

    def test_rate_limit_reset_in_past(self):
        """Test rate limit with reset time in the past."""
        past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
        rate_limit = RateLimitInfo(
            limit=5000,
            remaining=0,
            reset=past_time,
            used=5000,
        )
        assert rate_limit.is_exceeded
        assert rate_limit.wait_seconds == 0


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = MagicMock(spec=BotConfig)
    config.github_token = "test_token"
    config.github_repo_owner = "test_owner"
    config.github_repo_name = "test_repo"
    return config


@pytest.fixture
def github_service(mock_config):
    """Create GitHub service instance."""
    return GitHubService(mock_config)


class TestGitHubService:
    """Test GitHubService class."""

    def test_initialization(self, github_service, mock_config):
        """Test service initialization."""
        assert github_service.config == mock_config
        assert github_service.token == "test_token"
        assert github_service.repo_owner == "test_owner"
        assert github_service.repo_name == "test_repo"
        assert github_service.session is None
        assert github_service.repo_path == "test_owner/test_repo"

    def test_headers_with_token(self, github_service):
        """Test headers generation with token."""
        headers = github_service.headers
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Accept"] == "application/vnd.github+json"
        assert headers["X-GitHub-Api-Version"] == "2022-11-28"

    def test_headers_without_token(self, mock_config):
        """Test headers generation without token."""
        mock_config.github_token = None
        service = GitHubService(mock_config)
        headers = service.headers
        assert "Authorization" not in headers
        assert headers["Accept"] == "application/vnd.github+json"

    @pytest.mark.asyncio
    async def test_start_stop(self, github_service):
        """Test service start and stop."""
        # Start service
        await github_service.start()
        assert github_service.session is not None
        assert isinstance(github_service.session, aiohttp.ClientSession)

        # Stop service
        await github_service.stop()
        assert github_service.session is None

    @pytest.mark.asyncio
    async def test_ensure_session(self, github_service):
        """Test session creation on demand."""
        assert github_service.session is None

        session = await github_service._ensure_session()
        assert session is not None
        assert github_service.session is not None

        # Clean up
        await github_service.stop()

    def test_cache_key_generation(self, github_service):
        """Test cache key generation."""
        key1 = github_service._get_cache_key("GET", "/repos", page=1, sort="created")
        key2 = github_service._get_cache_key("GET", "/repos", sort="created", page=1)
        key3 = github_service._get_cache_key("GET", "/repos", page=2, sort="created")

        # Same parameters in different order should produce same key
        assert key1 == key2
        # Different parameters should produce different key
        assert key1 != key3

    def test_cache_operations(self, github_service):
        """Test cache set and validation."""
        key = "test_key"
        data = {"test": "data"}

        # Cache should be invalid initially
        assert not github_service._is_cache_valid(key)

        # Set cache with TTL
        github_service._set_cache(key, data, ttl=5)
        assert github_service._is_cache_valid(key)
        assert github_service._cache[key] == data

        # Simulate expired cache
        github_service._cache_expiry[key] = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert not github_service._is_cache_valid(key)

    def test_clear_expired_cache(self, github_service):
        """Test clearing expired cache entries."""
        # Add some cache entries
        github_service._set_cache("valid", {"data": 1}, ttl=300)
        github_service._set_cache("expired", {"data": 2}, ttl=0)

        # Manually expire the second entry
        github_service._cache_expiry["expired"] = datetime.now(timezone.utc) - timedelta(seconds=1)

        # Clear expired entries
        github_service._clear_expired_cache()

        assert "valid" in github_service._cache
        assert "expired" not in github_service._cache

    def test_update_rate_limit(self, github_service):
        """Test rate limit update from headers."""
        headers = {
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Remaining": "4999",
            "X-RateLimit-Reset": str(int(datetime.now(timezone.utc).timestamp() + 3600)),
            "X-RateLimit-Used": "1",
        }

        github_service._update_rate_limit(headers)

        assert github_service._rate_limit is not None
        assert github_service._rate_limit.limit == 5000
        assert github_service._rate_limit.remaining == 4999
        assert github_service._rate_limit.used == 1

    def test_update_rate_limit_invalid_headers(self, github_service):
        """Test rate limit update with invalid headers."""
        headers = {
            "X-RateLimit-Limit": "invalid",
        }

        # Should not raise exception
        github_service._update_rate_limit(headers)
        # Rate limit should remain unchanged
        assert github_service._rate_limit is None

    @pytest.mark.asyncio
    async def test_request_with_cache(self, github_service):
        """Test request with caching."""
        mock_response = {"data": "test"}

        with patch.object(github_service, "_ensure_session") as mock_ensure:
            mock_session = MagicMock()
            mock_ensure.return_value = mock_session

            # Mock the response with proper async context manager
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.headers = {}
            mock_resp.json = AsyncMock(return_value=mock_response)
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock()

            # Make request return a context manager, not a coroutine
            mock_session.request = MagicMock(return_value=mock_resp)

            # First request should hit API
            result1 = await github_service._request("GET", "test/path", use_cache=True)
            assert result1 == mock_response
            assert mock_session.request.call_count == 1

            # Second request should use cache
            result2 = await github_service._request("GET", "test/path", use_cache=True)
            assert result2 == mock_response
            assert mock_session.request.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_request_error_handling(self, github_service):
        """Test request error handling."""
        with patch.object(github_service, "_ensure_session") as mock_ensure:
            mock_session = MagicMock()
            mock_ensure.return_value = mock_session

            # Mock error response with proper async context manager
            mock_resp = MagicMock()
            mock_resp.status = 404
            mock_resp.headers = {}
            mock_resp.json = AsyncMock(return_value={"message": "Not Found"})
            # raise_for_status should raise an exception when called
            # Use a generic ClientError instead of ClientResponseError to avoid str() issues
            mock_resp.raise_for_status = MagicMock(side_effect=aiohttp.ClientError("Not Found"))
            mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_resp.__aexit__ = AsyncMock(return_value=None)

            # Make request return a context manager, not a coroutine
            mock_session.request = MagicMock(return_value=mock_resp)

            with pytest.raises(aiohttp.ClientError):
                await github_service._request("GET", "test/path")

    @pytest.mark.asyncio
    async def test_create_issue(self, github_service):
        """Test issue creation."""
        mock_issue = {
            "number": 123,
            "title": "Test Issue",
            "html_url": "https://github.com/test/repo/issues/123",
        }

        with patch.object(github_service, "_request", new=AsyncMock(return_value=mock_issue)):
            result = await github_service.create_issue(
                title="Test Issue",
                body="Test body",
                labels=["bug", "enhancement"],
            )

            assert result == mock_issue
            github_service._request.assert_called_once()
            call_args = github_service._request.call_args
            assert call_args[0] == ("POST", "repos/test_owner/test_repo/issues")
            assert call_args[1]["json"]["title"] == "Test Issue"
            assert call_args[1]["json"]["body"] == "Test body"
            assert call_args[1]["json"]["labels"] == ["bug", "enhancement"]

    @pytest.mark.asyncio
    async def test_get_issue(self, github_service):
        """Test getting issue details."""
        mock_issue = {"number": 123, "title": "Test Issue"}

        with patch.object(github_service, "_request", new=AsyncMock(return_value=mock_issue)):
            result = await github_service.get_issue(123)

            assert result == mock_issue
            github_service._request.assert_called_once_with(
                "GET", "repos/test_owner/test_repo/issues/123"
            )

    @pytest.mark.asyncio
    async def test_list_issues(self, github_service):
        """Test listing issues."""
        mock_issues = [
            {"number": 1, "title": "Issue 1"},
            {"number": 2, "title": "Issue 2"},
        ]

        with patch.object(github_service, "_request", new=AsyncMock(return_value=mock_issues)):
            result = await github_service.list_issues(state="open", labels="bug")

            assert result == mock_issues
            github_service._request.assert_called_once()
            call_args = github_service._request.call_args
            assert call_args[0] == ("GET", "repos/test_owner/test_repo/issues")
            assert call_args[1]["params"]["state"] == "open"
            assert call_args[1]["params"]["labels"] == "bug"

    @pytest.mark.asyncio
    async def test_create_pull_request(self, github_service):
        """Test creating pull request."""
        mock_pr = {
            "number": 456,
            "title": "Test PR",
            "html_url": "https://github.com/test/repo/pull/456",
        }

        with patch.object(github_service, "_request", new=AsyncMock(return_value=mock_pr)):
            result = await github_service.create_pull_request(
                title="Test PR",
                head="feature-branch",
                base="main",
                body="PR description",
                draft=True,
            )

            assert result == mock_pr
            github_service._request.assert_called_once()
            call_args = github_service._request.call_args
            assert call_args[0] == ("POST", "repos/test_owner/test_repo/pulls")
            assert call_args[1]["json"]["title"] == "Test PR"
            assert call_args[1]["json"]["head"] == "feature-branch"
            assert call_args[1]["json"]["base"] == "main"
            assert call_args[1]["json"]["draft"] is True

    @pytest.mark.asyncio
    async def test_get_rate_limit(self, github_service):
        """Test getting rate limit information."""
        mock_rate_data = {
            "rate": {
                "limit": 5000,
                "remaining": 4999,
                "reset": int(datetime.now(timezone.utc).timestamp() + 3600),
                "used": 1,
            }
        }

        with patch.object(github_service, "_request", new=AsyncMock(return_value=mock_rate_data)):
            result = await github_service.get_rate_limit()

            assert isinstance(result, RateLimitInfo)
            assert result.limit == 5000
            assert result.remaining == 4999
            assert result.used == 1
            github_service._request.assert_called_once_with("GET", "rate_limit", use_cache=False)
