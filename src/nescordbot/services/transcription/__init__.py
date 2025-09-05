"""音声文字起こしサービスパッケージ。

環境変数 TRANSCRIPTION_PROVIDER に応じて適切なサービスを提供する。
"""

import logging
import os

from .base import TranscriptionService
from .gemini import GeminiTranscriptionService
from .whisper import WhisperTranscriptionService

logger = logging.getLogger(__name__)


def get_transcription_service() -> TranscriptionService:
    """
    環境変数に応じて適切な文字起こしサービスを返すファクトリ関数。

    環境変数 TRANSCRIPTION_PROVIDER で以下のプロバイダーを指定可能:
    - "whisper": OpenAI Whisper API (デフォルト)
    - "gemini": Google Gemini API

    Returns:
        設定されたTranscriptionServiceインスタンス
    """
    provider = os.getenv("TRANSCRIPTION_PROVIDER", "whisper").lower()

    logger.info(f"文字起こしプロバイダーとして '{provider}' を選択しました。")

    if provider == "gemini":
        gemini_service = GeminiTranscriptionService()
        if gemini_service.is_available():
            logger.info("Gemini文字起こしサービスを使用します")
            return gemini_service
        else:
            logger.warning("Geminiサービスが利用不可。Whisperにフォールバックします")
            fallback_service = WhisperTranscriptionService()
            if fallback_service.is_available():
                return fallback_service
            else:
                logger.error("全ての文字起こしサービスが利用不可")
                return fallback_service  # エラーハンドリングは呼び出し側で

    elif provider == "whisper":
        service = WhisperTranscriptionService()
        logger.info(f"Whisper文字起こしサービスを使用します (利用可能: {service.is_available()})")
        return service

    else:
        logger.warning(f"無効なプロバイダー '{provider}' が指定されました。デフォルトのWhisperを使用します。")
        return WhisperTranscriptionService()


# パッケージの公開API
__all__ = [
    "TranscriptionService",
    "WhisperTranscriptionService",
    "GeminiTranscriptionService",
    "get_transcription_service",
]
