"""GitHub API Service for NescordBot."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, TypedDict

import aiohttp
from pydantic import BaseModel, Field

from ..config import BotConfig

logger = logging.getLogger(__name__)


class RateLimitInfo(BaseModel):
    """GitHub API rate limit information."""

    limit: int = Field(description="Maximum requests per hour")
    remaining: int = Field(description="Remaining requests")
    reset: datetime = Field(description="Reset time")
    used: int = Field(description="Used requests")

    @property
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.remaining <= 0

    @property
    def wait_seconds(self) -> float:
        """Calculate seconds to wait until reset."""
        if not self.is_exceeded:
            return 0
        now = datetime.now(timezone.utc)
        return max(0, (self.reset - now).total_seconds())


class IssueData(TypedDict, total=False):
    """Issue data structure for GitHub API."""

    title: str
    body: str
    state: str
    labels: List[str]
    assignees: List[str]
    milestone: Optional[int]


class PullRequestData(TypedDict, total=False):
    """Pull request data structure for GitHub API."""

    title: str
    body: str
    head: str
    base: str
    draft: bool
    maintainer_can_modify: bool


class GitHubService:
    """Service for interacting with GitHub API."""

    API_BASE = "https://api.github.com"
    DEFAULT_TIMEOUT = 30

    def __init__(self, config: BotConfig) -> None:
        """Initialize GitHub service.

        Args:
            config: Application configuration
        """
        self.config = config
        self.token = config.github_token
        self.repo_owner = config.github_repo_owner
        self.repo_name = config.github_repo_name
        self.session: Optional[aiohttp.ClientSession] = None
        self._rate_limit: Optional[RateLimitInfo] = None
        self._cache: Dict[str, Any] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    @property
    def repo_path(self) -> str:
        """Get the repository path for API calls."""
        return f"{self.repo_owner}/{self.repo_name}"

    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def start(self) -> None:
        """Start the GitHub service."""
        if not self.session:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            timeout = aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers,
            )
            logger.info("GitHub service started")

    async def stop(self) -> None:
        """Stop the GitHub service."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("GitHub service stopped")

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure session is available."""
        if not self.session:
            await self.start()
        assert self.session is not None
        return self.session

    async def _check_rate_limit(self) -> None:
        """Check and wait for rate limit if needed."""
        if self._rate_limit and self._rate_limit.is_exceeded:
            wait_time = self._rate_limit.wait_seconds
            if wait_time > 0:
                logger.warning(f"Rate limit exceeded, waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

    def _update_rate_limit(self, headers: Dict[str, str]) -> None:
        """Update rate limit information from response headers."""
        try:
            if "X-RateLimit-Limit" in headers:
                self._rate_limit = RateLimitInfo(
                    limit=int(headers["X-RateLimit-Limit"]),
                    remaining=int(headers["X-RateLimit-Remaining"]),
                    reset=datetime.fromtimestamp(
                        int(headers["X-RateLimit-Reset"]), tz=timezone.utc
                    ),
                    used=int(headers.get("X-RateLimit-Used", 0)),
                )
        except (ValueError, KeyError) as e:
            logger.debug(f"Failed to parse rate limit headers: {e}")

    def _get_cache_key(self, method: str, path: str, **params: Any) -> str:
        """Generate cache key for request."""
        params_str = json.dumps(params, sort_keys=True)
        return f"{method}:{path}:{params_str}"

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid."""
        if key not in self._cache:
            return False
        expiry = self._cache_expiry.get(key)
        if not expiry:
            return False
        return datetime.now(timezone.utc) < expiry

    def _set_cache(self, key: str, data: Any, ttl: int = 300) -> None:
        """Set cache entry with TTL in seconds."""
        self._cache[key] = data
        self._cache_expiry[key] = datetime.now(timezone.utc) + timedelta(seconds=ttl)

    def _clear_expired_cache(self) -> None:
        """Clear expired cache entries."""
        now = datetime.now(timezone.utc)
        expired_keys = [key for key, expiry in self._cache_expiry.items() if expiry <= now]
        for key in expired_keys:
            self._cache.pop(key, None)
            self._cache_expiry.pop(key, None)

    async def _request(
        self,
        method: str,
        path: str,
        use_cache: bool = True,
        cache_ttl: int = 300,
        **kwargs: Any,
    ) -> Any:
        """Make an API request with rate limiting and caching.

        Args:
            method: HTTP method
            path: API endpoint path
            use_cache: Whether to use caching for GET requests
            cache_ttl: Cache TTL in seconds
            **kwargs: Additional request parameters

        Returns:
            Response data

        Raises:
            aiohttp.ClientError: On request failure
        """
        # Check cache for GET requests
        if method == "GET" and use_cache:
            cache_key = self._get_cache_key(method, path, **kwargs)
            if self._is_cache_valid(cache_key):
                logger.debug(f"Cache hit for {path}")
                return self._cache[cache_key]

        # Check rate limit
        await self._check_rate_limit()

        # Make request
        session = await self._ensure_session()
        url = f"{self.API_BASE}/{path}"

        async with self._lock:
            try:
                async with session.request(method, url, **kwargs) as response:
                    # Update rate limit
                    self._update_rate_limit(dict(response.headers))

                    # Handle response
                    if response.status == 204:
                        return None

                    data = await response.json()

                    if response.status >= 400:
                        error_msg = data.get("message", "Unknown error")
                        logger.error(f"GitHub API error: {response.status} - {error_msg}")
                        response.raise_for_status()

                    # Cache successful GET requests
                    if method == "GET" and use_cache:
                        self._set_cache(cache_key, data, cache_ttl)
                        self._clear_expired_cache()

                    return data

            except asyncio.TimeoutError:
                logger.error(f"Request timeout for {url}")
                raise
            except aiohttp.ClientError as e:
                logger.error(f"Request failed for {url}: {e}")
                raise

    # Issue Management

    async def create_issue(
        self,
        title: str,
        body: str = "",
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new issue.

        Args:
            title: Issue title
            body: Issue body/description
            labels: Labels to apply
            assignees: Users to assign
            milestone: Milestone number

        Returns:
            Created issue data
        """
        data: IssueData = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        if milestone:
            data["milestone"] = milestone

        path = f"repos/{self.repo_path}/issues"
        result = await self._request("POST", path, json=data, use_cache=False)
        logger.info(f"Created issue #{result['number']}: {title}")
        return result  # type: ignore[no-any-return]

    async def get_issue(self, issue_number: int) -> Dict[str, Any]:
        """Get issue details.

        Args:
            issue_number: Issue number

        Returns:
            Issue data
        """
        path = f"repos/{self.repo_path}/issues/{issue_number}"
        return await self._request("GET", path)  # type: ignore[no-any-return]

    async def update_issue(
        self,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        milestone: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Update an existing issue.

        Args:
            issue_number: Issue number
            title: New title
            body: New body
            state: New state (open/closed)
            labels: New labels
            assignees: New assignees
            milestone: New milestone

        Returns:
            Updated issue data
        """
        data: IssueData = {}
        if title is not None:
            data["title"] = title
        if body is not None:
            data["body"] = body
        if state is not None:
            data["state"] = state
        if labels is not None:
            data["labels"] = labels
        if assignees is not None:
            data["assignees"] = assignees
        if milestone is not None:
            data["milestone"] = milestone

        path = f"repos/{self.repo_path}/issues/{issue_number}"
        result = await self._request("PATCH", path, json=data, use_cache=False)
        logger.info(f"Updated issue #{issue_number}")
        return result  # type: ignore[no-any-return]

    async def list_issues(
        self,
        state: str = "open",
        labels: Optional[str] = None,
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """List repository issues.

        Args:
            state: Issue state (open/closed/all)
            labels: Comma-separated label names
            sort: Sort field (created/updated/comments)
            direction: Sort direction (asc/desc)
            per_page: Results per page
            page: Page number

        Returns:
            List of issues
        """
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }
        if labels:
            params["labels"] = labels

        path = f"repos/{self.repo_path}/issues"
        return await self._request("GET", path, params=params)  # type: ignore[no-any-return]

    # Pull Request Management

    async def create_pull_request(
        self,
        title: str,
        head: str,
        base: str = "main",
        body: str = "",
        draft: bool = False,
    ) -> Dict[str, Any]:
        """Create a new pull request.

        Args:
            title: PR title
            head: Branch containing changes
            base: Branch to merge into
            body: PR description
            draft: Create as draft PR

        Returns:
            Created PR data
        """
        data: PullRequestData = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
        }

        path = f"repos/{self.repo_path}/pulls"
        result = await self._request("POST", path, json=data, use_cache=False)
        logger.info(f"Created PR #{result['number']}: {title}")
        return result  # type: ignore[no-any-return]

    async def get_pull_request(self, pr_number: int) -> Dict[str, Any]:
        """Get pull request details.

        Args:
            pr_number: PR number

        Returns:
            PR data
        """
        path = f"repos/{self.repo_path}/pulls/{pr_number}"
        return await self._request("GET", path)  # type: ignore[no-any-return]

    async def list_pull_requests(
        self,
        state: str = "open",
        head: Optional[str] = None,
        base: Optional[str] = None,
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """List repository pull requests.

        Args:
            state: PR state (open/closed/all)
            head: Filter by head branch
            base: Filter by base branch
            sort: Sort field (created/updated/popularity/long-running)
            direction: Sort direction (asc/desc)
            per_page: Results per page
            page: Page number

        Returns:
            List of pull requests
        """
        params = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": per_page,
            "page": page,
        }
        if head:
            params["head"] = head
        if base:
            params["base"] = base

        path = f"repos/{self.repo_path}/pulls"
        return await self._request("GET", path, params=params)  # type: ignore[no-any-return]

    async def merge_pull_request(
        self,
        pr_number: int,
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
        merge_method: str = "merge",
    ) -> Dict[str, Any]:
        """Merge a pull request.

        Args:
            pr_number: PR number
            commit_title: Merge commit title
            commit_message: Merge commit message
            merge_method: Merge method (merge/squash/rebase)

        Returns:
            Merge result
        """
        data = {"merge_method": merge_method}
        if commit_title:
            data["commit_title"] = commit_title
        if commit_message:
            data["commit_message"] = commit_message

        path = f"repos/{self.repo_path}/pulls/{pr_number}/merge"
        result = await self._request("PUT", path, json=data, use_cache=False)
        logger.info(f"Merged PR #{pr_number}")
        return result  # type: ignore[no-any-return]

    # Repository Information

    async def get_repository(self) -> Dict[str, Any]:
        """Get repository information.

        Returns:
            Repository data
        """
        path = f"repos/{self.repo_path}"
        return await self._request("GET", path)  # type: ignore[no-any-return]

    async def get_rate_limit(self) -> RateLimitInfo:
        """Get current rate limit status.

        Returns:
            Rate limit information
        """
        data = await self._request("GET", "rate_limit", use_cache=False)
        core = data["rate"]
        return RateLimitInfo(
            limit=core["limit"],
            remaining=core["remaining"],
            reset=datetime.fromtimestamp(core["reset"], tz=timezone.utc),
            used=core["used"],
        )
