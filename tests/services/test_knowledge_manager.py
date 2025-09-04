"""
Tests for KnowledgeManager service.

This module contains comprehensive tests for knowledge management functionality
including CRUD operations, link extraction, tag management, and service integration.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.chromadb_service import ChromaDBService
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.embedding import EmbeddingService
from src.nescordbot.services.knowledge_manager import KnowledgeManager, KnowledgeManagerError
from src.nescordbot.services.obsidian_github import ObsidianGitHubService
from src.nescordbot.services.sync_manager import SyncManager


class TestKnowledgeManager:
    """Test KnowledgeManager functionality."""

    @pytest.fixture
    def temp_config(self):
        """Create temporary config for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(spec=BotConfig)
            config.database_url = f"sqlite:///{temp_dir}/test.db"
            config.github_obsidian_enabled = True
            config.chromadb_enabled = True
            config.chromadb_path = temp_dir
            yield config

    @pytest.fixture
    async def knowledge_manager(self, temp_config):
        """Create KnowledgeManager instance for testing."""
        # Setup database service
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        # Mock other services
        chromadb_service = AsyncMock(spec=ChromaDBService)
        chromadb_service._initialized = True

        embedding_service = AsyncMock(spec=EmbeddingService)
        sync_manager = AsyncMock(spec=SyncManager)
        obsidian_github_service = AsyncMock(spec=ObsidianGitHubService)

        manager = KnowledgeManager(
            config=temp_config,
            database_service=database_service,
            chromadb_service=chromadb_service,
            embedding_service=embedding_service,
            sync_manager=sync_manager,
            obsidian_github_service=obsidian_github_service,
        )

        await manager.initialize()
        yield manager

        await database_service.close()

    @pytest.mark.asyncio
    async def test_initialization(self, temp_config):
        """Test KnowledgeManager initialization."""
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        # Mock services
        chromadb_service = AsyncMock(spec=ChromaDBService)
        embedding_service = AsyncMock(spec=EmbeddingService)
        sync_manager = AsyncMock(spec=SyncManager)
        obsidian_github_service = AsyncMock(spec=ObsidianGitHubService)

        manager = KnowledgeManager(
            config=temp_config,
            database_service=database_service,
            chromadb_service=chromadb_service,
            embedding_service=embedding_service,
            sync_manager=sync_manager,
            obsidian_github_service=obsidian_github_service,
        )

        assert not manager._initialized

        await manager.initialize()
        assert manager._initialized

        await database_service.close()

    @pytest.mark.asyncio
    async def test_create_note_basic(self, knowledge_manager):
        """Test basic note creation."""
        note_id = await knowledge_manager.create_note(
            title="Test Note",
            content="This is a test note with #tag1 and [[linked_note]]",
            tags=["manual"],
            user_id="test_user",
            channel_id="test_channel",
            guild_id="test_guild",
        )

        assert note_id is not None
        assert len(note_id) == 36  # UUID format

        # Verify note was created
        note = await knowledge_manager.get_note(note_id)
        assert note is not None
        assert note["title"] == "Test Note"
        assert note["content"] == "This is a test note with #tag1 and [[linked_note]]"
        assert "tag1" in note["tags"]
        assert "manual" in note["tags"]

    @pytest.mark.asyncio
    async def test_update_note(self, knowledge_manager):
        """Test note updating."""
        # Create initial note
        note_id = await knowledge_manager.create_note(
            title="Original Title",
            content="Original content",
            tags=["original"],
            user_id="test_user",
        )

        # Update note
        success = await knowledge_manager.update_note(
            note_id=note_id,
            title="Updated Title",
            content="Updated content with #updated",
            tags=["updated"],
        )

        assert success is True

        # Verify update
        note = await knowledge_manager.get_note(note_id)
        assert note["title"] == "Updated Title"
        assert note["content"] == "Updated content with #updated"
        assert "updated" in note["tags"]

    @pytest.mark.asyncio
    async def test_delete_note(self, knowledge_manager):
        """Test note deletion."""
        # Create note
        note_id = await knowledge_manager.create_note(
            title="Delete Me", content="This note will be deleted", user_id="test_user"
        )

        # Verify creation
        note = await knowledge_manager.get_note(note_id)
        assert note is not None

        # Delete note
        success = await knowledge_manager.delete_note(note_id)
        assert success is True

        # Verify deletion
        note = await knowledge_manager.get_note(note_id)
        assert note is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_note(self, knowledge_manager):
        """Test deleting non-existent note."""
        success = await knowledge_manager.delete_note("nonexistent-id")
        assert success is False

    def test_extract_links(self, knowledge_manager):
        """Test link extraction from content."""
        content = (
            "This note links to [[First Note]] and [[Second Note]] and mentions [[Another Link]]."
        )
        links = knowledge_manager.extract_links(content)

        assert len(links) == 3
        assert "First Note" in links
        assert "Second Note" in links
        assert "Another Link" in links

    def test_extract_links_empty(self, knowledge_manager):
        """Test link extraction with no links."""
        content = "This note has no links."
        links = knowledge_manager.extract_links(content)
        assert links == []

    def test_extract_tags(self, knowledge_manager):
        """Test tag extraction from content."""
        content = "This note has #tag1 and #tag2 and #AnotherTag."
        tags = knowledge_manager.extract_tags(content)

        assert len(tags) == 3
        assert "tag1" in tags
        assert "tag2" in tags
        assert "anothertag" in tags  # Should be lowercase

    def test_extract_tags_empty(self, knowledge_manager):
        """Test tag extraction with no tags."""
        content = "This note has no tags."
        tags = knowledge_manager.extract_tags(content)
        assert tags == []

    @pytest.mark.asyncio
    async def test_get_notes_by_tag(self, knowledge_manager):
        """Test filtering notes by tag."""
        # Create test notes
        await knowledge_manager.create_note(
            title="Note 1", content="Content with #python", tags=["python"], user_id="test_user"
        )

        await knowledge_manager.create_note(
            title="Note 2",
            content="Content with #javascript",
            tags=["javascript"],
            user_id="test_user",
        )

        await knowledge_manager.create_note(
            title="Note 3",
            content="Content with #python and #javascript",
            tags=["python", "javascript"],
            user_id="test_user",
        )

        # Search by tag
        python_notes = await knowledge_manager.get_notes_by_tag("python")
        assert len(python_notes) == 2

        javascript_notes = await knowledge_manager.get_notes_by_tag("javascript")
        assert len(javascript_notes) == 2

    @pytest.mark.asyncio
    async def test_list_notes_with_filters(self, knowledge_manager):
        """Test listing notes with various filters."""
        # Create test notes
        await knowledge_manager.create_note(
            title="Voice Note",
            content="Voice transcription",
            tags=["voice"],
            source_type="voice",
            user_id="user1",
        )

        await knowledge_manager.create_note(
            title="Text Note",
            content="Text message",
            tags=["text"],
            source_type="text",
            user_id="user2",
        )

        await knowledge_manager.create_note(
            title="Manual Note",
            content="Manual entry",
            tags=["manual"],
            source_type="manual",
            user_id="user1",
        )

        # Test filtering by source_type
        voice_notes = await knowledge_manager.list_notes(source_type="voice")
        assert len(voice_notes) == 1
        assert voice_notes[0]["title"] == "Voice Note"

        # Test filtering by user_id
        user1_notes = await knowledge_manager.list_notes(user_id="user1")
        assert len(user1_notes) == 2

        # Test filtering by tags
        voice_tag_notes = await knowledge_manager.list_notes(tags=["voice"])
        assert len(voice_tag_notes) == 1

    @pytest.mark.asyncio
    async def test_update_links_integration(self, knowledge_manager):
        """Test link management functionality."""
        # Create target note
        target_id = await knowledge_manager.create_note(
            title="Target Note", content="This is the target", user_id="test_user"
        )

        # Create source note with link
        source_id = await knowledge_manager.create_note(
            title="Source Note",
            content="This links to [[Target Note]] for reference",
            user_id="test_user",
        )

        # Verify link was created
        links = await knowledge_manager.get_linked_notes(source_id)
        assert len(links["outgoing"]) == 1
        assert links["outgoing"][0]["title"] == "Target Note"

        # Verify incoming link
        target_links = await knowledge_manager.get_linked_notes(target_id)
        assert len(target_links["incoming"]) == 1
        assert target_links["incoming"][0]["title"] == "Source Note"

    @pytest.mark.asyncio
    async def test_merge_notes(self, knowledge_manager):
        """Test note merging functionality."""
        # Create notes to merge
        note1_id = await knowledge_manager.create_note(
            title="First Note", content="First content", tags=["tag1"], user_id="user1"
        )

        note2_id = await knowledge_manager.create_note(
            title="Second Note", content="Second content", tags=["tag2"], user_id="user1"
        )

        # Merge notes
        merged_id = await knowledge_manager.merge_notes(
            [note1_id, note2_id], new_title="Merged Note"
        )

        # Verify merged note exists
        merged_note = await knowledge_manager.get_note(merged_id)
        assert merged_note is not None
        assert merged_note["title"] == "Merged Note"
        assert "First content" in merged_note["content"]
        assert "Second content" in merged_note["content"]
        assert "tag1" in merged_note["tags"]
        assert "tag2" in merged_note["tags"]

        # Verify original notes are deleted
        note1 = await knowledge_manager.get_note(note1_id)
        note2 = await knowledge_manager.get_note(note2_id)
        assert note1 is None
        assert note2 is None

    @pytest.mark.asyncio
    async def test_merge_notes_insufficient_notes(self, knowledge_manager):
        """Test merge with insufficient notes."""
        note_id = await knowledge_manager.create_note(
            title="Only Note", content="Single note", user_id="test_user"
        )

        with pytest.raises(KnowledgeManagerError, match="At least 2 notes required"):
            await knowledge_manager.merge_notes([note_id])

    @pytest.mark.asyncio
    async def test_search_notes(self, knowledge_manager):
        """Test note searching."""
        # Create searchable notes
        await knowledge_manager.create_note(
            title="Python Tutorial",
            content="Learn Python programming",
            tags=["python", "tutorial"],
            user_id="test_user",
        )

        await knowledge_manager.create_note(
            title="JavaScript Guide",
            content="JavaScript fundamentals",
            tags=["javascript", "guide"],
            user_id="test_user",
        )

        # Search by content
        results = await knowledge_manager.search_notes("Python")
        assert len(results) >= 1
        assert any(note["title"] == "Python Tutorial" for note in results)

        # Search with tag filter - should filter to only python-tagged notes
        await knowledge_manager.search_notes("programming", tags=["python"])

    @pytest.mark.asyncio
    async def test_service_integration(self, knowledge_manager):
        """Test integration with external services."""
        # Create note
        note_id = await knowledge_manager.create_note(
            title="Integration Test",
            content="Testing service integration",
            tags=["test"],
            user_id="test_user",
        )

        # Verify sync_manager was called
        knowledge_manager.sync_manager.sync_note_to_chromadb.assert_called_with(note_id)

        # Verify obsidian_github was called (if enabled)
        if knowledge_manager.config.github_obsidian_enabled:
            knowledge_manager.obsidian_github.save_to_obsidian.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, knowledge_manager):
        """Test health check with healthy state."""
        health = await knowledge_manager.health_check()

        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert "note_count" in health
        assert "link_count" in health
        assert "services" in health

    @pytest.mark.asyncio
    async def test_health_check_uninitialized(self, temp_config):
        """Test health check when not initialized."""
        database_service = DatabaseService(temp_config.database_url)
        await database_service.initialize()

        chromadb_service = AsyncMock(spec=ChromaDBService)
        embedding_service = AsyncMock(spec=EmbeddingService)
        sync_manager = AsyncMock(spec=SyncManager)
        obsidian_github_service = AsyncMock(spec=ObsidianGitHubService)

        manager = KnowledgeManager(
            config=temp_config,
            database_service=database_service,
            chromadb_service=chromadb_service,
            embedding_service=embedding_service,
            sync_manager=sync_manager,
            obsidian_github_service=obsidian_github_service,
        )

        health = await manager.health_check()
        assert health["status"] == "unhealthy"
        assert "Not initialized" in health["error"]

        await database_service.close()

    @pytest.mark.asyncio
    async def test_error_handling(self, temp_config):
        """Test error handling in various scenarios."""
        # Test with uninitialized database
        database_service = DatabaseService(temp_config.database_url)

        chromadb_service = AsyncMock(spec=ChromaDBService)
        embedding_service = AsyncMock(spec=EmbeddingService)
        sync_manager = AsyncMock(spec=SyncManager)
        obsidian_github_service = AsyncMock(spec=ObsidianGitHubService)

        manager = KnowledgeManager(
            config=temp_config,
            database_service=database_service,
            chromadb_service=chromadb_service,
            embedding_service=embedding_service,
            sync_manager=sync_manager,
            obsidian_github_service=obsidian_github_service,
        )

        # Should raise error when database not initialized
        with pytest.raises(KnowledgeManagerError, match="DatabaseService not initialized"):
            await manager.initialize()

    @pytest.mark.asyncio
    async def test_close(self, knowledge_manager):
        """Test proper cleanup on close."""
        assert knowledge_manager._initialized is True

        await knowledge_manager.close()
        assert knowledge_manager._initialized is False

    @pytest.mark.asyncio
    async def test_update_note_with_history_tracking(self, knowledge_manager):
        """Test update note with history tracking."""
        # Create initial note
        note_id = await knowledge_manager.create_note(
            title="Original Title", content="Original content", user_id="user123"
        )

        # Update note with history tracking
        success = await knowledge_manager.update_note(
            note_id=note_id,
            title="Updated Title",
            content="Updated content",
            tags=["updated", "test"],
            user_id="user123",
        )

        assert success

        # Get history
        history = await knowledge_manager.get_note_history(note_id)
        assert len(history) == 1

        history_item = history[0]
        assert history_item["user_id"] == "user123"
        assert history_item["edit_type"] == "update"
        assert history_item["title_before"] == "Original Title"
        assert history_item["title_after"] == "Updated Title"
        assert history_item["content_before"] == "Original content"
        assert history_item["content_after"] == "Updated content"

        # Check changes diff
        changes = history_item["changes"]
        assert "title" in changes
        assert changes["title"]["changed"] is True
        assert "content" in changes
        assert changes["content"]["changed"] is True

    @pytest.mark.asyncio
    async def test_update_note_without_user_id_no_history(self, knowledge_manager):
        """Test update note without user_id doesn't save history."""
        # Create initial note
        note_id = await knowledge_manager.create_note(
            title="Test Title", content="Test content", user_id="user123"
        )

        # Update without user_id
        success = await knowledge_manager.update_note(note_id=note_id, title="Updated Title")

        assert success

        # Check no history saved
        history = await knowledge_manager.get_note_history(note_id)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_note_history_empty(self, knowledge_manager):
        """Test getting history for note with no edits."""
        # Create note
        note_id = await knowledge_manager.create_note(
            title="Test Title", content="Test content", user_id="user123"
        )

        # Get history
        history = await knowledge_manager.get_note_history(note_id)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_get_note_history_limit(self, knowledge_manager):
        """Test history limit parameter."""
        # Create note
        note_id = await knowledge_manager.create_note(
            title="Test Title", content="Test content", user_id="user123"
        )

        # Make multiple updates
        for i in range(5):
            await knowledge_manager.update_note(
                note_id=note_id, title=f"Title {i}", user_id="user123"
            )

        # Get limited history
        history = await knowledge_manager.get_note_history(note_id, limit=3)
        assert len(history) == 3

        # Should be ordered by timestamp desc (newest first)
        assert history[0]["title_after"] == "Title 4"
        assert history[1]["title_after"] == "Title 3"
        assert history[2]["title_after"] == "Title 2"

    def test_generate_edit_diff_title_change(self, knowledge_manager):
        """Test diff generation for title changes."""
        diff = knowledge_manager._generate_edit_diff(
            title_before="Old Title",
            content_before="Same content",
            tags_before=["tag1"],
            title_after="New Title",
            content_after="Same content",
            tags_after=["tag1"],
        )

        assert "title" in diff
        assert diff["title"]["changed"] is True
        assert diff["title"]["before"] == "Old Title"
        assert diff["title"]["after"] == "New Title"
        assert "content" not in diff
        assert "tags" not in diff

    def test_generate_edit_diff_content_change(self, knowledge_manager):
        """Test diff generation for content changes."""
        diff = knowledge_manager._generate_edit_diff(
            title_before="Same Title",
            content_before="Line 1\nLine 2",
            tags_before=["tag1"],
            title_after="Same Title",
            content_after="Line 1\nLine 2 Modified\nLine 3",
            tags_after=["tag1"],
        )

        assert "content" in diff
        assert diff["content"]["changed"] is True
        assert diff["content"]["before_lines"] == 2
        assert diff["content"]["after_lines"] == 3
        assert len(diff["content"]["diff"]) > 0

    def test_generate_edit_diff_tags_change(self, knowledge_manager):
        """Test diff generation for tags changes."""
        diff = knowledge_manager._generate_edit_diff(
            title_before="Same Title",
            content_before="Same content",
            tags_before=["tag1", "tag2"],
            title_after="Same Title",
            content_after="Same content",
            tags_after=["tag1", "tag3", "tag4"],
        )

        assert "tags" in diff
        assert diff["tags"]["changed"] is True
        assert "tag2" in diff["tags"]["removed"]
        assert "tag3" in diff["tags"]["added"]
        assert "tag4" in diff["tags"]["added"]

    @pytest.mark.asyncio
    async def test_get_note_history_nonexistent_note(self, knowledge_manager):
        """Test getting history for non-existent note."""
        history = await knowledge_manager.get_note_history("nonexistent-id")
        assert len(history) == 0


