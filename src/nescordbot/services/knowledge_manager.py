"""
Knowledge management service for Personal Knowledge Management (PKM) functionality.

This module provides comprehensive note management, link extraction, tag management,
and integration with ChromaDB and ObsidianGitHub services for the NescordBot Phase 4.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, cast

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
        obsidian_github_service: Optional[ObsidianGitHubService],
        fallback_manager: Optional[Any] = None,
    ) -> None:
        """
        Initialize KnowledgeManager.

        Args:
            config: Bot configuration
            database_service: Database service for SQLite operations
            chromadb_service: ChromaDB service for vector operations
            embedding_service: Embedding service for text vectorization
            sync_manager: Synchronization manager for data consistency
            obsidian_github_service: Optional ObsidianGitHub service for external storage
            fallback_manager: Optional fallback manager for API limiting
        """
        self.config = config
        self.db = database_service
        self.chromadb = chromadb_service
        self.embedding = embedding_service
        self.sync_manager = sync_manager
        self.obsidian_github = obsidian_github_service
        self.fallback_manager = fallback_manager
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
        user_id: Optional[str] = None,
    ) -> bool:
        """
        Update an existing knowledge note with history tracking.

        Args:
            note_id: Note ID to update
            title: New title (optional)
            content: New content (optional)
            tags: New tags (optional)
            user_id: User ID for history tracking (optional)

        Returns:
            True if update succeeded

        Raises:
            KnowledgeManagerError: If update fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Get existing note for history tracking
            existing_note = await self.get_note(note_id)
            if not existing_note:
                raise KnowledgeManagerError(f"Note not found: {note_id}")

            # Store original values for history
            title_before = existing_note["title"]
            content_before = existing_note["content"]
            tags_before = existing_note["tags"]

            # Prepare update data
            update_fields = []
            update_values = []

            final_title = title if title is not None else title_before
            final_content = content if content is not None else content_before
            final_tags = tags if tags is not None else tags_before

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
                extracted_tags = self.extract_tags(final_content)
                all_tags = list(set(tags + extracted_tags))
                tags_json = json.dumps(all_tags, ensure_ascii=False)
                final_tags = all_tags

                update_fields.append("tags = ?")
                update_values.append(tags_json)

            if not update_fields:
                return True  # Nothing to update

            # Update updated_at timestamp
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat())

            async with self.db.get_connection() as conn:
                # Execute update
                update_sql = f"UPDATE knowledge_notes SET {', '.join(update_fields)} WHERE id = ?"
                update_values.append(note_id)
                await conn.execute(update_sql, update_values)

                # Save edit history if any changes were made
                if user_id and (title is not None or content is not None or tags is not None):
                    await self._save_edit_history(
                        conn,
                        note_id=note_id,
                        title_before=title_before,
                        content_before=content_before,
                        tags_before=tags_before,
                        title_after=final_title,
                        content_after=final_content,
                        tags_after=final_tags,
                        user_id=user_id,
                    )

                await conn.commit()

            # Sync with external services
            await self._sync_note_to_services(note_id)

            logger.info(f"Updated note: {note_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update note {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to update note: {e}")

    async def _save_edit_history(
        self,
        conn,
        note_id: str,
        title_before: str,
        content_before: str,
        tags_before: List[str],
        title_after: str,
        content_after: str,
        tags_after: List[str],
        user_id: str,
    ) -> None:
        """Save edit history record."""
        await conn.execute(
            """
            INSERT INTO note_history (
                note_id, title_before, content_before, tags_before,
                title_after, content_after, tags_after, user_id, edit_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'update')
        """,
            (
                note_id,
                title_before,
                content_before,
                json.dumps(tags_before, ensure_ascii=False),
                title_after,
                content_after,
                json.dumps(tags_after, ensure_ascii=False),
                user_id,
            ),
        )

    async def get_note_history(self, note_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get edit history for a note.

        Args:
            note_id: Note ID to get history for
            limit: Maximum number of history records to return

        Returns:
            List of history records with diff information

        Raises:
            KnowledgeManagerError: If history retrieval fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT id, title_before, content_before, tags_before,
                           title_after, content_after, tags_after,
                           user_id, edit_type, timestamp
                    FROM note_history
                    WHERE note_id = ?
                    ORDER BY timestamp DESC, id DESC
                    LIMIT ?
                """,
                    (note_id, limit),
                )

                rows = await cursor.fetchall()
                await cursor.close()

                history = []
                for row in rows:
                    (
                        history_id,
                        title_before,
                        content_before,
                        tags_before,
                        title_after,
                        content_after,
                        tags_after,
                        user_id,
                        edit_type,
                        timestamp,
                    ) = row

                    # Parse tags from JSON
                    tags_before_parsed = json.loads(tags_before) if tags_before else []
                    tags_after_parsed = json.loads(tags_after) if tags_after else []

                    # Generate diff information
                    diffs = self._generate_edit_diff(
                        title_before,
                        content_before,
                        tags_before_parsed,
                        title_after,
                        content_after,
                        tags_after_parsed,
                    )

                    history.append(
                        {
                            "id": history_id,
                            "user_id": user_id,
                            "edit_type": edit_type,
                            "timestamp": timestamp,
                            "changes": diffs,
                            "title_before": title_before,
                            "content_before": content_before,
                            "tags_before": tags_before_parsed,
                            "title_after": title_after,
                            "content_after": content_after,
                            "tags_after": tags_after_parsed,
                        }
                    )

                return history

        except Exception as e:
            logger.error(f"Failed to get note history for {note_id}: {e}")
            raise KnowledgeManagerError(f"Failed to get note history: {e}")

    def _generate_edit_diff(
        self,
        title_before: str,
        content_before: str,
        tags_before: List[str],
        title_after: str,
        content_after: str,
        tags_after: List[str],
    ) -> Dict[str, Any]:
        """Generate diff information for edit history."""
        import difflib

        changes = {}

        # Title changes
        if title_before != title_after:
            changes["title"] = {
                "before": title_before,
                "after": title_after,
                "changed": True,
            }

        # Content changes
        if content_before != content_after:
            # Generate unified diff
            content_diff = list(
                difflib.unified_diff(
                    content_before.splitlines(keepends=True),
                    content_after.splitlines(keepends=True),
                    fromfile="before",
                    tofile="after",
                    lineterm="",
                )
            )

            changes["content"] = {
                "before_lines": len(content_before.splitlines()),
                "after_lines": len(content_after.splitlines()),
                "diff": content_diff,
                "changed": True,
            }

        # Tags changes
        tags_before_set = set(tags_before)
        tags_after_set = set(tags_after)

        if tags_before_set != tags_after_set:
            added_tags = list(tags_after_set - tags_before_set)
            removed_tags = list(tags_before_set - tags_after_set)

            changes["tags"] = {
                "added": added_tags,
                "removed": removed_tags,
                "before": tags_before,
                "after": tags_after,
                "changed": True,
            }

        return changes

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

    async def suggest_tags_for_content(
        self,
        content: str,
        title: str = "",
        existing_tags: Optional[List[str]] = None,
        max_suggestions: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Suggest tags for content using AI analysis with fallback support.

        Args:
            content: Text content to analyze
            title: Optional title for additional context
            existing_tags: Existing manual tags to consider
            max_suggestions: Maximum number of tag suggestions

        Returns:
            List of tag suggestions with confidence scores
        """
        if not content.strip():
            return []

        try:
            # Check fallback manager for tag suggestion availability
            if self.fallback_manager and not self.fallback_manager.is_service_available(
                "tag_suggestion"
            ):
                logger.info("Tag suggestion service unavailable due to API limits, checking cache")
                # Try to get cached suggestions
                cache_key = f"{hash(content + title)}"
                cached_suggestions = await self.fallback_manager.get_cached_data(
                    "tag_suggestions", cache_key
                )
                if cached_suggestions:
                    logger.info("Returning cached tag suggestions")
                    return cast(List[Dict[str, Any]], cached_suggestions[:max_suggestions])
                else:
                    logger.warning("No cached tag suggestions available, returning basic tags")
                    return self._generate_basic_tag_suggestions(content, title, existing_tags or [])

            # Prepare content for analysis
            analysis_text = f"Title: {title}\n\nContent: {content}" if title else content

            # Get existing tags from database for context
            all_existing_tags = await self._get_all_existing_tags()

            # Call Gemini for content analysis
            import google.generativeai as genai

            genai.configure(api_key=self.config.gemini_api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

            # Create prompt for tag suggestion
            prompt = self._create_tag_suggestion_prompt(
                analysis_text, all_existing_tags, existing_tags or [], max_suggestions
            )

            # Generate suggestions
            response = await model.generate_content_async(prompt)

            # Parse response
            suggestions = self._parse_tag_suggestions(response.text)

            # Filter and score suggestions
            filtered_suggestions = self._filter_and_score_suggestions(
                suggestions, existing_tags or [], all_existing_tags
            )

            final_suggestions = filtered_suggestions[:max_suggestions]

            # Cache the suggestions for fallback
            if self.fallback_manager:
                cache_key = f"{hash(content + title)}"
                await self.fallback_manager.cache_data(
                    "tag_suggestions", cache_key, final_suggestions
                )

            return final_suggestions

        except Exception as e:
            logger.error(f"Error in tag suggestion: {str(e)}")
            # Try fallback cache on error
            if self.fallback_manager:
                cache_key = f"{hash(content + title)}"
                cached_suggestions = await self.fallback_manager.get_cached_data(
                    "tag_suggestions", cache_key
                )
                if cached_suggestions:
                    logger.info("Returning cached tag suggestions due to error")
                    return cast(List[Dict[str, Any]], cached_suggestions[:max_suggestions])
            return []

    async def auto_categorize_notes(
        self,
        note_ids: Optional[List[str]] = None,
        batch_size: int = 10,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        Auto-categorize notes using semantic analysis.

        Args:
            note_ids: Specific note IDs to categorize (None for all)
            batch_size: Number of notes to process at once
            progress_callback: Optional progress callback

        Returns:
            Dictionary with categorization results
        """
        try:
            # Get notes to categorize
            if note_ids:
                notes = []
                for note_id in note_ids:
                    note = await self.get_note(note_id)
                    if note:
                        notes.append(note)
            else:
                notes = await self.list_notes(limit=1000)  # Use large limit instead of None

            if not notes:
                return {"processed": 0, "categorized": 0, "errors": []}

            categorization_results: Dict[str, Any] = {
                "processed": 0,
                "categorized": 0,
                "errors": [],
                "categories": {},
            }

            # Process notes in batches
            for i in range(0, len(notes), batch_size):
                batch = notes[i : i + batch_size]

                for note in batch:
                    try:
                        # Suggest categories for this note
                        suggestions = await self.suggest_tags_for_content(
                            content=note["content"],
                            title=note["title"],
                            existing_tags=note.get("tags", []),
                            max_suggestions=3,
                        )

                        if suggestions:
                            # Apply high-confidence suggestions automatically
                            high_confidence_tags = [
                                s["tag"] for s in suggestions if s["confidence"] >= 0.8
                            ]

                            if high_confidence_tags:
                                # Update note with new tags
                                current_tags = set(note.get("tags", []))
                                new_tags = list(current_tags.union(high_confidence_tags))

                                await self.update_note(note_id=note["id"], tags=new_tags)

                                categorization_results["categorized"] += 1
                                categorization_results["categories"][note["id"]] = {
                                    "added_tags": high_confidence_tags,
                                    "suggestions": suggestions,
                                }

                        categorization_results["processed"] += 1

                        # Progress callback
                        if progress_callback:
                            progress_callback(categorization_results["processed"], len(notes))

                    except Exception as e:
                        error_msg = f"Error processing note {note['id']}: {str(e)}"
                        logger.error(error_msg)
                        categorization_results["errors"].append(error_msg)

            return categorization_results

        except Exception as e:
            logger.error(f"Error in batch categorization: {str(e)}")
            return {"processed": 0, "categorized": 0, "errors": [str(e)]}

    def _create_tag_suggestion_prompt(
        self,
        content: str,
        existing_tags: List[str],
        current_tags: List[str],
        max_suggestions: int,
    ) -> str:
        """Create optimized prompt for tag suggestion."""
        prompt = f"""あなたは知識管理システムの専門家です。以下のコンテンツに最適なタグを提案してください。

コンテンツ:
{content[:2000]}{"..." if len(content) > 2000 else ""}

現在のタグ: {", ".join(current_tags) if current_tags else "なし"}

システム内の既存タグ例: {", ".join(existing_tags[:20])}

要求:
1. コンテンツの主要テーマを表すタグを{max_suggestions}個以下で提案
2. 既存タグがある場合は再利用を優先
3. 日本語または英語の単語・短いフレーズ
4. 各タグの理由も説明

出力形式:
TAG1: [信頼度0.0-1.0] - 理由
TAG2: [信頼度0.0-1.0] - 理由

例:
プロジェクト管理: [0.9] - コンテンツの主要テーマ
技術仕様: [0.7] - 詳細な技術情報を含む"""

        return prompt

    def _parse_tag_suggestions(self, response_text: str) -> List[Dict[str, Any]]:
        """Parse Gemini response into structured tag suggestions."""
        suggestions = []

        try:
            lines = response_text.strip().split("\n")

            for line in lines:
                line = line.strip()
                if ":" in line and "[" in line and "]" in line:
                    # Extract tag and confidence
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        tag = parts[0].strip()
                        rest = parts[1].strip()

                        # Extract confidence score
                        if "[" in rest and "]" in rest:
                            start = rest.find("[") + 1
                            end = rest.find("]")
                            confidence_str = rest[start:end]
                            reason = rest[end + 1 :].strip(" -")

                            try:
                                confidence = float(confidence_str)
                                suggestions.append(
                                    {"tag": tag, "confidence": confidence, "reason": reason}
                                )
                            except ValueError:
                                continue

        except Exception as e:
            logger.error(f"Error parsing tag suggestions: {str(e)}")

        return suggestions

    def _filter_and_score_suggestions(
        self,
        suggestions: List[Dict[str, Any]],
        existing_tags: List[str],
        all_system_tags: List[str],
    ) -> List[Dict[str, Any]]:
        """Filter and adjust scoring for tag suggestions."""
        filtered = []

        for suggestion in suggestions:
            tag = suggestion["tag"].lower()

            # Skip if already exists as current tag
            if tag in [t.lower() for t in existing_tags]:
                continue

            # Boost confidence if tag exists in system
            if tag in [t.lower() for t in all_system_tags]:
                suggestion["confidence"] = min(1.0, suggestion["confidence"] + 0.1)
                suggestion["existing"] = True
            else:
                suggestion["existing"] = False

            # Only include suggestions with reasonable confidence
            if suggestion["confidence"] >= 0.4:
                filtered.append(suggestion)

        # Sort by confidence
        return sorted(filtered, key=lambda x: x["confidence"], reverse=True)

    def _generate_basic_tag_suggestions(
        self, content: str, title: str, existing_tags: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate basic tag suggestions without AI when API is limited.

        This method provides simple keyword-based tag suggestions as a fallback
        when the AI service is unavailable due to API limits.

        Args:
            content: Text content to analyze
            title: Title of the content
            existing_tags: Already assigned tags

        Returns:
            List of basic tag suggestions with low confidence scores
        """
        suggestions = []

        # Combine title and content for analysis
        text = (title + " " + content).lower()

        # Basic keyword patterns for common tags
        keyword_patterns = {
            "programming": ["code", "function", "class", "method", "algorithm", "debug"],
            "documentation": ["readme", "guide", "tutorial", "instruction", "manual"],
            "meeting": ["meeting", "discussion", "agenda", "notes", "action"],
            "idea": ["idea", "concept", "brainstorm", "thought", "inspiration"],
            "project": ["project", "task", "goal", "milestone", "deadline"],
            "research": ["research", "study", "analysis", "investigation", "findings"],
            "bug": ["bug", "error", "issue", "problem", "fix"],
            "todo": ["todo", "task", "action", "reminder", "checklist"],
        }

        # Check for keyword matches
        for tag, keywords in keyword_patterns.items():
            if tag not in existing_tags and any(keyword in text for keyword in keywords):
                suggestions.append(
                    {
                        "tag": tag,
                        "confidence": 0.6,  # Lower confidence for basic suggestions
                        "reason": "keyword_match",
                    }
                )

        # Add fleeting-note tag if content is short
        if len(content.split()) < 50 and "fleeting-note" not in existing_tags:
            suggestions.append(
                {
                    "tag": "fleeting-note",
                    "confidence": 0.7,
                    "reason": "short_content",
                }
            )

        # Limit to 3 basic suggestions
        return suggestions[:3]

    async def _get_all_existing_tags(self) -> List[str]:
        """Get all existing tags from the database."""
        try:
            async with self.db.get_connection() as conn:
                cursor = await conn.execute("SELECT DISTINCT tag FROM note_tags ORDER BY tag")
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error fetching existing tags: {str(e)}")
            return []

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

                if self.obsidian_github is not None:
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
                else:
                    logger.info(
                        f"ObsidianGitHub integration disabled, skipping save for note {note_id}"
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
        Search notes using database full-text search with fallback support.

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
            # Check fallback manager for knowledge search availability
            if self.fallback_manager and not self.fallback_manager.is_service_available(
                "knowledge_search"
            ):
                logger.info("Knowledge search service unavailable due to API limits, using cache")
                # Try to get cached search results
                cache_key = f"{hash(query + str(tags))}"
                cached_results = await self.fallback_manager.get_cached_data(
                    "search_results", cache_key
                )
                if cached_results:
                    logger.info("Returning cached search results")
                    return cast(List[Dict[str, Any]], cached_results[:limit])
                else:
                    logger.warning("No cached search results available, using basic search")

            # Use DatabaseService search_notes method
            results = await self.db.search_notes(query, limit=limit)

            # Apply tag filtering if specified
            if tags:
                filtered_results = []
                for note in results:
                    note_tags = set(note.get("tags", []))
                    if any(tag in note_tags for tag in tags):
                        filtered_results.append(note)
                final_results = filtered_results
            else:
                final_results = results

            # Cache the results for fallback
            if self.fallback_manager:
                cache_key = f"{hash(query + str(tags))}"
                await self.fallback_manager.cache_data("search_results", cache_key, final_results)

            return final_results

        except Exception as e:
            logger.error(f"Failed to search notes: {e}")
            # Try fallback cache on error
            if self.fallback_manager:
                cache_key = f"{hash(query + str(tags))}"
                cached_results = await self.fallback_manager.get_cached_data(
                    "search_results", cache_key
                )
                if cached_results:
                    logger.info("Returning cached search results due to error")
                    return cast(List[Dict[str, Any]], cached_results[:limit])
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

    async def bulk_embed_notes(
        self,
        note_ids: Optional[List[str]] = None,
        batch_size: int = 10,
        max_concurrent: int = 3,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Process large numbers of notes for embedding in batches with memory optimization.

        Args:
            note_ids: Optional list of specific note IDs.
                If None, processes all notes without embeddings
            batch_size: Number of notes to process in each batch
            max_concurrent: Maximum number of concurrent embedding operations
            progress_callback: Optional callback for progress updates

        Returns:
            Dict containing processing results and statistics
        """
        if not self._initialized:
            await self.initialize()

        from ..utils.memory import MemoryOptimizedProcessor
        from ..utils.progress import BatchProgressTracker

        start_time = time.time()

        try:
            # Get notes to process
            if note_ids is None:
                # Find notes without embeddings
                async with self.db.get_connection() as connection:
                    cursor = await connection.execute(
                        """
                        SELECT n.id, n.title, n.content
                        FROM knowledge_notes n
                        LEFT JOIN chromadb_sync cs ON n.id = cs.note_id
                        WHERE cs.note_id IS NULL OR cs.sync_status != 'synced'
                        ORDER BY n.created_at DESC
                    """
                    )
                    notes_data = await cursor.fetchall()
            else:
                # Get specific notes
                placeholders = ",".join("?" * len(note_ids))
                async with self.db.get_connection() as connection:
                    cursor = await connection.execute(
                        f"""
                        SELECT id, title, content
                        FROM knowledge_notes
                        WHERE id IN ({placeholders})
                        ORDER BY created_at DESC
                        """,
                        note_ids,
                    )
                    notes_data = await cursor.fetchall()

            if not notes_data:
                return {
                    "success": True,
                    "message": "No notes to process",
                    "processed": 0,
                    "failed": 0,
                    "elapsed_time": 0.0,
                }

            total_notes = len(notes_data)
            logger.info(f"Starting bulk embedding for {total_notes} notes")

            # Setup progress tracking
            progress_tracker = BatchProgressTracker(
                total_items=total_notes,
                batch_size=batch_size,
                description="Bulk Note Embedding",
                callback=progress_callback,
            )

            # Memory-optimized processor
            class NoteEmbeddingProcessor(MemoryOptimizedProcessor):
                def __init__(self, knowledge_manager):
                    super().__init__(memory_threshold_mb=400.0)
                    self.km = knowledge_manager

                async def process_note(self, note_data):
                    """Process a single note for embedding."""
                    note_id, title, content = note_data
                    try:
                        # Generate embedding
                        embedding = await self.km.embedding.embed_text(content)

                        # Store in ChromaDB
                        await self.km.chromadb.add_document(
                            id=note_id,
                            text=content,
                            embedding=embedding,
                            metadata={"title": title, "note_id": note_id, "type": "knowledge_note"},
                        )

                        # Update sync status
                        async with self.km.db.get_connection() as connection:
                            await connection.execute(
                                """
                                INSERT OR REPLACE INTO chromadb_sync
                                (note_id, sync_status, last_sync, vector_id)
                                VALUES (?, 'synced', datetime('now'), ?)
                                """,
                                (note_id, note_id),
                            )
                            await connection.commit()

                        return {"success": True, "note_id": note_id}

                    except Exception as e:
                        logger.error(f"Failed to process note {note_id}: {e}")
                        return {"success": False, "note_id": note_id, "error": str(e)}

            processor = NoteEmbeddingProcessor(self)

            # Process notes in batches with concurrency control
            processed = 0
            failed = 0
            semaphore = asyncio.Semaphore(max_concurrent)

            async def process_batch(batch_notes):
                """Process a batch of notes with concurrency control."""

                async def process_single(note_data):
                    async with semaphore:
                        return await processor.process_note(note_data)

                # Process batch concurrently
                tasks = [process_single(note) for note in batch_notes]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                batch_processed = 0
                batch_failed = 0
                for result in results:
                    if isinstance(result, Exception):
                        batch_failed += 1
                        logger.error(f"Batch processing exception: {result}")
                    elif isinstance(result, dict) and result.get("success"):
                        batch_processed += 1
                    else:
                        batch_failed += 1

                return batch_processed, batch_failed

            # Process all batches
            for i in range(0, total_notes, batch_size):
                batch = notes_data[i : i + batch_size]
                progress_tracker.start_batch(i // batch_size)

                batch_processed, batch_failed = await process_batch(batch)
                processed += batch_processed
                failed += batch_failed

                # Update progress
                for _ in range(len(batch)):
                    progress_tracker.update_item()

                progress_tracker.complete_batch()

                # Memory optimization between batches
                from ..utils.memory import optimize_memory

                gc_result = optimize_memory()
                if gc_result and gc_result["memory_freed_mb"] > 5.0:
                    logger.debug(f"Freed {gc_result['memory_freed_mb']:.2f}MB between batches")

                # Small delay between batches to prevent overwhelming
                await asyncio.sleep(0.5)

            elapsed_time = time.time() - start_time

            result = {
                "success": True,
                "total_notes": total_notes,
                "processed": processed,
                "failed": failed,
                "success_rate": processed / total_notes if total_notes > 0 else 0,
                "elapsed_time": elapsed_time,
                "rate_per_second": processed / elapsed_time if elapsed_time > 0 else 0,
                "memory_stats": processor.get_memory_stats(),
            }

            logger.info(
                f"Bulk embedding completed: {processed}/{total_notes} notes processed "
                f"in {elapsed_time:.2f}s ({result['rate_per_second']:.2f}/s)"
            )

            return result

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Bulk embedding failed after {elapsed_time:.2f}s: {e}")
            return {
                "success": False,
                "error": str(e),
                "processed": 0,
                "failed": 0,
                "elapsed_time": elapsed_time,
            }

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False
        logger.info("KnowledgeManager closed")
