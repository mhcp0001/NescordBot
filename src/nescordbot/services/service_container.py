"""
Service container for dependency injection.

This module provides a dependency injection container that manages
service lifecycle and dependencies throughout the application.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar

from ..config import BotConfig
from ..logger import get_logger

T = TypeVar("T")


class ServiceNotFoundError(Exception):
    """Exception raised when a requested service is not found."""

    def __init__(self, service_type: Type) -> None:
        super().__init__(f"Service of type {service_type.__name__} not found")
        self.service_type = service_type


class ServiceInitializationError(Exception):
    """Exception raised when service initialization fails."""

    def __init__(self, service_type: Type, error: Exception) -> None:
        super().__init__(f"Failed to initialize service {service_type.__name__}: {error}")
        self.service_type = service_type
        self.error = error


class ServiceContainer:
    """
    Dependency injection container for managing service lifecycle.

    This container provides:
    - Service registration and retrieval
    - Singleton pattern enforcement
    - Async service initialization
    - Graceful service shutdown
    - Configuration-based service setup
    """

    def __init__(self, config: Optional[BotConfig] = None) -> None:
        """Initialize the service container."""
        self.config = config
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Any] = {}
        self._initialized: bool = False
        self._shutdown: bool = False
        self._logger: Optional[logging.Logger] = None

    def _get_logger(self) -> logging.Logger:
        """Get logger instance."""
        if self._logger is None:
            self._logger = get_logger("service_container")
        return self._logger

    def register_service(self, service_type: Type[T], instance: T) -> None:
        """
        Register a service instance.

        Args:
            service_type: The service type to register
            instance: The service instance
        """
        if self._shutdown:
            raise RuntimeError("Cannot register services after shutdown")

        self._services[service_type] = instance
        self._get_logger().debug(f"Registered service: {service_type.__name__}")

    def register_singleton(self, service_type: Type[T], instance: T) -> None:
        """
        Register a singleton service instance.

        Args:
            service_type: The service type to register
            instance: The singleton service instance
        """
        if self._shutdown:
            raise RuntimeError("Cannot register services after shutdown")

        self._singletons[service_type] = instance
        self._get_logger().debug(f"Registered singleton: {service_type.__name__}")

    def register_factory(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """
        Register a service factory function.

        Args:
            service_type: The service type to register
            factory: Factory function that creates the service instance
        """
        if self._shutdown:
            raise RuntimeError("Cannot register services after shutdown")

        self._factories[service_type] = factory
        self._get_logger().debug(f"Registered factory: {service_type.__name__}")

    def get_service(self, service_type: Type[T]) -> T:
        """
        Get a service instance.

        Args:
            service_type: The service type to retrieve

        Returns:
            The service instance

        Raises:
            ServiceNotFoundError: If the service is not found
        """
        if self._shutdown:
            raise RuntimeError("Cannot get services after shutdown")

        # Check singletons first
        if service_type in self._singletons:
            return self._singletons[service_type]  # type: ignore[no-any-return]

        # Check registered services
        if service_type in self._services:
            return self._services[service_type]  # type: ignore[no-any-return]

        # Check factories
        if service_type in self._factories:
            try:
                instance = self._factories[service_type]()
                # Store as singleton for factories
                self._singletons[service_type] = instance
                self._get_logger().debug(f"Created service from factory: {service_type.__name__}")
                return instance  # type: ignore[no-any-return]
            except Exception as e:
                raise ServiceInitializationError(service_type, e)

        raise ServiceNotFoundError(service_type)

    def has_service(self, service_type: Type[T]) -> bool:
        """
        Check if a service is registered.

        Args:
            service_type: The service type to check

        Returns:
            True if the service is registered, False otherwise
        """
        return (
            service_type in self._services
            or service_type in self._singletons
            or service_type in self._factories
        )

    async def initialize_services(self) -> None:
        """Initialize all services that require async initialization."""
        if self._initialized:
            return

        logger = self._get_logger()
        logger.info("Initializing services...")

        # Initialize services with init_async method
        for service in list(self._services.values()) + list(self._singletons.values()):
            if hasattr(service, "init_async"):
                try:
                    logger.debug(f"Initializing {service.__class__.__name__}...")
                    await service.init_async()
                except Exception as e:
                    logger.error(f"Failed to initialize {service.__class__.__name__}: {e}")
                    raise ServiceInitializationError(service.__class__, e)

        self._initialized = True
        logger.info("All services initialized successfully")

    async def shutdown_services(self) -> None:
        """Shutdown all services gracefully."""
        if self._shutdown:
            return

        logger = self._get_logger()
        logger.info("Shutting down services...")

        # Shutdown services with shutdown_async method
        services = list(self._services.values()) + list(self._singletons.values())

        # Shutdown in reverse order
        for service in reversed(services):
            if hasattr(service, "shutdown_async"):
                try:
                    logger.debug(f"Shutting down {service.__class__.__name__}...")
                    await service.shutdown_async()
                except Exception as e:
                    logger.error(f"Error shutting down {service.__class__.__name__}: {e}")

        # Clear all services
        self._services.clear()
        self._singletons.clear()
        self._factories.clear()

        self._shutdown = True
        self._initialized = False
        logger.info("All services shut down")

    def get_all_services(self) -> List[Any]:
        """
        Get all registered service instances.

        Returns:
            List of all service instances
        """
        services: List[Any] = []
        services.extend(self._services.values())
        services.extend(self._singletons.values())
        return services

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about registered services.

        Returns:
            Dictionary with service information
        """
        return {
            "services": {
                service_type.__name__: type(instance).__name__
                for service_type, instance in self._services.items()
            },
            "singletons": {
                service_type.__name__: type(instance).__name__
                for service_type, instance in self._singletons.items()
            },
            "factories": {
                service_type.__name__: factory.__name__
                for service_type, factory in self._factories.items()
            },
            "initialized": self._initialized,
            "shutdown": self._shutdown,
            "total_services": len(self._services) + len(self._singletons) + len(self._factories),
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all services.

        Returns:
            Dictionary with health check results
        """
        health_status: Dict[str, Any] = {
            "container_status": "healthy"
            if self._initialized and not self._shutdown
            else "unhealthy",
            "services": {},
        }

        services = list(self._services.values()) + list(self._singletons.values())

        for service in services:
            service_name = service.__class__.__name__
            services_dict = health_status["services"]

            if hasattr(service, "health_check"):
                try:
                    if asyncio.iscoroutinefunction(service.health_check):
                        result = await service.health_check()
                    else:
                        result = service.health_check()
                    services_dict[service_name] = result
                except Exception as e:
                    services_dict[service_name] = {"status": "error", "error": str(e)}
            else:
                services_dict[service_name] = {"status": "no_health_check"}

        return health_status


# Global service container instance
_service_container: Optional[ServiceContainer] = None


def get_service_container() -> ServiceContainer:
    """Get the global service container instance."""
    global _service_container
    if _service_container is None:
        raise RuntimeError(
            "Service container not initialized. Call create_service_container() first."
        )
    return _service_container


def create_service_container(config: Optional[BotConfig] = None) -> ServiceContainer:
    """Create and set the global service container instance."""
    global _service_container
    _service_container = ServiceContainer(config)
    return _service_container


def reset_service_container() -> None:
    """Reset the global service container instance (for testing)."""
    global _service_container
    _service_container = None
