"""
Tests for database migration system.

Comprehensive test suite for DatabaseMigrationManager and all migrations
including version control, integrity verification, and rollback functionality.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest

from nescordbot.services.migrations import (
    CreateFTS5IndexMigration,
    CreateKnowledgeNotesMigration,
    CreateNoteLinksMigration,
    CreateTokenUsageMigration,
    DatabaseMigrationManager,
    ExtendTranscriptionsMigration,
    Migration,
    MigrationInfo,
)


class MockMigration(Migration):
    """Test migration for testing purposes."""

    def __init__(self, version: int = 999, should_fail: bool = False):
        super().__init__(version, "test_migration", "Test migration")
        self.should_fail = should_fail
        self.up_called = False
        self.down_called = False

    async def up(self, connection: aiosqlite.Connection) -> None:
        """Test migration up."""
        if self.should_fail:
            raise RuntimeError("Test migration failure")

        await connection.execute(
            """
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """
        )
        self.up_called = True

    async def down(self, connection: aiosqlite.Connection) -> None:
        """Test migration down."""
        if self.should_fail:
            raise RuntimeError("Test migration rollback failure")

        await connection.execute("DROP TABLE IF EXISTS test_table")
        self.down_called = True


@pytest.fixture
def temp_db_path():
    """Create temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
async def migration_manager(temp_db_path):
    """Create migration manager with temporary database."""
    manager = DatabaseMigrationManager(temp_db_path)
    yield manager


@pytest.fixture
async def connection(temp_db_path):
    """Create database connection."""
    conn = await aiosqlite.connect(temp_db_path)
    yield conn
    await conn.close()


class TestMigrationBase:
    """Tests for Migration base class."""

    def test_migration_init(self):
        """Test migration initialization."""
        migration = MockMigration(1)
        assert migration.version == 1
        assert migration.name == "test_migration"
        assert migration.description == "Test migration"

    def test_migration_checksum(self):
        """Test migration checksum generation."""
        migration1 = MockMigration(1)
        migration2 = MockMigration(1)
        migration3 = MockMigration(2)

        # Same migration should have same checksum
        assert migration1.get_checksum() == migration2.get_checksum()

        # Different migrations should have different checksums
        assert migration1.get_checksum() != migration3.get_checksum()


