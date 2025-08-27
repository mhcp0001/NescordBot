"""Tests for LinkSuggestor class."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nescordbot.services.database import DatabaseService
from nescordbot.services.link_suggestor import LinkSuggestionError, LinkSuggestor


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
async def link_suggestor(mock_db):
    """Create a LinkSuggestor instance with mocked dependencies."""
    db, _, _ = mock_db
    suggestor = LinkSuggestor(db)
    await suggestor.initialize()
    return suggestor, mock_db


class TestLinkSuggestor:
    """Test cases for LinkSuggestor."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_db):
        """Test proper initialization."""
        db, _, _ = mock_db
        suggestor = LinkSuggestor(db)

        # Should not be initialized initially
        assert not suggestor._initialized

        # Initialize
        await suggestor.initialize()

        # Should be initialized now
        assert suggestor._initialized

    @pytest.mark.asyncio
    async def test_suggest_links_for_note_not_found(self, link_suggestor):
        """Test suggestion for non-existent note."""
        suggestor, (db, mock_conn, mock_cursor) = link_suggestor

        # Mock note not found
        mock_cursor.fetchone.return_value = None

        with pytest.raises(LinkSuggestionError, match="Note test-id not found"):
            await suggestor.suggest_links_for_note("test-id")

    @pytest.mark.asyncio
    async def test_suggest_links_for_note_success(self, link_suggestor):
        """Test successful link suggestions."""
        suggestor, (db, mock_conn, mock_cursor) = link_suggestor

        # Mock source note data
        source_note_row = (
            "source-id",
            "Source Note",
            "Source content about Python programming",
            '["python", "programming"]',
        )

        # Mock candidate notes
        candidate_rows = [
            (
                "candidate-1",
                "Python Tutorial",
                "Learn Python programming basics",
                '["python", "tutorial"]',
            ),
            (
                "candidate-2",
                "Advanced Programming",
                "Advanced programming concepts",
                '["programming", "advanced"]',
            ),
            ("candidate-3", "Unrelated Note", "This is about cooking", '["cooking", "recipes"]'),
        ]

        # Setup mock returns
        mock_cursor.fetchone.return_value = source_note_row
        mock_cursor.fetchall.return_value = candidate_rows

        # Run suggestions
        suggestions = await suggestor.suggest_links_for_note(
            "source-id", max_suggestions=5, min_similarity=0.1
        )

        # Should return suggestions sorted by similarity
        assert len(suggestions) >= 1
        assert suggestions[0]["note_id"] in ["candidate-1", "candidate-2"]
        assert "similarity_score" in suggestions[0]
        assert "similarity_reasons" in suggestions[0]

    @pytest.mark.asyncio
    async def test_suggest_by_content_keywords_success(self, link_suggestor):
        """Test content-based keyword suggestions."""
        suggestor, (db, mock_conn, mock_cursor) = link_suggestor

        # Mock search results
        search_results = [
            ("note-1", "Python Guide", "Python programming guide", '["python"]'),
            ("note-2", "Machine Learning", "ML with Python", '["python", "ml"]'),
        ]

        mock_cursor.fetchall.return_value = search_results

        # Run content suggestions
        suggestions = await suggestor.suggest_by_content_keywords(
            "I want to learn Python programming", exclude_note_id="exclude-id", max_suggestions=5
        )

        # Should return relevant notes
        assert len(suggestions) == 2
        assert suggestions[0]["note_id"] == "note-1"
        assert suggestions[1]["note_id"] == "note-2"

    @pytest.mark.asyncio
    async def test_similarity_calculation(self, link_suggestor):
        """Test similarity calculation methods."""
        suggestor, _ = link_suggestor

        note1 = {
            "title": "Python Programming",
            "content": "Learn Python programming basics with examples",
            "tags": ["python", "programming", "tutorial"],
        }

        note2 = {
            "title": "Python Tutorial",
            "content": "Python programming tutorial for beginners",
            "tags": ["python", "tutorial", "beginners"],
        }

        # Calculate similarity
        similarity = suggestor._calculate_similarity(note1, note2)

        # Should be high similarity due to common title words, content, and tags
        assert similarity > 0.5
        assert similarity <= 1.0

    @pytest.mark.asyncio
    async def test_keyword_extraction(self, link_suggestor):
        """Test keyword extraction from text."""
        suggestor, _ = link_suggestor

        text = "This is about Python programming and machine learning algorithms"
        keywords = suggestor._extract_keywords(text)

        # Should extract meaningful keywords
        assert "python" in keywords
        assert "programming" in keywords
        assert "machine" in keywords
        assert "learning" in keywords
        assert "algorithms" in keywords

        # Should not extract stop words
        assert "this" not in keywords
        assert "is" not in keywords
        assert "and" not in keywords

    @pytest.mark.asyncio
    async def test_tag_similarity(self, link_suggestor):
        """Test tag similarity calculation."""
        suggestor, _ = link_suggestor

        tags1 = ["python", "programming", "tutorial"]
        tags2 = ["python", "tutorial", "beginners"]

        similarity = suggestor._tag_similarity(tags1, tags2)

        # Jaccard similarity: 2 common / 4 total = 0.5
        assert abs(similarity - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_content_similarity(self, link_suggestor):
        """Test content similarity calculation."""
        suggestor, _ = link_suggestor

        content1 = "Python programming tutorial for beginners"
        content2 = "Python programming guide for new learners"

        similarity = suggestor._content_similarity(content1, content2)

        # Should have some similarity due to common keywords
        assert similarity > 0
        assert similarity <= 1.0

    @pytest.mark.asyncio
    async def test_similarity_reasons(self, link_suggestor):
        """Test similarity reasons generation."""
        suggestor, _ = link_suggestor

        note1 = {
            "title": "Python Programming",
            "content": "Python tutorial content",
            "tags": ["python", "tutorial"],
        }

        note2 = {
            "title": "Python Tutorial",
            "content": "Python programming guide",
            "tags": ["python", "guide"],
        }

        reasons = suggestor._get_similarity_reasons(note1, note2)

        # Should identify common elements
        assert len(reasons) > 0
        # Should mention title similarity or common tags
        reasons_text = " ".join(reasons)
        assert any(keyword in reasons_text.lower() for keyword in ["title", "tags", "keywords"])

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, link_suggestor):
        """Test health check when service is healthy."""
        suggestor, (db, mock_conn, mock_cursor) = link_suggestor

        # Mock note count query
        mock_cursor.fetchone.return_value = (42,)

        health = await suggestor.health_check()

        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert health["total_notes"] == 42

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, mock_db):
        """Test health check when service is unhealthy."""
        db, mock_conn, mock_cursor = mock_db

        # Create uninitialized suggestor
        suggestor = LinkSuggestor(db)

        # Mock database error
        mock_cursor.fetchone.side_effect = Exception("Database error")

        health = await suggestor.health_check()

        assert health["status"] == "unhealthy"
        assert "error" in health
        assert health["initialized"] is False

    @pytest.mark.asyncio
    async def test_parse_tags_json_string(self, link_suggestor):
        """Test parsing tags from JSON string."""
        suggestor, _ = link_suggestor

        tags_json = '["python", "programming", "tutorial"]'
        tags = suggestor._parse_tags(tags_json)

        assert tags == ["python", "programming", "tutorial"]

    @pytest.mark.asyncio
    async def test_parse_tags_invalid_json(self, link_suggestor):
        """Test parsing invalid JSON tags."""
        suggestor, _ = link_suggestor

        invalid_json = "invalid json"
        tags = suggestor._parse_tags(invalid_json)

        assert tags == []

    @pytest.mark.asyncio
    async def test_parse_tags_none(self, link_suggestor):
        """Test parsing None tags."""
        suggestor, _ = link_suggestor

        tags = suggestor._parse_tags(None)

        assert tags == []

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_db):
        """Test error handling in various scenarios."""
        db, mock_conn, mock_cursor = mock_db

        # Test database connection error
        db.get_connection.side_effect = Exception("Connection error")

        suggestor = LinkSuggestor(db)
        await suggestor.initialize()

        with pytest.raises(LinkSuggestionError):
            await suggestor.suggest_links_for_note("test-id")

    @pytest.mark.asyncio
    async def test_min_similarity_filtering(self, link_suggestor):
        """Test that low similarity suggestions are filtered out."""
        suggestor, (db, mock_conn, mock_cursor) = link_suggestor

        # Mock source note
        source_note_row = ("source-id", "Python Programming", "Python content", '["python"]')

        # Mock candidates with varying similarity
        candidate_rows = [
            (
                "similar-note",
                "Python Tutorial",
                "Python programming guide",
                '["python", "tutorial"]',
            ),
            ("different-note", "Cooking Recipes", "How to cook pasta", '["cooking", "recipes"]'),
        ]

        mock_cursor.fetchone.return_value = source_note_row
        mock_cursor.fetchall.return_value = candidate_rows

        # Test with high min_similarity (should filter out cooking note)
        suggestions = await suggestor.suggest_links_for_note("source-id", min_similarity=0.5)

        # Should only return highly similar notes
        for suggestion in suggestions:
            assert suggestion["similarity_score"] >= 0.5
