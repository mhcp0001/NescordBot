"""Google Gemini APIを使用した文字起こしサービス。"""

import logging
import os
from typing import Optional

try:
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .base import TranscriptionService

logger = logging.getLogger(__name__)


class GeminiTranscriptionService(TranscriptionService):
    """Google Gemini APIを使用した文字起こしサービス。"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")

        if not GEMINI_AVAILABLE:
            logger.warning("google-generativeai パッケージがインストールされていません。")
            self.model = None
            return

        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel("gemini-1.5-pro-latest")
                logger.info("Gemini Audio API が初期化されました")
            except Exception as e:
                logger.error(f"Gemini API初期化エラー: {e}")
                self.model = None
        else:
            self.model = None
            logger.warning("GEMINI_API_KEYが設定されていません。Geminiサービスは利用できません。")

    def is_available(self) -> bool:
        """Gemini APIが利用可能かチェック。"""
        return GEMINI_AVAILABLE and self.model is not None

    async def transcribe(self, audio_path: str) -> Optional[str]:
        """
        音声ファイルをGemini APIで文字起こし。

        Args:
            audio_path: 音声ファイルのパス

        Returns:
            文字起こしされたテキスト、失敗時はNone
        """
        if not self.is_available():
            logger.error("Geminiサービスが利用不可のため、文字起こしをスキップします。")
            return None

        audio_file = None
        try:
            logger.info(f"Geminiにアップロードする音声ファイル: {audio_path}")

            # 音声ファイルをアップロード
            audio_file = await genai.upload_file_async(path=audio_path)

            # 文字起こしプロンプト
            prompt = """以下の音声ファイルを日本語で正確に文字起こししてください。

音声の内容をそのまま文字に起こしてください。話し言葉や方言、間投詞も含めて忠実に転写してください。"""

            # 文字起こし実行
            if self.model is not None:
                response = await self.model.generate_content_async([prompt, audio_file])

                if response.text:
                    logger.info(f"Gemini文字起こし完了: {len(response.text)}文字")
                    return str(response.text)
                else:
                    logger.warning("Geminiから空のレスポンスが返されました")
                    return None
            else:
                logger.warning("Geminiから空のレスポンスが返されました")
                return None

        except google_exceptions.ResourceExhausted:
            logger.warning("Gemini APIのレート制限に達しました。")
            return None
        except google_exceptions.InvalidArgument as e:
            logger.error(f"Gemini API無効な引数エラー: {e}")
            return None
        except Exception as e:
            logger.error(f"Gemini APIで予期せぬエラーが発生しました: {e}")
            return None
        finally:
            # アップロードしたファイルをクリーンアップ
            if audio_file:
                try:
                    await genai.delete_file_async(audio_file.name)
                    logger.debug(f"Geminiアップロードファイルを削除: {audio_file.name}")
                except Exception as del_e:
                    logger.warning(f"Geminiファイル削除エラー: {del_e}")
