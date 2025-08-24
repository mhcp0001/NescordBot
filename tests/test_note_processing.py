"""Tests for NoteProcessingService."""

from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from nescordbot.services.note_processing import NoteProcessingService


class TestNoteProcessingService:
    """Test NoteProcessingService functionality."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Test response"
        client.chat.completions.create.return_value = response
        return client

    @pytest.fixture
    def service_with_client(self, mock_openai_client):
        """Create service with mock client."""
        with patch("nescordbot.services.note_processing.OpenAI", return_value=mock_openai_client):
            service = NoteProcessingService(api_key="test-key")
        return service

    @pytest.fixture
    def service_without_client(self):
        """Create service without API key."""
        with patch.dict("os.environ", {}, clear=True):
            return NoteProcessingService(api_key=None)

    def test_init_with_api_key(self, mock_openai_client):
        """Test initialization with API key."""
        with patch("nescordbot.services.note_processing.OpenAI", return_value=mock_openai_client):
            service = NoteProcessingService(api_key="test-key")
        assert service.openai_client == mock_openai_client
        assert service.is_available()

    def test_init_without_api_key(self):
        """Test initialization without API key."""
        with patch.dict("os.environ", {}, clear=True):
            service = NoteProcessingService(api_key=None)
        assert service.openai_client is None
        assert not service.is_available()

    @pytest.mark.asyncio
    async def test_process_text_success(self, service_with_client):
        """Test successful text processing."""
        result = await service_with_client.process_text("Test text")

        assert result["processed"] == "Test response"
        assert result["summary"] == "Test response"

    @pytest.mark.asyncio
    async def test_process_text_without_client(self, service_without_client):
        """Test text processing without OpenAI client."""
        result = await service_without_client.process_text("Test text")

        assert result["processed"] == "Test text"
        assert result["summary"] == "AI処理は利用できません"

    @pytest.mark.asyncio
    async def test_process_text_rate_limit_error(self, service_with_client):
        """Test handling of RateLimitError."""
        service_with_client.openai_client.chat.completions.create.side_effect = (
            openai.RateLimitError(message="Rate limit exceeded", response=MagicMock(), body=None)
        )

        result = await service_with_client.process_text("Test text")

        assert result["processed"] == "Test text"
        assert "利用制限に達しました" in result["summary"]

    @pytest.mark.asyncio
    async def test_process_text_authentication_error(self, service_with_client):
        """Test handling of AuthenticationError."""
        service_with_client.openai_client.chat.completions.create.side_effect = (
            openai.AuthenticationError(message="Invalid API key", response=MagicMock(), body=None)
        )

        result = await service_with_client.process_text("Test text")

        assert result["processed"] == "Test text"
        assert "認証に失敗しました" in result["summary"]

    @pytest.mark.asyncio
    async def test_process_text_quota_error(self, service_with_client):
        """Test handling of quota/credit errors."""
        service_with_client.openai_client.chat.completions.create.side_effect = Exception(
            "insufficient_quota: You exceeded your current quota"
        )

        result = await service_with_client.process_text("Test text")

        assert result["processed"] == "Test text"
        assert "クレジットが不足している" in result["summary"]

    def test_classify_error_rate_limit(self, service_with_client):
        """Test error classification for RateLimitError."""
        error = openai.RateLimitError(message="Rate limit", response=MagicMock(), body=None)
        result = service_with_client._classify_error(error)
        assert "利用制限に達しました" in result

    def test_classify_error_authentication(self, service_with_client):
        """Test error classification for AuthenticationError."""
        error = openai.AuthenticationError(message="Invalid key", response=MagicMock(), body=None)
        result = service_with_client._classify_error(error)
        assert "認証に失敗しました" in result

    def test_classify_error_quota(self, service_with_client):
        """Test error classification for quota errors."""
        error = Exception("insufficient_quota exceeded")
        result = service_with_client._classify_error(error)
        assert "クレジットが不足している" in result

    def test_classify_error_generic(self, service_with_client):
        """Test error classification for generic errors."""
        error = Exception("Some unknown error")
        result = service_with_client._classify_error(error)
        assert "管理者に確認してください" in result

    @pytest.mark.asyncio
    async def test_check_api_status_no_client(self):
        """Test API status check without client."""
        with patch.dict("os.environ", {}, clear=True):
            service = NoteProcessingService(api_key=None)
            result = await service.check_api_status()

            assert not result["available"]
            assert "not initialized" in result["error"]
            assert "OPENAI_API_KEY" in result["suggestion"]

    @pytest.mark.asyncio
    async def test_check_api_status_success(self, service_with_client):
        """Test successful API status check."""
        result = await service_with_client.check_api_status()

        assert result["available"]
        assert result["model"] == "gpt-3.5-turbo"
        assert result["status"] == "正常"
        assert result["test_response"]

    @pytest.mark.asyncio
    async def test_check_api_status_error(self, service_with_client):
        """Test API status check with error."""
        service_with_client.openai_client.chat.completions.create.side_effect = (
            openai.AuthenticationError(message="Invalid key", response=MagicMock(), body=None)
        )

        result = await service_with_client.check_api_status()

        assert not result["available"]
        assert "Invalid key" in result["error"]
        assert "認証に失敗しました" in result["classified_error"]
        assert "APIキーを確認してください" in result["suggestion"]
