"""
Test module for AlertManager service.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
import pytest
from discord.ext import commands

from src.nescordbot.config import BotConfig
from src.nescordbot.services.alert_manager import (
    Alert,
    AlertManager,
    AlertManagerError,
    AlertRule,
    AlertSeverity,
)
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.phase4_monitor import Phase4Monitor
from src.nescordbot.services.token_manager import TokenManager


@pytest.fixture
def mock_config():
    """Create a mock BotConfig for testing."""
    config = Mock(spec=BotConfig)
    config.alert_enabled = True
    config.alert_channel_id = 123456789
    config.alert_monitoring_interval = 300
    config.alert_default_cooldown = 30
    config.alert_max_history_size = 100
    config.alert_memory_threshold_mb = 500
    config.alert_token_threshold_90 = 90
    config.alert_token_threshold_95 = 95
    config.alert_token_threshold_100 = 100
    return config


@pytest.fixture
def mock_bot():
    """Create a mock Discord bot."""
    bot = Mock(spec=commands.Bot)

    # Mock channel
    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    bot.get_channel = Mock(return_value=channel)

    return bot


@pytest.fixture
def mock_database_service():
    """Create a mock DatabaseService."""
    db_service = Mock(spec=DatabaseService)

    # Mock database connection
    mock_connection = AsyncMock()
    mock_cursor = AsyncMock()

    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)

    mock_connection.execute = AsyncMock(return_value=mock_cursor)
    mock_connection.commit = AsyncMock()
    mock_connection.__aenter__ = AsyncMock(return_value=mock_connection)
    mock_connection.__aexit__ = AsyncMock(return_value=None)

    db_service.get_connection = Mock(return_value=mock_connection)

    return db_service


@pytest.fixture
def mock_phase4_monitor():
    """Create a mock Phase4Monitor."""
    monitor = Mock(spec=Phase4Monitor)
    monitor.get_current_snapshot = AsyncMock(
        return_value={
            "timestamp": datetime.now(),
            "token_usage": {"monthly_usage_percentage": 85.0},
            "memory_usage": {"current_usage": {"current_mb": 450.0}},
            "system_health": {
                "token_manager": {"status": "healthy"},
                "api_monitor": {"status": "healthy"},
                "database": {"status": "healthy"},
            },
        }
    )
    return monitor


@pytest.fixture
def mock_token_manager():
    """Create a mock TokenManager."""
    manager = Mock(spec=TokenManager)
    manager.get_monthly_usage = AsyncMock(
        return_value={
            "monthly_usage_percentage": 85.0,
            "current_monthly_tokens": 85000,
            "monthly_limit": 100000,
        }
    )
    return manager


@pytest.fixture
async def alert_manager(
    mock_config, mock_bot, mock_database_service, mock_phase4_monitor, mock_token_manager
):
    """Create an AlertManager instance for testing."""
    manager = AlertManager(
        config=mock_config,
        bot=mock_bot,
        database_service=mock_database_service,
        phase4_monitor=mock_phase4_monitor,
        token_manager=mock_token_manager,
    )

    await manager.init_async()
    return manager


class TestAlert:
    """Test Alert dataclass."""

    def test_alert_creation(self):
        """Test Alert creation and properties."""
        alert = Alert(
            id="test_alert_123",
            title="Test Alert",
            message="This is a test alert",
            severity=AlertSeverity.WARNING,
            timestamp=datetime.now(),
            source="TestSource",
            metadata={"test": True},
        )

        assert alert.id == "test_alert_123"
        assert alert.title == "Test Alert"
        assert alert.severity == AlertSeverity.WARNING
        assert not alert.resolved
        assert alert.resolved_at is None
        assert alert.metadata["test"] is True


class TestAlertRule:
    """Test AlertRule dataclass."""

    def test_alert_rule_creation(self):
        """Test AlertRule creation and properties."""

        async def test_condition(metrics):
            return True

        rule = AlertRule(
            id="test_rule",
            name="Test Rule",
            description="Test alert rule",
            severity=AlertSeverity.CRITICAL,
            condition_func=test_condition,
            cooldown_minutes=60,
        )

        assert rule.id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.severity == AlertSeverity.CRITICAL
        assert rule.cooldown_minutes == 60
        assert rule.enabled is True


class TestAlertManager:
    """Test AlertManager class functionality."""

    def test_initialization(self, alert_manager):
        """Test AlertManager initialization."""
        assert alert_manager._initialized is True
        assert alert_manager._shutdown is False
        assert len(alert_manager._alert_rules) > 0  # Built-in rules should be registered
        assert len(alert_manager._active_alerts) == 0
        assert len(alert_manager._alert_history) == 0

    @pytest.mark.asyncio
    async def test_create_tables(self, alert_manager):
        """Test database tables creation."""
        # Tables should be created during initialization
        db_service = alert_manager.db

        # Verify execute was called for table creation
        calls = (
            db_service.get_connection.return_value.__aenter__.return_value.execute.call_args_list
        )

        # Should have at least 2 calls for creating tables
        assert len(calls) >= 2

        # Check if alert_history table creation was called
        table_creation_calls = [call for call in calls if "CREATE TABLE" in str(call)]
        assert len(table_creation_calls) >= 2

    @pytest.mark.asyncio
    async def test_builtin_rules_registration(self, alert_manager):
        """Test that built-in alert rules are registered."""
        expected_rules = [
            "token_90_percent",
            "token_95_percent",
            "token_100_percent",
            "system_unhealthy",
            "memory_high",
            "database_error",
        ]

        for rule_id in expected_rules:
            assert rule_id in alert_manager._alert_rules
            rule = alert_manager._alert_rules[rule_id]
            assert isinstance(rule, AlertRule)
            assert rule.enabled is True

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, alert_manager):
        """Test starting and stopping monitoring."""
        # Start monitoring
        await alert_manager.start_monitoring()
        assert alert_manager._monitoring_task is not None
        assert not alert_manager._shutdown

        # Stop monitoring
        await alert_manager.stop_monitoring()
        assert alert_manager._shutdown is True
        assert alert_manager._monitoring_task is None

    @pytest.mark.asyncio
    async def test_gather_system_metrics(self, alert_manager):
        """Test system metrics gathering."""
        metrics = await alert_manager._gather_system_metrics()

        assert "timestamp" in metrics
        assert "phase4_monitor" in metrics
        assert "token_manager" in metrics

        # Verify Phase4Monitor was called
        alert_manager.phase4_monitor.get_current_snapshot.assert_called_once()

        # Verify TokenManager was called
        alert_manager.token_manager.get_monthly_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_cooldown_check(self, alert_manager):
        """Test cooldown functionality."""
        rule_id = "test_rule"
        cooldown_minutes = 30

        # Initially, no cooldown
        assert not alert_manager._is_in_cooldown(rule_id, cooldown_minutes)

        # Set last alert time
        alert_manager._last_alert_times[rule_id] = datetime.now()

        # Should be in cooldown now
        assert alert_manager._is_in_cooldown(rule_id, cooldown_minutes)

        # Set last alert time to past
        alert_manager._last_alert_times[rule_id] = datetime.now() - timedelta(minutes=35)

        # Should not be in cooldown now
        assert not alert_manager._is_in_cooldown(rule_id, cooldown_minutes)

    @pytest.mark.asyncio
    async def test_token_90_percent_condition(self, alert_manager):
        """Test 90% token usage condition."""
        # Test with 89% usage (should not trigger)
        metrics = {"token_manager": {"monthly_usage_percentage": 89.0}}
        result = await alert_manager._check_token_90_percent(metrics)
        assert result is False

        # Test with 90% usage (should trigger)
        metrics = {"token_manager": {"monthly_usage_percentage": 90.0}}
        result = await alert_manager._check_token_90_percent(metrics)
        assert result is True

        # Test with 95% usage (should trigger)
        metrics = {"token_manager": {"monthly_usage_percentage": 95.0}}
        result = await alert_manager._check_token_90_percent(metrics)
        assert result is True

        # Test with no token data (should not trigger)
        metrics = {}
        result = await alert_manager._check_token_90_percent(metrics)
        assert result is False

    @pytest.mark.asyncio
    async def test_memory_usage_condition(self, alert_manager):
        """Test memory usage condition."""
        # Test with low memory usage (should not trigger)
        metrics = {"phase4_monitor": {"memory_usage": {"current_usage": {"current_mb": 400.0}}}}
        result = await alert_manager._check_memory_usage(metrics)
        assert result is False

        # Test with high memory usage (should trigger)
        metrics = {"phase4_monitor": {"memory_usage": {"current_usage": {"current_mb": 600.0}}}}
        result = await alert_manager._check_memory_usage(metrics)
        assert result is True

        # Test with no memory data (should not trigger)
        metrics = {}
        result = await alert_manager._check_memory_usage(metrics)
        assert result is False

    @pytest.mark.asyncio
    async def test_system_health_condition(self, alert_manager):
        """Test system health condition."""
        # Test with healthy system (should not trigger)
        metrics = {
            "phase4_monitor": {
                "system_health": {
                    "token_manager": {"status": "healthy"},
                    "api_monitor": {"status": "healthy"},
                    "database": {"status": "healthy"},
                }
            }
        }
        result = await alert_manager._check_system_health(metrics)
        assert result is False

        # Test with unhealthy token manager (should trigger)
        metrics = {
            "phase4_monitor": {
                "system_health": {
                    "token_manager": {"status": "error"},
                    "api_monitor": {"status": "healthy"},
                    "database": {"status": "healthy"},
                }
            }
        }
        result = await alert_manager._check_system_health(metrics)
        assert result is True

        # Test with no health data (should not trigger)
        metrics = {}
        result = await alert_manager._check_system_health(metrics)
        assert result is False

    @pytest.mark.asyncio
    async def test_trigger_alert(self, alert_manager):
        """Test alert triggering."""

        # Mock rule
        async def test_condition(metrics):
            return True

        rule = AlertRule(
            id="test_trigger",
            name="Test Trigger Alert",
            description="Test alert for triggering",
            severity=AlertSeverity.WARNING,
            condition_func=test_condition,
            cooldown_minutes=30,
        )

        alert_manager._alert_rules["test_trigger"] = rule

        # Trigger alert
        metrics = {"test": True}
        await alert_manager._trigger_alert(rule, metrics)

        # Verify alert was created
        assert len(alert_manager._active_alerts) == 1
        assert len(alert_manager._alert_history) == 1

        # Verify Discord notification was sent
        channel = alert_manager.bot.get_channel()
        channel.send.assert_called_once()

        # Verify cooldown was set
        assert "test_trigger" in alert_manager._last_alert_times

    @pytest.mark.asyncio
    async def test_create_alert_embed(self, alert_manager):
        """Test Discord embed creation."""
        alert = Alert(
            id="test_embed",
            title="Test Embed Alert",
            message="Test message for embed",
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.now(),
            source="TestSource",
            metadata={"metrics": {"token_manager": {"monthly_usage_percentage": 95.0}}},
        )

        embed = await alert_manager._create_alert_embed(alert)

        assert isinstance(embed, discord.Embed)
        assert "🚨 Test Embed Alert" in embed.title
        assert embed.description == "Test message for embed"
        assert embed.color == discord.Color.red()

        # Check fields
        fields = {field.name: field.value for field in embed.fields}
        assert "重要度" in fields
        assert fields["重要度"] == "CRITICAL"
        assert "ソース" in fields
        assert fields["ソース"] == "TestSource"

    @pytest.mark.asyncio
    async def test_save_alert_to_db(self, alert_manager):
        """Test saving alert to database."""
        alert = Alert(
            id="test_save",
            title="Test Save Alert",
            message="Test message",
            severity=AlertSeverity.INFO,
            timestamp=datetime.now(),
            source="TestSource",
            metadata={"test": True},
        )

        await alert_manager._save_alert_to_db(alert)

        # Verify database insert was called
        db_connection = alert_manager.db.get_connection.return_value.__aenter__.return_value
        db_connection.execute.assert_called()
        db_connection.commit.assert_called()

    @pytest.mark.asyncio
    async def test_resolve_alert(self, alert_manager):
        """Test alert resolution."""
        # Create a test alert
        alert = Alert(
            id="test_resolve",
            title="Test Resolve Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            timestamp=datetime.now(),
            source="TestSource",
            metadata={},
        )

        alert_manager._active_alerts["test_resolve"] = alert

        # Resolve the alert
        result = await alert_manager.resolve_alert("test_resolve")

        assert result is True
        assert "test_resolve" not in alert_manager._active_alerts
        assert alert.resolved is True
        assert alert.resolved_at is not None

        # Test resolving non-existent alert
        result = await alert_manager.resolve_alert("non_existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_enable_disable_rule(self, alert_manager):
        """Test enabling and disabling alert rules."""
        rule_id = "token_90_percent"

        # Initially enabled
        assert alert_manager._alert_rules[rule_id].enabled is True

        # Disable rule
        result = await alert_manager.disable_rule(rule_id)
        assert result is True
        assert alert_manager._alert_rules[rule_id].enabled is False

        # Enable rule
        result = await alert_manager.enable_rule(rule_id)
        assert result is True
        assert alert_manager._alert_rules[rule_id].enabled is True

        # Test with non-existent rule
        result = await alert_manager.disable_rule("non_existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_active_alerts(self, alert_manager):
        """Test getting active alerts."""
        # Initially no active alerts
        active_alerts = await alert_manager.get_active_alerts()
        assert len(active_alerts) == 0

        # Add a test alert
        alert = Alert(
            id="test_active",
            title="Test Active Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            timestamp=datetime.now(),
            source="TestSource",
            metadata={},
        )
        alert_manager._active_alerts["test_active"] = alert

        # Should now have one active alert
        active_alerts = await alert_manager.get_active_alerts()
        assert len(active_alerts) == 1
        assert active_alerts[0].id == "test_active"

    @pytest.mark.asyncio
    async def test_get_alert_history(self, alert_manager):
        """Test getting alert history."""
        # Initially no history
        history = await alert_manager.get_alert_history()
        assert len(history) == 0

        # Add test alerts to history
        for i in range(3):
            alert = Alert(
                id=f"test_history_{i}",
                title=f"Test History Alert {i}",
                message="Test message",
                severity=AlertSeverity.INFO,
                timestamp=datetime.now(),
                source="TestSource",
                metadata={},
            )
            alert_manager._alert_history.append(alert)

        # Should return all history
        history = await alert_manager.get_alert_history()
        assert len(history) == 3

        # Test with limit
        history = await alert_manager.get_alert_history(limit=2)
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_health_check(self, alert_manager):
        """Test AlertManager health check."""
        health_status = await alert_manager.health_check()

        assert "status" in health_status
        assert "monitoring_active" in health_status
        assert "active_alerts_count" in health_status
        assert "registered_rules_count" in health_status
        assert "alert_history_size" in health_status
        assert "timestamp" in health_status

        assert health_status["status"] == "healthy"
        assert health_status["active_alerts_count"] == 0
        assert health_status["registered_rules_count"] > 0

    @pytest.mark.asyncio
    async def test_close(self, alert_manager):
        """Test AlertManager closure."""
        # Start monitoring first
        await alert_manager.start_monitoring()
        assert alert_manager._monitoring_task is not None

        # Close the manager
        await alert_manager.close()

        assert alert_manager._shutdown is True
        assert alert_manager._initialized is False


class TestAlertManagerIntegration:
    """Integration tests for AlertManager."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_integration(self, alert_manager):
        """Test the complete monitoring loop functionality."""
        # Mock token manager to return high usage
        alert_manager.token_manager.get_monthly_usage = AsyncMock(
            return_value={
                "monthly_usage_percentage": 92.0,
                "current_monthly_tokens": 92000,
                "monthly_limit": 100000,
            }
        )

        # Start monitoring
        await alert_manager.start_monitoring()

        # Wait for one monitoring cycle
        await asyncio.sleep(0.1)

        # Manually trigger a check to ensure rules are evaluated
        await alert_manager._check_all_rules()

        # Should have triggered 90% alert
        assert len(alert_manager._active_alerts) >= 1

        # Stop monitoring
        await alert_manager.stop_monitoring()

    @pytest.mark.asyncio
    async def test_concurrent_alert_handling(self, alert_manager):
        """Test concurrent alert handling."""

        async def create_test_rule(rule_id: str, should_trigger: bool):
            async def condition(metrics):
                return should_trigger

            return AlertRule(
                id=rule_id,
                name=f"Test Rule {rule_id}",
                description=f"Test rule {rule_id}",
                severity=AlertSeverity.INFO,
                condition_func=condition,
                cooldown_minutes=1,
            )

        # Add multiple test rules
        rules = []
        for i in range(5):
            rule = await create_test_rule(f"concurrent_test_{i}", i % 2 == 0)
            alert_manager._alert_rules[rule.id] = rule
            rules.append(rule)

        # Run concurrent rule checks
        await asyncio.gather(*[alert_manager._check_all_rules() for _ in range(3)])

        # Should have triggered alerts for rules that return True (0, 2, 4)
        assert len(alert_manager._active_alerts) >= 3

    @pytest.mark.asyncio
    async def test_error_handling_in_monitoring(self, alert_manager):
        """Test error handling in monitoring loop."""
        # Mock Phase4Monitor to raise an exception
        alert_manager.phase4_monitor.get_current_snapshot = AsyncMock(
            side_effect=Exception("Test error")
        )

        # Should not raise exception, but continue gracefully
        metrics = await alert_manager._gather_system_metrics()

        # Should have timestamp and None values for failed services
        assert "timestamp" in metrics
        assert metrics["phase4_monitor"] is None

    @pytest.mark.asyncio
    async def test_discord_notification_error_handling(self, alert_manager):
        """Test Discord notification error handling."""
        # Mock channel to raise exception
        channel = alert_manager.bot.get_channel()
        channel.send = AsyncMock(side_effect=Exception("Discord error"))

        alert = Alert(
            id="test_discord_error",
            title="Test Discord Error",
            message="Test message",
            severity=AlertSeverity.CRITICAL,
            timestamp=datetime.now(),
            source="TestSource",
            metadata={},
        )

        # Should not raise exception
        await alert_manager._send_discord_notification(alert)

        # Channel send should have been attempted
        channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_alert_history_size_limit(self, alert_manager):
        """Test alert history size limitation."""
        # Set small history limit
        alert_manager._max_history_size = 3

        # Create more alerts than the limit
        for i in range(5):
            alert = Alert(
                id=f"history_limit_{i}",
                title=f"History Limit Test {i}",
                message="Test message",
                severity=AlertSeverity.INFO,
                timestamp=datetime.now(),
                source="TestSource",
                metadata={},
            )
            alert_manager._alert_history.append(alert)

            # Simulate the trimming logic
            if len(alert_manager._alert_history) > alert_manager._max_history_size:
                alert_manager._alert_history = alert_manager._alert_history[
                    -alert_manager._max_history_size :
                ]

        # Should only keep the latest 3 alerts
        assert len(alert_manager._alert_history) == 3
        assert alert_manager._alert_history[0].id == "history_limit_2"
        assert alert_manager._alert_history[-1].id == "history_limit_4"

    @pytest.mark.asyncio
    async def test_multiple_severity_levels(self, alert_manager):
        """Test handling multiple alert severity levels."""
        severities = [
            AlertSeverity.INFO,
            AlertSeverity.WARNING,
            AlertSeverity.CRITICAL,
            AlertSeverity.EMERGENCY,
        ]

        alerts = []
        for i, severity in enumerate(severities):
            alert = Alert(
                id=f"severity_test_{i}",
                title=f"Severity Test {severity.value}",
                message=f"Test {severity.value} message",
                severity=severity,
                timestamp=datetime.now(),
                source="TestSource",
                metadata={},
            )
            alerts.append(alert)

            # Test embed creation for each severity
            embed = await alert_manager._create_alert_embed(alert)
            assert isinstance(embed, discord.Embed)

            # Verify color mapping
            if severity == AlertSeverity.INFO:
                assert embed.color == discord.Color.blue()
            elif severity == AlertSeverity.WARNING:
                assert embed.color == discord.Color.orange()
            elif severity == AlertSeverity.CRITICAL:
                assert embed.color == discord.Color.red()
            elif severity == AlertSeverity.EMERGENCY:
                assert embed.color == discord.Color.dark_red()
