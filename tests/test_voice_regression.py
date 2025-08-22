"""Voice Cog リグレッションテスト

NoteProcessingService統合後の既存機能デグレード防止テスト
Issue #80対応
"""

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import discord
import pytest
from openai import OpenAI

from src.nescordbot.cogs.voice import TranscriptionView, Voice
from src.nescordbot.services import NoteProcessingService, ObsidianGitHubService


# 共通フィクスチャー
@pytest.fixture
def mock_bot():
    """モックBotインスタンス"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    return bot


@pytest.fixture
def mock_obsidian_service():
    """モックObsidianGitHubService"""
    service = MagicMock(spec=ObsidianGitHubService)
    service.save_to_obsidian = AsyncMock(return_value="test-request-id")
    return service


@pytest.fixture
def mock_note_processing_service():
    """モックNoteProcessingService"""
    service = MagicMock(spec=NoteProcessingService)
    service.process_text = AsyncMock(
        return_value={"processed": "リファクタリング後整形テキスト", "summary": "リファクタリング後要約"}
    )
    service.is_available = MagicMock(return_value=True)
    return service


class TestVoiceRegressionCore:
    """コア機能のリグレッションテスト"""

    @pytest.fixture
    def voice_cog_full(self, mock_bot, mock_obsidian_service, mock_note_processing_service):
        """フル機能のVoice Cogインスタンス"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            cog = Voice(mock_bot, mock_obsidian_service, mock_note_processing_service)
            return cog

    @pytest.mark.asyncio
    async def test_voice_cog_initialization_regression(self, voice_cog_full):
        """Voice Cogの初期化が正常に動作することを確認"""
        assert voice_cog_full.bot is not None
        assert voice_cog_full.obsidian_service is not None
        assert voice_cog_full.note_processing_service is not None
        assert voice_cog_full.openai_client is not None

    @pytest.mark.asyncio
    async def test_transcribe_audio_compatibility(self, voice_cog_full):
        """transcribe_audio メソッドの既存インターフェース確認"""
        with patch("builtins.open", create=True):
            with patch("asyncio.to_thread") as mock_to_thread:
                # OpenAI API応答をモック
                mock_response = MagicMock()
                mock_response.text = "リグレッションテスト用音声テキスト"
                mock_to_thread.return_value = mock_response

                result = await voice_cog_full.transcribe_audio("test_path.ogg")

                assert result == "リグレッションテスト用音声テキスト"
                mock_to_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_with_ai_service_integration(self, voice_cog_full):
        """process_with_ai メソッドのNoteProcessingService統合確認"""
        result = await voice_cog_full.process_with_ai("テスト音声テキスト")

        # NoteProcessingServiceが正しく呼び出されているか確認
        voice_cog_full.note_processing_service.process_text.assert_called_once_with(
            "テスト音声テキスト", processing_type="voice_transcription"
        )

        # 戻り値の構造が正しいか確認
        assert "processed" in result
        assert "summary" in result
        assert result["processed"] == "リファクタリング後整形テキスト"
        assert result["summary"] == "リファクタリング後要約"


@pytest.fixture
def voice_cog_perf(mock_bot, mock_obsidian_service, mock_note_processing_service):
    """パフォーマンステスト用Voice Cog"""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        cog = Voice(mock_bot, mock_obsidian_service, mock_note_processing_service)
        return cog


class TestVoiceRegressionPerformance:
    """パフォーマンステスト"""

    @pytest.mark.asyncio
    async def test_handle_voice_message_performance(self, voice_cog_perf):
        """音声メッセージ処理の性能要件確認（3秒以内）"""
        # モック設定
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 12345
        mock_message.author = "test_user"
        mock_message.reply = AsyncMock()

        mock_attachment = MagicMock(spec=discord.Attachment)
        mock_attachment.read = AsyncMock(return_value=b"mock_audio_data")
        mock_attachment.size = 1024 * 100  # 100KB
        mock_attachment.filename = "perf_test.ogg"

        mock_processing_msg = MagicMock()
        mock_processing_msg.edit = AsyncMock()
        mock_message.reply.return_value = mock_processing_msg

        # モック処理時間を設定
        async def mock_transcribe_with_delay(path):
            await asyncio.sleep(0.5)  # 500ms遅延をシミュレート
            return "パフォーマンステスト用音声テキスト"

        async def mock_process_ai_with_delay(text):
            await asyncio.sleep(0.3)  # 300ms遅延をシミュレート
            return {"processed": "パフォーマンステスト整形済み", "summary": "パフォーマンステスト要約"}

        voice_cog_perf.transcribe_audio = mock_transcribe_with_delay
        voice_cog_perf.process_with_ai = mock_process_ai_with_delay

        # パフォーマンス測定
        start_time = time.time()

        with patch("src.nescordbot.cogs.voice.os.makedirs"):
            with patch("builtins.open", create=True):
                with patch("src.nescordbot.cogs.voice.os.path.exists", return_value=True):
                    with patch("src.nescordbot.cogs.voice.os.remove"):
                        await voice_cog_perf.handle_voice_message(mock_message, mock_attachment)

        processing_time = time.time() - start_time

        # 性能要件確認: 3秒以内
        assert processing_time < 3.0, f"処理時間が要件を超過: {processing_time:.2f}秒"

    @pytest.mark.asyncio
    async def test_file_size_limit_regression(self, voice_cog_perf):
        """ファイルサイズ制限の動作確認（25MB制限）"""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 12345
        mock_message.reply = AsyncMock()

        # 25MB超過ファイル
        mock_large_attachment = MagicMock(spec=discord.Attachment)
        mock_large_attachment.size = 26 * 1024 * 1024  # 26MB
        mock_large_attachment.filename = "large_file.ogg"

        await voice_cog_perf.handle_voice_message(mock_message, mock_large_attachment)

        # エラーメッセージが返されることを確認
        mock_message.reply.assert_called_once()
        call_args = mock_message.reply.call_args[0][0]
        assert "ファイルサイズが大きすぎます" in call_args
        assert "25MB" in call_args


