"""Test KnowledgeManager fallback integration."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.chromadb_service import ChromaDBService
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.embedding import EmbeddingService
from src.nescordbot.services.fallback_manager import FallbackManager
from src.nescordbot.services.knowledge_manager import KnowledgeManager
from src.nescordbot.services.obsidian_github import ObsidianGitHubService
from src.nescordbot.services.sync_manager import SyncManager


@pytest.fixture
def mock_config():
    """Mock BotConfig for testing."""
    config = Mock(spec=BotConfig)
    config.gemini_api_key = "test_key"
    return config


@pytest.fixture
def mock_services():
    """Mock all required services."""
    database_service = Mock(spec=DatabaseService)
    chromadb_service = Mock(spec=ChromaDBService)
    embedding_service = Mock(spec=EmbeddingService)
    sync_manager = Mock(spec=SyncManager)
    obsidian_github_service = Mock(spec=ObsidianGitHubService)

    return {
        "database": database_service,
        "chromadb": chromadb_service,
        "embedding": embedding_service,
        "sync": sync_manager,
        "obsidian": obsidian_github_service,
    }


@pytest.fixture
async def mock_fallback_manager():
    """Mock FallbackManager for testing."""
    manager = Mock(spec=FallbackManager)
    manager.is_service_available = Mock()
    manager.get_cached_data = AsyncMock()
    manager.cache_data = AsyncMock()
    return manager


@pytest.fixture
def knowledge_manager(mock_config, mock_services, mock_fallback_manager):
    """Create KnowledgeManager instance with fallback manager."""
    return KnowledgeManager(
        config=mock_config,
        database_service=mock_services["database"],
        chromadb_service=mock_services["chromadb"],
        embedding_service=mock_services["embedding"],
        sync_manager=mock_services["sync"],
        obsidian_github_service=mock_services["obsidian"],
        fallback_manager=mock_fallback_manager,
    )


class TestKnowledgeManagerFallback:
    """Test KnowledgeManager fallback integration."""

    async def test_suggest_tags_with_fallback_unavailable(
        self, knowledge_manager, mock_fallback_manager
    ):
        """Test tag suggestion when service is unavailable."""
        # Setup: Service unavailable, no cached data
        mock_fallback_manager.is_service_available.return_value = False
        mock_fallback_manager.get_cached_data.return_value = None

        # Execute
        result = await knowledge_manager.suggest_tags_for_content(
            "This is a programming function that handles user authentication", "User Auth Function"
        )

        # Verify fallback to basic suggestions
        assert isinstance(result, list)
        # Should contain programming-related tags from basic suggestions
        tag_names = [suggestion["tag"] for suggestion in result]
        assert "programming" in tag_names

        # Verify fallback manager was consulted
        mock_fallback_manager.is_service_available.assert_called_once_with("tag_suggestion")
        mock_fallback_manager.get_cached_data.assert_called_once()

    async def test_suggest_tags_with_cached_data(self, knowledge_manager, mock_fallback_manager):
        """Test tag suggestion using cached data when service unavailable."""
        # Setup: Service unavailable, but cached data available
        mock_fallback_manager.is_service_available.return_value = False
        cached_suggestions = [
            {"tag": "cached-tag1", "confidence": 0.9, "reason": "cached"},
            {"tag": "cached-tag2", "confidence": 0.8, "reason": "cached"},
        ]
        mock_fallback_manager.get_cached_data.return_value = cached_suggestions

        # Execute
        result = await knowledge_manager.suggest_tags_for_content("Test content", "Test Title")

        # Verify cached data is returned
        assert result == cached_suggestions
        mock_fallback_manager.get_cached_data.assert_called_once()

    @patch("src.nescordbot.services.knowledge_manager.genai")
    async def test_suggest_tags_with_ai_and_caching(
        self, mock_genai, knowledge_manager, mock_fallback_manager, mock_services
    ):
        """Test tag suggestion with AI when service is available."""
        # Setup: Service available
        mock_fallback_manager.is_service_available.return_value = True

        # Mock database call
        mock_services["database"].get_connection = AsyncMock()
        mock_connection = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [("existing-tag1",), ("existing-tag2",)]
        mock_connection.execute.return_value = mock_cursor
        mock_services[
            "database"
        ].get_connection.return_value.__aenter__.return_value = mock_connection

        # Mock Gemini API response
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = (
            '{"suggestions": [{"tag": "ai-tag", "confidence": 0.95, "reason": "AI analysis"}]}'
        )
        mock_model.generate_content_async.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        # Mock the parsing method to return expected format
        knowledge_manager._parse_tag_suggestions = Mock(
            return_value=[{"tag": "ai-tag", "confidence": 0.95, "reason": "AI analysis"}]
        )
        knowledge_manager._filter_and_score_suggestions = Mock(
            return_value=[{"tag": "ai-tag", "confidence": 0.95, "reason": "AI analysis"}]
        )

        # Execute
        result = await knowledge_manager.suggest_tags_for_content(
            "Test content for AI analysis", "AI Test Title"
        )

        # Verify AI was used
        assert len(result) > 0
        assert result[0]["tag"] == "ai-tag"

        # Verify caching was called
        mock_fallback_manager.cache_data.assert_called_once()
        cache_call_args = mock_fallback_manager.cache_data.call_args
        assert cache_call_args[0][0] == "tag_suggestions"  # cache_type
        assert len(cache_call_args[0]) == 3  # cache_type, key, data

    async def test_suggest_tags_error_with_fallback_cache(
        self, knowledge_manager, mock_fallback_manager
    ):
        """Test tag suggestion error handling with fallback cache."""
        # Setup: Service available but AI call fails
        mock_fallback_manager.is_service_available.return_value = True

        # Mock database to raise an error (simulating AI service failure)
        with patch.object(
            knowledge_manager, "_get_all_existing_tags", side_effect=Exception("AI Error")
        ):
            # Setup cached data for fallback
            cached_suggestions = [{"tag": "fallback-tag", "confidence": 0.7, "reason": "cached"}]
            mock_fallback_manager.get_cached_data.return_value = cached_suggestions

            # Execute
            result = await knowledge_manager.suggest_tags_for_content("Test content", "Test Title")

            # Verify fallback cache is used
            assert result == cached_suggestions

    async def test_search_notes_with_fallback_unavailable(
        self, knowledge_manager, mock_fallback_manager, mock_services
    ):
        """Test note search when service is unavailable."""
        # Setup: Knowledge search unavailable, no cached data
        mock_fallback_manager.is_service_available.return_value = False
        mock_fallback_manager.get_cached_data.return_value = None

        # Mock database search to simulate basic search still working
        mock_services["database"].search_notes = AsyncMock(
            return_value=[{"id": "1", "title": "Test Note", "content": "Test content"}]
        )

        # Execute
        result = await knowledge_manager.search_notes("test query")

        # Verify basic search still works
        assert len(result) == 1
        assert result[0]["title"] == "Test Note"

        # Verify fallback manager was consulted
        mock_fallback_manager.is_service_available.assert_called_once_with("knowledge_search")

    async def test_search_notes_with_cached_results(self, knowledge_manager, mock_fallback_manager):
        """Test note search using cached results when service unavailable."""
        # Setup: Service unavailable, cached results available
        mock_fallback_manager.is_service_available.return_value = False
        cached_results = [{"id": "cached1", "title": "Cached Note", "content": "Cached content"}]
        mock_fallback_manager.get_cached_data.return_value = cached_results

        # Execute
        result = await knowledge_manager.search_notes("cached query")

        # Verify cached results are returned
        assert result == cached_results
        mock_fallback_manager.get_cached_data.assert_called_once()

    async def test_search_notes_with_caching(
        self, knowledge_manager, mock_fallback_manager, mock_services
    ):
        """Test note search with result caching when service is available."""
        # Setup: Service available
        mock_fallback_manager.is_service_available.return_value = True

        # Mock database search
        search_results = [
            {"id": "1", "title": "Search Result", "content": "Search content", "tags": ["tag1"]}
        ]
        mock_services["database"].search_notes = AsyncMock(return_value=search_results)

        # Execute
        result = await knowledge_manager.search_notes("test query", tags=["tag1"])

        # Verify results
        assert len(result) == 1
        assert result[0]["title"] == "Search Result"

        # Verify caching was called
        mock_fallback_manager.cache_data.assert_called_once()
        cache_call_args = mock_fallback_manager.cache_data.call_args
        assert cache_call_args[0][0] == "search_results"  # cache_type

    async def test_basic_tag_suggestions(self, knowledge_manager):
        """Test basic tag suggestion fallback method."""
        # Test programming content
        result = knowledge_manager._generate_basic_tag_suggestions(
            "This function handles user authentication with secure password hashing",
            "Auth Function",
            [],
        )

        # Should suggest programming-related tags
        tag_names = [suggestion["tag"] for suggestion in result]
        assert "programming" in tag_names

        # All suggestions should have reasonable confidence
        for suggestion in result:
            assert suggestion["confidence"] >= 0.4
            assert "reason" in suggestion

    async def test_basic_tag_suggestions_fleeting_note(self, knowledge_manager):
        """Test basic tag suggestion for short content (fleeting note)."""
        # Test short content
        result = knowledge_manager._generate_basic_tag_suggestions(
            "Quick idea about project management", "Project Idea", []
        )

        # Should suggest fleeting-note for short content
        tag_names = [suggestion["tag"] for suggestion in result]
        assert "fleeting-note" in tag_names or "project" in tag_names

    async def test_basic_tag_suggestions_with_existing_tags(self, knowledge_manager):
        """Test basic tag suggestion respects existing tags."""
        existing_tags = ["programming", "project"]

        result = knowledge_manager._generate_basic_tag_suggestions(
            "This is a programming project with code functions", "Code Project", existing_tags
        )

        # Should not suggest already existing tags
        tag_names = [suggestion["tag"] for suggestion in result]
        assert "programming" not in tag_names
        assert "project" not in tag_names

    async def test_fallback_manager_integration(self, knowledge_manager, mock_fallback_manager):
        """Test that fallback manager is properly integrated."""
        # Verify fallback manager is set
        assert knowledge_manager.fallback_manager is mock_fallback_manager

        # Test service availability check
        mock_fallback_manager.is_service_available.return_value = True
        assert knowledge_manager.fallback_manager.is_service_available("test_service") is True

        mock_fallback_manager.is_service_available.return_value = False
        assert knowledge_manager.fallback_manager.is_service_available("test_service") is False
