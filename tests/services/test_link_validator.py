"""Tests for LinkValidator class."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from nescordbot.services.database import DatabaseService
from nescordbot.services.link_validator import (
    LinkValidationError,
    LinkValidationResult,
    LinkValidator,
)


@pytest.fixture
async def mock_db():
    """Create a mock database service."""
    db = MagicMock(spec=DatabaseService)
    db.is_initialized = True

    # Mock connection context manager
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()

    db.get_connection = MagicMock()
    db.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    db.get_connection.return_value.__aexit__ = AsyncMock()

    return db, mock_conn, mock_cursor


@pytest.fixture
async def link_validator(mock_db):
    """Create a LinkValidator instance with mocked dependencies."""
    db, _, _ = mock_db
    validator = LinkValidator(db)
    await validator.initialize()
    return validator, mock_db


class TestLinkValidationResult:
    """Test cases for LinkValidationResult."""

    def test_initialization(self):
        """Test proper initialization of validation result."""
        result = LinkValidationResult()

        assert result.broken_links == []
        assert result.orphan_notes == []
        assert result.circular_links == []
        assert result.duplicate_links == []
        assert result.total_notes == 0
        assert result.total_links == 0
        assert result.validation_time is None

    def test_is_healthy_true(self):
        """Test is_healthy returns True when no issues."""
        result = LinkValidationResult()

        assert result.is_healthy() is True

    def test_is_healthy_false_with_broken_links(self):
        """Test is_healthy returns False with broken links."""
        result = LinkValidationResult()
        result.broken_links = [{"link_id": "test-link"}]

        assert result.is_healthy() is False

    def test_is_healthy_false_with_circular_links(self):
        """Test is_healthy returns False with circular links."""
        result = LinkValidationResult()
        result.circular_links = [["note-1", "note-2"]]

        assert result.is_healthy() is False

    def test_is_healthy_false_with_duplicate_links(self):
        """Test is_healthy returns False with duplicate links."""
        result = LinkValidationResult()
        result.duplicate_links = [{"from_note_id": "note-1", "to_note_id": "note-2"}]

        assert result.is_healthy() is False

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = LinkValidationResult()
        result.total_notes = 5
        result.total_links = 10
        result.validation_time = "2023-01-01T10:00:00"

        dict_result = result.to_dict()

        assert dict_result["total_notes"] == 5
        assert dict_result["total_links"] == 10
        assert dict_result["is_healthy"] is True
        assert dict_result["validation_time"] == "2023-01-01T10:00:00"


class TestLinkValidator:
    """Test cases for LinkValidator."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_db):
        """Test proper initialization."""
        db, _, _ = mock_db
        validator = LinkValidator(db)

        # Should not be initialized initially
        assert not validator._initialized

        # Initialize
        await validator.initialize()

        # Should be initialized now
        assert validator._initialized

    @pytest.mark.asyncio
    async def test_validate_all_links_success(self, link_validator):
        """Test successful validation of all links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock query results
        mock_cursor.fetchone.side_effect = [(5,), (8,)]  # total notes  # total links

        # Mock the validation method calls
        validator._find_broken_links = AsyncMock(return_value=[])
        validator._find_orphan_notes = AsyncMock(return_value=[])
        validator._find_circular_links = AsyncMock(return_value=[])
        validator._find_duplicate_links = AsyncMock(return_value=[])

        result = await validator.validate_all_links()

        assert isinstance(result, LinkValidationResult)
        assert result.total_notes == 5
        assert result.total_links == 8
        assert result.is_healthy() is True
        assert result.validation_time is not None

    @pytest.mark.asyncio
    async def test_validate_note_links_success(self, link_validator):
        """Test validation of specific note links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock note exists
        note_row = ("test-id", "Test Note")
        mock_cursor.fetchone.return_value = note_row

        # Mock outgoing links
        outgoing_links = [
            ("link-1", "target-1", "reference", "Target 1"),
            ("link-2", "target-2", "reference", None),  # Broken link
        ]

        # Mock incoming links
        incoming_links = [("link-3", "source-1", "reference", "Source 1")]

        mock_cursor.fetchall.side_effect = [outgoing_links, incoming_links]

        result = await validator.validate_note_links("test-id")

        assert result["note"]["id"] == "test-id"
        assert result["note"]["title"] == "Test Note"
        assert len(result["outgoing_links"]["valid"]) == 1
        assert len(result["outgoing_links"]["broken"]) == 1
        assert len(result["incoming_links"]["valid"]) == 1
        assert result["total_broken"] == 1

    @pytest.mark.asyncio
    async def test_validate_note_links_not_found(self, link_validator):
        """Test validation of non-existent note."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock note not found
        mock_cursor.fetchone.return_value = None

        with pytest.raises(LinkValidationError, match="Note test-id not found"):
            await validator.validate_note_links("test-id")

    @pytest.mark.asyncio
    async def test_find_missing_bidirectional_links(self, link_validator):
        """Test finding missing bidirectional links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock one-way links
        one_way_links = [
            ("note-1", "note-2", "Title 1", "Title 2"),
            ("note-3", "note-4", "Title 3", "Title 4"),
        ]

        mock_cursor.fetchall.return_value = one_way_links

        missing_links = await validator.find_missing_bidirectional_links()

        assert len(missing_links) == 2
        assert missing_links[0]["from_note_id"] == "note-2"  # Reverse direction
        assert missing_links[0]["to_note_id"] == "note-1"
        assert missing_links[0]["suggested_link_type"] == "reference"

    @pytest.mark.asyncio
    async def test_find_broken_links(self, link_validator):
        """Test finding broken links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock broken links query result
        broken_links_data = [("link-1", "note-1", "missing-note", "reference", "Note 1 Title")]

        mock_cursor.fetchall.return_value = broken_links_data

        broken_links = await validator._find_broken_links(mock_cursor[1])

        assert len(broken_links) == 1
        assert broken_links[0]["link_id"] == "link-1"
        assert broken_links[0]["to_note_id"] == "missing-note"
        assert broken_links[0]["issue"] == "Target note not found"

    @pytest.mark.asyncio
    async def test_find_orphan_notes(self, link_validator):
        """Test finding orphan notes."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock orphan notes query result
        orphan_notes_data = [
            ("orphan-1", "Orphan Note 1", "2023-01-01T10:00:00", '["tag1", "tag2"]'),
            ("orphan-2", "Orphan Note 2", "2023-01-02T10:00:00", None),
        ]

        mock_cursor.fetchall.return_value = orphan_notes_data

        orphan_notes = await validator._find_orphan_notes(mock_cursor[1])

        assert len(orphan_notes) == 2
        assert orphan_notes[0]["note_id"] == "orphan-1"
        assert orphan_notes[0]["tags"] == ["tag1", "tag2"]
        assert orphan_notes[1]["tags"] == []  # None should be converted to empty list

    @pytest.mark.asyncio
    async def test_find_circular_links(self, link_validator):
        """Test finding circular links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock circular links query result
        circular_links_data = [("note-1", "note-2"), ("note-3", "note-4")]

        mock_cursor.fetchall.return_value = circular_links_data

        circular_links = await validator._find_circular_links(mock_cursor[1])

        assert len(circular_links) == 2
        assert circular_links[0] == ["note-1", "note-2"]
        assert circular_links[1] == ["note-3", "note-4"]

    @pytest.mark.asyncio
    async def test_find_duplicate_links(self, link_validator):
        """Test finding duplicate links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock duplicate links query result
        duplicate_links_data = [
            ("note-1", "note-2", "reference", 3),
            ("note-3", "note-4", "mention", 2),
        ]

        mock_cursor.fetchall.return_value = duplicate_links_data

        duplicate_links = await validator._find_duplicate_links(mock_cursor[1])

        assert len(duplicate_links) == 2
        assert duplicate_links[0]["from_note_id"] == "note-1"
        assert duplicate_links[0]["duplicate_count"] == 3
        assert duplicate_links[1]["duplicate_count"] == 2

    @pytest.mark.asyncio
    async def test_repair_broken_links(self, link_validator):
        """Test repairing broken links."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Create validation result with issues
        validation_result = LinkValidationResult()
        validation_result.broken_links = [{"link_id": "broken-1"}, {"link_id": "broken-2"}]
        validation_result.duplicate_links = [
            {"from_note_id": "note-1", "to_note_id": "note-2", "link_type": "reference"}
        ]

        # Mock duplicate link IDs query
        mock_cursor.fetchall.return_value = [("dup-1",), ("dup-2",), ("dup-3",)]

        repair_counts = await validator.repair_broken_links(validation_result)

        assert repair_counts["broken_links_removed"] == 2
        assert repair_counts["duplicate_links_removed"] == 2  # Keep oldest, remove 2 others

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, link_validator):
        """Test health check when validator is healthy."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock healthy validation result
        validator.validate_all_links = AsyncMock()
        mock_result = LinkValidationResult()
        mock_result.total_notes = 10
        mock_result.total_links = 15
        validator.validate_all_links.return_value = mock_result

        health = await validator.health_check()

        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert health["summary"]["total_notes"] == 10
        assert health["summary"]["total_links"] == 15

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, mock_db):
        """Test health check when validator has issues."""
        db, mock_conn, mock_cursor = mock_db

        validator = LinkValidator(db)
        await validator.initialize()

        # Mock validation failure
        validator.validate_all_links = AsyncMock()
        mock_result = LinkValidationResult()
        mock_result.broken_links = [{"link_id": "test"}]
        validator.validate_all_links.return_value = mock_result

        health = await validator.health_check()

        assert health["status"] == "issues_found"
        assert health["summary"]["broken_links"] == 1

    @pytest.mark.asyncio
    async def test_health_check_error(self, mock_db):
        """Test health check when there's an error."""
        db, mock_conn, mock_cursor = mock_db

        # Create uninitialized validator
        validator = LinkValidator(db)

        # Mock validation error
        validator.validate_all_links = AsyncMock(side_effect=Exception("Test error"))

        health = await validator.health_check()

        assert health["status"] == "unhealthy"
        assert "error" in health
        assert health["initialized"] is False

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_db):
        """Test error handling in various scenarios."""
        db, mock_conn, mock_cursor = mock_db

        # Test database connection error
        db.get_connection.side_effect = Exception("Connection error")

        validator = LinkValidator(db)
        await validator.initialize()

        with pytest.raises(LinkValidationError):
            await validator.validate_all_links()

    @pytest.mark.asyncio
    async def test_validation_result_with_issues(self, link_validator):
        """Test validation when issues are found."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock query results
        mock_cursor.fetchone.side_effect = [(10,), (20,)]  # total notes  # total links

        # Mock validation methods with issues
        validator._find_broken_links = AsyncMock(return_value=[{"link_id": "broken"}])
        validator._find_orphan_notes = AsyncMock(return_value=[{"note_id": "orphan"}])
        validator._find_circular_links = AsyncMock(return_value=[["circular1", "circular2"]])
        validator._find_duplicate_links = AsyncMock(return_value=[{"from_note_id": "dup"}])

        result = await validator.validate_all_links()

        assert result.is_healthy() is False
        assert len(result.broken_links) == 1
        assert len(result.orphan_notes) == 1
        assert len(result.circular_links) == 1
        assert len(result.duplicate_links) == 1

    @pytest.mark.asyncio
    async def test_invalid_json_in_orphan_notes(self, link_validator):
        """Test handling of invalid JSON in orphan notes tags."""
        validator, (db, mock_conn, mock_cursor) = link_validator

        # Mock orphan notes with invalid JSON
        orphan_notes_data = [
            ("orphan-1", "Orphan Note", "2023-01-01T10:00:00", "invalid json"),
            ("orphan-2", "Orphan Note 2", "2023-01-01T10:00:00", "123"),  # Invalid type
        ]

        mock_cursor.fetchall.return_value = orphan_notes_data

        orphan_notes = await validator._find_orphan_notes(mock_cursor[1])

        # Should handle invalid JSON gracefully
        assert len(orphan_notes) == 2
        assert orphan_notes[0]["tags"] == []
        assert orphan_notes[1]["tags"] == []
