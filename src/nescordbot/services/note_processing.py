"""
Note processing service for AI-powered text processing.

This service provides text formatting and summarization capabilities
using OpenAI's GPT models, extracted from the Voice cog for reusability.
"""

import asyncio
import logging
import os
from typing import Dict, Optional

from openai import OpenAI


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
            # Rate limit error check
            if "rate_limit" in str(e).lower() or "429" in str(e):
                self.logger.warning(f"OpenAI APIレート制限: {e}")
                return {"processed": text, "summary": "APIレート制限により処理できません"}
            else:
                self.logger.error(f"AI処理エラー: {e}")
                return {"processed": text, "summary": "AI処理中にエラーが発生しました"}

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

        client = self.openai_client  # Type guard for mypy
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"以下のテキストを整形してください:\n\n{text}"},
                ],
                temperature=0.3,
                timeout=30.0,
            )
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

        client = self.openai_client  # Type guard for mypy
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": str(text)},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
                timeout=30.0,
            )
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
