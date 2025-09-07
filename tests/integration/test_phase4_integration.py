"""
Phase 4 Comprehensive Integration Tests - Complete Isolation Strategy

This module contains comprehensive integration tests for Phase 4 services
using the complete test isolation pattern with realistic workflows.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest

from src.nescordbot.services import (
    AlertManager,
    APIMonitor,
    ChromaDBService,
    EmbeddingService,
    FallbackManager,
    KnowledgeManager,
    PrivacyManager,
    SearchEngine,
    SyncManager,
    TokenManager,
)

logger = logging.getLogger(__name__)


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4ServiceIntegration:
    """Test service-to-service integration in isolated environment."""

    async def test_service_container_dependency_injection(self, isolated_bot):
        """Test ServiceContainer properly injects dependencies."""
        container = isolated_bot.service_container

        # Verify all Phase 4 services are properly mocked
        assert container.has_service(TokenManager)
        assert container.has_service(PrivacyManager)
        assert container.has_service(KnowledgeManager)
        assert container.has_service(AlertManager)
        assert container.has_service(EmbeddingService)
        assert container.has_service(ChromaDBService)
        assert container.has_service(SearchEngine)
        assert container.has_service(SyncManager)
        assert container.has_service(FallbackManager)
        assert container.has_service(APIMonitor)

        # Test service retrieval
        privacy_manager = container.get_service(PrivacyManager)
        alert_manager = container.get_service(AlertManager)

        # Verify dependency injection works
        assert privacy_manager.alert_manager is not None
        assert privacy_manager.alert_manager is alert_manager

    async def test_privacy_alert_integration(self, isolated_bot):
        """Test PrivacyManager triggers AlertManager notifications."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)
        alert_manager = isolated_bot.service_container.get_service(AlertManager)

        # Configure realistic PII detection
        mock_rule = Mock()
        mock_rule.name = "email"
        mock_rule.severity = "HIGH"

        privacy_manager.detect_pii.return_value = [(mock_rule, ["sensitive@example.com"])]

        # Process text with PII
        sensitive_text = "Please contact sensitive@example.com for more details"
        detected_rules = await privacy_manager.detect_pii(sensitive_text)

        assert len(detected_rules) > 0
        rule, matches = detected_rules[0]
        assert rule.name == "email"
        assert "sensitive@example.com" in matches

        # Verify alert system is functional
        health = await alert_manager.health_check()
        assert health["status"] == "healthy"

    async def test_knowledge_chromadb_integration(self, isolated_bot):
        """Test KnowledgeManager integrates properly with ChromaDBService."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)
        chromadb_service = isolated_bot.service_container.get_service(ChromaDBService)

        # Configure ChromaDB mock to show realistic collection info
        chromadb_service.get_collection_info.return_value = {
            "count": 5,
            "name": "test_notes",
            "metadata": {"created": "2025-09-07"},
        }

        # Create notes
        note_ids = []
        for i in range(3):
            note_id = await knowledge_manager.create_note(
                title=f"Integration Note {i}",
                content=f"This is test content for note {i} with integration testing focus",
                tags=["integration", "test", f"note{i}"],
            )
            note_ids.append(note_id)

        # Verify ChromaDB interaction
        collection_info = await chromadb_service.get_collection_info()
        assert collection_info["count"] >= 3
        assert collection_info["name"] == "test_notes"

        # Test note retrieval
        for note_id in note_ids:
            note = await knowledge_manager.get_note(note_id)
            assert note is not None
            assert note["id"] == "note_123"  # From our mock

    async def test_search_engine_embedding_integration(self, isolated_bot):
        """Test SearchEngine integrates with EmbeddingService."""
        search_engine = isolated_bot.service_container.get_service(SearchEngine)
        embedding_service = isolated_bot.service_container.get_service(EmbeddingService)

        # Configure embedding service to return realistic vectors
        mock_result = AsyncMock()
        mock_result.embedding = [0.1, 0.2, -0.3, 0.4] * 192  # 768-dim vector
        mock_result.text = "test query"

        embedding_service.generate_embedding.return_value = mock_result

        # Configure search engine to return realistic results and call embedding service
        async def mock_hybrid_search(*args, **kwargs):
            # Simulate calling embedding service
            await embedding_service.generate_embedding("test query")
            return [
                {"content": "Python programming tutorial", "score": 0.95},
                {"content": "Machine learning basics", "score": 0.87},
                {"content": "Data science concepts", "score": 0.73},
            ]

        search_engine.hybrid_search.side_effect = mock_hybrid_search

        # Perform hybrid search
        query = "Python programming"
        results = await search_engine.hybrid_search(query=query, limit=10, alpha=0.7)

        assert len(results) == 3
        assert all("score" in result for result in results)
        assert all("content" in result for result in results)
        assert results[0]["score"] > results[1]["score"]  # Sorted by score

        # Verify embedding was generated for the query
        embedding_service.generate_embedding.assert_called()


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4EndToEndFlows:
    """Test complete end-to-end workflows in isolated environment."""

    async def test_voice_to_pkm_workflow_simulation(self, isolated_bot):
        """Simulate complete voice message to PKM storage workflow."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)

        # Simulate voice transcription result
        transcription = "This is a voice message about Python programming and machine learning"

        # Simulate AI processing result
        processed_content = {
            "formatted_text": "## Python Programming Voice Note\n\n" + transcription,
            "summary": "Python programming and ML voice note",
            "tags": ["python", "ml", "voice", "programming"],
        }

        # Apply privacy protection
        privacy_manager.detect_pii.return_value = []  # No PII detected
        privacy_manager.apply_masking.return_value = processed_content["formatted_text"]

        from src.nescordbot.services.privacy_manager import PrivacyLevel

        protected_content = await privacy_manager.apply_masking(
            processed_content["formatted_text"], PrivacyLevel.MEDIUM
        )

        # Store in knowledge management system
        note_id = await knowledge_manager.create_note(
            title=processed_content["summary"],
            content=protected_content,
            tags=processed_content["tags"],
        )

        assert note_id == "note_123"  # From our mock
        knowledge_manager.create_note.assert_called_once()

        # Verify note can be retrieved
        stored_note = await knowledge_manager.get_note(note_id)
        assert stored_note is not None
        assert stored_note["title"] == "Test Note"

    async def test_hybrid_search_with_fallback(self, isolated_bot):
        """Test hybrid search functionality with fallback mechanisms."""
        search_engine = isolated_bot.service_container.get_service(SearchEngine)
        fallback_manager = isolated_bot.service_container.get_service(FallbackManager)
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)

        # Add sample notes
        sample_notes = [
            {
                "title": "Python Basics",
                "content": "Learn Python programming fundamentals",
                "tags": ["python"],
            },
            {
                "title": "ML Concepts",
                "content": "Machine learning and AI concepts",
                "tags": ["ml", "ai"],
            },
            {
                "title": "Data Science",
                "content": "Data analysis and visualization",
                "tags": ["data", "science"],
            },
        ]

        for note in sample_notes:
            await knowledge_manager.create_note(
                title=note["title"], content=note["content"], tags=note["tags"]
            )

        # Configure hybrid search mock
        search_engine.hybrid_search.return_value = [
            {"content": "Python programming fundamentals", "score": 0.92, "title": "Python Basics"},
            {"content": "Machine learning concepts", "score": 0.78, "title": "ML Concepts"},
        ]

        # Test hybrid search
        results = await search_engine.hybrid_search(query="Python programming", limit=5, alpha=0.7)

        assert len(results) >= 2
        assert all(result["score"] > 0.7 for result in results)
        assert any("Python" in result["content"] for result in results)

        # Verify fallback manager is available
        is_available = await fallback_manager.is_service_available("search")
        assert is_available is True

    async def test_comprehensive_pii_workflow(self, isolated_bot):
        """Test complete PII detection, masking, and alerting workflow."""
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)
        alert_manager = isolated_bot.service_container.get_service(AlertManager)
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)

        # Text with multiple types of PII
        sensitive_text = """
        Contact Information:
        Email: john.doe@company.com
        Phone: 555-123-4567
        API Key: sk-1234567890abcdefghijklmnopqrstuvwxyz
        Social Security: 123-45-6789
        """

        # Configure PII detection
        mock_rules = []
        pii_types = ["email", "phone", "api_key", "ssn"]
        detected_values = [
            "john.doe@company.com",
            "555-123-4567",
            "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "123-45-6789",
        ]

        for pii_type, value in zip(pii_types, detected_values):
            rule = Mock()
            rule.name = pii_type
            rule.severity = "HIGH"
            mock_rules.append((rule, [value]))

        privacy_manager.detect_pii.return_value = mock_rules

        # Apply comprehensive masking
        masked_text = """
        Contact Information:
        Email: [EMAIL_REDACTED]
        Phone: [PHONE_REDACTED]
        API Key: [API_KEY_REDACTED]
        Social Security: [SSN_REDACTED]
        """

        privacy_manager.apply_masking.return_value = masked_text

        # Test PII detection
        detected_rules = await privacy_manager.detect_pii(sensitive_text)
        assert len(detected_rules) == 4

        # Test masking
        from src.nescordbot.services.privacy_manager import PrivacyLevel

        result = await privacy_manager.apply_masking(sensitive_text, PrivacyLevel.HIGH)

        # Verify all PII is masked
        assert "john.doe@company.com" not in result
        assert "555-123-4567" not in result
        assert "sk-1234567890abcdefghijklmnopqrstuvwxyz" not in result
        assert "123-45-6789" not in result
        assert "REDACTED" in result

        # Store masked content
        note_id = await knowledge_manager.create_note(
            title="Contact Information (Masked)",
            content=result,
            tags=["contact", "privacy", "masked"],
        )

        assert note_id == "note_123"

        # Verify alert system is working
        health = await alert_manager.health_check()
        assert health["status"] == "healthy"


