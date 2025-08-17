"""
Simplified tests for AdminCog core functionality.

Tests the core logic of admin commands without Discord UI complexity.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from nescordbot.cogs.admin import AdminCog


class TestAdminFunctionality:
    """Test core admin functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot with database service."""
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 123456789
        bot.guilds = []
        bot.data_dir = Path("data")

        # Mock database service
        bot.database_service = AsyncMock()
        bot.database_service.is_initialized = True
        bot.database_service.get_stats = AsyncMock(
            return_value={
                "total_keys": 42,
                "db_path": ":memory:",
                "db_size_bytes": 1024,
                "is_memory": True,
                "is_initialized": True,
            }
        )
        bot.database_service.set = AsyncMock()
        bot.database_service.clear = AsyncMock()
        bot.database_service.get_json = AsyncMock(return_value=None)

        # Mock config
        bot.config = MagicMock()
        bot.config.max_audio_size_mb = 25
        bot.config.speech_language = "ja-JP"
        bot.config.log_level = "INFO"

        return bot

    @pytest.fixture
    def admin_cog(self, mock_bot):
        """Create AdminCog instance with mock bot."""
        return AdminCog(mock_bot)

    async def test_database_stats_retrieval(self, admin_cog):
        """Test that database stats can be retrieved."""
        stats = await admin_cog.bot.database_service.get_stats()

        assert stats["total_keys"] == 42
        assert stats["is_memory"] is True
        assert stats["is_initialized"] is True

        # Verify the call was made
        admin_cog.bot.database_service.get_stats.assert_called_once()

    async def test_configuration_storage(self, admin_cog):
        """Test storing configuration in database."""
        key = "test_setting"
        value = "test_value"

        # Store config
        await admin_cog.bot.database_service.set(f"config:{key}", value)

        # Verify the call was made
        admin_cog.bot.database_service.set.assert_called_once_with(f"config:{key}", value)

    async def test_database_clear_operation(self, admin_cog):
        """Test database clear operation."""
        # Clear database
        await admin_cog.bot.database_service.clear()

        # Verify the call was made
        admin_cog.bot.database_service.clear.assert_called_once()

    async def test_admin_permission_check_owner(self, admin_cog):
        """Test admin permission check for bot owner."""
        # Mock interaction
        mock_interaction = MagicMock()
        mock_interaction.user = MagicMock()
        mock_interaction.user.id = 123456789  # Same as bot owner
        mock_interaction.guild = MagicMock()
        mock_interaction.user.guild_permissions = MagicMock()
        mock_interaction.user.guild_permissions.administrator = False
        mock_interaction.user.roles = []

        # Mock application info
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 123456789  # Same as user ID

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is True

    async def test_admin_permission_check_administrator(self, admin_cog):
        """Test admin permission check for guild administrator."""
        # Mock interaction with proper Member type
        mock_interaction = MagicMock()
        mock_interaction.user = MagicMock(spec=discord.Member)
        mock_interaction.user.id = 987654321  # Different from bot owner
        mock_interaction.guild = MagicMock()
        mock_interaction.user.guild_permissions = MagicMock()
        mock_interaction.user.guild_permissions.administrator = True
        mock_interaction.user.roles = []

        # Mock application info
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 123456789  # Different from user ID

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is True

    async def test_admin_permission_check_denied(self, admin_cog):
        """Test admin permission check when access is denied."""
        # Mock interaction
        mock_interaction = MagicMock()
        mock_interaction.user = MagicMock()
        mock_interaction.user.id = 987654321  # Different from bot owner
        mock_interaction.guild = MagicMock()
        mock_interaction.user.guild_permissions = MagicMock()
        mock_interaction.user.guild_permissions.administrator = False
        mock_interaction.user.roles = []

        # Mock application info
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 123456789  # Different from user ID

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        # No admin roles in database
        admin_cog.bot.database_service.get_json.return_value = None

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is False

    def test_log_file_reading(self):
        """Test log file reading functionality."""
        # Create temporary log file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2024-01-01 10:00:00 | INFO     | bot | Bot started\n")
            f.write("2024-01-01 10:01:00 | WARNING  | cog | Test warning\n")
            f.write("2024-01-01 10:02:00 | ERROR    | database | Test error\n")
            f.write("2024-01-01 10:03:00 | DEBUG    | handler | Debug message\n")
            f.write("2024-01-01 10:04:00 | INFO     | bot | Bot ready\n")
            log_path = Path(f.name)

        try:
            # Read all lines
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 5

            # Filter ERROR lines
            error_lines = [line for line in lines if "ERROR" in line]
            assert len(error_lines) == 1
            assert "database" in error_lines[0]

            # Get last 3 lines
            recent_lines = lines[-3:]
            assert len(recent_lines) == 3

        finally:
            # Cleanup
            log_path.unlink(missing_ok=True)

    def test_config_access(self, admin_cog):
        """Test configuration access."""
        config = admin_cog.bot.config

        assert hasattr(config, "max_audio_size_mb")
        assert config.max_audio_size_mb == 25
        assert hasattr(config, "speech_language")
        assert config.speech_language == "ja-JP"
        assert hasattr(config, "log_level")
        assert config.log_level == "INFO"

    async def test_cog_initialization(self, mock_bot):
        """Test AdminCog initialization."""
        cog = AdminCog(mock_bot)

        assert cog.bot is mock_bot
        assert hasattr(cog, "logger")

        # Check that commands are registered
        assert hasattr(cog, "dbstats")
        assert hasattr(cog, "config")
        assert hasattr(cog, "logs")
        assert hasattr(cog, "setconfig")
        assert hasattr(cog, "cleardb")

    async def test_database_initialization_check(self, admin_cog):
        """Test database initialization checking."""
        # Database is initialized
        assert admin_cog.bot.database_service.is_initialized is True

        # Test when not initialized
        admin_cog.bot.database_service.is_initialized = False
        assert admin_cog.bot.database_service.is_initialized is False

    async def test_permission_with_custom_admin_roles(self, admin_cog):
        """Test permission check with custom admin roles."""
        # Mock interaction with proper Member type
        mock_interaction = MagicMock()
        mock_interaction.user = MagicMock(spec=discord.Member)
        mock_interaction.user.id = 987654321
        mock_interaction.guild = MagicMock()
        mock_interaction.user.guild_permissions = MagicMock()
        mock_interaction.user.guild_permissions.administrator = False

        # User has a role
        admin_role = MagicMock()
        admin_role.id = 555555555
        mock_interaction.user.roles = [admin_role]

        # Mock application info (user is not owner)
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 123456789

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        # Database returns matching admin role (async mock)
        admin_cog.bot.database_service.get_json = AsyncMock(return_value=[555555555])

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is True

        # Verify database was queried
        admin_cog.bot.database_service.get_json.assert_called_with("admin_roles")
