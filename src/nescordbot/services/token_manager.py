"""
Token usage tracking and management service.

This module provides comprehensive token usage tracking, cost calculation,
and limit management for external API services like Gemini and OpenAI.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import BotConfig
from .database import DatabaseService

logger = logging.getLogger(__name__)


class TokenUsageError(Exception):
    """Exception raised when token usage operations fail."""

    pass


class TokenLimitExceededError(Exception):
    """Exception raised when token limits are exceeded."""

    def __init__(self, provider: str, limit: int, current: int) -> None:
        super().__init__(f"{provider} token limit exceeded: {current}/{limit}")
        self.provider = provider
        self.limit = limit
        self.current = current


class TokenManager:
    """
    Manages token usage tracking and cost calculation for API services.

    Features:
    - Token usage recording for multiple providers
    - Monthly and daily usage tracking
    - Cost calculation with provider-specific rates
    - Usage limit enforcement
    - Historical usage analytics
    """

    # Token cost rates (per 1K tokens)
    COST_RATES = {
        "gemini": {
            "text-embedding-004": 0.000625,
            "gemini-1.5-pro": 0.0035,  # Input tokens
            "gemini-1.5-flash": 0.000875,
        },
        "openai": {
            "text-embedding-3-small": 0.00002,
            "text-embedding-3-large": 0.00013,
            "gpt-3.5-turbo": 0.0015,
            "gpt-4": 0.03,
            "whisper-1": 0.006,  # Per minute
        },
    }

    def __init__(self, config: BotConfig, database_service: DatabaseService) -> None:
        """
        Initialize TokenManager.

        Args:
            config: Bot configuration containing token limits
            database_service: Database service for persistence
        """
        self.config = config
        self.db = database_service
        self._initialized = False

    async def init_async(self) -> None:
        """Initialize async resources and database schema."""
        if self._initialized:
            return

        try:
            await self._create_tables()
            self._initialized = True
            logger.info("TokenManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TokenManager: {e}")
            raise TokenUsageError(f"Initialization failed: {e}")

    async def _create_tables(self) -> None:
        """Create token usage table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            user_id TEXT,
            request_type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_token_usage_provider ON token_usage(provider);",
            "CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp ON token_usage(timestamp);",
            "CREATE INDEX IF NOT EXISTS idx_token_usage_user ON token_usage(user_id);",
        ]

        async with self.db.get_connection() as conn:
            await conn.execute(create_table_sql)
            for index_sql in indexes:
                await conn.execute(index_sql)
            await conn.commit()

        logger.debug("Token usage tables created successfully")

    async def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        user_id: Optional[str] = None,
        request_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record token usage for a specific API call.

        Args:
            provider: API provider ('gemini', 'openai')
            model: Model name used
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
            user_id: Discord user ID
            request_type: Type of request ('embedding', 'chat', 'transcription')
            metadata: Additional metadata for the request

        Raises:
            TokenUsageError: If recording fails
        """
        if not self._initialized:
            await self.init_async()

        try:
            total_tokens = input_tokens + output_tokens
            cost_usd = self.calculate_cost(provider, model, total_tokens)

            metadata_json = json.dumps(metadata or {})

            insert_sql = """
            INSERT INTO token_usage (
                provider, model, input_tokens, output_tokens,
                cost_usd, user_id, request_type, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            async with self.db.get_connection() as conn:
                await conn.execute(
                    insert_sql,
                    (
                        provider,
                        model,
                        input_tokens,
                        output_tokens,
                        cost_usd,
                        user_id,
                        request_type,
                        metadata_json,
                    ),
                )
                await conn.commit()

            logger.debug(
                f"Recorded token usage: {provider}/{model} - "
                f"{total_tokens} tokens, ${cost_usd:.4f}"
            )

        except Exception as e:
            logger.error(f"Failed to record token usage: {e}")
            raise TokenUsageError(f"Failed to record usage: {e}")

    def calculate_cost(self, provider: str, model: str, tokens: int) -> float:
        """
        Calculate cost for token usage.

        Args:
            provider: API provider name
            model: Model name
            tokens: Number of tokens used

        Returns:
            Cost in USD
        """
        try:
            provider_rates = self.COST_RATES.get(provider, {})
            rate_per_1k = provider_rates.get(model, 0.0)
            return (tokens / 1000.0) * rate_per_1k
        except Exception as e:
            logger.warning(f"Cost calculation failed for {provider}/{model}: {e}")
            return 0.0

    async def get_monthly_usage(
        self,
        provider: Optional[str] = None,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get monthly token usage statistics.

        Args:
            provider: Filter by specific provider
            year: Target year (defaults to current)
            month: Target month (defaults to current)

        Returns:
            Dictionary with usage statistics
        """
        if not self._initialized:
            await self.init_async()

        now = datetime.now()
        year = year or now.year
        month = month or now.month

        # Calculate month boundaries
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        try:
            where_clause = "WHERE timestamp >= ? AND timestamp < ?"
            params = [start_date.isoformat(), end_date.isoformat()]

            if provider:
                where_clause += " AND provider = ?"
                params.append(provider)

            usage_sql = f"""
            SELECT
                provider,
                model,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(input_tokens + output_tokens) as total_tokens,
                SUM(cost_usd) as total_cost,
                COUNT(*) as request_count
            FROM token_usage
            {where_clause}
            GROUP BY provider, model
            ORDER BY total_tokens DESC
            """

            async with self.db.get_connection() as conn:
                cursor = await conn.execute(usage_sql, params)
                rows = await cursor.fetchall()

            # Format results
            usage_data = []
            total_tokens = 0
            total_cost = 0.0

            for row in rows:
                data = {
                    "provider": row[0],
                    "model": row[1],
                    "input_tokens": row[2],
                    "output_tokens": row[3],
                    "total_tokens": row[4],
                    "cost_usd": row[5],
                    "requests": row[6],
                }
                usage_data.append(data)
                total_tokens += data["total_tokens"]
                total_cost += data["cost_usd"]

            return {
                "year": year,
                "month": month,
                "period": f"{year}-{month:02d}",
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost,
                "providers": usage_data,
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get monthly usage: {e}")
            raise TokenUsageError(f"Failed to get monthly usage: {e}")

    async def check_limits(self, provider: str) -> Dict[str, Any]:
        """
        Check current usage against configured limits.

        Args:
            provider: Provider to check ('gemini', 'openai')

        Returns:
            Dictionary with limit check results
        """
        if not self._initialized:
            await self.init_async()

        try:
            # Get current month usage
            monthly_usage = await self.get_monthly_usage(provider)
            current_tokens = monthly_usage["total_tokens"]

            # Get configured limits
            limits = self._get_provider_limits(provider)
            monthly_limit = limits.get("monthly_limit", float("inf"))

            # Calculate usage percentages
            monthly_usage_pct = (
                (current_tokens / monthly_limit * 100) if monthly_limit != float("inf") else 0
            )

            return {
                "provider": provider,
                "current_monthly_tokens": current_tokens,
                "monthly_limit": monthly_limit,
                "monthly_usage_percentage": monthly_usage_pct,
                "monthly_limit_exceeded": current_tokens > monthly_limit,
                "approaching_limit": monthly_usage_pct > 80.0,
                "usage_data": monthly_usage,
                "checked_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to check limits for {provider}: {e}")
            raise TokenUsageError(f"Failed to check limits: {e}")

    def _get_provider_limits(self, provider: str) -> Dict[str, Any]:
        """Get configured limits for a provider."""
        if provider == "gemini":
            return {"monthly_limit": getattr(self.config, "gemini_monthly_limit", 1000000)}
        elif provider == "openai":
            return {"monthly_limit": getattr(self.config, "openai_monthly_limit", 100000)}
        else:
            return {"monthly_limit": float("inf")}

    async def get_usage_history(
        self, provider: Optional[str] = None, days: int = 30, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get historical usage data.

        Args:
            provider: Filter by provider
            days: Number of days to retrieve
            user_id: Filter by user ID

        Returns:
            List of usage records
        """
        if not self._initialized:
            await self.init_async()

        try:
            start_date = datetime.now() - timedelta(days=days)

            where_conditions = ["timestamp >= ?"]
            params = [start_date.isoformat()]

            if provider:
                where_conditions.append("provider = ?")
                params.append(provider)

            if user_id:
                where_conditions.append("user_id = ?")
                params.append(user_id)

            where_clause = " AND ".join(where_conditions)

            history_sql = f"""
            SELECT
                provider, model, input_tokens, output_tokens,
                cost_usd, user_id, request_type, timestamp, metadata
            FROM token_usage
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT 1000
            """

            async with self.db.get_connection() as conn:
                cursor = await conn.execute(history_sql, params)
                rows = await cursor.fetchall()

            history = []
            for row in rows:
                try:
                    metadata = json.loads(row[8]) if row[8] else {}
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

                history.append(
                    {
                        "provider": row[0],
                        "model": row[1],
                        "input_tokens": row[2],
                        "output_tokens": row[3],
                        "total_tokens": row[2] + row[3],
                        "cost_usd": row[4],
                        "user_id": row[5],
                        "request_type": row[6],
                        "timestamp": row[7],
                        "metadata": metadata,
                    }
                )

            return history

        except Exception as e:
            logger.error(f"Failed to get usage history: {e}")
            raise TokenUsageError(f"Failed to get usage history: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on TokenManager."""
        try:
            if not self._initialized:
                return {"status": "unhealthy", "error": "Not initialized"}

            # Test database connectivity
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM token_usage WHERE timestamp >= datetime('now', '-7 days')"
                )
                recent_records = (await cursor.fetchone())[0]

            return {
                "status": "healthy",
                "initialized": self._initialized,
                "recent_records": recent_records,
                "supported_providers": list(self.COST_RATES.keys()),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False
        logger.info("TokenManager closed")