@pytest.fixture
def voice_cog_error(mock_bot, mock_obsidian_service):
    """エラーテスト用Voice Cog（NoteProcessingServiceなし）"""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        cog = Voice(mock_bot, mock_obsidian_service, None)  # サービスなし
        return cog


class TestVoiceRegressionErrorHandling:
    """エラーハンドリングのリグレッションテスト"""

    @pytest.mark.asyncio
    async def test_fallback_behavior_regression(self, voice_cog_error):
        """NoteProcessingService障害時のフォールバック動作確認"""
        result = await voice_cog_error.process_with_ai("テストテキスト")

        # フォールバック処理が動作することを確認
        assert result["processed"] == "テストテキスト"
        assert "利用できないため" in result["summary"]

    @pytest.mark.asyncio
    async def test_note_processing_service_error_fallback(self, mock_bot, mock_obsidian_service):
        """NoteProcessingServiceでエラーが発生した場合のフォールバック"""
        # エラーを発生させるモックサービス
        error_service = MagicMock(spec=NoteProcessingService)
        error_service.is_available = MagicMock(return_value=True)
        error_service.process_text = AsyncMock(side_effect=Exception("テストエラー"))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
            cog = Voice(mock_bot, mock_obsidian_service, error_service)

        result = await cog.process_with_ai("エラーテストテキスト")

        # フォールバック処理が動作することを確認
        assert result["processed"] == "エラーテストテキスト"
        assert "利用できないため" in result["summary"]


@pytest.fixture
def voice_cog_integration(mock_bot, mock_obsidian_service, mock_note_processing_service):
    """統合テスト用Voice Cog"""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-api-key"}):
        cog = Voice(mock_bot, mock_obsidian_service, mock_note_processing_service)
        return cog


class TestVoiceRegressionIntegration:
    """統合テスト"""

    @pytest.mark.asyncio
    async def test_end_to_end_voice_processing(self, voice_cog_integration):
        """音声処理の全フロー統合テスト"""
        mock_message = MagicMock(spec=discord.Message)
        mock_message.id = 99999
        mock_message.author = "integration_test_user"
        mock_message.reply = AsyncMock()

        mock_attachment = MagicMock(spec=discord.Attachment)
        mock_attachment.read = AsyncMock(return_value=b"integration_test_audio")
        mock_attachment.size = 2048  # 2KB
        mock_attachment.filename = "integration_test.ogg"

        mock_processing_msg = MagicMock()
        mock_processing_msg.edit = AsyncMock()
        mock_message.reply.return_value = mock_processing_msg

        # モック設定
        voice_cog_integration.transcribe_audio = AsyncMock(return_value="統合テスト音声内容")

        with patch("src.nescordbot.cogs.voice.os.makedirs"):
            with patch("builtins.open", create=True):
                with patch("src.nescordbot.cogs.voice.os.path.exists", return_value=True):
                    with patch("src.nescordbot.cogs.voice.os.remove"):
                        await voice_cog_integration.handle_voice_message(
                            mock_message, mock_attachment
                        )

        # 全体フローの検証
        voice_cog_integration.transcribe_audio.assert_called_once()
        voice_cog_integration.note_processing_service.process_text.assert_called_once_with(
            "統合テスト音声内容", processing_type="voice_transcription"
        )
        mock_processing_msg.edit.assert_called()
        mock_message.reply.assert_called()

    @pytest.mark.asyncio
    async def test_transcription_view_compatibility(self, mock_obsidian_service):
        """TranscriptionViewの既存機能互換性確認"""
        view = TranscriptionView(
            transcription="統合テスト文字起こし",
            summary="統合テスト要約",
            obsidian_service=mock_obsidian_service,
        )

        assert view.transcription == "統合テスト文字起こし"
        assert view.summary == "統合テスト要約"
        assert view.obsidian_service == mock_obsidian_service
        assert view.timeout == 300  # 5分タイムアウト


# パフォーマンス基準値定義
PERFORMANCE_REQUIREMENTS = {
    "max_processing_time": 3.0,  # 最大処理時間（秒）
    "max_file_size": 25 * 1024 * 1024,  # 最大ファイルサイズ（バイト）
    "min_test_coverage": 0.78,  # 最小テストカバレッジ
}


def test_performance_requirements():
    """パフォーマンス要件の定数確認"""
    assert PERFORMANCE_REQUIREMENTS["max_processing_time"] == 3.0
    assert PERFORMANCE_REQUIREMENTS["max_file_size"] == 25 * 1024 * 1024
    assert PERFORMANCE_REQUIREMENTS["min_test_coverage"] == 0.78
