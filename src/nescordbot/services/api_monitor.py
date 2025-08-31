"""
APIモニター - TokenManagerとFallbackManagerの連携サービス.

API使用量の監視とフォールバック機能の自動制御を行う。
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from ..config import BotConfig
from .fallback_manager import FallbackLevel, FallbackManager
from .token_manager import TokenManager, TokenUsageError

logger = logging.getLogger(__name__)


class APIMonitorError(Exception):
    """APIMonitor related errors."""

    pass


class APIMonitor:
    """
    API使用量監視とフォールバック制御を管理するクラス.

    TokenManagerから使用量データを取得し、
    FallbackManagerのレベル制御を自動実行する。
    """

    def __init__(
        self,
        config: BotConfig,
        token_manager: TokenManager,
        fallback_manager: FallbackManager,
    ):
        """Initialize APIMonitor."""
        self.config = config
        self.token_manager = token_manager
        self.fallback_manager = fallback_manager
        self._monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 300  # 5分間隔
        self._shutdown = False

    async def start_monitoring(self) -> None:
        """API監視を開始."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("API monitoring already running")
            return

        logger.info("Starting API monitoring...")
        self._shutdown = False
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self) -> None:
        """API監視を停止."""
        logger.info("Stopping API monitoring...")
        self._shutdown = True

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("API monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """監視メインループ."""
        logger.info("API monitoring loop started")

        while not self._shutdown:
            try:
                await self._check_api_limits()
                await asyncio.sleep(self._monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # エラー時は1分待機

        logger.info("API monitoring loop stopped")

    async def _check_api_limits(self) -> None:
        """API制限をチェックしてフォールバックレベルを更新."""
        try:
            # Gemini APIの使用量をチェック
            usage_data = await self.token_manager.check_limits("gemini")

            # フォールバックレベルを更新
            new_level = await self.fallback_manager.check_and_update_fallback_level(usage_data)

            # ログ出力
            usage_pct = usage_data.get("monthly_usage_percentage", 0)
            current_tokens = usage_data.get("current_monthly_tokens", 0)
            monthly_limit = usage_data.get("monthly_limit", 0)

            logger.debug(
                f"API Status - Usage: {usage_pct:.1f}% "
                f"({current_tokens:,}/{monthly_limit:,} tokens), "
                f"Level: {new_level.value}"
            )

            # クリティカル状態での追加ログ
            if new_level in [FallbackLevel.CRITICAL, FallbackLevel.EMERGENCY]:
                logger.warning(
                    f"API CRITICAL STATUS: {usage_pct:.1f}% usage, level: {new_level.value}"
                )

        except TokenUsageError as e:
            logger.error(f"Token usage check failed: {e}")
        except Exception as e:
            logger.error(f"API limit check failed: {e}")

    async def force_check(self) -> Dict[str, Any]:
        """API状態の即座チェック（手動実行用）."""
        try:
            # 現在の使用量を取得
            usage_data = await self.token_manager.check_limits("gemini")

            # フォールバックレベルを更新
            current_level = await self.fallback_manager.check_and_update_fallback_level(usage_data)

            # サービス状態を取得
            service_states = self.fallback_manager.get_service_states()

            # キャッシュ統計を取得
            cache_stats = self.fallback_manager.get_cache_stats()

            return {
                "timestamp": datetime.now().isoformat(),
                "usage_data": usage_data,
                "fallback_level": current_level.value,
                "service_states": service_states,
                "cache_stats": cache_stats,
            }

        except Exception as e:
            logger.error(f"Force check failed: {e}")
            raise APIMonitorError(f"Force check failed: {e}")

    async def get_monitoring_status(self) -> Dict[str, Any]:
        """監視ステータスを取得."""
        return {
            "monitoring_active": self._monitoring_task is not None
            and not self._monitoring_task.done(),
            "monitoring_interval": self._monitoring_interval,
            "shutdown": self._shutdown,
            "fallback_level": self.fallback_manager.get_current_level().value,
            "service_states": self.fallback_manager.get_service_states(),
        }

    async def set_monitoring_interval(self, interval_seconds: int) -> None:
        """監視間隔を設定."""
        if interval_seconds < 60:
            raise APIMonitorError("Monitoring interval must be at least 60 seconds")

        old_interval = self._monitoring_interval
        self._monitoring_interval = interval_seconds
        logger.info(f"Monitoring interval changed: {old_interval}s -> {interval_seconds}s")

    async def emergency_override(self, level: FallbackLevel) -> None:
        """緊急時のフォールバックレベル手動設定."""
        logger.warning(f"Emergency override activated: {level.value}")
        await self.fallback_manager.set_manual_override(True, level)

    async def clear_emergency_override(self) -> None:
        """緊急時オーバーライドの解除."""
        logger.info("Emergency override cleared")
        await self.fallback_manager.set_manual_override(False)

    async def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """キャッシュのクリア."""
        await self.fallback_manager.clear_cache(cache_type)
        logger.info(f"Cache cleared: {cache_type or 'all'}")

    async def health_check(self) -> Dict[str, Any]:
        """APIMonitorの健全性チェック."""
        try:
            # 各コンポーネントの健全性をチェック
            token_manager_health = await self.token_manager.health_check()
            fallback_manager_health = await self.fallback_manager.health_check()

            monitoring_status = await self.get_monitoring_status()

            return {
                "status": "healthy",
                "components": {
                    "token_manager": token_manager_health,
                    "fallback_manager": fallback_manager_health,
                    "monitoring": monitoring_status,
                },
            }

        except Exception as e:
            logger.error(f"APIMonitor health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def close(self) -> None:
        """APIMonitorをクリーンアップ."""
        logger.info("Closing APIMonitor...")
        await self.stop_monitoring()
        logger.info("APIMonitor closed")