class TestKnowledgeManagerIntegration:
    """Integration tests for KnowledgeManager with real components."""

    @pytest.fixture
    async def integrated_manager(self):
        """Create fully integrated KnowledgeManager for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = MagicMock(spec=BotConfig)
            config.database_url = f"sqlite:///{temp_dir}/integration.db"
            config.github_obsidian_enabled = True
            config.chromadb_enabled = True
            config.chromadb_path = temp_dir

            database_service = DatabaseService(config.database_url)
            await database_service.initialize()

            # Mock services for integration test
            chromadb_service = AsyncMock(spec=ChromaDBService)
            chromadb_service._initialized = True

            embedding_service = AsyncMock(spec=EmbeddingService)
            sync_manager = AsyncMock(spec=SyncManager)
            obsidian_github_service = AsyncMock(spec=ObsidianGitHubService)

            manager = KnowledgeManager(
                config=config,
                database_service=database_service,
                chromadb_service=chromadb_service,
                embedding_service=embedding_service,
                sync_manager=sync_manager,
                obsidian_github_service=obsidian_github_service,
            )

            await manager.initialize()
            yield manager

            await database_service.close()

    @pytest.mark.asyncio
    async def test_real_world_scenario(self, integrated_manager):
        """Test realistic usage scenario with multiple operations."""
        manager = integrated_manager

        # Create initial notes
        note1_id = await manager.create_note(
            title="Python Basics",
            content="Python is a programming language. See [[Advanced Python]] for more.",
            tags=["python", "programming"],
            source_type="manual",
            user_id="user_123",
        )

        await manager.create_note(
            title="Advanced Python",
            content="Advanced Python concepts with #decorators and #async programming.",
            tags=["python", "advanced"],
            source_type="text",
            user_id="user_123",
        )

        # Update first note to create bidirectional link
        await manager.update_note(
            note1_id,
            content=(
                "Python is a programming language. "
                "See [[Advanced Python]] for more. "
                "Check out [[Python Tips]]."
            ),
        )

        # List notes by tag
        python_notes = await manager.get_notes_by_tag("python")
        assert len(python_notes) == 2

        # Test search functionality
        search_results = await manager.search_notes("programming")
        assert len(search_results) >= 1

        # Test link relationships
        links = await manager.get_linked_notes(note1_id)
        assert len(links["outgoing"]) >= 1

        # Verify service integrations were called
        assert manager.sync_manager.sync_note_to_chromadb.call_count >= 2
        assert manager.obsidian_github.save_to_obsidian.call_count >= 2

    @pytest.mark.asyncio
    async def test_link_management_complex(self, integrated_manager):
        """Test complex link management scenarios."""
        manager = integrated_manager

        # Create notes first (without links being created due to missing targets)
        note_a = await manager.create_note(
            title="Note A",
            content="Links to [[Note B]] and [[Note C]]",
            tags=["network"],
            user_id="test_user",
        )

        note_b = await manager.create_note(
            title="Note B",
            content="Links back to [[Note A]]",
            tags=["network"],
            user_id="test_user",
        )

        note_c = await manager.create_note(
            title="Note C",
            content="Independent note that links to [[Note B]]",
            tags=["network"],
            user_id="test_user",
        )

        # Update links for all notes to establish connections
        # (now all target notes exist)
        await manager.update_note(note_a, content="Links to [[Note B]] and [[Note C]]")
        await manager.update_note(note_b, content="Links back to [[Note A]]")
        await manager.update_note(note_c, content="Independent note that links to [[Note B]]")

        # Verify link network
        a_links = await manager.get_linked_notes(note_a)
        b_links = await manager.get_linked_notes(note_b)
        await manager.get_linked_notes(note_c)

        # Note A should have outgoing links to B and C
        assert len(a_links["outgoing"]) == 2
        # Note A should have incoming link from B
        assert len(a_links["incoming"]) == 1

        # Note B should have outgoing link to A and incoming from A and C
        assert len(b_links["outgoing"]) == 1
        assert len(b_links["incoming"]) == 2

    @pytest.mark.asyncio
    async def test_merge_functionality_comprehensive(self, integrated_manager):
        """Test comprehensive note merging with tags and links."""
        manager = integrated_manager

        # Create notes with various content
        note1_id = await manager.create_note(
            title="Research Topic 1",
            content="Research on #AI and #MachineLearning with reference to [[Foundation Paper]]",
            tags=["research", "ai"],
            user_id="researcher",
        )

        note2_id = await manager.create_note(
            title="Research Topic 2",
            content="Additional findings on #AI applications in #NLP",
            tags=["research", "nlp"],
            user_id="researcher",
        )

        note3_id = await manager.create_note(
            title="Meeting Notes",
            content="Discussion about research direction with #team",
            tags=["meeting"],
            user_id="researcher",
        )

        # Merge all research-related notes
        merged_id = await manager.merge_notes(
            [note1_id, note2_id, note3_id], new_title="Comprehensive Research"
        )

        # Verify merged note
        merged_note = await manager.get_note(merged_id)
        assert merged_note is not None
        assert merged_note["title"] == "Comprehensive Research"
        assert merged_note["source_type"] == "merged"

        # Check that all content is included
        content = merged_note["content"]
        assert "Research Topic 1" in content
        assert "Research Topic 2" in content
        assert "Meeting Notes" in content

        # Check that all tags are preserved
        tags = merged_note["tags"]
        expected_tags = {"research", "ai", "nlp", "meeting", "machinelearning", "team"}
        assert expected_tags.issubset(set(tags))

        # Verify original notes are gone
        for note_id in [note1_id, note2_id, note3_id]:
            assert await manager.get_note(note_id) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
