"""Tests for PKMCog Discord commands."""

import asyncio
from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from src.nescordbot.cogs.pkm import PKMCog
from src.nescordbot.services import KnowledgeManager, SearchEngine, SearchFilters
from src.nescordbot.services.search_engine import SearchResult
from src.nescordbot.ui.pkm_embeds import PKMEmbed


class TestPKMCog:
    """Test cases for PKMCog."""

    @pytest.fixture
    def mock_bot(self) -> MagicMock:
        """Create mock Discord bot."""
        bot = MagicMock(spec=commands.Bot)
        bot.service_container = MagicMock()
        return bot

    @pytest.fixture
    def mock_knowledge_manager(self) -> AsyncMock:
        """Create mock KnowledgeManager."""
        mock_km = AsyncMock(spec=KnowledgeManager)

        # Mock note creation
        mock_km.create_note = AsyncMock(return_value="test_note_123")

        # Mock note listing
        mock_km.list_notes = AsyncMock(
            return_value=[
                {
                    "id": "note1",
                    "title": "First Note",
                    "content": "Content 1",
                    "content_type": "fleeting",
                    "tags": '["tag1", "tag2"]',
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                {
                    "id": "note2",
                    "title": "Second Note",
                    "content": "Content 2",
                    "content_type": "permanent",
                    "tags": '["tag3"]',
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
            ]
        )

        # Mock note by tag
        mock_km.get_notes_by_tag = AsyncMock(return_value=[])

        # Mock note retrieval
        mock_km.get_note = AsyncMock(
            return_value={
                "id": "test_note_123",
                "title": "Test Note",
                "content": "Test content",
                "content_type": "fleeting",
                "user_id": "123456789",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "tags": '["test"]',
            }
        )

        # Mock deletion
        mock_km.delete_note = AsyncMock(return_value=True)
        mock_km.initialize = AsyncMock()

        return mock_km

    @pytest.fixture
    def mock_search_engine(self) -> AsyncMock:
        """Create mock SearchEngine."""
        mock_se = AsyncMock(spec=SearchEngine)

        # Mock search results
        mock_results = [
            SearchResult(
                note_id="search_result_1",
                title="Search Result 1",
                content="Content that matches search",
                score=0.9,
                source="hybrid",
                metadata={"user_id": "123456789"},
                created_at=datetime.now(),
                relevance_reason="High similarity match",
            ),
            SearchResult(
                note_id="search_result_2",
                title="Search Result 2",
                content="Another matching content",
                score=0.7,
                source="hybrid",
                metadata={"user_id": "123456789"},
                created_at=datetime.now(),
                relevance_reason="Keyword match",
            ),
        ]

        mock_se.hybrid_search = AsyncMock(return_value=mock_results)

        return mock_se

    @pytest.fixture
    def pkm_cog(
        self, mock_bot: MagicMock, mock_knowledge_manager: AsyncMock, mock_search_engine: AsyncMock
    ) -> PKMCog:
        """Create PKMCog instance with mocked dependencies."""
        cog = PKMCog(mock_bot)
        cog.knowledge_manager = mock_knowledge_manager
        cog.search_engine = mock_search_engine
        cog._initialized = True
        return cog

    @pytest.fixture
    def mock_interaction(self) -> AsyncMock:
        """Create mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user.id = 123456789
        interaction.response.defer = AsyncMock()
        interaction.response.send_message = AsyncMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.mark.asyncio
    async def test_note_command_success(self, pkm_cog: PKMCog, mock_interaction: AsyncMock) -> None:
        """Test successful note creation."""
        # Execute command
        await pkm_cog.note_command.callback(
            pkm_cog,
            interaction=mock_interaction,
            title="Test Note",
            content="This is a test note content",
            tags="test,mock",
            note_type="fleeting",
        )

        # Verify defer was called
        mock_interaction.response.defer.assert_called_once()

        # Verify knowledge manager was called correctly
        pkm_cog.knowledge_manager.create_note.assert_called_once_with(
            title="Test Note",
            content="This is a test note content",
            tags=["test", "mock"],
            source_type="manual",
            user_id="123456789",
        )

        # Verify response was sent
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_note_command_invalid_tags(
        self, pkm_cog: PKMCog, mock_interaction: AsyncMock
    ) -> None:
        """Test note creation with invalid tags."""
        # Execute command with invalid tags
        await pkm_cog.note_command.callback(
            pkm_cog,
            interaction=mock_interaction,
            title="Test Note",
            content="Test content",
            tags="test,@invalid!tag",
            note_type="fleeting",
        )

        # Should send error response
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1]["embed"]
        assert "エラー" in embed.title

    @pytest.mark.asyncio
    async def test_search_command_success(
        self, pkm_cog: PKMCog, mock_interaction: AsyncMock
    ) -> None:
        """Test successful search operation."""
        # Execute command
        await pkm_cog.search_command.callback(
            pkm_cog,
            interaction=mock_interaction,
            query="test query",
            limit=5,
            note_type="all",
            min_score=0.1,
        )

        # Verify defer was called
        mock_interaction.response.defer.assert_called_once()

        # Verify search was performed
        pkm_cog.search_engine.hybrid_search.assert_called_once()
        call_args = pkm_cog.search_engine.hybrid_search.call_args
        assert call_args[1]["query"] == "test query"
        assert call_args[1]["limit"] == 5

        # Verify response was sent with view
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "view" in call_args[1]

    @pytest.mark.asyncio
    async def test_search_command_no_results(
        self, pkm_cog: PKMCog, mock_interaction: AsyncMock
    ) -> None:
        """Test search with no results."""
        # Mock empty search results
        pkm_cog.search_engine.hybrid_search = AsyncMock(return_value=[])

        # Execute command
        await pkm_cog.search_command.callback(
            pkm_cog, interaction=mock_interaction, query="nonexistent query", limit=5
        )

        # Should send warning message
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1]["embed"]
        assert "エラー" in embed.title

    @pytest.mark.asyncio
    async def test_list_command_success(self, pkm_cog: PKMCog, mock_interaction: AsyncMock) -> None:
        """Test successful note listing."""
        # Execute command
        await pkm_cog.list_command.callback(
            pkm_cog,
            interaction=mock_interaction,
            limit=10,
            sort="updated",
            note_type="all",
            tag=None,
        )

        # Verify defer was called
        mock_interaction.response.defer.assert_called_once()

        # Verify list was fetched
        pkm_cog.knowledge_manager.list_notes.assert_called_once()

        # Verify response was sent with view
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "view" in call_args[1]

    @pytest.mark.asyncio
    async def test_list_command_with_tag_filter(
        self, pkm_cog: PKMCog, mock_interaction: AsyncMock
    ) -> None:
        """Test note listing with tag filter."""
        # Mock tag-based results
        pkm_cog.knowledge_manager.get_notes_by_tag = AsyncMock(
            return_value=[
                {
                    "id": "tagged_note",
                    "title": "Tagged Note",
                    "content": "Content with tag",
                    "content_type": "fleeting",
                    "tags": '["specific_tag"]',
                }
            ]
        )

        # Execute command with tag filter
        await pkm_cog.list_command.callback(
            pkm_cog, interaction=mock_interaction, tag="specific_tag"
        )

        # Verify tag search was used
        pkm_cog.knowledge_manager.get_notes_by_tag.assert_called_once_with(
            "specific_tag", limit=20  # limit * 2
        )

    @pytest.mark.asyncio
    async def test_help_command(self, pkm_cog: PKMCog, mock_interaction: AsyncMock) -> None:
        """Test help command."""
        # Execute command
        await pkm_cog.help_command.callback(pkm_cog, mock_interaction)

        # Verify response was sent
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]
        assert "PKM" in embed.title
        assert "view" in call_args[1]

    @pytest.mark.asyncio
    async def test_service_initialization_error(
        self, mock_bot: MagicMock, mock_interaction: AsyncMock
    ) -> None:
        """Test error handling when service initialization fails."""
        # Create cog without services
        cog = PKMCog(mock_bot)

        # Mock service container to raise exception
        mock_bot.service_container = None

        # Execute command - should handle initialization error
        await cog.note_command.callback(
            cog, interaction=mock_interaction, title="Test", content="Test content"
        )

        # Should send error message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        embed = call_args[1]["embed"]
        assert "エラー" in embed.title

    @pytest.mark.asyncio
    async def test_command_timeout_handling(
        self, pkm_cog: PKMCog, mock_interaction: AsyncMock
    ) -> None:
        """Test timeout handling in commands."""
        # Mock timeout in knowledge manager
        pkm_cog.knowledge_manager.create_note = AsyncMock(
            side_effect=asyncio.TimeoutError("Operation timed out")
        )

        # Execute command
        await pkm_cog.note_command.callback(
            pkm_cog, interaction=mock_interaction, title="Test Note", content="Test content"
        )

        # Should send timeout error
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1]["embed"]
        assert "エラー" in embed.title

    @pytest.mark.asyncio
    async def test_knowledge_manager_error_handling(
        self, pkm_cog: PKMCog, mock_interaction: AsyncMock
    ) -> None:
        """Test KnowledgeManagerError handling."""
        # Mock KnowledgeManagerError
        from src.nescordbot.services import KnowledgeManagerError

        pkm_cog.knowledge_manager.create_note = AsyncMock(
            side_effect=KnowledgeManagerError("Database error")
        )

        # Execute command
        await pkm_cog.note_command.callback(
            pkm_cog, interaction=mock_interaction, title="Test Note", content="Test content"
        )

        # Should send appropriate error
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        embed = call_args[1]["embed"]
        assert "エラー" in embed.title


class TestPKMEmbeds:
    """Test cases for PKM embed formatting."""

    def test_note_created_embed(self) -> None:
        """Test note creation success embed."""
        created_at = datetime.now()
        embed = PKMEmbed.note_created(
            note_id="test123", title="Test Note", created_at=created_at, note_type="fleeting"
        )

        assert "ノート作成完了" in embed.title
        assert "Test Note" in embed.description
        assert embed.color == PKMEmbed.COLOR_SUCCESS
        assert len(embed.fields) == 3  # ID, Type, Created

    def test_search_results_embed(self) -> None:
        """Test search results embed."""
        results = [
            SearchResult(
                note_id="result1",
                title="Result 1",
                content="Content 1",
                score=0.9,
                source="hybrid",
                metadata={},
                created_at=datetime.now(),
                relevance_reason="Test match",
            )
        ]

        embed = PKMEmbed.search_results(
            results=results, query="test query", page=0, total_pages=1, total_results=1
        )

        assert "検索結果" in embed.title
        assert "test query" in embed.title
        # Check for actual result content in description
        assert "Result 1" in embed.description
        assert "Content 1" in embed.description

    def test_note_list_embed(self) -> None:
        """Test note list embed."""
        notes = [
            {
                "id": "note1",
                "title": "Note 1",
                "content_type": "fleeting",
                "tags": '["tag1"]',
                "updated_at": datetime.now().isoformat(),
            }
        ]

        embed = PKMEmbed.note_list(
            notes=notes, page=0, total_pages=1, total_notes=1, sort_by="updated", filter_type="all"
        )

        assert "ノート一覧" in embed.title
        # Check for actual note content in description (not count)
        assert "Note 1" in embed.description
        assert "fleeting" in embed.description

    def test_error_embed(self) -> None:
        """Test error embed formatting."""
        embed = PKMEmbed.error(message="Test error message", suggestion="Test suggestion")

        assert "エラー" in embed.title
        assert "Test error message" in embed.description
        assert embed.color == PKMEmbed.COLOR_ERROR
        assert len(embed.fields) == 1  # Solution field

    def test_error_embed_without_suggestion(self) -> None:
        """Test error embed without suggestion."""
        embed = PKMEmbed.error(message="Simple error")

        assert "エラー" in embed.title
        assert "Simple error" in embed.description
        assert len(embed.fields) == 0


class TestPKMViews:
    """Test cases for PKM UI views."""

    @pytest.fixture
    def mock_knowledge_manager(self) -> AsyncMock:
        """Create mock KnowledgeManager for views."""
        mock_km = AsyncMock()
        mock_km.delete_note = AsyncMock(return_value=True)
        mock_km.get_note = AsyncMock(
            return_value={"id": "test_note", "title": "Test Note", "content": "Test content"}
        )
        return mock_km

    def test_view_classes_importable(self) -> None:
        """Test that view classes can be imported."""
        from src.nescordbot.ui.pkm_embeds import PKMEmbed
        from src.nescordbot.ui.pkm_views import PKMListView, PKMNoteView, SearchResultView

        # Basic class verification
        assert PKMNoteView is not None
        assert SearchResultView is not None
        assert PKMListView is not None
        assert PKMEmbed is not None

    def test_embed_classes_work(self) -> None:
        """Test embed class methods work correctly."""
        from src.nescordbot.ui.pkm_embeds import PKMEmbed

        # Test basic embed creation
        embed = PKMEmbed.success("Test", "Test description")
        assert embed.title == "✅ Test"
        assert embed.description == "Test description"


class TestPKMIntegration:
    """Integration tests for PKM functionality."""

    @pytest.mark.asyncio
    async def test_full_note_creation_flow(self) -> None:
        """Test complete note creation flow."""
        # This would be an integration test with real services
        # For now, it's a placeholder for future implementation
        pass

    @pytest.mark.asyncio
    async def test_full_search_flow(self) -> None:
        """Test complete search flow."""
        # This would be an integration test with real services
        # For now, it's a placeholder for future implementation
        pass

    @pytest.mark.asyncio
    async def test_error_recovery_scenarios(self) -> None:
        """Test error recovery in various failure scenarios."""
        # This would test recovery from service failures
        # For now, it's a placeholder for future implementation
        pass
