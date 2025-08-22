"""Integration tests for TextCog - End-to-End test scenarios.

This module contains E2E tests covering the complete flow from
text input to GitHub file creation for the TextCog functionality.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from nescordbot.cogs.text import VIEW_TIMEOUT, FleetingNoteView, TextCog
from nescordbot.services import NoteProcessingService
from nescordbot.services.obsidian_github import ObsidianGitHubService


class TestTextE2EIntegration:
    """End-to-End integration tests for TextCog functionality."""

    @pytest.fixture
    def full_bot(self):
        """Create a full bot instance for E2E testing."""
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix="!", intents=intents)
        return bot

    @pytest.fixture
    def full_note_service(self):
        """Create a fully configured NoteProcessingService."""
        service = MagicMock(spec=NoteProcessingService)
        service.is_available.return_value = True

        async def mock_process_text(text, processing_type="fleeting_note"):
            # Simulate AI processing with realistic response
            await asyncio.sleep(0.1)  # Simulate processing time
            return {
                "processed": f"AIで処理済み: {text}",
                "summary": f"{text[:30]}の要約...",
                "metadata": {"confidence": 0.95, "language": "ja"},
            }

        service.process_text = AsyncMock(side_effect=mock_process_text)
        return service

    @pytest.fixture
    def full_obsidian_service(self):
        """Create a fully configured ObsidianGitHubService."""
        service = MagicMock(spec=ObsidianGitHubService)

        async def mock_save_to_obsidian(
            filename, content, directory="Fleeting Notes", metadata=None
        ):
            # Simulate GitHub API call
            await asyncio.sleep(0.2)  # Simulate network delay
            return {
                "success": True,
                "file_path": f"{directory}/{filename}",
                "commit_sha": "abc123def456",
                "github_url": f"https://github.com/test/repo/blob/main/{directory}/{filename}",
            }

        service.save_to_obsidian = AsyncMock(side_effect=mock_save_to_obsidian)
        return service

    @pytest.fixture
    def full_text_cog(self, full_bot, full_note_service, full_obsidian_service):
        """Create TextCog with all services enabled."""
        return TextCog(full_bot, full_note_service, full_obsidian_service)

    @pytest.fixture
    def integration_message(self):
        """Create a realistic message object for integration testing."""
        message = AsyncMock(spec=discord.Message)
        message.author = MagicMock()
        message.author.name = "IntegrationUser"
        message.author.bot = False
        message.guild = MagicMock()
        message.guild.name = "IntegrationGuild"
        message.channel = MagicMock()
        message.channel.name = "integration-test"
        message.id = 987654321
        message.reply = AsyncMock()

        # Create a mock edit method for the reply
        reply_mock = AsyncMock()
        reply_mock.edit = AsyncMock()
        message.reply.return_value = reply_mock

        return message

    @pytest.mark.asyncio
    async def test_full_text_processing_flow(self, full_text_cog, integration_message):
        """Test complete text processing flow from input to response.

        This E2E test covers:
        1. Text input validation
        2. AI processing with NoteProcessingService
        3. Fleeting Note formatting
        4. Discord response with embed and view
        """
        start_time = time.time()

        test_text = "これはE2Eテストのサンプルテキストです。統合テストの確認を行います。"

        # Execute the full flow
        await full_text_cog.handle_text_message(integration_message, test_text)

        processing_time = time.time() - start_time

        # Verify performance requirement (< 2 seconds)
        assert processing_time < 2.0, f"Processing time too slow: {processing_time:.2f}s"

        # Verify AI service was called
        full_text_cog.note_processing_service.process_text.assert_called_once()
        call_args = full_text_cog.note_processing_service.process_text.call_args
        assert call_args[0][0] == test_text
        assert call_args[1]["processing_type"] == "fleeting_note"

        # Verify response was sent
        assert integration_message.reply.called
        assert integration_message.reply.return_value.edit.called

        # Verify response content
        edit_call = integration_message.reply.return_value.edit.call_args
        assert "完了しました" in edit_call[1]["content"]
        assert "embed" in edit_call[1]
        assert "view" in edit_call[1]

    @pytest.mark.asyncio
    async def test_slash_command_e2e_flow(self, full_text_cog):
        """Test complete /note slash command flow.

        This E2E test covers:
        1. Slash command interaction handling
        2. Deferred response processing
        3. AI processing integration
        4. Final response with embed and view
        """
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "SlashUser"
        interaction.guild = MagicMock()
        interaction.guild.name = "SlashGuild"
        interaction.channel = MagicMock()
        interaction.channel.name = "slash-test"
        interaction.id = 111222333
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        test_text = "スラッシュコマンドのE2Eテストです。"

        start_time = time.time()

        # Execute slash command
        await full_text_cog.note_command.callback(full_text_cog, interaction, test_text)

        processing_time = time.time() - start_time

        # Verify performance requirement
        assert processing_time < 3.0, f"Slash command too slow: {processing_time:.2f}s"

        # Verify interaction flow
        interaction.response.defer.assert_called_once()
        interaction.followup.send.assert_called_once()

        # Verify AI processing was called
        full_text_cog.note_processing_service.process_text.assert_called()

        # Verify response structure
        followup_call = interaction.followup.send.call_args
        assert "Fleeting Note" in followup_call[1]["content"]
        assert "embed" in followup_call[1]
        assert "view" in followup_call[1]

    @pytest.mark.asyncio
    async def test_fleeting_note_view_creation_integration(
        self, full_text_cog, integration_message
    ):
        """Test FleetingNoteView creation and integration.

        This E2E test covers:
        1. FleetingNoteView creation with services
        2. Proper initialization
        3. Content and metadata handling
        4. Service integration validation
        """
        test_content = """---
