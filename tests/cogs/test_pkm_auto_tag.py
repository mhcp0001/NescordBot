"""
Test cases for PKM Cog Auto-Tag functionality (Issue #110).

Tests cover:
- /auto-tag command with different modes
- Tag suggestion functionality
- Auto-application logic
- Batch processing capabilities
- Error handling and edge cases
"""

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest
from discord.ext import commands

from src.nescordbot.cogs.pkm import PKMCog
from src.nescordbot.config import BotConfig


@pytest.fixture
def mock_bot():
    """Mock Discord bot instance"""
    bot = Mock(spec=commands.Bot)
    bot.user = Mock()
    bot.user.id = 12345
    return bot


@pytest.fixture
def mock_config():
    """Mock bot configuration"""
    config = Mock(spec=BotConfig)
    config.gemini_api_key = "test_gemini_key"
    return config


@pytest.fixture
def mock_knowledge_manager():
    """Mock KnowledgeManager with auto-tag methods"""
    km = AsyncMock()

    # Mock suggest_tags_for_content
    km.suggest_tags_for_content.return_value = [
        {
            "tag": "プロジェクト管理",
            "confidence": 0.9,
            "reason": "プロジェクト管理に関する内容が含まれています",
            "existing": True,
        },
        {"tag": "技術仕様", "confidence": 0.7, "reason": "技術的な仕様について詳しく記述されています", "existing": False},
    ]

    # Mock auto_categorize_notes
    km.auto_categorize_notes.return_value = {
        "processed": 10,
        "categorized": 5,
        "errors": [],
        "categories": {
            "note1": {"added_tags": ["AI", "開発"], "suggestions": []},
            "note2": {"added_tags": ["データベース"], "suggestions": []},
        },
    }

    # Mock get_note
    km.get_note.return_value = {
        "id": "test_note_1",
        "title": "テストノート",
        "content": "これはテスト用のノート内容です。プロジェクト管理について説明しています。",
        "tags": ["既存タグ"],
        "created_at": "2025-08-31T10:00:00Z",
    }

    # Mock update_note
    km.update_note.return_value = None

    # Mock list_notes
    km.list_notes.return_value = [
        {"id": "sample1", "title": "サンプルノート1", "content": "AI技術について", "tags": []},
        {"id": "sample2", "title": "サンプルノート2", "content": "データベース設計の基礎", "tags": ["データベース"]},
    ]

    return km


@pytest.fixture
def mock_search_engine():
    """Mock SearchEngine"""
    return AsyncMock()


@pytest.fixture
async def pkm_cog(mock_bot, mock_knowledge_manager, mock_search_engine):
    """PKMCog instance with mocked dependencies"""
    cog = PKMCog(mock_bot)
    cog.knowledge_manager = mock_knowledge_manager
    cog.search_engine = mock_search_engine
    cog._initialized = True

    return cog


