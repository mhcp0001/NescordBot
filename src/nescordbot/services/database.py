"""
Database service for NescordBot.

Provides a simple key-value store interface using aiosqlite for
data persistence with JSON support and basic operations.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class IDataStore(ABC):
    """
    Abstract interface for data storage operations.

    Defines the contract for data persistence services,
    allowing for different implementations (SQLite, Redis, etc.).
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the data store and create necessary structures."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the data store connection and clean up resources."""
        pass

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """
        Retrieve a value by key.

        Args:
            key: The key to retrieve

        Returns:
            The stored value or None if not found
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        """
        Store a key-value pair.

        Args:
            key: The key to store
            value: The value to store
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Delete a key-value pair.

        Args:
            key: The key to delete
        """
        pass

    @abstractmethod
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and deserialize a JSON value by key.

        Args:
            key: The key to retrieve

        Returns:
            The deserialized JSON object or None if not found/invalid
        """
        pass

    @abstractmethod
    async def set_json(self, key: str, value: Dict[str, Any]) -> None:
        """
        Serialize and store a JSON object.

        Args:
            key: The key to store
            value: The object to serialize and store
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists.

        Args:
            key: The key to check

        Returns:
            True if the key exists, False otherwise
        """
        pass

    @abstractmethod
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        List keys matching a pattern.

        Args:
            pattern: SQL LIKE pattern (default: "*" for all keys)

        Returns:
            List of matching keys
        """
        pass


class DatabaseService(IDataStore):
    """
    SQLite-based implementation of IDataStore.

    Provides persistent key-value storage with JSON support
    using aiosqlite for async operations.
    """

    def __init__(self, db_path: str = "nescord.db"):
        """
        Initialize the database service.

        Args:
            db_path: Path to the SQLite database file, SQLite URL, or ":memory:" for in-memory
        """
        # Parse SQLite URL if provided
        if db_path.startswith("sqlite:///"):
            # Extract path from sqlite:///path/to/file.db
            self.db_path = db_path[10:]  # Remove "sqlite:///"
        elif db_path.startswith("sqlite://"):
            # Handle sqlite://path (relative path)
            self.db_path = db_path[9:]  # Remove "sqlite://"
        else:
            self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Check if the database is initialized."""
        return self._initialized and self.connection is not None

    async def initialize(self) -> None:
        """Initialize the database and create the key-value table."""
        async with self._lock:
            if self._initialized:
                logger.warning("Database already initialized")
                return

            try:
                # Create directory if needed (except for in-memory)
                if self.db_path != ":memory:":
                    Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

                # Open connection
                self.connection = await aiosqlite.connect(self.db_path)

                # Enable WAL mode for better concurrent access
                if self.db_path != ":memory:":
                    await self.connection.execute("PRAGMA journal_mode=WAL")

                # Create table if not exists
                await self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS kv_store (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Create index for better performance
                await self.connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_kv_store_updated_at
                    ON kv_store(updated_at)
                """
                )

                await self.connection.commit()
                self._initialized = True

                logger.info(f"Database initialized: {self.db_path}")

            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                if self.connection:
                    await self.connection.close()
                    self.connection = None
                raise

    async def close(self) -> None:
        """Close the database connection."""
        async with self._lock:
            if self.connection:
                await self.connection.close()
                self.connection = None
                self._initialized = False
                logger.info("Database connection closed")

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a value by key."""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                cursor = await self.connection.execute(
                    "SELECT value FROM kv_store WHERE key = ?", (key,)
                )
                row = await cursor.fetchone()
                await cursor.close()

                return row[0] if row else None

            except Exception as e:
                logger.error(f"Failed to get key '{key}': {e}")
                raise

    async def set(self, key: str, value: str) -> None:
        """Store a key-value pair."""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                await self.connection.execute(
                    """
                    INSERT OR REPLACE INTO kv_store (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (key, value),
                )
                await self.connection.commit()

                logger.debug(f"Set key '{key}' with {len(value)} characters")

            except Exception as e:
                logger.error(f"Failed to set key '{key}': {e}")
                raise

    async def delete(self, key: str) -> None:
        """Delete a key-value pair."""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                cursor = await self.connection.execute("DELETE FROM kv_store WHERE key = ?", (key,))
                await self.connection.commit()

                if cursor.rowcount > 0:
                    logger.debug(f"Deleted key '{key}'")
                else:
                    logger.debug(f"Key '{key}' not found for deletion")

                await cursor.close()

            except Exception as e:
                logger.error(f"Failed to delete key '{key}': {e}")
                raise

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve and deserialize a JSON value by key."""
        value = await self.get(key)
        if value is None:
            return None

        try:
            result = json.loads(value)
            return result if isinstance(result, dict) else None
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to parse JSON for key '{key}': {e}")
            return None

    async def set_json(self, key: str, value: Dict[str, Any]) -> None:
        """Serialize and store a JSON object."""
        try:
            json_str = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            await self.set(key, json_str)
            logger.debug(f"Set JSON key '{key}' with {len(json_str)} characters")
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize JSON for key '{key}': {e}")
            raise

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                cursor = await self.connection.execute(
                    "SELECT 1 FROM kv_store WHERE key = ? LIMIT 1", (key,)
                )
                row = await cursor.fetchone()
                await cursor.close()

                return row is not None

            except Exception as e:
                logger.error(f"Failed to check existence of key '{key}': {e}")
                raise

    async def keys(self, pattern: str = "*") -> List[str]:
        """List keys matching a pattern."""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                # Convert shell-style patterns to SQL LIKE patterns
                sql_pattern = pattern.replace("*", "%").replace("?", "_")

                cursor = await self.connection.execute(
                    "SELECT key FROM kv_store WHERE key LIKE ? ORDER BY key", (sql_pattern,)
                )
                rows = await cursor.fetchall()
                await cursor.close()

                return [row[0] for row in rows]

            except Exception as e:
                logger.error(f"Failed to list keys with pattern '{pattern}': {e}")
                raise

    async def clear(self) -> None:
        """Clear all data from the store. Use with caution!"""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                await self.connection.execute("DELETE FROM kv_store")
                await self.connection.commit()
                logger.warning("All data cleared from database")

            except Exception as e:
                logger.error(f"Failed to clear database: {e}")
                raise

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        if not self.is_initialized or self.connection is None:
            raise RuntimeError("Database not initialized")

        async with self._lock:
            try:
                # Count total keys
                cursor = await self.connection.execute("SELECT COUNT(*) FROM kv_store")
                row = await cursor.fetchone()
                total_keys = row[0] if row else 0
                await cursor.close()

                # Get database file size (if not in-memory)
                db_size = 0
                if self.db_path != ":memory:":
                    db_file = Path(self.db_path)
                    if db_file.exists():
                        db_size = db_file.stat().st_size

                return {
                    "total_keys": total_keys,
                    "db_path": self.db_path,
                    "db_size_bytes": db_size,
                    "is_memory": self.db_path == ":memory:",
                    "is_initialized": self._initialized,
                }

            except Exception as e:
                logger.error(f"Failed to get database stats: {e}")
                raise

    def get_connection(self):
        """Get a context manager for the database connection."""
        return DatabaseConnectionManager(self)


class DatabaseConnectionManager:
    """Context manager for database connections."""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    async def __aenter__(self):
        if not self.db_service.is_initialized or self.db_service.connection is None:
            raise RuntimeError("Database not initialized")
        return DatabaseConnectionProxy(self.db_service)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class DatabaseConnectionProxy:
    """Proxy for database connection with proper locking."""

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service

    async def execute(self, query: str, parameters=None):
        """Execute a query with proper locking."""
        if self.db_service.connection is None:
            raise RuntimeError("Database connection is None")
        async with self.db_service._lock:
            return await self.db_service.connection.execute(query, parameters or [])

    async def executescript(self, script: str):
        """Execute a script with proper locking."""
        if self.db_service.connection is None:
            raise RuntimeError("Database connection is None")
        async with self.db_service._lock:
            await self.db_service.connection.executescript(script)

    async def commit(self):
        """Commit transaction with proper locking."""
        if self.db_service.connection is None:
            raise RuntimeError("Database connection is None")
        async with self.db_service._lock:
            await self.db_service.connection.commit()
