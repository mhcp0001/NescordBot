"""GeminiTranscriptionServiceのテスト。"""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.services.transcription.gemini import GeminiTranscriptionService


class TestGeminiTranscriptionService:
    """GeminiTranscriptionServiceのテスト。"""

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    def test_init_with_api_key(self):
        """API キー有りでの初期化テスト。"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                mock_model = MagicMock()
                mock_genai.GenerativeModel.return_value = mock_model

                service = GeminiTranscriptionService()
                assert service.is_available() is True
                assert service.model is not None

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    def test_init_without_api_key(self):
        """API キー無しでの初期化テスト。"""
        with patch.dict(os.environ, {}, clear=True):
            service = GeminiTranscriptionService()
            assert service.is_available() is False
            assert service.model is None

    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", False)
    def test_init_gemini_unavailable(self):
        """Gemini SDK未インストール時のテスト。"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            service = GeminiTranscriptionService()
            assert service.is_available() is False
            assert service.model is None

    def test_provider_name(self):
        """プロバイダー名のテスト。"""
        with patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True):
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
                with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                    mock_model = MagicMock()
                    mock_genai.GenerativeModel.return_value = mock_model

                    service = GeminiTranscriptionService()
                    assert service.provider_name == "gemini"

    @pytest.mark.asyncio
    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    async def test_transcribe_success(self):
        """正常な文字起こしのテスト。"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                # モックの設定
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "Gemini文字起こし結果"
                mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                mock_genai.GenerativeModel.return_value = mock_model

                # ファイルアップロード/削除のモック
                mock_audio_file = MagicMock()
                mock_audio_file.name = "temp_file_id"
                mock_genai.upload_file_async = AsyncMock(return_value=mock_audio_file)
                mock_genai.delete_file_async = AsyncMock()

                service = GeminiTranscriptionService()

                # 一時的なオーディオファイルを作成
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(b"fake audio data")
                    temp_file_path = temp_file.name

                try:
                    result = await service.transcribe(temp_file_path)
                    assert result == "Gemini文字起こし結果"

                    # API呼び出しの確認
                    mock_genai.upload_file_async.assert_called_once_with(path=temp_file_path)
                    mock_model.generate_content_async.assert_called_once()
                    mock_genai.delete_file_async.assert_called_once_with("temp_file_id")
                finally:
                    os.unlink(temp_file_path)

    @pytest.mark.asyncio
    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", False)
    async def test_transcribe_unavailable_service(self):
        """サービス利用不可時のテスト。"""
        service = GeminiTranscriptionService()
        result = await service.transcribe("dummy_path.wav")
        assert result is None

    @pytest.mark.asyncio
    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    async def test_transcribe_resource_exhausted(self):
        """リソース枯渇エラーのテスト。"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                with patch(
                    "src.nescordbot.services.transcription.gemini.google_exceptions"
                ) as mock_exceptions:
                    # ResourceExhausted例外クラスを作成
                    class MockResourceExhausted(Exception):
                        pass

                    mock_exceptions.ResourceExhausted = MockResourceExhausted

                    mock_model = MagicMock()
                    mock_genai.GenerativeModel.return_value = mock_model

                    # ファイルアップロードは成功するが、generate_content_asyncで例外
                    mock_audio_file = MagicMock()
                    mock_audio_file.name = "temp_file_id"
                    mock_genai.upload_file_async = AsyncMock(return_value=mock_audio_file)
                    mock_genai.delete_file_async = AsyncMock()
                    mock_model.generate_content_async = AsyncMock(
                        side_effect=MockResourceExhausted("API quota exceeded")
                    )

                    service = GeminiTranscriptionService()

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                        temp_file.write(b"fake audio data")
                        temp_file_path = temp_file.name

                    try:
                        result = await service.transcribe(temp_file_path)
                        assert result is None

                        # ファイル削除が呼ばれることを確認
                        mock_genai.delete_file_async.assert_called_once_with("temp_file_id")
                    finally:
                        os.unlink(temp_file_path)

    @pytest.mark.asyncio
    @patch("src.nescordbot.services.transcription.gemini.GEMINI_AVAILABLE", True)
    async def test_transcribe_empty_response(self):
        """空のレスポンスのテスト。"""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            with patch("src.nescordbot.services.transcription.gemini.genai") as mock_genai:
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = None  # 空のレスポンス
                mock_model.generate_content_async = AsyncMock(return_value=mock_response)
                mock_genai.GenerativeModel.return_value = mock_model

                mock_audio_file = MagicMock()
                mock_audio_file.name = "temp_file_id"
                mock_genai.upload_file_async = AsyncMock(return_value=mock_audio_file)
                mock_genai.delete_file_async = AsyncMock()

                service = GeminiTranscriptionService()

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_file.write(b"fake audio data")
                    temp_file_path = temp_file.name

                try:
                    result = await service.transcribe(temp_file_path)
                    assert result is None
                finally:
                    os.unlink(temp_file_path)
