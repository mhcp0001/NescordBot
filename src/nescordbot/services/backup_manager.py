"""
BackupManagerサービス - データベースとファイルのバックアップ・リストア機能

このモジュールは自動・手動バックアップ機能、世代管理、災害復旧機能を提供します。
"""

import asyncio
import hashlib
import logging
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from ..config import BotConfig


class BackupManagerError(Exception):
    """BackupManagerで発生するエラーの基底クラス"""

    pass


class BackupIntegrityError(BackupManagerError):
    """バックアップファイルの整合性エラー"""

    pass


class RestoreError(BackupManagerError):
    """リストア処理エラー"""

    pass


class BackupInfo:
    """バックアップ情報を表すデータクラス"""

    def __init__(
        self,
        filename: str,
        created_at: datetime,
        size_bytes: int,
        checksum: str,
        backup_type: str = "manual",
        description: str = "",
    ):
        self.filename = filename
        self.created_at = created_at
        self.size_bytes = size_bytes
        self.checksum = checksum
        self.backup_type = backup_type
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "filename": self.filename,
            "created_at": self.created_at.isoformat(),
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "backup_type": self.backup_type,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupInfo":
        """辞書から生成"""
        return cls(
            filename=data["filename"],
            created_at=datetime.fromisoformat(data["created_at"]),
            size_bytes=data["size_bytes"],
            checksum=data["checksum"],
            backup_type=data.get("backup_type", "manual"),
            description=data.get("description", ""),
        )


