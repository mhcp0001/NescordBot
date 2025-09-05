"""Tests for ReviewService."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.nescordbot.config import BotConfig
from src.nescordbot.services.database import DatabaseService
from src.nescordbot.services.knowledge_manager import KnowledgeManager
from src.nescordbot.services.review_service import ReviewService, ReviewServiceError


class TestReviewService:
    """Test ReviewService functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock BotConfig."""
        config = MagicMock(spec=BotConfig)
        return config

    @pytest.fixture
    def mock_db(self):
        """Mock DatabaseService."""
        db = AsyncMock(spec=DatabaseService)

        # Mock connection context manager
        mock_connection = AsyncMock()
        mock_cursor = AsyncMock()

        # Setup cursor fetchone/fetchall returns
        mock_cursor.fetchone.return_value = (5,)  # Default count
        mock_cursor.fetchall.return_value = []

        mock_connection.execute.return_value = mock_cursor
        mock_connection.__aenter__.return_value = mock_connection
        mock_connection.__aexit__.return_value = None

        db.get_connection.return_value = mock_connection
        return db

    @pytest.fixture
    def mock_km(self):
        """Mock KnowledgeManager."""
        km = AsyncMock(spec=KnowledgeManager)
        km._initialized = True
        km.initialize.return_value = None
        return km

    @pytest.fixture
    def review_service(self, mock_config, mock_db, mock_km):
        """Create ReviewService instance."""
        return ReviewService(mock_config, mock_db, mock_km)

    @pytest.mark.asyncio
    async def test_initialization(self, review_service, mock_km):
        """Test service initialization."""
        assert not review_service._initialized

        # KM is already initialized in fixture, so initialize() won't be called
        await review_service.initialize()

        assert review_service._initialized
        # Don't assert initialize was called since km._initialized is True

    @pytest.mark.asyncio
    async def test_initialization_km_not_initialized(self, review_service, mock_km):
        """Test service initialization when KM is not initialized."""
        mock_km._initialized = False

        await review_service.initialize()

        assert review_service._initialized
        mock_km.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_review_success(self, review_service):
        """Test successful daily review generation."""
        review_service._initialized = True

        # Mock the entire _generate_period_review method for simplicity
        mock_review_data = {
            "period_type": "daily",
            "user_id": "user123",
            "statistics": {
                "notes_created": 2,
                "notes_edited": 1,
                "total_activity": 3,
                "total_content_length": 500,
                "unique_tags_used": 4,
                "avg_note_length": 250,
            },
            "trends": {
                "trend_direction": "increasing",
                "avg_daily_activity": 1.5,
                "daily_activity": [{"date": "2024-01-01", "activity": 2}],
            },
            "tag_analysis": {
                "total_tags": 4,
                "top_tags": [("python", 2), ("ai", 1)],
                "tag_distribution": {"python": 2, "ai": 1},
            },
            "insights": ["Test insight"],
            "generated_at": datetime.utcnow().isoformat(),
        }

        with patch.object(review_service, "_get_cached_review", return_value=None), patch.object(
            review_service, "_cache_review"
        ), patch.object(review_service, "_generate_period_review", return_value=mock_review_data):
            result = await review_service.generate_daily_review("user123")

            assert result["period_type"] == "daily"
            assert result["user_id"] == "user123"
            assert "statistics" in result
            assert "trends" in result
            assert "tag_analysis" in result
            assert "insights" in result

    @pytest.mark.asyncio
    async def test_daily_review_cached(self, review_service):
        """Test daily review with cached result."""
        review_service._initialized = True

        cached_data = {
            "period_type": "daily",
            "user_id": "user123",
            "statistics": {"total_activity": 3},
            "trends": {"trend_direction": "stable"},
            "tag_analysis": {"top_tags": []},
            "insights": ["Test insight"],
            "generated_at": datetime.utcnow().isoformat(),
        }

        with patch.object(review_service, "_get_cached_review", return_value=cached_data):
            result = await review_service.generate_daily_review("user123")

            assert result == cached_data

    @pytest.mark.asyncio
    async def test_weekly_review_success(self, review_service, mock_db):
        """Test successful weekly review generation."""
        review_service._initialized = True

        with patch.object(review_service, "_generate_period_review") as mock_generate:
            mock_generate.return_value = {
                "period_type": "weekly",
                "user_id": "user123",
                "statistics": {"total_activity": 15},
                "trends": {"trend_direction": "increasing"},
                "tag_analysis": {"top_tags": [("work", 5)]},
                "insights": ["Great progress this week!"],
                "generated_at": datetime.utcnow().isoformat(),
            }

            with patch.object(
                review_service, "_get_cached_review", return_value=None
            ), patch.object(review_service, "_cache_review"):
                result = await review_service.generate_weekly_review("user123")

                assert result["period_type"] == "weekly"
                assert result["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_monthly_review_success(self, review_service):
        """Test successful monthly review generation."""
        review_service._initialized = True

        with patch.object(review_service, "_generate_period_review") as mock_generate:
            mock_generate.return_value = {
                "period_type": "monthly",
                "user_id": "user123",
                "statistics": {"total_activity": 50},
                "trends": {"trend_direction": "stable"},
                "tag_analysis": {"top_tags": [("learning", 15)]},
                "insights": ["Consistent learning pattern"],
                "generated_at": datetime.utcnow().isoformat(),
            }

            with patch.object(
                review_service, "_get_cached_review", return_value=None
            ), patch.object(review_service, "_cache_review"):
                result = await review_service.generate_monthly_review("user123")

                assert result["period_type"] == "monthly"

    @pytest.mark.asyncio
    async def test_custom_review_success(self, review_service):
        """Test successful custom review generation."""
        review_service._initialized = True

        days = 14

        with patch.object(review_service, "_generate_period_review") as mock_generate:
            mock_generate.return_value = {
                "period_type": f"custom_{days}",
                "user_id": "user123",
                "statistics": {"total_activity": 25},
                "trends": {"trend_direction": "increasing"},
                "tag_analysis": {"top_tags": []},
                "insights": ["Good progress over 2 weeks"],
                "generated_at": datetime.utcnow().isoformat(),
            }

            with patch.object(
                review_service, "_get_cached_review", return_value=None
            ), patch.object(review_service, "_cache_review"):
                result = await review_service.generate_custom_review("user123", days)

                assert result["period_type"] == f"custom_{days}"

    @pytest.mark.asyncio
    async def test_custom_review_invalid_days(self, review_service):
        """Test custom review with invalid days parameter."""
        review_service._initialized = True

        with pytest.raises(ReviewServiceError, match="Days must be between 1 and 365"):
            await review_service.generate_custom_review("user123", 0)

        with pytest.raises(ReviewServiceError, match="Days must be between 1 and 365"):
            await review_service.generate_custom_review("user123", 400)

    @pytest.mark.asyncio
    async def test_period_statistics(self, review_service, mock_db):
        """Test _get_period_statistics method."""
        review_service._initialized = True

        start_time = datetime.utcnow() - timedelta(days=1)
        end_time = datetime.utcnow()

        mock_connection = mock_db.get_connection.return_value.__aenter__.return_value
        mock_cursor = AsyncMock()

        # Mock database responses
        mock_cursor.fetchone.side_effect = [
            (3,),  # notes created
            (2,),  # notes edited
            (750,),  # total content length
        ]

        # Mock tags query
        mock_cursor.__aiter__.return_value = iter(
            [
                ('["python", "ai"]',),
                ('["development", "testing"]',),
            ]
        )

        mock_connection.execute.return_value = mock_cursor

        stats = await review_service._get_period_statistics("user123", start_time, end_time)

        assert stats["notes_created"] == 3
        assert stats["notes_edited"] == 2
        assert stats["total_activity"] == 5
        assert stats["total_content_length"] == 750
        assert stats["unique_tags_used"] == 4  # python, ai, development, testing
        assert stats["avg_note_length"] == 250  # 750 / 3

    @pytest.mark.asyncio
    async def test_tag_analysis(self, review_service, mock_db):
        """Test _get_tag_analysis method."""
        review_service._initialized = True

        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        mock_connection = mock_db.get_connection.return_value.__aenter__.return_value
        mock_cursor = AsyncMock()

        # Mock tags query response
        mock_cursor.__aiter__.return_value = iter(
            [
                ('["python", "ai"]',),
                ('["python", "development"]',),
                ('["ai", "machine-learning"]',),
            ]
        )

        mock_connection.execute.return_value = mock_cursor

        analysis = await review_service._get_tag_analysis("user123", start_time, end_time)

        assert analysis["total_tags"] == 4
        assert len(analysis["top_tags"]) <= 10
        # python appears twice, so it should be first
        assert analysis["top_tags"][0] == ("python", 2)

    @pytest.mark.asyncio
    async def test_growth_insights(self, review_service):
        """Test _generate_growth_insights method."""
        stats = {
            "total_activity": 8,
            "notes_created": 5,
            "notes_edited": 3,
            "avg_note_length": 150,
            "unique_tags_used": 12,
        }

        trends = {
            "trend_direction": "increasing",
            "avg_daily_activity": 2.5,
        }

        tag_analysis = {
            "top_tags": [("python", 5), ("ai", 3)],
            "total_tags": 12,
        }

        insights = await review_service._generate_growth_insights(
            stats, trends, tag_analysis, "weekly"
        )

        assert len(insights) > 0
        assert any("python" in insight for insight in insights)
        assert any("増加傾向" in insight for insight in insights)

    @pytest.mark.asyncio
    async def test_cache_operations(self, review_service, mock_db):
        """Test cache get and set operations."""
        review_service._initialized = True

        user_id = "user123"
        period_type = "daily"
        start_time = datetime.utcnow() - timedelta(days=1)
        end_time = datetime.utcnow()

        # Test cache miss
        mock_connection = mock_db.get_connection.return_value.__aenter__.return_value
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None
        mock_connection.execute.return_value = mock_cursor

        result = await review_service._get_cached_review(user_id, period_type, start_time, end_time)
        assert result is None

        # Test cache set
        review_data = {
            "period_type": "daily",
            "user_id": user_id,
            "statistics": {"total_activity": 5},
        }

        await review_service._cache_review(
            user_id, period_type, start_time, end_time, review_data, hours=1
        )

        # Verify cache insert was called
        mock_connection.execute.assert_called()

    @pytest.mark.asyncio
    async def test_service_not_initialized_error(self, review_service):
        """Test that service initializes automatically when not initialized."""
        assert not review_service._initialized

        # Service should auto-initialize, so we'll test auto-initialization instead
        with patch.object(review_service, "_get_cached_review", return_value=None), patch.object(
            review_service, "_cache_review"
        ), patch.object(review_service, "_generate_period_review") as mock_generate:
            mock_generate.return_value = {
                "period_type": "daily",
                "user_id": "user123",
                "statistics": {"total_activity": 0},
                "trends": {"trend_direction": "stable"},
                "tag_analysis": {"top_tags": []},
                "insights": [],
                "generated_at": datetime.utcnow().isoformat(),
            }

            result = await review_service.generate_daily_review("user123")

            # Service should be initialized after the call
            assert review_service._initialized
            assert result["user_id"] == "user123"

    @pytest.mark.asyncio
    async def test_close(self, review_service):
        """Test service cleanup."""
        review_service._initialized = True

        await review_service.close()

        assert not review_service._initialized
