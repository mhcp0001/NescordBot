"""
TestServiceContainer - Complete Test Isolation

This module provides a test-only ServiceContainer that completely blocks
real service creation and ensures 100% mocked environment.
"""

import logging
from typing import Any, Callable, Dict, Type, TypeVar

from src.nescordbot.config import BotConfig
from src.nescordbot.services.service_container import ServiceContainer

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TestConfigurationError(Exception):
    """Raised when test configuration is invalid or incomplete."""

    pass


class TestServiceContainer(ServiceContainer):
    """
    Test-only ServiceContainer that completely blocks real service creation.

    Key differences from production ServiceContainer:
    1. Blocks all factory registration in test mode
    2. Only serves pre-registered mock services
    3. Raises clear errors for missing mocks
    4. Provides detailed logging for debugging
    """

    def __init__(self, config: BotConfig):
        super().__init__(config)
        self._test_mode = True
        self._mock_registry: Dict[Type, Any] = {}
        self._blocked_factories: Dict[Type, str] = {}

        # Pre-populate blocked factories for demonstration in tests
        # These represent the factories that would have been blocked during normal initialization
        from src.nescordbot.services import (
            AlertManager,
            APIMonitor,
            ChromaDBService,
            EmbeddingService,
            FallbackManager,
            KnowledgeManager,
            Phase4Monitor,
            PrivacyManager,
            SearchEngine,
            SyncManager,
            TokenManager,
        )

        for service_type in [
            TokenManager,
            PrivacyManager,
            KnowledgeManager,
            AlertManager,
            EmbeddingService,
            ChromaDBService,
            SearchEngine,
            SyncManager,
            FallbackManager,
            APIMonitor,
            Phase4Monitor,
        ]:
            self._blocked_factories[service_type] = f"Blocked_{service_type.__name__}_factory"

        logger.info("TestServiceContainer initialized - real service creation blocked")

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """
        Block factory registration in test mode.

        This prevents the accidental creation of real services during testing.
        """
        if self._test_mode:
            factory_name = getattr(factory, "__name__", str(factory))
            self._blocked_factories[service_type] = factory_name
            logger.debug(
                f"Blocked factory registration for {service_type.__name__}: {factory_name}"
            )
            return

        # In non-test mode, delegate to parent
        super().register_factory(service_type, factory)

    def register_test_mock(self, service_type: Type[T], mock: T) -> None:
        """
        Register a test mock service.

        This is the only way to register services in TestServiceContainer.
        """
        self._mock_registry[service_type] = mock
        self.register_singleton(service_type, mock)
        logger.debug(f"Registered test mock for {service_type.__name__}")

    def get_service(self, service_type: Type[T]) -> T:  # type: ignore
        """
        Get service from mock registry only.

        Raises TestConfigurationError if mock is not registered,
        preventing accidental real service creation.
        """
        # Check mock registry first
        if service_type in self._mock_registry:
            return self._mock_registry[service_type]  # type: ignore

        # Check singletons (for compatibility)
        if service_type in self._singletons:
            return self._singletons[service_type]  # type: ignore

        # If we reach here, no mock was registered
        blocked_factory = self._blocked_factories.get(service_type, "Unknown")
        raise TestConfigurationError(
            f"No mock registered for {service_type.__name__}. "
            f"Blocked factory: {blocked_factory}. "
            f"Register mock using register_test_mock() before testing."
        )

    def has_service(self, service_type: Type[T]) -> bool:
        """Check if a mock service is registered."""
        return service_type in self._mock_registry or service_type in self._singletons

    def get_test_info(self) -> Dict[str, Any]:
        """Get detailed information about test configuration."""
        return {
            "test_mode": self._test_mode,
            "registered_mocks": [
                service_type.__name__ for service_type in self._mock_registry.keys()
            ],
            "blocked_factories": [
                f"{service_type.__name__}: {factory_name}"
                for service_type, factory_name in self._blocked_factories.items()
            ],
            "singleton_count": len(self._singletons),
            "total_services": len(self._mock_registry) + len(self._singletons),
        }

    async def initialize_services(self) -> None:
        """
        Initialize all registered mock services.

        Only calls init_async on services that have this method.
        """
        if self._initialized:
            return

        logger.info("Initializing test mock services...")

        # Initialize mocks with init_async method
        services = list(self._mock_registry.values()) + list(self._singletons.values())

        for service in services:
            if hasattr(service, "init_async"):
                try:
                    logger.debug(f"Initializing mock {service.__class__.__name__}...")
                    await service.init_async()
                except Exception as e:
                    logger.error(f"Failed to initialize mock {service.__class__.__name__}: {e}")
                    # Don't raise - mocks should be fault-tolerant

        self._initialized = True
        logger.info(f"All {len(services)} mock services initialized successfully")

    async def shutdown_services(self) -> None:
        """Shutdown all mock services gracefully."""
        if self._shutdown:
            return

        logger.info("Shutting down test mock services...")

        # Shutdown in reverse order
        services = list(self._mock_registry.values()) + list(self._singletons.values())

        for service in reversed(services):
            if hasattr(service, "shutdown_async"):
                try:
                    logger.debug(f"Shutting down mock {service.__class__.__name__}...")
                    await service.shutdown_async()
                except Exception as e:
                    logger.error(f"Error shutting down mock {service.__class__.__name__}: {e}")

        # Clear all registrations
        self._mock_registry.clear()
        self._singletons.clear()
        self._blocked_factories.clear()

        self._shutdown = True
        self._initialized = False
        logger.info("All mock services shut down")
