"""Tests for TextCog."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from nescordbot.cogs.text import FleetingNoteView, TextCog


@pytest.fixture
def bot():
    """Create a mock bot instance."""
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    return bot


@pytest.fixture
def note_processing_service():
    """Create a mock NoteProcessingService."""
    service = AsyncMock()
    service.is_available.return_value = True
    service.process_text.return_value = {
        "processed": "Processed text content",
        "summary": "Test summary",
    }
    return service


@pytest.fixture
def obsidian_service():
    """Create a mock ObsidianGitHubService."""
    service = AsyncMock()
    service.save_to_obsidian = AsyncMock()
    return service


@pytest.fixture
def text_cog(bot, note_processing_service, obsidian_service):
    """Create a TextCog instance with mocked services."""
    return TextCog(bot, note_processing_service, obsidian_service)


@pytest.fixture
def mock_message():
    """Create a mock Discord message."""
    message = AsyncMock(spec=discord.Message)
    message.author = MagicMock()
    message.author.bot = False
    message.author.name = "TestUser"
    message.author.display_name = "TestUser"
    message.guild = MagicMock()
    message.guild.name = "TestGuild"
    message.channel = MagicMock()
    message.channel.name = "general"
    message.id = 987654321
    message.created_at = datetime.now()
    message.reply = AsyncMock()
    message.add_reaction = AsyncMock()
    return message


class TestTextCog:
    """Test TextCog functionality."""

    def test_init(self, bot, note_processing_service, obsidian_service):
        """Test TextCog initialization."""
        cog = TextCog(bot, note_processing_service, obsidian_service)
        assert cog.bot == bot
        assert cog.note_processing_service == note_processing_service
        assert cog.obsidian_service == obsidian_service

    def test_init_without_services(self, bot):
        """Test TextCog initialization without services."""
        cog = TextCog(bot)
        assert cog.bot == bot
        assert cog.note_processing_service is None
        assert cog.obsidian_service is None

    @pytest.mark.asyncio
    async def test_handle_text_message_success(self, text_cog, mock_message):
        """Test successful text message handling."""
        text = "This is a test message"

        await text_cog.handle_text_message(mock_message, text)

        # Verify processing message was sent
        assert mock_message.reply.called
        processing_call = mock_message.reply.call_args_list[0]
        assert "処理中" in processing_call[0][0]

        # Verify result message was sent
        result_call = mock_message.reply.return_value.edit
        assert result_call.called

    @pytest.mark.asyncio
    async def test_handle_text_message_empty(self, text_cog, mock_message):
        """Test handling empty text message."""
        await text_cog.handle_text_message(mock_message, "")

        mock_message.reply.assert_called_once()
        assert "テキストを入力してください" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_text_message_too_long(self, text_cog, mock_message):
        """Test handling text message that's too long."""
        long_text = "a" * 4001

        await text_cog.handle_text_message(mock_message, long_text)

        mock_message.reply.assert_called_once()
        assert "長すぎます" in mock_message.reply.call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_text_message_without_ai_service(
        self, bot, obsidian_service, mock_message
    ):
        """Test handling text message without AI service."""
        cog = TextCog(bot, None, obsidian_service)
        text = "Test message"

        await cog.handle_text_message(mock_message, text)

        # Should still process the message without AI
        assert mock_message.reply.called

    def test_format_fleeting_note(self, text_cog, mock_message):
        """Test Fleeting Note formatting."""
        text = "Test content"
        summary = "Test summary"

        result = text_cog._format_fleeting_note(text, summary, mock_message, "text")

        # Check YAML frontmatter
        assert "---" in result
        assert "type: fleeting_note" in result
        assert "tags:" in result
        assert "discord/text" in result

        # Check content sections
        assert "## 💭 アイデア・思考の断片" in result
        assert text in result
        assert "## 🔗 関連しそうなこと" in result
        assert "## ❓ 疑問・調べたいこと" in result
        assert "## 📝 次のアクション" in result

        # Check Discord info
        assert "TestGuild" in result
        assert "general" in result
        assert "TestUser" in result

    def test_sanitize_username(self, text_cog):
        """Test username sanitization."""
        # Test normal username
        assert text_cog._sanitize_username("TestUser") == "TestUser"

        # Test username with special characters
        assert text_cog._sanitize_username("Test@User#123") == "TestUser123"

        # Test username with spaces
        assert text_cog._sanitize_username("Test User") == "Test_User"

        # Test long username
        long_name = "a" * 30
        sanitized = text_cog._sanitize_username(long_name)
        assert len(sanitized) <= 20

    @pytest.mark.asyncio
    async def test_note_command(self, text_cog):
        """Test /note slash command."""
        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user = MagicMock()
        interaction.user.name = "TestUser"
        interaction.guild = MagicMock()
        interaction.guild.name = "TestGuild"
        interaction.channel = MagicMock()
        interaction.channel.name = "general"
        interaction.id = 123456
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        text = "Test slash command text"

        # Call the callback directly since it's a command
        await text_cog.note_command.callback(text_cog, interaction, text)

        # Verify defer was called
        interaction.response.defer.assert_called_once()

        # Verify followup was sent
        interaction.followup.send.assert_called_once()
        call_args = interaction.followup.send.call_args
        assert "Fleeting Note" in call_args[1]["content"]

    @pytest.mark.asyncio
    async def test_on_message_with_prefix(self, text_cog, mock_message):
        """Test on_message listener with !note prefix."""
        mock_message.content = "!note Test message"
        mock_message.author.bot = False

        await text_cog.on_message(mock_message)

        # Verify handle_text_message was called
        assert mock_message.reply.called

    @pytest.mark.asyncio
    async def test_on_message_ignore_bot(self, text_cog):
        """Test that bot messages are ignored."""
        message = AsyncMock(spec=discord.Message)
        message.author.bot = True
        message.content = "!note Test"

        await text_cog.on_message(message)

        # Should not process bot messages
        message.reply.assert_not_called()


