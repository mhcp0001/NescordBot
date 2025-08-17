"""
Test cases for AdminCog.

Tests administrative commands, permissions, and database interactions.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from src.cogs.admin import AdminCog, ConfirmationView


class TestAdminCog:
    """Test cases for AdminCog functionality."""

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

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock()
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 987654321
        interaction.guild = MagicMock()
        interaction.user.guild_permissions = MagicMock()
        interaction.user.guild_permissions.administrator = False
        interaction.user.roles = []
        return interaction

    @pytest.fixture
    def temp_log_file(self):
        """Create a temporary log file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            # Write sample log entries
            f.write("2024-01-01 10:00:00 | INFO     | bot | Bot started\n")
            f.write("2024-01-01 10:01:00 | WARNING  | cog | Test warning\n")
            f.write("2024-01-01 10:02:00 | ERROR    | database | Test error\n")
            f.write("2024-01-01 10:03:00 | DEBUG    | handler | Debug message\n")
            f.write("2024-01-01 10:04:00 | INFO     | bot | Bot ready\n")
            log_path = f.name

        yield Path(log_path)

        # Cleanup
        Path(log_path).unlink(missing_ok=True)

    async def test_dbstats_command(self, admin_cog, mock_interaction):
        """Test database statistics command."""
        # Call the callback directly, not the command decorator
        await admin_cog.dbstats.callback(admin_cog, mock_interaction)

        # Verify database service was called
        admin_cog.bot.database_service.get_stats.assert_called_once()

        # Verify interaction response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

        # Check that embed was created with stats
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args[1]
        embed = call_args[1]["embed"]
        assert embed.title == "📊 データベース統計"

    async def test_dbstats_command_not_initialized(self, admin_cog, mock_interaction):
        """Test database statistics when database is not initialized."""
        admin_cog.bot.database_service.is_initialized = False

        await admin_cog.dbstats(mock_interaction)

        # Verify error message
        mock_interaction.followup.send.assert_called_once_with("❌ データベースが初期化されていません。")

    async def test_config_command(self, admin_cog, mock_interaction):
        """Test configuration display command."""
        await admin_cog.config(mock_interaction)

        # Verify interaction response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

        # Check that embed was created with config
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args[1]
        embed = call_args[1]["embed"]
        assert embed.title == "⚙️ ボット設定"

    async def test_logs_command_with_file(self, admin_cog, mock_interaction, temp_log_file):
        """Test logs command with actual log file."""
        # Mock the log file path
        admin_cog.bot.data_dir = temp_log_file.parent
        logs_dir = temp_log_file.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Copy temp file to expected location
        log_file = logs_dir / "bot.log"
        log_file.write_text(temp_log_file.read_text())

        try:
            await admin_cog.logs(mock_interaction, level=None, lines=3)

            # Verify interaction response
            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()

            # Check that embed was created with logs
            call_args = mock_interaction.followup.send.call_args
            assert "embed" in call_args[1]
            embed = call_args[1]["embed"]
            assert embed.title.startswith("📋 最新のログ")

        finally:
            # Cleanup
            log_file.unlink(missing_ok=True)
            logs_dir.rmdir()

    async def test_logs_command_no_file(self, admin_cog, mock_interaction):
        """Test logs command when log file doesn't exist."""
        # Ensure log file doesn't exist
        admin_cog.bot.data_dir = Path("/nonexistent")

        await admin_cog.logs(mock_interaction)

        # Verify error message
        mock_interaction.followup.send.assert_called_once_with("❌ ログファイルが見つかりません。")

    async def test_logs_command_with_level_filter(self, admin_cog, mock_interaction, temp_log_file):
        """Test logs command with level filtering."""
        # Mock the log file path
        admin_cog.bot.data_dir = temp_log_file.parent
        logs_dir = temp_log_file.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Copy temp file to expected location
        log_file = logs_dir / "bot.log"
        log_file.write_text(temp_log_file.read_text())

        try:
            await admin_cog.logs(mock_interaction, level="ERROR", lines=10)

            # Verify interaction response
            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()

        finally:
            # Cleanup
            log_file.unlink(missing_ok=True)
            logs_dir.rmdir()

    async def test_setconfig_command_unauthorized(self, admin_cog, mock_interaction):
        """Test setconfig command without proper permissions."""
        # Mock permission check to return False
        with patch.object(admin_cog, "_check_admin_permissions", return_value=False):
            await admin_cog.setconfig(mock_interaction, "test_key", "test_value")

        # Verify permission denied message
        mock_interaction.followup.send.assert_called_once_with(
            "❌ この操作を実行する権限がありません。", ephemeral=True
        )

    async def test_setconfig_command_authorized(self, admin_cog, mock_interaction):
        """Test setconfig command with proper permissions."""
        # Mock permission check to return True
        with patch.object(admin_cog, "_check_admin_permissions", return_value=True):
            await admin_cog.setconfig(mock_interaction, "test_key", "test_value")

        # Verify database service was called
        admin_cog.bot.database_service.set.assert_called_once_with("config:test_key", "test_value")

        # Verify success message
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args[1]
        embed = call_args[1]["embed"]
        assert embed.title == "✅ 設定が更新されました"

    async def test_cleardb_command_unauthorized(self, admin_cog, mock_interaction):
        """Test cleardb command without proper permissions."""
        with patch.object(admin_cog, "_check_admin_permissions", return_value=False):
            await admin_cog.cleardb(mock_interaction)

        # Verify permission denied message
        mock_interaction.followup.send.assert_called_once_with(
            "❌ この操作を実行する権限がありません。", ephemeral=True
        )

    async def test_check_admin_permissions_owner(self, admin_cog, mock_interaction):
        """Test admin permission check for bot owner."""
        # Mock application info
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = mock_interaction.user.id

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is True

    async def test_check_admin_permissions_administrator(self, admin_cog, mock_interaction):
        """Test admin permission check for guild administrator."""
        # Mock application info (user is not owner)
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 999999999  # Different from user ID

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        # User has administrator permissions
        mock_interaction.user.guild_permissions.administrator = True

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is True

    async def test_check_admin_permissions_custom_role(self, admin_cog, mock_interaction):
        """Test admin permission check for custom admin role."""
        # Mock application info (user is not owner)
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 999999999  # Different from user ID

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        # User doesn't have administrator permissions
        mock_interaction.user.guild_permissions.administrator = False

        # Mock user has admin role
        admin_role = MagicMock()
        admin_role.id = 555555555
        mock_interaction.user.roles = [admin_role]

        # Mock database returning admin roles
        admin_cog.bot.database_service.get_json.return_value = [555555555]

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is True

    async def test_check_admin_permissions_denied(self, admin_cog, mock_interaction):
        """Test admin permission check when access is denied."""
        # Mock application info (user is not owner)
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 999999999  # Different from user ID

        admin_cog.bot.application_info = AsyncMock(return_value=app_info)

        # User doesn't have administrator permissions
        mock_interaction.user.guild_permissions.administrator = False

        # User has no special roles
        mock_interaction.user.roles = []

        # No admin roles in database
        admin_cog.bot.database_service.get_json.return_value = None

        result = await admin_cog._check_admin_permissions(mock_interaction)
        assert result is False


