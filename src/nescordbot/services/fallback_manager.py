"""
FallbackManager - API制限時のフォールバック機能管理.

Gemini APIトークン制限時の段階的機能制限システムと
ローカルキャッシュ活用による継続サービス提供を管理する。
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

from ..config import BotConfig

# Logger setup
logger = logging.getLogger(__name__)


class FallbackLevel(Enum):
    """フォールバックレベル定義."""

    NORMAL = "normal"  # 通常動作（90%未満）
    LIMITED = "limited"  # 制限モード（90-95%）
    CRITICAL = "critical"  # クリティカルモード（95-100%）
    EMERGENCY = "emergency"  # 緊急モード（100%以上）


class ServicePriority(Enum):
    """サービス優先度定義."""

    ESSENTIAL = 1  # 必須サービス（制限時も維持）
    IMPORTANT = 2  # 重要サービス（CRITICAL時まで維持）
    OPTIONAL = 3  # オプション（LIMITED時に停止）


class FallbackManagerError(Exception):
    """FallbackManager related errors."""

    pass


class FallbackManager:
    """
    API制限時フォールバック機能管理クラス.

    TokenManagerと連携してAPI使用量を監視し、
    段階的な機能制限とキャッシュ活用を管理する。
    """

    def __init__(self, config: BotConfig):
        """Initialize FallbackManager."""
        self.config = config
        self._initialized = False
        self._current_level = FallbackLevel.NORMAL
        self._service_states: Dict[str, bool] = {}
        self._cache_data: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}
        self._alert_sent = False
        self._manual_override = False

        # サービス優先度マッピング
        self._service_priorities = {
            "embedding": ServicePriority.ESSENTIAL,
            "knowledge_search": ServicePriority.ESSENTIAL,
            "tag_suggestion": ServicePriority.IMPORTANT,
            "auto_categorization": ServicePriority.IMPORTANT,
            "content_expansion": ServicePriority.OPTIONAL,
            "batch_processing": ServicePriority.OPTIONAL,
        }

        # キャッシュ設定
        self._cache_ttl = {
            "embeddings": timedelta(hours=24),  # 24時間
            "search_results": timedelta(hours=6),  # 6時間
            "tag_suggestions": timedelta(hours=12),  # 12時間
        }

    async def initialize(self) -> None:
        """Initialize the FallbackManager."""
        if self._initialized:
            return

        logger.info("Initializing FallbackManager...")

        # 初期状態設定
        self._current_level = FallbackLevel.NORMAL
        self._service_states = {service: True for service in self._service_priorities.keys()}
        self._cache_data.clear()
        self._cache_timestamps.clear()
        self._alert_sent = False
        self._manual_override = False

        self._initialized = True
        logger.info("FallbackManager initialized successfully")

    async def check_and_update_fallback_level(self, usage_data: Dict[str, Any]) -> FallbackLevel:
        """
        使用量データに基づいてフォールバックレベルを更新.

        Args:
            usage_data: TokenManagerからの使用量データ

        Returns:
            更新後のフォールバックレベル
        """
        if not self._initialized:
            await self.initialize()

        # 手動オーバーライド中は変更しない
        if self._manual_override:
            logger.info("Manual override active, keeping current fallback level")
            return self._current_level

        usage_percentage = usage_data.get("monthly_usage_percentage", 0)
        previous_level = self._current_level

        # フォールバックレベル判定
        if usage_percentage >= 100:
            new_level = FallbackLevel.EMERGENCY
        elif usage_percentage >= 95:
            new_level = FallbackLevel.CRITICAL
        elif usage_percentage >= 90:
            new_level = FallbackLevel.LIMITED
        else:
            new_level = FallbackLevel.NORMAL

        # レベル変更時の処理
        if new_level != previous_level:
            logger.warning(f"Fallback level changed: {previous_level.value} -> {new_level.value}")
            self._current_level = new_level
            await self._update_service_states(new_level)

            # アラート送信
            if new_level in [FallbackLevel.CRITICAL, FallbackLevel.EMERGENCY]:
                await self._send_alert(new_level, usage_data)

        return new_level

    async def _update_service_states(self, level: FallbackLevel) -> None:
        """フォールバックレベルに応じてサービス状態を更新."""
        logger.info(f"Updating service states for level: {level.value}")

        for service, priority in self._service_priorities.items():
            should_be_active = self._should_service_be_active(priority, level)
            self._service_states[service] = should_be_active

            status = "active" if should_be_active else "disabled"
            logger.info(f"Service '{service}' (priority: {priority.name}): {status}")

    def _should_service_be_active(self, priority: ServicePriority, level: FallbackLevel) -> bool:
        """サービス優先度とフォールバックレベルから有効性を判定."""
        if level == FallbackLevel.NORMAL:
            return True
        elif level == FallbackLevel.LIMITED:
            return priority in [ServicePriority.ESSENTIAL, ServicePriority.IMPORTANT]
        elif level == FallbackLevel.CRITICAL:
            return priority == ServicePriority.ESSENTIAL
        else:  # EMERGENCY
            return False

    async def _send_alert(self, level: FallbackLevel, usage_data: Dict[str, Any]) -> None:
        """アラート送信（実装は今後Discord通知と連携）."""
        if self._alert_sent:
            return

        logger.critical(f"API LIMIT ALERT: Fallback level {level.value}")
        logger.critical(f"Usage: {usage_data.get('monthly_usage_percentage', 0):.1f}%")

        # TODO: Discord管理者チャンネルに通知送信
        # await self._send_discord_alert(level, usage_data)

        self._alert_sent = True

    def is_service_available(self, service_name: str) -> bool:
        """指定されたサービスが利用可能かチェック."""
        return self._service_states.get(service_name, False)

    def get_current_level(self) -> FallbackLevel:
        """現在のフォールバックレベルを取得."""
        return self._current_level

    def get_service_states(self) -> Dict[str, bool]:
        """全サービスの状態を取得."""
        return self._service_states.copy()

    async def cache_data(self, cache_type: str, key: str, data: Any) -> None:
        """データをキャッシュに保存."""
        cache_key = f"{cache_type}:{key}"
        self._cache_data[cache_key] = data
        self._cache_timestamps[cache_key] = datetime.now()

        logger.debug(f"Cached data: {cache_key}")

    async def get_cached_data(self, cache_type: str, key: str) -> Optional[Any]:
        """キャッシュからデータを取得."""
        cache_key = f"{cache_type}:{key}"

        # キャッシュ存在チェック
        if cache_key not in self._cache_data:
            return None

        # TTL チェック
        if cache_type in self._cache_ttl:
            cached_time = self._cache_timestamps.get(cache_key)
            if cached_time and datetime.now() - cached_time > self._cache_ttl[cache_type]:
                # 期限切れのため削除
                del self._cache_data[cache_key]
                del self._cache_timestamps[cache_key]
                logger.debug(f"Cache expired: {cache_key}")
                return None

        logger.debug(f"Cache hit: {cache_key}")
        return self._cache_data[cache_key]

    async def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """キャッシュをクリア."""
        if cache_type:
            # 特定タイプのキャッシュをクリア
            keys_to_remove = [k for k in self._cache_data.keys() if k.startswith(f"{cache_type}:")]
            for key in keys_to_remove:
                del self._cache_data[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]
            logger.info(f"Cleared cache for type: {cache_type}")
        else:
            # 全キャッシュをクリア
            self._cache_data.clear()
            self._cache_timestamps.clear()
            logger.info("Cleared all cache")

    async def set_manual_override(
        self, enabled: bool, level: Optional[FallbackLevel] = None
    ) -> None:
        """手動オーバーライドモードの設定."""
        self._manual_override = enabled

        if enabled and level:
            old_level = self._current_level
            self._current_level = level
            await self._update_service_states(level)
            logger.warning(f"Manual override enabled: {old_level.value} -> {level.value}")
        elif not enabled:
            logger.info("Manual override disabled")
            self._alert_sent = False  # アラート状態もリセット

    def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計情報を取得."""
        cache_types: Dict[str, int] = {}
        for key in self._cache_data.keys():
            cache_type = key.split(":", 1)[0]
            cache_types[cache_type] = cache_types.get(cache_type, 0) + 1

        return {
            "total_entries": len(self._cache_data),
            "types": cache_types,
            "current_level": self._current_level.value,
            "manual_override": self._manual_override,
        }

    async def health_check(self) -> Dict[str, Any]:
        """FallbackManagerの健全性チェック."""
        try:
            return {
                "status": "healthy" if self._initialized else "not_initialized",
                "current_level": self._current_level.value,
                "manual_override": self._manual_override,
                "active_services": sum(1 for active in self._service_states.values() if active),
                "total_services": len(self._service_states),
                "cache_entries": len(self._cache_data),
                "alert_sent": self._alert_sent,
            }
        except Exception as e:
            logger.error(f"FallbackManager health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def close(self) -> None:
        """FallbackManagerをクリーンアップ."""
        logger.info("Closing FallbackManager...")
        await self.clear_cache()
        self._initialized = False
