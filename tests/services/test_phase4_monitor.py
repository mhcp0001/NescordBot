"""
Test module for Phase4Monitor service.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.api_monitor import APIMonitor
from src.nescordbot.services.chromadb_service import ChromaDBService
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.knowledge_manager import KnowledgeManager
from src.nescordbot.services.phase4_monitor import Phase4Monitor, Phase4MonitorError, PKMMetrics
from src.nescordbot.services.search_engine import SearchEngine
from src.nescordbot.services.token_manager import TokenManager


@pytest.fixture
def mock_config():
    """Create a mock BotConfig for testing."""
    config = Mock(spec=BotConfig)
    config.database_url = "sqlite:///:memory:"
    return config


@pytest.fixture
def mock_services():
    """Create mock services for Phase4Monitor."""
    token_manager = Mock(spec=TokenManager)
    token_manager.health_check = AsyncMock(return_value={"status": "healthy"})
    token_manager.get_monthly_usage = AsyncMock(
        return_value={
            "current_monthly_tokens": 1000,
            "monthly_limit": 10000,
            "monthly_usage_percentage": 10.0,
        }
    )
    token_manager.check_limits = AsyncMock(
        return_value={
            "current_monthly_tokens": 1000,
            "monthly_limit": 10000,
            "monthly_usage_percentage": 10.0,
        }
    )

    api_monitor = Mock(spec=APIMonitor)
    api_monitor.health_check = AsyncMock(return_value={"status": "healthy"})
    api_monitor.get_monitoring_status = AsyncMock(
        return_value={"monitoring_active": True, "fallback_level": "normal"}
    )

    search_engine = Mock(spec=SearchEngine)
    knowledge_manager = Mock(spec=KnowledgeManager)
    chromadb_service = Mock(spec=ChromaDBService)

    database_service = Mock(spec=DatabaseService)
    database_service.get_connection = Mock()
    database_service.get_connection.return_value.__aenter__ = AsyncMock()
    database_service.get_connection.return_value.__aexit__ = AsyncMock()
    db_connection = Mock()
    db_connection.execute = Mock()
    db_connection.execute.return_value.__aenter__ = AsyncMock()
    db_connection.execute.return_value.__aexit__ = AsyncMock()
    cursor = Mock()
    cursor.fetchone = AsyncMock(return_value=(1,))
    db_connection.execute.return_value.__aenter__.return_value = cursor
    database_service.get_connection.return_value.__aenter__.return_value = db_connection

    return {
        "token_manager": token_manager,
        "api_monitor": api_monitor,
        "search_engine": search_engine,
        "knowledge_manager": knowledge_manager,
        "chromadb_service": chromadb_service,
        "database_service": database_service,
    }


@pytest.fixture
def phase4_monitor(mock_config, mock_services):
    """Create a Phase4Monitor instance for testing."""
    return Phase4Monitor(
        config=mock_config,
        token_manager=mock_services["token_manager"],
        api_monitor=mock_services["api_monitor"],
        search_engine=mock_services["search_engine"],
        knowledge_manager=mock_services["knowledge_manager"],
        chromadb_service=mock_services["chromadb_service"],
        database_service=mock_services["database_service"],
    )


class TestPKMMetrics:
    """Test PKMMetrics class functionality."""

    def test_pkm_metrics_initialization(self):
        """Test PKMMetrics initialization."""
        metrics = PKMMetrics()
        assert len(metrics.search_queries) == 0
        assert len(metrics.knowledge_operations) == 0
        assert len(metrics.chromadb_operations) == 0
        assert len(metrics.database_operations) == 0

    def test_add_search_query(self):
        """Test adding search query metrics."""
        metrics = PKMMetrics()

        # Add a search query
        metrics.add_search_query(0.5, 10, {"filter": "test"})

        assert len(metrics.search_queries) == 1
        query = metrics.search_queries[0]
        assert query["query_time"] == 0.5
        assert query["result_count"] == 10
        assert query["filters"] == {"filter": "test"}
        assert isinstance(query["timestamp"], datetime)

    def test_search_queries_limit(self):
        """Test that search queries are limited to 100 entries."""
        metrics = PKMMetrics()

        # Add 150 search queries
        for i in range(150):
            metrics.add_search_query(i * 0.1, i, {"query": i})

        # Should only keep the latest 100
        assert len(metrics.search_queries) == 100
        # The first query should be index 50 (since we kept the last 100 from 150)
        assert metrics.search_queries[0]["filters"]["query"] == 50

    def test_add_knowledge_operation(self):
        """Test adding knowledge operation metrics."""
        metrics = PKMMetrics()

        metrics.add_knowledge_operation("search", 1.5, True)

        assert len(metrics.knowledge_operations) == 1
        operation = metrics.knowledge_operations[0]
        assert operation["operation"] == "search"
        assert operation["processing_time"] == 1.5
        assert operation["success"] is True

    def test_get_summary(self):
        """Test metrics summary generation."""
        metrics = PKMMetrics()

        # Add some test data
        metrics.add_search_query(0.5, 5, {})
        metrics.add_search_query(1.0, 3, {})
        metrics.add_knowledge_operation("search", 0.8, True)
        metrics.add_knowledge_operation("update", 1.2, False)

        summary = metrics.get_summary()

        assert "search_engine" in summary
        assert "knowledge_manager" in summary
        assert "chromadb" in summary
        assert "database" in summary

        search_summary = summary["search_engine"]
        assert search_summary["query_count"] == 2
        assert search_summary["avg_query_time"] == 0.75  # (0.5 + 1.0) / 2
        assert search_summary["avg_result_count"] == 4.0  # (5 + 3) / 2

        knowledge_summary = summary["knowledge_manager"]
        assert knowledge_summary["operation_count"] == 2
        assert knowledge_summary["avg_processing_time"] == 1.0  # (0.8 + 1.2) / 2
        assert knowledge_summary["success_rate"] == 0.5  # 1 success out of 2


class TestPhase4Monitor:
    """Test Phase4Monitor class functionality."""

    def test_initialization(self, phase4_monitor):
        """Test Phase4Monitor initialization."""
        assert phase4_monitor._monitoring_task is None
        assert phase4_monitor._monitoring_interval == 60
        assert phase4_monitor._shutdown is False
        assert isinstance(phase4_monitor.pkm_metrics, PKMMetrics)
        assert len(phase4_monitor._metric_history) == 0

    @pytest.mark.asyncio
    async def test_start_monitoring(self, phase4_monitor):
        """Test starting the monitoring loop."""
        await phase4_monitor.start_monitoring()

        assert phase4_monitor._monitoring_task is not None
        assert not phase4_monitor._shutdown

        # Clean up
        await phase4_monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self, phase4_monitor):
        """Test stopping the monitoring loop."""
        await phase4_monitor.start_monitoring()
        await phase4_monitor.stop_monitoring()

        assert phase4_monitor._shutdown is True

    @pytest.mark.asyncio
    async def test_get_current_snapshot(self, phase4_monitor):
        """Test getting current metrics snapshot."""
        snapshot = await phase4_monitor.get_current_snapshot()

        assert "timestamp" in snapshot
        assert "token_usage" in snapshot
        assert "memory_usage" in snapshot
        assert "search_metrics" in snapshot
        assert "system_health" in snapshot
        assert "pkm_performance" in snapshot

    @pytest.mark.asyncio
    async def test_get_metrics_history(self, phase4_monitor):
        """Test getting metrics history."""
        # Initially no history
        history = await phase4_monitor.get_metrics_history(hours=1)
        assert len(history) == 0

        # Collect a snapshot to create history
        await phase4_monitor._collect_metrics_snapshot()

        history = await phase4_monitor.get_metrics_history(hours=1)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_get_dashboard_data(self, phase4_monitor):
        """Test getting dashboard data."""
        dashboard_data = await phase4_monitor.get_dashboard_data()

        assert "current" in dashboard_data
        assert "history_1hour" in dashboard_data
        assert "api_status" in dashboard_data
        assert "monitoring_active" in dashboard_data
        assert "last_update" in dashboard_data

    def test_record_search_query(self, phase4_monitor):
        """Test recording search query metrics."""
        initial_count = len(phase4_monitor.pkm_metrics.search_queries)

        phase4_monitor.record_search_query(0.5, 10, {"test": True})

        assert len(phase4_monitor.pkm_metrics.search_queries) == initial_count + 1

    def test_record_knowledge_operation(self, phase4_monitor):
        """Test recording knowledge operation metrics."""
        initial_count = len(phase4_monitor.pkm_metrics.knowledge_operations)

        phase4_monitor.record_knowledge_operation("search", 1.0, True)

        assert len(phase4_monitor.pkm_metrics.knowledge_operations) == initial_count + 1

    def test_record_chromadb_operation(self, phase4_monitor):
        """Test recording ChromaDB operation metrics."""
        initial_count = len(phase4_monitor.pkm_metrics.chromadb_operations)

        phase4_monitor.record_chromadb_operation("query", 0.8, 5)

        assert len(phase4_monitor.pkm_metrics.chromadb_operations) == initial_count + 1

    def test_record_database_operation(self, phase4_monitor):
        """Test recording database operation metrics."""
        initial_count = len(phase4_monitor.pkm_metrics.database_operations)

        phase4_monitor.record_database_operation("INSERT", 0.3, 1)

        assert len(phase4_monitor.pkm_metrics.database_operations) == initial_count + 1

    @pytest.mark.asyncio
    async def test_health_check(self, phase4_monitor):
        """Test Phase4Monitor health check."""
        health_status = await phase4_monitor.health_check()

        assert "status" in health_status
        assert "monitoring_active" in health_status
        assert "metric_history_size" in health_status
        assert "pkm_metrics" in health_status
        assert "timestamp" in health_status

        assert health_status["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_collect_token_metrics(self, phase4_monitor):
        """Test token metrics collection."""
        token_metrics = await phase4_monitor._collect_token_metrics()

        assert "monthly_usage" in token_metrics
        assert "current_limits" in token_metrics
        assert "timestamp" in token_metrics

    @pytest.mark.asyncio
    async def test_collect_memory_metrics(self, phase4_monitor):
        """Test memory metrics collection."""
        with patch("src.nescordbot.services.phase4_monitor.get_memory_monitor") as mock_get_memory:
            mock_monitor = Mock()
            mock_monitor.get_memory_usage.return_value = {"current_mb": 100.0, "peak_mb": 120.0}
            mock_monitor.should_trigger_gc.return_value = False
            mock_get_memory.return_value = mock_monitor

            # Recreate Phase4Monitor to use the mocked memory monitor
            phase4_monitor.memory_monitor = mock_monitor

            memory_metrics = await phase4_monitor._collect_memory_metrics()

            assert "current_usage" in memory_metrics
            assert "should_trigger_gc" in memory_metrics
            assert "timestamp" in memory_metrics

    @pytest.mark.asyncio
    async def test_collect_system_health(self, phase4_monitor):
        """Test system health metrics collection."""
        system_health = await phase4_monitor._collect_system_health()

        assert "token_manager" in system_health
        assert "api_monitor" in system_health
        assert "database" in system_health
        assert "timestamp" in system_health

    @pytest.mark.asyncio
    async def test_check_database_health(self, phase4_monitor):
        """Test database health check."""
        db_health = await phase4_monitor._check_database_health()

        assert "status" in db_health
        assert "connection_test" in db_health
        assert "query_time" in db_health
        assert "timestamp" in db_health

        assert db_health["status"] == "healthy"
        assert db_health["connection_test"] is True

    @pytest.mark.asyncio
    async def test_collect_metrics_snapshot(self, phase4_monitor):
        """Test collecting a complete metrics snapshot."""
        initial_history_size = len(phase4_monitor._metric_history)

        await phase4_monitor._collect_metrics_snapshot()

        assert len(phase4_monitor._metric_history) == initial_history_size + 1

    @pytest.mark.asyncio
    async def test_metric_history_size_limit(self, phase4_monitor):
        """Test that metric history respects size limit."""
        phase4_monitor._max_history_size = 5  # Set a small limit for testing

        # Add more snapshots than the limit
        for _ in range(10):
            await phase4_monitor._collect_metrics_snapshot()

        # Should only keep the latest 5
        assert len(phase4_monitor._metric_history) == 5

    @pytest.mark.asyncio
    async def test_error_handling_in_dashboard_data(self, phase4_monitor):
        """Test error handling in dashboard data collection."""
        # Mock an error in snapshot collection
        with patch.object(
            phase4_monitor, "get_current_snapshot", side_effect=Exception("Test error")
        ):
            with pytest.raises(Phase4MonitorError):
                await phase4_monitor.get_dashboard_data()

    @pytest.mark.asyncio
    async def test_close(self, phase4_monitor):
        """Test closing Phase4Monitor."""
        await phase4_monitor.start_monitoring()
        await phase4_monitor.close()

        assert phase4_monitor._shutdown is True


class TestPhase4MonitorIntegration:
    """Integration tests for Phase4Monitor."""

    @pytest.mark.asyncio
    async def test_monitoring_loop_integration(self, phase4_monitor):
        """Test the complete monitoring loop functionality."""
        # Start monitoring
        await phase4_monitor.start_monitoring()

        # Wait a short time to allow some metrics collection
        await asyncio.sleep(0.1)

        # Add some PKM metrics
        phase4_monitor.record_search_query(0.5, 10, {"test": True})
        phase4_monitor.record_knowledge_operation("test_op", 1.0, True)

        # Get dashboard data
        dashboard_data = await phase4_monitor.get_dashboard_data()

        assert dashboard_data["monitoring_active"] is True
        assert "current" in dashboard_data

        # Stop monitoring
        await phase4_monitor.stop_monitoring()

        dashboard_data_after_stop = await phase4_monitor.get_dashboard_data()
        assert dashboard_data_after_stop["monitoring_active"] is False

    @pytest.mark.asyncio
    async def test_concurrent_metric_recording(self, phase4_monitor):
        """Test concurrent metric recording operations."""

        async def record_metrics():
            for i in range(10):
                phase4_monitor.record_search_query(i * 0.1, i, {"batch": i})
                phase4_monitor.record_knowledge_operation(f"op_{i}", i * 0.2, i % 2 == 0)
                await asyncio.sleep(0.01)

        # Run multiple concurrent metric recording tasks
        await asyncio.gather(*[record_metrics() for _ in range(3)])

        # Verify all metrics were recorded
        assert len(phase4_monitor.pkm_metrics.search_queries) == 30
        assert len(phase4_monitor.pkm_metrics.knowledge_operations) == 30

        # Verify summary works correctly
        summary = phase4_monitor.pkm_metrics.get_summary()
        assert summary["search_engine"]["query_count"] == 30
        assert summary["knowledge_manager"]["operation_count"] == 30
