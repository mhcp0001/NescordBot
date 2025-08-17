"""
Test cases for DatabaseService.

Tests basic database operations, error handling, and concurrent access.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from nescordbot.services.database import DatabaseService, IDataStore


class TestDatabaseService:
    """Test cases for DatabaseService implementation."""

    @pytest.fixture
    async def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        service = DatabaseService(db_path)
        await service.initialize()

        yield service

        await service.close()
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def memory_db(self):
        """Create an in-memory database for testing."""
        return DatabaseService(":memory:")

    async def test_initialization(self, memory_db):
        """Test database initialization."""
        await memory_db.initialize()
        assert memory_db.is_initialized
        await memory_db.close()

    async def test_basic_operations(self, temp_db):
        """Test basic set/get/delete operations."""
        # Test set and get
        await temp_db.set("test_key", "test_value")
        result = await temp_db.get("test_key")
        assert result == "test_value"

        # Test get non-existent key
        result = await temp_db.get("non_existent")
        assert result is None

        # Test delete
        await temp_db.delete("test_key")
        result = await temp_db.get("test_key")
        assert result is None

    async def test_json_operations(self, temp_db):
        """Test JSON set/get operations."""
        test_data = {
            "name": "TestBot",
            "version": "1.0.0",
            "features": ["logging", "database", "commands"],
            "config": {"debug": True, "max_users": 100},
        }

        # Test JSON set and get
        await temp_db.set_json("config", test_data)
        result = await temp_db.get_json("config")
        assert result == test_data

        # Test get non-existent JSON
        result = await temp_db.get_json("non_existent")
        assert result is None

        # Test invalid JSON handling
        await temp_db.set("invalid_json", "not a json")
        result = await temp_db.get_json("invalid_json")
        assert result is None

    async def test_key_operations(self, temp_db):
        """Test key listing and existence operations."""
        # Setup test data
        await temp_db.set("key1", "value1")
        await temp_db.set("key2", "value2")
        await temp_db.set_json("json_key", {"test": True})

        # Test exists
        assert await temp_db.exists("key1") is True
        assert await temp_db.exists("non_existent") is False

        # Test keys
        keys = await temp_db.keys()
        assert set(keys) == {"key1", "key2", "json_key"}

        # Test keys with pattern
        keys = await temp_db.keys("key*")
        assert set(keys) == {"key1", "key2"}

    async def test_concurrent_access(self, temp_db):
        """Test concurrent database operations."""

        async def write_data(key: str, value: str):
            await temp_db.set(key, value)

        async def read_data(key: str) -> str:
            result = await temp_db.get(key)
            return str(result) if result is not None else ""

        # Concurrent writes
        tasks = [write_data(f"key_{i}", f"value_{i}") for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all data was written
        for i in range(10):
            result = await temp_db.get(f"key_{i}")
            assert result == f"value_{i}"

        # Concurrent reads
        tasks = [read_data(f"key_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            assert result == f"value_{i}"

    async def test_error_handling(self):
        """Test error handling for invalid operations."""
        # Test with a path that cannot be created (no permissions)
        if Path("/").exists():  # Unix-like system
            service = DatabaseService("/root/nescord_test.db")
        else:  # Windows or other systems
            service = DatabaseService("C:\\Windows\\System32\\nescord_test.db")

        # Test initialization with invalid path (should raise exception)
        try:
            await service.initialize()
            # If no exception was raised, skip this test (permissions may vary)
            pytest.skip("Permission test skipped - path may be accessible")
        except Exception:
            # Expected behavior
            pass

    async def test_close_and_reinitialize(self, temp_db):
        """Test closing and reinitializing database."""
        # Add some data
        await temp_db.set("test", "value")

        # Close database
        await temp_db.close()
        assert not temp_db.is_initialized

        # Reinitialize
        await temp_db.initialize()
        assert temp_db.is_initialized

        # Data should persist
        result = await temp_db.get("test")
        assert result == "value"

    async def test_transaction_like_behavior(self, temp_db):
        """Test multiple operations work correctly together."""
        # Simulate a complex operation
        user_data = {"id": "user123", "name": "TestUser", "settings": {"theme": "dark"}}

        await temp_db.set_json("user:user123", user_data)
        await temp_db.set("user:user123:last_seen", "2024-01-01T00:00:00Z")
        await temp_db.set("stats:total_users", "1")

        # Verify all operations completed
        stored_user = await temp_db.get_json("user:user123")
        last_seen = await temp_db.get("user:user123:last_seen")
        total_users = await temp_db.get("stats:total_users")

        assert stored_user == user_data
        assert last_seen == "2024-01-01T00:00:00Z"
        assert total_users == "1"


class TestIDataStoreInterface:
    """Test the IDataStore interface compliance."""

    def test_interface_methods(self):
        """Test that DatabaseService implements IDataStore interface."""
        service = DatabaseService(":memory:")

        # Check that all required methods exist
        assert hasattr(service, "initialize")
        assert hasattr(service, "close")
        assert hasattr(service, "get")
        assert hasattr(service, "set")
        assert hasattr(service, "delete")
        assert hasattr(service, "get_json")
        assert hasattr(service, "set_json")
        assert hasattr(service, "exists")
        assert hasattr(service, "keys")

        # Check methods are callable
        assert callable(service.initialize)
        assert callable(service.close)
        assert callable(service.get)
        assert callable(service.set)
        assert callable(service.delete)
        assert callable(service.get_json)
        assert callable(service.set_json)
        assert callable(service.exists)
        assert callable(service.keys)


@pytest.mark.integration
class TestDatabaseServiceIntegration:
    """Integration tests for DatabaseService with realistic scenarios."""

    @pytest.fixture
    async def persistent_db(self):
        """Create a persistent database for integration testing."""
        db_path = Path("test_integration.db")
        service = DatabaseService(str(db_path))
        await service.initialize()

        yield service

        await service.close()
        db_path.unlink(missing_ok=True)

    async def test_bot_configuration_storage(self, persistent_db):
        """Test storing and retrieving bot configuration."""
        config = {
            "discord": {"token": "test_token", "guild_id": 123456789},
            "features": {"voice_processing": True, "github_integration": False},
            "limits": {"max_audio_size": 25, "rate_limit": 10},
        }

        await persistent_db.set_json("bot:config", config)

        # Simulate restart - close and reopen
        await persistent_db.close()
        await persistent_db.initialize()

        retrieved_config = await persistent_db.get_json("bot:config")
        assert retrieved_config == config

    async def test_user_session_management(self, persistent_db):
        """Test managing user sessions and preferences."""
        users = [
            {"id": "user1", "name": "Alice", "preferences": {"theme": "dark"}},
            {"id": "user2", "name": "Bob", "preferences": {"theme": "light"}},
            {"id": "user3", "name": "Charlie", "preferences": {"theme": "auto"}},
        ]

        # Store user data
        for user in users:
            await persistent_db.set_json(f"user:{user['id']}", user)
            await persistent_db.set(f"session:{user['id']}", "active")

        # Retrieve all users
        user_keys = await persistent_db.keys("user:*")
        assert len(user_keys) == 3

        # Retrieve specific user
        alice = await persistent_db.get_json("user:user1")
        assert alice["name"] == "Alice"

        # Check session status
        session_keys = await persistent_db.keys("session:*")
        assert len(session_keys) == 3