class TestAutoTagCommand:
    """Test cases for the /auto-tag command"""

    @pytest.mark.asyncio
    async def test_auto_tag_suggest_mode_with_note_id(self, pkm_cog, mock_knowledge_manager):
        """Test auto-tag suggest mode for specific note"""
        # Mock Discord interaction
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Execute command callback directly
        await pkm_cog.auto_tag_command.callback(
            pkm_cog,
            interaction=interaction,
            mode="suggest",
            note_id="test_note_1",
            max_suggestions=5,
            confidence_threshold=0.8,
        )

        # Verify API calls
        interaction.response.defer.assert_called_once()
        mock_knowledge_manager.get_note.assert_called_once_with("test_note_1")
        mock_knowledge_manager.suggest_tags_for_content.assert_called_once()

        # Verify response sent
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        assert "embed" in call_args.kwargs

        embed = call_args.kwargs["embed"]
        assert "AIタグ提案" in embed.title
        assert "テストノート" in embed.description

    @pytest.mark.asyncio
    async def test_auto_tag_suggest_mode_sample(self, pkm_cog, mock_knowledge_manager):
        """Test auto-tag suggest mode without specific note (sample mode)"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Execute command without note_id
        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="suggest", note_id="", max_suggestions=3
        )

        # Verify sample notes fetched
        mock_knowledge_manager.list_notes.assert_called_once_with(limit=5)

        # Verify tag suggestions called for sample notes
        assert mock_knowledge_manager.suggest_tags_for_content.call_count >= 1

        # Verify embeds sent
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        assert "embeds" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_auto_tag_apply_mode(self, pkm_cog, mock_knowledge_manager):
        """Test auto-tag apply mode with confidence threshold"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Execute apply mode
        await pkm_cog.auto_tag_command.callback(
            pkm_cog,
            interaction=interaction,
            mode="apply",
            note_id="test_note_1",
            confidence_threshold=0.8,
        )

        # Verify high-confidence tag applied
        mock_knowledge_manager.update_note.assert_called_once()
        call_args = mock_knowledge_manager.update_note.call_args
        assert call_args.kwargs["note_id"] == "test_note_1"

        # High confidence tag (0.9) should be applied
        updated_tags = call_args.kwargs["tags"]
        assert "プロジェクト管理" in updated_tags
        assert "既存タグ" in updated_tags  # Existing tag preserved

        # Verify success response
        interaction.followup.send.assert_called_once()
        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "タグ自動適用完了" in embed.title

    @pytest.mark.asyncio
    async def test_auto_tag_apply_no_high_confidence_tags(self, pkm_cog, mock_knowledge_manager):
        """Test apply mode when no tags meet confidence threshold"""
        # Mock low confidence suggestions only
        mock_knowledge_manager.suggest_tags_for_content.return_value = [
            {"tag": "低信頼度タグ", "confidence": 0.5, "reason": "信頼度が低い提案", "existing": False}
        ]

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        await pkm_cog.auto_tag_command.callback(
            pkm_cog,
            interaction=interaction,
            mode="apply",
            note_id="test_note_1",
            confidence_threshold=0.8,
        )

        # Should not update note
        mock_knowledge_manager.update_note.assert_not_called()

        # Should send "no applicable tags" message
        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "適用可能なタグなし" in embed.title

    @pytest.mark.asyncio
    async def test_auto_tag_batch_mode(self, pkm_cog, mock_knowledge_manager):
        """Test batch processing mode"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock progress message
        progress_message = AsyncMock()
        interaction.followup.send.return_value = progress_message

        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="batch", confidence_threshold=0.8
        )

        # Verify batch processing called
        mock_knowledge_manager.auto_categorize_notes.assert_called_once()
        call_args = mock_knowledge_manager.auto_categorize_notes.call_args
        assert call_args.kwargs["batch_size"] == 5
        assert "progress_callback" in call_args.kwargs

        # Verify progress and final messages
        assert interaction.followup.send.call_count == 1
        progress_message.edit.assert_called()  # Final result edit

    @pytest.mark.asyncio
    async def test_auto_tag_parameter_validation(self, pkm_cog):
        """Test parameter validation for auto-tag command"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Test invalid max_suggestions
        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="suggest", max_suggestions=15  # > 10
        )

        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        # Could be positional or keyword argument
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "1-10 の範囲" in content

        # Reset mocks
        interaction.followup.send.reset_mock()

        # Test invalid confidence_threshold
        await pkm_cog.auto_tag_command.callback(
            pkm_cog,
            interaction=interaction,
            mode="apply",
            note_id="test",
            confidence_threshold=1.5,  # > 1.0
        )

        call_args = interaction.followup.send.call_args
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "0.1-1.0 の範囲" in content

    @pytest.mark.asyncio
    async def test_auto_tag_apply_without_note_id(self, pkm_cog):
        """Test apply mode requires note_id"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="apply", note_id=""  # Empty note_id
        )

        call_args = interaction.followup.send.call_args
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "note_id の指定が必要" in content

    @pytest.mark.asyncio
    async def test_auto_tag_note_not_found(self, pkm_cog, mock_knowledge_manager):
        """Test handling when specified note is not found"""
        # Mock get_note to return None
        mock_knowledge_manager.get_note.return_value = None

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="suggest", note_id="nonexistent_note"
        )

        call_args = interaction.followup.send.call_args
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "が見つかりません" in content

    @pytest.mark.asyncio
    async def test_auto_tag_service_not_initialized(self, pkm_cog):
        """Test error handling when services not initialized"""
        pkm_cog._initialized = False

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()

        await pkm_cog.auto_tag_command.callback(pkm_cog, interaction=interaction, mode="suggest")

        interaction.response.send_message.assert_called_once()
        call_args = interaction.response.send_message.call_args
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "初期化されていません" in content
        assert call_args.kwargs.get("ephemeral") is True

    @pytest.mark.asyncio
    async def test_auto_tag_exception_handling(self, pkm_cog, mock_knowledge_manager):
        """Test exception handling in auto-tag command"""
        # Make knowledge_manager raise exception
        mock_knowledge_manager.suggest_tags_for_content.side_effect = Exception("Test error")

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.response.is_done.return_value = True  # Mock as already responded
        interaction.followup = AsyncMock()

        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="suggest", note_id="test_note_1"
        )

        # Should send error message
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "エラーが発生しました" in content


class TestAutoTagHelpers:
    """Test cases for auto-tag helper methods"""

    @pytest.mark.asyncio
    async def test_handle_tag_suggestion_no_suggestions(self, pkm_cog, mock_knowledge_manager):
        """Test handling when no tag suggestions are returned"""
        # Mock empty suggestions
        mock_knowledge_manager.suggest_tags_for_content.return_value = []

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.followup = AsyncMock()

        note = {"id": "test", "title": "Test Note", "content": "Content", "tags": []}

        await pkm_cog._send_tag_suggestions_response(interaction, note, [])

        embed = interaction.followup.send.call_args.kwargs["embed"]
        assert "提案できるタグがありませんでした" in embed.description

    @pytest.mark.asyncio
    async def test_batch_progress_callback(self, pkm_cog, mock_knowledge_manager):
        """Test progress callback functionality in batch mode"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        progress_message = AsyncMock()
        interaction.followup.send.return_value = progress_message

        # Capture progress callback
        progress_callback = None

        def capture_callback(*args, **kwargs):
            nonlocal progress_callback
            progress_callback = kwargs.get("progress_callback")
            return {"processed": 20, "categorized": 10, "errors": [], "categories": {}}

        mock_knowledge_manager.auto_categorize_notes.side_effect = capture_callback

        await pkm_cog._handle_batch_tagging(
            interaction, max_suggestions=5, confidence_threshold=0.8
        )

        # Test progress callback
        assert progress_callback is not None
        progress_callback(10, 20)  # Callback is synchronous, not async

        # Verify progress message was edited
        progress_message.edit.assert_called()