class TestFleetingNoteView:
    """Test FleetingNoteView functionality."""

    @pytest.mark.asyncio
    async def test_init(self, obsidian_service):
        """Test FleetingNoteView initialization."""
        content = "Test content"
        summary = "Test summary"

        # Create view within async context
        view = FleetingNoteView(content, summary, obsidian_service)

        assert view.content == content
        assert view.summary == summary
        assert view.obsidian_service == obsidian_service
        assert view.note_type == "voice"  # Default

    @pytest.mark.asyncio
    async def test_generate_filename(self, obsidian_service):
        """Test filename generation."""
        view = FleetingNoteView("content", "summary", obsidian_service, note_type="text")

        filename = view._generate_filename("TestUser")

        # Check filename format
        assert filename.endswith(".md")
        assert "discord_text" in filename
        assert "TestUser" in filename

        # Check date format (YYYYMMDD_HHMM)
        parts = filename.split("_")
        assert len(parts[0]) == 8  # Date part
        assert len(parts[1]) == 4  # Time part

    @pytest.mark.asyncio
    async def test_generate_filename_with_special_chars(self, obsidian_service):
        """Test filename generation with special characters."""
        view = FleetingNoteView("content", "summary", obsidian_service)

        filename = view._generate_filename("Test@User#123")

        # Special characters should be removed
        assert "@" not in filename
        assert "#" not in filename
        assert "TestUser123" in filename

    @pytest.mark.asyncio
    async def test_save_to_obsidian_success(self, obsidian_service):
        """Test successful save to Obsidian."""
        view = FleetingNoteView("content", "summary", obsidian_service)

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user.name = "TestUser"
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.message = AsyncMock()
        interaction.message.edit = AsyncMock()
        interaction.channel = MagicMock()

        # Call the button callback directly
        # save_to_obsidian is a button callback, so we need to call it directly
        button = None
        for item in view.children:
            if hasattr(item, "callback") and item.label == "Obsidianに保存":
                button = item
                await item.callback(interaction)
                break

        # Verify defer was called
        interaction.response.defer.assert_called_once_with(ephemeral=True)

        # Verify save was called
        obsidian_service.save_to_obsidian.assert_called_once()

        # Verify success message
        interaction.followup.send.assert_called_once()
        assert "保存しました" in interaction.followup.send.call_args[0][0]

        # Verify button was disabled
        assert button is not None
        assert button.disabled is True

    @pytest.mark.asyncio
    async def test_save_to_obsidian_no_service(self):
        """Test save when ObsidianGitHubService is not available."""
        view = FleetingNoteView("content", "summary", None)  # No service

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.response.send_message = AsyncMock()

        # Call the button callback directly
        # save_to_obsidian is a button callback, so we need to call it directly
        for item in view.children:
            if hasattr(item, "callback") and item.label == "Obsidianに保存":
                await item.callback(interaction)
                break

        # Should send error message
        interaction.response.send_message.assert_called_once()
        assert "利用できません" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_save_to_obsidian_error(self, obsidian_service):
        """Test save error handling."""
        view = FleetingNoteView("content", "summary", obsidian_service)

        # Make save_to_obsidian raise an error
        obsidian_service.save_to_obsidian.side_effect = Exception("Test error")

        interaction = AsyncMock(spec=discord.Interaction)
        interaction.user.name = "TestUser"
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.channel = MagicMock()

        # Call the button callback directly
        # save_to_obsidian is a button callback, so we need to call it directly
        for item in view.children:
            if hasattr(item, "callback") and item.label == "Obsidianに保存":
                await item.callback(interaction)
                break

        # Should send error message
        interaction.followup.send.assert_called_once()
        assert "エラーが発生しました" in interaction.followup.send.call_args[0][0]


@pytest.mark.asyncio
async def test_setup(bot):
    """Test cog setup function."""
    bot.note_processing_service = AsyncMock()
    bot.obsidian_service = AsyncMock()
    bot.add_cog = AsyncMock()

    # Import and run setup
    from nescordbot.cogs.text import setup

    await setup(bot)

    # Verify cog was added
    bot.add_cog.assert_called_once()
    cog = bot.add_cog.call_args[0][0]
    assert isinstance(cog, TextCog)
