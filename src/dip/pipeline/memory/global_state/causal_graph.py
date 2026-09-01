"""
Causal Graph Engine (Layer 7)
=============================
Replaces the simple ABM contagion matrix with a strict NetworkX directed graph.
Finds causal paths (A -> B -> C) to calculate exact economic and military shockwaves.
"""

import networkx as nx
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("Layer7.causal_graph")

# Base relationships. In a real system, this is populated from the DB.
# Format: (Source, Target, Weight, EdgeType)
KNOWLEDGE_GRAPH_EDGES = [
    ("CHN", "TWN", 0.90, "MIL_THREAT"),
    ("CHN", "USA", 0.75, "TRADE_WAR"),
    ("TWN", "USA", 0.80, "TECH_SUPPLY"),
    ("TWN", "IND", 0.40, "TECH_SUPPLY"),
    ("USA", "IND", 0.60, "STRATEGIC_ALLIANCE"),
    ("CHN", "IND", 0.70, "BORDER_TENSION"),
    ("RUS", "UKR", 0.95, "KINETIC_WAR"),
    ("RUS", "EUR", 0.70, "ENERGY_SUPPLY"),
    ("USA", "EUR", 0.85, "NATO_ALLIANCE"),
    ("EUR", "UKR", 0.75, "FINANCIAL_AID"),
]

class CausalGraph:
    def __init__(self):
        self.G = nx.DiGraph()
        self._build_graph()
        
    def _build_graph(self):
        for src, tgt, weight, rel_type in KNOWLEDGE_GRAPH_EDGES:
            self.G.add_edge(src, tgt, weight=weight, type=rel_type)
            
    def calculate_spillover(self, initial_shocks: Dict[str, float], max_depth: int = 4) -> Dict[str, float]:
        """
        Uses BFS to traverse the knowledge graph up to max_depth and calculates
        spillover decay along the path.
        """
        final_spillovers = {}
        
        for source_node, initial_shock in initial_shocks.items():
            if source_node not in self.G:
                continue
                
            # Perform a BFS up to max_depth
            edges = nx.bfs_edges(self.G, source=source_node, depth_limit=max_depth)
            
            # Keep track of the 'current shock' value at each node in the tree
            node_shocks = {source_node: initial_shock}
            
            for u, v in edges:
                edge_data = self.G.get_edge_data(u, v)
                weight = edge_data.get("weight", 0.1)
                
                # Spillover physics: shock transfers but loses energy (decay factor 0.8)
                incoming_shock = node_shocks[u] * weight * 0.8
                
                # Accumulate shock at target node
                if v not in node_shocks:
                    node_shocks[v] = 0.0
                node_shocks[v] += incoming_shock
                
                # Add to total spillovers
                if v not in final_spillovers:
                    final_spillovers[v] = 0.0
                final_spillovers[v] = min(1.0, final_spillovers[v] + incoming_shock)
                
        return {k: round(v, 3) for k, v in final_spillovers.items() if v > 0.05}

    def get_causal_path(self, source: str, target: str) -> List[str]:
        """Finds the strongest causal path between two countries."""
        try:
            # shortest path by negative weight (since higher weight = stronger connection)
            # networkx doesn't do longest path easily, so we invert weights
            def inverted_weight(u, v, d):
                return 1.0 - d.get("weight", 0)
                
            path = nx.shortest_path(self.G, source, target, weight=inverted_weight)
            
            # Format nicely
            chain = []
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                rel = self.G[u][v]['type']
                chain.append(f"{u} -[{rel}]-> {v}")
            return chain
        except nx.NetworkXNoPath:
            return []
        except nx.NodeNotFound:
            return []
