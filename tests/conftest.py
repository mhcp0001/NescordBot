"""
Pytest configuration and shared fixtures for NescordBot tests.

This module provides common fixtures and test utilities used across
all test modules in the NescordBot project.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import discord
from discord.ext import commands

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Set up test environment variables before each test."""
    # Store original values
    original_values = {}
    
    # Set required environment variables for testing
    test_env_vars = {
        "DISCORD_TOKEN": "MTA1234567890123456.GH7890.abcdefghijklmnop123456789012345678901234",
        "OPENAI_API_KEY": "sk-abcdef1234567890abcdef1234567890abcdef1234567890ab",
        "LOG_LEVEL": "DEBUG",
        "MAX_AUDIO_SIZE_MB": "25",
        "SPEECH_LANGUAGE": "ja"
    }
    
    for key, value in test_env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = original_value


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singleton instances before each test."""
    # Reset ConfigManager singleton
    import src.config
    src.config._config_manager = None
    
    # Reset LoggerService singleton
    import src.logger
    src.logger._logger_service = None
    
    yield
    
    # Clean up after test
    src.config._config_manager = None
    src.logger._logger_service = None


@pytest.fixture
def mock_discord_user():
    """Create a mock Discord user."""
    user = MagicMock(spec=discord.User)
    user.id = 123456789
    user.name = "test_user"
    user.display_name = "Test User"
    user.bot = False
    user.mention = "<@123456789>"
    return user


@pytest.fixture
def mock_discord_guild():
    """Create a mock Discord guild."""
    guild = MagicMock(spec=discord.Guild)
    guild.id = 987654321
    guild.name = "Test Server"
    guild.member_count = 100
    return guild


@pytest.fixture
def mock_discord_channel():
    """Create a mock Discord text channel."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 555666777
    channel.name = "test-channel"
    channel.mention = "<#555666777>"
    return channel


@pytest.fixture
def mock_discord_message(mock_discord_user, mock_discord_guild, mock_discord_channel):
    """Create a mock Discord message."""
    message = MagicMock(spec=discord.Message)
    message.id = 111222333
    message.author = mock_discord_user
    message.guild = mock_discord_guild
    message.channel = mock_discord_channel
    message.content = "Test message"
    message.attachments = []
    message.created_at = discord.utils.utcnow()
    
    # Mock async methods
    message.reply = AsyncMock()
    message.add_reaction = AsyncMock()
    message.remove_reaction = AsyncMock()
    
    return message


@pytest.fixture
def mock_discord_attachment():
    """Create a mock Discord attachment."""
    attachment = MagicMock(spec=discord.Attachment)
    attachment.id = 444555666
    attachment.filename = "test_audio.ogg"
    attachment.size = 1024 * 1024  # 1MB
    attachment.content_type = "audio/ogg"
    attachment.url = "https://cdn.discordapp.com/attachments/test_audio.ogg"
    
    # Mock async methods
    attachment.save = AsyncMock()
    attachment.read = AsyncMock(return_value=b"fake_audio_data")
    
    return attachment


