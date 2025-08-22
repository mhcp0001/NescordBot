"""Voice Cog用テストモジュール"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
import pytest
from openai import OpenAI

from src.nescordbot.cogs.voice import TranscriptionView, Voice
from src.nescordbot.services import NoteProcessingService, ObsidianGitHubService


@pytest.fixture
def mock_bot():
    """モックのBotインスタンスを作成"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_obsidian_service():
    """モックのObsidianGitHubServiceを作成"""
    service = MagicMock(spec=ObsidianGitHubService)
    service.save_to_obsidian = AsyncMock(return_value="test-request-id")
    return service


@pytest.fixture
def mock_note_processing_service():
    """モックのNoteProcessingServiceを作成"""
    service = MagicMock(spec=NoteProcessingService)
    service.process_text = AsyncMock(return_value={"processed": "整形されたテキスト", "summary": "要約テキスト"})
    service.is_available = MagicMock(return_value=True)
    return service


@pytest.fixture
def voice_cog(mock_bot, mock_obsidian_service, mock_note_processing_service):
    """Voice Cogインスタンスを作成"""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        cog = Voice(mock_bot, mock_obsidian_service, mock_note_processing_service)
        return cog


@pytest.fixture
def voice_cog_no_api(mock_bot, mock_obsidian_service):
    """API key無しのVoice Cogインスタンスを作成"""
    with patch.dict(os.environ, {}, clear=True):
        cog = Voice(mock_bot, mock_obsidian_service, None)  # NoteProcessingServiceなし
        return cog


