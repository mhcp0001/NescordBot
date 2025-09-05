"""
Phase 4監視システム - PKM機能専用メトリクス収集と監視.

TokenManager、APIMonitor、MemoryMonitorを統合し、
PKM機能の特化メトリクス収集とシステム健全性チェックを実装。
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, NamedTuple, Optional

from ..config import BotConfig
from ..services.api_monitor import APIMonitor
from ..services.chromadb_service import ChromaDBService
from ..services.database import DatabaseService
from ..services.knowledge_manager import KnowledgeManager
from ..services.search_engine import SearchEngine
from ..services.token_manager import TokenManager
from ..utils.memory import get_memory_monitor

logger = logging.getLogger(__name__)


class MetricSnapshot(NamedTuple):
    """メトリクスのスナップショット."""

    timestamp: datetime
    token_usage: Dict[str, Any]
    memory_usage: Dict[str, Any]
    search_metrics: Dict[str, Any]
    system_health: Dict[str, Any]
    pkm_performance: Dict[str, Any]


class PKMMetrics:
    """PKM機能専用メトリクス."""

    def __init__(self):
        self.search_queries: List[Dict[str, Any]] = []
        self.knowledge_operations: List[Dict[str, Any]] = []
        self.chromadb_operations: List[Dict[str, Any]] = []
        self.database_operations: List[Dict[str, Any]] = []

    def add_search_query(self, query_time: float, result_count: int, filters: Dict[str, Any]):
        """検索クエリのメトリクスを記録."""
        self.search_queries.append(
            {
                "timestamp": datetime.now(),
                "query_time": query_time,
                "result_count": result_count,
                "filters": filters,
            }
        )

        # 最新100件のみ保持
        if len(self.search_queries) > 100:
            self.search_queries = self.search_queries[-100:]

    def add_knowledge_operation(self, operation: str, processing_time: float, success: bool):
        """ナレッジマネージャー操作のメトリクスを記録."""
        self.knowledge_operations.append(
            {
                "timestamp": datetime.now(),
                "operation": operation,
                "processing_time": processing_time,
                "success": success,
            }
        )

        if len(self.knowledge_operations) > 100:
            self.knowledge_operations = self.knowledge_operations[-100:]

    def add_chromadb_operation(self, operation: str, operation_time: float, record_count: int):
        """ChromaDB操作のメトリクスを記録."""
        self.chromadb_operations.append(
            {
                "timestamp": datetime.now(),
                "operation": operation,
                "operation_time": operation_time,
                "record_count": record_count,
            }
        )

        if len(self.chromadb_operations) > 100:
            self.chromadb_operations = self.chromadb_operations[-100:]

    def add_database_operation(self, operation: str, execution_time: float, affected_rows: int):
        """データベース操作のメトリクスを記録."""
        self.database_operations.append(
            {
                "timestamp": datetime.now(),
                "operation": operation,
                "execution_time": execution_time,
                "affected_rows": affected_rows,
            }
        )

        if len(self.database_operations) > 100:
            self.database_operations = self.database_operations[-100:]

    def get_summary(self) -> Dict[str, Any]:
        """メトリクスのサマリーを取得."""
        now = datetime.now()
        one_hour_ago = now - timedelta(hours=1)

        # 過去1時間のデータをフィルタ
        recent_searches = [s for s in self.search_queries if s["timestamp"] >= one_hour_ago]
        recent_knowledge = [k for k in self.knowledge_operations if k["timestamp"] >= one_hour_ago]
        recent_chromadb = [c for c in self.chromadb_operations if c["timestamp"] >= one_hour_ago]
        recent_database = [d for d in self.database_operations if d["timestamp"] >= one_hour_ago]

        return {
            "search_engine": {
                "query_count": len(recent_searches),
                "avg_query_time": sum(s["query_time"] for s in recent_searches)
                / max(1, len(recent_searches)),
                "avg_result_count": sum(s["result_count"] for s in recent_searches)
                / max(1, len(recent_searches)),
            },
            "knowledge_manager": {
                "operation_count": len(recent_knowledge),
                "avg_processing_time": sum(k["processing_time"] for k in recent_knowledge)
                / max(1, len(recent_knowledge)),
                "success_rate": sum(1 for k in recent_knowledge if k["success"])
                / max(1, len(recent_knowledge)),
            },
            "chromadb": {
                "operation_count": len(recent_chromadb),
                "avg_operation_time": sum(c["operation_time"] for c in recent_chromadb)
                / max(1, len(recent_chromadb)),
                "avg_record_count": sum(c["record_count"] for c in recent_chromadb)
                / max(1, len(recent_chromadb)),
            },
            "database": {
                "operation_count": len(recent_database),
                "avg_execution_time": sum(d["execution_time"] for d in recent_database)
                / max(1, len(recent_database)),
                "total_affected_rows": sum(d["affected_rows"] for d in recent_database),
            },
        }


class Phase4MonitorError(Exception):
    """Phase4Monitor関連のエラー."""

    pass


class Phase4Monitor:
    """
    Phase 4統合監視システム.

    PKM機能の専用メトリクス収集、システム健全性チェック、
    統合ダッシュボード用データ提供を行う。
    """

    def __init__(
        self,
        config: BotConfig,
        token_manager: TokenManager,
        api_monitor: APIMonitor,
        search_engine: SearchEngine,
        knowledge_manager: KnowledgeManager,
        chromadb_service: ChromaDBService,
        database_service: DatabaseService,
    ):
        """Phase4Monitorを初期化."""
        self.config = config
        self.token_manager = token_manager
        self.api_monitor = api_monitor
        self.search_engine = search_engine
        self.knowledge_manager = knowledge_manager
        self.chromadb_service = chromadb_service
        self.database_service = database_service

        # メモリモニター取得
        self.memory_monitor = get_memory_monitor()

        # PKM専用メトリクス
        self.pkm_metrics = PKMMetrics()

        # 監視設定
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 60  # 1分間隔
        self._shutdown = False

        # メトリクススナップショット履歴（過去24時間分）
        self._metric_history: List[MetricSnapshot] = []
        self._max_history_size = 1440  # 24時間 × 60分

    async def start_monitoring(self) -> None:
        """監視を開始."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Phase4Monitor already running")
            return

        logger.info("Starting Phase4Monitor...")
        self._shutdown = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self) -> None:
        """監視を停止."""
        logger.info("Stopping Phase4Monitor...")
        self._shutdown = True

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Phase4Monitor stopped")

    async def _monitoring_loop(self) -> None:
        """監視メインループ."""
        logger.info("Phase4Monitor loop started")

        while not self._shutdown:
            try:
                await self._collect_metrics_snapshot()
                await asyncio.sleep(self._monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in Phase4Monitor loop: {e}")
                await asyncio.sleep(30)  # エラー時は30秒待機

        logger.info("Phase4Monitor loop stopped")

    async def _collect_metrics_snapshot(self) -> None:
        """メトリクススナップショットを収集."""
        try:
            # 各コンポーネントからメトリクスを収集
            token_usage = await self._collect_token_metrics()
            memory_usage = await self._collect_memory_metrics()
            search_metrics = await self._collect_search_metrics()
            system_health = await self._collect_system_health()
            pkm_performance = await self._collect_pkm_performance()

            # スナップショットを作成
            snapshot = MetricSnapshot(
                timestamp=datetime.now(),
                token_usage=token_usage,
                memory_usage=memory_usage,
                search_metrics=search_metrics,
                system_health=system_health,
                pkm_performance=pkm_performance,
            )

            # 履歴に追加
            self._metric_history.append(snapshot)

            # 履歴サイズ制限
            if len(self._metric_history) > self._max_history_size:
                self._metric_history = self._metric_history[-self._max_history_size :]

            logger.debug(f"Metrics snapshot collected at {snapshot.timestamp}")

        except Exception as e:
            logger.error(f"Failed to collect metrics snapshot: {e}")

    async def _collect_token_metrics(self) -> Dict[str, Any]:
        """トークン使用量メトリクスを収集."""
        try:
            usage_data = await self.token_manager.get_monthly_usage()
            limits_data = await self.token_manager.check_limits("gemini")

            return {
                "monthly_usage": usage_data,
                "current_limits": limits_data,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to collect token metrics: {e}")
            return {"error": str(e)}

    async def _collect_memory_metrics(self) -> Dict[str, Any]:
        """メモリ使用量メトリクスを収集."""
        try:
            memory_usage = self.memory_monitor.get_memory_usage()
            return {
                "current_usage": memory_usage,
                "should_trigger_gc": self.memory_monitor.should_trigger_gc(),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to collect memory metrics: {e}")
            return {"error": str(e)}

    async def _collect_search_metrics(self) -> Dict[str, Any]:
        """検索エンジンメトリクスを収集."""
        try:
            # SearchEngineから統計情報を取得（実装により異なる）
            # ここでは基本的な情報のみ収集
            return {"service_status": "active", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"Failed to collect search metrics: {e}")
            return {"error": str(e)}

    async def _collect_system_health(self) -> Dict[str, Any]:
        """システム健全性メトリクスを収集."""
        try:
            # 各コンポーネントのヘルスチェック
            token_health = await self.token_manager.health_check()
            api_health = await self.api_monitor.health_check()

            # データベース接続チェック
            db_health = await self._check_database_health()

            return {
                "token_manager": token_health,
                "api_monitor": api_health,
                "database": db_health,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to collect system health: {e}")
            return {"error": str(e)}

    async def _collect_pkm_performance(self) -> Dict[str, Any]:
        """PKM機能パフォーマンスメトリクスを収集."""
        try:
            pkm_summary = self.pkm_metrics.get_summary()
            return {"pkm_summary": pkm_summary, "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error(f"Failed to collect PKM performance: {e}")
            return {"error": str(e)}

    async def _check_database_health(self) -> Dict[str, Any]:
        """データベース健全性をチェック."""
        try:
            start_time = time.time()

            # 簡単なクエリでデータベース接続をテスト
            async with self.database_service.get_connection() as db:
                async with db.execute("SELECT 1") as cursor:
                    result = await cursor.fetchone()

            query_time = time.time() - start_time

            return {
                "status": "healthy",
                "connection_test": result is not None,
                "query_time": query_time,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    # Public API methods

    async def get_current_snapshot(self) -> Dict[str, Any]:
        """現在のメトリクススナップショットを取得."""
        await self._collect_metrics_snapshot()
        if self._metric_history:
            latest = self._metric_history[-1]
            return {
                "timestamp": latest.timestamp.isoformat(),
                "token_usage": latest.token_usage,
                "memory_usage": latest.memory_usage,
                "search_metrics": latest.search_metrics,
                "system_health": latest.system_health,
                "pkm_performance": latest.pkm_performance,
            }
        return {}

    async def get_metrics_history(self, hours: int = 1) -> List[Dict[str, Any]]:
        """指定時間のメトリクス履歴を取得."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        filtered_history = [
            {
                "timestamp": snapshot.timestamp.isoformat(),
                "token_usage": snapshot.token_usage,
                "memory_usage": snapshot.memory_usage,
                "search_metrics": snapshot.search_metrics,
                "system_health": snapshot.system_health,
                "pkm_performance": snapshot.pkm_performance,
            }
            for snapshot in self._metric_history
            if snapshot.timestamp >= cutoff_time
        ]
        return filtered_history

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """ダッシュボード用の統合データを取得."""
        try:
            current_snapshot = await self.get_current_snapshot()
            recent_history = await self.get_metrics_history(hours=1)

            # APIフォールバック状態
            api_status = await self.api_monitor.get_monitoring_status()

            return {
                "current": current_snapshot,
                "history_1hour": recent_history,
                "api_status": api_status,
                "monitoring_active": not self._shutdown,
                "last_update": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            raise Phase4MonitorError(f"Dashboard data collection failed: {e}")

    # PKM metrics recording methods (to be called by PKM services)

    def record_search_query(self, query_time: float, result_count: int, filters: Dict[str, Any]):
        """検索クエリメトリクスを記録（SearchEngineから呼び出し）."""
        self.pkm_metrics.add_search_query(query_time, result_count, filters)

    def record_knowledge_operation(self, operation: str, processing_time: float, success: bool):
        """ナレッジ操作メトリクスを記録（KnowledgeManagerから呼び出し）."""
        self.pkm_metrics.add_knowledge_operation(operation, processing_time, success)

    def record_chromadb_operation(self, operation: str, operation_time: float, record_count: int):
        """ChromaDB操作メトリクスを記録（ChromaDBServiceから呼び出し）."""
        self.pkm_metrics.add_chromadb_operation(operation, operation_time, record_count)

    def record_database_operation(self, operation: str, execution_time: float, affected_rows: int):
        """データベース操作メトリクスを記録（DatabaseServiceから呼び出し）."""
        self.pkm_metrics.add_database_operation(operation, execution_time, affected_rows)

    async def health_check(self) -> Dict[str, Any]:
        """Phase4Monitor自体のヘルスチェック."""
        try:
            return {
                "status": "healthy",
                "monitoring_active": not self._shutdown,
                "metric_history_size": len(self._metric_history),
                "pkm_metrics": {
                    "search_queries": len(self.pkm_metrics.search_queries),
                    "knowledge_operations": len(self.pkm_metrics.knowledge_operations),
                    "chromadb_operations": len(self.pkm_metrics.chromadb_operations),
                    "database_operations": len(self.pkm_metrics.database_operations),
                },
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

    async def close(self) -> None:
        """Phase4Monitorをクリーンアップ."""
        logger.info("Closing Phase4Monitor...")
        await self.stop_monitoring()
        logger.info("Phase4Monitor closed")
