"""
Knowledge management service for Personal Knowledge Management (PKM) functionality.

This module provides comprehensive note management, link extraction, tag management,
and integration with ChromaDB and ObsidianGitHub services for the NescordBot Phase 4.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import BotConfig
from .chromadb_service import ChromaDBService
from .database import DatabaseService
from .embedding import EmbeddingService
from .link_graph_builder import LinkCluster, LinkGraphBuilder
from .link_suggestor import LinkSuggestor
from .link_validator import LinkValidationResult, LinkValidator
from .obsidian_github import ObsidianGitHubService
from .sync_manager import SyncManager

logger = logging.getLogger(__name__)


class KnowledgeManagerError(Exception):
    """Exception raised when knowledge management operations fail."""

    pass


class KnowledgeManager:
    """
    Manages personal knowledge management operations for NescordBot.

    Features:
    - Note CRUD operations with knowledge_notes table
    - Link extraction and management ([[note_name]] pattern)
    - Tag management and organization
    - Integration with ChromaDB for vector storage
    - ObsidianGitHub integration for external persistence
    """

    def __init__(
        self,
        config: BotConfig,
        database_service: DatabaseService,
        chromadb_service: ChromaDBService,
        embedding_service: EmbeddingService,
        sync_manager: SyncManager,
        obsidian_github_service: ObsidianGitHubService,
    ) -> None:
        """
        Initialize KnowledgeManager.

        Args:
            config: Bot configuration
            database_service: Database service for SQLite operations
            chromadb_service: ChromaDB service for vector operations
            embedding_service: Embedding service for text vectorization
            sync_manager: Synchronization manager for data consistency
            obsidian_github_service: ObsidianGitHub service for external storage
        """
        self.config = config
        self.db = database_service
        self.chromadb = chromadb_service
        self.embedding = embedding_service
        self.sync_manager = sync_manager
        self.obsidian_github = obsidian_github_service
        self._initialized = False

        # Link and tag extraction patterns
        self.link_pattern = re.compile(r"\[\[([^\]]+)\]\]")
        self.tag_pattern = re.compile(r"#(\w+)")

        # Initialize link management services
        self.link_suggestor = LinkSuggestor(database_service)
        self.link_validator = LinkValidator(database_service)
        self.link_graph_builder = LinkGraphBuilder(database_service)

    async def initialize(self) -> None:
        """Initialize async resources and verify dependencies."""
        if self._initialized:
            return

        try:
            # Ensure all dependencies are initialized
            if not self.db.is_initialized:
                raise KnowledgeManagerError("DatabaseService not initialized")

            # Verify required tables exist
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_notes'"
                )
                if not await cursor.fetchone():
                    raise KnowledgeManagerError("knowledge_notes table not found")

                cursor = await conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='note_links'"
                )
                if not await cursor.fetchone():
                    raise KnowledgeManagerError("note_links table not found")

            # Initialize link management services
            await self.link_suggestor.initialize()
            await self.link_validator.initialize()
            await self.link_graph_builder.initialize()

            self._initialized = True
            logger.info("KnowledgeManager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize KnowledgeManager: {e}")
            raise KnowledgeManagerError(f"Initialization failed: {e}")

    async def create_note(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source_type: str = "manual",
        source_id: Optional[str] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        guild_id: Optional[str] = None,
    ) -> str:
        """
        Create a new knowledge note.

        Args:
            title: Note title
            content: Note content
            tags: List of tags for categorization
            source_type: Source type ('voice', 'text', 'manual')
            source_id: Source reference ID
            user_id: Discord user ID
            channel_id: Discord channel ID
            guild_id: Discord guild ID

        Returns:
            Note ID

        Raises:
            KnowledgeManagerError: If creation fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            note_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            # Extract links and tags from content
            extracted_links = self.extract_links(content)
            extracted_tags = self.extract_tags(content)

            # Combine with provided tags
            all_tags = list(set((tags or []) + extracted_tags))
            tags_json = json.dumps(all_tags, ensure_ascii=False)

            # Insert into knowledge_notes table
            insert_sql = """
            INSERT INTO knowledge_notes (
                id, title, content, tags, source_type, source_id,
                user_id, channel_id, guild_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            async with self.db.get_connection() as conn:
                await conn.execute(
                    insert_sql,
                    (
                        note_id,
                        title,
                        content,
                        tags_json,
                        source_type,
                        source_id,
                        user_id,
                        channel_id,
                        guild_id,
                        now,
                        now,
                    ),
                )
                await conn.commit()

            # Process links
            if extracted_links:
                await self.update_links(note_id, content)

            # Sync with external services
            await self._sync_note_to_services(note_id)

            logger.info(f"Created note: {note_id} - {title}")
            return note_id

        except Exception as e:
            logger.error(f"Failed to create note: {e}")
            raise KnowledgeManagerError(f"Failed to create note: {e}")

    async def update_note(
        self,
        note_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        Update an existing knowledge note.

        Args:
            note_id: Note ID to update
            title: New title (optional)
            content: New content (optional)
            tags: New tags (optional)

        Returns:
            True if update succeeded

        Raises:
            KnowledgeManagerError: If update fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get existing note
            existing_note = await self.get_note(note_id)
            if not existing_note:
                raise KnowledgeManagerError(f"Note not found: {note_id}")

            # Prepare update data
            update_fields = []
            update_values = []

            if title is not None:
                update_fields.append("title = ?")
                update_values.append(title)

            if content is not None:
                update_fields.append("content = ?")
                update_values.append(content)

                # Update links if content changed
                await self.update_links(note_id, content)

            if tags is not None:
                # Combine provided tags with extracted tags
                extracted_tags = self.extract_tags(content or existing_note["content"])
                all_tags = list(set(tags + extracted_tags))
                tags_json = json.dumps(all_tags, ensure_ascii=False)

                update_fields.append("tags = ?")
                update_values.append(tags_json)

            if not update_fields:
                return True  # Nothing to update

            # Update updated_at timestamp
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat())

            # Execute update
            update_sql = f"UPDATE knowledge_notes SET {', '.join(update_fields)} WHERE id = ?"
            update_values.append(note_id)

            async with self.db.get_connection() as conn:
                await conn.execute(update_sql, update_values)
                await conn.commit()

            # Sync with external services
            await self._sync_note_to_services(note_id)

            logger.info(f"Updated note: {note_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update note {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to update note: {e}")

    async def delete_note(self, note_id: str) -> bool:
        """
        Delete a knowledge note and all related links.

        Args:
            note_id: Note ID to delete

        Returns:
            True if deletion succeeded

        Raises:
            KnowledgeManagerError: If deletion fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Check if note exists
            existing_note = await self.get_note(note_id)
            if not existing_note:
                return False

            async with self.db.get_connection() as conn:
                # Delete from note_links (both directions)
                await conn.execute(
                    "DELETE FROM note_links WHERE from_note_id = ? OR to_note_id = ?",
                    (note_id, note_id),
                )

                # Delete from knowledge_notes
                await conn.execute("DELETE FROM knowledge_notes WHERE id = ?", (note_id,))

                await conn.commit()

            # Remove from ChromaDB
            try:
                await self.chromadb.delete_document(note_id)
            except Exception as e:
                logger.warning(f"Failed to delete from ChromaDB: {e}")

            logger.info(f"Deleted note: {note_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete note {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to delete note: {e}")

    async def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a knowledge note by ID.

        Args:
            note_id: Note ID to retrieve

        Returns:
            Note data dict or None if not found

        Raises:
            KnowledgeManagerError: If retrieval fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            query_sql = """
            SELECT id, title, content, tags, source_type, source_id,
                   user_id, channel_id, guild_id, created_at, updated_at, vector_updated_at
            FROM knowledge_notes
            WHERE id = ?
            """

            async with self.db.get_connection() as conn:
                cursor = await conn.execute(query_sql, (note_id,))
                row = await cursor.fetchone()

            if not row:
                return None

            # Parse tags JSON
            tags = json.loads(row[3]) if row[3] else []

            return {
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "tags": tags,
                "source_type": row[4],
                "source_id": row[5],
                "user_id": row[6],
                "channel_id": row[7],
                "guild_id": row[8],
                "created_at": row[9],
                "updated_at": row[10],
                "vector_updated_at": row[11],
            }

        except Exception as e:
            logger.error(f"Failed to get note {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to retrieve note: {e}")

    def extract_links(self, content: str) -> List[str]:
        """
        Extract [[note_name]] pattern links from content.

        Args:
            content: Text content to extract links from

        Returns:
            List of extracted link names
        """
        matches = self.link_pattern.findall(content)
        return [match.strip() for match in matches if match.strip()]

    def extract_tags(self, content: str) -> List[str]:
        """
        Extract #tag pattern tags from content.

        Args:
            content: Text content to extract tags from

        Returns:
            List of extracted tag names
        """
        matches = self.tag_pattern.findall(content)
        return [match.lower() for match in matches if match]

    async def update_links(self, note_id: str, content: str) -> None:
        """
        Update note links based on content analysis.

        Args:
            note_id: Source note ID
            content: Content to analyze for links

        Raises:
            KnowledgeManagerError: If link update fails
        """
        try:
            extracted_links = self.extract_links(content)

            async with self.db.get_connection() as conn:
                # Remove existing outgoing links
                await conn.execute("DELETE FROM note_links WHERE from_note_id = ?", (note_id,))

                # Add new links
                for link_name in extracted_links:
                    # Try to find target note by title
                    cursor = await conn.execute(
                        "SELECT id FROM knowledge_notes WHERE title = ?",
                        (link_name,),
                    )
                    target_row = await cursor.fetchone()

                    if target_row:
                        target_id = target_row[0]
                        # Use NULL for id to let AUTOINCREMENT handle it
                        await conn.execute(
                            "INSERT INTO note_links "
                            "(from_note_id, to_note_id, link_type, created_at) "
                            "VALUES (?, ?, ?, ?)",
                            (note_id, target_id, "reference", datetime.now().isoformat()),
                        )

                await conn.commit()

        except Exception as e:
            logger.error(f"Failed to update links for note {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to update links: {e}")

    async def get_linked_notes(self, note_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all notes linked to/from the specified note.

        Args:
            note_id: Note ID to get links for

        Returns:
            Dict with 'outgoing' and 'incoming' link lists

        Raises:
            KnowledgeManagerError: If link retrieval fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db.get_connection() as conn:
                # Get outgoing links
                outgoing_cursor = await conn.execute(
                    """
                    SELECT kn.id, kn.title, kn.tags, nl.link_type, nl.created_at
                    FROM note_links nl
                    JOIN knowledge_notes kn ON nl.to_note_id = kn.id
                    WHERE nl.from_note_id = ?
                    ORDER BY nl.created_at DESC
                    """,
                    (note_id,),
                )
                outgoing_rows = await outgoing_cursor.fetchall()

                # Get incoming links
                incoming_cursor = await conn.execute(
                    """
                    SELECT kn.id, kn.title, kn.tags, nl.link_type, nl.created_at
                    FROM note_links nl
                    JOIN knowledge_notes kn ON nl.from_note_id = kn.id
                    WHERE nl.to_note_id = ?
                    ORDER BY nl.created_at DESC
                    """,
                    (note_id,),
                )
                incoming_rows = await incoming_cursor.fetchall()

            # Format results
            def format_link_row(row):
                return {
                    "id": row[0],
                    "title": row[1],
                    "tags": json.loads(row[2]) if row[2] else [],
                    "link_type": row[3],
                    "created_at": row[4],
                }

            return {
                "outgoing": [format_link_row(row) for row in outgoing_rows],
                "incoming": [format_link_row(row) for row in incoming_rows],
            }

        except Exception as e:
            logger.error(f"Failed to get linked notes for {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to get linked notes: {e}")

    async def get_notes_by_tag(self, tag: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get notes that contain the specified tag.

        Args:
            tag: Tag name to search for
            limit: Maximum number of notes to return

        Returns:
            List of note dictionaries

        Raises:
            KnowledgeManagerError: If search fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            query_sql = """
            SELECT id, title, content, tags, source_type, created_at, updated_at
            FROM knowledge_notes
            WHERE JSON_EXTRACT(tags, '$') LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
            """

            async with self.db.get_connection() as conn:
                cursor = await conn.execute(query_sql, (f'%"{tag}"%', limit))
                rows = await cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "tags": json.loads(row[3]) if row[3] else [],
                    "source_type": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to search notes by tag {tag}: {e}")
            raise KnowledgeManagerError(f"Failed to search by tag: {e}")

    async def list_notes(
        self,
        tags: Optional[List[str]] = None,
        source_type: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List knowledge notes with optional filtering.

        Args:
            tags: Filter by tags (AND operation)
            source_type: Filter by source type
            user_id: Filter by user ID
            limit: Maximum number of notes to return
            offset: Offset for pagination

        Returns:
            List of note dictionaries

        Raises:
            KnowledgeManagerError: If listing fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            where_conditions = []
            params: List[str] = []

            # Tag filtering
            if tags:
                for tag in tags:
                    where_conditions.append("JSON_EXTRACT(tags, '$') LIKE ?")
                    params.append(f'%"{tag}"%')

            # Source type filtering
            if source_type:
                where_conditions.append("source_type = ?")
                params.append(source_type)

            # User filtering
            if user_id:
                where_conditions.append("user_id = ?")
                params.append(user_id)

            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

            query_sql = f"""
            SELECT id, title, content, tags, source_type, user_id, created_at, updated_at
            FROM knowledge_notes
            {where_clause}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """

            # Add limit and offset as strings for SQLite compatibility
            params.extend([str(limit), str(offset)])

            async with self.db.get_connection() as conn:
                cursor = await conn.execute(query_sql, params)
                rows = await cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "content": row[2],
                    "tags": json.loads(row[3]) if row[3] else [],
                    "source_type": row[4],
                    "user_id": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to list notes: {e}")
            raise KnowledgeManagerError(f"Failed to list notes: {e}")

    async def merge_notes(self, note_ids: List[str], new_title: Optional[str] = None) -> str:
        """
        Merge multiple notes into a single permanent note.

        Args:
            note_ids: List of note IDs to merge
            new_title: Title for merged note (optional)

        Returns:
            ID of the merged note

        Raises:
            KnowledgeManagerError: If merge fails
        """
        if not self._initialized:
            await self.initialize()

        if len(note_ids) < 2:
            raise KnowledgeManagerError("At least 2 notes required for merge")

        try:
            # Get all notes to merge
            notes = []
            all_tags = set()

            for note_id in note_ids:
                note = await self.get_note(note_id)
                if note:
                    notes.append(note)
                    all_tags.update(note["tags"])

            if not notes:
                raise KnowledgeManagerError("No valid notes found for merge")

            # Generate merged content
            merged_title = (
                new_title or f"Merged: {', '.join([note['title'] for note in notes[:3]])}"
            )
            merged_content = self._generate_merged_content(notes)
            merged_tags = list(all_tags)

            # Create new merged note
            merged_note_id = await self.create_note(
                title=merged_title,
                content=merged_content,
                tags=merged_tags,
                source_type="merged",
                user_id=notes[0]["user_id"],
                channel_id=notes[0]["channel_id"],
                guild_id=notes[0]["guild_id"],
            )

            # Delete original notes
            for note_id in note_ids:
                await self.delete_note(note_id)

            logger.info(f"Merged {len(note_ids)} notes into {merged_note_id}")
            return merged_note_id

        except Exception as e:
            logger.error(f"Failed to merge notes {note_ids}: {e}")
            raise KnowledgeManagerError(f"Failed to merge notes: {e}")

    async def _sync_note_to_services(self, note_id: str) -> None:
        """
        Sync note to external services (ChromaDB, ObsidianGitHub).

        Args:
            note_id: Note ID to sync
        """
        try:
            # Trigger sync via SyncManager
            await self.sync_manager.sync_note_to_chromadb(note_id)

            # Save to ObsidianGitHub if configured
            note = await self.get_note(note_id)
            if note and self.config.github_obsidian_enabled:
                # Create markdown filename from note title
                safe_title = "".join(
                    c for c in note["title"] if c.isalnum() or c in (" ", "-", "_")
                ).strip()
                filename = f"{safe_title}.md"

                # Create markdown content with frontmatter
                tags = note["tags"]
                frontmatter = f"""---
title: {note["title"]}
tags: {', '.join(tags)}
created: {note["created_at"]}
updated: {note["updated_at"]}
---

"""
                content = frontmatter + note["content"]

                await self.obsidian_github.save_to_obsidian(
                    filename=filename,
                    content=content,
                    directory="knowledge_notes",
                    metadata={
                        "note_id": note_id,
                        "source_type": note["source_type"],
                        "user_id": note["user_id"],
                    },
                )

        except Exception as e:
            logger.warning(f"Failed to sync note {note_id} to services: {e}")

    def _generate_merged_content(self, notes: List[Dict[str, Any]]) -> str:
        """
        Generate merged content from multiple notes.

        Args:
            notes: List of note dictionaries

        Returns:
            Merged content string
        """
        merged_parts = []
        merged_parts.append("# Merged Notes")
        merged_parts.append(f"**Merged on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        merged_parts.append(f"**Source notes**: {len(notes)}")
        merged_parts.append("")

        for i, note in enumerate(notes, 1):
            merged_parts.append(f"## {i}. {note['title']}")
            merged_parts.append(f"**Created**: {note['created_at']}")
            merged_parts.append(f"**Tags**: {', '.join(note['tags'])}")
            merged_parts.append("")
            merged_parts.append(note["content"])
            merged_parts.append("")
            merged_parts.append("---")
            merged_parts.append("")

        return "\n".join(merged_parts)

    async def search_notes(
        self, query: str, tags: Optional[List[str]] = None, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search notes using database full-text search.

        Args:
            query: Search query string
            tags: Optional tag filters
            limit: Maximum number of results

        Returns:
            List of matching notes

        Raises:
            KnowledgeManagerError: If search fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Use DatabaseService search_notes method
            results = await self.db.search_notes(query, limit=limit)

            # Apply tag filtering if specified
            if tags:
                filtered_results = []
                for note in results:
                    note_tags = set(note.get("tags", []))
                    if any(tag in note_tags for tag in tags):
                        filtered_results.append(note)
                return filtered_results

            return results

        except Exception as e:
            logger.error(f"Failed to search notes: {e}")
            raise KnowledgeManagerError(f"Failed to search notes: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on KnowledgeManager."""
        try:
            if not self._initialized:
                return {"status": "unhealthy", "error": "Not initialized"}

            # Test database connectivity
            async with self.db.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM knowledge_notes")
                note_count = (await cursor.fetchone())[0]

                cursor = await conn.execute("SELECT COUNT(*) FROM note_links")
                link_count = (await cursor.fetchone())[0]

            return {
                "status": "healthy",
                "initialized": self._initialized,
                "note_count": note_count,
                "link_count": link_count,
                "services": {
                    "database": self.db.is_initialized,
                    "chromadb": self.chromadb._initialized
                    if hasattr(self.chromadb, "_initialized")
                    else False,
                    "embedding": hasattr(self.embedding, "_initialized"),
                    "sync_manager": hasattr(self.sync_manager, "_initialized"),
                },
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    # Link Management Methods

    async def suggest_links_for_note(
        self, note_id: str, max_suggestions: int = 5, min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Suggest potential links for a note based on content similarity.

        Args:
            note_id: ID of the note to suggest links for
            max_suggestions: Maximum number of suggestions to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of suggested notes with similarity scores
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_suggestor.suggest_links_for_note(
            note_id, max_suggestions, min_similarity
        )

    async def suggest_links_by_content(
        self, content: str, exclude_note_id: Optional[str] = None, max_suggestions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Suggest notes based on content keywords.

        Args:
            content: Content to analyze for keywords
            exclude_note_id: Note ID to exclude from suggestions
            max_suggestions: Maximum number of suggestions

        Returns:
            List of suggested notes
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_suggestor.suggest_by_content_keywords(
            content, exclude_note_id, max_suggestions
        )

    async def validate_all_links(self) -> LinkValidationResult:
        """
        Validate all links in the knowledge base.

        Returns:
            Comprehensive validation results
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_validator.validate_all_links()

    async def validate_note_links(self, note_id: str) -> Dict[str, Any]:
        """
        Validate links for a specific note.

        Args:
            note_id: ID of the note to validate

        Returns:
            Validation results for the specific note
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_validator.validate_note_links(note_id)

    async def find_missing_bidirectional_links(self) -> List[Dict[str, Any]]:
        """
        Find links that should be bidirectional but aren't.

        Returns:
            List of missing reverse links
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_validator.find_missing_bidirectional_links()

    async def repair_broken_links(self, validation_result: LinkValidationResult) -> Dict[str, int]:
        """
        Repair broken links by removing invalid entries.

        Args:
            validation_result: Result from validate_all_links()

        Returns:
            Count of repaired items
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_validator.repair_broken_links(validation_result)

    async def build_link_graph(self, include_orphans: bool = False):
        """
        Build a directed graph from note links.

        Args:
            include_orphans: Whether to include notes without links

        Returns:
            NetworkX directed graph
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_graph_builder.build_graph(include_orphans)

    async def find_note_clusters(self, min_cluster_size: int = 3) -> List[LinkCluster]:
        """
        Find clusters of highly connected notes.

        Args:
            min_cluster_size: Minimum number of notes in a cluster

        Returns:
            List of identified clusters
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_graph_builder.find_clusters(min_cluster_size)

    async def find_central_notes(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Find the most central/important notes in the graph.

        Args:
            top_n: Number of top central notes to return

        Returns:
            List of notes with centrality scores
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_graph_builder.find_central_notes(top_n)

    async def find_shortest_path(self, from_note_id: str, to_note_id: str) -> Optional[List[str]]:
        """
        Find shortest path between two notes.

        Args:
            from_note_id: Starting note ID
            to_note_id: Target note ID

        Returns:
            List of note IDs in the shortest path, or None if no path exists
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_graph_builder.find_shortest_path(from_note_id, to_note_id)

    async def get_graph_metrics(self) -> Dict[str, Any]:
        """
        Get overall graph metrics and statistics.

        Returns:
            Dictionary with graph metrics
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_graph_builder.get_graph_metrics()

    async def suggest_bridge_notes(
        self, cluster1_id: str, cluster2_id: str, clusters: List[LinkCluster]
    ) -> List[Dict[str, Any]]:
        """
        Suggest notes that could bridge two clusters.

        Args:
            cluster1_id: First cluster ID
            cluster2_id: Second cluster ID
            clusters: List of all clusters

        Returns:
            List of potential bridge notes
        """
        if not self._initialized:
            await self.initialize()

        return await self.link_graph_builder.suggest_bridge_notes(
            cluster1_id, cluster2_id, clusters
        )

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False
        logger.info("KnowledgeManager closed")
