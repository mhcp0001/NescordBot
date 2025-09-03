"""
AlertManager service for system monitoring and notification.

This service monitors system health and sends alerts to Discord administrators
when critical conditions are detected.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

import discord
from discord.ext import commands

from ..config import BotConfig
from ..logger import get_logger
from .database import DatabaseService
from .phase4_monitor import Phase4Monitor
from .token_manager import TokenManager


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class Alert:
    """Represents an alert."""

    id: str
    title: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    source: str
    metadata: Dict[str, Any]
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class AlertRule:
    """Defines an alert rule with condition and action."""

    id: str
    name: str
    description: str
    severity: AlertSeverity
    condition_func: Callable[[Dict[str, Any]], Awaitable[bool]]
    cooldown_minutes: int = 30
    enabled: bool = True


class AlertManagerError(Exception):
    """Base exception for AlertManager."""

    pass


class AlertManager:
    """
    AlertManager monitors system health and sends notifications.

    Features:
    - Monitors Phase4Monitor and TokenManager metrics
    - Sends Discord notifications to administrators
    - Manages alert history and rate limiting
    - Configurable alert rules and thresholds
    """

    def __init__(
        self,
        config: BotConfig,
        bot: commands.Bot,
        database_service: DatabaseService,
        phase4_monitor: Optional[Phase4Monitor] = None,
        token_manager: Optional[TokenManager] = None,
    ):
        """Initialize AlertManager."""
        self.config = config
        self.bot = bot
        self.db = database_service
        self.phase4_monitor = phase4_monitor
        self.token_manager = token_manager

        self._logger = get_logger("alert_manager")
        self._initialized = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._shutdown = False

        # Alert management
        self._alert_rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: List[Alert] = []
        self._last_alert_times: Dict[str, datetime] = {}

        # Configuration
        self._monitoring_interval = getattr(config, "alert_monitoring_interval", 300)  # 5 minutes
        self._max_history_size = getattr(config, "alert_max_history_size", 100)
        self._default_cooldown = getattr(config, "alert_default_cooldown", 30)  # minutes

    async def init_async(self) -> None:
        """Initialize the AlertManager asynchronously."""
        if self._initialized:
            return

        self._logger.info("Initializing AlertManager...")

        try:
            # Create database tables
            await self._create_tables()

            # Register built-in alert rules
            await self._register_builtin_rules()

            # Load alert history
            await self._load_alert_history()

            self._initialized = True
            self._logger.info("AlertManager initialized successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize AlertManager: {e}")
            raise AlertManagerError(f"AlertManager initialization failed: {e}")

    async def _create_tables(self) -> None:
        """Create necessary database tables."""
        async with self.db.get_connection() as conn:
            # Alert history table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_history (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata TEXT,
                    timestamp DATETIME NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at DATETIME
                )
            """
            )

            # Alert settings table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_settings (
                    rule_id TEXT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT TRUE,
                    cooldown_minutes INTEGER DEFAULT 30,
                    threshold_data TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            await conn.commit()

    async def _register_builtin_rules(self) -> None:
        """Register built-in alert rules."""

        # Token usage alerts
        await self._register_rule(
            AlertRule(
                id="token_90_percent",
                name="Token Usage 90%",
                description="Monthly token usage reached 90%",
                severity=AlertSeverity.WARNING,
                condition_func=self._check_token_90_percent,
                cooldown_minutes=60,
            )
        )

        await self._register_rule(
            AlertRule(
                id="token_95_percent",
                name="Token Usage 95%",
                description="Monthly token usage reached 95%",
                severity=AlertSeverity.CRITICAL,
                condition_func=self._check_token_95_percent,
                cooldown_minutes=30,
            )
        )

        await self._register_rule(
            AlertRule(
                id="token_100_percent",
                name="Token Usage 100%",
                description="Monthly token usage reached 100%",
                severity=AlertSeverity.EMERGENCY,
                condition_func=self._check_token_100_percent,
                cooldown_minutes=15,
            )
        )

        # System health alerts
        await self._register_rule(
            AlertRule(
                id="system_unhealthy",
                name="System Health Critical",
                description="System health check failed",
                severity=AlertSeverity.CRITICAL,
                condition_func=self._check_system_health,
                cooldown_minutes=30,
            )
        )

        # Memory usage alerts
        await self._register_rule(
            AlertRule(
                id="memory_high",
                name="High Memory Usage",
                description="Memory usage exceeded threshold",
                severity=AlertSeverity.WARNING,
                condition_func=self._check_memory_usage,
                cooldown_minutes=60,
            )
        )

        # Database health alerts
        await self._register_rule(
            AlertRule(
                id="database_error",
                name="Database Connection Error",
                description="Database health check failed",
                severity=AlertSeverity.CRITICAL,
                condition_func=self._check_database_health,
                cooldown_minutes=30,
            )
        )

    async def _register_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        self._alert_rules[rule.id] = rule
        self._logger.debug(f"Registered alert rule: {rule.name}")

    async def start_monitoring(self) -> None:
        """Start the alert monitoring loop."""
        if self._monitoring_task is not None:
            return

        self._shutdown = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        self._logger.info("Alert monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop the alert monitoring loop."""
        self._shutdown = True

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        self._logger.info("Alert monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while not self._shutdown:
            try:
                await self._check_all_rules()
                await asyncio.sleep(self._monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _check_all_rules(self) -> None:
        """Check all registered alert rules."""
        if not self._initialized:
            return

        # Gather system metrics
        metrics = await self._gather_system_metrics()

        # Check each rule
        for rule in self._alert_rules.values():
            if not rule.enabled:
                continue

            try:
                # Check cooldown
                if self._is_in_cooldown(rule.id, rule.cooldown_minutes):
                    continue

                # Check condition
                if await rule.condition_func(metrics):
                    await self._trigger_alert(rule, metrics)

            except Exception as e:
                self._logger.error(f"Error checking rule {rule.name}: {e}")

    async def _gather_system_metrics(self) -> Dict[str, Any]:
        """Gather current system metrics."""
        metrics: Dict[str, Any] = {
            "timestamp": datetime.now(),
            "phase4_monitor": None,
            "token_manager": None,
        }

        try:
            if self.phase4_monitor:
                phase4_metrics = await self.phase4_monitor.get_current_snapshot()
                if isinstance(phase4_metrics, dict):
                    metrics["phase4_monitor"] = phase4_metrics
        except Exception as e:
            self._logger.warning(f"Failed to get Phase4Monitor metrics: {e}")

        try:
            if self.token_manager:
                token_metrics = await self.token_manager.get_monthly_usage()
                if isinstance(token_metrics, dict):
                    metrics["token_manager"] = token_metrics
        except Exception as e:
            self._logger.warning(f"Failed to get TokenManager metrics: {e}")

        return metrics

    def _is_in_cooldown(self, rule_id: str, cooldown_minutes: int) -> bool:
        """Check if alert is in cooldown period."""
        if rule_id not in self._last_alert_times:
            return False

        time_since_last = datetime.now() - self._last_alert_times[rule_id]
        return time_since_last < timedelta(minutes=cooldown_minutes)

    async def _trigger_alert(self, rule: AlertRule, metrics: Dict[str, Any]) -> None:
        """Trigger an alert."""
        alert_id = f"{rule.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        alert = Alert(
            id=alert_id,
            title=rule.name,
            message=rule.description,
            severity=rule.severity,
            timestamp=datetime.now(),
            source="AlertManager",
            metadata={"rule_id": rule.id, "metrics": metrics},
        )

        # Add to active alerts
        self._active_alerts[alert_id] = alert

        # Send notification
        await self._send_discord_notification(alert)

        # Record alert time
        self._last_alert_times[rule.id] = datetime.now()

        # Save to database
        await self._save_alert_to_db(alert)

        # Add to history
        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_history_size:
            self._alert_history = self._alert_history[-self._max_history_size :]

        self._logger.info(f"Alert triggered: {alert.title} ({alert.severity.value})")

    async def _send_discord_notification(self, alert: Alert) -> None:
        """Send Discord notification for alert."""
        try:
            # Get alert channel
            channel_id = getattr(self.config, "alert_channel_id", None)
            if not channel_id:
                self._logger.warning("Alert channel not configured")
                return

            channel = self.bot.get_channel(channel_id)
            if not channel:
                self._logger.error(f"Alert channel not found: {channel_id}")
                return

            # Type check: ensure channel supports sending messages
            if not hasattr(channel, "send"):
                self._logger.error(f"Channel does not support sending messages: {channel_id}")
                return

            # Create embed
            embed = await self._create_alert_embed(alert)

            # Send message - Type cast to ensure it's a text channel that can send messages
            from discord import TextChannel

            if isinstance(channel, TextChannel):
                await channel.send(embed=embed)
            else:
                self._logger.error(f"Channel is not a text channel: {channel_id}")

            self._logger.debug(f"Discord notification sent for alert: {alert.id}")

        except Exception as e:
            self._logger.error(f"Failed to send Discord notification: {e}")

    async def _create_alert_embed(self, alert: Alert) -> discord.Embed:
        """Create Discord embed for alert."""
        color_map = {
            AlertSeverity.INFO: discord.Color.blue(),
            AlertSeverity.WARNING: discord.Color.orange(),
            AlertSeverity.CRITICAL: discord.Color.red(),
            AlertSeverity.EMERGENCY: discord.Color.dark_red(),
        }

        emoji_map = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.EMERGENCY: "🆘",
        }

        embed = discord.Embed(
            title=f"{emoji_map[alert.severity]} {alert.title}",
            description=alert.message,
            color=color_map[alert.severity],
            timestamp=alert.timestamp,
        )

        embed.add_field(name="重要度", value=alert.severity.value.upper(), inline=True)
        embed.add_field(name="ソース", value=alert.source, inline=True)
        embed.add_field(name="時刻", value=alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"), inline=True)

        # Add metrics info if available
        if "metrics" in alert.metadata:
            metrics = alert.metadata["metrics"]
            if "token_manager" in metrics and metrics["token_manager"]:
                token_data = metrics["token_manager"]
                if "monthly_usage_percentage" in token_data:
                    embed.add_field(
                        name="月間トークン使用率",
                        value=f"{token_data['monthly_usage_percentage']:.1f}%",
                        inline=True,
                    )

        embed.set_footer(text=f"Alert ID: {alert.id}")

        return embed

    async def _save_alert_to_db(self, alert: Alert) -> None:
        """Save alert to database."""
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO alert_history
                    (id, title, message, severity, source, metadata,
                     timestamp, resolved, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        alert.id,
                        alert.title,
                        alert.message,
                        alert.severity.value,
                        alert.source,
                        str(alert.metadata),
                        alert.timestamp,
                        alert.resolved,
                        alert.resolved_at,
                    ),
                )
                await conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to save alert to database: {e}")

    async def _load_alert_history(self) -> None:
        """Load alert history from database."""
        try:
            async with self.db.get_connection() as conn:
                async with conn.execute(
                    """
                    SELECT id, title, message, severity, source, metadata,
                           timestamp, resolved, resolved_at
                    FROM alert_history
                    ORDER BY timestamp DESC
                    LIMIT ?
                """,
                    (self._max_history_size,),
                ) as cursor:
                    rows = await cursor.fetchall()

                self._alert_history = []
                for row in rows:
                    alert = Alert(
                        id=row[0],
                        title=row[1],
                        message=row[2],
                        severity=AlertSeverity(row[3]),
                        timestamp=datetime.fromisoformat(row[6]),
                        source=row[4],
                        metadata=eval(row[5]) if row[5] else {},
                        resolved=bool(row[7]),
                        resolved_at=datetime.fromisoformat(row[8]) if row[8] else None,
                    )
                    self._alert_history.append(alert)

        except Exception as e:
            self._logger.error(f"Failed to load alert history: {e}")

    # Alert condition functions
    async def _check_token_90_percent(self, metrics: Dict[str, Any]) -> bool:
        """Check if token usage is >= 90%."""
        token_data = metrics.get("token_manager")
        if not token_data:
            return False
        return bool(token_data.get("monthly_usage_percentage", 0) >= 90.0)

    async def _check_token_95_percent(self, metrics: Dict[str, Any]) -> bool:
        """Check if token usage is >= 95%."""
        token_data = metrics.get("token_manager")
        if not token_data:
            return False
        return bool(token_data.get("monthly_usage_percentage", 0) >= 95.0)

    async def _check_token_100_percent(self, metrics: Dict[str, Any]) -> bool:
        """Check if token usage is >= 100%."""
        token_data = metrics.get("token_manager")
        if not token_data:
            return False
        return bool(token_data.get("monthly_usage_percentage", 0) >= 100.0)

    async def _check_system_health(self, metrics: Dict[str, Any]) -> bool:
        """Check if system health is critical."""
        phase4_data = metrics.get("phase4_monitor")
        if not phase4_data:
            return False

        system_health = phase4_data.get("system_health", {})
        token_manager_health = system_health.get("token_manager", {})
        api_monitor_health = system_health.get("api_monitor", {})
        database_health = system_health.get("database", {})

        # Check if any critical service is unhealthy
        return bool(
            token_manager_health.get("status") != "healthy"
            or api_monitor_health.get("status") != "healthy"
            or database_health.get("status") != "healthy"
        )

    async def _check_memory_usage(self, metrics: Dict[str, Any]) -> bool:
        """Check if memory usage is high."""
        phase4_data = metrics.get("phase4_monitor")
        if not phase4_data:
            return False

        memory_usage = phase4_data.get("memory_usage", {})
        current_usage = memory_usage.get("current_usage", {})
        current_mb = current_usage.get("current_mb", 0)

        # Alert if memory usage > 500MB
        threshold = getattr(self.config, "alert_memory_threshold_mb", 500)
        return bool(current_mb > threshold)

    async def _check_database_health(self, metrics: Dict[str, Any]) -> bool:
        """Check if database health is critical."""
        phase4_data = metrics.get("phase4_monitor")
        if not phase4_data:
            return False

        system_health = phase4_data.get("system_health", {})
        database_health = system_health.get("database", {})

        return bool(database_health.get("status") != "healthy")

    # Public API
    async def get_active_alerts(self) -> List[Alert]:
        """Get currently active alerts."""
        return list(self._active_alerts.values())

    async def get_alert_history(self, limit: int = 50) -> List[Alert]:
        """Get alert history."""
        return self._alert_history[-limit:]

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert."""
        if alert_id not in self._active_alerts:
            return False

        alert = self._active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_at = datetime.now()

        # Update database
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    UPDATE alert_history
                    SET resolved = ?, resolved_at = ?
                    WHERE id = ?
                """,
                    (True, alert.resolved_at, alert_id),
                )
                await conn.commit()
        except Exception as e:
            self._logger.error(f"Failed to update alert resolution in database: {e}")

        # Remove from active alerts
        del self._active_alerts[alert_id]

        self._logger.info(f"Alert resolved: {alert_id}")
        return True

    async def enable_rule(self, rule_id: str) -> bool:
        """Enable an alert rule."""
        if rule_id not in self._alert_rules:
            return False

        self._alert_rules[rule_id].enabled = True
        await self._save_rule_settings(rule_id)
        return True

    async def disable_rule(self, rule_id: str) -> bool:
        """Disable an alert rule."""
        if rule_id not in self._alert_rules:
            return False

        self._alert_rules[rule_id].enabled = False
        await self._save_rule_settings(rule_id)
        return True

    async def _save_rule_settings(self, rule_id: str) -> None:
        """Save rule settings to database."""
        if rule_id not in self._alert_rules:
            return

        rule = self._alert_rules[rule_id]
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO alert_settings
                    (rule_id, enabled, cooldown_minutes, updated_at)
                    VALUES (?, ?, ?, ?)
                """,
                    (rule_id, rule.enabled, rule.cooldown_minutes, datetime.now()),
                )
                await conn.commit()
        except Exception as e:
            self._logger.error(f"Failed to save rule settings: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check."""
        return {
            "status": "healthy" if self._initialized else "initializing",
            "monitoring_active": self._monitoring_task is not None and not self._shutdown,
            "active_alerts_count": len(self._active_alerts),
            "registered_rules_count": len(self._alert_rules),
            "alert_history_size": len(self._alert_history),
            "timestamp": datetime.now(),
        }

    async def close(self) -> None:
        """Close AlertManager."""
        await self.stop_monitoring()
        self._initialized = False
        self._logger.info("AlertManager closed")
