"""
Note processing service for AI-powered text processing.

This service provides text formatting and summarization capabilities
using OpenAI's GPT models, extracted from the Voice cog for reusability.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import openai
from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


class NoteProcessingService:
    """Service for processing notes with AI."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the note processing service.

        Args:
            api_key: OpenAI API key. If None, tries to get from environment.
        """
        self.logger = logging.getLogger(__name__)
        self.openai_client: Optional[OpenAI] = None
        self._setup_openai(api_key)

    def _setup_openai(self, api_key: Optional[str] = None) -> None:
        """Setup OpenAI client."""
        key = api_key or os.getenv("OPENAI_API_KEY")
        if key:
            self.openai_client = OpenAI(api_key=key)
            self.logger.info("OpenAI API client initialized")
        else:
            self.logger.warning("OpenAI API key not provided - AI processing disabled")

    async def process_text(
        self,
        text: str,
        processing_type: str = "default",
        custom_prompts: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Process text with AI for formatting and summarization.

        Args:
            text: Input text to process
            processing_type: Type of processing (default, fleeting_note, etc.)
            custom_prompts: Optional custom prompts for formatting and summary

        Returns:
            Dict with 'processed' and 'summary' keys
        """
        if not self.openai_client:
            return {"processed": text, "summary": "AI処理は利用できません"}

        try:
            # Determine prompts based on processing type
            prompts = self._get_prompts(processing_type, custom_prompts)

            # Format text
            processed_text = await self.format_text(text, prompts["format"])

            # Generate summary
            summary = await self.summarize_text(processed_text, prompts["summary"], max_tokens=100)

            return {"processed": processed_text, "summary": summary}

        except TimeoutError:
            self.logger.error("AI処理タイムアウト: 処理時間が30秒を超えました")
            return {"processed": text, "summary": "AI処理がタイムアウトしました"}
        except Exception as e:
            error_message = self._classify_error(e)
            return {"processed": text, "summary": error_message}

    async def format_text(self, text: str, system_prompt: str) -> str:
        """
        Format text using AI.

        Args:
            text: Text to format
            system_prompt: System prompt for formatting

        Returns:
            Formatted text
        """
        if self.openai_client is None:
            return text

        response = await self._call_openai_with_retry(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下のテキストを整形してください:\n\n{text}"},
            ],
            temperature=0.3,
            timeout=30.0,
        )

        return response.choices[0].message.content or text if response.choices else text

    async def summarize_text(
        self, text: str, system_prompt: str = "1行で要約してください。", max_tokens: int = 100
    ) -> str:
        """
        Summarize text using AI.

        Args:
            text: Text to summarize
            system_prompt: System prompt for summarization
            max_tokens: Maximum tokens for summary

        Returns:
            Summary text
        """
        if self.openai_client is None:
            return "要約機能は利用できません"

        response = await self._call_openai_with_retry(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": str(text)},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            timeout=30.0,
        )

        return (
            response.choices[0].message.content or "要約に失敗しました" if response.choices else "要約に失敗しました"
        )

    def _get_prompts(
        self, processing_type: str, custom_prompts: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Get prompts based on processing type.

        Args:
            processing_type: Type of processing
            custom_prompts: Optional custom prompts

        Returns:
            Dict with format and summary prompts
        """
        if custom_prompts:
            return {
                "format": custom_prompts.get("format", self._default_format_prompt()),
                "summary": custom_prompts.get("summary", self._default_summary_prompt()),
            }

        # Default prompts based on processing type
        if processing_type == "fleeting_note":
            return {
                "format": (
                    "あなたはFleeting Note作成アシスタントです。"
                    "提供されたテキストを整理し、後で発展させやすい形に整形してください。"
                    "誤字脱字を修正し、読みやすく構造化してください。"
                ),
                "summary": "このテキストの核心的なアイデアを1行で要約してください。",
            }
        elif processing_type == "voice_transcription":
            return {
                "format": ("あなたは文字起こしされたテキストを整形するアシスタントです。" "誤字脱字を修正し、読みやすく整形してください。"),
                "summary": "1行で要約してください。",
            }
        else:  # default
            return {
                "format": self._default_format_prompt(),
                "summary": self._default_summary_prompt(),
            }

    def _default_format_prompt(self) -> str:
        """Default formatting prompt."""
        return "あなたはテキストを整形するアシスタントです。" "誤字脱字を修正し、読みやすく整形してください。"

    def _default_summary_prompt(self) -> str:
        """Default summary prompt."""
        return "1行で要約してください。"

    def is_available(self) -> bool:
        """Check if the service is available (has OpenAI client)."""
        return self.openai_client is not None

    async def check_api_status(self) -> Dict[str, Any]:
        """OpenAI APIの状態を確認する（診断用）"""
        if not self.openai_client:
            return {
                "available": False,
                "error": "OpenAI client not initialized",
                "suggestion": "OPENAI_API_KEY環境変数を設定してください",
            }

        try:
            # Simple test API call
            response = await self._call_openai_with_retry(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1,
                temperature=0,
            )

            return {
                "available": True,
                "model": "gpt-3.5-turbo",
                "status": "正常",
                "test_response": bool(response.choices),
            }

        except Exception as e:
            error_message = self._classify_error(e)
            return {
                "available": False,
                "error": str(e),
                "classified_error": error_message,
                "suggestion": self._get_error_suggestion(e),
            }

    def _get_error_suggestion(self, error: Exception) -> str:
        """エラーに対する対処法を提案"""
        if isinstance(error, openai.AuthenticationError):
            return "OpenAI APIキーを確認してください: https://platform.openai.com/account/api-keys"
        elif isinstance(error, openai.RateLimitError):
            return "時間を置いて再度試すか、利用プランをアップグレードしてください"
        elif "quota" in str(error).lower() or "credit" in str(error).lower():
            return "OpenAI アカウントの課金設定を確認してください: https://platform.openai.com/account/billing"
        else:
            return "ネットワーク接続とOpenAIサービスの状態を確認してください"

    def _classify_error(self, error: Exception) -> str:
        """Classify OpenAI API error and return appropriate user message."""
        error_str = str(error).lower()

        # Check for specific OpenAI error types
        if isinstance(error, openai.RateLimitError):
            self.logger.warning(f"OpenAI APIレート制限エラー: {error}")
            return "OpenAI APIの利用制限に達しました。時間を置いて再度お試しください。"

        if isinstance(error, openai.AuthenticationError):
            self.logger.error(f"OpenAI API認証エラー: {error}")
            return "OpenAI APIの認証に失敗しました。管理者に確認してください。"

        if isinstance(error, openai.PermissionDeniedError):
            self.logger.error(f"OpenAI API権限エラー: {error}")
            return "OpenAI APIの権限が不足しています。管理者に確認してください。"

        if isinstance(error, openai.BadRequestError):
            self.logger.error(f"OpenAI APIリクエストエラー: {error}")
            return "リクエストに問題があります。管理者に確認してください。"

        # Check for insufficient funds / quota exceeded
        if any(
            keyword in error_str
            for keyword in [
                "insufficient_quota",
                "quota",
                "billing",
                "credit",
                "balance",
                "payment",
                "insufficient funds",
            ]
        ):
            self.logger.error(f"OpenAI APIクレジット不足: {error}")
            return "OpenAI APIのクレジットが不足している可能性があります。管理者に確認してください。"

        # Legacy rate limit detection
        if any(keyword in error_str for keyword in ["rate_limit", "429", "too many requests"]):
            self.logger.warning(f"OpenAI APIレート制限（レガシー検出）: {error}")
            return "OpenAI APIの利用制限に達しました。時間を置いて再度お試しください。"

        # Generic network/connection errors
        if any(
            keyword in error_str for keyword in ["connection", "network", "timeout", "unreachable"]
        ):
            self.logger.error(f"OpenAI API接続エラー: {error}")
            return "OpenAI APIとの接続に問題があります。しばらく時間を置いて再度お試しください。"

        # Unknown error
        self.logger.error(f"OpenAI API未知のエラー: {error}")
        return "AI処理中にエラーが発生しました。管理者に確認してください。"

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=3),
        retry=retry_if_exception_type(
            (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError)
        ),
        before_sleep=lambda retry_state: logging.getLogger(__name__).info(
            f"OpenAI APIリトライ {retry_state.attempt_number}/2"
        ),
    )
    async def _call_openai_with_retry(self, **kwargs) -> Any:
        """OpenAI API呼び出し（リトライ付き）"""
        if self.openai_client is None:
            raise RuntimeError("OpenAI client not initialized")

        client = self.openai_client  # Type narrowing for mypy
        return await asyncio.to_thread(lambda: client.chat.completions.create(**kwargs))
