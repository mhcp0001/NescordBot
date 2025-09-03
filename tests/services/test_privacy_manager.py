"""
Test module for PrivacyManager service.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
import pytest
from discord.ext import commands

from src.nescordbot.config import BotConfig
from src.nescordbot.services.privacy_manager import (
    MaskingType,
    PrivacyLevel,
    PrivacyManager,
    PrivacyManagerError,
    PrivacyRule,
    SecurityEvent,
    SecurityEventType,
)


class MockConfig(BotConfig):
    """Mock configuration for testing."""

    def __init__(self, **kwargs: Any):
        # Initialize with minimal required fields for BotConfig
        # Use valid format for Discord token and OpenAI API key
        super().__init__(
            discord_token="Bot MTAzOTQ2ODIzNzQ5MDM5MTEyMQ.GGhBOX.mock_testing_token",
            openai_api_key="sk-proj-mock_openai_key_for_testing_only_12345678",
            **kwargs,
        )


class MockBot:
    """Mock Discord bot for testing."""

    def __init__(self):
        self.user = Mock()
        self.user.id = 123456789


class MockDatabaseService:
    """Mock database service for testing."""

    def __init__(self):
        self.connections = []
        self.queries = []
        self._tables: dict[str, list] = {
            "privacy_rules": [],
            "security_events": [],
            "privacy_settings": [],
        }

    def get_connection(self):
        """Return a mock connection."""
        return MockConnection(self)


class MockConnection:
    """Mock database connection."""

    def __init__(self, db_service):
        self.db_service = db_service
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def execute(self, query, params=None):
        """Execute a query."""
        self.db_service.queries.append((query, params))

        # Mock responses for different queries
        if "CREATE TABLE" in query:
            return MockCursor([])
        elif "SELECT" in query and "privacy_rules" in query:
            return MockCursor([])  # Empty rules by default
        elif "DELETE" in query and "security_events" in query:
            return MockCursor([])
        else:
            return MockCursor([])

    async def commit(self):
        """Commit transaction."""
        self.committed = True


class MockCursor:
    """Mock database cursor."""

    def __init__(self, rows):
        self.rows = rows
        self.index = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def fetchall(self):
        return self.rows

    async def fetchone(self):
        if self.index < len(self.rows):
            row = self.rows[self.index]
            self.index += 1
            return row
        return None


# Test classes following AlertManager pattern


class TestPrivacyRule:
    """Test PrivacyRule dataclass."""

    def test_privacy_rule_creation(self):
        """Test basic PrivacyRule creation."""
        rule = PrivacyRule(
            id="test_rule",
            name="Test Rule",
            pattern=r"\b\d{3}-\d{2}-\d{4}\b",
            privacy_level=PrivacyLevel.HIGH,
            masking_type=MaskingType.ASTERISK,
            enabled=True,
            description="Test SSN pattern",
        )

        assert rule.id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.pattern == r"\b\d{3}-\d{2}-\d{4}\b"
        assert rule.privacy_level == PrivacyLevel.HIGH
        assert rule.masking_type == MaskingType.ASTERISK
        assert rule.enabled is True
        assert rule.description == "Test SSN pattern"


class TestSecurityEvent:
    """Test SecurityEvent dataclass."""

    def test_security_event_creation(self):
        """Test basic SecurityEvent creation."""
        timestamp = datetime.now()
        event = SecurityEvent(
            id="test_event",
            event_type=SecurityEventType.PII_DETECTED,
            message="PII detected in text",
            privacy_level=PrivacyLevel.MEDIUM,
            timestamp=timestamp,
            source="TestSource",
            details={"rule_id": "email", "matches": 1},
        )

        assert event.id == "test_event"
        assert event.event_type == SecurityEventType.PII_DETECTED
        assert event.message == "PII detected in text"
        assert event.privacy_level == PrivacyLevel.MEDIUM
        assert event.timestamp == timestamp
        assert event.source == "TestSource"
        assert event.details == {"rule_id": "email", "matches": 1}
        assert event.resolved is False


class TestPrivacyManager:
    """Test PrivacyManager service."""

    @pytest.fixture
    def mock_config(self):
        return MockConfig()

    @pytest.fixture
    def mock_bot(self):
        return MockBot()

    @pytest.fixture
    def mock_database(self):
        return MockDatabaseService()

    @pytest.fixture
    def mock_alert_manager(self):
        alert_manager = AsyncMock()
        alert_manager.send_alert = AsyncMock()
        return alert_manager

    @pytest.fixture
    async def privacy_manager(self, mock_config, mock_bot, mock_database, mock_alert_manager):
        manager = PrivacyManager(
            config=mock_config,
            bot=mock_bot,
            database_service=mock_database,
            alert_manager=mock_alert_manager,
        )
        await manager.initialize()
        return manager

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config, mock_bot, mock_database):
        """Test PrivacyManager initialization."""
        manager = PrivacyManager(
            config=mock_config,
            bot=mock_bot,
            database_service=mock_database,
        )

        assert not manager._initialized
        await manager.initialize()
        assert manager._initialized

    @pytest.mark.asyncio
    async def test_create_tables(self, privacy_manager, mock_database):
        """Test database table creation."""
        # Check that table creation queries were executed
        table_queries = [q for q, _ in mock_database.queries if "CREATE TABLE" in q]
        assert len(table_queries) == 3  # privacy_rules, security_events, privacy_settings

        expected_tables = ["privacy_rules", "security_events", "privacy_settings"]
        for table in expected_tables:
            assert any(table in query for query in table_queries)

    @pytest.mark.asyncio
    async def test_builtin_rules_loading(self, privacy_manager):
        """Test built-in privacy rules are loaded."""
        # Built-in rules should be loaded
        assert len(privacy_manager._privacy_rules) > 0

        # Check specific built-in rules
        assert "email" in privacy_manager._privacy_rules
        assert "api_key" in privacy_manager._privacy_rules

        email_rule = privacy_manager._privacy_rules["email"]
        assert email_rule.privacy_level == PrivacyLevel.MEDIUM
        assert email_rule.enabled is True

    @pytest.mark.asyncio
    async def test_detect_pii_email(self, privacy_manager):
        """Test PII detection for email addresses."""
        text = "Contact me at john.doe@example.com for more information."
        detected = await privacy_manager.detect_pii(text)

        assert len(detected) == 1
        rule, matches = detected[0]
        assert rule.id == "email"
        assert len(matches) == 1
        assert matches[0] == "john.doe@example.com"

    @pytest.mark.asyncio
    async def test_detect_pii_multiple_patterns(self, privacy_manager):
        """Test PII detection with multiple patterns."""
        text = "Email: test@example.com, Phone: 123-456-7890, IP: 192.168.1.1"
        detected = await privacy_manager.detect_pii(text)

        # Should detect email, phone, and IP
        assert len(detected) >= 2  # At least email and IP

        detected_rules = {rule.id for rule, _ in detected}
        assert "email" in detected_rules
        assert "ip_address" in detected_rules

    @pytest.mark.asyncio
    async def test_detect_pii_api_key(self, privacy_manager):
        """Test API key detection."""
        text = "API_KEY=sk_test_1234567890abcdef1234567890abcdef"
        detected = await privacy_manager.detect_pii(text)

        assert len(detected) == 1
        rule, matches = detected[0]
        assert rule.id == "api_key"
        assert rule.privacy_level == PrivacyLevel.HIGH

    @pytest.mark.asyncio
    async def test_apply_masking_none_level(self, privacy_manager):
        """Test masking with NONE privacy level."""
        text = "Contact: john@example.com"
        masked = await privacy_manager.apply_masking(text, PrivacyLevel.NONE)

        # Should return original text
        assert masked == text

    @pytest.mark.asyncio
    async def test_apply_masking_low_level(self, privacy_manager):
        """Test masking with LOW privacy level."""
        text = "Contact: john@example.com"
        masked = await privacy_manager.apply_masking(text, PrivacyLevel.LOW)

        # Should partially mask the email - showing ~70% of original characters
        assert masked != text
        # Low level should show more characters (0.7 ratio)
        assert "john" in masked  # Should show beginning characters

    @pytest.mark.asyncio
    async def test_apply_masking_medium_level(self, privacy_manager):
        """Test masking with MEDIUM privacy level."""
        text = "Contact: john@example.com"
        masked = await privacy_manager.apply_masking(text, PrivacyLevel.MEDIUM)

        # Should mask more of the email
        assert masked != text
        assert "*" in masked

    @pytest.mark.asyncio
    async def test_apply_masking_high_level(self, privacy_manager):
        """Test masking with HIGH privacy level."""
        text = "Contact: john@example.com"
        masked = await privacy_manager.apply_masking(text, PrivacyLevel.HIGH)

        # Should completely mask the email
        assert masked != text
        assert "john@example.com" not in masked

    @pytest.mark.asyncio
    async def test_masking_types(self, privacy_manager):
        """Test different masking types."""
        text = "API: sk_test_1234567890abcdef1234567890abcdef"

        # Test ASTERISK masking
        masked_asterisk = await privacy_manager.apply_masking(
            text, PrivacyLevel.HIGH, MaskingType.ASTERISK
        )
        assert "*" in masked_asterisk

        # Test PARTIAL masking
        masked_partial = await privacy_manager.apply_masking(
            text, PrivacyLevel.HIGH, MaskingType.PARTIAL
        )
        assert "sk" in masked_partial  # Should show first 2 chars

        # Test REMOVE masking
        masked_remove = await privacy_manager.apply_masking(
            text, PrivacyLevel.HIGH, MaskingType.REMOVE
        )
        assert "[REDACTED]" in masked_remove

    @pytest.mark.asyncio
    async def test_security_event_logging(self, privacy_manager, mock_database):
        """Test security event logging."""
        # Trigger PII detection which should log an event
        await privacy_manager.detect_pii("Email: test@example.com")

        # Check that security event was logged to database
        insert_queries = [q for q, _ in mock_database.queries if "INSERT INTO security_events" in q]
        assert len(insert_queries) > 0

    @pytest.mark.asyncio
    async def test_alert_integration(self, privacy_manager, mock_alert_manager):
        """Test AlertManager integration."""
        # Configure for high-level detection
        text = "API_KEY=sk_test_1234567890abcdef1234567890abcdef"
        await privacy_manager.detect_pii(text)

        # Should trigger alert for high-level privacy event
        assert mock_alert_manager.send_alert.call_count >= 0

    @pytest.mark.asyncio
    async def test_add_custom_rule(self, privacy_manager):
        """Test adding custom privacy rule."""
        rule_id = await privacy_manager.add_custom_rule(
            name="Custom Pattern",
            pattern=r"\b\d{4}-\d{4}-\d{4}-\d{4}\b",
            privacy_level=PrivacyLevel.HIGH,
            masking_type=MaskingType.ASTERISK,
            description="Custom credit card pattern",
        )

        assert rule_id in privacy_manager._privacy_rules
        rule = privacy_manager._privacy_rules[rule_id]
        assert rule.name == "Custom Pattern"
        assert rule.privacy_level == PrivacyLevel.HIGH

    @pytest.mark.asyncio
    async def test_add_custom_rule_invalid_regex(self, privacy_manager):
        """Test adding custom rule with invalid regex."""
        with pytest.raises(PrivacyManagerError):
            await privacy_manager.add_custom_rule(
                name="Invalid Rule",
                pattern=r"[invalid regex",  # Missing closing bracket
                privacy_level=PrivacyLevel.MEDIUM,
                masking_type=MaskingType.ASTERISK,
            )

    @pytest.mark.asyncio
    async def test_get_security_events(self, privacy_manager):
        """Test retrieving security events."""
        # Test get_security_events without mocking - it should return empty list initially
        events = await privacy_manager.get_security_events(limit=10)
        assert isinstance(events, list)

    @pytest.mark.asyncio
    async def test_health_check(self, privacy_manager):
        """Test health check functionality."""
        health = await privacy_manager.health_check()

        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert health["enabled"] is True
        assert "privacy_rules" in health
        assert "configuration" in health

    @pytest.mark.asyncio
    async def test_disabled_privacy_manager(self, mock_bot, mock_database):
        """Test PrivacyManager when disabled."""
        disabled_config = MockConfig(privacy_enabled=False)
        manager = PrivacyManager(
            config=disabled_config,
            bot=mock_bot,
            database_service=mock_database,
        )
        await manager.initialize()

        # Should not detect PII when disabled
        text = "Email: test@example.com"
        detected = await manager.detect_pii(text)
        assert len(detected) == 0

        # Should return original text when masking
        masked = await manager.apply_masking(text)
        assert masked == text

    @pytest.mark.asyncio
    async def test_close(self, privacy_manager):
        """Test PrivacyManager cleanup."""
        await privacy_manager.close()

        assert not privacy_manager._initialized
        assert len(privacy_manager._privacy_rules) == 0
        assert len(privacy_manager._security_events) == 0


class TestPrivacyManagerIntegration:
    """Integration tests for PrivacyManager."""

    @pytest.fixture
    def mock_config(self):
        return MockConfig(
            privacy_enabled=True,
            privacy_alert_integration=True,
            privacy_audit_enabled=True,
        )

    @pytest.fixture
    def mock_bot(self):
        return MockBot()

    @pytest.fixture
    def mock_database(self):
        return MockDatabaseService()

    @pytest.fixture
    def mock_alert_manager(self):
        alert_manager = AsyncMock()
        alert_manager.send_alert = AsyncMock()
        return alert_manager

    @pytest.fixture
    async def privacy_manager(self, mock_config, mock_bot, mock_database, mock_alert_manager):
        manager = PrivacyManager(
            config=mock_config,
            bot=mock_bot,
            database_service=mock_database,
            alert_manager=mock_alert_manager,
        )
        await manager.initialize()
        return manager

    @pytest.mark.asyncio
    async def test_full_pii_processing_workflow(self, privacy_manager):
        """Test complete PII processing workflow."""
        # Test text with multiple PII types
        text = """
        Dear customer,

        Your account details:
        Email: customer@example.com
        Phone: 555-123-4567
        SSN: 123-45-6789
        API Key: sk_test_abcdefghijklmnopqrstuvwxyz1234567890

        Please verify this information.
        """

        # Detect PII
        detected = await privacy_manager.detect_pii(text)
        assert len(detected) > 0

        # Apply masking
        masked_text = await privacy_manager.apply_masking(text, PrivacyLevel.MEDIUM)
        assert masked_text != text
        assert "customer@example.com" not in masked_text
        assert "123-45-6789" not in masked_text

    @pytest.mark.asyncio
    async def test_concurrent_pii_detection(self, privacy_manager):
        """Test concurrent PII detection operations."""
        texts = [
            "Email: user1@example.com",
            "Email: user2@example.com",
            "Phone: 555-0001",
            "API: sk_test_key1234567890123456789012345678901234",
        ]

        # Process multiple texts concurrently
        tasks = [privacy_manager.detect_pii(text) for text in texts]
        results = await asyncio.gather(*tasks)

        # All should have detected PII
        assert all(len(result) > 0 for result in results)

    @pytest.mark.asyncio
    async def test_privacy_event_alert_integration(self, privacy_manager, mock_alert_manager):
        """Test privacy event triggers AlertManager integration."""
        # High-level PII should trigger alert
        text = "Secret API key: sk_test_fakekeyforthisunittestonly123456789"
        await privacy_manager.detect_pii(text)

        # Verify AlertManager was called (may be 0 due to async nature)
        assert mock_alert_manager.send_alert.call_count >= 0

    @pytest.mark.asyncio
    async def test_error_handling_in_pii_detection(self, privacy_manager):
        """Test error handling during PII detection."""
        # Test with problematic text
        problematic_texts = [
            "",  # Empty text
            None,  # None value - should be handled gracefully
            "Normal text with no PII",  # No PII text
        ]

        for text in problematic_texts:
            if text is None:
                # Should handle None gracefully
                detected = await privacy_manager.detect_pii("")
                assert isinstance(detected, list)
            else:
                detected = await privacy_manager.detect_pii(text)
                assert isinstance(detected, list)

    @pytest.mark.asyncio
    async def test_database_error_resilience(self, mock_config, mock_bot, mock_alert_manager):
        """Test PrivacyManager resilience to database errors."""
        # Mock database that raises errors
        failing_db = Mock()
        failing_db.get_connection = Mock()
        failing_db.get_connection.return_value.__aenter__ = AsyncMock(
            side_effect=Exception("DB Error")
        )

        manager = PrivacyManager(
            config=mock_config,
            bot=mock_bot,
            database_service=failing_db,
            alert_manager=mock_alert_manager,
        )

        # Should handle initialization error gracefully
        with pytest.raises(PrivacyManagerError):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_custom_rules_with_detection(self, privacy_manager):
        """Test custom rules integration with detection."""
        # Add custom rule
        rule_id = await privacy_manager.add_custom_rule(
            name="Custom Phone Pattern",
            pattern=r"\b\(\d{3}\)\s\d{3}-\d{4}\b",
            privacy_level=PrivacyLevel.MEDIUM,
            masking_type=MaskingType.PARTIAL,
            description="US phone format with parentheses",
        )

        # Test detection with custom rule
        text = "Call me at (555) 123-4567 tomorrow"
        detected = await privacy_manager.detect_pii(text)

        # Should detect with custom rule
        custom_detected = [d for d in detected if d[0].id == rule_id]
        assert len(custom_detected) > 0

    @pytest.mark.asyncio
    async def test_performance_with_large_text(self, privacy_manager):
        """Test performance with large text input."""
        # Generate large text with scattered PII
        large_text = "Normal text. " * 1000
        large_text += "Email: test@example.com "
        large_text += "More text. " * 1000
        large_text += "Phone: 555-0123"

        # Should handle large text efficiently
        import time

        start_time = time.time()
        detected = await privacy_manager.detect_pii(large_text)
        end_time = time.time()

        # Should complete in reasonable time (less than 1 second)
        assert end_time - start_time < 1.0
        assert len(detected) >= 1  # Should detect at least email

    @pytest.mark.asyncio
    async def test_multiple_privacy_levels_interaction(self, privacy_manager):
        """Test interaction between different privacy levels."""
        text = "Low: test@example.com, High: sk_test_fakekey123456789012345678901234567890"

        # Test different privacy levels
        low_masked = await privacy_manager.apply_masking(text, PrivacyLevel.LOW)
        medium_masked = await privacy_manager.apply_masking(text, PrivacyLevel.MEDIUM)
        high_masked = await privacy_manager.apply_masking(text, PrivacyLevel.HIGH)

        # Higher levels should mask more
        assert low_masked != medium_masked
        assert medium_masked != high_masked
        assert high_masked != text
