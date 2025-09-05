"""WhisperTranscriptionServiceのテスト。"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.services.transcription.whisper import WhisperTranscriptionService


class TestWhisperTranscriptionService:
    """WhisperTranscriptionServiceのテスト。"""

    def test_init_with_api_key(self):
        """API キー有りでの初期化テスト。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = WhisperTranscriptionService()
            assert service.is_available() is True
            assert service.client is not None

    def test_init_without_api_key(self):
        """API キー無しでの初期化テスト。"""
        with patch.dict(os.environ, {}, clear=True):
            service = WhisperTranscriptionService()
            assert service.is_available() is False
            assert service.client is None

    def test_provider_name(self):
        """プロバイダー名のテスト。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = WhisperTranscriptionService()
            assert service.provider_name == "whisper"

    @pytest.mark.asyncio
    async def test_transcribe_success(self):
        """正常な文字起こしのテスト。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = WhisperTranscriptionService()

            # OpenAI クライアントをモック
            mock_transcript = MagicMock()
            mock_transcript.text = "テストの文字起こし結果"

            service.client = MagicMock()

            # asyncio.to_thread をモック
            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_transcript

                # 一時的なオーディオファイルを作成
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(b"fake audio data")
                    temp_file_path = temp_file.name

                try:
                    result = await service.transcribe(temp_file_path)
                    assert result == "テストの文字起こし結果"
                    mock_to_thread.assert_called_once()
                finally:
                    # 一時ファイルを削除
                    os.unlink(temp_file_path)

    @pytest.mark.asyncio
    async def test_transcribe_unavailable_service(self):
        """サービス利用不可時のテスト。"""
        with patch.dict(os.environ, {}, clear=True):
            service = WhisperTranscriptionService()
            result = await service.transcribe("dummy_path.wav")
            assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_timeout_error(self):
        """タイムアウトエラーのテスト。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = WhisperTranscriptionService()
            service.client = MagicMock()

            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.side_effect = TimeoutError("API timeout")

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(b"fake audio data")
                    temp_file_path = temp_file.name

                try:
                    result = await service.transcribe(temp_file_path)
                    assert result is None
                finally:
                    os.unlink(temp_file_path)

    @pytest.mark.asyncio
    async def test_transcribe_rate_limit_error(self):
        """レート制限エラーのテスト。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = WhisperTranscriptionService()
            service.client = MagicMock()

            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.side_effect = Exception("rate_limit exceeded")

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(b"fake audio data")
                    temp_file_path = temp_file.name

                try:
                    result = await service.transcribe(temp_file_path)
                    assert result is None
                finally:
                    os.unlink(temp_file_path)

    @pytest.mark.asyncio
    async def test_transcribe_general_error(self):
        """一般的なエラーのテスト。"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = WhisperTranscriptionService()
            service.client = MagicMock()

            with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.side_effect = Exception("General API error")

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(b"fake audio data")
                    temp_file_path = temp_file.name

                try:
                    result = await service.transcribe(temp_file_path)
                    assert result is None
                finally:
                    os.unlink(temp_file_path)