class TestConfirmationView:
    """Test cases for ConfirmationView."""

    def test_confirmation_view_initialization(self):
        """Test ConfirmationView initialization."""
        view = ConfirmationView()
        assert view.confirmed is False
        assert view.timeout == 30.0
        assert len(view.children) == 2  # Confirm and Cancel buttons

    async def test_confirm_button(self):
        """Test confirm button functionality."""
        view = ConfirmationView()

        # Mock interaction
        interaction = AsyncMock()

        # Mock button
        button = MagicMock()
        button.disabled = False
        view.cancel_button = MagicMock()
        view.cancel_button.disabled = False

        # Call confirm method
        await view.confirm(interaction, button)

        # Verify state
        assert view.confirmed is True
        assert button.disabled is True
        assert view.cancel_button.disabled is True

        # Verify interaction response
        interaction.response.edit_message.assert_called_once_with(view=view)

    async def test_cancel_button(self):
        """Test cancel button functionality."""
        view = ConfirmationView()

        # Mock interaction
        interaction = AsyncMock()

        # Mock buttons
        button = MagicMock()
        button.disabled = False
        view.confirm = MagicMock()
        view.confirm.disabled = False

        # Call cancel method
        await view.cancel_button(interaction, button)

        # Verify state
        assert view.confirmed is False
        assert button.disabled is True
        assert view.confirm.disabled is True

        # Verify interaction response
        interaction.response.edit_message.assert_called_once_with(view=view)

    async def test_timeout_handling(self):
        """Test timeout handling."""
        view = ConfirmationView()

        # Mock children
        child1 = MagicMock()
        child1.disabled = False
        child2 = MagicMock()
        child2.disabled = False
        view.children = [child1, child2]

        # Call timeout
        await view.on_timeout()

        # Verify state
        assert view.confirmed is False
        assert child1.disabled is True
        assert child2.disabled is True
