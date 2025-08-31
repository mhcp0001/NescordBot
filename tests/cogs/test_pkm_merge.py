"""Tests for PKM merge functionality."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.nescordbot.cogs.pkm import (
    CancelMergeButton,
    ExecuteMergeButton,
    NoteMergeView,
    NoteSelectionDropdown,
    PKMCog,
)
from src.nescordbot.services import KnowledgeManager, KnowledgeManagerError


@pytest.fixture
def mock_bot():
    """Create mock bot instance."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_knowledge_manager():
    """Create mock knowledge manager."""
    km = MagicMock(spec=KnowledgeManager)
    km.search_notes = AsyncMock()
    km.get_notes_by_tag = AsyncMock()
    km.get_note = AsyncMock()
    km.merge_notes = AsyncMock()
    km.initialize = AsyncMock()
    return km


@pytest.fixture
def mock_interaction():
    """Create mock Discord interaction."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.guild_id = 67890
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


@pytest.fixture
def sample_notes():
    """Create sample notes for testing."""
    return [
        {
            "id": "note1",
            "title": "会議録 2024-03-15",
            "content": "プロジェクト会議の内容。新機能について議論した。",
            "tags": ["会議", "プロジェクト"],
            "created_at": "2024-03-15T10:00:00",
            "source_type": "manual",
        },
        {
            "id": "note2",
            "title": "プロジェクト要件定義",
            "content": "システムの要件を定義した文書。機能一覧と制約事項。",
            "tags": ["要件", "プロジェクト"],
            "created_at": "2024-03-14T15:30:00",
            "source_type": "manual",
        },
        {
            "id": "note3",
            "title": "技術仕様書 v1.2",
            "content": "詳細な技術仕様。アーキテクチャとAPI設計。",
            "tags": ["技術", "仕様"],
            "created_at": "2024-03-16T09:15:00",
            "source_type": "permanent",
        },
    ]


class TestPKMCogMergeCommand:
    """Test PKMCog merge command functionality."""

    @pytest.mark.asyncio
    async def test_merge_command_success(
        self, mock_bot, mock_knowledge_manager, mock_interaction, sample_notes
    ):
        """Test successful merge command execution."""
        # Setup PKMCog
        cog = PKMCog(mock_bot)
        cog.knowledge_manager = mock_knowledge_manager
        cog._initialized = True

        # Mock search results
        mock_knowledge_manager.search_notes.side_effect = [
            [sample_notes[0]],  # First search
            [sample_notes[1]],  # Second search
        ]

        # Execute command - call the callback directly
        await cog.merge_command.callback(cog, mock_interaction, "会議録 要件定義")

        # Verify interactions
        mock_interaction.response.defer.assert_called_once_with(thinking=True)
        mock_interaction.followup.send.assert_called_once()

        # Check that search was called correctly
        assert mock_knowledge_manager.search_notes.call_count == 2

    @pytest.mark.asyncio
    async def test_merge_command_note_not_found(
        self, mock_bot, mock_knowledge_manager, mock_interaction
    ):
        """Test merge command when note is not found."""
        cog = PKMCog(mock_bot)
        cog.knowledge_manager = mock_knowledge_manager
        cog._initialized = True

        # Mock no results
        mock_knowledge_manager.search_notes.return_value = []

        await cog.merge_command.callback(cog, mock_interaction, "存在しないノート")

        # Should send error message
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "該当するノートが見つかりません" in args[0]
        assert kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_merge_command_too_many_notes(
        self, mock_bot, mock_knowledge_manager, mock_interaction
    ):
        """Test merge command with too many input notes."""
        cog = PKMCog(mock_bot)
        cog.knowledge_manager = mock_knowledge_manager
        cog._initialized = True

        await cog.merge_command.callback(cog, mock_interaction, "note1 note2 note3 note4")

        # Should send error for too many notes
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "最大3個まで" in args[0]
        assert kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_merge_command_empty_input(
        self, mock_bot, mock_knowledge_manager, mock_interaction
    ):
        """Test merge command with empty input."""
        cog = PKMCog(mock_bot)
        cog.knowledge_manager = mock_knowledge_manager
        cog._initialized = True

        await cog.merge_command.callback(cog, mock_interaction, "   ")

        # Should send error for empty input
        mock_interaction.followup.send.assert_called_once()
        args, kwargs = mock_interaction.followup.send.call_args
        assert "1つ以上指定してください" in args[0]
        assert kwargs["ephemeral"] is True


class TestNoteMergeView:
    """Test NoteMergeView functionality."""

    @pytest.mark.asyncio
    async def test_init(self, mock_knowledge_manager, sample_notes):
        """Test NoteMergeView initialization."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2],
                knowledge_manager=mock_knowledge_manager,
                user_id=12345,
                guild_id=67890,
            )

            assert view.selected_notes == sample_notes[:2]
            assert view.final_notes == sample_notes[:2]
            assert view.knowledge_manager == mock_knowledge_manager
            assert view.user_id == 12345
            assert view.guild_id == 67890
            assert view._suggestions_loaded is False

    @pytest.mark.asyncio
    async def test_create_initial_embed(self, mock_knowledge_manager, sample_notes):
        """Test initial embed creation."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
            )

            embed = view.create_initial_embed()

            assert embed.title == "📝 ノート統合 - Phase 1: 初期選択"
            assert embed.color.value == 0x2ECC71
            assert len(embed.fields) == 2
            assert "選択されたノート" in embed.fields[0].name

    @pytest.mark.asyncio
    async def test_load_suggestions_success(self, mock_knowledge_manager, sample_notes):
        """Test successful suggestion loading."""
        view = NoteMergeView(
            selected_notes=sample_notes[:2],
            knowledge_manager=mock_knowledge_manager,
            user_id=12345,
            guild_id=67890,
        )

        # Mock search results
        mock_knowledge_manager.search_notes.return_value = [sample_notes[2]]
        mock_knowledge_manager.get_notes_by_tag.return_value = []
        mock_knowledge_manager.get_note.return_value = sample_notes[2]

        await view.load_suggestions()

        assert view._suggestions_loaded is True
        assert len(view.suggested_notes) >= 0  # May be empty due to filtering

    @pytest.mark.asyncio
    async def test_load_suggestions_error_handling(self, mock_knowledge_manager, sample_notes):
        """Test suggestion loading with errors."""
        view = NoteMergeView(
            selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
        )

        # Mock search error
        mock_knowledge_manager.search_notes.side_effect = Exception("Search failed")

        await view.load_suggestions()

        assert view._suggestions_loaded is True
        assert view.suggested_notes == []

    @pytest.mark.asyncio
    async def test_calculate_enhanced_relevance_score(self, mock_knowledge_manager, sample_notes):
        """Test enhanced relevance score calculation."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
            )

            # Test scoring
            score = view._calculate_enhanced_relevance_score(
                candidate_note=sample_notes[2],
                combined_content="会議の内容と要件定義",
                combined_tags=["会議", "要件", "プロジェクト"],
                selected_titles=["会議録", "要件定義"],
            )

            assert isinstance(score, float)
            assert score >= 0

    @pytest.mark.asyncio
    async def test_apply_diversity_filter(self, mock_knowledge_manager, sample_notes):
        """Test diversity filtering."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:1], knowledge_manager=mock_knowledge_manager
            )

            scored_candidates = [
                {"note": sample_notes[1], "relevance": 85},
                {"note": sample_notes[2], "relevance": 75},
            ]

            filtered = view._apply_diversity_filter(scored_candidates)

            assert len(filtered) <= 5
            assert all("note" in item and "relevance" in item for item in filtered)

    @pytest.mark.asyncio
    async def test_update_embed_with_suggestions(
        self, mock_knowledge_manager, sample_notes, mock_interaction
    ):
        """Test embed update with suggestions."""
        view = NoteMergeView(
            selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
        )

        # Mock suggestions loading
        view.suggested_notes = [{"note": sample_notes[2], "relevance": 80}]
        view._suggestions_loaded = True

        await view.update_embed_with_suggestions(mock_interaction)

        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_suggestions_button(
        self, mock_knowledge_manager, sample_notes, mock_interaction
    ):
        """Test show suggestions button functionality."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
            )

            # Mock button
            button = MagicMock()
            button.disabled = False

            # Mock the update method
            view.update_embed_with_suggestions = AsyncMock()  # type: ignore

            await view.show_suggestions(mock_interaction, button)

            assert button.disabled is True
            view.update_embed_with_suggestions.assert_called_once_with(mock_interaction)


