"""Tests for LinkGraphBuilder class."""

from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest

from nescordbot.services.database import DatabaseService
from nescordbot.services.link_graph_builder import LinkCluster, LinkGraphBuilder, LinkGraphError


@pytest.fixture
async def mock_db():
    """Create a mock database service."""
    db = MagicMock(spec=DatabaseService)
    db.is_initialized = True

    # Mock connection context manager
    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()

    db.get_connection = MagicMock()
    db.get_connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    db.get_connection.return_value.__aexit__ = AsyncMock()

    return db, mock_conn, mock_cursor


@pytest.fixture
async def link_graph_builder(mock_db):
    """Create a LinkGraphBuilder instance with mocked dependencies."""
    db, _, _ = mock_db
    builder = LinkGraphBuilder(db)
    await builder.initialize()
    return builder, mock_db


class TestLinkCluster:
    """Test cases for LinkCluster."""

    def test_initialization(self):
        """Test proper initialization of LinkCluster."""
        centrality_scores = {"note-1": 0.8, "note-2": 0.6, "note-3": 0.4}
        notes = ["note-1", "note-2", "note-3"]

        cluster = LinkCluster("cluster-1", notes, centrality_scores)

        assert cluster.cluster_id == "cluster-1"
        assert cluster.notes == notes
        assert cluster.size == 3
        assert cluster.centrality_scores == centrality_scores
        assert cluster.representative_note == "note-1"  # Highest centrality
        assert cluster.density == 0.0  # Default value

    def test_to_dict(self):
        """Test conversion to dictionary."""
        centrality_scores = {"note-1": 0.8, "note-2": 0.6}
        notes = ["note-1", "note-2"]

        cluster = LinkCluster("cluster-1", notes, centrality_scores)
        cluster.density = 0.75

        dict_result = cluster.to_dict()

        assert dict_result["cluster_id"] == "cluster-1"
        assert dict_result["notes"] == notes
        assert dict_result["size"] == 2
        assert dict_result["density"] == 0.75
        assert dict_result["representative_note"] == "note-1"
        assert dict_result["centrality_scores"] == centrality_scores