class TestDatabaseMigrationManager:
    """Tests for DatabaseMigrationManager."""

    @pytest.mark.asyncio
    async def test_init_migration_table(self, migration_manager, connection):
        """Test migration table initialization."""
        await migration_manager.initialize_migration_table(connection)

        # Check if table exists
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_migrations'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None
        assert result[0] == "schema_migrations"

    @pytest.mark.asyncio
    async def test_apply_migration(self, migration_manager, connection):
        """Test applying a single migration."""
        await migration_manager.initialize_migration_table(connection)

        test_migration = MockMigration(1)
        await migration_manager.apply_migration(test_migration, connection)

        # Check migration was applied
        assert test_migration.up_called

        # Check migration record
        cursor = await connection.execute(
            """
            SELECT version, name, description FROM schema_migrations WHERE version = 1
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None
        assert result[0] == 1
        assert result[1] == "test_migration"

    @pytest.mark.asyncio
    async def test_rollback_migration(self, migration_manager, connection):
        """Test rolling back a migration."""
        await migration_manager.initialize_migration_table(connection)

        test_migration = MockMigration(1)

        # Apply then rollback
        await migration_manager.apply_migration(test_migration, connection)
        await migration_manager.rollback_migration(test_migration, connection)

        # Check rollback was called
        assert test_migration.down_called

        # Check migration record removed
        cursor = await connection.execute(
            """
            SELECT COUNT(*) FROM schema_migrations WHERE version = 1
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result[0] == 0

    @pytest.mark.asyncio
    async def test_migration_failure_rollback(self, migration_manager, connection):
        """Test transaction rollback on migration failure."""
        await migration_manager.initialize_migration_table(connection)

        failing_migration = MockMigration(1, should_fail=True)

        with pytest.raises(RuntimeError, match="Test migration failure"):
            await migration_manager.apply_migration(failing_migration, connection)

        # Check no migration record was created
        cursor = await connection.execute(
            """
            SELECT COUNT(*) FROM schema_migrations WHERE version = 1
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result[0] == 0

    @pytest.mark.asyncio
    async def test_get_applied_migrations(self, migration_manager, connection):
        """Test getting applied migrations."""
        await migration_manager.initialize_migration_table(connection)

        test_migration = MockMigration(1)
        await migration_manager.apply_migration(test_migration, connection)

        applied = await migration_manager.get_applied_migrations(connection)

        assert len(applied) == 1
        assert applied[0].version == 1
        assert applied[0].name == "test_migration"
        assert applied[0].applied_at is not None

    @pytest.mark.asyncio
    async def test_verify_migration_integrity(self, migration_manager, connection):
        """Test migration integrity verification."""
        await migration_manager.initialize_migration_table(connection)

        # Apply migration
        test_migration = MockMigration(1)
        await migration_manager.apply_migration(test_migration, connection)

        # Override migration list to include our test migration
        migration_manager._migrations = [test_migration]

        # Integrity should be valid
        assert await migration_manager.verify_migration_integrity(connection)

        # Modify checksum manually to simulate corruption
        await connection.execute(
            """
            UPDATE schema_migrations SET checksum = 'invalid' WHERE version = 1
        """
        )
        await connection.commit()

        # Integrity should now be invalid
        assert not await migration_manager.verify_migration_integrity(connection)


class TestIndividualMigrations:
    """Tests for individual migration classes."""

    @pytest.mark.asyncio
    async def test_create_knowledge_notes_migration(self, connection):
        """Test knowledge_notes table creation."""
        migration = CreateKnowledgeNotesMigration()

        await migration.up(connection)
        await connection.commit()

        # Check table exists
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='knowledge_notes'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None

        # Check table structure
        cursor = await connection.execute("PRAGMA table_info(knowledge_notes)")
        columns = await cursor.fetchall()
        await cursor.close()

        column_names = [col[1] for col in columns]
        expected_columns = [
            "id",
            "title",
            "content",
            "tags",
            "source_type",
            "source_id",
            "user_id",
            "channel_id",
            "guild_id",
            "created_at",
            "updated_at",
            "vector_updated_at",
        ]

        for col in expected_columns:
            assert col in column_names

    @pytest.mark.asyncio
    async def test_create_note_links_migration(self, connection):
        """Test note_links table creation."""
        # Create knowledge_notes first (dependency)
        knowledge_migration = CreateKnowledgeNotesMigration()
        await knowledge_migration.up(connection)

        migration = CreateNoteLinksMigration()
        await migration.up(connection)
        await connection.commit()

        # Check table exists
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='note_links'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None

        # Test unique constraint
        await connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, user_id)
            VALUES ('note1', 'Test Note 1', 'Content 1', 'user1')
        """
        )
        await connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, user_id)
            VALUES ('note2', 'Test Note 2', 'Content 2', 'user1')
        """
        )

        # First link should succeed
        await connection.execute(
            """
            INSERT INTO note_links (from_note_id, to_note_id)
            VALUES ('note1', 'note2')
        """
        )

        # Duplicate link should fail
        with pytest.raises(aiosqlite.IntegrityError):
            await connection.execute(
                """
                INSERT INTO note_links (from_note_id, to_note_id)
                VALUES ('note1', 'note2')
            """
            )

    @pytest.mark.asyncio
    async def test_create_token_usage_migration(self, connection):
        """Test token_usage table creation."""
        migration = CreateTokenUsageMigration()

        await migration.up(connection)
        await connection.commit()

        # Check table exists
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='token_usage'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None

        # Test data insertion
        await connection.execute(
            """
            INSERT INTO token_usage (provider, model, input_tokens, output_tokens, user_id)
            VALUES ('gemini', 'gemini-pro', 500, 500, 'user1')
        """
        )
        await connection.commit()

        cursor = await connection.execute("SELECT COUNT(*) FROM token_usage")
        result = await cursor.fetchone()
        await cursor.close()

        assert result[0] == 1

    @pytest.mark.asyncio
    async def test_extend_transcriptions_migration(self, connection):
        """Test transcriptions table extension."""
        migration = ExtendTranscriptionsMigration()

        await migration.up(connection)
        await connection.commit()

        # Check table exists (created if not exists)
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='transcriptions'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None

        # Check new columns exist
        cursor = await connection.execute("PRAGMA table_info(transcriptions)")
        columns = await cursor.fetchall()
        await cursor.close()

        column_names = [col[1] for col in columns]
        assert "note_id" in column_names
        assert "tags" in column_names
        assert "links" in column_names

    @pytest.mark.asyncio
    async def test_create_fts5_migration(self, connection):
        """Test FTS5 index creation."""
        # Create knowledge_notes first (dependency)
        knowledge_migration = CreateKnowledgeNotesMigration()
        await knowledge_migration.up(connection)
        await connection.commit()

        migration = CreateFTS5IndexMigration()

        # Check if FTS5 is available (skip if not)
        try:
            await connection.execute("SELECT fts5_version()")
        except aiosqlite.OperationalError:
            pytest.skip("FTS5 not available in this SQLite build")

        await migration.up(connection)
        await connection.commit()

        # Check virtual table exists
        cursor = await connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='knowledge_notes_fts'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None

        # Test FTS5 search functionality
        await connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, user_id)
            VALUES ('test1', 'Test Title', 'Test content for search', 'user1')
        """
        )
        await connection.commit()

        # FTS5 should automatically index the content
        cursor = await connection.execute(
            """
            SELECT title FROM knowledge_notes_fts WHERE knowledge_notes_fts MATCH 'search'
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        assert result is not None
        assert result[0] == "Test Title"


class TestDatabaseServiceIntegration:
    """Integration tests for DatabaseService with migrations."""

    @pytest.mark.asyncio
    async def test_database_service_with_migrations(self, temp_db_path):
        """Test DatabaseService initialization with automatic migrations."""
        from nescordbot.services.database import DatabaseService

        service = DatabaseService(temp_db_path)

        # Initialize should run migrations
        await service.initialize()

        # Check migration table exists
        cursor = await service.connection.execute(
            """
            SELECT COUNT(*) FROM schema_migrations
        """
        )
        result = await cursor.fetchone()
        await cursor.close()

        # Should have applied 7 migrations (including Migration 007: note_history)
        assert result[0] == 7

        # Check new tables exist
        cursor = await service.connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN (
                'knowledge_notes', 'note_links', 'token_usage', 'note_history'
            )
        """
        )
        tables = await cursor.fetchall()
        await cursor.close()

        table_names = {row[0] for row in tables}
        assert "knowledge_notes" in table_names
        assert "note_links" in table_names
        assert "token_usage" in table_names
        assert "note_history" in table_names

        await service.close()

    @pytest.mark.asyncio
    async def test_search_notes_functionality(self, temp_db_path):
        """Test FTS5 search functionality through DatabaseService."""
        from nescordbot.services.database import DatabaseService

        service = DatabaseService(temp_db_path)
        await service.initialize()

        # Skip if FTS5 not available
        try:
            await service.connection.execute("SELECT fts5_version()")
        except aiosqlite.OperationalError:
            pytest.skip("FTS5 not available in this SQLite build")

        # Insert test data
        await service.connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, tags, user_id)
            VALUES ('note1', 'Python Programming',
                    'Learn Python basics and advanced features',
                    '["programming", "python"]', 'user1')
        """
        )
        await service.connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, tags, user_id)
            VALUES ('note2', 'JavaScript Guide',
                    'Web development with JavaScript',
                    '["programming", "javascript"]', 'user1')
        """
        )
        await service.connection.commit()

        # Test search
        results = await service.search_notes("Python", limit=5)

        assert len(results) == 1
        assert results[0]["id"] == "note1"
        assert results[0]["title"] == "Python Programming"
        assert results[0]["tags"] == ["programming", "python"]

        await service.close()

    @pytest.mark.asyncio
    async def test_note_links_functionality(self, temp_db_path):
        """Test note links functionality through DatabaseService."""
        from nescordbot.services.database import DatabaseService

        service = DatabaseService(temp_db_path)
        await service.initialize()

        # Insert test notes
        await service.connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, user_id)
            VALUES ('note1', 'Note 1', 'Content 1', 'user1')
        """
        )
        await service.connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, user_id)
            VALUES ('note2', 'Note 2', 'Content 2', 'user1')
        """
        )
        await service.connection.execute(
            """
            INSERT INTO knowledge_notes (id, title, content, user_id)
            VALUES ('note3', 'Note 3', 'Content 3', 'user1')
        """
        )

        # Create links
        await service.connection.execute(
            """
            INSERT INTO note_links (from_note_id, to_note_id, link_type)
            VALUES ('note1', 'note2', 'reference')
        """
        )
        await service.connection.execute(
            """
            INSERT INTO note_links (from_note_id, to_note_id, link_type)
            VALUES ('note3', 'note1', 'related')
        """
        )
        await service.connection.commit()

        # Test get_note_links
        links = await service.get_note_links("note1")

        assert len(links["outgoing"]) == 1
        assert len(links["incoming"]) == 1
        assert links["outgoing"][0]["note_id"] == "note2"
        assert links["incoming"][0]["note_id"] == "note3"

        await service.close()

    @pytest.mark.asyncio
    async def test_token_usage_stats(self, temp_db_path):
        """Test token usage statistics functionality."""
        from nescordbot.services.database import DatabaseService

        service = DatabaseService(temp_db_path)
        await service.initialize()

        # Insert test usage data
        await service.connection.execute(
            """
            INSERT INTO token_usage (provider, model, input_tokens, output_tokens, user_id)
            VALUES ('gemini', 'gemini-pro', 500, 500, 'user1')
        """
        )
        await service.connection.execute(
            """
            INSERT INTO token_usage (provider, model, input_tokens, output_tokens, user_id)
            VALUES ('gemini', 'gemini-1.5-pro', 1000, 1000, 'user1')
        """
        )
        await service.connection.execute(
            """
            INSERT INTO token_usage (provider, model, input_tokens, output_tokens, user_id)
            VALUES ('openai', 'gpt-3.5-turbo', 250, 250, 'user2')
        """
        )
        await service.connection.commit()

        # Test overall stats
        stats = await service.get_token_usage_stats()

        assert stats["total_tokens"] == 3500
        assert stats["total_requests"] == 3
        assert "gemini" in stats["usage_by_type"]
        assert "openai" in stats["usage_by_type"]

        # Test user-specific stats
        user_stats = await service.get_token_usage_stats(user_id="user1")

        assert user_stats["total_tokens"] == 3000
        assert user_stats["total_requests"] == 2

        await service.close()


