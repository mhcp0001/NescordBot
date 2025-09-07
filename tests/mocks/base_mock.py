"""
Base Mock Classes

Provides base functionality for all service mocks.
"""

import logging
from typing import Any, Dict, Type
from unittest.mock import AsyncMock

logger = logging.getLogger(__name__)


class BaseMockService:
    """Base class for all mock services."""

    @classmethod
    def create_mock(cls, service_type: Type, config=None, **kwargs) -> AsyncMock:
        """
        Create a basic mock for any service type.

        Args:
            service_type: The service class to mock
            config: Configuration object
            **kwargs: Additional dependencies

        Returns:
            AsyncMock with basic setup
        """
        mock = AsyncMock(spec=service_type)
        mock._initialized = True
        mock.config = config

        # Set up basic methods that all services should have
        cls._setup_basic_methods(mock)

        logger.debug(f"Created base mock for {service_type.__name__}")
        return mock

    @staticmethod
    def _setup_basic_methods(mock: AsyncMock) -> None:
        """Set up methods common to all services."""
        mock.health_check = AsyncMock(return_value={"status": "healthy"})
        mock.init_async = AsyncMock()
        mock.shutdown_async = AsyncMock()


class DatabaseAwareMock(BaseMockService):
    """Base class for mocks that need database functionality."""

    @classmethod
    def create_db_mock(
        cls, service_type: Type, config=None, db_service=None, **kwargs
    ) -> AsyncMock:
        """
        Create a mock with database functionality.

        Args:
            service_type: The service class to mock
            config: Configuration object
            db_service: Mock database service
            **kwargs: Additional dependencies

        Returns:
            AsyncMock with database setup
        """
        mock = cls.create_mock(service_type, config, **kwargs)
        mock.db = db_service or cls._create_inline_db_mock()

        # Database-aware services initialization
        cls._setup_database_methods(mock)

        logger.debug(f"Created database-aware mock for {service_type.__name__}")
        return mock

    @staticmethod
    def _create_inline_db_mock():
        """Create an inline database mock."""
        from unittest.mock import MagicMock

        mock_connection = AsyncMock()
        mock_connection.execute = AsyncMock()
        mock_connection.fetchall = AsyncMock(return_value=[])
        mock_connection.fetchone = AsyncMock(return_value=None)
        mock_connection.commit = AsyncMock()

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_context.__aexit__ = AsyncMock()

        db_mock = AsyncMock()
        db_mock._initialized = True
        db_mock.get_connection = MagicMock(return_value=mock_context)

        return db_mock

    @staticmethod
    def _setup_database_methods(mock: AsyncMock) -> None:
        """Set up database-related methods."""
        mock.initialize = AsyncMock()
        mock._create_tables = AsyncMock()


class RealisticResponseMixin:
    """Mixin for creating realistic responses."""

    @staticmethod
    def create_realistic_usage_data() -> Dict[str, Any]:
        """Create realistic token usage data."""
        return {
            "provider": "test_provider",
            "model": "test_model",
            "input_tokens": 100,
            "output_tokens": 50,
            "cost_usd": 0.001,
            "timestamp": "2025-09-06T12:00:00Z",
        }

    @staticmethod
    def create_realistic_note_data() -> Dict[str, Any]:
        """Create realistic note data."""
        return {
            "id": "note_123",
            "title": "Test Note",
            "content": "This is test content for integration testing",
            "tags": ["test", "integration"],
            "created_at": "2025-09-06T12:00:00Z",
            "updated_at": "2025-09-06T12:00:00Z",
        }

    @staticmethod
    def create_realistic_pii_rules():
        """Create realistic PII detection rules."""
        from unittest.mock import Mock

        # Create mock PII rule
        mock_rule = Mock()
        mock_rule.name = "email"
        mock_rule.pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        mock_rule.severity = "HIGH"

        return [(mock_rule, ["test@example.com"])]
