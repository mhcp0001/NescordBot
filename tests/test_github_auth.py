"""
Test cases for GitHubAuthManager service.

Tests cover PAT and GitHub App authentication, permission verification,
and error handling scenarios.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.github_auth import (
    AuthMode,
    GitHubAppAuthProvider,
    GitHubAuthError,
    GitHubAuthManager,
    PATAuthProvider,
)


class MockConfig:
    """Mock configuration for testing."""

    def __init__(self, **kwargs):
        # Set defaults
        self.github_auth_mode = kwargs.get("github_auth_mode", "pat")
        self.github_token = kwargs.get("github_token", "test_token")
        self.github_repo_owner = kwargs.get("github_repo_owner", "test_owner")
        self.github_repo_name = kwargs.get("github_repo_name", "test_repo")

        # GitHub App settings
        self.github_app_id = kwargs.get("github_app_id")
        self.github_private_key = kwargs.get("github_private_key")
        self.github_installation_id = kwargs.get("github_installation_id")


@pytest.fixture
def pat_config():
    """Create PAT configuration for testing."""
    return MockConfig(
        github_auth_mode="pat",
        github_token="ghp_test_token_12345",
        github_repo_owner="test_owner",
        github_repo_name="test_repo",
    )


@pytest.fixture
def github_app_config():
    """Create GitHub App configuration for testing."""
    return MockConfig(
        github_auth_mode="github_app",
        github_app_id="123456",
        github_private_key="test_private_key",
        github_installation_id="789012",
        github_repo_owner="test_owner",
        github_repo_name="test_repo",
    )


class TestPATAuthProvider:
    """Test PAT authentication provider."""

    @pytest.fixture
    def pat_provider(self):
        """Create PAT provider for testing."""
        return PATAuthProvider("ghp_test_token_12345")

    @pytest.mark.asyncio
    async def test_get_auth(self, pat_provider):
        """Test PAT authentication creation."""
        auth = await pat_provider.get_auth()
        assert auth is not None
        assert hasattr(auth, "token")

    @pytest.mark.asyncio
    async def test_is_valid_success(self, pat_provider):
        """Test PAT validation success."""
        with patch.object(pat_provider, "get_client") as mock_get_client:
            # Mock successful validation
            mock_user = MagicMock()
            mock_user.login = "test_user"
            mock_client = MagicMock()
            mock_client.get_user.return_value = mock_user
            mock_get_client.return_value = mock_client

            is_valid = await pat_provider.is_valid()
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_is_valid_failure(self, pat_provider):
        """Test PAT validation failure."""
        with patch("github.Github") as mock_github:
            # Mock validation failure
            mock_client = MagicMock()
            mock_client.get_user.side_effect = Exception("Invalid token")
            mock_github.return_value = mock_client

            is_valid = await pat_provider.is_valid()
            assert is_valid is False

    @pytest.mark.asyncio
    async def test_verify_permissions_success(self, pat_provider):
        """Test permission verification success."""
        with patch.object(pat_provider, "get_client") as mock_get_client:
            # Mock successful permission check
            mock_repo = MagicMock()
            mock_repo.get_contents.return_value = MagicMock()
            mock_repo.get_collaborator_permission.return_value = "admin"

            mock_user = MagicMock()
            mock_user.login = "test_user"

            mock_client = MagicMock()
            mock_client.get_repo.return_value = mock_repo
            mock_client.get_user.return_value = mock_user
            mock_get_client.return_value = mock_client

            has_permissions = await pat_provider.verify_permissions("test_owner/test_repo")
            assert has_permissions is True

    @pytest.mark.asyncio
    async def test_verify_permissions_failure(self, pat_provider):
        """Test permission verification failure."""
        with patch("github.Github") as mock_github:
            # Mock permission check failure
            mock_client = MagicMock()
            mock_client.get_repo.side_effect = Exception("No access")
            mock_github.return_value = mock_client

            has_permissions = await pat_provider.verify_permissions("test_owner/test_repo")
            assert has_permissions is False


class TestGitHubAppAuthProvider:
    """Test GitHub App authentication provider."""

    @pytest.fixture
    def app_provider(self):
        """Create GitHub App provider for testing."""
        return GitHubAppAuthProvider(
            app_id="123456", private_key="test_private_key", installation_id="789012"
        )

    @pytest.mark.asyncio
    async def test_get_auth(self, app_provider):
        """Test GitHub App authentication creation."""
        with patch("github.Auth.AppAuth") as mock_app_auth:
            # Mock the auth chain
            mock_installation_auth = MagicMock()
            mock_app_auth_instance = MagicMock()
            mock_app_auth_instance.get_installation_auth.return_value = mock_installation_auth
            mock_app_auth.return_value = mock_app_auth_instance

            auth = await app_provider.get_auth()
            assert auth is mock_installation_auth
            mock_app_auth.assert_called_once_with("123456", "test_private_key")

    @pytest.mark.asyncio
    async def test_is_valid_success(self, app_provider):
        """Test GitHub App validation success."""
        with patch.object(app_provider, "get_client") as mock_get_client:
            # Mock successful validation
            mock_installation = MagicMock()
            mock_app = MagicMock()
            mock_app.get_installation.return_value = mock_installation
            mock_client = MagicMock()
            mock_client.get_app.return_value = mock_app
            mock_get_client.return_value = mock_client

            is_valid = await app_provider.is_valid()
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_is_valid_failure(self, app_provider):
        """Test GitHub App validation failure."""
        with patch("github.Github") as mock_github, patch("github.Auth.AppAuth"):
            # Mock validation failure
            mock_client = MagicMock()
            mock_client.get_app.side_effect = Exception("Invalid app")
            mock_github.return_value = mock_client

            is_valid = await app_provider.is_valid()
            assert is_valid is False


class TestGitHubAuthManager:
    """Test GitHub authentication manager."""

    @pytest.mark.asyncio
    async def test_pat_initialization(self, pat_config):
        """Test PAT authentication initialization."""
        auth_manager = GitHubAuthManager(pat_config)

        with patch.object(auth_manager, "_provider") as mock_provider:
            mock_provider.is_valid = AsyncMock(return_value=True)

            await auth_manager.initialize()

            assert auth_manager.auth_mode == AuthMode.PAT
            assert auth_manager._provider is not None

    @pytest.mark.asyncio
    async def test_github_app_initialization(self, github_app_config):
        """Test GitHub App authentication initialization."""
        auth_manager = GitHubAuthManager(github_app_config)

        with patch(
            "src.nescordbot.services.github_auth.GitHubAppAuthProvider"
        ) as mock_provider_class:
            mock_provider = AsyncMock()
            mock_provider.is_valid.return_value = True
            mock_provider_class.return_value = mock_provider

            await auth_manager.initialize()

            assert auth_manager.auth_mode == AuthMode.GITHUB_APP
            mock_provider_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialization_missing_token(self):
        """Test initialization failure with missing token."""
        config = MockConfig(github_auth_mode="pat", github_token=None)
        auth_manager = GitHubAuthManager(config)  # type: ignore

        with pytest.raises(GitHubAuthError, match="GitHub token not found"):
            await auth_manager.initialize()

    @pytest.mark.asyncio
    async def test_initialization_invalid_auth_mode(self):
        """Test initialization with invalid authentication mode."""
        config = MockConfig(github_auth_mode="invalid_mode")
        auth_manager = GitHubAuthManager(config)  # type: ignore

        # Should fall back to PAT mode
        assert auth_manager.auth_mode == AuthMode.PAT

    @pytest.mark.asyncio
    async def test_get_client_success(self, pat_config):
        """Test successful client retrieval."""
        auth_manager = GitHubAuthManager(pat_config)

        # Mock provider and auth
        from github.Auth import Auth

        mock_auth = MagicMock(spec=Auth)
        mock_client = MagicMock()
        mock_provider = AsyncMock()
        mock_provider.is_valid.return_value = True
        mock_provider.get_auth.return_value = mock_auth

        auth_manager._provider = mock_provider

        with patch("src.nescordbot.services.github_auth.Github") as mock_github:
            mock_github.return_value = mock_client
            client = await auth_manager.get_client()
            assert client is mock_client
            mock_github.assert_called_once_with(auth=mock_auth)

    @pytest.mark.asyncio
    async def test_get_client_auto_initialize(self, pat_config):
        """Test client retrieval with automatic initialization."""
        auth_manager = GitHubAuthManager(pat_config)

        with patch.object(auth_manager, "initialize") as mock_init:
            mock_init.return_value = None

            # Mock provider and auth
            from github.Auth import Auth

            mock_auth = MagicMock(spec=Auth)
            mock_client = MagicMock()
            mock_provider = AsyncMock()
            mock_provider.get_auth.return_value = mock_auth

            # Set up mocks so initialize() gets called
            auth_manager._provider = None  # Force initialization
            mock_init.side_effect = lambda: setattr(auth_manager, "_provider", mock_provider)

            with patch("src.nescordbot.services.github_auth.Github") as mock_github:
                mock_github.return_value = mock_client
                client = await auth_manager.get_client()

                mock_init.assert_called_once()
                assert client is mock_client
                mock_github.assert_called_once_with(auth=mock_auth)

    @pytest.mark.asyncio
    async def test_verify_permissions_with_repo_path(self, pat_config):
        """Test permission verification with explicit repo path."""
        auth_manager = GitHubAuthManager(pat_config)

        mock_provider = AsyncMock()
        mock_provider.is_valid.return_value = True
        mock_provider.verify_permissions.return_value = True
        auth_manager._provider = mock_provider

        result = await auth_manager.verify_permissions("owner/repo")

        assert result is True
        mock_provider.verify_permissions.assert_called_once_with("owner/repo")

    @pytest.mark.asyncio
    async def test_verify_permissions_from_config(self, pat_config):
        """Test permission verification using config repo."""
        auth_manager = GitHubAuthManager(pat_config)

        mock_provider = AsyncMock()
        mock_provider.is_valid.return_value = True
        mock_provider.verify_permissions.return_value = True
        auth_manager._provider = mock_provider

        result = await auth_manager.verify_permissions()

        assert result is True
        mock_provider.verify_permissions.assert_called_once_with("test_owner/test_repo")

    @pytest.mark.asyncio
    async def test_verify_permissions_missing_config(self):
        """Test permission verification with missing config."""
        config = MockConfig(github_repo_owner=None, github_repo_name=None, github_token=None)
        auth_manager = GitHubAuthManager(config)  # type: ignore

        with pytest.raises(GitHubAuthError, match="GitHub token not found"):
            await auth_manager.verify_permissions()

    @pytest.mark.asyncio
    async def test_get_rate_limit_info(self, pat_config):
        """Test rate limit information retrieval."""
        auth_manager = GitHubAuthManager(pat_config)

        # Mock rate limit data
        mock_rate_limit = MagicMock()
        mock_rate_limit.core.limit = 5000
        mock_rate_limit.core.remaining = 4500
        mock_rate_limit.core.used = 500
        mock_rate_limit.search.limit = 30
        mock_rate_limit.search.remaining = 25
        mock_rate_limit.search.used = 5

        mock_client = MagicMock()
        mock_client.get_rate_limit.return_value = mock_rate_limit

        # Mock get_client to return mock_client
        with patch.object(auth_manager, "get_client") as mock_get_client:
            mock_get_client.return_value = mock_client
            rate_info = await auth_manager.get_rate_limit_info()

            assert rate_info["core"]["limit"] == 5000
            assert rate_info["core"]["remaining"] == 4500
            assert rate_info["search"]["limit"] == 30

    @pytest.mark.asyncio
    async def test_get_rate_limit_info_error(self, pat_config):
        """Test rate limit information retrieval error handling."""
        auth_manager = GitHubAuthManager(pat_config)

        mock_provider = AsyncMock()
        mock_provider.get_client.side_effect = Exception("Client error")
        auth_manager._provider = mock_provider

        rate_info = await auth_manager.get_rate_limit_info()

        assert rate_info == {}

    @pytest.mark.asyncio
    async def test_cleanup(self, pat_config):
        """Test authentication cleanup."""
        auth_manager = GitHubAuthManager(pat_config)

        # Set up mock provider and client
        auth_manager._provider = MagicMock()
        auth_manager._client = MagicMock()

        await auth_manager.cleanup()

        assert auth_manager._provider is None
        assert auth_manager._client is None