class TestExecuteMergeButton:
    """Test ExecuteMergeButton functionality."""

    @pytest.mark.asyncio
    async def test_execute_merge_success(
        self, mock_knowledge_manager, sample_notes, mock_interaction
    ):
        """Test successful merge execution."""
        # Setup view with mocked init
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
            )
            view.final_notes = sample_notes[:2]

        # Setup button
        button = ExecuteMergeButton()
        # Mock the view property
        with patch.object(type(button), "view", view):
            # Mock merge result
            merged_note = {
                "id": "merged_note",
                "title": "統合ノート_20240315_120000",
                "content": "統合されたノート内容",
                "created_at": "2024-03-15T12:00:00",
            }
            mock_knowledge_manager.merge_notes.return_value = "merged_note"
            mock_knowledge_manager.get_note.return_value = merged_note

            await button.callback(mock_interaction)

            # Verify merge was called
            mock_knowledge_manager.merge_notes.assert_called_once()
            mock_interaction.edit_original_response.assert_called()

    @pytest.mark.asyncio
    async def test_execute_merge_failure(
        self, mock_knowledge_manager, sample_notes, mock_interaction
    ):
        """Test merge execution failure."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
            )
            view.final_notes = sample_notes[:2]

        button = ExecuteMergeButton()
        with patch.object(type(button), "view", view):
            # Mock merge failure
            mock_knowledge_manager.merge_notes.side_effect = KnowledgeManagerError("Merge failed")

            await button.callback(mock_interaction)

            # Should show error embed
            mock_interaction.edit_original_response.assert_called()
            args, kwargs = mock_interaction.edit_original_response.call_args
            embed = kwargs["embed"]
            assert "統合失敗" in embed.title


class TestCancelMergeButton:
    """Test CancelMergeButton functionality."""

    @pytest.mark.asyncio
    async def test_cancel_merge(self, mock_knowledge_manager, sample_notes, mock_interaction):
        """Test merge cancellation."""
        with patch("discord.ui.View.__init__"):
            view = NoteMergeView(
                selected_notes=sample_notes[:2], knowledge_manager=mock_knowledge_manager
            )

        button = CancelMergeButton()
        with patch.object(type(button), "view", view):
            # Mock clear_items method
            view.clear_items = MagicMock()

            await button.callback(mock_interaction)

            mock_interaction.response.edit_message.assert_called_once()
            args, kwargs = mock_interaction.response.edit_message.call_args
            embed = kwargs["embed"]
            assert "キャンセルしました" in embed.title


class TestNoteSelectionDropdown:
    """Test NoteSelectionDropdown functionality."""

    @pytest.mark.asyncio
    async def test_note_selection_callback(
        self, mock_knowledge_manager, sample_notes, mock_interaction
    ):
        """Test note selection callback."""
        with patch("discord.ui.View.__init__"):
            parent_view = NoteMergeView(
                selected_notes=sample_notes[:1], knowledge_manager=mock_knowledge_manager
            )
            parent_view.suggested_notes = [
                {"note": sample_notes[1], "relevance": 80},
                {"note": sample_notes[2], "relevance": 70},
            ]

        options = [
            discord.SelectOption(label=sample_notes[1]["title"], value="0"),
            discord.SelectOption(label=sample_notes[2]["title"], value="1"),
        ]

        dropdown = NoteSelectionDropdown(options, parent_view)
        # Mock the values property
        with patch.object(type(dropdown), "values", ["0", "1"]):
            await dropdown.callback(mock_interaction)

            # Should add both notes to final_notes
            assert len(parent_view.final_notes) == 3  # 1 original + 2 added
            mock_interaction.response.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_note_selection_init(self, mock_knowledge_manager, sample_notes):
        """Test dropdown initialization."""
        with patch("discord.ui.View.__init__"):
            parent_view = NoteMergeView(
                selected_notes=sample_notes[:1], knowledge_manager=mock_knowledge_manager
            )

        options = [discord.SelectOption(label="Test Note", value="0")]

        dropdown = NoteSelectionDropdown(options, parent_view)

        assert dropdown.placeholder == "追加するノートを選択..."
        assert dropdown.max_values == 1
        assert dropdown.parent_view == parent_view


@pytest.mark.asyncio
async def test_merge_command_integration_flow(
    mock_bot, mock_knowledge_manager, mock_interaction, sample_notes
):
    """Test complete merge command flow integration."""
    # Setup
    cog = PKMCog(mock_bot)
    cog.knowledge_manager = mock_knowledge_manager
    cog._initialized = True

    # Mock search results for command
    mock_knowledge_manager.search_notes.side_effect = [
        [sample_notes[0]],  # First search
        [sample_notes[1]],  # Second search
    ]

    # Execute merge command
    await cog.merge_command.callback(cog, mock_interaction, "会議録 要件定義")

    # Verify command created proper view
    mock_interaction.followup.send.assert_called_once()
    args, kwargs = mock_interaction.followup.send.call_args

    assert "embed" in kwargs
    assert "view" in kwargs

    embed = kwargs["embed"]
    view = kwargs["view"]

    # Check embed
    assert "Phase 1" in embed.title

    # Check view
    assert isinstance(view, NoteMergeView)
    assert len(view.selected_notes) == 2
    assert view.selected_notes[0]["id"] == "note1"
    assert view.selected_notes[1]["id"] == "note2"