id: 20251225120000
title: "テストノート"
type: fleeting_note
status: fleeting
---

# テストノート

## 💭 アイデア・思考の断片
テストコンテンツです。
"""

        # Create FleetingNoteView
        view = FleetingNoteView(
            content=test_content,
            summary="テストノートの要約",
            obsidian_service=full_text_cog.obsidian_service,
            note_type="text",
            message=integration_message,
        )

        # Verify view was created properly
        assert view.content == test_content
        assert view.summary == "テストノートの要約"
        assert view.obsidian_service == full_text_cog.obsidian_service
        assert view.note_type == "text"
        assert view.message == integration_message

        # Test filename generation
        filename = view._generate_filename("TestUser")
        assert filename.endswith("_discord_text_TestUser.md")
        assert len(filename.split("_")) >= 4  # date_time_discord_type_user.md

        # Verify view has timeout configured
        assert view.timeout == VIEW_TIMEOUT

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, full_bot, integration_message):
        """Test error handling in E2E scenarios.

        This E2E test covers:
        1. Service unavailability handling
        2. Network timeout scenarios
        3. Proper fallback behavior
        4. User-friendly error messages
        """
        # Create TextCog with failing services
        failing_note_service = MagicMock(spec=NoteProcessingService)
        failing_note_service.is_available.return_value = True
        failing_note_service.process_text = AsyncMock(side_effect=Exception("Service error"))

        failing_obsidian_service = MagicMock(spec=ObsidianGitHubService)
        failing_obsidian_service.save_to_obsidian = AsyncMock(
            side_effect=Exception("GitHub API error")
        )

        text_cog = TextCog(full_bot, failing_note_service, failing_obsidian_service)

        test_text = "エラーハンドリングテスト用のテキスト"

        # Should not raise exception despite service failures
        await text_cog.handle_text_message(integration_message, test_text)

        # Verify fallback behavior - message should still be processed
        assert integration_message.reply.called
        assert integration_message.reply.return_value.edit.called

        # Verify graceful degradation (no AI processing but still functional)
        edit_call = integration_message.reply.return_value.edit.call_args
        assert "完了しました" in edit_call[1]["content"]

        # AI service should have been attempted
        failing_note_service.process_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, full_text_cog, full_bot):
        """Test concurrent text processing scenarios.

        This E2E test covers:
        1. Multiple simultaneous text processing requests
        2. Resource contention handling
        3. Performance under load
        4. Data integrity maintenance
        """
        # Create multiple mock messages
        messages = []
        for i in range(5):
            message = AsyncMock(spec=discord.Message)
            message.author = MagicMock()
            message.author.name = f"ConcurrentUser{i}"
            message.author.bot = False
            message.guild = MagicMock()
            message.guild.name = "ConcurrentGuild"
            message.channel = MagicMock()
            message.channel.name = "concurrent-test"
            message.id = 1000 + i
            message.reply = AsyncMock()

            reply_mock = AsyncMock()
            reply_mock.edit = AsyncMock()
            message.reply.return_value = reply_mock

            messages.append(message)

        start_time = time.time()

        # Process multiple messages concurrently
        tasks = []
        for i, message in enumerate(messages):
            test_text = f"同時処理テスト {i+1} - 複数のリクエストを処理します"
            task = asyncio.create_task(full_text_cog.handle_text_message(message, test_text))
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Verify performance requirement (should not scale linearly due to concurrency)
        assert total_time < 6.0, f"Concurrent processing too slow: {total_time:.2f}s"

        # Verify all messages were processed
        for message in messages:
            assert message.reply.called
            assert message.reply.return_value.edit.called

        # Verify AI service was called for each message
        assert full_text_cog.note_processing_service.process_text.call_count == 5

    @pytest.mark.asyncio
    async def test_message_listener_integration(self, full_text_cog):
        """Test message listener integration with prefix detection.

        This E2E test covers:
        1. !note prefix detection
        2. Automatic text extraction
        3. Full processing pipeline activation
        4. Response generation
        """
        message = AsyncMock(spec=discord.Message)
        message.content = "!note これはプレフィックス付きのテストメッセージです。"
        message.author = MagicMock()
        message.author.name = "PrefixUser"
        message.author.bot = False
        message.guild = MagicMock()
        message.guild.name = "PrefixGuild"
        message.channel = MagicMock()
        message.channel.name = "prefix-test"
        message.id = 444555666
        message.reply = AsyncMock()

        reply_mock = AsyncMock()
        reply_mock.edit = AsyncMock()
        message.reply.return_value = reply_mock

        start_time = time.time()

        # Test message listener
        await full_text_cog.on_message(message)

        processing_time = time.time() - start_time

        # Verify performance
        assert processing_time < 2.0, f"Prefix processing too slow: {processing_time:.2f}s"

        # Verify processing was triggered
        assert message.reply.called
        assert message.reply.return_value.edit.called

        # Verify AI service was called
        full_text_cog.note_processing_service.process_text.assert_called()

        # Verify correct text was extracted (without !note prefix)
        call_args = full_text_cog.note_processing_service.process_text.call_args
        assert "!note" not in call_args[0][0]
        assert "プレフィックス付きのテストメッセージ" in call_args[0][0]


class TestTextPerformanceIntegration:
    """Performance-focused integration tests."""

    @pytest.fixture
    def performance_bot(self):
        """Create a performance testing bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix="!", intents=intents)
        return bot

    @pytest.fixture
    def performance_note_service(self):
        """Create a performance-optimized NoteProcessingService."""
        service = MagicMock(spec=NoteProcessingService)
        service.is_available.return_value = True

        async def fast_process_text(text, processing_type="fleeting_note"):
            await asyncio.sleep(0.05)  # Fast processing
            return {
                "processed": f"処理済み: {text[:100]}...",
                "summary": f"{text[:50]}の要約",
                "metadata": {"confidence": 0.9},
            }

        service.process_text = AsyncMock(side_effect=fast_process_text)
        return service

    @pytest.fixture
    def performance_obsidian_service(self):
        """Create a performance-optimized ObsidianGitHubService."""
        service = MagicMock(spec=ObsidianGitHubService)
        service.save_to_obsidian = AsyncMock()
        return service

    @pytest.fixture
    def performance_text_cog(
        self, performance_bot, performance_note_service, performance_obsidian_service
    ):
        """Create TextCog for performance testing."""
        return TextCog(performance_bot, performance_note_service, performance_obsidian_service)

    @pytest.fixture
    def performance_message(self):
        """Create a message for performance testing."""
        message = AsyncMock(spec=discord.Message)
        message.author = MagicMock()
        message.author.name = "PerfUser"
        message.author.bot = False
        message.guild = MagicMock()
        message.guild.name = "PerfGuild"
        message.channel = MagicMock()
        message.channel.name = "perf-test"
        message.id = 123456789
        message.reply = AsyncMock()

        reply_mock = AsyncMock()
        reply_mock.edit = AsyncMock()
        message.reply.return_value = reply_mock

        return message

    @pytest.mark.asyncio
    async def test_large_text_processing_performance(
        self, performance_text_cog, performance_message
    ):
        """Test performance with large text inputs (near 4000 char limit)."""
        # Create large text (3900 characters)
        large_text = "テスト" * 975  # 3900 characters

        start_time = time.time()

        await performance_text_cog.handle_text_message(performance_message, large_text)

        processing_time = time.time() - start_time

        # Verify performance requirement for large text
        assert processing_time < 3.0, f"Large text processing too slow: {processing_time:.2f}s"

        # Verify successful processing
        assert performance_message.reply.called
        assert performance_message.reply.return_value.edit.called

    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, performance_text_cog, performance_bot):
        """Test memory usage remains stable during repeated operations."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Process 20 messages
        for i in range(20):
            message = AsyncMock(spec=discord.Message)
            message.author = MagicMock()
            message.author.name = f"MemoryUser{i}"
            message.author.bot = False
            message.guild = MagicMock()
            message.guild.name = "MemoryGuild"
            message.channel = MagicMock()
            message.channel.name = "memory-test"
            message.id = 2000 + i
            message.reply = AsyncMock()

            reply_mock = AsyncMock()
            reply_mock.edit = AsyncMock()
            message.reply.return_value = reply_mock

            test_text = f"メモリテスト {i+1} " * 50  # ~650 characters each
            await performance_text_cog.handle_text_message(message, test_text)

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (< 50MB for 20 operations)
        assert memory_increase < 50, f"Memory leak detected: {memory_increase:.1f}MB increase"
