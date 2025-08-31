"""TranscriptionServiceファクトリのテスト。"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.nescordbot.services.transcription import get_transcription_service
from src.nescordbot.services.transcription.gemini import GeminiTranscriptionService
from src.nescordbot.services.transcription.whisper import WhisperTranscriptionService


class TestTranscriptionServiceFactory:
    """TranscriptionServiceファクトリのテスト。"""

    def test_get_whisper_service_explicit(self):
        """明示的にwhisperを指定した場合のテスト。"""
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "whisper"}):
            service = get_transcription_service()
            assert isinstance(service, WhisperTranscriptionService)

    def test_get_whisper_service_default(self):
        """デフォルト（環境変数なし）でwhisperが選択されるテスト。"""
        with patch.dict(os.environ, {}, clear=True):
            service = get_transcription_service()
            assert isinstance(service, WhisperTranscriptionService)

    def test_get_whisper_service_invalid_provider(self):
        """無効なプロバイダーでwhisperにフォールバックするテスト。"""
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "invalid_provider"}):
            service = get_transcription_service()
            assert isinstance(service, WhisperTranscriptionService)

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    def test_get_gemini_service_available(self):
        """Geminiが利用可能な場合のテスト。"""
        with patch.dict(
            os.environ, {"TRANSCRIPTION_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}
        ):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model

                service = get_transcription_service()
                assert isinstance(service, GeminiTranscriptionService)

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    def test_get_gemini_service_fallback_to_whisper_no_api_key(self):
        """GeminiのAPIキーがない場合にWhisperにフォールバックするテスト。"""
        with patch.dict(
            os.environ,
            {"TRANSCRIPTION_PROVIDER": "gemini", "OPENAI_API_KEY": "whisper-key"},
            clear=True,
        ):
            # GEMINI_API_KEYは設定されていない状態
            service = get_transcription_service()
            # Geminiが利用不可なのでWhisperにフォールバック
            assert isinstance(service, WhisperTranscriptionService)

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", False)
    def test_get_gemini_service_fallback_to_whisper_unavailable(self):
        """Gemini SDKが利用不可の場合にWhisperにフォールバックするテスト。"""
        with patch.dict(
            os.environ,
            {
                "TRANSCRIPTION_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-key",
                "OPENAI_API_KEY": "whisper-key",
            },
        ):
            service = get_transcription_service()
            # Gemini SDKが利用不可なのでWhisperにフォールバック
            assert isinstance(service, WhisperTranscriptionService)

    def test_case_insensitive_provider(self):
        """プロバイダー名の大文字小文字が無視されるテスト。"""
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "WHISPER"}):
            service = get_transcription_service()
            assert isinstance(service, WhisperTranscriptionService)

        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "Whisper"}):
            service = get_transcription_service()
            assert isinstance(service, WhisperTranscriptionService)
