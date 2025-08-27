"""
Database migration system for NescordBot.

Provides versioned database schema management with automatic migration
execution, rollback capabilities, and integrity verification.
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiosqlite

from ..logger import get_logger


@dataclass
class MigrationInfo:
    """Migration metadata."""

    version: int
    name: str
    description: str
    applied_at: Optional[datetime] = None
    checksum: Optional[str] = None


class Migration(ABC):
    """Base class for database migrations."""

    def __init__(self, version: int, name: str, description: str):
        self.version = version
        self.name = name
        self.description = description

    @abstractmethod
    async def up(self, connection: aiosqlite.Connection) -> None:
        """Apply the migration."""
        pass

    @abstractmethod
    async def down(self, connection: aiosqlite.Connection) -> None:
        """Rollback the migration."""
        pass

    def get_checksum(self) -> str:
        """Generate checksum for migration integrity."""
        import hashlib

        content = f"{self.version}{self.name}{self.description}"
        return hashlib.md5(content.encode()).hexdigest()


class CreateKnowledgeNotesMigration(Migration):
    """Migration 001: Create knowledge_notes table."""

    def __init__(self):
        super().__init__(
            version=1,
            name="create_knowledge_notes",
            description="Create knowledge_notes table for PKM functionality",
        )

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Create knowledge_notes table."""
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                source_type TEXT,
                source_id TEXT,
                user_id TEXT NOT NULL,
                channel_id TEXT,
                guild_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                vector_updated_at DATETIME
            )
        """
        )

        # Create indexes for performance
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_notes_user_id
            ON knowledge_notes(user_id)
        """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_notes_created_at
            ON knowledge_notes(created_at)
        """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_notes_source_type
            ON knowledge_notes(source_type)
        """
        )

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Drop knowledge_notes table."""
        await connection.execute("DROP TABLE IF EXISTS knowledge_notes")
        await connection.execute("DROP INDEX IF EXISTS idx_knowledge_notes_user_id")
        await connection.execute("DROP INDEX IF EXISTS idx_knowledge_notes_created_at")
        await connection.execute("DROP INDEX IF EXISTS idx_knowledge_notes_source_type")


class CreateNoteLinksMigration(Migration):
    """Migration 002: Create note_links table."""

    def __init__(self):
        super().__init__(
            version=2,
            name="create_note_links",
            description="Create note_links table for note relationships",
        )

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Create note_links table."""
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS note_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_note_id TEXT NOT NULL,
                to_note_id TEXT NOT NULL,
                link_type TEXT DEFAULT 'reference',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_note_id) REFERENCES knowledge_notes(id),
                FOREIGN KEY (to_note_id) REFERENCES knowledge_notes(id),
                UNIQUE(from_note_id, to_note_id)
            )
        """
        )

        # Create indexes
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_note_links_from_note_id
            ON note_links(from_note_id)
        """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_note_links_to_note_id
            ON note_links(to_note_id)
        """
        )

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Drop note_links table."""
        await connection.execute("DROP TABLE IF EXISTS note_links")
        await connection.execute("DROP INDEX IF EXISTS idx_note_links_from_note_id")
        await connection.execute("DROP INDEX IF EXISTS idx_note_links_to_note_id")


class CreateTokenUsageMigration(Migration):
    """Migration 003: Create token_usage table."""

    def __init__(self):
        super().__init__(
            version=3,
            name="create_token_usage",
            description="Create token_usage table for API usage tracking",
        )

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Create token_usage table."""
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                cost_usd REAL,
                user_id TEXT,
                request_type TEXT,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_usage_provider
            ON token_usage(provider)
        """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_usage_timestamp
            ON token_usage(timestamp)
        """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_usage_user_id
            ON token_usage(user_id)
        """
        )

        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_token_usage_model
            ON token_usage(model)
        """
        )

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Drop token_usage table."""
        await connection.execute("DROP TABLE IF EXISTS token_usage")
        await connection.execute("DROP INDEX IF EXISTS idx_token_usage_provider")
        await connection.execute("DROP INDEX IF EXISTS idx_token_usage_timestamp")
        await connection.execute("DROP INDEX IF EXISTS idx_token_usage_user_id")
        await connection.execute("DROP INDEX IF EXISTS idx_token_usage_model")


