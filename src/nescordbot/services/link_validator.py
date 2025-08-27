"""Link validation functionality for note connections."""

import json
import logging
from typing import Any, Dict, List, Optional

from .database import DatabaseService

logger = logging.getLogger(__name__)


class LinkValidationError(Exception):
    """Exception raised when link validation fails."""


class LinkValidationResult:
    """Result of link validation."""

    def __init__(self):
        self.broken_links: List[Dict[str, Any]] = []
        self.orphan_notes: List[Dict[str, Any]] = []
        self.circular_links: List[List[str]] = []
        self.duplicate_links: List[Dict[str, Any]] = []
        self.total_notes: int = 0
        self.total_links: int = 0
        self.validation_time: Optional[str] = None

    def is_healthy(self) -> bool:
        """Check if the link graph is healthy."""
        return (
            len(self.broken_links) == 0
            and len(self.circular_links) == 0
            and len(self.duplicate_links) == 0
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "broken_links": self.broken_links,
            "orphan_notes": self.orphan_notes,
            "circular_links": self.circular_links,
            "duplicate_links": self.duplicate_links,
            "total_notes": self.total_notes,
            "total_links": self.total_links,
            "is_healthy": self.is_healthy(),
            "validation_time": self.validation_time,
        }


class LinkValidator:
    """Validates note links and detects issues."""

    def __init__(self, db: DatabaseService):
        """
        Initialize LinkValidator.

        Args:
            db: Database service instance
        """
        self.db = db
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the link validator."""
        if not self._initialized:
            if not self.db.is_initialized:
                await self.db.initialize()
            self._initialized = True
            logger.info("LinkValidator initialized")

    async def validate_all_links(self) -> LinkValidationResult:
        """
        Validate all links in the knowledge base.

        Returns:
            Comprehensive validation results

        Raises:
            LinkValidationError: If validation fails
        """
        if not self._initialized:
            await self.initialize()

        result = LinkValidationResult()

        try:
            from datetime import datetime

            result.validation_time = datetime.now().isoformat()

            async with self.db.get_connection() as conn:
                # Get basic counts
                cursor = await conn.execute("SELECT COUNT(*) FROM knowledge_notes")
                result.total_notes = (await cursor.fetchone())[0]

                cursor = await conn.execute("SELECT COUNT(*) FROM note_links")
                result.total_links = (await cursor.fetchone())[0]

                # Find broken links
                result.broken_links = await self._find_broken_links(conn)

                # Find orphan notes
                result.orphan_notes = await self._find_orphan_notes(conn)

                # Find circular links
                result.circular_links = await self._find_circular_links(conn)

                # Find duplicate links
                result.duplicate_links = await self._find_duplicate_links(conn)

            logger.info(
                f"Link validation completed: {len(result.broken_links)} broken, "
                f"{len(result.orphan_notes)} orphans, "
                f"{len(result.circular_links)} circular, "
                f"{len(result.duplicate_links)} duplicates"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to validate links: {e}")
            raise LinkValidationError(f"Failed to validate links: {e}")

    async def validate_note_links(self, note_id: str) -> Dict[str, Any]:
        """
        Validate links for a specific note.

        Args:
            note_id: ID of the note to validate

        Returns:
            Validation results for the specific note
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Initialize variables early to avoid UnboundLocalError
            outgoing_rows = []
            incoming_rows = []

            async with self.db.get_connection() as conn:
                # Check if note exists
                cursor = await conn.execute(
                    "SELECT id, title FROM knowledge_notes WHERE id = ?", (note_id,)
                )
                note_row = await cursor.fetchone()

                if not note_row:
                    raise LinkValidationError(f"Note {note_id} not found")

                note_info = {"id": note_row[0], "title": note_row[1]}

                # Get outgoing links
                cursor = await conn.execute(
                    """
                    SELECT nl.id, nl.to_note_id, nl.link_type, kn.title
                    FROM note_links nl
                    LEFT JOIN knowledge_notes kn ON kn.id = nl.to_note_id
                    WHERE nl.from_note_id = ?
                    """,
                    (note_id,),
                )
                outgoing_rows = await cursor.fetchall()

                # Get incoming links
                cursor = await conn.execute(
                    """
                    SELECT nl.id, nl.from_note_id, nl.link_type, kn.title
                    FROM note_links nl
                    LEFT JOIN knowledge_notes kn ON kn.id = nl.from_note_id
                    WHERE nl.to_note_id = ?
                    """,
                    (note_id,),
                )
                incoming_rows = await cursor.fetchall()

            # Analyze links
            broken_outgoing = []
            valid_outgoing = []

            for row in outgoing_rows:
                link_data = {
                    "link_id": row[0],
                    "target_id": row[1],
                    "link_type": row[2],
                    "target_title": row[3],
                }

                if row[3] is None:  # Target note doesn't exist
                    broken_outgoing.append(link_data)
                else:
                    valid_outgoing.append(link_data)

            broken_incoming = []
            valid_incoming = []

            for row in incoming_rows:
                link_data = {
                    "link_id": row[0],
                    "source_id": row[1],
                    "link_type": row[2],
                    "source_title": row[3],
                }

                if row[3] is None:  # Source note doesn't exist
                    broken_incoming.append(link_data)
                else:
                    valid_incoming.append(link_data)

            return {
                "note": note_info,
                "outgoing_links": {
                    "valid": valid_outgoing,
                    "broken": broken_outgoing,
                    "count": len(valid_outgoing),
                },
                "incoming_links": {
                    "valid": valid_incoming,
                    "broken": broken_incoming,
                    "count": len(valid_incoming),
                },
                "is_orphan": len(valid_outgoing) == 0 and len(valid_incoming) == 0,
                "total_broken": len(broken_outgoing) + len(broken_incoming),
            }

        except Exception as e:
            logger.error(f"Failed to validate links for note {note_id}: {e}")
            raise LinkValidationError(f"Failed to validate note links: {e}")

    async def find_missing_bidirectional_links(self) -> List[Dict[str, Any]]:
        """
        Find links that should be bidirectional but aren't.

        Returns:
            List of missing reverse links
        """
        if not self._initialized:
            await self.initialize()

        try:
            async with self.db.get_connection() as conn:
                # Find one-way links that could be bidirectional
                cursor = await conn.execute(
                    """
                    SELECT DISTINCT
                        nl1.from_note_id, nl1.to_note_id,
                        kn1.title as from_title, kn2.title as to_title
                    FROM note_links nl1
                    JOIN knowledge_notes kn1 ON kn1.id = nl1.from_note_id
                    JOIN knowledge_notes kn2 ON kn2.id = nl1.to_note_id
                    WHERE NOT EXISTS (
                        SELECT 1 FROM note_links nl2
                        WHERE nl2.from_note_id = nl1.to_note_id
                        AND nl2.to_note_id = nl1.from_note_id
                    )
                    ORDER BY kn1.title, kn2.title
                    """
                )
                rows = await cursor.fetchall()

            missing_links = []
            for row in rows:
                missing_links.append(
                    {
                        "from_note_id": row[1],  # Reverse direction
                        "to_note_id": row[0],
                        "from_title": row[3],
                        "to_title": row[2],
                        "suggested_link_type": "reference",
                    }
                )

            return missing_links

        except Exception as e:
            logger.error(f"Failed to find missing bidirectional links: {e}")
            raise LinkValidationError(f"Failed to find missing links: {e}")

    async def _find_broken_links(self, conn) -> List[Dict[str, Any]]:
        """Find links pointing to non-existent notes."""
        cursor = await conn.execute(
            """
            SELECT nl.id, nl.from_note_id, nl.to_note_id, nl.link_type,
                   kn_from.title as from_title
            FROM note_links nl
            JOIN knowledge_notes kn_from ON kn_from.id = nl.from_note_id
            LEFT JOIN knowledge_notes kn_to ON kn_to.id = nl.to_note_id
            WHERE kn_to.id IS NULL
            """
        )
        rows = await cursor.fetchall()

        broken_links = []
        for row in rows:
            broken_links.append(
                {
                    "link_id": row[0],
                    "from_note_id": row[1],
                    "to_note_id": row[2],
                    "link_type": row[3],
                    "from_title": row[4],
                    "issue": "Target note not found",
                }
            )

        return broken_links

    async def _find_orphan_notes(self, conn) -> List[Dict[str, Any]]:
        """Find notes with no incoming or outgoing links."""
        cursor = await conn.execute(
            """
            SELECT kn.id, kn.title, kn.created_at, kn.tags
            FROM knowledge_notes kn
            WHERE kn.id NOT IN (
                SELECT DISTINCT from_note_id FROM note_links
                UNION
                SELECT DISTINCT to_note_id FROM note_links
            )
            ORDER BY kn.created_at DESC
            """
        )
        rows = await cursor.fetchall()

        orphan_notes = []
        for row in rows:
            try:
                tags = json.loads(row[3]) if row[3] else []
            except (json.JSONDecodeError, TypeError):
                tags = []

            orphan_notes.append(
                {"note_id": row[0], "title": row[1], "created_at": row[2], "tags": tags}
            )

        return orphan_notes

    async def _find_circular_links(self, conn) -> List[List[str]]:
        """Find circular link dependencies."""
        # Simple implementation: find direct circular links (A -> B -> A)
        cursor = await conn.execute(
            """
            SELECT DISTINCT nl1.from_note_id, nl1.to_note_id
            FROM note_links nl1
            JOIN note_links nl2 ON nl1.to_note_id = nl2.from_note_id
                                AND nl1.from_note_id = nl2.to_note_id
            WHERE nl1.from_note_id < nl1.to_note_id  -- Avoid duplicates
            """
        )
        rows = await cursor.fetchall()

        circular_links = []
        for row in rows:
            circular_links.append([row[0], row[1]])

        return circular_links

    async def _find_duplicate_links(self, conn) -> List[Dict[str, Any]]:
        """Find duplicate links between the same notes."""
        cursor = await conn.execute(
            """
            SELECT from_note_id, to_note_id, link_type, COUNT(*) as count
            FROM note_links
            GROUP BY from_note_id, to_note_id, link_type
            HAVING COUNT(*) > 1
            """
        )
        rows = await cursor.fetchall()

        duplicates = []
        for row in rows:
            duplicates.append(
                {
                    "from_note_id": row[0],
                    "to_note_id": row[1],
                    "link_type": row[2],
                    "duplicate_count": row[3],
                }
            )

        return duplicates

    async def repair_broken_links(self, validation_result: LinkValidationResult) -> Dict[str, int]:
        """
        Repair broken links by removing invalid entries.

        Args:
            validation_result: Result from validate_all_links()

        Returns:
            Count of repaired items
        """
        if not self._initialized:
            await self.initialize()

        repair_counts = {"broken_links_removed": 0, "duplicate_links_removed": 0}

        try:
            async with self.db.get_connection() as conn:
                # Remove broken links
                for broken_link in validation_result.broken_links:
                    await conn.execute(
                        "DELETE FROM note_links WHERE id = ?", (broken_link["link_id"],)
                    )
                    repair_counts["broken_links_removed"] += 1

                # Remove duplicate links (keep one of each)
                for duplicate in validation_result.duplicate_links:
                    # Keep the oldest duplicate, remove others
                    cursor = await conn.execute(
                        """
                        SELECT id FROM note_links
                        WHERE from_note_id = ? AND to_note_id = ? AND link_type = ?
                        ORDER BY created_at
                        """,
                        (
                            duplicate["from_note_id"],
                            duplicate["to_note_id"],
                            duplicate["link_type"],
                        ),
                    )
                    link_ids = [row[0] for row in await cursor.fetchall()]

                    # Remove all but the first (oldest)
                    for link_id in link_ids[1:]:
                        await conn.execute("DELETE FROM note_links WHERE id = ?", (link_id,))
                        repair_counts["duplicate_links_removed"] += 1

                await conn.commit()

            logger.info(f"Link repair completed: {repair_counts}")
            return repair_counts

        except Exception as e:
            logger.error(f"Failed to repair links: {e}")
            raise LinkValidationError(f"Failed to repair links: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the link validator.

        Returns:
            Health status information
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Perform a quick validation
            validation_result = await self.validate_all_links()

            return {
                "status": "healthy" if validation_result.is_healthy() else "issues_found",
                "initialized": self._initialized,
                "database_connected": self.db.is_initialized,
                "summary": {
                    "total_notes": validation_result.total_notes,
                    "total_links": validation_result.total_links,
                    "broken_links": len(validation_result.broken_links),
                    "orphan_notes": len(validation_result.orphan_notes),
                    "circular_links": len(validation_result.circular_links),
                    "duplicate_links": len(validation_result.duplicate_links),
                },
            }
        except Exception as e:
            logger.error(f"LinkValidator health check failed: {e}")
            return {"status": "unhealthy", "error": str(e), "initialized": self._initialized}
