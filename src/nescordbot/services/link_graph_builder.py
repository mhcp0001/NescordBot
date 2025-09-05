"""Link graph building and analysis functionality for note networks."""

import logging
from typing import Any, Dict, List, Optional

import networkx as nx

from .database import DatabaseService

logger = logging.getLogger(__name__)


class LinkGraphError(Exception):
    """Exception raised when link graph operations fail."""


class LinkCluster:
    """Represents a cluster of related notes."""

    def __init__(self, cluster_id: str, notes: List[str], centrality_scores: Dict[str, float]):
        self.cluster_id = cluster_id
        self.notes = notes
        self.centrality_scores = centrality_scores
        self.size = len(notes)
        self.density = 0.0
        self.representative_note = ""

        # Find representative note (highest centrality)
        if centrality_scores:
            self.representative_note = max(centrality_scores.items(), key=lambda x: x[1])[0]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "cluster_id": self.cluster_id,
            "notes": self.notes,
            "size": self.size,
            "density": self.density,
            "representative_note": self.representative_note,
            "centrality_scores": self.centrality_scores,
        }


class LinkGraphBuilder:
    """Builds and analyzes link graphs from note connections."""

    def __init__(self, db: DatabaseService):
        """
        Initialize LinkGraphBuilder.

        Args:
            db: Database service instance
        """
        self.db = db
        self._initialized = False
        self.graph: Optional[nx.DiGraph] = None

    async def initialize(self) -> None:
        """Initialize the link graph builder."""
        if not self._initialized:
            if not self.db.is_initialized:
                await self.db.initialize()
            self._initialized = True
            logger.info("LinkGraphBuilder initialized")

    async def build_graph(self, include_orphans: bool = False) -> nx.DiGraph:
        """
        Build a directed graph from note links.

        Args:
            include_orphans: Whether to include notes without links

        Returns:
            NetworkX directed graph

        Raises:
            LinkGraphError: If graph building fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            self.graph = nx.DiGraph()

            async with self.db.get_connection() as conn:
                # Add all notes as nodes
                cursor = await conn.execute("SELECT id, title, tags FROM knowledge_notes")
                note_rows = await cursor.fetchall()

                for row in note_rows:
                    self.graph.add_node(row[0], title=row[1], tags=row[2])

                # Add edges from links
                cursor = await conn.execute(
                    """
                    SELECT nl.from_note_id, nl.to_note_id, nl.link_type
                    FROM note_links nl
                    JOIN knowledge_notes kn1 ON kn1.id = nl.from_note_id
                    JOIN knowledge_notes kn2 ON kn2.id = nl.to_note_id
                    """
                )
                link_rows = await cursor.fetchall()

                for row in link_rows:
                    self.graph.add_edge(row[0], row[1], link_type=row[2])

            # Remove orphan nodes if requested
            if not include_orphans:
                orphan_nodes = [node for node in self.graph.nodes() if self.graph.degree(node) == 0]
                self.graph.remove_nodes_from(orphan_nodes)

            logger.info(
                f"Built graph with {self.graph.number_of_nodes()} nodes "
                f"and {self.graph.number_of_edges()} edges"
            )

            return self.graph

        except Exception as e:
            logger.error(f"Failed to build link graph: {e}")
            raise LinkGraphError(f"Failed to build graph: {e}")

    async def find_clusters(self, min_cluster_size: int = 3) -> List[LinkCluster]:
        """
        Find clusters of highly connected notes.

        Args:
            min_cluster_size: Minimum number of notes in a cluster

        Returns:
            List of identified clusters
        """
        if self.graph is None:
            await self.build_graph()

        assert self.graph is not None, "Graph should be initialized after build_graph()"

        try:
            # Convert to undirected for clustering
            undirected = self.graph.to_undirected()

            # Find connected components
            components = list(nx.connected_components(undirected))

            clusters = []
            for i, component in enumerate(components):
                if len(component) >= min_cluster_size:
                    # Create subgraph for this component
                    subgraph = undirected.subgraph(component)

                    # Calculate centrality scores
                    centrality = nx.betweenness_centrality(subgraph)

                    # Calculate density
                    density = nx.density(subgraph)

                    # Create cluster
                    cluster = LinkCluster(
                        cluster_id=f"cluster_{i}",
                        notes=list(component),
                        centrality_scores=centrality,
                    )
                    cluster.density = density

                    clusters.append(cluster)

            # Sort by size descending
            clusters.sort(key=lambda x: x.size, reverse=True)

            logger.info(f"Found {len(clusters)} clusters with min size {min_cluster_size}")
            return clusters

        except Exception as e:
            logger.error(f"Failed to find clusters: {e}")
            raise LinkGraphError(f"Failed to find clusters: {e}")

    async def find_central_notes(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Find the most central/important notes in the graph.

        Args:
            top_n: Number of top central notes to return

        Returns:
            List of notes with centrality scores
        """
        if self.graph is None:
            await self.build_graph()

        assert self.graph is not None, "Graph should be initialized after build_graph()"

        try:
            # Calculate various centrality measures
            pagerank = nx.pagerank(self.graph)
            betweenness = nx.betweenness_centrality(self.graph)
            closeness = nx.closeness_centrality(self.graph)
            in_degree = dict(self.graph.in_degree())
            out_degree = dict(self.graph.out_degree())

            # Combine scores (weighted average)
            combined_scores = {}
            for node in self.graph.nodes():
                combined_scores[node] = (
                    pagerank.get(node, 0) * 0.3
                    + betweenness.get(node, 0) * 0.2
                    + closeness.get(node, 0) * 0.2
                    + (in_degree.get(node, 0) / max(1, max(in_degree.values()))) * 0.15
                    + (out_degree.get(node, 0) / max(1, max(out_degree.values()))) * 0.15
                )

            # Get top nodes
            top_nodes = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

            # Get node details
            central_notes = []
            async with self.db.get_connection() as conn:
                for node_id, score in top_nodes:
                    cursor = await conn.execute(
                        "SELECT id, title FROM knowledge_notes WHERE id = ?", (node_id,)
                    )
                    row = await cursor.fetchone()

                    if row:
                        central_notes.append(
                            {
                                "note_id": row[0],
                                "title": row[1],
                                "centrality_score": score,
                                "pagerank": pagerank.get(node_id, 0),
                                "betweenness": betweenness.get(node_id, 0),
                                "closeness": closeness.get(node_id, 0),
                                "in_degree": in_degree.get(node_id, 0),
                                "out_degree": out_degree.get(node_id, 0),
                            }
                        )

            return central_notes

        except Exception as e:
            logger.error(f"Failed to find central notes: {e}")
            raise LinkGraphError(f"Failed to find central notes: {e}")

    async def find_shortest_path(self, from_note_id: str, to_note_id: str) -> Optional[List[str]]:
        """
        Find shortest path between two notes.

        Args:
            from_note_id: Starting note ID
            to_note_id: Target note ID

        Returns:
            List of note IDs in the shortest path, or None if no path exists
        """
        if self.graph is None:
            await self.build_graph()

        assert self.graph is not None, "Graph should be initialized after build_graph()"

        try:
            if from_note_id not in self.graph or to_note_id not in self.graph:
                return None

            # Try finding path in directed graph
            try:
                path = nx.shortest_path(self.graph, from_note_id, to_note_id)
                return list(path)
            except nx.NetworkXNoPath:
                # Try in undirected graph
                undirected = self.graph.to_undirected()
                try:
                    path = nx.shortest_path(undirected, from_note_id, to_note_id)
                    return list(path)
                except nx.NetworkXNoPath:
                    return None

        except Exception as e:
            logger.error(f"Failed to find shortest path: {e}")
            return None

    async def get_graph_metrics(self) -> Dict[str, Any]:
        """
        Get overall graph metrics and statistics.

        Returns:
            Dictionary with graph metrics
        """
        if self.graph is None:
            await self.build_graph()

        assert self.graph is not None, "Graph should be initialized after build_graph()"

        try:
            # Basic metrics
            num_nodes = self.graph.number_of_nodes()
            num_edges = self.graph.number_of_edges()

            # Density
            density = nx.density(self.graph)

            # Connected components
            undirected = self.graph.to_undirected()
            num_components = nx.number_connected_components(undirected)
            largest_component_size = len(
                max(nx.connected_components(undirected), key=len, default=[])
            )

            # Average clustering coefficient
            try:
                clustering = nx.average_clustering(undirected) if num_nodes > 0 else 0.0
            except ZeroDivisionError:
                clustering = 0.0

            # Average path length (for largest component)
            try:
                if num_components > 0:
                    largest_component = undirected.subgraph(
                        max(nx.connected_components(undirected), key=len, default=[])
                    )
                    if largest_component.number_of_nodes() > 1:
                        avg_path_length = nx.average_shortest_path_length(largest_component)
                    else:
                        avg_path_length = 0.0
                else:
                    avg_path_length = 0.0
            except (nx.NetworkXError, ValueError, ZeroDivisionError):
                avg_path_length = 0.0

            # Degree statistics
            degrees = [d for n, d in self.graph.degree()]
            avg_degree = sum(degrees) / len(degrees) if degrees else 0
            max_degree = max(degrees) if degrees else 0

            # In/out degree statistics for directed graph
            in_degrees = [d for n, d in self.graph.in_degree()]
            out_degrees = [d for n, d in self.graph.out_degree()]
            avg_in_degree = sum(in_degrees) / len(in_degrees) if in_degrees else 0
            avg_out_degree = sum(out_degrees) / len(out_degrees) if out_degrees else 0

            return {
                "nodes": num_nodes,
                "edges": num_edges,
                "density": density,
                "connected_components": num_components,
                "largest_component_size": largest_component_size,
                "average_clustering": clustering,
                "average_path_length": avg_path_length,
                "average_degree": avg_degree,
                "max_degree": max_degree,
                "average_in_degree": avg_in_degree,
                "average_out_degree": avg_out_degree,
            }

        except Exception as e:
            logger.error(f"Failed to calculate graph metrics: {e}")
            raise LinkGraphError(f"Failed to calculate metrics: {e}")

    async def suggest_bridge_notes(
        self, cluster1_id: str, cluster2_id: str, clusters: List[LinkCluster]
    ) -> List[Dict[str, Any]]:
        """
        Suggest notes that could bridge two clusters.

        Args:
            cluster1_id: First cluster ID
            cluster2_id: Second cluster ID
            clusters: List of all clusters

        Returns:
            List of potential bridge notes
        """
        if self.graph is None:
            await self.build_graph()

        assert self.graph is not None, "Graph should be initialized after build_graph()"

        try:
            # Find the specified clusters
            cluster1 = next((c for c in clusters if c.cluster_id == cluster1_id), None)
            cluster2 = next((c for c in clusters if c.cluster_id == cluster2_id), None)

            if not cluster1 or not cluster2:
                return []

            bridge_candidates = []

            # Find nodes that have connections to both clusters
            for node in self.graph.nodes():
                if node in cluster1.notes or node in cluster2.notes:
                    continue

                # Check connections to both clusters
                cluster1_connections = sum(
                    1 for neighbor in self.graph.neighbors(node) if neighbor in cluster1.notes
                )
                cluster2_connections = sum(
                    1 for neighbor in self.graph.neighbors(node) if neighbor in cluster2.notes
                )

                if cluster1_connections > 0 and cluster2_connections > 0:
                    # Get note details
                    node_attrs = self.graph.nodes[node]
                    bridge_candidates.append(
                        {
                            "note_id": node,
                            "title": node_attrs.get("title", ""),
                            "cluster1_connections": cluster1_connections,
                            "cluster2_connections": cluster2_connections,
                            "bridge_strength": cluster1_connections + cluster2_connections,
                        }
                    )

            # Sort by bridge strength
            bridge_candidates.sort(key=lambda x: x["bridge_strength"], reverse=True)

            return bridge_candidates[:10]  # Return top 10

        except Exception as e:
            logger.error(f"Failed to suggest bridge notes: {e}")
            raise LinkGraphError(f"Failed to suggest bridge notes: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the link graph builder.

        Returns:
            Health status information
        """
        try:
            if not self._initialized:
                await self.initialize()

            # Build a test graph
            test_graph = await self.build_graph(include_orphans=True)

            return {
                "status": "healthy",
                "initialized": self._initialized,
                "database_connected": self.db.is_initialized,
                "graph_nodes": test_graph.number_of_nodes(),
                "graph_edges": test_graph.number_of_edges(),
            }
        except Exception as e:
            logger.error(f"LinkGraphBuilder health check failed: {e}")
            return {"status": "unhealthy", "error": str(e), "initialized": self._initialized}
