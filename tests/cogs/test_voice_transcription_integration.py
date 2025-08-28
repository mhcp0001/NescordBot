"""VoiceCogのTranscriptionService統合テスト。"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from src.nescordbot.cogs.voice import Voice


class TestVoiceTranscriptionIntegration:
    """VoiceCogのTranscriptionService統合テスト。"""

    @pytest.fixture
    def mock_bot(self):
        """モックBot。"""
        return MagicMock(spec=commands.Bot)

    @pytest.fixture
    def voice_cog_whisper(self, mock_bot):
        """Whisper使用のVoiceCogフィクスチャ。"""
        with patch.dict(
            os.environ, {"TRANSCRIPTION_PROVIDER": "whisper", "OPENAI_API_KEY": "test-key"}
        ):
            return Voice(mock_bot)

    @pytest.fixture
    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    def voice_cog_gemini(self, mock_bot):
        """Gemini使用のVoiceCogフィクスチャ。"""
        with patch.dict(
            os.environ, {"TRANSCRIPTION_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}
        ):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model
                return Voice(mock_bot)

    @pytest.mark.asyncio
    async def test_transcribe_with_whisper(self, voice_cog_whisper):
        """WhisperでのVoiceCog文字起こしテスト。"""
        # TranscriptionServiceをモック
        mock_transcription = AsyncMock()
        mock_transcription.transcribe.return_value = "Whisperによる文字起こし"
        mock_transcription.is_available.return_value = True
        mock_transcription.provider_name = "whisper"

        voice_cog_whisper.transcription_service = mock_transcription

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            temp_file_path = temp_file.name

        try:
            result = await voice_cog_whisper.transcribe_audio(temp_file_path)
            assert result == "Whisperによる文字起こし"
            mock_transcription.transcribe.assert_called_once_with(temp_file_path)
        finally:
            os.unlink(temp_file_path)

    @pytest.mark.asyncio
    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    async def test_transcribe_with_gemini(self, voice_cog_gemini):
        """GeminiでのVoiceCog文字起こしテスト。"""
        # TranscriptionServiceをモック
        mock_transcription = AsyncMock()
        mock_transcription.transcribe.return_value = "Geminiによる文字起こし"
        mock_transcription.is_available.return_value = True
        mock_transcription.provider_name = "gemini"

        voice_cog_gemini.transcription_service = mock_transcription

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            temp_file_path = temp_file.name

        try:
            result = await voice_cog_gemini.transcribe_audio(temp_file_path)
            assert result == "Geminiによる文字起こし"
            mock_transcription.transcribe.assert_called_once_with(temp_file_path)
        finally:
            os.unlink(temp_file_path)

    @pytest.mark.asyncio
    async def test_transcribe_service_unavailable(self, voice_cog_whisper):
        """TranscriptionService利用不可時のテスト。"""
        # TranscriptionServiceを利用不可に設定
        mock_transcription = MagicMock()
        mock_transcription.is_available.return_value = False
        mock_transcription.provider_name = "whisper"

        voice_cog_whisper.transcription_service = mock_transcription

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(b"fake audio data")
            temp_file_path = temp_file.name

        try:
            result = await voice_cog_whisper.transcribe_audio(temp_file_path)
            assert result is None
            # transcribeは呼ばれないことを確認
            mock_transcription.transcribe.assert_not_called()
        finally:
            os.unlink(temp_file_path)

    def test_initialization_whisper_provider(self, mock_bot):
        """Whisperプロバイダーでの初期化テスト。"""
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "whisper"}):
            cog = Voice(mock_bot)
            assert cog.transcription_service.provider_name == "whisper"

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    def test_initialization_gemini_provider(self, mock_bot):
        """Geminiプロバイダーでの初期化テスト。"""
        with patch.dict(
            os.environ, {"TRANSCRIPTION_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}
        ):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model

                cog = Voice(mock_bot)
                assert cog.transcription_service.provider_name == "gemini"

    def test_backward_compatibility_openai_client(self, voice_cog_whisper):
        """後方互換性のためのopenai_clientテスト。"""
        # 後方互換性のため、openai_clientも設定されていることを確認
        assert hasattr(voice_cog_whisper, "openai_client")
