"""Review service for knowledge growth analysis and periodic reviews."""

import json
import logging
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Dict, List, Optional

from ..config import BotConfig
from .database import DatabaseService
from .knowledge_manager import KnowledgeManager

logger = logging.getLogger(__name__)


class ReviewServiceError(Exception):
    """Review service specific error."""


class ReviewService:
    """
    Service for generating periodic knowledge reviews and growth analysis.

    Provides functionality for daily, weekly, monthly and custom period reviews,
    with caching for performance optimization.
    """

    def __init__(self, config: BotConfig, db: DatabaseService, km: KnowledgeManager):
        """Initialize the review service."""
        self.config = config
        self.db = db
        self.km = km
        self._initialized = False
        logger.info("ReviewService initialized")

    async def initialize(self) -> None:
        """Initialize the review service."""
        if self._initialized:
            return

        try:
            # Ensure knowledge manager is initialized
            if not self.km._initialized:
                await self.km.initialize()

            # Clean up expired cache entries
            await self._cleanup_expired_cache()

            self._initialized = True
            logger.info("ReviewService initialization completed")

        except Exception as e:
            logger.error(f"Failed to initialize ReviewService: {e}")
            raise ReviewServiceError(f"Failed to initialize: {e}")

    async def generate_daily_review(self, user_id: str) -> Dict[str, Any]:
        """
        Generate a daily review for the user.

        Args:
            user_id: User ID to generate review for

        Returns:
            Dictionary containing daily review data

        Raises:
            ReviewServiceError: If review generation fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            now = datetime.utcnow()
            period_start = now - timedelta(days=1)
            period_end = now

            # Check cache first
            cached_review = await self._get_cached_review(
                user_id, "daily", period_start, period_end
            )
            if cached_review:
                return cached_review

            # Generate fresh review
            review_data = await self._generate_period_review(
                user_id, period_start, period_end, "daily"
            )

            # Cache the result (expires in 1 hour)
            await self._cache_review(
                user_id, "daily", period_start, period_end, review_data, hours=1
            )

            return review_data

        except Exception as e:
            logger.error(f"Failed to generate daily review for {user_id}: {e}")
            raise ReviewServiceError(f"Daily review generation failed: {e}")

    async def generate_weekly_review(self, user_id: str) -> Dict[str, Any]:
        """
        Generate a weekly review for the user.

        Args:
            user_id: User ID to generate review for

        Returns:
            Dictionary containing weekly review data

        Raises:
            ReviewServiceError: If review generation fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            now = datetime.utcnow()
            period_start = now - timedelta(days=7)
            period_end = now

            # Check cache first
            cached_review = await self._get_cached_review(
                user_id, "weekly", period_start, period_end
            )
            if cached_review:
                return cached_review

            # Generate fresh review
            review_data = await self._generate_period_review(
                user_id, period_start, period_end, "weekly"
            )

            # Cache the result (expires in 6 hours)
            await self._cache_review(
                user_id, "weekly", period_start, period_end, review_data, hours=6
            )

            return review_data

        except Exception as e:
            logger.error(f"Failed to generate weekly review for {user_id}: {e}")
            raise ReviewServiceError(f"Weekly review generation failed: {e}")

    async def generate_monthly_review(self, user_id: str) -> Dict[str, Any]:
        """
        Generate a monthly review for the user.

        Args:
            user_id: User ID to generate review for

        Returns:
            Dictionary containing monthly review data

        Raises:
            ReviewServiceError: If review generation fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            now = datetime.utcnow()
            period_start = now - timedelta(days=30)
            period_end = now

            # Check cache first
            cached_review = await self._get_cached_review(
                user_id, "monthly", period_start, period_end
            )
            if cached_review:
                return cached_review

            # Generate fresh review
            review_data = await self._generate_period_review(
                user_id, period_start, period_end, "monthly"
            )

            # Cache the result (expires in 24 hours)
            await self._cache_review(
                user_id, "monthly", period_start, period_end, review_data, hours=24
            )

            return review_data

        except Exception as e:
            logger.error(f"Failed to generate monthly review for {user_id}: {e}")
            raise ReviewServiceError(f"Monthly review generation failed: {e}")

    async def generate_custom_review(self, user_id: str, days: int) -> Dict[str, Any]:
        """
        Generate a custom period review for the user.

        Args:
            user_id: User ID to generate review for
            days: Number of days to review

        Returns:
            Dictionary containing custom review data

        Raises:
            ReviewServiceError: If review generation fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            if days <= 0 or days > 365:
                raise ReviewServiceError("Days must be between 1 and 365")

            now = datetime.utcnow()
            period_start = now - timedelta(days=days)
            period_end = now

            # Check cache first (use custom period type with days)
            period_type = f"custom_{days}"
            cached_review = await self._get_cached_review(
                user_id, period_type, period_start, period_end
            )
            if cached_review:
                return cached_review

            # Generate fresh review
            review_data = await self._generate_period_review(
                user_id, period_start, period_end, period_type
            )

            # Cache the result (expires based on period length)
            cache_hours = min(max(days // 10, 1), 24)  # 1-24 hours based on period
            await self._cache_review(
                user_id, period_type, period_start, period_end, review_data, hours=cache_hours
            )

            return review_data

        except Exception as e:
            logger.error(f"Failed to generate custom review for {user_id}: {e}")
            raise ReviewServiceError(f"Custom review generation failed: {e}")

    async def _generate_period_review(
        self, user_id: str, start_time: datetime, end_time: datetime, period_type: str
    ) -> Dict[str, Any]:
        """Generate review data for a specific time period."""
        try:
            # Get period statistics
            stats = await self._get_period_statistics(user_id, start_time, end_time)

            # Get activity trends
            trends = await self._get_activity_trends(user_id, start_time, end_time)

            # Get top tags and themes
            tag_analysis = await self._get_tag_analysis(user_id, start_time, end_time)

            # Get growth insights
            insights = await self._generate_growth_insights(
                stats, trends, tag_analysis, period_type
            )

            return {
                "period_type": period_type,
                "period_start": start_time.isoformat(),
                "period_end": end_time.isoformat(),
                "user_id": user_id,
                "statistics": stats,
                "trends": trends,
                "tag_analysis": tag_analysis,
                "insights": insights,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to generate period review: {e}")
            raise ReviewServiceError(f"Period review generation failed: {e}")

    async def _get_period_statistics(
        self, user_id: str, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get statistical data for the period."""
        try:
            async with self.db.get_connection() as conn:
                # Notes created
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM knowledge_notes
                    WHERE user_id = ? AND created_at BETWEEN ? AND ?
                """,
                    (user_id, start_time.isoformat(), end_time.isoformat()),
                )
                notes_created = (await cursor.fetchone())[0]

                # Notes edited (from history table)
                cursor = await conn.execute(
                    """
                    SELECT COUNT(*) FROM note_history
                    WHERE user_id = ? AND timestamp BETWEEN ? AND ?
                """,
                    (user_id, start_time.isoformat(), end_time.isoformat()),
                )
                notes_edited = (await cursor.fetchone())[0]

                # Total content length
                cursor = await conn.execute(
                    """
                    SELECT COALESCE(SUM(LENGTH(content)), 0) FROM knowledge_notes
                    WHERE user_id = ? AND created_at BETWEEN ? AND ?
                """,
                    (user_id, start_time.isoformat(), end_time.isoformat()),
                )
                total_content_length = (await cursor.fetchone())[0]

                # Unique tags used
                cursor = await conn.execute(
                    """
                    SELECT tags FROM knowledge_notes
                    WHERE user_id = ? AND created_at BETWEEN ? AND ?
                """,
                    (user_id, start_time.isoformat(), end_time.isoformat()),
                )

                all_tags = set()
                async for row in cursor:
                    if row[0]:
                        tags = json.loads(row[0])
                        all_tags.update(tags)

                return {
                    "notes_created": notes_created,
                    "notes_edited": notes_edited,
                    "total_activity": notes_created + notes_edited,
                    "total_content_length": total_content_length,
                    "unique_tags_used": len(all_tags),
                    "avg_note_length": (
                        total_content_length // notes_created if notes_created > 0 else 0
                    ),
                }

        except Exception as e:
            logger.error(f"Failed to get period statistics: {e}")
            raise ReviewServiceError(f"Statistics generation failed: {e}")

    async def _get_activity_trends(
        self, user_id: str, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get activity trend analysis for the period."""
        try:
            # Daily activity breakdown
            daily_activity = []
            current_date = start_time.date()
            end_date = end_time.date()

            async with self.db.get_connection() as conn:
                while current_date <= end_date:
                    day_start = datetime.combine(current_date, datetime.min.time())
                    day_end = datetime.combine(current_date, datetime.max.time())

                    # Count daily activities
                    cursor = await conn.execute(
                        """
                        SELECT
                            (SELECT COUNT(*) FROM knowledge_notes
                             WHERE user_id = ? AND created_at BETWEEN ? AND ?) +
                            (SELECT COUNT(*) FROM note_history
                             WHERE user_id = ? AND timestamp BETWEEN ? AND ?) as total_activity
                    """,
                        (
                            user_id,
                            day_start.isoformat(),
                            day_end.isoformat(),
                            user_id,
                            day_start.isoformat(),
                            day_end.isoformat(),
                        ),
                    )
                    activity_count = (await cursor.fetchone())[0]

                    daily_activity.append(
                        {"date": current_date.isoformat(), "activity": activity_count}
                    )

                    current_date += timedelta(days=1)

                # Calculate trend metrics
                activities = [day["activity"] for day in daily_activity]
                avg_daily_activity = sum(activities) / len(activities) if activities else 0

                # Simple trend calculation (slope)
                if len(activities) > 1:
                    x_values = list(range(len(activities)))
                    x_mean = sum(x_values) / len(x_values)
                    y_mean = avg_daily_activity

                    numerator = sum(
                        (x - x_mean) * (y - y_mean) for x, y in zip(x_values, activities)
                    )
                    denominator = sum((x - x_mean) ** 2 for x in x_values)

                    trend_slope = numerator / denominator if denominator != 0 else 0
                else:
                    trend_slope = 0

                return {
                    "daily_activity": daily_activity,
                    "avg_daily_activity": round(avg_daily_activity, 2),
                    "trend_direction": "increasing"
                    if trend_slope > 0
                    else "decreasing"
                    if trend_slope < 0
                    else "stable",
                    "trend_strength": abs(trend_slope),
                }

        except Exception as e:
            logger.error(f"Failed to get activity trends: {e}")
            raise ReviewServiceError(f"Trend analysis failed: {e}")

    async def _get_tag_analysis(
        self, user_id: str, start_time: datetime, end_time: datetime
    ) -> Dict[str, Any]:
        """Get tag usage analysis for the period."""
        try:
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT tags FROM knowledge_notes
                    WHERE user_id = ? AND created_at BETWEEN ? AND ?
                """,
                    (user_id, start_time.isoformat(), end_time.isoformat()),
                )

                tag_counts: Dict[str, int] = {}
                async for row in cursor:
                    if row[0]:
                        tags = json.loads(row[0])
                        for tag in tags:
                            tag_counts[tag] = tag_counts.get(tag, 0) + 1

                # Sort by frequency
                sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)

                return {
                    "total_tags": len(tag_counts),
                    "top_tags": sorted_tags[:10],  # Top 10 tags
                    "tag_distribution": dict(sorted_tags),
                }

        except Exception as e:
            logger.error(f"Failed to get tag analysis: {e}")
            raise ReviewServiceError(f"Tag analysis failed: {e}")

    async def _generate_growth_insights(
        self,
        stats: Dict[str, Any],
        trends: Dict[str, Any],
        tag_analysis: Dict[str, Any],
        period_type: str,
    ) -> List[str]:
        """Generate growth insights based on the analysis."""
        insights = []

        # Activity level insights
        total_activity = stats["total_activity"]
        if period_type == "daily":
            if total_activity >= 5:
                insights.append("🔥 素晴らしい！今日は非常に活発な知識活動でした")
            elif total_activity >= 2:
                insights.append("✅ 今日も順調に知識を蓄積しています")
            else:
                insights.append("💡 明日はもう少し多くの知識を記録してみませんか？")
        elif period_type == "weekly":
            if total_activity >= 20:
                insights.append("🚀 この1週間は知識蓄積のペースが素晴らしいです！")
            elif total_activity >= 10:
                insights.append("📈 安定した学習ペースを維持できています")
            else:
                insights.append("📝 来週はより多くの学習記録を目指しましょう")

        # Content quality insights
        avg_length = stats["avg_note_length"]
        if avg_length > 200:
            insights.append("📚 詳細で充実したノートを作成されています")
        elif avg_length > 100:
            insights.append("✏️ 適切な長さのノートが作成できています")

        # Tag diversity insights
        unique_tags = stats["unique_tags_used"]
        if unique_tags > 10:
            insights.append("🏷️ 多様なトピックに取り組まれていて素晴らしいです")
        elif unique_tags > 5:
            insights.append("🎯 バランスの取れた学習領域をカバーしています")

        # Trend insights
        if trends["trend_direction"] == "increasing":
            insights.append("📊 学習活動が増加傾向にあります。この調子です！")
        elif trends["trend_direction"] == "decreasing":
            insights.append("⚠️ 最近活動が減少気味です。無理のない範囲で継続を心がけましょう")

        # Top tag insights
        if tag_analysis["top_tags"]:
            top_tag, count = tag_analysis["top_tags"][0]
            insights.append(f"🏆 最も注力している分野は「{top_tag}」です（{count}回使用）")

        return insights

    async def _get_cached_review(
        self, user_id: str, period_type: str, start_time: datetime, end_time: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get cached review if available and not expired."""
        try:
            cache_key = self._generate_cache_key(user_id, period_type, start_time, end_time)

            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT cache_data FROM review_cache
                    WHERE cache_key = ? AND expires_at > ?
                """,
                    (cache_key, datetime.utcnow().isoformat()),
                )

                row = await cursor.fetchone()
                if row:
                    cached_data: Dict[str, Any] = json.loads(row[0])
                    return cached_data

                return None

        except Exception as e:
            logger.warning(f"Failed to get cached review: {e}")
            return None

    async def _cache_review(
        self,
        user_id: str,
        period_type: str,
        start_time: datetime,
        end_time: datetime,
        review_data: Dict[str, Any],
        hours: int = 1,
    ) -> None:
        """Cache review data for performance."""
        try:
            cache_key = self._generate_cache_key(user_id, period_type, start_time, end_time)
            expires_at = datetime.utcnow() + timedelta(hours=hours)

            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT OR REPLACE INTO review_cache
                    (cache_key, user_id, period_type, period_start, period_end,
                     cache_data, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        cache_key,
                        user_id,
                        period_type,
                        start_time.isoformat(),
                        end_time.isoformat(),
                        json.dumps(review_data),
                        expires_at.isoformat(),
                    ),
                )

        except Exception as e:
            logger.warning(f"Failed to cache review: {e}")

    def _generate_cache_key(
        self, user_id: str, period_type: str, start_time: datetime, end_time: datetime
    ) -> str:
        """Generate a unique cache key for the review."""
        key_data = f"{user_id}:{period_type}:{start_time.isoformat()}:{end_time.isoformat()}"
        return sha256(key_data.encode()).hexdigest()

    async def _cleanup_expired_cache(self) -> None:
        """Clean up expired cache entries."""
        try:
            async with self.db.get_connection() as conn:
                await conn.execute(
                    "DELETE FROM review_cache WHERE expires_at < ?",
                    (datetime.utcnow().isoformat(),),
                )

        except Exception as e:
            logger.warning(f"Failed to cleanup expired cache: {e}")

    async def close(self) -> None:
        """Close the review service and cleanup resources."""
        self._initialized = False
        logger.info("ReviewService closed")
