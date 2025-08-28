"""音声文字起こしサービスの抽象基底クラス。"""

from abc import ABC, abstractmethod
from typing import Optional


class TranscriptionService(ABC):
    """音声文字起こしサービスの抽象ベースクラス。

    異なる音声認識APIを統一的に扱うためのインターフェースを提供する。
    """

    @abstractmethod
    async def transcribe(self, audio_path: str) -> Optional[str]:
        """
        指定された音声ファイルを文字起こしする。

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            文字起こしされたテキスト。失敗した場合はNone。
        """
        pass

    def is_available(self) -> bool:
        """
        サービスが利用可能かどうかを返す。

        Returns:
            サービスが利用可能な場合True
        """
        return True

    @property
    def provider_name(self) -> str:
        """プロバイダー名を返す。"""
        return self.__class__.__name__.replace("TranscriptionService", "").lower()