class TestAutoTagIntegration:
    """Integration test cases"""

    @pytest.mark.asyncio
    async def test_auto_tag_full_workflow_suggest_to_apply(self, pkm_cog, mock_knowledge_manager):
        """Test complete workflow: suggest → apply tags"""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Step 1: Get suggestions
        await pkm_cog.auto_tag_command.callback(
            pkm_cog, interaction=interaction, mode="suggest", note_id="test_note_1"
        )

        # Reset mocks for step 2
        interaction.followup.send.reset_mock()
        mock_knowledge_manager.update_note.reset_mock()

        # Step 2: Apply high-confidence tags
        await pkm_cog.auto_tag_command.callback(
            pkm_cog,
            interaction=interaction,
            mode="apply",
            note_id="test_note_1",
            confidence_threshold=0.8,
        )

        # Verify tag was applied
        mock_knowledge_manager.update_note.assert_called_once()
        applied_tags = mock_knowledge_manager.update_note.call_args.kwargs["tags"]
        assert "プロジェクト管理" in applied_tags  # High confidence tag

    @pytest.mark.asyncio
    async def test_auto_tag_batch_with_errors(self, pkm_cog, mock_knowledge_manager):
        """Test batch processing with some errors"""
        # Mock batch processing with errors
        mock_knowledge_manager.auto_categorize_notes.return_value = {
            "processed": 10,
            "categorized": 7,
            "errors": [
                "Error processing note 1: API timeout",
                "Error processing note 5: Invalid content",
            ],
            "categories": {"note2": {"added_tags": ["AI"], "suggestions": []}},
        }

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        progress_message = AsyncMock()
        interaction.followup.send.return_value = progress_message

        await pkm_cog.auto_tag_command.callback(pkm_cog, interaction=interaction, mode="batch")

        # Verify error handling in result
        final_embed = progress_message.edit.call_args.kwargs["embed"]
        assert final_embed.color.value == 0xFFA500  # Warning color for errors

        # Check error field is present
        error_field = None
        for field in final_embed.fields:
            if "エラー詳細" in field.name:
                error_field = field
                break

        assert error_field is not None
        assert "API timeout" in error_field.value
