from __future__ import annotations
from dip.Config.config import config
"""NetworkX adapter for theater contagion, actor graphs, and causal path scoring.

When networkx is installed, this provides graph-based contagion propagation
and centrality analysis for multi-theater assessments.
"""

import os
from typing import Any, Dict, List, Optional, Set, Tuple

# Optional import
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except Exception:
    NETWORKX_AVAILABLE = False

from .contracts import AssessmentGoal


class NetworkXContagionAdapter:
    """NetworkX-backed contagion and actor graph analysis."""

    def __init__(self):
        if not NETWORKX_AVAILABLE:
            raise RuntimeError("networkx not installed. Install with: pip install networkx")
        self.actor_graph = nx.DiGraph()
        self.theater_graph = nx.DiGraph()
        self._initialize_base_graphs()

    def _initialize_base_graphs(self) -> None:
        """Initialize base actor and theater graphs with known relationships."""
        # Major state actors
        actors = [
            "IND", "CHN", "PAK", "USA", "RUS", "GBR", "FRA", "DEU", "JPN", "AUS",
            "ISR", "IRN", "SAU", "TUR", "EGY", "ARE", "QAT", "KOR", "TWN", "SGP"
        ]
        for actor in actors:
            self.actor_graph.add_node(actor, type="state")

        # Theater definitions
        theaters = {
            "indo_pacific": ["IND", "CHN", "JPN", "AUS", "KOR", "TWN", "SGP"],
            "middle_east": ["ISR", "IRN", "SAU", "TUR", "EGY", "ARE", "QAT"],
            "europe": ["GBR", "FRA", "DEU", "RUS", "USA"],
            "south_asia": ["IND", "PAK", "CHN"],
        }
        for theater, members in theaters.items():
            self.theater_graph.add_node(theater, type="theater")
            for member in members:
                self.theater_graph.add_edge(theater, member, relationship="contains")

        # Known alliances and rivalries
        alliances = [
            ("USA", "JPN", "alliance"),
            ("USA", "KOR", "alliance"),
            ("USA", "AUS", "alliance"),
            ("USA", "GBR", "alliance"),
            ("USA", "FRA", "alliance"),
            ("USA", "DEU", "alliance"),
            ("IND", "USA", "strategic_partnership"),
            ("IND", "FRA", "strategic_partnership"),
            ("IND", "RUS", "defense_partnership"),
            ("CHN", "PAK", "alliance"),
            ("CHN", "RUS", "strategic_partnership"),
            ("ISR", "USA", "alliance"),
            ("SAU", "USA", "security_cooperation"),
        ]
        for a, b, rel in alliances:
            self.actor_graph.add_edge(a, b, relationship=rel, weight=0.8)
            self.actor_graph.add_edge(b, a, relationship=rel, weight=0.8)

        rivalries = [
            ("IND", "PAK", "rivalry"),
            ("IND", "CHN", "border_dispute"),
            ("CHN", "TWN", "sovereignty_dispute"),
            ("CHN", "JPN", "territorial_dispute"),
            ("ISR", "IRN", "proxy_conflict"),
            ("RUS", "USA", "strategic_competition"),
        ]
        for a, b, rel in rivalries:
            self.actor_graph.add_edge(a, b, relationship=rel, weight=-0.8)
            self.actor_graph.add_edge(b, a, relationship=rel, weight=-0.8)

    def compute_contagion(self, source_country: str, threat_score: float, 
                          max_hops: int = 2) -> Dict[str, float]:
        """Compute contagion spread from a source country."""
        if source_country not in self.actor_graph:
            return {}

        contagion = {source_country: threat_score}
        visited = {source_country}
        current_layer = {source_country}

        for hop in range(max_hops):
            next_layer = set()
            for node in current_layer:
                for neighbor in self.actor_graph.successors(node):
                    if neighbor in visited:
                        continue
                    edge_data = self.actor_graph.get_edge_data(node, neighbor)
                    weight = edge_data.get("weight", 0.1) if edge_data else 0.1
                    # Contagion decays with distance and relationship type
                    decay = 0.5 ** (hop + 1)
                    spread = threat_score * abs(weight) * decay
                    if spread > 0.05:  # Threshold
                        contagion[neighbor] = contagion.get(neighbor, 0) + spread
                        next_layer.add(neighbor)
            visited.update(next_layer)
            current_layer = next_layer

        # Cap at 1.0
        return {k: min(1.0, v) for k, v in contagion.items()}

    def get_centrality_scores(self) -> Dict[str, Dict[str, float]]:
        """Compute centrality metrics for all actors."""
        return {
            "betweenness": nx.betweenness_centrality(self.actor_graph),
            "eigenvector": nx.eigenvector_centrality_numpy(self.actor_graph, max_iter=1000),
            "pagerank": nx.pagerank(self.actor_graph),
            "degree": dict(self.actor_graph.degree()),
        }

    def find_causal_paths(self, source: str, target: str, max_length: int = 4) -> List[List[str]]:
        """Find causal paths between two actors."""
        if source not in self.actor_graph or target not in self.actor_graph:
            return []
        try:
            paths = list(nx.all_simple_paths(self.actor_graph, source, target, cutoff=max_length))
            return paths[:10]  # Limit results
        except nx.NetworkXNoPath:
            return []

    def get_theater_members(self, theater: str) -> List[str]:
        """Get member states of a theater."""
        if theater not in self.theater_graph:
            return []
        return list(self.theater_graph.successors(theater))

    def assess_theater_risk(self, theater: str, country_scores: Dict[str, float]) -> Dict[str, Any]:
        """Assess aggregate risk for a theater."""
        members = self.get_theater_members(theater)
        if not members:
            return {"theater": theater, "risk": 0.0, "members": []}

        scores = [country_scores.get(m, 0) for m in members]
        return {
            "theater": theater,
            "risk": max(scores) if scores else 0.0,
            "avg_risk": sum(scores) / len(scores) if scores else 0.0,
            "members": [{"country": m, "score": country_scores.get(m, 0)} for m in members],
        }


def create_networkx_adapter() -> Optional[NetworkXContagionAdapter]:
    """Factory to create NetworkX adapter if available."""
    if not NETWORKX_AVAILABLE:
        return None
    if not config.DIP_NETWORKX_ENABLED:
            return None
    return NetworkXContagionAdapter()