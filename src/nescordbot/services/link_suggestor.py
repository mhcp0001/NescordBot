"""Link suggestion functionality for note connections."""

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from .database import DatabaseService

logger = logging.getLogger(__name__)


class LinkSuggestionError(Exception):
    """Exception raised when link suggestion fails."""


class LinkSuggestor:
    """Suggests links between notes based on content similarity and relationships."""

    def __init__(self, db: DatabaseService):
        """
        Initialize LinkSuggestor.

        Args:
            db: Database service instance
        """
        self.db = db
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the link suggestor."""
        if not self._initialized:
            if not self.db.is_initialized:
                await self.db.initialize()
            self._initialized = True
            logger.info("LinkSuggestor initialized")

    async def suggest_links_for_note(
        self, note_id: str, max_suggestions: int = 5, min_similarity: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Suggest potential links for a given note.

        Args:
            note_id: ID of the note to suggest links for
            max_suggestions: Maximum number of suggestions to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of suggested notes with similarity scores

        Raises:
            LinkSuggestionError: If suggestion generation fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Check if note exists first
            async with self.db.get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT id, title, content, tags FROM knowledge_notes WHERE id = ?", (note_id,)
                )
                source_row = await cursor.fetchone()

            # Check outside the context manager to avoid exception suppression
            if not source_row:
                raise LinkSuggestionError(f"Note {note_id} not found")

            # Proceed with processing
            source_note = {
                "id": source_row[0],
                "title": source_row[1],
                "content": source_row[2],
                "tags": self._parse_tags(source_row[3]),
            }

            async with self.db.get_connection() as conn:
                # Get all other notes (excluding current one and already linked)
                cursor = await conn.execute(
                    """
                    SELECT kn.id, kn.title, kn.content, kn.tags
                    FROM knowledge_notes kn
                    WHERE kn.id != ?
                    AND kn.id NOT IN (
                        SELECT to_note_id FROM note_links WHERE from_note_id = ?
                        UNION
                        SELECT from_note_id FROM note_links WHERE to_note_id = ?
                    )
                    """,
                    (note_id, note_id, note_id),
                )
                candidate_rows = await cursor.fetchall()

                # Initialize candidates after we know source note exists
                candidates = []
                for row in candidate_rows:
                    candidates.append(
                        {
                            "id": row[0],
                            "title": row[1],
                            "content": row[2],
                            "tags": self._parse_tags(row[3]),
                        }
                    )

                # Calculate similarity scores
                suggestions = []
                for candidate in candidates:
                    similarity_score = self._calculate_similarity(source_note, candidate)

                    if similarity_score >= min_similarity:
                        suggestions.append(
                            {
                                "note_id": candidate["id"],
                                "title": candidate["title"],
                                "similarity_score": similarity_score,
                                "similarity_reasons": self._get_similarity_reasons(
                                    source_note, candidate
                                ),
                            }
                        )

                # Sort by similarity score and return top suggestions
                suggestions.sort(key=lambda x: x["similarity_score"], reverse=True)
                return suggestions[:max_suggestions]

        except LinkSuggestionError:
            # Re-raise LinkSuggestionError as-is to preserve error semantics
            raise
        except Exception as e:
            logger.error(f"Failed to suggest links for note {note_id}: {e}")
            raise LinkSuggestionError(f"Failed to suggest links: {e}")

    async def suggest_by_content_keywords(
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

        try:
            # Extract keywords from content
            keywords = self._extract_keywords(content)
            if not keywords:
                return []

            async with self.db.get_connection() as conn:
                query = """
                    SELECT id, title, content, tags,
                           (CASE WHEN title LIKE ? THEN 3 ELSE 0 END +
                            CASE WHEN content LIKE ? THEN 1 ELSE 0 END) as relevance_score
                    FROM knowledge_notes
                    WHERE (title LIKE ? OR content LIKE ?)
                """
                params: List[Any] = []

                for keyword in keywords[:5]:  # Use top 5 keywords for LIKE search
                    pattern = f"%{keyword}%"
                    query += " OR title LIKE ? OR content LIKE ?"
                    params.extend([pattern, pattern])

                if exclude_note_id:
                    query += " AND id != ?"
                    params.append(exclude_note_id)

                query += " ORDER BY relevance_score DESC LIMIT ?"
                params.append(max_suggestions)

                # Simple fallback query
                cursor = await conn.execute(
                    """
                    SELECT id, title, content, tags
                    FROM knowledge_notes
                    WHERE (title LIKE ? OR content LIKE ?)
                    AND id != COALESCE(?, '')
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (
                        f"%{keywords[0]}%" if keywords else "%",
                        f"%{keywords[0]}%" if keywords else "%",
                        exclude_note_id,
                        max_suggestions,
                    ),
                )

                rows = await cursor.fetchall()

            suggestions = []
            for row in rows:
                suggestions.append(
                    {
                        "note_id": row[0],
                        "title": row[1],
                        "tags": self._parse_tags(row[3]),
                        "match_reason": "content_keywords",
                    }
                )

            return suggestions

        except Exception as e:
            logger.error(f"Failed to suggest by content keywords: {e}")
            raise LinkSuggestionError(f"Failed to suggest by keywords: {e}")

    def _calculate_similarity(self, note1: Dict[str, Any], note2: Dict[str, Any]) -> float:
        """
        Calculate similarity between two notes.

        Args:
            note1: First note data
            note2: Second note data

        Returns:
            Similarity score (0.0-1.0)
        """
        # Title similarity (weight: 0.4)
        title_sim = SequenceMatcher(None, note1["title"].lower(), note2["title"].lower()).ratio()

        # Content similarity (weight: 0.4)
        content_sim = self._content_similarity(note1["content"], note2["content"])

        # Tag similarity (weight: 0.2)
        tag_sim = self._tag_similarity(note1["tags"], note2["tags"])

        # Weighted average
        total_similarity = title_sim * 0.4 + content_sim * 0.4 + tag_sim * 0.2
        return min(total_similarity, 1.0)

    def _content_similarity(self, content1: str, content2: str) -> float:
        """Calculate content similarity using keyword overlap."""
        keywords1 = set(self._extract_keywords(content1))
        keywords2 = set(self._extract_keywords(content2))

        if not keywords1 or not keywords2:
            return 0.0

        # Jaccard similarity
        intersection = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))

        return intersection / union if union > 0 else 0.0

    def _tag_similarity(self, tags1: List[str], tags2: List[str]) -> float:
        """Calculate tag similarity."""
        if not tags1 or not tags2:
            return 0.0

        set1 = set(tag.lower() for tag in tags1)
        set2 = set(tag.lower() for tag in tags2)

        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))

        return intersection / union if union > 0 else 0.0

    def _extract_keywords(self, text: str, min_length: int = 3) -> List[str]:
        """
        Extract keywords from text.

        Args:
            text: Text to extract keywords from
            min_length: Minimum keyword length

        Returns:
            List of keywords sorted by frequency
        """
        if not text:
            return []

        # Remove common words and extract meaningful terms
        stop_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "は",
            "が",
            "を",
            "に",
            "へ",
            "と",
            "で",
            "から",
            "まで",
            "より",
            "こと",
            "もの",
            "これ",
            "それ",
            "あれ",
            "この",
            "その",
            "あの",
            "です",
            "である",
            "だ",
            "である",
        }

        # Extract words (alphanumeric sequences)
        words = re.findall(r"\b\w+\b", text.lower())

        # Filter by length and remove stop words
        keywords = [word for word in words if len(word) >= min_length and word not in stop_words]

        # Count frequency and return sorted by frequency
        word_count: Dict[str, int] = {}
        for word in keywords:
            word_count[word] = word_count.get(word, 0) + 1

        return sorted(word_count.keys(), key=lambda x: word_count[x], reverse=True)

    def _get_similarity_reasons(self, note1: Dict[str, Any], note2: Dict[str, Any]) -> List[str]:
        """Get reasons why two notes are similar."""
        reasons = []

        # Title similarity
        title_sim = SequenceMatcher(None, note1["title"].lower(), note2["title"].lower()).ratio()
        if title_sim > 0.5:
            reasons.append(f"Similar titles ({title_sim:.1%})")

        # Common tags
        common_tags = set(tag.lower() for tag in note1["tags"]) & set(
            tag.lower() for tag in note2["tags"]
        )
        if common_tags:
            reasons.append(f"Common tags: {', '.join(common_tags)}")

        # Common keywords
        keywords1 = set(self._extract_keywords(note1["content"])[:10])
        keywords2 = set(self._extract_keywords(note2["content"])[:10])
        common_keywords = keywords1 & keywords2
        if common_keywords:
            reasons.append(f"Common keywords: {', '.join(list(common_keywords)[:3])}")

        return reasons

    def _parse_tags(self, tags_str: Optional[str]) -> List[str]:
        """Parse tags from JSON string."""
        if not tags_str:
            return []

        try:
            import json

            parsed = json.loads(tags_str) if tags_str else []
            return list(parsed) if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the link suggestor.

        Returns:
            Health status information
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Test basic functionality
            async with self.db.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM knowledge_notes")
                result = await cursor.fetchone()

            # Process result outside context manager to allow exceptions to propagate
            note_count = result[0]

            return {
                "status": "healthy",
                "initialized": self._initialized,
                "total_notes": note_count,
                "database_connected": self.db.is_initialized,
            }
        except Exception as e:
            logger.error(f"LinkSuggestor health check failed: {e}")
            return {"status": "unhealthy", "error": str(e), "initialized": self._initialized}
