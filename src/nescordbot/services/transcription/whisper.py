"""OpenAI Whisper APIを使用した文字起こしサービス。"""

import asyncio
import logging
import os
from typing import Optional

from openai import OpenAI

from .base import TranscriptionService

logger = logging.getLogger(__name__)


class WhisperTranscriptionService(TranscriptionService):
    """OpenAI Whisper APIを使用した文字起こしサービス。"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client: Optional[OpenAI]
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("OPENAI_API_KEYが設定されていません。Whisperサービスは利用できません。")

    def is_available(self) -> bool:
        """OpenAI APIキーが設定されているかチェック。"""
        return self.client is not None

    async def transcribe(self, audio_path: str) -> Optional[str]:
        """
        音声ファイルをOpenAI Whisper APIで文字起こし。

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            文字起こしされたテキスト、失敗時はNone
        """
        if not self.is_available():
            logger.error("Whisperサービスが利用不可のため、文字起こしをスキップします。")
            return None

        try:
            if self.client is not None:
                with open(audio_path, "rb") as audio_file:
                    transcript = await asyncio.to_thread(
                        self.client.audio.transcriptions.create,
                        model="whisper-1",
                        file=audio_file,
                        language="ja",
                        timeout=30.0,
                    )
            else:
                return None

            return transcript.text if transcript else None

        except TimeoutError:
            logger.error("音声認識タイムアウト: 処理時間が30秒を超えました")
            return None
        except Exception as e:
            # レート制限エラーのチェック
            if "rate_limit" in str(e).lower() or "429" in str(e):
                logger.warning(f"OpenAI APIレート制限: {e}")
            else:
                logger.error(f"音声認識エラー: {e}")
            return None