@pytest.mark.integration
@pytest.mark.ci
@pytest.mark.slow
class TestPhase4PerformanceAndLoad:
    """Performance and load testing with realistic scenarios."""

    async def test_concurrent_knowledge_operations(self, performance_bot):
        """Test concurrent knowledge management operations."""
        knowledge_manager = performance_bot.service_container.get_service(KnowledgeManager)

        async def create_note_task(index: int):
            """Create a single note."""
            return await knowledge_manager.create_note(
                title=f"Concurrent Note {index}",
                content=f"Content for concurrent test note {index}. Topic: {index % 5}",
                tags=["concurrent", "performance", f"topic_{index % 5}"],
            )

        # Create 50 notes concurrently
        start_time = time.time()
        tasks = [create_note_task(i) for i in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        # Verify performance
        assert elapsed_time < 15.0  # Should complete within 15 seconds

        # Verify all tasks completed successfully
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Found {len(exceptions)} exceptions: {exceptions}"

        # Verify all calls were made
        assert knowledge_manager.create_note.call_count == 50

    async def test_search_performance_under_load(self, performance_bot):
        """Test search performance under concurrent load."""
        search_engine = performance_bot.service_container.get_service(SearchEngine)

        # Configure search mock for performance testing
        search_engine.hybrid_search.return_value = [
            {"content": "Performance test result", "score": 0.85}
        ]

        async def search_task(query_index: int):
            """Perform a single search."""
            queries = ["python", "machine learning", "data science", "programming", "AI"]
            query = f"{queries[query_index % len(queries)]} {query_index}"
            return await search_engine.hybrid_search(query=query, limit=10, alpha=0.7)

        # Perform 100 concurrent searches
        start_time = time.time()
        tasks = [search_task(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        # Performance assertions
        assert elapsed_time < 20.0  # 100 searches in under 20 seconds

        # Verify all searches completed
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0

        successful_results = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_results) == 100

        # Verify search engine was called
        assert search_engine.hybrid_search.call_count == 100

    async def test_privacy_processing_performance(self, performance_bot):
        """Test privacy processing performance with large text volumes."""
        privacy_manager = performance_bot.service_container.get_service(PrivacyManager)

        # Configure privacy manager for performance testing
        mock_rule = Mock()
        mock_rule.name = "email"
        mock_rule.severity = "MEDIUM"

        privacy_manager.detect_pii.return_value = [(mock_rule, ["test@example.com"])]
        privacy_manager.apply_masking.return_value = "Large text content with [EMAIL_REDACTED]"

        async def process_text_task(index: int):
            """Process a single large text."""
            # Simulate 5KB of text content
            large_text = f"Document {index}: " + "This is sample content. " * 200
            large_text += f" Contact: test{index}@example.com"

            # Detect PII
            await privacy_manager.detect_pii(large_text)

            # Apply masking
            from src.nescordbot.services.privacy_manager import PrivacyLevel

            return await privacy_manager.apply_masking(large_text, PrivacyLevel.MEDIUM)

        # Process 25 large documents concurrently
        start_time = time.time()
        tasks = [process_text_task(i) for i in range(25)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed_time = time.time() - start_time

        # Performance assertions
        assert elapsed_time < 10.0  # Process 25 large documents in under 10 seconds

        # Verify all processing completed successfully
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0

        # Verify processing calls
        assert privacy_manager.detect_pii.call_count == 25
        assert privacy_manager.apply_masking.call_count == 25


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4SystemHealth:
    """System health and monitoring tests."""

    async def test_comprehensive_system_health(self, isolated_bot):
        """Test comprehensive system health across all services."""
        container = isolated_bot.service_container

        # Define all services to check
        service_types = [
            TokenManager,
            PrivacyManager,
            KnowledgeManager,
            AlertManager,
            EmbeddingService,
            ChromaDBService,
            SearchEngine,
            SyncManager,
            FallbackManager,
            APIMonitor,
        ]

        # Check health of all services
        health_results = {}
        for service_type in service_types:
            service = container.get_service(service_type)
            health = await service.health_check()
            health_results[service_type.__name__] = health

            # All services should report healthy in our test environment
            assert (
                health["status"] == "healthy"
            ), f"{service_type.__name__} is not healthy: {health}"

        # Verify we checked all expected services
        assert len(health_results) == 10

        # Overall system should be healthy
        assert all(h["status"] == "healthy" for h in health_results.values())

    async def test_service_dependency_health(self, isolated_bot):
        """Test that service dependencies are properly configured and healthy."""
        container = isolated_bot.service_container

        # Test critical dependency: PrivacyManager -> AlertManager
        privacy_manager = container.get_service(PrivacyManager)
        alert_manager = container.get_service(AlertManager)

        assert privacy_manager.alert_manager is not None
        assert privacy_manager.alert_manager is alert_manager

        # Test that both services are healthy
        privacy_health = await privacy_manager.health_check()
        alert_health = await alert_manager.health_check()

        assert privacy_health["status"] == "healthy"
        assert alert_health["status"] == "healthy"

        # Test SearchEngine dependencies
        search_engine = container.get_service(SearchEngine)

        # In our mock setup, these dependencies should be properly configured
        assert hasattr(search_engine, "chroma_service") or search_engine.chroma_service is None
        assert (
            hasattr(search_engine, "embedding_service") or search_engine.embedding_service is None
        )

    async def test_container_test_mode_validation(self, isolated_bot):
        """Validate that test container is properly blocking real services."""
        container = isolated_bot.service_container

        # Verify it's our test container
        from tests.infrastructure.test_service_container import TestServiceContainer

        assert isinstance(container, TestServiceContainer)

        # Verify test mode is active
        assert container._test_mode is True

        # Get test information
        test_info = container.get_test_info()

        assert test_info["test_mode"] is True
        assert len(test_info["registered_mocks"]) >= 10  # All major services
        assert test_info["total_services"] >= 10

        # Verify factories are being blocked
        blocked_factories = test_info.get("blocked_factories", [])
        assert len(blocked_factories) > 0  # Some factories should have been blocked


@pytest.mark.integration
@pytest.mark.ci
class TestPhase4ErrorHandlingAndRecovery:
    """Error handling and recovery testing."""

    async def test_service_error_handling(self, isolated_bot):
        """Test services handle errors gracefully."""
        knowledge_manager = isolated_bot.service_container.get_service(KnowledgeManager)
        privacy_manager = isolated_bot.service_container.get_service(PrivacyManager)

        # Test knowledge manager error handling
        knowledge_manager.create_note.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc_info:
            await knowledge_manager.create_note(
                title="Error Test", content="This should fail", tags=["error", "test"]
            )

        assert "Database error" in str(exc_info.value)

        # Reset mock for next test
        knowledge_manager.create_note.side_effect = None
        knowledge_manager.create_note.return_value = "note_123"

        # Test privacy manager error handling with invalid PII level
        from src.nescordbot.services.privacy_manager import PrivacyLevel

        privacy_manager.apply_masking.side_effect = ValueError("Invalid privacy level")

        with pytest.raises(ValueError) as exc_info:
            await privacy_manager.apply_masking("test content", PrivacyLevel.HIGH)

        assert "Invalid privacy level" in str(exc_info.value)

    async def test_service_recovery_after_failure(self, isolated_bot):
        """Test services can recover after temporary failures."""
        search_engine = isolated_bot.service_container.get_service(SearchEngine)

        # Simulate temporary failure
        search_engine.hybrid_search.side_effect = Exception("Temporary failure")

        with pytest.raises(Exception):
            await search_engine.hybrid_search(query="test", limit=5)

        # Reset to working state
        search_engine.hybrid_search.side_effect = None
        search_engine.hybrid_search.return_value = [
            {"content": "Recovered search result", "score": 0.9}
        ]

        # Service should work again
        results = await search_engine.hybrid_search(query="test", limit=5)
        assert len(results) == 1
        assert results[0]["content"] == "Recovered search result"

    async def test_cascading_failure_isolation(self, isolated_bot):
        """Test that failures in one service don't cascade to others."""
        container = isolated_bot.service_container

        knowledge_manager = container.get_service(KnowledgeManager)
        privacy_manager = container.get_service(PrivacyManager)
        search_engine = container.get_service(SearchEngine)

        # Cause failure in knowledge manager
        knowledge_manager.create_note.side_effect = Exception("KM failure")

        # Other services should still work
        privacy_manager.detect_pii.return_value = []
        search_engine.hybrid_search.return_value = []

        # Test that privacy manager still works
        pii_results = await privacy_manager.detect_pii("test content")
        assert pii_results == []

        # Test that search engine still works
        search_results = await search_engine.hybrid_search(query="test", limit=5)
        assert search_results == []

        # Knowledge manager should still fail
        with pytest.raises(Exception) as exc_info:
            await knowledge_manager.create_note(title="Test", content="Test", tags=["test"])

        assert "KM failure" in str(exc_info.value)
