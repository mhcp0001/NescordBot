"""
SearchEngine for hybrid vector and keyword search.

This module provides SearchEngine with RRF (Reciprocal Rank Fusion)
for combining vector similarity search and FTS5 keyword search results.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast

from ..config import BotConfig
from ..logger import get_logger
from .chromadb_service import ChromaDBService
from .database import DatabaseService
from .embedding import EmbeddingService


@dataclass
class SearchResult:
    """Result from hybrid search."""

    note_id: str
    title: str
    content: str
    score: float  # 0.0 - 1.0 normalized score
    source: str  # "vector", "keyword", "hybrid"
    metadata: Dict[str, Any]
    created_at: datetime
    relevance_reason: Optional[str] = None


@dataclass
class SearchFilters:
    """Filters for advanced search."""

    tags: Optional[List[str]] = None
    date_range: Optional[Tuple[datetime, datetime]] = None
    min_score: Optional[float] = None
    content_type: Optional[str] = None  # "fleeting", "permanent", "link"
    user_id: Optional[str] = None


@dataclass
class SearchHistory:
    """Search history entry."""

    id: str
    user_id: str
    query: str
    results_count: int
    timestamp: datetime
    execution_time_ms: Optional[float] = None


class SearchEngineError(Exception):
    """Base exception for SearchEngine."""

    pass


class SearchTimeoutError(SearchEngineError):
    """Search operation timeout."""

    pass


class SearchIndexError(SearchEngineError):
    """Search index related errors."""

    pass


class SearchQueryError(SearchEngineError):
    """Invalid search query."""

    pass


class SearchEngine:
    """Hybrid vector and keyword search engine with RRF fusion."""

    def __init__(
        self,
        chroma_service: ChromaDBService,
        db_service: DatabaseService,
        embedding_service: EmbeddingService,
        config: BotConfig,
    ):
        """Initialize SearchEngine with required services.

        Args:
            chroma_service: ChromaDB service for vector search
            db_service: Database service for keyword search and history
            embedding_service: Embedding service for query embeddings
            config: Bot configuration
        """
        self.chroma = chroma_service
        self.db = db_service
        self.embeddings = embedding_service
        self.config = config
        self.logger = get_logger(__name__)

        # RRF configuration
        self.rrf_k = 60  # RRF constant (typical value)
        self.default_alpha = 0.7  # Vector search weight

        # Performance settings
        self.max_search_time = 30.0  # seconds
        self.default_limit = 10

    async def hybrid_search(
        self,
        query: str,
        alpha: Optional[float] = None,
        limit: Optional[int] = None,
        filters: Optional[SearchFilters] = None,
    ) -> List[SearchResult]:
        """Perform hybrid search using RRF fusion.

        Args:
            query: Search query text
            alpha: Vector search weight (0.0-1.0), defaults to 0.7
            limit: Maximum results to return
            filters: Optional search filters

        Returns:
            List of SearchResult ordered by relevance score

        Raises:
            SearchQueryError: Invalid query
            SearchTimeoutError: Search timeout
            SearchEngineError: General search error
        """
        start_time = time.time()

        if not query or not query.strip():
            raise SearchQueryError("Empty search query")

        if alpha is None:
            alpha = self.default_alpha
        if limit is None:
            limit = self.default_limit

        # Validate parameters
        if not 0.0 <= alpha <= 1.0:
            raise SearchQueryError(f"Alpha must be between 0.0 and 1.0, got {alpha}")
        if limit <= 0:
            raise SearchQueryError(f"Limit must be positive, got {limit}")

        query = query.strip()

        try:
            # Run vector and keyword search in parallel
            search_limit = min(limit * 3, 100)  # Get more results for better fusion

            vector_task = self._vector_search(query, search_limit, filters)
            keyword_task = self._keyword_search(query, search_limit, filters)

            vector_results, keyword_results = await asyncio.gather(
                vector_task, keyword_task, return_exceptions=True
            )

            # Handle exceptions from parallel execution
            vector_results_list: List[SearchResult] = []
            keyword_results_list: List[SearchResult] = []

            if isinstance(vector_results, Exception):
                self.logger.error(f"Vector search failed: {vector_results}")
                vector_results_list = []
            else:
                vector_results_list = cast(List[SearchResult], vector_results)

            if isinstance(keyword_results, Exception):
                self.logger.error(f"Keyword search failed: {keyword_results}")
                keyword_results_list = []
            else:
                keyword_results_list = cast(List[SearchResult], keyword_results)

            # Fusion using RRF
            fused_results = self._rrf_fusion(vector_results_list, keyword_results_list, alpha)

            # Apply post-fusion filters and limit
            final_results = self._post_process_results(fused_results, filters, limit)

            execution_time = (time.time() - start_time) * 1000  # ms

            self.logger.info(
                f"Hybrid search completed: query='{query[:50]}...', "
                f"vector={len(vector_results_list)}, keyword={len(keyword_results_list)}, "
                f"final={len(final_results)}, time={execution_time:.1f}ms"
            )

            return final_results

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.logger.error(
                f"Hybrid search failed: query='{query[:50]}...', "
                f"error={e}, time={execution_time:.1f}ms"
            )
            raise SearchEngineError(f"Hybrid search failed: {e}") from e

    async def vector_search(
        self, query: str, limit: Optional[int] = None, filters: Optional[SearchFilters] = None
    ) -> List[SearchResult]:
        """Perform pure vector similarity search.

        Args:
            query: Search query text
            limit: Maximum results to return
            filters: Optional search filters

        Returns:
            List of SearchResult ordered by similarity score
        """
        if limit is None:
            limit = self.default_limit

        return await self._vector_search(query, limit, filters)

    async def keyword_search(
        self, query: str, limit: Optional[int] = None, filters: Optional[SearchFilters] = None
    ) -> List[SearchResult]:
        """Perform pure keyword search using SQLite FTS5.

        Args:
            query: Search query text
            limit: Maximum results to return
            filters: Optional search filters

        Returns:
            List of SearchResult ordered by relevance score
        """
        if limit is None:
            limit = self.default_limit

        return await self._keyword_search(query, limit, filters)

    async def save_search_history(
        self,
        user_id: str,
        query: str,
        results_count: int,
        execution_time_ms: Optional[float] = None,
    ) -> None:
        """Save search to history.

        Args:
            user_id: Discord user ID
            query: Search query
            results_count: Number of results returned
            execution_time_ms: Execution time in milliseconds
        """
        try:
            history_id = str(uuid.uuid4())

            conn = await self.db.get_connection()
            await conn.execute(
                """
                INSERT INTO search_history
                (id, user_id, query, results_count, timestamp, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (history_id, user_id, query, results_count, datetime.now(), execution_time_ms),
            )
            await conn.commit()

        except Exception as e:
            self.logger.error(f"Failed to save search history: {e}")
            # Don't raise - history is not critical

    async def get_search_history(self, user_id: str, limit: int = 10) -> List[SearchHistory]:
        """Get search history for user.

        Args:
            user_id: Discord user ID
            limit: Maximum entries to return

        Returns:
            List of SearchHistory entries, most recent first
        """
        try:
            conn = await self.db.get_connection()
            cursor = await conn.execute(
                """
                SELECT id, user_id, query, results_count, timestamp, execution_time_ms
                FROM search_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = await cursor.fetchall()

            return [
                SearchHistory(
                    id=row[0],
                    user_id=row[1],
                    query=row[2],
                    results_count=row[3],
                    timestamp=row[4],
                    execution_time_ms=row[5],
                )
                for row in rows
            ]

        except Exception as e:
            self.logger.error(f"Failed to get search history: {e}")
            return []

    async def _vector_search(
        self, query: str, limit: int, filters: Optional[SearchFilters] = None
    ) -> List[SearchResult]:
        """Internal vector similarity search implementation."""
        try:
            # Generate query embedding
            embedding_result = await self.embeddings.generate_embedding(text=query)

            # Prepare ChromaDB query filters
            where_clause = {}
            if filters:
                if filters.user_id:
                    where_clause["user_id"] = filters.user_id
                if filters.content_type:
                    where_clause["content_type"] = filters.content_type
                if filters.tags:
                    # ChromaDB supports array contains
                    where_clause["tags"] = filters.tags[0]

            # Search in ChromaDB
            chroma_search_results = await self.chroma.search_documents(
                query_embedding=embedding_result.embedding,
                n_results=limit,
                where=where_clause if where_clause else None,
            )

            # Convert ChromaDB SearchResult to our SearchResult
            search_results = []
            for chroma_result in chroma_search_results:
                search_results.append(
                    SearchResult(
                        note_id=chroma_result.metadata.document_id or chroma_result.document_id,
                        title=chroma_result.metadata.title or "",
                        content=chroma_result.content,
                        score=chroma_result.score,
                        source="vector",
                        metadata=chroma_result.metadata.__dict__,
                        created_at=datetime.fromisoformat(
                            chroma_result.metadata.created_at or datetime.now().isoformat()
                        ),
                        relevance_reason=f"Vector similarity: {chroma_result.score:.3f}",
                    )
                )

            return search_results

        except Exception as e:
            self.logger.error(f"Vector search failed: {e}")
            return []

    async def _keyword_search(
        self, query: str, limit: int, filters: Optional[SearchFilters] = None
    ) -> List[SearchResult]:
        """Internal keyword search implementation using FTS5."""
        try:
            # Build FTS5 query
            fts_query = self._build_fts_query(query)

            # Build SQL query with filters (using FTS5 virtual table)
            sql_query = """
            SELECT
                kn.id, kn.title, kn.content, kn.tags, kn.created_at, kn.updated_at,
                kn.user_id, kn.content_type,
                bm25(knowledge_notes_fts) as score
            FROM knowledge_notes_fts
            JOIN knowledge_notes kn ON knowledge_notes_fts.rowid = kn.rowid
            WHERE knowledge_notes_fts MATCH ?
            """

            params = [fts_query]

            # Apply filters
            if filters:
                if filters.user_id:
                    sql_query += " AND kn.user_id = ?"
                    params.append(filters.user_id)
                if filters.content_type:
                    sql_query += " AND kn.content_type = ?"
                    params.append(filters.content_type)
                if filters.tags:
                    # Simple tag matching (can be improved)
                    tag_conditions = []
                    for tag in filters.tags:
                        tag_conditions.append("kn.tags LIKE ?")
                        params.append(f"%{tag}%")
                    if tag_conditions:
                        sql_query += f" AND ({' OR '.join(tag_conditions)})"

            sql_query += " ORDER BY score DESC LIMIT ?"
            params.append(str(limit))

            # Execute search
            conn = await self.db.get_connection()
            cursor = await conn.execute(sql_query, params)
            rows = await cursor.fetchall()

            # Convert to SearchResult
            search_results = []
            for row in rows:
                # Normalize BM25 score to 0.0-1.0 range
                # BM25 scores can vary widely, this is a simple normalization
                normalized_score = min(1.0, max(0.0, row[8] / 10.0))  # score is index 8

                # Parse tags
                tags = []
                if row[3]:  # tags is index 3
                    try:
                        if row[3].startswith("["):
                            import json

                            tags = json.loads(row[3])
                        else:
                            tags = [tag.strip() for tag in row[3].split(",")]
                    except Exception:
                        tags = []

                metadata = {
                    "note_id": row[0],  # id
                    "title": row[1],  # title
                    "tags": tags,
                    "user_id": row[6],  # user_id
                    "content_type": row[7],  # content_type
                    "created_at": row[4],  # created_at
                    "updated_at": row[5],  # updated_at
                }

                search_results.append(
                    SearchResult(
                        note_id=row[0],  # id
                        title=row[1],  # title
                        content=row[2],  # content
                        score=normalized_score,
                        source="keyword",
                        metadata=metadata,
                        created_at=datetime.fromisoformat(row[4]),  # created_at
                        relevance_reason=f"Keyword match: {normalized_score:.3f}",
                    )
                )

            return search_results

        except Exception as e:
            self.logger.error(f"Keyword search failed: {e}")
            return []

    def _build_fts_query(self, query: str) -> str:
        """Build FTS5 query string from user query."""
        # Simple FTS5 query building
        # Can be enhanced with phrase detection, boolean operators, etc.

        words = query.strip().split()
        if not words:
            return '""'

        # For now, use simple OR query
        # Future: detect phrases, handle quotes, operators
        fts_terms = []
        for word in words:
            # Escape special FTS5 characters
            word = word.replace('"', '""')
            fts_terms.append(f'"{word}"')

        return " OR ".join(fts_terms)

    def _rrf_fusion(
        self, vector_results: List[SearchResult], keyword_results: List[SearchResult], alpha: float
    ) -> List[SearchResult]:
        """Fuse vector and keyword results using RRF.

        RRF Score = α × (1/(rank_vector + k)) + (1-α) × (1/(rank_keyword + k))
        where k is the RRF constant (typically 60).
        """
        # Create rank maps
        vector_ranks = {result.note_id: rank for rank, result in enumerate(vector_results)}
        keyword_ranks = {result.note_id: rank for rank, result in enumerate(keyword_results)}

        # Get all unique note IDs
        all_note_ids = set(vector_ranks.keys()) | set(keyword_ranks.keys())

        # Create results map for easy lookup
        results_map = {}
        for result in vector_results:
            results_map[result.note_id] = result
        for result in keyword_results:
            results_map[result.note_id] = result

        # Calculate RRF scores
        fused_results = []
        for note_id in all_note_ids:
            vector_rank = vector_ranks.get(note_id, len(vector_results))
            keyword_rank = keyword_ranks.get(note_id, len(keyword_results))

            # RRF formula
            vector_score = 1.0 / (vector_rank + self.rrf_k)
            keyword_score = 1.0 / (keyword_rank + self.rrf_k)
            rrf_score = alpha * vector_score + (1 - alpha) * keyword_score

            # Get the result object (prefer vector over keyword for metadata)
            result = results_map[note_id]

            # Create new result with RRF score
            fused_result = SearchResult(
                note_id=result.note_id,
                title=result.title,
                content=result.content,
                score=rrf_score,
                source="hybrid",
                metadata=result.metadata,
                created_at=result.created_at,
                relevance_reason=f"RRF fusion: v_rank={vector_rank}, k_rank={keyword_rank}",
            )

            fused_results.append(fused_result)

        # Sort by RRF score descending
        fused_results.sort(key=lambda x: x.score, reverse=True)

        return fused_results

    def _post_process_results(
        self, results: List[SearchResult], filters: Optional[SearchFilters], limit: int
    ) -> List[SearchResult]:
        """Apply post-processing filters and limits."""
        processed_results = results

        # Apply score threshold
        if filters and filters.min_score:
            processed_results = [r for r in processed_results if r.score >= filters.min_score]

        # Apply date range filter
        if filters and filters.date_range:
            start_date, end_date = filters.date_range
            processed_results = [
                r for r in processed_results if start_date <= r.created_at <= end_date
            ]

        # Apply limit
        processed_results = processed_results[:limit]

        return processed_results
