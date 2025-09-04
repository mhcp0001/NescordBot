"""Tests for PKM edit UI components."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.nescordbot.ui.pkm_views import (
    EditNoteModal,
    EditNoteResultView,
    EditNoteSelectionView,
    NoteDiffModal,
    NoteHistoryView,
)


class TestEditNoteModal:
    """Test EditNoteModal component."""

    @pytest.fixture
    def mock_knowledge_manager(self):
        """Mock KnowledgeManager."""
        km = AsyncMock()
        km.update_note.return_value = True
        return km

    @pytest.fixture
    def mock_interaction(self):
        """Mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user.id = "123456789"
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        return interaction

    @pytest.fixture
    def note_data(self):
        """Sample note data."""
        return {
            "id": "test-note-1",
            "title": "Test Note",
            "content": "Test content",
            "tags": ["test", "note"],
        }

    def test_modal_initialization(self, note_data, mock_knowledge_manager):
        """Test modal initialization."""
        modal = EditNoteModal(note_data, mock_knowledge_manager)

        assert modal.title == "ノートを編集"
        assert modal.title_input.default == note_data["title"]
        assert modal.content_input.default == note_data["content"]
        assert modal.tags_input.default == "test, note"

    @pytest.mark.asyncio
    async def test_on_submit_success(self, note_data, mock_knowledge_manager, mock_interaction):
        """Test successful modal submission."""
        modal = EditNoteModal(note_data, mock_knowledge_manager)

        # Set input values
        modal.title_input.value = "Updated Title"
        modal.content_input.value = "Updated content"
        modal.tags_input.value = "updated, test"

        await modal.on_submit(mock_interaction)

        # Verify update_note was called correctly
        mock_knowledge_manager.update_note.assert_called_once_with(
            note_id="test-note-1",
            title="Updated Title",
            content="Updated content",
            tags=["updated", "test"],
            user_id="123456789",
        )

        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_submit_failure(self, note_data, mock_knowledge_manager, mock_interaction):
        """Test modal submission failure."""
        mock_knowledge_manager.update_note.return_value = False
        modal = EditNoteModal(note_data, mock_knowledge_manager)

        modal.title_input.value = "Updated Title"
        modal.content_input.value = "Updated content"
        modal.tags_input.value = ""

        await modal.on_submit(mock_interaction)

        # Verify error response
        call_args = mock_interaction.followup.send.call_args
        assert call_args[1]["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_on_submit_exception(self, note_data, mock_knowledge_manager, mock_interaction):
        """Test modal submission with exception."""
        mock_knowledge_manager.update_note.side_effect = Exception("Test error")
        modal = EditNoteModal(note_data, mock_knowledge_manager)

        modal.title_input.value = "Updated Title"
        modal.content_input.value = "Updated content"
        modal.tags_input.value = ""

        await modal.on_submit(mock_interaction)

        # Verify error response
        call_args = mock_interaction.followup.send.call_args
        assert call_args[1]["ephemeral"] is True


class TestEditNoteResultView:
    """Test EditNoteResultView component."""

    @pytest.fixture
    def mock_knowledge_manager(self):
        """Mock KnowledgeManager."""
        km = AsyncMock()
        km.get_note_history.return_value = [
            {
                "id": 1,
                "user_id": "123456789",
                "timestamp": "2023-12-01T10:00:00",
                "edit_type": "update",
                "changes": {
                    "title": {"before": "Old Title", "after": "New Title", "changed": True},
                    "content": {"before_lines": 5, "after_lines": 7, "diff": [], "changed": True},
                },
            }
        ]
        return km

    @pytest.fixture
    def mock_interaction(self):
        """Mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        return interaction

    def test_view_initialization(self, mock_knowledge_manager):
        """Test view initialization."""
        view = EditNoteResultView("test-note-1", mock_knowledge_manager)

        assert view.note_id == "test-note-1"
        assert view.km == mock_knowledge_manager
        assert view.timeout == 300

    @pytest.mark.asyncio
    async def test_show_history_success(self, mock_knowledge_manager, mock_interaction):
        """Test showing history successfully."""
        view = EditNoteResultView("test-note-1", mock_knowledge_manager)
        button = MagicMock()

        await view.show_history(mock_interaction, button)

        # Verify history was fetched
        mock_knowledge_manager.get_note_history.assert_called_once_with("test-note-1", limit=10)

        # Verify response
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_history_empty(self, mock_knowledge_manager, mock_interaction):
        """Test showing history when no history exists."""
        mock_knowledge_manager.get_note_history.return_value = []
        view = EditNoteResultView("test-note-1", mock_knowledge_manager)
        button = MagicMock()

        await view.show_history(mock_interaction, button)

        # Verify no history response
        call_args = mock_interaction.followup.send.call_args
        assert call_args[1]["ephemeral"] is True
        embed = call_args[1]["embed"]
        assert "履歴がありません" in embed.title

    @pytest.mark.asyncio
    async def test_show_history_exception(self, mock_knowledge_manager, mock_interaction):
        """Test showing history with exception."""
        mock_knowledge_manager.get_note_history.side_effect = Exception("Test error")
        view = EditNoteResultView("test-note-1", mock_knowledge_manager)
        button = MagicMock()

        await view.show_history(mock_interaction, button)

        # Verify error response
        call_args = mock_interaction.followup.send.call_args
        assert call_args[1]["ephemeral"] is True


class TestNoteHistoryView:
    """Test NoteHistoryView component."""

    @pytest.fixture
    def sample_history(self):
        """Sample history data."""
        return [
            {
                "id": 1,
                "user_id": "123456789",
                "timestamp": "2023-12-01T10:00:00",
                "edit_type": "update",
                "changes": {"title": {"before": "Title 1", "after": "Title 2", "changed": True}},
            },
            {
                "id": 2,
                "user_id": "987654321",
                "timestamp": "2023-12-01T09:00:00",
                "edit_type": "update",
                "changes": {
                    "content": {"before_lines": 3, "after_lines": 5, "diff": [], "changed": True}
                },
            },
        ]

    @pytest.fixture
    def mock_knowledge_manager(self):
        """Mock KnowledgeManager."""
        return AsyncMock()

    def test_view_initialization(self, sample_history, mock_knowledge_manager):
        """Test view initialization."""
        view = NoteHistoryView("test-note-1", sample_history, mock_knowledge_manager)

        assert view.note_id == "test-note-1"
        assert view.history == sample_history
        assert view.current_index == 0
        assert view.prev_button.disabled is True
        assert view.next_button.disabled is False

    def test_button_states_single_item(self, mock_knowledge_manager):
        """Test button states with single history item."""
        history = [
            {
                "id": 1,
                "user_id": "123",
                "timestamp": "2023-12-01T10:00:00",
                "edit_type": "update",
                "changes": {},
            }
        ]
        view = NoteHistoryView("test-note-1", history, mock_knowledge_manager)

        assert view.prev_button.disabled is True
        assert view.next_button.disabled is True

    @pytest.mark.asyncio
    async def test_next_button(self, sample_history, mock_knowledge_manager):
        """Test next button functionality."""
        view = NoteHistoryView("test-note-1", sample_history, mock_knowledge_manager)
        mock_interaction = AsyncMock(spec=discord.Interaction)
        button = MagicMock()

        await view.next_button(mock_interaction, button)

        assert view.current_index == 1
        mock_interaction.response.edit_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_prev_button(self, sample_history, mock_knowledge_manager):
        """Test previous button functionality."""
        view = NoteHistoryView("test-note-1", sample_history, mock_knowledge_manager)
        view.current_index = 1  # Start at second item
        view._update_buttons()

        mock_interaction = AsyncMock(spec=discord.Interaction)
        button = MagicMock()

        await view.prev_button(mock_interaction, button)

        assert view.current_index == 0
        mock_interaction.response.edit_message.assert_called_once()


class TestNoteDiffModal:
    """Test NoteDiffModal component."""

    @pytest.fixture
    def sample_history_item(self):
        """Sample history item with changes."""
        return {
            "id": 1,
            "user_id": "123456789",
            "timestamp": "2023-12-01T10:00:00",
            "edit_type": "update",
            "changes": {
                "title": {"before": "Old Title", "after": "New Title", "changed": True},
                "content": {
                    "before_lines": 3,
                    "after_lines": 5,
                    "diff": ["- Old line", "+ New line"],
                    "changed": True,
                },
                "tags": {"added": ["new_tag"], "removed": ["old_tag"], "changed": True},
            },
        }

    def test_modal_initialization(self, sample_history_item):
        """Test modal initialization."""
        modal = NoteDiffModal(sample_history_item)

        assert modal.title == "詳細な差分表示"
        assert len(modal.diff_display.default) > 0

    def test_create_diff_text_all_changes(self, sample_history_item):
        """Test diff text creation with all change types."""
        modal = NoteDiffModal(sample_history_item)
        changes = sample_history_item["changes"]

        diff_text = modal._create_diff_text(changes)

        assert "=== タイトル変更 ===" in diff_text
        assert "Old Title" in diff_text
        assert "New Title" in diff_text
        assert "=== 内容変更 ===" in diff_text
        assert "=== タグ変更 ===" in diff_text
        assert "new_tag" in diff_text
        assert "old_tag" in diff_text

    def test_create_diff_text_title_only(self):
        """Test diff text creation with title change only."""
        changes = {"title": {"before": "Old", "after": "New", "changed": True}}
        modal = NoteDiffModal({"changes": changes})

        diff_text = modal._create_diff_text(changes)

        assert "=== タイトル変更 ===" in diff_text
        assert "=== 内容変更 ===" not in diff_text
        assert "=== タグ変更 ===" not in diff_text

    @pytest.mark.asyncio
    async def test_on_submit(self, sample_history_item):
        """Test modal submission."""
        modal = NoteDiffModal(sample_history_item)
        mock_interaction = AsyncMock(spec=discord.Interaction)

        await modal.on_submit(mock_interaction)

        mock_interaction.response.defer.assert_called_once()
