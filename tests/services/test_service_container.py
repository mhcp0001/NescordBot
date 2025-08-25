"""
Tests for ServiceContainer.

This module tests the dependency injection container functionality.
"""

import asyncio
from unittest.mock import Mock

import pytest

from nescordbot.config import BotConfig
from nescordbot.services.service_container import (
    ServiceContainer,
    ServiceInitializationError,
    ServiceNotFoundError,
    create_service_container,
    get_service_container,
    reset_service_container,
)


class MockService:
    """Mock service for testing."""

    def __init__(self):
        self.initialized = False
        self.shutdown = False

    async def init_async(self):
        """Mock async initialization."""
        self.initialized = True

    async def shutdown_async(self):
        """Mock async shutdown."""
        self.shutdown = True

    def health_check(self):
        """Mock health check."""
        return {"status": "healthy"}


class MockServiceWithError:
    """Mock service that fails initialization."""

    async def init_async(self):
        """Mock async initialization that fails."""
        raise RuntimeError("Initialization failed")


class TestServiceContainer:
    """Test cases for ServiceContainer."""

    @pytest.fixture
    def container(self):
        """Create a service container for testing."""
        config = Mock(spec=BotConfig)
        return ServiceContainer(config)

    @pytest.fixture(autouse=True)
    def cleanup_global_container(self):
        """Reset global container after each test."""
        yield
        reset_service_container()

    def test_register_and_get_service(self, container):
        """Test service registration and retrieval."""
        service = MockService()
        container.register_service(MockService, service)

        retrieved = container.get_service(MockService)
        assert retrieved is service

    def test_register_and_get_singleton(self, container):
        """Test singleton registration and retrieval."""
        service = MockService()
        container.register_singleton(MockService, service)

        retrieved1 = container.get_service(MockService)
        retrieved2 = container.get_service(MockService)

        assert retrieved1 is service
        assert retrieved1 is retrieved2

    def test_register_and_get_factory(self, container):
        """Test factory registration and service creation."""

        def factory():
            return MockService()

        container.register_factory(MockService, factory)

        service1 = container.get_service(MockService)
        service2 = container.get_service(MockService)

        # Factory creates singleton on first call
        assert service1 is service2
        assert isinstance(service1, MockService)

    def test_service_not_found(self, container):
        """Test ServiceNotFoundError when service is not registered."""
        with pytest.raises(ServiceNotFoundError) as exc_info:
            container.get_service(MockService)

        assert exc_info.value.service_type is MockService

    def test_has_service(self, container):
        """Test has_service method."""
        assert not container.has_service(MockService)

        service = MockService()
        container.register_service(MockService, service)
        assert container.has_service(MockService)

    def test_factory_initialization_error(self, container):
        """Test ServiceInitializationError when factory fails."""

        def failing_factory():
            raise RuntimeError("Factory failed")

        container.register_factory(MockService, failing_factory)

        with pytest.raises(ServiceInitializationError) as exc_info:
            container.get_service(MockService)

        assert exc_info.value.service_type is MockService
        assert "Factory failed" in str(exc_info.value.error)

    @pytest.mark.asyncio
    async def test_initialize_services(self, container):
        """Test async service initialization."""
        service = MockService()
        container.register_service(MockService, service)

        assert not service.initialized
        await container.initialize_services()
        assert service.initialized

    @pytest.mark.asyncio
    async def test_initialize_services_error(self, container):
        """Test initialization error handling."""
        service = MockServiceWithError()
        container.register_service(MockServiceWithError, service)

        with pytest.raises(ServiceInitializationError):
            await container.initialize_services()

    @pytest.mark.asyncio
    async def test_shutdown_services(self, container):
        """Test async service shutdown."""
        service = MockService()
        container.register_service(MockService, service)

        await container.initialize_services()
        assert not service.shutdown

        await container.shutdown_services()
        assert service.shutdown

    @pytest.mark.asyncio
    async def test_health_check(self, container):
        """Test health check functionality."""
        service = MockService()
        container.register_service(MockService, service)
        await container.initialize_services()

        health = await container.health_check()

        assert health["container_status"] == "healthy"
        assert "MockService" in health["services"]
        assert health["services"]["MockService"]["status"] == "healthy"

    def test_get_service_info(self, container):
        """Test service information retrieval."""
        service = MockService()
        container.register_service(MockService, service)

        info = container.get_service_info()

        assert "MockService" in info["services"]
        assert info["total_services"] == 1
        assert not info["initialized"]
        assert not info["shutdown"]

    def test_get_all_services(self, container):
        """Test get all services functionality."""
        service1 = MockService()
        service2 = MockService()

        container.register_service(MockService, service1)
        container.register_singleton(str, service2)

        services = container.get_all_services()
        assert len(services) == 2
        assert service1 in services
        assert service2 in services

    def test_operations_after_shutdown(self, container):
        """Test that operations fail after shutdown."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(container.shutdown_services())

            with pytest.raises(RuntimeError):
                container.register_service(MockService, MockService())

            with pytest.raises(RuntimeError):
                container.get_service(MockService)
        finally:
            loop.close()


class TestGlobalServiceContainer:
    """Test cases for global service container functions."""

    @pytest.fixture(autouse=True)
    def cleanup_global_container(self):
        """Reset global container after each test."""
        yield
        reset_service_container()

    def test_create_and_get_service_container(self):
        """Test global container creation and retrieval."""
        config = Mock(spec=BotConfig)
        container = create_service_container(config)

        retrieved = get_service_container()
        assert retrieved is container
        assert retrieved.config is config

    def test_get_service_container_not_initialized(self):
        """Test error when getting container before creation."""
        with pytest.raises(RuntimeError, match="Service container not initialized"):
            get_service_container()

    def test_reset_service_container(self):
        """Test service container reset."""
        create_service_container()
        reset_service_container()

        with pytest.raises(RuntimeError):
            get_service_container()


@pytest.mark.asyncio
async def test_integration_scenario():
    """Test complete integration scenario."""
    # Setup
    config = Mock(spec=BotConfig)
    container = create_service_container(config)

    # Register services
    service1 = MockService()
    service2 = MockService()

    container.register_service(MockService, service1)
    container.register_singleton(str, service2)

    try:
        # Initialize
        await container.initialize_services()
        assert service1.initialized

        # Get services
        retrieved1 = container.get_service(MockService)
        assert retrieved1 is service1

        # Health check
        health = await container.health_check()
        assert health["container_status"] == "healthy"

        # Service info
        info = container.get_service_info()
        assert info["total_services"] == 2
        assert info["initialized"]

    finally:
        # Cleanup
        await container.shutdown_services()
        reset_service_container()

        assert service1.shutdown
