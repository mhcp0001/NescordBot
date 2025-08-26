"""
SyncManager for SQLite-ChromaDB synchronization.

This module provides SyncManager service for maintaining data consistency
between knowledge_notes table (SQLite) and ChromaDB vector database.
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, cast

from ..config import BotConfig
from .chromadb_service import ChromaDBService, DocumentMetadata
from .database import DatabaseService
from .embedding import EmbeddingService

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Synchronization status for notes."""

    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    FAILED = "failed"
    CONFLICT = "conflict"


class SyncError(Exception):
    """Base exception for synchronization errors."""

    pass


class SyncServiceUnavailableError(SyncError):
    """Raised when required services are unavailable."""

    pass


class SyncConsistencyError(SyncError):
    """Raised when data consistency issues are detected."""

    pass


@dataclass
class SyncResult:
    """Result of a synchronization operation."""

    note_id: str
    success: bool
    status: SyncStatus
    error: Optional[str] = None
    synced_at: Optional[datetime] = None
    retry_count: int = 0


@dataclass
class SyncReport:
    """Comprehensive synchronization report."""

    total_notes: int
    successful_syncs: int
    failed_syncs: int
    skipped_syncs: int
    results: List[SyncResult]
    started_at: datetime
    completed_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate synchronization success rate."""
        if self.total_notes == 0:
            return 0.0
        return self.successful_syncs / self.total_notes


@dataclass
class ConsistencyCheck:
    """Result of consistency verification."""

    note_id: str
    sqlite_exists: bool
    chromadb_exists: bool
    embedding_matches: bool
    metadata_matches: bool
    last_modified: Optional[str] = None


@dataclass
class ConsistencyReport:
    """Comprehensive consistency report."""

    total_checked: int
    consistent_notes: int
    inconsistent_notes: int
    missing_from_chromadb: int
    missing_from_sqlite: int
    checks: List[ConsistencyCheck]
    checked_at: datetime


@dataclass
class RepairResult:
    """Result of inconsistency repair."""

    note_id: str
    repair_type: str
    success: bool
    error: Optional[str] = None


@dataclass
class RepairReport:
    """Comprehensive repair report."""

    total_repairs: int
    successful_repairs: int
    failed_repairs: int
    results: List[RepairResult]
    started_at: datetime
    completed_at: Optional[datetime] = None


class SyncManager:
    """
    Manages synchronization between SQLite knowledge_notes and ChromaDB.

    Features:
    - Bidirectional synchronization
    - Change detection and monitoring
    - Batch processing for efficiency
    - Data consistency verification
    - Error handling and recovery
    """

    def __init__(
        self,
        config: BotConfig,
        database_service: DatabaseService,
        chromadb_service: ChromaDBService,
        embedding_service: EmbeddingService,
    ):
        """
        Initialize SyncManager.

        Args:
            config: Bot configuration
            database_service: SQLite database service
            chromadb_service: ChromaDB vector database service
            embedding_service: Text embedding service
        """
        self.config = config
        self.db = database_service
        self.chromadb = chromadb_service
        self.embedding = embedding_service
        self._initialized = False

        # Sync configuration
        self.batch_size = getattr(config, "sync_batch_size", 100)
        self.max_retries = getattr(config, "sync_max_retries", 3)
        self.retry_delay = getattr(config, "sync_retry_delay", 5.0)

        logger.info("SyncManager initialized")

    async def init_async(self) -> None:
        """Initialize async resources and create sync metadata table."""
        if self._initialized:
            return

        try:
            # Ensure required services are available
            if not self.db.is_initialized:
                await self.db.initialize()

            if not self.chromadb._initialized:
                await self.chromadb.initialize()

            if not self.embedding.is_available():
                logger.warning("EmbeddingService not available - sync functionality limited")

            # Create sync metadata table
            await self._create_sync_metadata_table()

            self._initialized = True
            logger.info("SyncManager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize SyncManager: {e}")
            raise SyncServiceUnavailableError(f"SyncManager initialization failed: {e}")

    async def _create_sync_metadata_table(self) -> None:
        """Create sync metadata table for tracking synchronization state."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS sync_metadata (
            note_id TEXT PRIMARY KEY,
            last_synced_at DATETIME,
            sync_status TEXT DEFAULT 'pending',
            chromadb_doc_id TEXT,
            embedding_hash TEXT,
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (note_id) REFERENCES knowledge_notes(id)
        );
        """

        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_sync_metadata_status ON sync_metadata(sync_status);",
            "CREATE INDEX IF NOT EXISTS idx_sync_metadata_synced_at "
            "ON sync_metadata(last_synced_at);",
            "CREATE INDEX IF NOT EXISTS idx_sync_metadata_retry ON sync_metadata(retry_count);",
        ]

        async with self.db.get_connection() as conn:
            await conn.execute(create_table_sql)
            for index_sql in indexes:
                await conn.execute(index_sql)
            await conn.commit()

        logger.debug("Sync metadata table created successfully")

    def _generate_embedding_hash(self, content: str) -> str:
        """Generate hash for embedding content to detect changes."""
        # Include model name in hash to handle model changes
        content_with_model = f"{content}:{self.embedding.model_name}"
        return hashlib.sha256(content_with_model.encode()).hexdigest()

    def _generate_doc_id(self, note_id: str) -> str:
        """Generate ChromaDB document ID from note ID."""
        return f"note_{note_id}"

    async def _ensure_initialized(self) -> None:
        """Ensure SyncManager is initialized before operations."""
        if not self._initialized:
            await self.init_async()

    async def get_sync_status(self, note_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get synchronization status for notes.

        Args:
            note_id: Optional specific note ID to check

        Returns:
            Dictionary containing sync status information
        """
        await self._ensure_initialized()

        try:
            if note_id:
                # Get status for specific note
                async with self.db.get_connection() as conn:
                    cursor = await conn.execute(
                        """
                        SELECT sm.*, kn.title, kn.updated_at as note_updated_at
                        FROM sync_metadata sm
                        JOIN knowledge_notes kn ON kn.id = sm.note_id
                        WHERE sm.note_id = ?
                        """,
                        (note_id,),
                    )
                    row = await cursor.fetchone()

                if row:
                    return {
                        "note_id": row[0],
                        "last_synced_at": row[1],
                        "sync_status": row[2],
                        "chromadb_doc_id": row[3],
                        "embedding_hash": row[4],
                        "retry_count": row[5],
                        "last_error": row[6],
                        "title": row[9],
                        "note_updated_at": row[10],
                    }
                else:
                    return {"error": f"Note {note_id} not found or not synced"}

            else:
                # Get overall sync statistics
                async with self.db.get_connection() as conn:
                    cursor = await conn.execute(
                        """
                        SELECT
                            sync_status,
                            COUNT(*) as count
                        FROM sync_metadata
                        GROUP BY sync_status
                        """
                    )
                    status_counts = {row[0]: row[1] for row in await cursor.fetchall()}

                    # Get total notes count
                    cursor = await conn.execute("SELECT COUNT(*) FROM knowledge_notes")
                    total_notes = (await cursor.fetchone())[0]

                    # Get synced notes count
                    synced_notes = sum(status_counts.values())

                    return {
                        "total_notes": total_notes,
                        "synced_notes": synced_notes,
                        "unsynced_notes": total_notes - synced_notes,
                        "status_breakdown": status_counts,
                        "last_checked": datetime.now().isoformat(),
                    }

        except Exception as e:
            logger.error(f"Failed to get sync status: {e}")
            raise SyncError(f"Sync status retrieval failed: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on SyncManager and dependencies."""
        health_status: Dict[str, Any] = {
            "status": "healthy",
            "initialized": self._initialized,
            "services": {},
            "checked_at": datetime.now().isoformat(),
        }

        try:
            # Check database service
            db_status = await self.db.get_stats()
            health_status["services"]["database"] = {
                "available": True,
                "connection_count": db_status.get("total_keys", 0),
            }

            # Check ChromaDB service
            try:
                doc_count = await self.chromadb.get_document_count()
                health_status["services"]["chromadb"] = {
                    "available": True,
                    "document_count": doc_count,
                }
            except Exception as e:
                health_status["services"]["chromadb"] = {"available": False, "error": str(e)}
                health_status["status"] = "degraded"

            # Check embedding service
            health_status["services"]["embedding"] = {"available": self.embedding.is_available()}

            if not self.embedding.is_available():
                health_status["status"] = "degraded"

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)

        return health_status

    async def sync_note_to_chromadb(self, note_id: str) -> SyncResult:
        """
        Synchronize a single note from SQLite to ChromaDB.

        Args:
            note_id: ID of the note to synchronize

        Returns:
            SyncResult containing sync operation details
        """
        await self._ensure_initialized()

        start_time = datetime.now()

        try:
            # Get note data from SQLite
            note_data = await self._get_note_data(note_id)
            if not note_data:
                return SyncResult(
                    note_id=note_id,
                    success=False,
                    status=SyncStatus.FAILED,
                    error="Note not found in SQLite",
                )

            # Check if embedding service is available
            if not self.embedding.is_available():
                return SyncResult(
                    note_id=note_id,
                    success=False,
                    status=SyncStatus.FAILED,
                    error="EmbeddingService not available",
                )

            # Generate embedding for note content
            content = self._prepare_content_for_embedding(note_data)
            embedding_hash = self._generate_embedding_hash(content)

            # Check if we need to sync (compare embedding hash)
            sync_metadata = await self._get_sync_metadata(note_id)
            if (
                sync_metadata
                and sync_metadata.get("embedding_hash") == embedding_hash
                and sync_metadata.get("sync_status") == "synced"
            ):
                return SyncResult(
                    note_id=note_id,
                    success=True,
                    status=SyncStatus.SYNCED,
                    synced_at=start_time,
                    retry_count=sync_metadata.get("retry_count", 0),
                )

            # Generate embedding
            embedding_result = await self.embedding.generate_embedding(content)
            if not embedding_result:
                return SyncResult(
                    note_id=note_id,
                    success=False,
                    status=SyncStatus.FAILED,
                    error="Failed to generate embedding",
                )

            # Prepare ChromaDB document
            doc_id = self._generate_doc_id(note_id)
            metadata = self._create_document_metadata(note_data)

            # Update sync status to syncing
            await self._update_sync_metadata(
                note_id=note_id, status=SyncStatus.SYNCING, chromadb_doc_id=doc_id
            )

            # Add/update document in ChromaDB
            success = await self.chromadb.add_document(
                document_id=doc_id,
                content=content,
                embedding=embedding_result.embedding,
                metadata=metadata,
            )

            if success:
                # Update sync metadata
                await self._update_sync_metadata(
                    note_id=note_id,
                    status=SyncStatus.SYNCED,
                    chromadb_doc_id=doc_id,
                    embedding_hash=embedding_hash,
                    last_synced_at=start_time,
                )

                return SyncResult(
                    note_id=note_id, success=True, status=SyncStatus.SYNCED, synced_at=start_time
                )
            else:
                await self._update_sync_metadata(
                    note_id=note_id, status=SyncStatus.FAILED, error="ChromaDB add_document failed"
                )

                return SyncResult(
                    note_id=note_id,
                    success=False,
                    status=SyncStatus.FAILED,
                    error="ChromaDB add_document failed",
                )

        except Exception as e:
            error_msg = f"Sync failed: {e}"
            logger.error(f"Failed to sync note {note_id}: {e}")

            # Update sync metadata with error
            await self._update_sync_metadata(
                note_id=note_id, status=SyncStatus.FAILED, error=error_msg
            )

            return SyncResult(
                note_id=note_id, success=False, status=SyncStatus.FAILED, error=error_msg
            )

    async def sync_notes_batch(self, note_ids: List[str]) -> Dict[str, SyncResult]:
        """
        Synchronize multiple notes in batch.

        Args:
            note_ids: List of note IDs to synchronize

        Returns:
            Dictionary mapping note_id to SyncResult
        """
        await self._ensure_initialized()

        results = {}

        # Process in chunks to respect batch size limits
        for i in range(0, len(note_ids), self.batch_size):
            batch = note_ids[i : i + self.batch_size]

            # Process batch concurrently
            tasks = [self.sync_note_to_chromadb(note_id) for note_id in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for note_id, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    results[note_id] = SyncResult(
                        note_id=note_id, success=False, status=SyncStatus.FAILED, error=str(result)
                    )
                else:
                    results[note_id] = cast(SyncResult, result)

        return results

    async def sync_all_notes(self) -> SyncReport:
        """
        Synchronize all notes from SQLite to ChromaDB.

        Returns:
            Comprehensive synchronization report
        """
        await self._ensure_initialized()

        start_time = datetime.now()

        try:
            # Get all note IDs
            async with self.db.get_connection() as conn:
                cursor = await conn.execute("SELECT id FROM knowledge_notes")
                note_ids = [row[0] for row in await cursor.fetchall()]

            if not note_ids:
                return SyncReport(
                    total_notes=0,
                    successful_syncs=0,
                    failed_syncs=0,
                    skipped_syncs=0,
                    results=[],
                    started_at=start_time,
                    completed_at=datetime.now(),
                )

            # Sync all notes
            sync_results = await self.sync_notes_batch(note_ids)

            # Compile report
            results_list = list(sync_results.values())
            successful_syncs = sum(1 for r in results_list if r.success)
            failed_syncs = sum(1 for r in results_list if not r.success)

            return SyncReport(
                total_notes=len(note_ids),
                successful_syncs=successful_syncs,
                failed_syncs=failed_syncs,
                skipped_syncs=0,
                results=results_list,
                started_at=start_time,
                completed_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Failed to sync all notes: {e}")
            return SyncReport(
                total_notes=0,
                successful_syncs=0,
                failed_syncs=1,
                skipped_syncs=0,
                results=[],
                started_at=start_time,
                completed_at=datetime.now(),
            )

    async def _get_note_data(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Get note data from SQLite."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, title, content, tags, source_type,
                       created_at, updated_at, user_id
                FROM knowledge_notes
                WHERE id = ?
                """,
                (note_id,),
            )
            row = await cursor.fetchone()

        if row:
            return {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "tags": row[3],
                "source_type": row[4],
                "created_at": row[5],
                "updated_at": row[6],
                "user_id": row[7],
            }
        return None

    def _prepare_content_for_embedding(self, note_data: Dict[str, Any]) -> str:
        """Prepare note content for embedding generation."""
        parts = []

        # Add title if available
        if note_data.get("title"):
            parts.append(f"Title: {note_data['title']}")

        # Add main content
        if note_data.get("content"):
            parts.append(note_data["content"])

        # Add tags if available
        if note_data.get("tags"):
            parts.append(f"Tags: {note_data['tags']}")

        return "\n\n".join(parts)

    def _create_document_metadata(self, note_data: Dict[str, Any]) -> DocumentMetadata:
        """Create ChromaDB DocumentMetadata from note data."""
        return DocumentMetadata(
            document_id=note_data["id"],
            title=note_data.get("title"),
            source=note_data.get("source_type"),
            created_at=note_data.get("created_at"),
            updated_at=note_data.get("updated_at"),
            tags=note_data.get("tags", "").split(",") if note_data.get("tags") else None,
            user_id=note_data.get("user_id"),
            content_type="note",
        )

    async def _get_sync_metadata(self, note_id: str) -> Optional[Dict[str, Any]]:
        """Get sync metadata for a note."""
        async with self.db.get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM sync_metadata WHERE note_id = ?", (note_id,))
            row = await cursor.fetchone()

        if row:
            return {
                "note_id": row[0],
                "last_synced_at": row[1],
                "sync_status": row[2],
                "chromadb_doc_id": row[3],
                "embedding_hash": row[4],
                "retry_count": row[5],
                "last_error": row[6],
                "created_at": row[7],
                "updated_at": row[8],
            }
        return None

    async def _update_sync_metadata(
        self,
        note_id: str,
        status: SyncStatus,
        chromadb_doc_id: Optional[str] = None,
        embedding_hash: Optional[str] = None,
        last_synced_at: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update sync metadata for a note."""
        current_time = datetime.now()

        # First check if record exists
        existing = await self._get_sync_metadata(note_id)

        if existing:
            # Update existing record
            update_sql = """
            UPDATE sync_metadata
            SET sync_status = ?,
                updated_at = ?,
                chromadb_doc_id = COALESCE(?, chromadb_doc_id),
                embedding_hash = COALESCE(?, embedding_hash),
                last_synced_at = COALESCE(?, last_synced_at),
                last_error = ?,
                retry_count = CASE
                    WHEN ? = 'failed' THEN retry_count + 1
                    WHEN ? = 'synced' THEN 0
                    ELSE retry_count
                END
            WHERE note_id = ?
            """

            async with self.db.get_connection() as conn:
                await conn.execute(
                    update_sql,
                    (
                        status.value,
                        current_time.isoformat(),
                        chromadb_doc_id,
                        embedding_hash,
                        last_synced_at.isoformat() if last_synced_at else None,
                        error,
                        status.value,
                        status.value,
                        note_id,
                    ),
                )
                await conn.commit()
        else:
            # Insert new record
            insert_sql = """
            INSERT INTO sync_metadata
            (note_id, sync_status, chromadb_doc_id, embedding_hash,
             last_synced_at, last_error, retry_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            retry_count = 1 if status == SyncStatus.FAILED else 0

            async with self.db.get_connection() as conn:
                await conn.execute(
                    insert_sql,
                    (
                        note_id,
                        status.value,
                        chromadb_doc_id,
                        embedding_hash,
                        last_synced_at.isoformat() if last_synced_at else None,
                        error,
                        retry_count,
                        current_time.isoformat(),
                        current_time.isoformat(),
                    ),
                )
                await conn.commit()

    async def verify_consistency(self) -> ConsistencyReport:
        """
        Verify data consistency between SQLite and ChromaDB.

        Returns:
            Comprehensive consistency report
        """
        await self._ensure_initialized()

        checked_at = datetime.now()
        checks = []

        try:
            # Get all notes from SQLite
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT id, title, content, tags, updated_at FROM knowledge_notes"
                )
                sqlite_notes = {row[0]: row for row in await cursor.fetchall()}

            # Get ChromaDB document count
            await self.chromadb.get_document_count()

            # Check each SQLite note against ChromaDB
            for note_id, note_data in sqlite_notes.items():
                check = await self._verify_single_note_consistency(note_id, note_data)
                checks.append(check)

            # Compile statistics
            consistent_notes = sum(
                1
                for check in checks
                if check.sqlite_exists
                and check.chromadb_exists
                and check.embedding_matches
                and check.metadata_matches
            )

            inconsistent_notes = len(checks) - consistent_notes
            missing_from_chromadb = sum(
                1 for check in checks if check.sqlite_exists and not check.chromadb_exists
            )
            missing_from_sqlite = sum(
                1 for check in checks if not check.sqlite_exists and check.chromadb_exists
            )

            return ConsistencyReport(
                total_checked=len(checks),
                consistent_notes=consistent_notes,
                inconsistent_notes=inconsistent_notes,
                missing_from_chromadb=missing_from_chromadb,
                missing_from_sqlite=missing_from_sqlite,
                checks=checks,
                checked_at=checked_at,
            )

        except Exception as e:
            logger.error(f"Failed to verify consistency: {e}")
            return ConsistencyReport(
                total_checked=0,
                consistent_notes=0,
                inconsistent_notes=1,
                missing_from_chromadb=0,
                missing_from_sqlite=0,
                checks=[],
                checked_at=checked_at,
            )

    async def _verify_single_note_consistency(
        self, note_id: str, note_data: Tuple[str, ...]
    ) -> ConsistencyCheck:
        """Verify consistency for a single note."""
        doc_id = self._generate_doc_id(note_id)

        # Check SQLite existence
        sqlite_exists = note_data is not None

        # Check ChromaDB existence
        chromadb_exists = False
        embedding_matches = False
        metadata_matches = False

        try:
            # Try to search for the document in ChromaDB
            # Since we don't have a direct "get by ID" method, we'll use search
            test_embedding = [0.1] * self.embedding.embedding_dimension
            results = await self.chromadb.search_documents(
                query_embedding=test_embedding,
                n_results=1000,  # Get many results to find our document
                where={"document_id": note_id},
            )

            # Look for our document in the results
            chromadb_doc = None
            for result in results:
                if result.document_id == doc_id:
                    chromadb_doc = result
                    chromadb_exists = True
                    break

            if chromadb_exists and chromadb_doc:
                # Check embedding consistency
                note_content = self._prepare_content_for_embedding(
                    {"title": note_data[1], "content": note_data[2], "tags": note_data[3]}
                )
                expected_hash = self._generate_embedding_hash(note_content)

                # Get sync metadata to compare hash
                sync_metadata = await self._get_sync_metadata(note_id)
                if sync_metadata:
                    embedding_matches = sync_metadata.get("embedding_hash") == expected_hash

                # Check metadata consistency (basic check)
                metadata_matches = (
                    chromadb_doc.metadata.document_id == note_id
                    and chromadb_doc.metadata.title == note_data[1]
                )

        except Exception as e:
            logger.debug(f"Error checking ChromaDB consistency for note {note_id}: {e}")
            # ChromaDB check failed, assume not exists
            chromadb_exists = False

        return ConsistencyCheck(
            note_id=note_id,
            sqlite_exists=sqlite_exists,
            chromadb_exists=chromadb_exists,
            embedding_matches=embedding_matches,
            metadata_matches=metadata_matches,
            last_modified=note_data[4] if sqlite_exists and len(note_data) > 4 else None,
        )

    async def repair_inconsistencies(self, consistency_report: ConsistencyReport) -> RepairReport:
        """
        Repair data inconsistencies found by verify_consistency.

        Args:
            consistency_report: Report from verify_consistency()

        Returns:
            Comprehensive repair report
        """
        await self._ensure_initialized()

        started_at = datetime.now()
        repair_results = []

        # Find notes that need repair
        notes_to_sync = []

        for check in consistency_report.checks:
            if check.sqlite_exists and not check.chromadb_exists:
                # Missing from ChromaDB - need to sync
                notes_to_sync.append(check.note_id)
            elif check.sqlite_exists and check.chromadb_exists and not check.embedding_matches:
                # Embedding mismatch - need to re-sync
                notes_to_sync.append(check.note_id)
            elif check.sqlite_exists and check.chromadb_exists and not check.metadata_matches:
                # Metadata mismatch - need to re-sync
                notes_to_sync.append(check.note_id)

        # Perform batch sync for identified notes
        if notes_to_sync:
            try:
                sync_results = await self.sync_notes_batch(notes_to_sync)

                for note_id, sync_result in sync_results.items():
                    if sync_result.success:
                        repair_results.append(
                            RepairResult(
                                note_id=note_id, repair_type="sync_to_chromadb", success=True
                            )
                        )
                    else:
                        repair_results.append(
                            RepairResult(
                                note_id=note_id,
                                repair_type="sync_to_chromadb",
                                success=False,
                                error=sync_result.error,
                            )
                        )

            except Exception as e:
                logger.error(f"Failed to repair inconsistencies: {e}")
                for note_id in notes_to_sync:
                    repair_results.append(
                        RepairResult(
                            note_id=note_id,
                            repair_type="sync_to_chromadb",
                            success=False,
                            error=str(e),
                        )
                    )

        # Handle notes missing from SQLite (if any found in ChromaDB but not SQLite)
        # This would be a more complex repair - for now just log
        missing_from_sqlite = [
            check
            for check in consistency_report.checks
            if not check.sqlite_exists and check.chromadb_exists
        ]

        if missing_from_sqlite:
            logger.warning(
                f"Found {len(missing_from_sqlite)} documents in ChromaDB "
                "that are missing from SQLite - manual intervention may be required"
            )

        successful_repairs = sum(1 for r in repair_results if r.success)
        failed_repairs = len(repair_results) - successful_repairs

        return RepairReport(
            total_repairs=len(repair_results),
            successful_repairs=successful_repairs,
            failed_repairs=failed_repairs,
            results=repair_results,
            started_at=started_at,
            completed_at=datetime.now(),
        )

    async def delete_note_from_chromadb(self, note_id: str) -> bool:
        """
        Delete a note from ChromaDB.

        Args:
            note_id: ID of the note to delete

        Returns:
            True if deletion was successful
        """
        await self._ensure_initialized()

        try:
            doc_id = self._generate_doc_id(note_id)
            success = await self.chromadb.delete_document(doc_id)

            if success:
                # Update sync metadata to mark as deleted/unsynced
                await self._update_sync_metadata(
                    note_id=note_id, status=SyncStatus.PENDING, error="Deleted from ChromaDB"
                )

                # Or alternatively, delete the sync metadata entirely
                async with self.db.get_connection() as conn:
                    await conn.execute("DELETE FROM sync_metadata WHERE note_id = ?", (note_id,))
                    await conn.commit()

                logger.debug(f"Note {note_id} deleted from ChromaDB successfully")

            return success

        except Exception as e:
            logger.error(f"Failed to delete note {note_id} from ChromaDB: {e}")
            return False

    async def get_unsynced_notes(self, limit: int = 100) -> List[str]:
        """
        Get list of note IDs that need synchronization.

        Args:
            limit: Maximum number of note IDs to return

        Returns:
            List of note IDs that need sync
        """
        await self._ensure_initialized()

        try:
            async with self.db.get_connection() as conn:
                # Get notes that have never been synced or failed sync
                cursor = await conn.execute(
                    """
                    SELECT kn.id
                    FROM knowledge_notes kn
                    LEFT JOIN sync_metadata sm ON kn.id = sm.note_id
                    WHERE sm.note_id IS NULL
                       OR sm.sync_status IN ('pending', 'failed')
                       OR (sm.sync_status = 'synced' AND kn.updated_at > sm.last_synced_at)
                    ORDER BY kn.updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

                return [row[0] for row in await cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get unsynced notes: {e}")
            return []

    async def retry_failed_syncs(self, max_retries: Optional[int] = None) -> SyncReport:
        """
        Retry synchronization for notes that previously failed.

        Args:
            max_retries: Override default max retries setting

        Returns:
            Synchronization report for retry operations
        """
        await self._ensure_initialized()

        start_time = datetime.now()
        max_retries = max_retries or self.max_retries

        try:
            # Get failed syncs that haven't exceeded retry limit
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT note_id FROM sync_metadata
                    WHERE sync_status = 'failed'
                      AND retry_count < ?
                    ORDER BY updated_at DESC
                    """,
                    (max_retries,),
                )
                failed_note_ids = [row[0] for row in await cursor.fetchall()]

            if not failed_note_ids:
                return SyncReport(
                    total_notes=0,
                    successful_syncs=0,
                    failed_syncs=0,
                    skipped_syncs=0,
                    results=[],
                    started_at=start_time,
                    completed_at=datetime.now(),
                )

            # Retry synchronization with exponential backoff
            retry_results = {}
            for note_id in failed_note_ids:
                # Get current retry count
                sync_metadata = await self._get_sync_metadata(note_id)
                current_retries = sync_metadata.get("retry_count", 0) if sync_metadata else 0

                # Calculate delay based on retry count
                delay = self.retry_delay * (2**current_retries)
                if current_retries > 0:
                    await asyncio.sleep(min(delay, 60.0))  # Cap at 60 seconds

                # Attempt retry
                result = await self.sync_note_to_chromadb(note_id)
                retry_results[note_id] = result

                logger.info(
                    f"Retry {current_retries + 1} for note {note_id}: "
                    f"{'Success' if result.success else 'Failed'}"
                )

            # Compile report
            results_list = list(retry_results.values())
            successful_syncs = sum(1 for r in results_list if r.success)
            failed_syncs = len(results_list) - successful_syncs

            return SyncReport(
                total_notes=len(failed_note_ids),
                successful_syncs=successful_syncs,
                failed_syncs=failed_syncs,
                skipped_syncs=0,
                results=results_list,
                started_at=start_time,
                completed_at=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Failed to retry failed syncs: {e}")
            return SyncReport(
                total_notes=0,
                successful_syncs=0,
                failed_syncs=1,
                skipped_syncs=0,
                results=[],
                started_at=start_time,
                completed_at=datetime.now(),
            )

    async def clear_old_sync_metadata(self, days_old: int = 30) -> int:
        """
        Clean up old sync metadata entries.

        Args:
            days_old: Remove metadata older than this many days

        Returns:
            Number of entries removed
        """
        await self._ensure_initialized()

        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)

            async with self.db.get_connection() as conn:
                # Remove old failed sync entries that are no longer relevant
                cursor = await conn.execute(
                    """
                    DELETE FROM sync_metadata
                    WHERE sync_status = 'failed'
                      AND updated_at < ?
                      AND retry_count >= ?
                    """,
                    (cutoff_date.isoformat(), self.max_retries),
                )

                # Get count of deleted rows
                deleted_count = cursor.rowcount or 0
                await conn.commit()

                logger.info(f"Cleaned up {deleted_count} old sync metadata entries")
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to clean up old sync metadata: {e}")
            return 0

    async def get_sync_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive synchronization statistics.

        Returns:
            Dictionary containing various sync statistics
        """
        await self._ensure_initialized()

        try:
            stats = {}

            async with self.db.get_connection() as conn:
                # Basic counts
                cursor = await conn.execute("SELECT COUNT(*) FROM knowledge_notes")
                stats["total_notes"] = (await cursor.fetchone())[0]

                cursor = await conn.execute("SELECT COUNT(*) FROM sync_metadata")
                stats["sync_records"] = (await cursor.fetchone())[0]

                # Status breakdown
                cursor = await conn.execute(
                    """
                    SELECT sync_status, COUNT(*)
                    FROM sync_metadata
                    GROUP BY sync_status
                    """
                )
                status_counts = dict(await cursor.fetchall())
                stats["status_breakdown"] = status_counts

                # Recent activity
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM sync_metadata
                    WHERE last_synced_at > datetime('now', '-24 hours')
                    """
                )
                stats["synced_last_24h"] = (await cursor.fetchone())[0]

                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM sync_metadata
                    WHERE last_synced_at > datetime('now', '-7 days')
                    """
                )
                stats["synced_last_week"] = (await cursor.fetchone())[0]

                # Error analysis
                cursor = await conn.execute(
                    """
                    SELECT last_error, COUNT(*)
                    FROM sync_metadata
                    WHERE sync_status = 'failed'
                      AND last_error IS NOT NULL
                    GROUP BY last_error
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                    """
                )
                error_stats = dict(await cursor.fetchall())
                stats["top_errors"] = error_stats

                # Retry analysis
                cursor = await conn.execute(
                    """
                    SELECT
                        AVG(retry_count) as avg_retries,
                        MAX(retry_count) as max_retries,
                        COUNT(CASE WHEN retry_count >= ? THEN 1 END) as max_retries_exceeded
                    FROM sync_metadata
                    WHERE sync_status = 'failed'
                    """,
                    (self.max_retries,),
                )
                retry_row = await cursor.fetchone()
                if retry_row:
                    stats["retry_analysis"] = {
                        "avg_retries": retry_row[0] or 0,
                        "max_retries": retry_row[1] or 0,
                        "max_retries_exceeded": retry_row[2] or 0,
                    }

                # ChromaDB statistics
                try:
                    chromadb_count = await self.chromadb.get_document_count()
                    stats["chromadb_documents"] = chromadb_count
                except Exception as e:
                    stats["chromadb_documents"] = f"Error: {e}"

                # Success rate calculation
                total_attempts = sum(status_counts.values())
                successful = status_counts.get("synced", 0)
                stats["success_rate"] = (
                    successful / total_attempts * 100 if total_attempts > 0 else 0
                )

                stats["generated_at"] = datetime.now().isoformat()

            return stats

        except Exception as e:
            logger.error(f"Failed to get sync statistics: {e}")
            return {"error": str(e), "generated_at": datetime.now().isoformat()}

    async def handle_sync_conflict(
        self, note_id: str, resolution_strategy: str = "latest_wins"
    ) -> SyncResult:
        """
        Handle synchronization conflicts between SQLite and ChromaDB.

        Args:
            note_id: ID of the conflicted note
            resolution_strategy: Strategy for conflict resolution
                - "latest_wins": Use the most recently modified version
                - "sqlite_wins": Prefer SQLite version
                - "chromadb_wins": Prefer ChromaDB version

        Returns:
            Result of conflict resolution
        """
        await self._ensure_initialized()

        try:
            if resolution_strategy == "sqlite_wins" or resolution_strategy == "latest_wins":
                # For now, always sync from SQLite to ChromaDB
                # In future, could implement more sophisticated conflict resolution
                result = await self.sync_note_to_chromadb(note_id)

                if result.success:
                    # Update sync metadata to mark conflict as resolved
                    await self._update_sync_metadata(
                        note_id=note_id, status=SyncStatus.SYNCED, last_synced_at=datetime.now()
                    )

                return result

            elif resolution_strategy == "chromadb_wins":
                # This would require implementing sync from ChromaDB to SQLite
                # For now, return an error
                return SyncResult(
                    note_id=note_id,
                    success=False,
                    status=SyncStatus.CONFLICT,
                    error="ChromaDB-to-SQLite sync not yet implemented",
                )

            else:
                return SyncResult(
                    note_id=note_id,
                    success=False,
                    status=SyncStatus.CONFLICT,
                    error=f"Unknown resolution strategy: {resolution_strategy}",
                )

        except Exception as e:
            logger.error(f"Failed to handle sync conflict for note {note_id}: {e}")
            return SyncResult(
                note_id=note_id,
                success=False,
                status=SyncStatus.FAILED,
                error=f"Conflict resolution failed: {e}",
            )

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False
        logger.info("SyncManager closed")