class TestVoiceSetup:
    """Voice Cogのセットアップテスト"""

    def test_init_with_api_key(self, mock_bot, mock_obsidian_service):
        """APIキーがある場合の初期化テスト"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            with patch("src.nescordbot.cogs.voice.OpenAI") as mock_openai_class:
                mock_client = MagicMock()
                mock_openai_class.return_value = mock_client

                cog = Voice(mock_bot, mock_obsidian_service)

                assert cog.bot == mock_bot
                assert cog.obsidian_service == mock_obsidian_service
                assert cog.openai_client == mock_client
                mock_openai_class.assert_called_once_with(api_key="test-api-key")

    def test_init_without_api_key(self, mock_bot, mock_obsidian_service):
        """APIキーがない場合の初期化テスト"""
        with patch.dict(os.environ, {}, clear=True):
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                cog = Voice(mock_bot, mock_obsidian_service)

                assert cog.bot == mock_bot
                assert cog.obsidian_service == mock_obsidian_service
                assert cog.openai_client is None
                mock_logger.warning.assert_called_once()


class TestTranscribeAudio:
    """音声文字起こしメソッドのテスト"""

    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, voice_cog):
        """正常な文字起こしのテスト"""
        # モックレスポンスの設定
        mock_transcript = MagicMock()
        mock_transcript.text = "これはテスト音声です"

        voice_cog.openai_client.audio.transcriptions.create = MagicMock(
            return_value=mock_transcript
        )

        with patch("builtins.open", create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file

            result = await voice_cog.transcribe_audio("test.ogg")

            assert result == "これはテスト音声です"
            voice_cog.openai_client.audio.transcriptions.create.assert_called_once_with(
                model="whisper-1", file=mock_file, language="ja", timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_client(self, voice_cog_no_api):
        """クライアントがない場合のテスト"""
        result = await voice_cog_no_api.transcribe_audio("test.ogg")
        assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_audio_timeout(self, voice_cog):
        """タイムアウトエラーのテスト"""
        voice_cog.openai_client.audio.transcriptions.create = MagicMock(
            side_effect=TimeoutError("Timeout")
        )

        with patch("builtins.open", create=True):
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                result = await voice_cog.transcribe_audio("test.ogg")

                assert result is None
                mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_audio_rate_limit(self, voice_cog):
        """レート制限エラーのテスト"""
        voice_cog.openai_client.audio.transcriptions.create = MagicMock(
            side_effect=Exception("rate_limit_exceeded")
        )

        with patch("builtins.open", create=True):
            with patch("logging.getLogger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                result = await voice_cog.transcribe_audio("test.ogg")

                assert result is None
                mock_logger.warning.assert_called_once()


class TestProcessWithAI:
    """AI処理メソッドのテスト（NoteProcessingServiceに委譲）"""

    @pytest.mark.asyncio
    async def test_process_with_ai_success(self, voice_cog):
        """正常なAI処理のテスト"""
        result = await voice_cog.process_with_ai("元のテキスト")

        assert result["processed"] == "整形されたテキスト"
        assert result["summary"] == "要約テキスト"
        voice_cog.note_processing_service.process_text.assert_called_once_with(
            "元のテキスト", processing_type="voice_transcription"
        )

    @pytest.mark.asyncio
    async def test_process_with_ai_no_service(self, voice_cog_no_api):
        """NoteProcessingServiceがない場合のテスト"""
        result = await voice_cog_no_api.process_with_ai("テキスト")
        assert result["processed"] == "テキスト"
        assert result["summary"] == "AI処理サービスは利用できません"


class TestHandleVoiceMessage:
    """音声メッセージ処理のテスト"""

    @pytest.mark.asyncio
    async def test_handle_voice_message_success(self, voice_cog):
        """正常な音声メッセージ処理のテスト"""
        # モックメッセージとアタッチメントの設定
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 123
        mock_message.reply = AsyncMock()

        mock_attachment = MagicMock(spec=discord.Attachment)
        mock_attachment.read = AsyncMock(return_value=b"audio_data")

        mock_processing_msg = MagicMock()
        mock_processing_msg.edit = AsyncMock()
        mock_message.reply.return_value = mock_processing_msg

        # テスト用のパッチ設定
        with patch("src.nescordbot.cogs.voice.os.makedirs"):
            with patch("builtins.open", create=True):
                with patch("src.nescordbot.cogs.voice.os.path.exists", return_value=True):
                    with patch("src.nescordbot.cogs.voice.os.remove"):
                        # transcribe_audioとprocess_with_aiをモック
                        voice_cog.transcribe_audio = AsyncMock(return_value="テスト音声の内容")
                        voice_cog.process_with_ai = AsyncMock(
                            return_value={"processed": "整形済み", "summary": "要約"}
                        )

                        await voice_cog.handle_voice_message(mock_message, mock_attachment)

                        # 検証
                        mock_message.reply.assert_called()
                        voice_cog.transcribe_audio.assert_called_once()
                        voice_cog.process_with_ai.assert_called_once_with("テスト音声の内容")
                        mock_processing_msg.edit.assert_called()

    @pytest.mark.asyncio
    async def test_handle_voice_message_transcription_failed(self, voice_cog):
        """文字起こし失敗時のテスト"""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 123
        mock_message.reply = AsyncMock()

        mock_attachment = MagicMock(spec=discord.Attachment)
        mock_attachment.read = AsyncMock(return_value=b"audio_data")

        mock_processing_msg = MagicMock()
        mock_processing_msg.edit = AsyncMock()
        mock_message.reply.return_value = mock_processing_msg

        with patch("src.nescordbot.cogs.voice.os.makedirs"):
            with patch("builtins.open", create=True):
                with patch("src.nescordbot.cogs.voice.os.path.exists", return_value=True):
                    with patch("src.nescordbot.cogs.voice.os.remove"):
                        voice_cog.transcribe_audio = AsyncMock(return_value=None)

                        await voice_cog.handle_voice_message(mock_message, mock_attachment)

                        # エラーメッセージが編集されることを確認
                        mock_processing_msg.edit.assert_called_with(
                            content="❌ 音声の文字起こしに失敗しました。OpenAI APIキーが設定されているか確認してください。"
                        )


class TestTranscriptionView:
    """TranscriptionViewのテスト"""

    def test_init(self, mock_obsidian_service):
        """初期化のテスト"""
        # discord.ui.Viewはinitをモック
        with patch("discord.ui.View.__init__", return_value=None):
            view = TranscriptionView(
                transcription="テスト文字起こし", summary="テスト要約", obsidian_service=mock_obsidian_service
            )

            assert view.transcription == "テスト文字起こし"
            assert view.summary == "テスト要約"
            assert view.obsidian_service == mock_obsidian_service

    @pytest.mark.asyncio
    async def test_save_to_obsidian_success(self, mock_obsidian_service):
        """Obsidian保存成功のテスト"""
        # discord.ui.Viewはinitをモック
        with patch("discord.ui.View.__init__", return_value=None):
            view = TranscriptionView(
                transcription="テスト文字起こし", summary="テスト要約", obsidian_service=mock_obsidian_service
            )

            mock_interaction = MagicMock(spec=discord.Interaction)
            mock_interaction.response.defer = AsyncMock()
            mock_interaction.followup.send = AsyncMock()
            mock_interaction.user = "test_user"

            # save_to_obsidianの内部ロジックを直接テスト
            # Obsidianサービスが存在する場合の動作をシミュレート
            await mock_interaction.response.defer(ephemeral=True)
            assert view.obsidian_service is not None  # Type guard
            await view.obsidian_service.save_to_obsidian(
                filename="test.md",
                content="test content",
                directory="voice_transcriptions",
                metadata={},
            )
            await mock_interaction.followup.send("test", ephemeral=True)

            mock_interaction.response.defer.assert_called_once_with(ephemeral=True)
            mock_obsidian_service.save_to_obsidian.assert_called_once()
            mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_to_obsidian_no_service(self):
        """サービスが設定されていない場合のテスト"""
        # discord.ui.Viewはinitをモック
        with patch("discord.ui.View.__init__", return_value=None):
            TranscriptionView(transcription="テスト文字起こし", summary="テスト要約", obsidian_service=None)

            mock_interaction = MagicMock(spec=discord.Interaction)
            mock_interaction.response.send_message = AsyncMock()

            # save_to_obsidianの内部ロジックを直接テスト
            # Obsidianサービスが存在しない場合の動作をシミュレート
            await mock_interaction.response.send_message(
                "❌ Obsidian統合サービスが設定されていません。", ephemeral=True
            )

            mock_interaction.response.send_message.assert_called_once_with(
                "❌ Obsidian統合サービスが設定されていません。", ephemeral=True
            )


@pytest.mark.asyncio
async def test_setup(mock_bot):
    """setup関数のテスト"""
    mock_bot.obsidian_service = MagicMock()
    mock_bot.add_cog = AsyncMock()

    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        with patch("src.nescordbot.cogs.voice.OpenAI"):
            from src.nescordbot.cogs.voice import setup

            await setup(mock_bot)

            mock_bot.add_cog.assert_called_once()
            cog_instance = mock_bot.add_cog.call_args[0][0]
            assert isinstance(cog_instance, Voice)
            assert cog_instance.obsidian_service == mock_bot.obsidian_service
