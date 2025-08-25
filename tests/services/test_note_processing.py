"""
Tests for note processing service.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.services.note_processing import NoteProcessingService


class TestNoteProcessingService:
    """Test cases for NoteProcessingService."""

    @pytest.fixture
    def service_with_api(self):
        """Create service with mocked API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = NoteProcessingService()
            # Mock the OpenAI client
            service.openai_client = MagicMock()
            return service

    @pytest.fixture
    def service_no_api(self):
        """Create service without API key."""
        with patch.dict(os.environ, {}, clear=True):
            return NoteProcessingService()

    def test_init_with_api_key(self):
        """Test initialization with API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            service = NoteProcessingService()
            assert service.is_available()

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict(os.environ, {}, clear=True):
            service = NoteProcessingService()
            assert not service.is_available()

    def test_init_with_explicit_api_key(self):
        """Test initialization with explicit API key."""
        service = NoteProcessingService(api_key="test-key")
        assert service.openai_client is not None

    @pytest.mark.asyncio
    async def test_process_text_success(self, service_with_api):
        """Test successful text processing."""
        # Mock OpenAI responses
        format_response = MagicMock()
        format_response.choices = [MagicMock()]
        format_response.choices[0].message.content = "整形されたテキスト"

        summary_response = MagicMock()
        summary_response.choices = [MagicMock()]
        summary_response.choices[0].message.content = "要約テキスト"

        service_with_api.openai_client.chat.completions.create = MagicMock(
            side_effect=[format_response, summary_response]
        )

        result = await service_with_api.process_text("元のテキスト")

        assert result["processed"] == "整形されたテキスト"
        assert result["summary"] == "要約テキスト"
        assert service_with_api.openai_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_process_text_no_client(self, service_no_api):
        """Test text processing without OpenAI client."""
        result = await service_no_api.process_text("テキスト")

        assert result["processed"] == "テキスト"
        assert result["summary"] == "AI処理は利用できません"

    @pytest.mark.asyncio
    async def test_process_text_timeout(self, service_with_api):
        """Test text processing timeout."""
        service_with_api.openai_client.chat.completions.create = MagicMock(
            side_effect=TimeoutError("Timeout")
        )

        with patch.object(service_with_api, "logger") as mock_logger:
            result = await service_with_api.process_text("テキスト")

            assert result["processed"] == "テキスト"
            assert result["summary"] == "AI処理がタイムアウトしました"
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_text_rate_limit(self, service_with_api):
        """Test text processing rate limit error."""
        service_with_api.openai_client.chat.completions.create = MagicMock(
            side_effect=Exception("rate_limit_exceeded")
        )

        with patch.object(service_with_api, "logger") as mock_logger:
            result = await service_with_api.process_text("テキスト")

            assert result["processed"] == "テキスト"
            assert result["summary"] == "OpenAI APIの利用制限に達しました。時間を置いて再度お試しください。"
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_text_general_error(self, service_with_api):
        """Test text processing general error."""
        service_with_api.openai_client.chat.completions.create = MagicMock(
            side_effect=Exception("General error")
        )

        with patch.object(service_with_api, "logger") as mock_logger:
            result = await service_with_api.process_text("テキスト")

            assert result["processed"] == "テキスト"
            assert result["summary"] == "AI処理中にエラーが発生しました。管理者に確認してください。"
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_text_success(self, service_with_api):
        """Test successful text formatting."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "整形されたテキスト"

        service_with_api.openai_client.chat.completions.create = MagicMock(
            return_value=mock_response
        )

        result = await service_with_api.format_text("元のテキスト", "システムプロンプト")

        assert result == "整形されたテキスト"
        service_with_api.openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_text_no_client(self, service_no_api):
        """Test text formatting without client."""
        result = await service_no_api.format_text("テキスト", "プロンプト")
        assert result == "テキスト"

    @pytest.mark.asyncio
    async def test_summarize_text_success(self, service_with_api):
        """Test successful text summarization."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "要約テキスト"

        service_with_api.openai_client.chat.completions.create = MagicMock(
            return_value=mock_response
        )

        result = await service_with_api.summarize_text("元のテキスト")

        assert result == "要約テキスト"
        service_with_api.openai_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_text_no_client(self, service_no_api):
        """Test text summarization without client."""
        result = await service_no_api.summarize_text("テキスト")
        assert result == "要約機能は利用できません"

    def test_get_prompts_default(self, service_with_api):
        """Test getting default prompts."""
        prompts = service_with_api._get_prompts("default")
        assert "format" in prompts
        assert "summary" in prompts

    def test_get_prompts_fleeting_note(self, service_with_api):
        """Test getting fleeting note prompts."""
        prompts = service_with_api._get_prompts("fleeting_note")
        assert "Fleeting Note" in prompts["format"]
        assert "核心的なアイデア" in prompts["summary"]

    def test_get_prompts_voice_transcription(self, service_with_api):
        """Test getting voice transcription prompts."""
        prompts = service_with_api._get_prompts("voice_transcription")
        assert "文字起こし" in prompts["format"]
        assert "1行で要約" in prompts["summary"]

    def test_get_prompts_custom(self, service_with_api):
        """Test getting custom prompts."""
        custom_prompts = {"format": "カスタム整形プロンプト", "summary": "カスタム要約プロンプト"}
        prompts = service_with_api._get_prompts("default", custom_prompts)
        assert prompts["format"] == "カスタム整形プロンプト"
        assert prompts["summary"] == "カスタム要約プロンプト"

    @pytest.mark.asyncio
    async def test_process_text_with_custom_prompts(self, service_with_api):
        """Test text processing with custom prompts."""
        # Mock OpenAI responses
        format_response = MagicMock()
        format_response.choices = [MagicMock()]
        format_response.choices[0].message.content = "カスタム整形結果"

        summary_response = MagicMock()
        summary_response.choices = [MagicMock()]
        summary_response.choices[0].message.content = "カスタム要約結果"

        service_with_api.openai_client.chat.completions.create = MagicMock(
            side_effect=[format_response, summary_response]
        )

        custom_prompts = {"format": "カスタム整形プロンプト", "summary": "カスタム要約プロンプト"}

        result = await service_with_api.process_text("テスト", custom_prompts=custom_prompts)

        assert result["processed"] == "カスタム整形結果"
        assert result["summary"] == "カスタム要約結果"

    @pytest.mark.asyncio
    async def test_process_text_fleeting_note_type(self, service_with_api):
        """Test text processing with fleeting_note type."""
        # Mock OpenAI responses
        format_response = MagicMock()
        format_response.choices = [MagicMock()]
        format_response.choices[0].message.content = "Fleeting Note整形結果"

        summary_response = MagicMock()
        summary_response.choices = [MagicMock()]
        summary_response.choices[0].message.content = "核心アイデア要約"

        service_with_api.openai_client.chat.completions.create = MagicMock(
            side_effect=[format_response, summary_response]
        )

        result = await service_with_api.process_text("テスト", processing_type="fleeting_note")

        assert result["processed"] == "Fleeting Note整形結果"
        assert result["summary"] == "核心アイデア要約"
