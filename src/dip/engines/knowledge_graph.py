"""Lightweight strategic knowledge graph.

Uses NetworkX when available and degrades to a serializable edge list.  This is
the OpenCTI/STIX-inspired layer for actors, signals, evidence, and theaters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

try:
    import networkx as nx
except Exception:  # pragma: no cover - dependency may be optional in minimal envs
    nx = None


def _node_id(kind: str, value: str) -> str:
    return f"{kind}:{str(value or 'UNKNOWN').strip().upper()}"


class StrategicKnowledgeGraph:
    """Graph of countries, signals, assessments, and spillover relationships."""

    def __init__(self):
        self.graph = nx.DiGraph() if nx else None
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Tuple[str, str, Dict[str, Any]]] = []

    def add_node(self, node_id: str, **attrs: Any) -> None:
        self.nodes[node_id] = {**self.nodes.get(node_id, {}), **attrs}
        if self.graph is not None:
            self.graph.add_node(node_id, **attrs)

    def add_edge(self, source: str, target: str, **attrs: Any) -> None:
        self.edges.append((source, target, attrs))
        if self.graph is not None:
            self.graph.add_edge(source, target, **attrs)

    def ingest_assessment(self, country: str, state_context: Any, result: Dict[str, Any]) -> None:
        country_node = _node_id("country", country)
        self.add_node(country_node, kind="country", label=country)

        risk = str(result.get("threat_level") or "UNKNOWN")
        assessment_node = _node_id("assessment", result.get("trace_id") or f"{country}-{risk}")
        self.add_node(
            assessment_node,
            kind="assessment",
            risk_level=risk,
            confidence=float(result.get("verification_score", 0.0) or 0.0),
        )
        self.add_edge(country_node, assessment_node, relation="HAS_ASSESSMENT")

        for signal in list(getattr(state_context, "current_signals", []) or []):
            action = str(getattr(signal, "action", "") or "").upper()
            if not action:
                continue
            signal_node = _node_id("signal", action)
            confidence = float(getattr(signal, "confidence", 0.0) or 0.0)
            self.add_node(signal_node, kind="signal", label=action, confidence=confidence)
            self.add_edge(country_node, signal_node, relation="OBSERVED", confidence=confidence)
            self.add_edge(signal_node, assessment_node, relation="SUPPORTS", confidence=confidence)

        contagion = result.get("contagion") if isinstance(result.get("contagion"), dict) else {}
        for target, weight in contagion.items():
            target_node = _node_id("country", str(target))
            self.add_node(target_node, kind="country", label=str(target).upper())
            self.add_edge(country_node, target_node, relation="SPILLOVER_RISK", weight=float(weight or 0.0))

    def centrality(self) -> Dict[str, float]:
        if self.graph is None or not self.graph.nodes:
            return {node: 0.0 for node in self.nodes}
        return {node: round(score, 4) for node, score in nx.degree_centrality(self.graph).items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [{"id": node_id, **attrs} for node_id, attrs in self.nodes.items()],
            "edges": [
                {"source": source, "target": target, **attrs}
                for source, target, attrs in self.edges
            ],
            "centrality": self.centrality(),
        }
