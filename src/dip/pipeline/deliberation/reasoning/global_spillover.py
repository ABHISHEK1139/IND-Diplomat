"""
Phase 14: Global / Cross-Theater Spillover Model.

Models how a crisis in one theater spills over to other theaters.

Example:
  Taiwan escalation -> US-China relations -> Japan/Korea
       -> Semiconductors -> Global trade -> European security

Uses a weighted directed graph where edges represent causal influence
and nodes represent theaters/domains.
"""

import logging
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("Layer9.GlobalModel")


class TheaterNode(BaseModel):
    """A geopolitical theater or domain."""
    name: str
    current_tension: float = 0.0  # 0-1
    description: str = ""


class SpilloverEdge(BaseModel):
    """A causal influence edge between theaters."""
    source: str
    target: str
    weight: float  # 0-1, strength of causal link
    mechanism: str = ""  # How the spillover works


class SpilloverResult(BaseModel):
    """Result of a spillover simulation."""
    source_theater: str
    source_tension: float
    affected_theaters: Dict[str, float]  # theater -> new tension
    propagation_chain: List[str]


class GlobalSpilloverModel:
    """
    Directed graph model for cross-theater contagion analysis.
    """

    def __init__(self):
        self.theaters: Dict[str, TheaterNode] = {}
        self.edges: List[SpilloverEdge] = []
        self._init_default_graph()

    def _init_default_graph(self):
        """Initialize with the standard geopolitical theater graph."""
        # Theaters
        theaters = [
            TheaterNode(name="Taiwan_Strait", description="US-China military confrontation zone"),
            TheaterNode(name="US_China_Relations", description="Bilateral strategic competition"),
            TheaterNode(name="Indo_Pacific", description="Japan, Korea, ASEAN, Australia"),
            TheaterNode(name="Semiconductors", description="Global chip supply chain"),
            TheaterNode(name="Global_Trade", description="International commerce and finance"),
            TheaterNode(name="European_Security", description="NATO, Russia, Ukraine"),
            TheaterNode(name="Middle_East", description="Gulf, Iran, Israel-Palestine"),
            TheaterNode(name="South_Asia", description="India-Pakistan, India-China LAC"),
            TheaterNode(name="Energy_Markets", description="Oil, gas, renewables"),
            TheaterNode(name="Cyber_Domain", description="State-sponsored cyber operations"),
        ]
        for t in theaters:
            self.theaters[t.name] = t

        # Edges (causal influence)
        edges = [
            SpilloverEdge(source="Taiwan_Strait", target="US_China_Relations", weight=0.9,
                          mechanism="Direct military confrontation escalates bilateral tensions"),
            SpilloverEdge(source="Taiwan_Strait", target="Semiconductors", weight=0.85,
                          mechanism="TSMC production at risk, chip supply disruption"),
            SpilloverEdge(source="US_China_Relations", target="Indo_Pacific", weight=0.75,
                          mechanism="Alliance activation, Japan/Korea drawn in"),
            SpilloverEdge(source="US_China_Relations", target="Global_Trade", weight=0.70,
                          mechanism="Trade decoupling, sanctions, tariffs"),
            SpilloverEdge(source="Semiconductors", target="Global_Trade", weight=0.65,
                          mechanism="Tech supply chain disruption cascades"),
            SpilloverEdge(source="Global_Trade", target="European_Security", weight=0.40,
                          mechanism="Economic pressure shifts NATO priorities"),
            SpilloverEdge(source="Middle_East", target="Energy_Markets", weight=0.80,
                          mechanism="Oil supply disruption, price spikes"),
            SpilloverEdge(source="Energy_Markets", target="Global_Trade", weight=0.60,
                          mechanism="Energy cost inflation"),
            SpilloverEdge(source="South_Asia", target="Indo_Pacific", weight=0.50,
                          mechanism="Regional instability draws US attention"),
            SpilloverEdge(source="European_Security", target="Energy_Markets", weight=0.55,
                          mechanism="Russia gas supply weaponization"),
            SpilloverEdge(source="Cyber_Domain", target="Semiconductors", weight=0.45,
                          mechanism="Supply chain attacks on chip manufacturers"),
            SpilloverEdge(source="Cyber_Domain", target="Global_Trade", weight=0.40,
                          mechanism="Financial system disruption"),
        ]
        self.edges = edges

    def simulate_spillover(
        self,
        source_theater: str,
        tension_increase: float,
        decay: float = 0.7,
        max_hops: int = 4,
    ) -> SpilloverResult:
        """
        Simulate how a tension increase in one theater propagates.
        Uses BFS with exponential decay at each hop.
        """
        if source_theater not in self.theaters:
            return SpilloverResult(
                source_theater=source_theater,
                source_tension=0.0,
                affected_theaters={},
                propagation_chain=[],
            )

        # Set source tension
        self.theaters[source_theater].current_tension = min(
            1.0, self.theaters[source_theater].current_tension + tension_increase
        )

        affected: Dict[str, float] = {}
        chain: List[str] = [source_theater]
        visited = {source_theater}

        # BFS propagation
        frontier = [(source_theater, tension_increase, 0)]

        while frontier:
            current, current_tension, hop = frontier.pop(0)
            if hop >= max_hops:
                continue

            # Find outgoing edges
            for edge in self.edges:
                if edge.source == current and edge.target not in visited:
                    propagated = current_tension * edge.weight * (decay ** hop)
                    if propagated > 0.01:  # Threshold
                        self.theaters[edge.target].current_tension = min(
                            1.0,
                            self.theaters[edge.target].current_tension + propagated,
                        )
                        affected[edge.target] = round(
                            self.theaters[edge.target].current_tension, 4
                        )
                        chain.append(f"{current}->{edge.target} ({propagated:.3f})")
                        visited.add(edge.target)
                        frontier.append((edge.target, propagated, hop + 1))

        return SpilloverResult(
            source_theater=source_theater,
            source_tension=self.theaters[source_theater].current_tension,
            affected_theaters=affected,
            propagation_chain=chain,
        )

    def get_global_tension_map(self) -> Dict[str, float]:
        """Return current tension levels across all theaters."""
        return {
            name: round(t.current_tension, 4)
            for name, t in self.theaters.items()
        }

    def reset(self):
        """Reset all tensions to zero."""
        for t in self.theaters.values():
            t.current_tension = 0.0
