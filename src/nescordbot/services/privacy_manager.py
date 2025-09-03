"""
PrivacyManager service for personal information protection and security enhancement.

This service provides comprehensive privacy protection including PII detection,
data masking, security auditing, and integration with AlertManager.
"""

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from discord.ext import commands

from ..config import BotConfig
from ..logger import get_logger
from .database import DatabaseService


class PrivacyLevel(Enum):
    """Privacy protection levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MaskingType(Enum):
    """Data masking types."""

    ASTERISK = "asterisk"
    PARTIAL = "partial"
    HASH = "hash"
    REMOVE = "remove"


class SecurityEventType(Enum):
    """Security event types."""

    PII_DETECTED = "pii_detected"
    API_KEY_EXPOSED = "api_key_exposed"
    SUSPICIOUS_PATTERN = "suspicious_pattern"
    ACCESS_VIOLATION = "access_violation"


@dataclass
class PrivacyRule:
    """Defines a privacy protection rule."""

    id: str
    name: str
    pattern: str
    privacy_level: PrivacyLevel
    masking_type: MaskingType
    enabled: bool = True
    description: str = ""


@dataclass
class SecurityEvent:
    """Represents a security event."""

    id: str
    event_type: SecurityEventType
    message: str
    privacy_level: PrivacyLevel
    timestamp: datetime
    source: str
    details: Dict[str, Any]
    resolved: bool = False


class PrivacyManagerError(Exception):
    """Exception raised by PrivacyManager operations."""

    pass


class PrivacyManager:
    """
    Privacy and security management service.

    Provides comprehensive privacy protection including PII detection,
    data masking, security auditing, and AlertManager integration.
    """

    # Built-in PII detection patterns
    BUILTIN_PII_PATTERNS = {
        "email": {
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "level": PrivacyLevel.MEDIUM,
            "description": "Email address detection",
        },
        "phone_jp": {
            "pattern": r"\b0\d{1,4}-\d{1,4}-\d{4}\b",
            "level": PrivacyLevel.MEDIUM,
            "description": "Japanese phone number",
        },
        "phone_us": {
            "pattern": r"\b\d{3}-\d{3}-\d{4}\b",
            "level": PrivacyLevel.MEDIUM,
            "description": "US phone number",
        },
        "credit_card": {
            "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "level": PrivacyLevel.HIGH,
            "description": "Credit card number",
        },
        "ssn": {
            "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
            "level": PrivacyLevel.HIGH,
            "description": "Social Security Number",
        },
        "api_key": {
            "pattern": r"\b(?:sk_live_|sk_test_|pk_live_|pk_test_)[A-Za-z0-9]{32,}\b",
            "level": PrivacyLevel.HIGH,
            "description": "API key or token",
        },
        "jwt_token": {
            "pattern": r"\beyJ[A-Za-z0-9_/+\-=]+\b",
            "level": PrivacyLevel.HIGH,
            "description": "JWT token",
        },
        "ip_address": {
            "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "level": PrivacyLevel.LOW,
            "description": "IP address",
        },
    }

    def __init__(
        self,
        config: BotConfig,
        bot: commands.Bot,
        database_service: DatabaseService,
        alert_manager=None,
    ):
        """Initialize PrivacyManager."""
        self.config = config
        self.bot = bot
        self.db = database_service
        self.alert_manager = alert_manager
        self._logger = get_logger(__name__)

        # Runtime state
        self._initialized = False
        self._privacy_rules: Dict[str, PrivacyRule] = {}
        self._security_events: List[SecurityEvent] = []

        # Configuration
        self._enabled = getattr(config, "privacy_enabled", True)
        self._default_level = PrivacyLevel(getattr(config, "privacy_default_level", "medium"))
        self._default_masking = MaskingType(getattr(config, "privacy_masking_type", "asterisk"))
        self._pii_detection = getattr(config, "privacy_pii_detection", True)
        self._api_key_detection = getattr(config, "privacy_api_key_detection", True)
        self._audit_enabled = getattr(config, "privacy_audit_enabled", True)
        self._alert_integration = getattr(config, "privacy_alert_integration", True)
        self._retention_days = getattr(config, "privacy_retention_days", 90)

    async def initialize(self) -> None:
        """Initialize the PrivacyManager service."""
        if self._initialized:
            return

        try:
            # Create database tables
            await self._create_tables()

            # Load built-in privacy rules
            await self._load_builtin_rules()

            # Load custom rules from database
            await self._load_custom_rules()

            # Clean up old events
            await self._cleanup_old_events()

            self._initialized = True
            self._logger.info("PrivacyManager initialized successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize PrivacyManager: {e}")
            raise PrivacyManagerError(f"Initialization failed: {e}")

    async def _create_tables(self) -> None:
        """Create privacy-related database tables."""
        async with self.db.get_connection() as conn:
            # Privacy rules table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS privacy_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    privacy_level TEXT NOT NULL,
                    masking_type TEXT NOT NULL,
                    enabled BOOLEAN DEFAULT 1,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Security events table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS security_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    privacy_level TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source TEXT NOT NULL,
                    details TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TIMESTAMP
                )
                """
            )

            # Privacy settings table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS privacy_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            await conn.commit()

    async def _load_builtin_rules(self) -> None:
        """Load built-in privacy rules."""
        for rule_id, pattern_info in self.BUILTIN_PII_PATTERNS.items():
            if rule_id == "api_key" and not self._api_key_detection:
                continue
            if rule_id != "api_key" and not self._pii_detection:
                continue

            rule = PrivacyRule(
                id=rule_id,
                name=str(pattern_info["description"]),
                pattern=str(pattern_info["pattern"]),
                privacy_level=PrivacyLevel(pattern_info["level"]),
                masking_type=self._default_masking,
                enabled=True,
                description=f"Built-in rule: {pattern_info['description']}",
            )
            self._privacy_rules[rule_id] = rule

        self._logger.debug(f"Loaded {len(self._privacy_rules)} built-in privacy rules")

    async def _load_custom_rules(self) -> None:
        """Load custom privacy rules from database."""
        try:
            async with self.db.get_connection() as conn:
                query = (
                    "SELECT id, name, pattern, privacy_level, masking_type, enabled, "
                    "description FROM privacy_rules WHERE enabled = 1"
                )
                async with conn.execute(query) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                rule = PrivacyRule(
                    id=row[0],
                    name=row[1],
                    pattern=row[2],
                    privacy_level=PrivacyLevel(row[3]),
                    masking_type=MaskingType(row[4]),
                    enabled=bool(row[5]),
                    description=row[6] or "",
                )
                self._privacy_rules[rule.id] = rule

            self._logger.debug(f"Loaded {len(rows)} custom privacy rules")

        except Exception as e:
            self._logger.error(f"Failed to load custom privacy rules: {e}")

    async def _cleanup_old_events(self) -> None:
        """Clean up old security events."""
        try:
            cutoff_date = datetime.now() - timedelta(days=self._retention_days)
            async with self.db.get_connection() as conn:
                await conn.execute(
                    "DELETE FROM security_events WHERE timestamp < ?", (cutoff_date,)
                )
                await conn.commit()
        except Exception as e:
            self._logger.error(f"Failed to cleanup old events: {e}")

    async def detect_pii(self, text: str) -> List[Tuple[PrivacyRule, List[str]]]:
        """
        Detect personally identifiable information in text.

        Returns:
            List of (rule, matches) tuples for detected PII.
        """
        if not self._enabled or not text:
            return []

        detected = []

        for rule in self._privacy_rules.values():
            if not rule.enabled:
                continue

            try:
                pattern = re.compile(rule.pattern, re.IGNORECASE)
                matches = pattern.findall(text)

                if matches:
                    detected.append((rule, matches))

                    # Log security event
                    if self._audit_enabled:
                        await self._log_security_event(
                            SecurityEventType.PII_DETECTED,
                            f"PII detected by rule '{rule.name}': {len(matches)} matches",
                            rule.privacy_level,
                            "PrivacyManager.detect_pii",
                            {
                                "rule_id": rule.id,
                                "rule_name": rule.name,
                                "match_count": len(matches),
                            },
                        )

            except re.error as e:
                self._logger.warning(f"Invalid regex pattern in rule {rule.id}: {e}")
                continue

        return detected

    async def apply_masking(
        self,
        text: str,
        privacy_level: Optional[PrivacyLevel] = None,
        masking_type: Optional[MaskingType] = None,
    ) -> str:
        """
        Apply data masking to text based on privacy level and masking type.

        Args:
            text: Text to mask
            privacy_level: Privacy level to apply (uses default if None)
            masking_type: Masking type to use (uses default if None)

        Returns:
            Masked text
        """
        if not self._enabled or not text:
            return text

        level = privacy_level or self._default_level
        mask_type = masking_type or self._default_masking

        # Detect PII first
        detected_pii = await self.detect_pii(text)
        if not detected_pii:
            return text

        masked_text = text

        for rule, matches in detected_pii:
            # If explicitly requested NONE level, skip all masking
            if level == PrivacyLevel.NONE:
                continue

            # Use rule's privacy level if higher than requested level
            level_order = [
                PrivacyLevel.NONE,
                PrivacyLevel.LOW,
                PrivacyLevel.MEDIUM,
                PrivacyLevel.HIGH,
            ]
            effective_level = max(rule.privacy_level, level, key=lambda x: level_order.index(x))

            for match in matches:
                if effective_level == PrivacyLevel.NONE:
                    continue
                elif effective_level == PrivacyLevel.LOW:
                    replacement = self._mask_partial(match, 0.7)
                elif effective_level == PrivacyLevel.MEDIUM:
                    replacement = self._mask_partial(match, 0.3)
                elif effective_level == PrivacyLevel.HIGH:
                    replacement = self._get_high_level_mask(match, mask_type)

                masked_text = masked_text.replace(match, replacement)

        return masked_text

    def _mask_partial(self, text: str, show_ratio: float) -> str:
        """Apply partial masking showing specified ratio of original text."""
        if len(text) <= 2:
            return "*" * len(text)

        show_chars = max(1, int(len(text) * show_ratio))
        mask_chars = len(text) - show_chars

        # Show characters at the beginning
        return text[:show_chars] + "*" * mask_chars

    def _get_high_level_mask(self, text: str, mask_type: MaskingType) -> str:
        """Apply high-level masking based on masking type."""
        if mask_type == MaskingType.ASTERISK:
            return "*" * len(text)
        elif mask_type == MaskingType.PARTIAL:
            return text[:2] + "*" * (len(text) - 2) if len(text) > 2 else "*" * len(text)
        elif mask_type == MaskingType.HASH:
            return hashlib.md5(text.encode()).hexdigest()[:8] + "..."
        elif mask_type == MaskingType.REMOVE:
            return "[REDACTED]"
        else:
            return "***MASKED***"

    async def _log_security_event(
        self,
        event_type: SecurityEventType,
        message: str,
        privacy_level: PrivacyLevel,
        source: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log a security event and optionally trigger alerts."""
        event_id = str(uuid.uuid4())

        event = SecurityEvent(
            id=event_id,
            event_type=event_type,
            message=message,
            privacy_level=privacy_level,
            timestamp=datetime.now(),
            source=source,
            details=details or {},
        )

        # Store in memory
        self._security_events.append(event)

        # Store in database
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO security_events
                    (id, event_type, message, privacy_level, timestamp, source, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.event_type.value,
                        event.message,
                        event.privacy_level.value,
                        event.timestamp,
                        event.source,
                        json.dumps(event.details),
                    ),
                )
                await conn.commit()
        except Exception as e:
            self._logger.error(f"Failed to save security event: {e}")

        # Trigger alert if configured
        if self._alert_integration and self.alert_manager and privacy_level in [PrivacyLevel.HIGH]:
            await self._trigger_privacy_alert(event)

        return event_id

    async def _trigger_privacy_alert(self, event: SecurityEvent) -> None:
        """Trigger an alert through AlertManager."""
        try:
            # Import Alert here to avoid circular imports
            from .alert_manager import Alert, AlertSeverity

            # Map privacy level to alert severity
            severity_mapping = {
                PrivacyLevel.LOW: AlertSeverity.INFO,
                PrivacyLevel.MEDIUM: AlertSeverity.WARNING,
                PrivacyLevel.HIGH: AlertSeverity.CRITICAL,
            }

            alert = Alert(
                id=f"privacy_{event.id}",
                title=f"Privacy Event: {event.event_type.value}",
                message=event.message,
                severity=severity_mapping.get(event.privacy_level, AlertSeverity.WARNING),
                timestamp=event.timestamp,
                source="PrivacyManager",
                metadata={
                    "event_id": event.id,
                    "event_type": event.event_type.value,
                    "privacy_level": event.privacy_level.value,
                    "details": event.details,
                },
            )

            await self.alert_manager.send_alert(alert)

        except Exception as e:
            self._logger.error(f"Failed to trigger privacy alert: {e}")

    async def get_security_events(
        self, limit: int = 50, event_type: Optional[SecurityEventType] = None
    ) -> List[SecurityEvent]:
        """Get recent security events."""
        try:
            query = (
                "SELECT id, event_type, message, privacy_level, timestamp, "
                "source, details, resolved, resolved_at FROM security_events"
            )
            params = []

            if event_type:
                query += " WHERE event_type = ?"
                params.append(event_type.value)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(str(limit))

            events = []
            async with self.db.get_connection() as conn:
                async with conn.execute(query, tuple(params)) as cursor:
                    rows = await cursor.fetchall()

            for row in rows:
                details = {}
                try:
                    if row[6]:  # details column
                        details = json.loads(row[6])
                except json.JSONDecodeError:
                    pass

                event = SecurityEvent(
                    id=row[0],
                    event_type=SecurityEventType(row[1]),
                    message=row[2],
                    privacy_level=PrivacyLevel(row[3]),
                    timestamp=row[4]
                    if isinstance(row[4], datetime)
                    else datetime.fromisoformat(row[4]),
                    source=row[5],
                    details=details,
                    resolved=bool(row[7]),
                )
                events.append(event)

            return events

        except Exception as e:
            self._logger.error(f"Failed to get security events: {e}")
            return []

    async def add_custom_rule(
        self,
        name: str,
        pattern: str,
        privacy_level: PrivacyLevel,
        masking_type: MaskingType,
        description: str = "",
    ) -> str:
        """Add a custom privacy rule."""
        rule_id = str(uuid.uuid4())

        rule = PrivacyRule(
            id=rule_id,
            name=name,
            pattern=pattern,
            privacy_level=privacy_level,
            masking_type=masking_type,
            description=description,
        )

        try:
            # Validate regex pattern
            re.compile(pattern)

            # Store in database
            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO privacy_rules
                    (id, name, pattern, privacy_level, masking_type, enabled, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rule.id,
                        rule.name,
                        rule.pattern,
                        rule.privacy_level.value,
                        rule.masking_type.value,
                        rule.enabled,
                        rule.description,
                    ),
                )
                await conn.commit()

            # Add to runtime rules
            self._privacy_rules[rule_id] = rule

            self._logger.info(f"Added custom privacy rule: {name}")
            return rule_id

        except re.error as e:
            raise PrivacyManagerError(f"Invalid regex pattern: {e}")
        except Exception as e:
            self._logger.error(f"Failed to add custom rule: {e}")
            raise PrivacyManagerError(f"Failed to add rule: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status."""
        try:
            # Check database connectivity
            async with self.db.get_connection() as conn:
                await conn.execute("SELECT 1")

            # Get basic stats
            recent_events = len(
                [e for e in self._security_events if (datetime.now() - e.timestamp).days < 1]
            )

            return {
                "status": "healthy",
                "initialized": self._initialized,
                "enabled": self._enabled,
                "privacy_rules": len(self._privacy_rules),
                "recent_events": recent_events,
                "alert_integration": self._alert_integration and self.alert_manager is not None,
                "configuration": {
                    "default_level": self._default_level.value,
                    "default_masking": self._default_masking.value,
                    "pii_detection": self._pii_detection,
                    "api_key_detection": self._api_key_detection,
                    "audit_enabled": self._audit_enabled,
                },
            }

        except Exception as e:
            self._logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "initialized": self._initialized,
            }

    async def close(self) -> None:
        """Clean up resources."""
        try:
            # Clean up any resources if needed
            self._security_events.clear()
            self._privacy_rules.clear()
            self._initialized = False

            self._logger.info("PrivacyManager closed successfully")

        except Exception as e:
            self._logger.error(f"Error during PrivacyManager cleanup: {e}")
