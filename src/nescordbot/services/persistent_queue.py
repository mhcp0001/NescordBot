"""
Persistent Queue Service for Obsidian file processing.

This module provides SQLite-backed queue functionality with automatic recovery
and dead letter queue support for failed tasks.
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .database import DatabaseService


@dataclass
class FileRequest:
    """Represents a file processing request."""

    filename: str
    content: str
    directory: str
    metadata: Dict[str, Any]
    created_at: datetime
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileRequest":
        """Create FileRequest from dictionary."""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class PersistentQueue:
    """SQLite-backed persistent queue for Obsidian file processing."""

    def __init__(self, db_service: DatabaseService, config: Any = None):
        """Initialize the persistent queue.

        Args:
            db_service: Database service instance
            config: Configuration object with queue settings
        """
        self.db_service = db_service
        self.logger = logging.getLogger(__name__)

        # Configuration with defaults
        self.batch_size = getattr(config, "obsidian_batch_size", 10)
        self.batch_timeout = getattr(config, "obsidian_batch_timeout", 30.0)
        self.max_queue_size = getattr(config, "obsidian_max_queue_size", 1000)
        self.max_retry_count = getattr(config, "obsidian_max_retry_count", 5)

        # 永続化キューとインメモリキューの2層構造
        self._memory_queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self.max_queue_size)
        self._processing_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._batch_count = 0
        self._queue_table = "obsidian_file_queue"
        self._dlq_table = "obsidian_dead_letter_queue"

    async def initialize(self) -> None:
        """永続化キューテーブルの初期化"""
        await self._create_queue_tables()
        await self._recover_pending_tasks()

    def set_git_service(self, git_service) -> None:
        """Set GitOperationService for actual file processing.

        Args:
            git_service: GitOperationService instance for GitHub operations
        """
        self._git_service = git_service
        self.logger.info("GitOperationService injected into PersistentQueue")

    async def _create_queue_tables(self) -> None:
        """SQLiteキューテーブルの作成"""
        queue_schema = """
        CREATE TABLE IF NOT EXISTS obsidian_file_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            priority INTEGER DEFAULT 0 NOT NULL,
            retry_count INTEGER DEFAULT 0 NOT NULL,
            status TEXT DEFAULT 'pending' NOT NULL
                CHECK(status IN ('pending', 'processing', 'completed', 'failed')),
            idempotency_key TEXT UNIQUE,
            file_request_json TEXT NOT NULL,
            last_error TEXT,
            batch_id INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_queue_processing
        ON obsidian_file_queue (status, priority, created_at);

        CREATE TABLE IF NOT EXISTS obsidian_dead_letter_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_queue_id INTEGER,
            created_at TIMESTAMP NOT NULL,
            moved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            retry_count INTEGER NOT NULL,
            file_request_json TEXT NOT NULL,
            last_error TEXT NOT NULL
        );
        """

        async with self.db_service.get_connection() as conn:
            await conn.executescript(queue_schema)
            await conn.commit()

    async def _recover_pending_tasks(self) -> None:
        """Bot再起動時の未処理タスク復旧"""
        async with self.db_service.get_connection() as conn:
            # 5分以上前から processing 状態のタスクを pending に戻す
            await conn.execute(
                """
                UPDATE obsidian_file_queue
                SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'processing'
                AND datetime(updated_at, '+5 minutes') < datetime('now')
            """
            )

            # pending タスクをメモリキューに復元
            cursor = await conn.execute(
                """
                SELECT id FROM obsidian_file_queue
                WHERE status = 'pending'
                ORDER BY priority DESC, created_at ASC
                LIMIT ?
            """,
                (self.max_queue_size,),
            )

            pending_ids = await cursor.fetchall()
            recovered_count = 0

            for (queue_id,) in pending_ids:
                try:
                    self._memory_queue.put_nowait(str(queue_id))
                    recovered_count += 1
                except asyncio.QueueFull:
                    # メモリキューが満杯の場合は後で処理される
                    break

            await conn.commit()

            if recovered_count > 0:
                self.logger.info(f"Recovered {recovered_count} pending tasks to memory queue")

    async def enqueue(
        self, file_request: FileRequest, idempotency_key: Optional[str] = None
    ) -> int:
        """キューにファイル処理リクエストを追加"""
        if idempotency_key is None:
            import hashlib

            hash_input = (
                f"{file_request.filename}:{file_request.directory}:"
                f"{file_request.created_at.isoformat()}"
            )
            content_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
            idempotency_key = content_hash

        file_request_json = json.dumps(file_request.to_dict())

        async with self.db_service.get_connection() as conn:
            try:
                cursor = await conn.execute(
                    """
                    INSERT INTO obsidian_file_queue
                    (idempotency_key, file_request_json, priority)
                    VALUES (?, ?, ?)
                """,
                    (idempotency_key, file_request_json, file_request.priority),
                )

                queue_id = cursor.lastrowid
                await conn.commit()

                if queue_id is None:
                    raise RuntimeError("Failed to get queue ID from database")

                # メモリキューにも追加（可能な場合）
                try:
                    self._memory_queue.put_nowait(str(queue_id))
                    self.logger.debug(f"Added queue item {queue_id} to memory queue")
                except asyncio.QueueFull:
                    self.logger.warning(
                        f"Memory queue full, item {queue_id} will be processed later"
                    )

                return int(queue_id)

            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    # 重複リクエストの場合は既存のIDを返す
                    cursor = await conn.execute(
                        """
                        SELECT id FROM obsidian_file_queue
                        WHERE idempotency_key = ?
                    """,
                        (idempotency_key,),
                    )

                    result = await cursor.fetchone()
                    if result:
                        existing_id = result[0]
                        self.logger.info(
                            f"Duplicate request ignored, existing queue ID: {existing_id}"
                        )
                        return int(existing_id)

                raise

    async def _load_file_requests(self, queue_ids: List[str]) -> List[FileRequest]:
        """キューIDからFileRequestオブジェクトを復元"""
        file_requests = []

        async with self.db_service.get_connection() as conn:
            placeholders = ",".join(["?" for _ in queue_ids])
            cursor = await conn.execute(
                f"""
                SELECT id, file_request_json FROM obsidian_file_queue
                WHERE id IN ({placeholders}) AND status = 'pending'
            """,
                queue_ids,
            )

            rows = await cursor.fetchall()

            for queue_id, file_request_json in rows:
                try:
                    data = json.loads(file_request_json)
                    file_request = FileRequest.from_dict(data)
                    file_requests.append(file_request)
                except Exception as e:
                    self.logger.error(f"Failed to deserialize queue item {queue_id}: {e}")
                    # 破損したアイテムを failed にマーク
                    await self._update_queue_status([str(queue_id)], "failed", str(e))

        return file_requests

    async def _update_queue_status(
        self,
        queue_ids: List[str],
        status: str,
        error_message: Optional[str] = None,
        batch_id: Optional[int] = None,
    ) -> None:
        """キューアイテムのステータスを更新"""
        async with self.db_service.get_connection() as conn:
            placeholders = ",".join(["?" for _ in queue_ids])
            update_parts = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
            params = [status]

            if error_message:
                update_parts.append("last_error = ?")
                params.append(error_message)

            if batch_id is not None:
                update_parts.append("batch_id = ?")
                params.append(str(batch_id))

            params.extend(queue_ids)

            await conn.execute(
                f"""
                UPDATE obsidian_file_queue
                SET {', '.join(update_parts)}
                WHERE id IN ({placeholders})
            """,
                params,
            )

            await conn.commit()

    async def _handle_batch_failure(self, queue_ids: List[str], error_message: str) -> None:
        """バッチ処理失敗時の処理"""
        async with self.db_service.get_connection() as conn:
            # retry_countを増やす
            placeholders = ",".join(["?" for _ in queue_ids])
            await conn.execute(
                f"""
                UPDATE obsidian_file_queue
                SET retry_count = retry_count + 1,
                    status = 'pending',
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """,
                [error_message] + queue_ids,
            )

            # 最大リトライ回数を超えたアイテムをDLQに移動
            cursor = await conn.execute(
                f"""
                SELECT id, file_request_json, retry_count
                FROM obsidian_file_queue
                WHERE id IN ({placeholders}) AND retry_count >= ?
            """,
                queue_ids + [self.max_retry_count],
            )

            dlq_items = await cursor.fetchall()

            for queue_id, file_request_json, retry_count in dlq_items:
                # DLQに移動
                await conn.execute(
                    """
                    INSERT INTO obsidian_dead_letter_queue
                    (original_queue_id, created_at, retry_count, file_request_json, last_error)
                    VALUES (?, datetime('now'), ?, ?, ?)
                """,
                    (queue_id, retry_count, file_request_json, error_message),
                )

                # 元のキューから削除
                await conn.execute("DELETE FROM obsidian_file_queue WHERE id = ?", (queue_id,))

                self.logger.warning(
                    f"Moved queue item {queue_id} to dead letter queue after {retry_count} retries"
                )

            await conn.commit()

            # 残りのアイテムを再度メモリキューに追加
            remaining_cursor = await conn.execute(
                f"""
                SELECT id FROM obsidian_file_queue
                WHERE id IN ({placeholders}) AND status = 'pending'
            """,
                queue_ids,
            )

            remaining_ids = await remaining_cursor.fetchall()
            for (queue_id,) in remaining_ids:
                try:
                    self._memory_queue.put_nowait(str(queue_id))
                except asyncio.QueueFull:
                    # メモリキューが満杯の場合は後で処理される
                    pass

    async def get_queue_status(self) -> Dict[str, int]:
        """キューの現在状況を取得（管理者向け）"""
        async with self.db_service.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM obsidian_file_queue
                GROUP BY status
            """
            )

            status_counts = dict(await cursor.fetchall())

            # DLQのカウントも取得
            dlq_cursor = await conn.execute("SELECT COUNT(*) FROM obsidian_dead_letter_queue")
            dlq_count = (await dlq_cursor.fetchone())[0]

            return {
                "pending": status_counts.get("pending", 0),
                "processing": status_counts.get("processing", 0),
                "completed": status_counts.get("completed", 0),
                "failed": status_counts.get("failed", 0),
                "dead_letter": dlq_count,
                "memory_queue": self._memory_queue.qsize(),
            }

    async def start_processing(self) -> None:
        """キュー処理を開始"""
        if self._processing_task is not None:
            self.logger.warning("Queue processing is already running")
            return

        self._shutdown_event.clear()
        self._processing_task = asyncio.create_task(self._process_queue())
        self.logger.info("Started queue processing")

    async def stop_processing(self, graceful: bool = True) -> None:
        """キュー処理を停止"""
        self._shutdown_event.set()

        if self._processing_task:
            if graceful:
                # 現在のバッチ処理が完了するまで待機
                await self._processing_task
            else:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass

            self._processing_task = None

        self.logger.info("Stopped queue processing")

    async def _process_queue(self) -> None:
        """キュー処理のメインループ（永続化対応）"""
        self.logger.info("Queue processing started")

        try:
            while not self._shutdown_event.is_set():
                try:
                    # バッチ収集（タイムアウト付き）
                    batch_queue_ids = []

                    # 最初のアイテムを待機（ブロッキング）
                    try:
                        first_id = await asyncio.wait_for(
                            self._memory_queue.get(), timeout=self.batch_timeout
                        )
                        batch_queue_ids.append(first_id)
                    except asyncio.TimeoutError:
                        continue  # タイムアウト時は次のループへ

                    # 残りのアイテムを非ブロッキングで収集
                    while len(batch_queue_ids) < self.batch_size:
                        try:
                            queue_id = self._memory_queue.get_nowait()
                            batch_queue_ids.append(queue_id)
                        except asyncio.QueueEmpty:
                            break

                    if not batch_queue_ids:
                        continue

                    # データベースから実際のFileRequestを取得
                    file_requests = await self._load_file_requests(batch_queue_ids)

                    if not file_requests:
                        self.logger.warning(
                            f"No valid file requests found for batch {batch_queue_ids}"
                        )
                        continue

                    self._batch_count += 1
                    batch_id = self._batch_count

                    # ステータスを processing に更新
                    await self._update_queue_status(
                        batch_queue_ids, "processing", batch_id=batch_id
                    )

                    # バッチ処理実行（仮想的な処理 - 実際の処理は別のサービスで行う）
                    success = await self._process_batch(file_requests, batch_id)

                    if success:
                        # 成功時は completed に更新
                        await self._update_queue_status(batch_queue_ids, "completed")
                        self.logger.info(
                            f"Batch {batch_id} completed successfully ({len(file_requests)} items)"
                        )
                    else:
                        # 失敗時はリトライ処理
                        await self._handle_batch_failure(batch_queue_ids, "Batch processing failed")

                except Exception as e:
                    self.logger.error(f"Error in queue processing: {e}")
                    if batch_queue_ids:
                        await self._handle_batch_failure(batch_queue_ids, str(e))

        except asyncio.CancelledError:
            self.logger.info("Queue processing cancelled")
            raise
        except Exception as e:
            self.logger.error(f"Fatal error in queue processing: {e}")
            raise
        finally:
            self.logger.info("Queue processing stopped")

    async def _process_batch(self, file_requests: List[FileRequest], batch_id: int) -> bool:
        """バッチ処理の実装 - 実際のGitHub保存処理"""
        self.logger.info(f"Processing batch {batch_id} with {len(file_requests)} items")

        try:
            # GitOperationServiceへのアクセス（依存性注入で取得）
            git_service = getattr(self, "_git_service", None)
            if not git_service:
                self.logger.error("GitOperationService not available - cannot process batch")
                return False

            success_count = 0
            failed_requests = []

            for request in file_requests:
                try:
                    # ファイルパスを生成
                    file_path = (
                        f"{request.directory}/{request.filename}"
                        if request.directory
                        else request.filename
                    )

                    # GitHub にファイルを保存
                    result = await git_service.create_or_update_file(
                        file_path=file_path,
                        content=request.content,
                        commit_message=f"Add {request.metadata.get('type', 'fleeting_note')}: "
                        f"{request.filename}",
                        metadata=request.metadata,
                    )

                    if result.get("success", False):
                        success_count += 1
                        self.logger.info(f"Successfully saved file: {file_path}")
                    else:
                        failed_requests.append((request, result.get("error", "Unknown error")))
                        self.logger.error(f"Failed to save file {file_path}: {result.get('error')}")

                except Exception as e:
                    failed_requests.append((request, str(e)))
                    self.logger.error(
                        f"Exception saving file {request.filename}: {e}", exc_info=True
                    )

            # バッチ処理結果をログ
            if failed_requests:
                self.logger.warning(
                    f"Batch {batch_id} completed with {success_count}/"
                    f"{len(file_requests)} successes"
                )
                for request, error in failed_requests:
                    self.logger.error(f"Failed request: {request.filename} - {error}")
            else:
                self.logger.info(
                    f"Batch {batch_id} completed successfully - all {success_count} files saved"
                )

            # 全て成功した場合のみTrue、一部でも失敗した場合はFalse
            return len(failed_requests) == 0

        except Exception as e:
            self.logger.error(f"Fatal error processing batch {batch_id}: {e}", exc_info=True)
            return False

    async def cleanup(self) -> None:
        """リソースのクリーンアップ"""
        await self.stop_processing(graceful=True)

        # メモリキューの残りアイテムをSQLiteに保存（必要に応じて）
        remaining_count = self._memory_queue.qsize()
        if remaining_count > 0:
            self.logger.info(
                f"Graceful shutdown: {remaining_count} items remain in memory queue "
                "(will be recovered on restart)"
            )