class TestLinkGraphBuilder:
    """Test cases for LinkGraphBuilder."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_db):
        """Test proper initialization."""
        db, _, _ = mock_db
        builder = LinkGraphBuilder(db)

        # Should not be initialized initially
        assert not builder._initialized
        assert builder.graph is None

        # Initialize
        await builder.initialize()

        # Should be initialized now
        assert builder._initialized

    @pytest.mark.asyncio
    async def test_build_graph_success(self, link_graph_builder):
        """Test successful graph building."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Mock nodes (notes)
        note_rows = [
            ("note-1", "Note 1", '["tag1"]'),
            ("note-2", "Note 2", '["tag2"]'),
            ("note-3", "Note 3", '["tag3"]'),
        ]

        # Mock edges (links)
        link_rows = [("note-1", "note-2", "reference"), ("note-2", "note-3", "mention")]

        mock_cursor.fetchall.side_effect = [note_rows, link_rows]

        graph = await builder.build_graph(include_orphans=True)

        assert isinstance(graph, nx.DiGraph)
        assert graph.number_of_nodes() == 3
        assert graph.number_of_edges() == 2
        assert graph.has_edge("note-1", "note-2")
        assert graph.has_edge("note-2", "note-3")

    @pytest.mark.asyncio
    async def test_build_graph_exclude_orphans(self, link_graph_builder):
        """Test graph building with orphan exclusion."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Mock nodes including orphan
        note_rows = [
            ("note-1", "Note 1", '["tag1"]'),
            ("note-2", "Note 2", '["tag2"]'),
            ("orphan", "Orphan Note", '["orphan"]'),
        ]

        # Mock edges (orphan has no connections)
        link_rows = [("note-1", "note-2", "reference")]

        mock_cursor.fetchall.side_effect = [note_rows, link_rows]

        graph = await builder.build_graph(include_orphans=False)

        assert graph.number_of_nodes() == 2  # Orphan excluded
        assert graph.number_of_edges() == 1
        assert not graph.has_node("orphan")

    @pytest.mark.asyncio
    async def test_find_clusters(self, link_graph_builder):
        """Test cluster finding."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create a mock graph with clusters
        builder.graph = nx.DiGraph()

        # Cluster 1: nodes 1-3
        builder.graph.add_edges_from(
            [("note-1", "note-2"), ("note-2", "note-3"), ("note-3", "note-1")]
        )

        # Cluster 2: nodes 4-6
        builder.graph.add_edges_from([("note-4", "note-5"), ("note-5", "note-6")])

        # Single node (too small for cluster)
        builder.graph.add_node("note-7")

        clusters = await builder.find_clusters(min_cluster_size=3)

        assert len(clusters) == 1  # Only cluster 1 meets min size
        assert clusters[0].size == 3
        assert set(clusters[0].notes) == {"note-1", "note-2", "note-3"}

    @pytest.mark.asyncio
    async def test_find_central_notes(self, link_graph_builder):
        """Test finding central notes."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create a mock graph
        builder.graph = nx.DiGraph()
        builder.graph.add_edges_from(
            [
                ("central", "note-1"),
                ("central", "note-2"),
                ("central", "note-3"),
                ("note-1", "central"),
                ("note-2", "central"),
            ]
        )

        # Mock database queries for note details
        note_details = [("central", "Central Note"), ("note-1", "Note 1"), ("note-2", "Note 2")]

        mock_cursor.fetchone.side_effect = note_details

        central_notes = await builder.find_central_notes(top_n=3)

        assert len(central_notes) <= 3
        assert central_notes[0]["note_id"] == "central"  # Should be most central
        assert "centrality_score" in central_notes[0]
        assert "pagerank" in central_notes[0]
        assert "betweenness" in central_notes[0]

    @pytest.mark.asyncio
    async def test_find_shortest_path_exists(self, link_graph_builder):
        """Test finding shortest path when path exists."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create a simple path graph
        builder.graph = nx.DiGraph()
        builder.graph.add_edges_from([("start", "middle"), ("middle", "end")])

        path = await builder.find_shortest_path("start", "end")

        assert path == ["start", "middle", "end"]

    @pytest.mark.asyncio
    async def test_find_shortest_path_no_path(self, link_graph_builder):
        """Test finding shortest path when no path exists."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create disconnected nodes
        builder.graph = nx.DiGraph()
        builder.graph.add_node("isolated-1")
        builder.graph.add_node("isolated-2")

        path = await builder.find_shortest_path("isolated-1", "isolated-2")

        assert path is None

    @pytest.mark.asyncio
    async def test_find_shortest_path_undirected_fallback(self, link_graph_builder):
        """Test shortest path with undirected fallback."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create nodes connected only in reverse direction
        builder.graph = nx.DiGraph()
        builder.graph.add_edge("end", "start")  # Only reverse connection

        path = await builder.find_shortest_path("start", "end")

        # Should find path in undirected version
        assert path is not None
        assert len(path) == 2

    @pytest.mark.asyncio
    async def test_find_shortest_path_nonexistent_nodes(self, link_graph_builder):
        """Test shortest path with nonexistent nodes."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        builder.graph = nx.DiGraph()
        builder.graph.add_node("existing")

        path = await builder.find_shortest_path("nonexistent", "existing")

        assert path is None

    @pytest.mark.asyncio
    async def test_get_graph_metrics(self, link_graph_builder):
        """Test graph metrics calculation."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create a simple connected graph
        builder.graph = nx.DiGraph()
        builder.graph.add_edges_from(
            [("node-1", "node-2"), ("node-2", "node-3"), ("node-3", "node-1")]
        )

        metrics = await builder.get_graph_metrics()

        assert metrics["nodes"] == 3
        assert metrics["edges"] == 3
        assert "density" in metrics
        assert "connected_components" in metrics
        assert "average_clustering" in metrics
        assert "average_degree" in metrics
        assert "average_in_degree" in metrics
        assert "average_out_degree" in metrics

    @pytest.mark.asyncio
    async def test_suggest_bridge_notes(self, link_graph_builder):
        """Test bridge note suggestions."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create graph with two clusters and a bridge
        builder.graph = nx.DiGraph()

        # Cluster 1
        cluster1_nodes = ["c1-node1", "c1-node2"]
        builder.graph.add_edge("c1-node1", "c1-node2")

        # Cluster 2
        cluster2_nodes = ["c2-node1", "c2-node2"]
        builder.graph.add_edge("c2-node1", "c2-node2")

        # Bridge node
        builder.graph.add_edges_from([("bridge", "c1-node1"), ("bridge", "c2-node1")])
        builder.graph.nodes["bridge"]["title"] = "Bridge Note"

        # Create clusters
        cluster1 = LinkCluster("cluster-1", cluster1_nodes, {})
        cluster2 = LinkCluster("cluster-2", cluster2_nodes, {})
        clusters = [cluster1, cluster2]

        bridge_candidates = await builder.suggest_bridge_notes("cluster-1", "cluster-2", clusters)

        assert len(bridge_candidates) == 1
        assert bridge_candidates[0]["note_id"] == "bridge"
        assert bridge_candidates[0]["cluster1_connections"] == 1
        assert bridge_candidates[0]["cluster2_connections"] == 1

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, link_graph_builder):
        """Test health check when builder is healthy."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Mock successful graph building
        builder.build_graph = AsyncMock()
        mock_graph = nx.DiGraph()
        mock_graph.add_nodes_from(["node-1", "node-2"])
        mock_graph.add_edge("node-1", "node-2")
        builder.build_graph.return_value = mock_graph

        health = await builder.health_check()

        assert health["status"] == "healthy"
        assert health["initialized"] is True
        assert health["graph_nodes"] == 2
        assert health["graph_edges"] == 1

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, mock_db):
        """Test health check when builder has issues."""
        db, mock_conn, mock_cursor = mock_db

        # Create uninitialized builder
        builder = LinkGraphBuilder(db)

        # Mock build_graph error
        builder.build_graph = AsyncMock(side_effect=Exception("Build error"))

        health = await builder.health_check()

        assert health["status"] == "unhealthy"
        assert "error" in health
        assert health["initialized"] is False

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_db):
        """Test error handling in various scenarios."""
        db, mock_conn, mock_cursor = mock_db

        # Test database connection error
        db.get_connection.side_effect = Exception("Connection error")

        builder = LinkGraphBuilder(db)
        await builder.initialize()

        with pytest.raises(LinkGraphError):
            await builder.build_graph()

    @pytest.mark.asyncio
    async def test_graph_rebuild_on_methods(self, link_graph_builder):
        """Test that graph is rebuilt when needed."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Mock graph building
        builder.build_graph = AsyncMock()
        mock_graph = nx.DiGraph()
        mock_graph.add_node("test")
        builder.build_graph.return_value = mock_graph

        # Call method that requires graph
        await builder.find_clusters()

        # Should have called build_graph
        builder.build_graph.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_graph_handling(self, link_graph_builder):
        """Test handling of empty graphs."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Mock empty graph
        mock_cursor.fetchall.side_effect = [[], []]  # No nodes, no edges

        graph = await builder.build_graph()

        assert graph.number_of_nodes() == 0
        assert graph.number_of_edges() == 0

        # Test metrics with empty graph
        metrics = await builder.get_graph_metrics()
        assert metrics["nodes"] == 0
        assert metrics["edges"] == 0

    @pytest.mark.asyncio
    async def test_large_graph_performance(self, link_graph_builder):
        """Test performance considerations with larger graphs."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create a larger mock graph
        builder.graph = nx.DiGraph()

        # Add many nodes and edges
        nodes = [f"node-{i}" for i in range(50)]
        edges = [(f"node-{i}", f"node-{(i+1)%50}") for i in range(50)]

        builder.graph.add_nodes_from(nodes)
        builder.graph.add_edges_from(edges)

        # Mock database responses for central notes
        mock_cursor.fetchone.side_effect = [(f"node-{i}", f"Note {i}") for i in range(10)]

        # Test that centrality calculation works
        central_notes = await builder.find_central_notes(top_n=10)

        assert len(central_notes) <= 10

        # Test metrics calculation
        metrics = await builder.get_graph_metrics()

        assert metrics["nodes"] == 50
        assert metrics["edges"] == 50

    @pytest.mark.asyncio
    async def test_cluster_density_calculation(self, link_graph_builder):
        """Test cluster density calculation."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        # Create a graph with known density
        builder.graph = nx.DiGraph()

        # Complete triangle (maximum density for 3 nodes)
        builder.graph.add_edges_from(
            [
                ("a", "b"),
                ("b", "c"),
                ("c", "a"),
                ("a", "c"),
                ("b", "a"),
                ("c", "b"),  # All possible connections
            ]
        )

        clusters = await builder.find_clusters(min_cluster_size=3)

        assert len(clusters) == 1
        assert clusters[0].size == 3
        # For undirected graph of complete triangle, density should be 1.0
        assert abs(clusters[0].density - 1.0) < 0.01

    @pytest.mark.asyncio
    async def test_bridge_notes_invalid_clusters(self, link_graph_builder):
        """Test bridge note suggestions with invalid cluster IDs."""
        builder, (db, mock_conn, mock_cursor) = link_graph_builder

        builder.graph = nx.DiGraph()
        clusters: List[LinkCluster] = []

        bridge_candidates = await builder.suggest_bridge_notes(
            "nonexistent-1", "nonexistent-2", clusters
        )

        assert bridge_candidates == []
