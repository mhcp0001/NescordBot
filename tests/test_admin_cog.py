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

from nescordbot.cogs.admin import AdminCog, ConfirmationView


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
        interaction.user = MagicMock(spec=discord.Member)
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

        await admin_cog.dbstats.callback(admin_cog, mock_interaction)

        # Verify error message
        mock_interaction.followup.send.assert_called_once_with("❌ データベースが初期化されていません。")

    async def test_config_command(self, admin_cog, mock_interaction):
        """Test configuration display command."""
        await admin_cog.config.callback(admin_cog, mock_interaction)

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
        # Create proper directory structure: data_dir.parent/logs/bot.log
        test_data_dir = temp_log_file.parent / "data"
        test_data_dir.mkdir(exist_ok=True)
        logs_dir = temp_log_file.parent / "logs"
        logs_dir.mkdir(exist_ok=True)

        # Set bot data_dir correctly
        admin_cog.bot.data_dir = test_data_dir

        # Copy temp file to expected location
        log_file = logs_dir / "bot.log"
        log_file.write_text(temp_log_file.read_text())

        try:
            await admin_cog.logs.callback(admin_cog, mock_interaction, level=None, lines=3)

            # Verify interaction response
            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()

            # Check that embed was created with logs
            call_args = mock_interaction.followup.send.call_args
            kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else call_args[1]
            assert "embed" in kwargs
            embed = kwargs["embed"]
            assert embed.title.startswith("📋 最新のログ")

        finally:
            # Cleanup
            log_file.unlink(missing_ok=True)
            if logs_dir.exists() and not any(logs_dir.iterdir()):
                logs_dir.rmdir()
            if test_data_dir.exists() and not any(test_data_dir.iterdir()):
                test_data_dir.rmdir()

    async def test_logs_command_no_file(self, admin_cog, mock_interaction):
        """Test logs command when log file doesn't exist."""
        # Ensure log file doesn't exist
        admin_cog.bot.data_dir = Path("/nonexistent")

        await admin_cog.logs.callback(admin_cog, mock_interaction)

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
            await admin_cog.logs.callback(admin_cog, mock_interaction, level="ERROR", lines=10)

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
            await admin_cog.setconfig.callback(
                admin_cog, mock_interaction, "test_key", "test_value"
            )

        # Verify permission denied message
        mock_interaction.followup.send.assert_called_once_with(
            "❌ この操作を実行する権限がありません。", ephemeral=True
        )

    async def test_setconfig_command_authorized(self, admin_cog, mock_interaction):
        """Test setconfig command with proper permissions."""
        # Mock permission check to return True
        with patch.object(admin_cog, "_check_admin_permissions", return_value=True):
            await admin_cog.setconfig.callback(
                admin_cog, mock_interaction, "test_key", "test_value"
            )

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
            await admin_cog.cleardb.callback(admin_cog, mock_interaction)

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

        # Mock database returning admin roles (async mock)
        admin_cog.bot.database_service.get_json = AsyncMock(return_value=[555555555])

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

    @pytest.mark.asyncio
    async def test_confirmation_view_initialization(self):
        """Test ConfirmationView initialization."""
        view = ConfirmationView()
        assert view.confirmed is False
        assert view.timeout == 30.0
        assert len(view.children) == 2  # Confirm and Cancel buttons

    @pytest.mark.asyncio
    async def test_confirm_button(self):
        """Test confirm button functionality."""
        view = ConfirmationView()

        # Mock interaction
        interaction = AsyncMock()

        # Get the actual buttons from the view
        confirm_button = None
        cancel_button = None
        for child in view.children:
            if hasattr(child, "label"):
                if child.label == "確認":
                    confirm_button = child
                elif child.label == "キャンセル":
                    cancel_button = child

        assert confirm_button is not None
        assert cancel_button is not None

        # Call confirm method
        await view.confirm.callback(interaction)

        # Verify state
        assert view.confirmed is True
        assert confirm_button.disabled is True
        assert cancel_button.disabled is True

        # Verify interaction response
        interaction.response.edit_message.assert_called_once_with(view=view)

    @pytest.mark.asyncio
    async def test_cancel_button(self):
        """Test cancel button functionality."""
        view = ConfirmationView()

        # Mock interaction
        interaction = AsyncMock()

        # Get the actual buttons from the view
        confirm_button = None
        cancel_button = None
        for child in view.children:
            if hasattr(child, "label"):
                if child.label == "確認":
                    confirm_button = child
                elif child.label == "キャンセル":
                    cancel_button = child

        assert confirm_button is not None
        assert cancel_button is not None

        # Call cancel method
        await view.cancel_button.callback(interaction)

        # Verify state
        assert view.confirmed is False
        assert cancel_button.disabled is True
        assert confirm_button.disabled is True

        # Verify interaction response
        interaction.response.edit_message.assert_called_once_with(view=view)

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout handling."""
        view = ConfirmationView()

        # Get the actual buttons from the view
        confirm_button = None
        cancel_button = None
        for child in view.children:
            if hasattr(child, "label"):
                if child.label == "確認":
                    confirm_button = child
                elif child.label == "キャンセル":
                    cancel_button = child

        assert confirm_button is not None
        assert cancel_button is not None

        # Ensure buttons are initially enabled
        confirm_button.disabled = False
        cancel_button.disabled = False

        # Call timeout
        await view.on_timeout()

        # Verify state
        assert view.confirmed is False
        assert confirm_button.disabled is True
        assert cancel_button.disabled is True


class TestAdminCogStatsCommand:
    """Test cases for /stats command in AdminCog."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot with service container."""
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 123456789
        bot.guilds = []
        bot.data_dir = Path("data")

        # Mock service container
        bot.service_container = MagicMock()

        # Mock database service for admin role checks
        bot.database_service = AsyncMock()
        bot.database_service.get_json = AsyncMock(return_value=None)

        # Mock application_info for admin permission checks
        app_info = MagicMock()
        app_info.owner = MagicMock()
        app_info.owner.id = 999999999  # Different from test user
        bot.application_info = AsyncMock(return_value=app_info)

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
        interaction.user = MagicMock(spec=discord.Member)
        interaction.user.id = 987654321
        interaction.guild = MagicMock()
        interaction.user.guild_permissions = MagicMock()
        interaction.user.guild_permissions.administrator = False
        interaction.user.roles = []
        return interaction

    @pytest.mark.asyncio
    async def test_stats_command_success(self, admin_cog, mock_interaction):
        """Test /stats command successful execution."""
        # Mock admin permissions
        mock_interaction.user.guild_permissions.administrator = True

        # Mock Phase4Monitor service
        mock_phase4_monitor = AsyncMock()
        mock_dashboard_data = {
            "current": {
                "timestamp": "2025-09-03T10:00:00",
                "token_usage": {
                    "monthly_usage": {
                        "current_monthly_tokens": 5000,
                        "monthly_limit": 50000,
                        "monthly_usage_percentage": 10.0,
                    }
                },
                "memory_usage": {
                    "current_usage": {"current_mb": 150.0, "peak_mb": 200.0},
                    "should_trigger_gc": False,
                },
                "pkm_performance": {
                    "pkm_summary": {
                        "search_engine": {
                            "query_count": 25,
                            "avg_query_time": 0.250,
                            "avg_result_count": 8.5,
                        },
                        "knowledge_manager": {
                            "operation_count": 15,
                            "success_rate": 0.95,
                            "avg_processing_time": 0.800,
                        },
                    }
                },
                "system_health": {
                    "database": {"status": "healthy", "connection_test": True, "query_time": 0.005}
                },
            },
            "api_status": {"monitoring_active": True, "fallback_level": "normal"},
            "last_update": "2025-09-03T10:00:00",
        }
        mock_phase4_monitor.get_dashboard_data = AsyncMock(return_value=mock_dashboard_data)

        # Mock service container
        admin_cog.bot.service_container = MagicMock()
        admin_cog.bot.service_container.get_service.return_value = mock_phase4_monitor

        # Execute command
        await admin_cog.stats.callback(admin_cog, mock_interaction)

        # Verify Phase4Monitor was called
        mock_phase4_monitor.get_dashboard_data.assert_called_once()

        # Verify interaction responses
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

        # Verify embed was sent with view
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args.kwargs
        assert "view" in call_args.kwargs

        embed = call_args.kwargs["embed"]
        assert embed.title == "📊 システムメトリクス & パフォーマンス統計"

    @pytest.mark.asyncio
    async def test_stats_command_service_not_found(self, admin_cog, mock_interaction):
        """Test /stats command when Phase4Monitor service is not found."""
        from nescordbot.services import ServiceNotFoundError

        # Mock admin permissions
        mock_interaction.user.guild_permissions.administrator = True

        # Mock service container throwing ServiceNotFoundError
        admin_cog.bot.service_container = MagicMock()
        admin_cog.bot.service_container.get_service.side_effect = ServiceNotFoundError(type)

        # Execute command
        await admin_cog.stats.callback(admin_cog, mock_interaction)

        # Verify interaction responses
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

        # Verify error embed was sent
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args.kwargs

        embed = call_args.kwargs["embed"]
        assert embed.title == "❌ システムメトリクス"
        assert "Phase4Monitor サービスが利用できません" in embed.description

    @pytest.mark.asyncio
    async def test_stats_command_no_admin_permission(self, admin_cog, mock_interaction):
        """Test /stats command without admin permissions."""
        # Mock non-admin user
        mock_interaction.user.guild_permissions.administrator = False
        mock_interaction.user.roles = []

        # Execute command
        await admin_cog.stats.callback(admin_cog, mock_interaction)

        # Should return early due to permission check
        mock_interaction.response.send_message.assert_called_once()

        # Verify error message
        call_args = mock_interaction.response.send_message.call_args
        assert call_args.kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_stats_command_dashboard_error(self, admin_cog, mock_interaction):
        """Test /stats command when dashboard data collection fails."""
        # Mock admin permissions
        mock_interaction.user.guild_permissions.administrator = True

        # Mock Phase4Monitor service with error
        mock_phase4_monitor = AsyncMock()
        mock_phase4_monitor.get_dashboard_data = AsyncMock(side_effect=Exception("Test error"))

        # Mock service container
        admin_cog.bot.service_container = MagicMock()
        admin_cog.bot.service_container.get_service.return_value = mock_phase4_monitor

        # Execute command
        await admin_cog.stats.callback(admin_cog, mock_interaction)

        # Verify interaction responses
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

        # Verify error embed was sent
        call_args = mock_interaction.followup.send.call_args
        assert "embed" in call_args.kwargs

        embed = call_args.kwargs["embed"]
        assert embed.title == "❌ システムメトリクス"
        assert "統計情報の取得中にエラーが発生しました" in embed.description
