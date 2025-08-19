"""
GitHub Authentication Manager.

Provides authentication management for GitHub API access with support for
both Personal Access Tokens (PAT) and GitHub App authentication.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

from github import Auth, Github

from ..config import BotConfig

logger = logging.getLogger(__name__)


class AuthMode(Enum):
    """GitHub authentication modes."""

    PAT = "pat"
    GITHUB_APP = "github_app"


class GitHubAuthError(Exception):
    """GitHub authentication related errors."""

    pass


class IAuthProvider(ABC):
    """Abstract interface for GitHub authentication providers."""

    @abstractmethod
    async def get_auth(self) -> Auth.Auth:
        """Get authentication instance."""
        pass

    @abstractmethod
    async def verify_permissions(self, repo_path: str) -> bool:
        """Verify repository access permissions."""
        pass

    @abstractmethod
    async def is_valid(self) -> bool:
        """Check if authentication is valid."""
        pass


class PATAuthProvider(IAuthProvider):
    """Personal Access Token authentication provider."""

    def __init__(self, token: str):
        self.token = token
        self._auth: Optional[Auth.Token] = None
        self._client: Optional[Github] = None

    async def get_auth(self) -> Auth.Token:
        """Get PAT authentication instance."""
        if not self._auth:
            self._auth = Auth.Token(self.token)
        return self._auth

    async def verify_permissions(self, repo_path: str) -> bool:
        """Verify repository access permissions."""
        try:
            client = await self.get_client()
            repo = client.get_repo(repo_path)
            # Test read access
            repo.get_contents("README.md")
            # Test if we can write (check permissions)
            permissions = repo.get_collaborator_permission(client.get_user().login)
            return permissions in ["admin", "write"]
        except Exception as e:
            logger.error(f"Permission verification failed: {e}")
            return False

    async def is_valid(self) -> bool:
        """Check if authentication is valid."""
        try:
            client = await self.get_client()
            # Simple API call to verify token validity
            user = client.get_user()
            _ = user.login  # Access property to trigger API call
            return True
        except Exception as e:
            logger.debug(f"PAT validation failed: {e}")
            return False

    async def get_client(self) -> Github:
        """Get authenticated GitHub client."""
        if not self._client:
            auth = await self.get_auth()
            self._client = Github(auth=auth)
        return self._client


class GitHubAppAuthProvider(IAuthProvider):
    """GitHub App authentication provider."""

    def __init__(
        self,
        app_id: str,
        private_key: str,
        installation_id: str,
        permissions: Optional[Dict[str, str]] = None,
    ):
        self.app_id = app_id
        self.private_key = private_key
        self.installation_id = installation_id
        self.permissions = permissions or {"contents": "write", "metadata": "read"}
        self._auth: Optional[Auth.AppInstallationAuth] = None
        self._client: Optional[Github] = None

    async def get_auth(self) -> Auth.AppInstallationAuth:
        """Get GitHub App authentication instance."""
        if not self._auth:
            app_auth = Auth.AppAuth(self.app_id, self.private_key)
            self._auth = app_auth.get_installation_auth(int(self.installation_id), self.permissions)
        return self._auth

    async def verify_permissions(self, repo_path: str) -> bool:
        """Verify repository access permissions."""
        try:
            client = await self.get_client()
            repo = client.get_repo(repo_path)
            # Test read access
            repo.get_contents("README.md")
            # For GitHub Apps, check if we have the required permissions
            return True  # If we got here, we have access
        except Exception as e:
            logger.error(f"Permission verification failed: {e}")
            return False

    async def is_valid(self) -> bool:
        """Check if authentication is valid."""
        try:
            client = await self.get_client()
            # Get installation to verify app auth is valid
            installation = client.get_app().get_installation(int(self.installation_id))
            return installation is not None
        except Exception as e:
            logger.debug(f"GitHub App validation failed: {e}")
            return False

    async def get_client(self) -> Github:
        """Get authenticated GitHub client."""
        if not self._client:
            auth = await self.get_auth()
            self._client = Github(auth=auth)
        return self._client


class GitHubAuthManager:
    """GitHub authentication management with multiple provider support."""

    def __init__(self, config: BotConfig):
        self.config = config
        self._provider: Optional[IAuthProvider] = None
        self._client: Optional[Github] = None
        self._last_verification: Optional[datetime] = None
        self._verification_interval = timedelta(hours=1)
        self._lock = asyncio.Lock()

    @property
    def auth_mode(self) -> AuthMode:
        """Get current authentication mode from config."""
        mode = getattr(self.config, "github_auth_mode", "pat")
        try:
            return AuthMode(mode.lower())
        except ValueError:
            logger.warning(f"Invalid auth mode '{mode}', falling back to PAT")
            return AuthMode.PAT

    async def initialize(self) -> None:
        """Initialize authentication provider based on config."""
        async with self._lock:
            if self._provider is not None:
                return

            mode = self.auth_mode

            if mode == AuthMode.PAT:
                token = getattr(self.config, "github_token", None)
                if not token:
                    raise GitHubAuthError("GitHub token not found in config")
                self._provider = PATAuthProvider(token)
                logger.info("Initialized PAT authentication")

            elif mode == AuthMode.GITHUB_APP:
                app_id = getattr(self.config, "github_app_id", None)
                private_key = getattr(self.config, "github_private_key", None)
                installation_id = getattr(self.config, "github_installation_id", None)

                if not all([app_id, private_key, installation_id]):
                    raise GitHubAuthError("GitHub App credentials not complete in config")

                self._provider = GitHubAppAuthProvider(
                    str(app_id), str(private_key), str(installation_id)
                )
                logger.info("Initialized GitHub App authentication")
            else:
                raise GitHubAuthError(f"Unsupported authentication mode: {mode}")

            # Verify authentication works
            if not await self._provider.is_valid():
                raise GitHubAuthError(f"Authentication validation failed for {mode.value}")

    async def get_client(self) -> Github:
        """Get authenticated GitHub client with automatic refresh."""
        if not self._provider:
            await self.initialize()

        # Check if we need to verify authentication
        if self._needs_verification():
            await self._verify_auth()

        if not self._client and self._provider:
            auth = await self._provider.get_auth()
            self._client = Github(auth=auth)

        if not self._client:
            raise GitHubAuthError("Failed to get authenticated GitHub client")

        return self._client

    async def verify_permissions(self, repo_path: Optional[str] = None) -> bool:
        """Verify repository access permissions."""
        if not self._provider:
            await self.initialize()

        if not repo_path:
            repo_owner = getattr(self.config, "github_repo_owner", None)
            repo_name = getattr(self.config, "github_repo_name", None)
            if not repo_owner or not repo_name:
                raise GitHubAuthError("Repository path not provided and not found in config")
            repo_path = f"{repo_owner}/{repo_name}"

        if not self._provider:
            return False

        return await self._provider.verify_permissions(repo_path)

    def _needs_verification(self) -> bool:
        """Check if authentication needs re-verification."""
        if not self._last_verification:
            return True

        elapsed = datetime.now(timezone.utc) - self._last_verification
        return elapsed > self._verification_interval

    async def _verify_auth(self) -> None:
        """Verify authentication is still valid."""
        if not self._provider:
            return

        async with self._lock:
            try:
                is_valid = await self._provider.is_valid()
                if not is_valid:
                    logger.warning("Authentication validation failed, reinitializing...")
                    self._provider = None
                    self._client = None
                    await self.initialize()
                else:
                    self._last_verification = datetime.now(timezone.utc)
                    logger.debug("Authentication verification successful")
            except Exception as e:
                logger.error(f"Authentication verification error: {e}")
                # Reset provider to force reinitialization on next request
                self._provider = None
                self._client = None
                raise GitHubAuthError(f"Authentication verification failed: {e}")

    async def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limit information from GitHub API."""
        try:
            client = await self.get_client()
            rate_limit = client.get_rate_limit()

            return {
                "core": {
                    "limit": rate_limit.core.limit,
                    "remaining": rate_limit.core.remaining,
                    "reset": rate_limit.core.reset,
                    "used": rate_limit.core.used,
                },
                "search": {
                    "limit": rate_limit.search.limit,
                    "remaining": rate_limit.search.remaining,
                    "reset": rate_limit.search.reset,
                    "used": rate_limit.search.used,
                },
            }
        except Exception as e:
            logger.error(f"Failed to get rate limit info: {e}")
            return {}

    async def cleanup(self) -> None:
        """Clean up authentication resources."""
        async with self._lock:
            if self._client:
                # PyGithub doesn't have explicit close method
                self._client = None
            self._provider = None
            logger.info("GitHub authentication cleanup completed")