class TestMigrationEdgeCases:
    """Tests for edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_database_migration(self, migration_manager):
        """Test migration on completely empty database."""
        result = await migration_manager.migrate_to_latest()

        assert result["applied"] == 7  # All 7 migrations applied (updated from 6 to 7)
        assert result["current_version"] == 7  # Updated from 6 to 7

    @pytest.mark.asyncio
    async def test_already_migrated_database(self, migration_manager):
        """Test migration on already up-to-date database."""
        # Apply all migrations first
        await migration_manager.migrate_to_latest()

        # Try to migrate again
        result = await migration_manager.migrate_to_latest()

        assert result["applied"] == 0  # No new migrations
        assert result["current_version"] == 7  # Updated from 6 to 7 (Migration 007 added)

    @pytest.mark.asyncio
    async def test_partial_migration_rollback(self, migration_manager):
        """Test rollback to specific version."""
        # Apply all migrations
        await migration_manager.migrate_to_latest()

        # Rollback to version 3
        result = await migration_manager.rollback_to_version(3)

        assert (
            result["rolled_back"] == 4
        )  # Versions 4, 5, 6, and 7 rolled back (updated from 3 to 4)
        assert result["current_version"] == 3

    @pytest.mark.asyncio
    async def test_migration_status_reporting(self, migration_manager):
        """Test migration status reporting."""
        # Apply first 3 migrations manually
        async with aiosqlite.connect(migration_manager.db_path) as connection:
            await migration_manager.initialize_migration_table(connection)

            for migration in migration_manager._migrations[:3]:
                await migration_manager.apply_migration(migration, connection)

        # Get status
        status = await migration_manager.get_migration_status()

        assert status["current_version"] == 3
        assert status["latest_version"] == 8  # Updated from 7 to 8 (Migration 008 added)
        assert status["applied_migrations"] == 3
        assert status["pending_migrations"] == 5  # Updated from 4 to 5 (one more pending migration)
        assert status["integrity_valid"] is True
        assert len(status["migrations"]["applied"]) == 3
        assert len(status["migrations"]["pending"]) == 5  # Updated from 4 to 5


@pytest.mark.asyncio
async def test_fts5_availability():
    """Test FTS5 availability detection."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        async with aiosqlite.connect(db_path) as connection:
            try:
                await connection.execute("SELECT fts5_version()")
                fts5_available = True
            except aiosqlite.OperationalError:
                fts5_available = False

        # This test documents FTS5 availability but doesn't fail
        # if FTS5 is not available in the test environment
        print(f"FTS5 available: {fts5_available}")

    finally:
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__])