class ExtendTranscriptionsMigration(Migration):
    """Migration 004: Extend transcriptions table."""

    def __init__(self):
        super().__init__(
            version=4,
            name="extend_transcriptions",
            description="Extend transcriptions table with PKM fields",
        )

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Add PKM fields to transcriptions table."""
        # Check if table exists first
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='transcriptions'
        """
        )
        table_exists = await cursor.fetchone()
        await cursor.close()

        if not table_exists:
            # Create basic transcriptions table
            await connection.execute(
                """
                CREATE TABLE transcriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    audio_file TEXT,
                    transcript TEXT,
                    summary TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

        # Add new columns if they don't exist
        try:
            await connection.execute("ALTER TABLE transcriptions ADD COLUMN note_id TEXT")
        except aiosqlite.OperationalError:
            pass  # Column already exists

        try:
            await connection.execute("ALTER TABLE transcriptions ADD COLUMN tags TEXT")
        except aiosqlite.OperationalError:
            pass  # Column already exists

        try:
            await connection.execute("ALTER TABLE transcriptions ADD COLUMN links TEXT")
        except aiosqlite.OperationalError:
            pass  # Column already exists

        # Create index for note_id
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_transcriptions_note_id
            ON transcriptions(note_id)
        """
        )

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Remove PKM fields from transcriptions table."""
        # SQLite doesn't support DROP COLUMN, so we'd need to recreate table
        # For safety, we'll leave the columns but drop the index
        await connection.execute("DROP INDEX IF EXISTS idx_transcriptions_note_id")


class CreateFTS5IndexMigration(Migration):
    """Migration 005: Create FTS5 search index."""

    def __init__(self):
        super().__init__(
            version=5,
            name="create_fts5_index",
            description="Create FTS5 virtual table for full-text search",
        )

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Create FTS5 virtual table."""
        # Check if FTS5 is available
        try:
            await connection.execute("SELECT fts5_version()")
        except aiosqlite.OperationalError:
            # FTS5 not available - log warning and skip
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("FTS5 extension not available - full-text search will be disabled")
            return

        # Create FTS5 virtual table
        await connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_notes_fts USING fts5(
                title, content, tags,
                content=knowledge_notes,
                content_rowid=rowid,
                tokenize='unicode61'
            )
        """
        )

        # Create triggers to keep FTS5 in sync
        await connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS knowledge_notes_fts_insert AFTER INSERT ON knowledge_notes
            BEGIN
                INSERT INTO knowledge_notes_fts(rowid, title, content, tags)
                VALUES (new.rowid, new.title, new.content, new.tags);
            END
        """
        )

        await connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS knowledge_notes_fts_delete AFTER DELETE ON knowledge_notes
            BEGIN
                INSERT INTO knowledge_notes_fts(knowledge_notes_fts, rowid, title, content, tags)
                VALUES ('delete', old.rowid, old.title, old.content, old.tags);
            END
        """
        )

        await connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS knowledge_notes_fts_update AFTER UPDATE ON knowledge_notes
            BEGIN
                INSERT INTO knowledge_notes_fts(knowledge_notes_fts, rowid, title, content, tags)
                VALUES ('delete', old.rowid, old.title, old.content, old.tags);
                INSERT INTO knowledge_notes_fts(rowid, title, content, tags)
                VALUES (new.rowid, new.title, new.content, new.tags);
            END
        """
        )

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Drop FTS5 virtual table and triggers."""
        await connection.execute("DROP TRIGGER IF EXISTS knowledge_notes_fts_insert")
        await connection.execute("DROP TRIGGER IF EXISTS knowledge_notes_fts_delete")
        await connection.execute("DROP TRIGGER IF EXISTS knowledge_notes_fts_update")
        await connection.execute("DROP TABLE IF EXISTS knowledge_notes_fts")


class CreateSearchHistoryMigration(Migration):
    """Migration 006: Create search history table."""

    def __init__(self):
        super().__init__(
            version=6,
            name="create_search_history",
            description="Create search_history table for tracking user searches",
        )

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Create search_history table."""
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                query TEXT NOT NULL,
                results_count INTEGER NOT NULL DEFAULT 0,
                execution_time_ms REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_search_user_timestamp (user_id, timestamp)
            )
        """
        )

        # Create index for efficient history queries
        await connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_search_history_user_time
            ON search_history(user_id, timestamp DESC)
        """
        )

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Drop search_history table."""
        await connection.execute("DROP INDEX IF EXISTS idx_search_history_user_time")
        await connection.execute("DROP TABLE IF EXISTS search_history")


class DatabaseMigrationManager:
    """
    Database migration management system.

    Handles versioned schema changes with automatic execution,
    rollback capabilities, and integrity verification.
    """

    def __init__(self, db_path: str):
        """Initialize migration manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.logger = get_logger(__name__)
        self._migrations: List[Migration] = []
        self._lock = asyncio.Lock()

        # Register all migrations
        self._register_migrations()

    def _register_migrations(self) -> None:
        """Register all available migrations in order."""
        self._migrations = [
            CreateKnowledgeNotesMigration(),
            CreateNoteLinksMigration(),
            CreateTokenUsageMigration(),
            ExtendTranscriptionsMigration(),
            CreateFTS5IndexMigration(),
            CreateSearchHistoryMigration(),
        ]

        # Verify version sequence
        expected_versions = list(range(1, len(self._migrations) + 1))
        actual_versions = [m.version for m in self._migrations]

        if actual_versions != expected_versions:
            raise RuntimeError(f"Migration versions must be sequential: {actual_versions}")

    async def initialize_migration_table(self, connection: aiosqlite.Connection) -> None:
        """Create migration tracking table if it doesn't exist."""
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

    async def get_applied_migrations(self, connection: aiosqlite.Connection) -> List[MigrationInfo]:
        """Get list of applied migrations."""
        cursor = await connection.execute(
            """
            SELECT version, name, description, applied_at, checksum
            FROM schema_migrations
            ORDER BY version
        """
        )
        rows = await cursor.fetchall()
        await cursor.close()

        migrations = []
        for row in rows:
            version, name, description, applied_at, checksum = row
            applied_at = datetime.fromisoformat(applied_at) if applied_at else None
            migrations.append(
                MigrationInfo(
                    version=version,
                    name=name,
                    description=description,
                    applied_at=applied_at,
                    checksum=checksum,
                )
            )

        return migrations

    async def get_pending_migrations(self) -> List[Migration]:
        """Get list of migrations that need to be applied."""
        async with aiosqlite.connect(self.db_path) as connection:
            await self.initialize_migration_table(connection)
            applied = await self.get_applied_migrations(connection)
            applied_versions = {m.version for m in applied}

            pending = [
                migration
                for migration in self._migrations
                if migration.version not in applied_versions
            ]

            return pending

    async def verify_migration_integrity(self, connection: aiosqlite.Connection) -> bool:
        """Verify that applied migrations match expected checksums."""
        applied = await self.get_applied_migrations(connection)
        migration_map = {m.version: m for m in self._migrations}

        for applied_migration in applied:
            if applied_migration.version in migration_map:
                expected_migration = migration_map[applied_migration.version]
                expected_checksum = expected_migration.get_checksum()

                if applied_migration.checksum != expected_checksum:
                    self.logger.error(
                        f"Migration {applied_migration.version} checksum mismatch: "
                        f"expected {expected_checksum}, got {applied_migration.checksum}"
                    )
                    return False

        return True

    async def apply_migration(self, migration: Migration, connection: aiosqlite.Connection) -> None:
        """Apply a single migration with transaction safety."""
        async with self._lock:
            try:
                # Start transaction
                await connection.execute("BEGIN")

                self.logger.info(f"Applying migration {migration.version}: {migration.name}")

                # Apply migration
                await migration.up(connection)

                # Record migration
                await connection.execute(
                    """
                    INSERT INTO schema_migrations (version, name, description, checksum)
                    VALUES (?, ?, ?, ?)
                """,
                    (
                        migration.version,
                        migration.name,
                        migration.description,
                        migration.get_checksum(),
                    ),
                )

                # Commit transaction
                await connection.commit()

                self.logger.info(f"Migration {migration.version} applied successfully")

            except Exception as e:
                # Rollback on error
                await connection.rollback()
                self.logger.error(f"Failed to apply migration {migration.version}: {e}")
                raise

    async def rollback_migration(
        self, migration: Migration, connection: aiosqlite.Connection
    ) -> None:
        """Rollback a single migration with transaction safety."""
        async with self._lock:
            try:
                # Start transaction
                await connection.execute("BEGIN")

                self.logger.info(f"Rolling back migration {migration.version}: {migration.name}")

                # Rollback migration
                await migration.down(connection)

                # Remove migration record
                await connection.execute(
                    """
                    DELETE FROM schema_migrations WHERE version = ?
                """,
                    (migration.version,),
                )

                # Commit transaction
                await connection.commit()

                self.logger.info(f"Migration {migration.version} rolled back successfully")

            except Exception as e:
                # Rollback on error
                await connection.rollback()
                self.logger.error(f"Failed to rollback migration {migration.version}: {e}")
                raise

    async def migrate_to_latest(self) -> Dict[str, int]:
        """Apply all pending migrations to bring database to latest version."""
        async with aiosqlite.connect(self.db_path) as connection:
            # Ensure migration table exists
            await self.initialize_migration_table(connection)

            # Verify integrity
            if not await self.verify_migration_integrity(connection):
                raise RuntimeError("Migration integrity check failed")

            # Get pending migrations
            pending = await self.get_pending_migrations()

            if not pending:
                self.logger.info("Database is already up to date")
                current_version = max(
                    (m.version for m in await self.get_applied_migrations(connection)), default=0
                )
                return {
                    "applied": 0,
                    "total": len(self._migrations),
                    "current_version": current_version,
                }

            # Apply each pending migration
            applied_count = 0
            for migration in pending:
                await self.apply_migration(migration, connection)
                applied_count += 1

            self.logger.info(f"Applied {applied_count} migrations successfully")

            return {
                "applied": applied_count,
                "total": len(self._migrations),
                "current_version": max(m.version for m in self._migrations),
            }

    async def rollback_to_version(self, target_version: int) -> Dict[str, int]:
        """Rollback database to specific version."""
        async with aiosqlite.connect(self.db_path) as connection:
            applied = await self.get_applied_migrations(connection)
            migration_map = {m.version: m for m in self._migrations}

            # Find migrations to rollback (in reverse order)
            to_rollback = [
                migration_map[m.version]
                for m in applied
                if m.version > target_version and m.version in migration_map
            ]
            to_rollback.reverse()  # Rollback in reverse order

            if not to_rollback:
                self.logger.info(f"Database is already at or below version {target_version}")
                return {"rolled_back": 0, "current_version": target_version}

            # Rollback each migration
            rolled_back_count = 0
            for migration in to_rollback:
                await self.rollback_migration(migration, connection)
                rolled_back_count += 1

            self.logger.info(
                f"Rolled back {rolled_back_count} migrations to version {target_version}"
            )

            return {"rolled_back": rolled_back_count, "current_version": target_version}

    async def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status and information."""
        async with aiosqlite.connect(self.db_path) as connection:
            await self.initialize_migration_table(connection)

            applied = await self.get_applied_migrations(connection)
            pending = await self.get_pending_migrations()

            current_version = max((m.version for m in applied), default=0)
            latest_version = max(m.version for m in self._migrations)

            return {
                "current_version": current_version,
                "latest_version": latest_version,
                "applied_migrations": len(applied),
                "pending_migrations": len(pending),
                "integrity_valid": await self.verify_migration_integrity(connection),
                "migrations": {
                    "applied": [
                        {
                            "version": m.version,
                            "name": m.name,
                            "description": m.description,
                            "applied_at": m.applied_at.isoformat() if m.applied_at else None,
                        }
                        for m in applied
                    ],
                    "pending": [
                        {"version": m.version, "name": m.name, "description": m.description}
                        for m in pending
                    ],
                },
            }