class BackupManager:
    """
    データバックアップ・リストア管理サービス

    機能:
    - SQLiteデータベースの自動・手動バックアップ
    - バックアップファイルの世代管理とクリーンアップ
    - 整合性チェック機能
    - 災害復旧機能
    """

    def __init__(self, config: BotConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._initialized = False
        self._backup_task: Optional[asyncio.Task] = None

        # データベースパス
        self.db_path = Path(config.database_url.replace("sqlite:///", ""))

        # バックアップ設定
        self.backup_dir = self.db_path.parent / "backups"
        self.max_backups = getattr(config, "max_backups", 30)  # 最大30世代
        self.backup_interval_hours = getattr(config, "backup_interval_hours", 24)  # 24時間毎
        self.compress_backups = getattr(config, "compress_backups", True)

    async def initialize(self) -> None:
        """BackupManagerを初期化"""
        if self._initialized:
            return

        try:
            # バックアップディレクトリ作成
            self.backup_dir.mkdir(parents=True, exist_ok=True)

            # 自動バックアップタスク開始
            if hasattr(self.config, "enable_auto_backup") and self.config.enable_auto_backup:
                await self._start_auto_backup()

            self._initialized = True
            self.logger.info(f"BackupManager initialized - backup directory: {self.backup_dir}")

        except Exception as e:
            self.logger.error(f"Failed to initialize BackupManager: {e}")
            raise BackupManagerError(f"Initialization failed: {e}") from e

    async def close(self) -> None:
        """BackupManagerをクローズ"""
        if self._backup_task and not self._backup_task.done():
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass

        self._initialized = False
        self.logger.info("BackupManager closed")

    async def create_backup(
        self,
        backup_type: str = "manual",
        description: str = "",
    ) -> BackupInfo:
        """
        データベースのバックアップを作成

        Args:
            backup_type: バックアップタイプ（manual/auto）
            description: バックアップの説明

        Returns:
            作成されたバックアップの情報

        Raises:
            BackupManagerError: バックアップ作成に失敗した場合
        """
        if not self._initialized:
            await self.initialize()

        try:
            # バックアップファイル名生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{timestamp}_{backup_type}.db"
            if self.compress_backups:
                backup_filename += ".zip"

            backup_path = self.backup_dir / backup_filename

            # データベースバックアップ実行
            if self.compress_backups:
                await self._create_compressed_backup(backup_path)
            else:
                await self._create_simple_backup(backup_path)

            # チェックサム計算
            checksum = await self._calculate_checksum(backup_path)

            # バックアップ情報作成
            backup_info = BackupInfo(
                filename=backup_filename,
                created_at=datetime.now(),
                size_bytes=backup_path.stat().st_size,
                checksum=checksum,
                backup_type=backup_type,
                description=description,
            )

            self.logger.info(
                f"Backup created successfully: {backup_filename} "
                f"({backup_info.size_bytes} bytes, {checksum[:8]}...)"
            )

            # 古いバックアップのクリーンアップ
            await self._cleanup_old_backups()

            return backup_info

        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            raise BackupManagerError(f"Backup creation failed: {e}") from e

    async def _create_simple_backup(self, backup_path: Path) -> None:
        """シンプルなデータベースコピーバックアップ"""
        if not self.db_path.exists():
            raise BackupManagerError(f"Database file not found: {self.db_path}")

        # SQLite VACUUMしてからバックアップ
        async with aiosqlite.connect(str(self.db_path)) as conn:
            await conn.execute("VACUUM")
            await conn.commit()

        # ファイルコピー
        shutil.copy2(self.db_path, backup_path)

    async def _create_compressed_backup(self, backup_path: Path) -> None:
        """圧縮バックアップ作成"""
        if not self.db_path.exists():
            raise BackupManagerError(f"Database file not found: {self.db_path}")

        # 一時ファイルでVACUUMしたDBを作成
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # VACUUMしてからコピー
            async with aiosqlite.connect(str(self.db_path)) as source_conn:
                await source_conn.execute("VACUUM")
                await source_conn.commit()

            shutil.copy2(self.db_path, temp_path)

            # ZIP圧縮
            with zipfile.ZipFile(
                backup_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
            ) as zip_file:
                zip_file.write(temp_path, f"database_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

        finally:
            # 一時ファイル削除
            if temp_path.exists():
                temp_path.unlink()

    async def restore_backup(self, backup_filename: str, verify_integrity: bool = True) -> None:
        """
        バックアップからデータベースを復元

        Args:
            backup_filename: 復元するバックアップファイル名
            verify_integrity: 整合性チェックを行うかどうか

        Raises:
            RestoreError: 復元処理に失敗した場合
            BackupIntegrityError: バックアップファイルの整合性に問題がある場合
        """
        if not self._initialized:
            await self.initialize()

        backup_path = self.backup_dir / backup_filename

        if not backup_path.exists():
            raise RestoreError(f"Backup file not found: {backup_filename}")

        try:
            # 整合性チェック
            if verify_integrity:
                await self._verify_backup_integrity(backup_path)

            # 現在のDBのバックアップ作成（リストア前の保護）
            restore_backup = await self.create_backup(
                "pre_restore", f"Before restoring {backup_filename}"
            )

            self.logger.info(f"Pre-restore backup created: {restore_backup.filename}")

            # リストア実行
            if backup_filename.endswith(".zip"):
                await self._restore_compressed_backup(backup_path)
            else:
                await self._restore_simple_backup(backup_path)

            self.logger.info(f"Database restored successfully from: {backup_filename}")

        except Exception as e:
            self.logger.error(f"Failed to restore backup {backup_filename}: {e}")
            raise RestoreError(f"Restore failed: {e}") from e

    async def _restore_simple_backup(self, backup_path: Path) -> None:
        """シンプルバックアップからの復元"""
        # 現在のDBファイルを置き換え
        shutil.copy2(backup_path, self.db_path)

        # データベース接続テスト
        async with aiosqlite.connect(str(self.db_path)) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = await cursor.fetchone()
            if not table_count or table_count[0] == 0:
                raise RestoreError("Restored database appears to be empty or corrupted")

    async def _restore_compressed_backup(self, backup_path: Path) -> None:
        """圧縮バックアップからの復元"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # ZIP展開
            with zipfile.ZipFile(backup_path, "r") as zip_file:
                zip_file.extractall(temp_path)

                # 展開されたDBファイルを検索
                db_files = list(temp_path.glob("*.db"))
                if not db_files:
                    raise RestoreError("No database file found in backup archive")

                extracted_db = db_files[0]

                # データベース接続テスト
                async with aiosqlite.connect(str(extracted_db)) as conn:
                    cursor = await conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    )
                    table_count = await cursor.fetchone()
                    if not table_count or table_count[0] == 0:
                        raise RestoreError("Backup database appears to be empty or corrupted")

                # 現在のDBファイルを置き換え
                shutil.copy2(extracted_db, self.db_path)

    async def list_backups(self) -> List[BackupInfo]:
        """
        利用可能なバックアップ一覧を取得

        Returns:
            バックアップ情報のリスト（作成日時降順）
        """
        if not self._initialized:
            await self.initialize()

        backups = []

        try:
            for backup_file in self.backup_dir.glob("backup_*.db*"):
                try:
                    # ファイル情報取得
                    stat = backup_file.stat()
                    created_at = datetime.fromtimestamp(stat.st_mtime)

                    # バックアップタイプを推測
                    backup_type = "auto" if "_auto." in backup_file.name else "manual"

                    # チェックサム計算
                    checksum = await self._calculate_checksum(backup_file)

                    backup_info = BackupInfo(
                        filename=backup_file.name,
                        created_at=created_at,
                        size_bytes=stat.st_size,
                        checksum=checksum,
                        backup_type=backup_type,
                    )
                    backups.append(backup_info)

                except Exception as e:
                    self.logger.warning(f"Failed to process backup file {backup_file}: {e}")

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")

        # 作成日時で降順ソート
        backups.sort(key=lambda x: x.created_at, reverse=True)
        return backups

    async def delete_backup(self, backup_filename: str) -> None:
        """
        指定されたバックアップファイルを削除

        Args:
            backup_filename: 削除するバックアップファイル名

        Raises:
            BackupManagerError: 削除に失敗した場合
        """
        backup_path = self.backup_dir / backup_filename

        if not backup_path.exists():
            raise BackupManagerError(f"Backup file not found: {backup_filename}")

        try:
            backup_path.unlink()
            self.logger.info(f"Backup deleted: {backup_filename}")
        except Exception as e:
            self.logger.error(f"Failed to delete backup {backup_filename}: {e}")
            raise BackupManagerError(f"Backup deletion failed: {e}") from e

    async def _verify_backup_integrity(self, backup_path: Path) -> None:
        """バックアップファイルの整合性チェック"""
        try:
            if backup_path.name.endswith(".zip"):
                # ZIP整合性チェック
                with zipfile.ZipFile(backup_path, "r") as zip_file:
                    # ZIP内容確認
                    bad_file = zip_file.testzip()
                    if bad_file:
                        raise BackupIntegrityError(f"Corrupted file in archive: {bad_file}")

                    # DB ファイル存在確認
                    db_files = [name for name in zip_file.namelist() if name.endswith(".db")]
                    if not db_files:
                        raise BackupIntegrityError("No database file found in backup archive")

                    # DBファイル整合性チェック
                    with tempfile.TemporaryDirectory() as temp_dir:
                        db_path = zip_file.extract(db_files[0], temp_dir)
                        await self._verify_database_integrity(Path(db_path))
            else:
                # 単純DBファイルの整合性チェック
                await self._verify_database_integrity(backup_path)

        except BackupIntegrityError:
            raise
        except Exception as e:
            raise BackupIntegrityError(f"Integrity verification failed: {e}") from e

    async def _verify_database_integrity(self, db_path: Path) -> None:
        """データベースファイルの整合性チェック"""
        try:
            async with aiosqlite.connect(str(db_path)) as conn:
                # PRAGMA integrity_check実行
                cursor = await conn.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()

                if not result or result[0] != "ok":
                    raise BackupIntegrityError(f"Database integrity check failed: {result}")

                # テーブル存在確認
                cursor = await conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = await cursor.fetchone()
                if not table_count or table_count[0] == 0:
                    raise BackupIntegrityError("Database contains no tables")

        except aiosqlite.Error as e:
            raise BackupIntegrityError(f"Database verification failed: {e}") from e

    async def _calculate_checksum(self, file_path: Path) -> str:
        """ファイルのSHA256チェックサムを計算"""
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()

    async def _cleanup_old_backups(self) -> None:
        """古いバックアップファイルをクリーンアップ"""
        try:
            backups = await self.list_backups()

            if len(backups) <= self.max_backups:
                return

            # 削除対象は古い順から
            to_delete = backups[self.max_backups :]

            for backup in to_delete:
                try:
                    await self.delete_backup(backup.filename)
                    self.logger.info(f"Cleaned up old backup: {backup.filename}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup backup {backup.filename}: {e}")

        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")

    async def _start_auto_backup(self) -> None:
        """自動バックアップタスクを開始"""

        async def backup_loop():
            while True:
                try:
                    await asyncio.sleep(self.backup_interval_hours * 3600)  # 秒に変換

                    if not self._initialized:
                        break

                    await self.create_backup("auto", "Scheduled automatic backup")
                    self.logger.info("Automatic backup completed")

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Automatic backup failed: {e}")

        self._backup_task = asyncio.create_task(backup_loop())
        self.logger.info(f"Automatic backup started (interval: {self.backup_interval_hours} hours)")

    def is_healthy(self) -> bool:
        """サービスの健康状態をチェック"""
        try:
            return self._initialized and self.backup_dir.exists() and self.db_path.exists()
        except Exception:
            return False

    async def get_backup_stats(self) -> Dict[str, Any]:
        """バックアップ統計情報を取得"""
        try:
            backups = await self.list_backups()

            total_size = sum(backup.size_bytes for backup in backups)
            auto_count = sum(1 for backup in backups if backup.backup_type == "auto")
            manual_count = len(backups) - auto_count

            return {
                "total_backups": len(backups),
                "auto_backups": auto_count,
                "manual_backups": manual_count,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "latest_backup": backups[0].to_dict() if backups else None,
                "backup_directory": str(self.backup_dir),
                "max_backups": self.max_backups,
                "backup_interval_hours": self.backup_interval_hours,
                "auto_backup_enabled": self._backup_task is not None,
            }

        except Exception as e:
            self.logger.error(f"Failed to get backup stats: {e}")
            return {"error": str(e)}
