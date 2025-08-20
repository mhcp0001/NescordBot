"""
ObsidianGitHub統合サービス

Discord→GitHub→Obsidianの統合フローを管理するサービス
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ..config import BotConfig
from ..security import SecurityValidator
from .batch_processor import BatchProcessor

logger = logging.getLogger(__name__)


class ObsidianSyncStatus(BaseModel):
    """Obsidian同期ステータス"""

    request_id: str = Field(description="リクエストID")
    status: str = Field(description="処理ステータス")
    created_at: datetime = Field(description="作成日時")
    updated_at: datetime = Field(description="更新日時")
    error_message: Optional[str] = Field(default=None, description="エラーメッセージ")
    github_url: Optional[str] = Field(default=None, description="GitHub URL")
    file_path: str = Field(description="ファイルパス")


class ObsidianGitHubService:
    """
    ObsidianGitHub統合サービス

    Discord音声→テキスト変換→Obsidianファイル→GitHub同期の
    統合フローを管理する
    """

    def __init__(
        self,
        config: BotConfig,
        batch_processor: BatchProcessor,
        security_validator: SecurityValidator,
    ):
        self.config = config
        self.batch_processor = batch_processor
        self.security_validator = security_validator

        self._initialized = False
        self._processing_lock = asyncio.Lock()
        self._status_cache: Dict[str, ObsidianSyncStatus] = {}

        logger.info("ObsidianGitHubService初期化完了")

    async def initialize(self) -> None:
        """サービスを初期化"""
        if self._initialized:
            return

        logger.info("ObsidianGitHubService初期化開始")

        # バッチプロセッサの初期化
        await self.batch_processor.initialize()

        self._initialized = True
        logger.info("ObsidianGitHubService初期化完了")

    async def save_to_obsidian(
        self,
        filename: str,
        content: str,
        directory: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Obsidianファイルをキューに追加

        Args:
            filename: ファイル名
            content: ファイル内容
            directory: ディレクトリ（オプション）
            metadata: メタデータ（オプション）

        Returns:
            request_id: リクエストID

        Raises:
            ValueError: バリデーションエラー
            RuntimeError: サービス未初期化
        """
        if not self._initialized:
            raise RuntimeError("サービスが初期化されていません")

        # セキュリティ検証
        try:
            sanitized_filename = self.security_validator.sanitize_filename(filename)
            if not sanitized_filename or sanitized_filename != filename:
                raise ValueError(f"無効なファイル名: {filename}")
        except Exception:
            raise ValueError(f"無効なファイル名: {filename}")

        try:
            self.security_validator.validate_discord_content(content)
        except Exception:
            raise ValueError("無効なコンテンツが検出されました")

        if directory:
            try:
                sanitized_path = self.security_validator.validate_file_path(directory)
                if not sanitized_path or sanitized_path != directory:
                    raise ValueError(f"無効なディレクトリパス: {directory}")
            except Exception:
                raise ValueError(f"無効なディレクトリパス: {directory}")

        # リクエストID生成
        request_id = str(uuid4())

        # バッチプロセッサ経由でキューに追加
        queue_id = await self.batch_processor.enqueue_file_request(
            filename=filename,
            content=content,
            directory=directory or "notes",
            metadata=metadata or {},
            idempotency_key=request_id,
        )

        # ステータス追加
        status = ObsidianSyncStatus(
            request_id=request_id,
            status="queued",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            file_path=f"{directory or 'notes'}/{filename}",
        )
        self._status_cache[request_id] = status

        logger.info(f"Obsidianファイル保存リクエスト追加: {request_id} -> {queue_id}")
        return request_id

    async def get_status(self, request_id: str) -> Optional[ObsidianSyncStatus]:
        """
        リクエストステータスを取得

        Args:
            request_id: リクエストID

        Returns:
            ステータス情報
        """
        return self._status_cache.get(request_id)

    async def list_recent_requests(self, limit: int = 20) -> List[ObsidianSyncStatus]:
        """
        最近のリクエスト一覧を取得

        Args:
            limit: 取得件数上限

        Returns:
            ステータス一覧
        """
        statuses = list(self._status_cache.values())
        statuses.sort(key=lambda x: x.created_at, reverse=True)
        return statuses[:limit]

    async def get_processing_statistics(self) -> Dict[str, Any]:
        """
        処理統計を取得

        Returns:
            統計情報
        """
        if not self._initialized:
            return {"error": "サービスが初期化されていません"}

        try:
            # バッチプロセッサ統計
            batch_stats = await self.batch_processor.get_processing_status()

            # ステータス統計
            status_counts: Dict[str, int] = {}
            for status in self._status_cache.values():
                status_counts[status.status] = status_counts.get(status.status, 0) + 1

            return {
                "batch_processor": batch_stats,
                "status_counts": status_counts,
                "total_requests": len(self._status_cache),
            }

        except Exception as e:
            logger.error(f"統計取得エラー: {e}")
            return {"error": str(e)}

    async def cleanup_old_status(self, days: int = 7) -> int:
        """
        古いステータスをクリーンアップ

        Args:
            days: 保持日数

        Returns:
            削除件数
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        removed_count = 0

        to_remove = []
        for request_id, status in self._status_cache.items():
            if status.created_at < cutoff_date:
                to_remove.append(request_id)

        for request_id in to_remove:
            del self._status_cache[request_id]
            removed_count += 1

        logger.info(f"古いステータス削除: {removed_count}件")
        return removed_count

    async def start_processing(self) -> None:
        """バッチ処理を開始"""
        if not self._initialized:
            await self.initialize()

        await self.batch_processor.start_processing()
        logger.info("Obsidianバッチ処理開始")

    async def stop_processing(self) -> None:
        """バッチ処理を停止"""
        await self.batch_processor.stop_processing()
        logger.info("Obsidianバッチ処理停止")

    async def shutdown(self) -> None:
        """サービスをシャットダウン"""
        logger.info("ObsidianGitHubService終了開始")

        await self.stop_processing()

        self._initialized = False
        logger.info("ObsidianGitHubService終了完了")
