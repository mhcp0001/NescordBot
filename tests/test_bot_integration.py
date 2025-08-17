"""
Integration tests for NescordBot with DatabaseService integration.

Tests bot initialization, database service integration, and proper cleanup.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from nescordbot.bot import NescordBot


class TestBotDatabaseIntegration:
    """Test NescordBot integration with DatabaseService."""

    @pytest.fixture
    def mock_config(self, monkeypatch):
        """Mock configuration for testing."""

        class MockConfig:
            discord_token = "test_token"
            max_audio_size_mb = 25
            speech_language = "ja-JP"
            log_level = "INFO"
            database_url = ":memory:"  # Use in-memory database for testing

        class MockConfigManager:
            def __init__(self):
                self.config = MockConfig()

        def mock_get_config_manager():
            return MockConfigManager()

        # Mock the configuration manager
        monkeypatch.setattr("nescordbot.bot.get_config_manager", mock_get_config_manager)

        return MockConfig()

    @pytest.fixture
    def mock_logger(self, monkeypatch):
        """Mock logger for testing."""

        class MockLogger:
            def info(self, msg):
                print(f"INFO: {msg}")

            def error(self, msg):
                print(f"ERROR: {msg}")

            def warning(self, msg):
                print(f"WARNING: {msg}")

            def debug(self, msg):
                print(f"DEBUG: {msg}")

        def mock_get_logger(name):
            return MockLogger()

        monkeypatch.setattr("nescordbot.bot.get_logger", mock_get_logger)

    async def test_bot_initialization_with_database(self, mock_config, mock_logger):
        """Test that bot initializes with database service."""
        bot = NescordBot()

        # Check that database service is initialized
        assert hasattr(bot, "database_service")
        assert bot.database_service is not None
        assert not bot.database_service.is_initialized  # Not yet initialized

        # Cleanup
        await bot.close()

    async def test_bot_setup_hook_initializes_database(self, mock_config, mock_logger):
        """Test that setup_hook properly initializes database service."""
        bot = NescordBot()

        # Run setup hook (without actually connecting to Discord)
        await bot.setup_hook()

        # Check that database is initialized
        assert bot.database_service.is_initialized

        # Test database operations
        await bot.database_service.set("test_key", "test_value")
        result = await bot.database_service.get("test_key")
        assert result == "test_value"

        # Cleanup
        await bot.close()

    async def test_bot_close_properly_closes_database(self, mock_config, mock_logger):
        """Test that bot.close() properly closes database service."""
        bot = NescordBot()

        # Initialize database
        await bot.setup_hook()
        assert bot.database_service.is_initialized

        # Close bot
        await bot.close()

        # Check that database is closed
        assert not bot.database_service.is_initialized

    async def test_database_persistence_across_operations(self, mock_config, mock_logger):
        """Test that database maintains data across multiple operations."""
        bot = NescordBot()
        await bot.setup_hook()

        # Store configuration data
        config_data = {
            "bot_name": "NescordBot",
            "version": "1.0.0",
            "features": ["voice", "database", "commands"],
        }

        await bot.database_service.set_json("bot:config", config_data)

        # Store user preferences
        user_prefs = {"user_id": "123456789", "theme": "dark", "notifications": True}

        await bot.database_service.set_json("user:123456789:prefs", user_prefs)

        # Verify data persistence
        retrieved_config = await bot.database_service.get_json("bot:config")
        assert retrieved_config == config_data

        retrieved_prefs = await bot.database_service.get_json("user:123456789:prefs")
        assert retrieved_prefs == user_prefs

        # Test key listing
        keys = await bot.database_service.keys("*")
        assert "bot:config" in keys
        assert "user:123456789:prefs" in keys

        # Cleanup
        await bot.close()

    async def test_database_error_handling(self, mock_config, mock_logger):
        """Test database error handling scenarios."""
        bot = NescordBot()

        # Try to use database before initialization
        with pytest.raises(RuntimeError, match="Database not initialized"):
            await bot.database_service.get("test_key")

        # Initialize database
        await bot.setup_hook()

        # Test invalid JSON handling
        await bot.database_service.set("invalid_json", "not a json string")
        result = await bot.database_service.get_json("invalid_json")
        assert result is None  # Should return None for invalid JSON

        # Cleanup
        await bot.close()


@pytest.mark.integration
class TestBotDatabaseRealFile:
    """Integration tests with real database file."""

    @pytest.fixture
    def temp_db_config(self, monkeypatch):
        """Create temporary database file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        class MockConfig:
            discord_token = "test_token"
            max_audio_size_mb = 25
            speech_language = "ja-JP"
            log_level = "INFO"
            database_url = db_path

        class MockConfigManager:
            def __init__(self):
                self.config = MockConfig()

        def mock_get_config_manager():
            return MockConfigManager()

        monkeypatch.setattr("nescordbot.bot.get_config_manager", mock_get_config_manager)

        yield MockConfig()

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def mock_logger(self, monkeypatch):
        """Mock logger for testing."""

        class MockLogger:
            def info(self, msg):
                pass  # Silent for integration tests

            def error(self, msg):
                print(f"ERROR: {msg}")

            def warning(self, msg):
                pass

            def debug(self, msg):
                pass

        def mock_get_logger(name):
            return MockLogger()

        monkeypatch.setattr("nescordbot.bot.get_logger", mock_get_logger)

    async def test_database_file_persistence(self, temp_db_config, mock_logger):
        """Test that data persists to actual database file."""
        # First bot instance
        bot1 = NescordBot()
        await bot1.setup_hook()

        # Store some data
        await bot1.database_service.set("persistent_key", "persistent_value")
        await bot1.database_service.set_json("config", {"version": "1.0"})

        # Close first instance
        await bot1.close()

        # Create second bot instance with same database
        bot2 = NescordBot()
        await bot2.setup_hook()

        # Verify data persisted
        value = await bot2.database_service.get("persistent_key")
        assert value == "persistent_value"

        config = await bot2.database_service.get_json("config")
        assert config == {"version": "1.0"}

        # Cleanup
        await bot2.close()