@pytest.fixture
def mock_discord_interaction(mock_discord_user, mock_discord_guild, mock_discord_channel):
    """Create a mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.id = 777888999
    interaction.user = mock_discord_user
    interaction.guild = mock_discord_guild
    interaction.channel = mock_discord_channel
    interaction.data = {}
    interaction.locale = discord.Locale.japanese
    
    # Mock async methods
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    
    return interaction


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.guilds = True
    
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock(spec=discord.ClientUser)
    bot.user.id = 999888777
    bot.user.name = "NescordBot"
    bot.user.display_name = "NescordBot"
    bot.user.bot = True
    
    # Mock async methods
    bot.start = AsyncMock()
    bot.close = AsyncMock()
    bot.change_presence = AsyncMock()
    bot.load_extension = AsyncMock()
    bot.tree.sync = AsyncMock(return_value=[])
    
    return bot


@pytest.fixture
async def config_manager():
    """Get a configured ConfigManager instance."""
    from src.config import get_config_manager
    return get_config_manager()


@pytest.fixture
async def logger_service():
    """Get a configured LoggerService instance."""
    from src.logger import get_logger
    return get_logger("test")


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create a temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_audio_file(temp_data_dir):
    """Create a mock audio file for testing."""
    audio_file = temp_data_dir / "test_audio.ogg"
    audio_file.write_bytes(b"fake_audio_data" * 100)  # Create some fake audio data
    return audio_file


class AsyncContextManager:
    """Helper class for creating async context managers in tests."""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """Factory for creating async context managers."""
    return AsyncContextManager


def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Mark integration tests
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Mark network tests
        if any(keyword in item.name.lower() for keyword in ["api", "http", "network"]):
            item.add_marker(pytest.mark.network)


class MockBotContext:
    """
    Mock context for testing bot interactions.
    
    Provides a complete mock environment for testing Discord bot functionality
    without requiring actual Discord connections.
    """
    
    def __init__(self):
        self.bot = None
        self.guild = None
        self.channel = None
        self.user = None
        self.message = None
        self.interaction = None
        self.attachment = None
        
    def setup_basic_mocks(self):
        """Set up basic mock objects for testing."""
        # Mock bot
        self.bot = MagicMock(spec=commands.Bot)
        self.bot.user = MagicMock(spec=discord.ClientUser)
        self.bot.user.id = 999888777
        self.bot.user.name = "NescordBot"
        self.bot.user.bot = True
        self.bot.latency = 0.05
        self.bot.guilds = []
        
        # Mock async methods
        self.bot.start = AsyncMock()
        self.bot.close = AsyncMock()
        self.bot.change_presence = AsyncMock()
        self.bot.load_extension = AsyncMock()
        self.bot.tree.sync = AsyncMock(return_value=[])
        
        # Mock guild
        self.guild = MagicMock(spec=discord.Guild)
        self.guild.id = 987654321
        self.guild.name = "Test Server"
        self.guild.member_count = 100
        
        # Mock channel
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.id = 555666777
        self.channel.name = "test-channel"
        self.channel.mention = "<#555666777>"
        
        # Mock user
        self.user = MagicMock(spec=discord.User)
        self.user.id = 123456789
        self.user.name = "test_user"
        self.user.display_name = "Test User"
        self.user.bot = False
        self.user.mention = "<@123456789>"
        
        # Mock message
        self.message = MagicMock(spec=discord.Message)
        self.message.id = 111222333
        self.message.author = self.user
        self.message.guild = self.guild
        self.message.channel = self.channel
        self.message.content = "Test message"
        self.message.attachments = []
        self.message.created_at = discord.utils.utcnow()
        
        # Mock async methods for message
        self.message.reply = AsyncMock()
        self.message.add_reaction = AsyncMock()
        self.message.remove_reaction = AsyncMock()
        
        # Mock interaction
        self.interaction = MagicMock(spec=discord.Interaction)
        self.interaction.id = 777888999
        self.interaction.user = self.user
        self.interaction.guild = self.guild
        self.interaction.channel = self.channel
        self.interaction.data = {}
        self.interaction.locale = discord.Locale.japanese
        
        # Mock async methods for interaction
        self.interaction.response.send_message = AsyncMock()
        self.interaction.response.defer = AsyncMock()
        self.interaction.response.edit_message = AsyncMock()
        self.interaction.response.is_done = MagicMock(return_value=False)
        self.interaction.followup.send = AsyncMock()
        
        # Mock attachment
        self.attachment = MagicMock(spec=discord.Attachment)
        self.attachment.id = 444555666
        self.attachment.filename = "test_audio.ogg"
        self.attachment.size = 1024 * 1024  # 1MB
        self.attachment.content_type = "audio/ogg"
        self.attachment.url = "https://cdn.discordapp.com/attachments/test_audio.ogg"
        self.attachment.save = AsyncMock()
        self.attachment.read = AsyncMock(return_value=b"fake_audio_data")
        
        return self
    
    def add_voice_attachment_to_message(self):
        """Add a voice attachment to the mock message."""
        if self.message and self.attachment:
            self.message.attachments = [self.attachment]
        return self
    
    def set_bot_guilds(self, count: int = 2):
        """Set up multiple guilds for the bot."""
        if self.bot:
            self.bot.guilds = [MagicMock(spec=discord.Guild) for _ in range(count)]
            for i, guild in enumerate(self.bot.guilds):
                guild.id = 1000000000 + i
                guild.name = f"Test Server {i+1}"
                guild.member_count = 100 * (i + 1)
        return self
    
    def configure_interaction_for_command(self, command_name: str):
        """Configure interaction for specific command testing."""
        if self.interaction:
            self.interaction.command = MagicMock()
            self.interaction.command.name = command_name
        return self


@pytest.fixture
def mock_bot_context():
    """Factory fixture for creating mock bot contexts."""
    def _create_context():
        return MockBotContext().setup_basic_mocks()
    
    return _create_context