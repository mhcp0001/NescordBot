"""TranscriptionService基底クラスのテスト。"""

from unittest.mock import MagicMock

import pytest

from src.nescordbot.services.transcription.base import TranscriptionService


class ConcreteTranscriptionService(TranscriptionService):
    """テスト用の具象クラス。"""

    def __init__(self, available: bool = True):
        self._available = available

    async def transcribe(self, audio_path: str):
        if not self.is_available():
            return None
        return f"transcribed: {audio_path}"

    def is_available(self) -> bool:
        return self._available


class TestTranscriptionService:
    """TranscriptionService基底クラスのテスト。"""

    @pytest.mark.asyncio
    async def test_transcribe_interface(self):
        """transcribeメソッドが正常に実装されているかテスト。"""
        service = ConcreteTranscriptionService()
        result = await service.transcribe("test_audio.wav")
        assert result == "transcribed: test_audio.wav"

    def test_is_available_default(self):
        """is_availableのデフォルト実装テスト。"""
        service = ConcreteTranscriptionService()
        assert service.is_available() is True

    def test_is_available_false(self):
        """is_availableがFalseの場合のテスト。"""
        service = ConcreteTranscriptionService(available=False)
        assert service.is_available() is False

    @pytest.mark.asyncio
    async def test_transcribe_unavailable(self):
        """サービス利用不可時のtranscribeテスト。"""
        service = ConcreteTranscriptionService(available=False)
        result = await service.transcribe("test_audio.wav")
        assert result is None

    def test_provider_name_property(self):
        """provider_nameプロパティのテスト。"""
        service = ConcreteTranscriptionService()
        # ConcreteTranscriptionService -> concrete
        assert service.provider_name == "concrete"
