"""
Actor Network Model — Geopolitical Relationship Graph
======================================================

Extends the existing Layer7 contagion engine with a richer
actor relationship model that captures:

- Alliance/adversary relationships
- Proxy actor connections
- Regional influence spheres
- Escalation cascade paths

This is an **additive layer** on top of the existing
``Layer7_GlobalModel.interdependence_matrix``.
It does NOT modify the existing contagion engine.

Usage::

    from analysis.actor_network import ActorNetwork

    net = ActorNetwork()
    net.propagate_escalation("IRN", sre=0.75)
    cascade = net.trace_cascade("IRN")
    print(cascade)

Architecture::

    Existing interdependence_matrix
                ↓
    ActorNetwork (enriched graph)
                ↓
    Cascade analysis
                ↓
    Second-order risk assessment
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("analysis.actor_network")


class RelationType(str, Enum):
    """Types of geopolitical relationships."""
    ALLIANCE = "alliance"           # Formal defense pact
    ADVERSARY = "adversary"         # Active rivalry / hostility
    PROXY = "proxy"                 # Proxy relationship (sponsor → proxy)
    TRADE_PARTNER = "trade"         # Major trade dependency
    NUCLEAR_RIVAL = "nuclear"       # Nuclear deterrence relationship
    GEOGRAPHIC = "geographic"       # Geographic adjacency
    ENERGY_LINK = "energy"          # Energy supply dependency
    PROXY_BATTLEFIELD = "proxy_bf"  # Country where proxies fight


@dataclass
class ActorRelation:
    """A directed relationship between two actors."""
    source: str          # ISO-3 source actor
    target: str          # ISO-3 target actor
    relation: RelationType
    weight: float        # Influence weight [0, 1]
    cascade_factor: float = 0.25  # How much escalation propagates
    description: str = ""


@dataclass
class CascadeStep:
    """One step in an escalation cascade."""
    from_actor: str
    to_actor: str
    relation: str
    incoming_sre: float
    propagated_risk: float
    depth: int


@dataclass
class CascadeResult:
    """Complete cascade analysis result."""
    origin: str
    origin_sre: float
    steps: List[CascadeStep] = field(default_factory=list)
    affected_actors: Dict[str, float] = field(default_factory=dict)
    max_depth: int = 0
    total_propagated_risk: float = 0.0

    def to_dict(self) -> dict:
        return {
            "origin": self.origin,
            "origin_sre": self.origin_sre,
            "affected_actors": self.affected_actors,
            "max_depth": self.max_depth,
            "total_propagated_risk": round(self.total_propagated_risk, 4),
            "cascade_steps": [
                {
                    "from": s.from_actor,
                    "to": s.to_actor,
                    "relation": s.relation,
                    "risk": round(s.propagated_risk, 4),
                    "depth": s.depth,
                }
                for s in self.steps
            ],
        }


# ══════════════════════════════════════════════════════════════════
#  ACTOR GRAPH — Comprehensive geopolitical relationship database
# ══════════════════════════════════════════════════════════════════

ACTOR_RELATIONS: List[ActorRelation] = [

    # ── Iran Axis ─────────────────────────────────────────────────
    ActorRelation("IRN", "ISR", RelationType.ADVERSARY, 0.85, 0.30, "Direct adversary — existential threat framing"),
    ActorRelation("ISR", "IRN", RelationType.ADVERSARY, 0.80, 0.28, "Israel reactive to Iranian nuclear program"),
    ActorRelation("IRN", "USA", RelationType.ADVERSARY, 0.70, 0.25, "Strategic competition — sanctions / nuclear"),
    ActorRelation("USA", "IRN", RelationType.ADVERSARY, 0.65, 0.22, "US maximum pressure policy"),
    ActorRelation("IRN", "SAU", RelationType.ADVERSARY, 0.60, 0.20, "Regional Sunni-Shia rivalry"),
    ActorRelation("SAU", "IRN", RelationType.ADVERSARY, 0.55, 0.18, "Saudi defensive posture"),
    ActorRelation("IRN", "LBN", RelationType.PROXY, 0.75, 0.30, "Hezbollah sponsor — primary proxy"),
    ActorRelation("LBN", "IRN", RelationType.PROXY, 0.35, 0.12, "Limited return influence"),
    ActorRelation("IRN", "SYR", RelationType.PROXY, 0.65, 0.25, "Syrian theater — Quds Force presence"),
    ActorRelation("IRN", "YEM", RelationType.PROXY, 0.55, 0.20, "Houthi support — Red Sea dimension"),
    ActorRelation("IRN", "IRQ", RelationType.PROXY, 0.60, 0.22, "Shia militia influence in Iraq"),

    # ── Israel Axis ───────────────────────────────────────────────
    ActorRelation("ISR", "LBN", RelationType.ADVERSARY, 0.75, 0.28, "Border confrontation — Hezbollah"),
    ActorRelation("LBN", "ISR", RelationType.ADVERSARY, 0.65, 0.25, "Southern Lebanon resistance"),
    ActorRelation("ISR", "USA", RelationType.ALLIANCE, 0.80, 0.15, "Strategic alliance — military aid"),
    ActorRelation("USA", "ISR", RelationType.ALLIANCE, 0.75, 0.15, "US commitment to Israel security"),
    ActorRelation("ISR", "SYR", RelationType.ADVERSARY, 0.50, 0.18, "Golan / Iranian presence in Syria"),
    ActorRelation("ISR", "PSE", RelationType.ADVERSARY, 0.70, 0.22, "Occupation / resistance dynamic"),

    # ── Russia–Ukraine Axis ───────────────────────────────────────
    ActorRelation("RUS", "UKR", RelationType.ADVERSARY, 0.95, 0.35, "Primary conflict dyad — active war"),
    ActorRelation("UKR", "RUS", RelationType.ADVERSARY, 0.90, 0.30, "Ukrainian resistance / counter-offensive"),
    ActorRelation("RUS", "USA", RelationType.NUCLEAR_RIVAL, 0.55, 0.18, "Superpower nuclear deterrence"),
    ActorRelation("USA", "RUS", RelationType.NUCLEAR_RIVAL, 0.50, 0.15, "US strategic competition"),
    ActorRelation("RUS", "BLR", RelationType.ALLIANCE, 0.70, 0.20, "Military staging partner"),
    ActorRelation("USA", "UKR", RelationType.ALLIANCE, 0.65, 0.12, "US military aid to Ukraine"),
    ActorRelation("RUS", "TUR", RelationType.GEOGRAPHIC, 0.35, 0.12, "Black Sea competition"),
    ActorRelation("RUS", "GEO", RelationType.ADVERSARY, 0.50, 0.15, "Frozen conflicts — Abkhazia/Ossetia"),

    # ── China–Taiwan Axis ─────────────────────────────────────────
    ActorRelation("CHN", "TWN", RelationType.ADVERSARY, 0.90, 0.32, "Unification pressure — existential for Taiwan"),
    ActorRelation("TWN", "CHN", RelationType.ADVERSARY, 0.50, 0.15, "Taiwan defensive posture"),
    ActorRelation("CHN", "USA", RelationType.NUCLEAR_RIVAL, 0.60, 0.20, "Great power competition"),
    ActorRelation("USA", "CHN", RelationType.NUCLEAR_RIVAL, 0.55, 0.18, "Indo-Pacific strategy"),
    ActorRelation("USA", "TWN", RelationType.ALLIANCE, 0.70, 0.15, "Taiwan Relations Act — strategic ambiguity"),
    ActorRelation("CHN", "JPN", RelationType.ADVERSARY, 0.45, 0.15, "Senkaku/Diaoyu + historical tensions"),
    ActorRelation("CHN", "IND", RelationType.ADVERSARY, 0.45, 0.15, "LAC border disputes"),
    ActorRelation("CHN", "PHL", RelationType.ADVERSARY, 0.40, 0.12, "South China Sea — Second Thomas Shoal"),
    ActorRelation("CHN", "AUS", RelationType.ADVERSARY, 0.30, 0.10, "Pacific influence competition"),

    # ── India–Pakistan Axis ───────────────────────────────────────
    ActorRelation("IND", "PAK", RelationType.NUCLEAR_RIVAL, 0.80, 0.28, "Kashmir / nuclear deterrence"),
    ActorRelation("PAK", "IND", RelationType.NUCLEAR_RIVAL, 0.75, 0.25, "Asymmetric deterrence"),
    ActorRelation("IND", "CHN", RelationType.ADVERSARY, 0.45, 0.15, "Ladakh LAC standoff"),
    ActorRelation("PAK", "CHN", RelationType.ALLIANCE, 0.55, 0.12, "CPEC / all-weather friendship"),

    # ── Korean Peninsula ──────────────────────────────────────────
    ActorRelation("PRK", "USA", RelationType.NUCLEAR_RIVAL, 0.65, 0.22, "ICBM / nuclear threat"),
    ActorRelation("USA", "PRK", RelationType.ADVERSARY, 0.55, 0.18, "Maximum pressure / deterrence"),
    ActorRelation("PRK", "KOR", RelationType.ADVERSARY, 0.80, 0.28, "Korean War armistice state"),
    ActorRelation("KOR", "PRK", RelationType.ADVERSARY, 0.70, 0.22, "South Korean defense posture"),
    ActorRelation("USA", "KOR", RelationType.ALLIANCE, 0.75, 0.12, "US–ROK mutual defense treaty"),
    ActorRelation("USA", "JPN", RelationType.ALLIANCE, 0.70, 0.12, "US–Japan security alliance"),
    ActorRelation("CHN", "PRK", RelationType.ALLIANCE, 0.45, 0.12, "PRC–DPRK buffer state relationship"),

    # ── Turkey Regional ───────────────────────────────────────────
    ActorRelation("TUR", "SYR", RelationType.GEOGRAPHIC, 0.55, 0.18, "Northern Syria operations — Kurdish dimension"),
    ActorRelation("TUR", "GRC", RelationType.ADVERSARY, 0.35, 0.12, "Aegean / Cyprus disputes"),
    ActorRelation("TUR", "RUS", RelationType.ADVERSARY, 0.30, 0.10, "Libya / Black Sea competition"),

    # ── Middle East Energy ────────────────────────────────────────
    ActorRelation("SAU", "USA", RelationType.ENERGY_LINK, 0.55, 0.12, "Oil supply partnership"),
    ActorRelation("IRN", "CHN", RelationType.ENERGY_LINK, 0.45, 0.10, "Sanctioned oil trade"),
    ActorRelation("RUS", "DEU", RelationType.ENERGY_LINK, 0.40, 0.10, "Gas dependency (reduced post-2022)"),

    # ── Africa ────────────────────────────────────────────────────
    ActorRelation("ETH", "ERI", RelationType.ADVERSARY, 0.50, 0.15, "Horn of Africa rivalry"),
    ActorRelation("RUS", "LBY", RelationType.PROXY, 0.35, 0.12, "Wagner Group presence"),
    ActorRelation("RUS", "MLI", RelationType.PROXY, 0.35, 0.12, "Wagner / Africa Corps"),
    ActorRelation("RUS", "SDN", RelationType.PROXY, 0.30, 0.10, "RSF ties"),
]


class ActorNetwork:
    """
    Geopolitical actor network model.

    Extends the existing Layer7 contagion system with richer
    relationship types and cascade analysis.
    """

    def __init__(self) -> None:
        # Build adjacency index
        self._outgoing: Dict[str, List[ActorRelation]] = {}
        self._incoming: Dict[str, List[ActorRelation]] = {}
        self._all_actors: Set[str] = set()

        for rel in ACTOR_RELATIONS:
            self._outgoing.setdefault(rel.source, []).append(rel)
            self._incoming.setdefault(rel.target, []).append(rel)
            self._all_actors.add(rel.source)
            self._all_actors.add(rel.target)

    @property
    def actor_count(self) -> int:
        return len(self._all_actors)

    @property
    def relation_count(self) -> int:
        return len(ACTOR_RELATIONS)

    def get_neighbors(self, actor: str) -> List[ActorRelation]:
        """Get all outgoing relations from an actor."""
        return self._outgoing.get(actor.upper(), [])

    def get_adversaries(self, actor: str) -> List[ActorRelation]:
        """Get adversary relations for an actor."""
        return [
            r for r in self.get_neighbors(actor)
            if r.relation in {RelationType.ADVERSARY, RelationType.NUCLEAR_RIVAL}
        ]

    def get_allies(self, actor: str) -> List[ActorRelation]:
        """Get alliance relations for an actor."""
        return [
            r for r in self.get_neighbors(actor)
            if r.relation == RelationType.ALLIANCE
        ]

    def get_proxies(self, actor: str) -> List[ActorRelation]:
        """Get proxy relations (actors sponsored by this one)."""
        return [
            r for r in self.get_neighbors(actor)
            if r.relation == RelationType.PROXY
        ]

    def compute_centrality(self) -> Dict[str, float]:
        """
        Compute weighted degree centrality for all actors.

        Higher centrality = more geopolitical connections = higher
        systemic importance.
        """
        scores: Dict[str, float] = {}
        for actor in self._all_actors:
            out_weight = sum(r.weight for r in self._outgoing.get(actor, []))
            in_weight = sum(r.weight for r in self._incoming.get(actor, []))
            scores[actor] = round(out_weight + in_weight, 3)
        return dict(sorted(scores.items(), key=lambda x: -x[1]))

    def trace_cascade(
        self,
        origin: str,
        origin_sre: float = 0.50,
        *,
        max_depth: int = 3,
        min_propagation: float = 0.01,
    ) -> CascadeResult:
        """
        Trace escalation cascade from an origin actor.

        Simulates how escalation in one country propagates
        through the actor network via alliance obligations,
        adversary reactions, and proxy mobilization.

        Parameters
        ----------
        origin : str
            ISO-3 code of the escalating actor.
        origin_sre : float
            SRE score of the origin actor.
        max_depth : int
            Maximum cascade depth (prevents infinite loops).
        min_propagation : float
            Minimum propagated risk to continue cascading.

        Returns
        -------
        CascadeResult
            Complete cascade analysis.
        """
        result = CascadeResult(origin=origin.upper(), origin_sre=origin_sre)
        visited: Set[str] = {origin.upper()}
        queue: List[Tuple[str, float, int]] = [(origin.upper(), origin_sre, 0)]

        while queue:
            actor, sre, depth = queue.pop(0)

            if depth >= max_depth:
                continue

            for rel in self.get_neighbors(actor):
                target = rel.target
                if target in visited:
                    continue

                # Calculate propagated risk
                propagated = sre * rel.cascade_factor

                # Adversaries react more strongly
                if rel.relation in {RelationType.ADVERSARY, RelationType.NUCLEAR_RIVAL}:
                    propagated *= 1.5
                # Proxies mobilize proportionally
                elif rel.relation == RelationType.PROXY:
                    propagated *= 1.3
                # Allies may be pulled in
                elif rel.relation == RelationType.ALLIANCE:
                    propagated *= 0.8

                propagated = round(min(1.0, propagated), 4)

                if propagated < min_propagation:
                    continue

                step = CascadeStep(
                    from_actor=actor,
                    to_actor=target,
                    relation=rel.relation.value,
                    incoming_sre=sre,
                    propagated_risk=propagated,
                    depth=depth + 1,
                )
                result.steps.append(step)

                # Accumulate risk for target
                result.affected_actors[target] = round(
                    result.affected_actors.get(target, 0.0) + propagated, 4,
                )
                result.total_propagated_risk += propagated

                visited.add(target)
                result.max_depth = max(result.max_depth, depth + 1)

                # Continue cascade from this actor
                if propagated >= min_propagation:
                    queue.append((target, propagated, depth + 1))

        logger.info(
            "[ACTOR-NET] Cascade from %s (SRE=%.3f): %d actors affected, "
            "total_risk=%.3f, depth=%d",
            origin, origin_sre, len(result.affected_actors),
            result.total_propagated_risk, result.max_depth,
        )

        return result

    def propagate_escalation(
        self,
        source: str,
        sre: float,
    ) -> Dict[str, float]:
        """
        Simple one-hop escalation propagation (compatible with Layer7).

        Like ``contagion_engine.propagate_shock`` but uses the richer
        ActorNetwork graph instead of the flat interdependence matrix.

        Returns
        -------
        dict
            target_country → propagated risk amount.
        """
        cc = source.upper()
        if sre < 0.20:
            return {}

        spillovers: Dict[str, float] = {}
        for rel in self.get_neighbors(cc):
            propagated = round(sre * rel.cascade_factor, 4)
            if propagated >= 0.01:
                spillovers[rel.target] = propagated

        return spillovers

    def get_influence_sphere(self, actor: str) -> Dict[str, List[str]]:
        """
        Get the influence sphere of an actor grouped by relation type.

        Returns
        -------
        dict
            {relation_type: [actor_codes]}
        """
        sphere: Dict[str, List[str]] = {}
        for rel in self.get_neighbors(actor.upper()):
            sphere.setdefault(rel.relation.value, []).append(rel.target)
        return sphere

    def print_network_summary(self) -> str:
        """Format a human-readable network summary."""
        centrality = self.compute_centrality()
        top10 = list(centrality.items())[:10]

        lines = [
            "=" * 60,
            "ACTOR NETWORK SUMMARY",
            "=" * 60,
            f"Total Actors:     {self.actor_count}",
            f"Total Relations:  {self.relation_count}",
            "",
            "Top 10 by Centrality:",
            f"  {'Actor':<8} {'Score':>8}  {'Out':>4}  {'In':>4}",
            "  " + "-" * 30,
        ]

        for actor, score in top10:
            out_n = len(self._outgoing.get(actor, []))
            in_n = len(self._incoming.get(actor, []))
            lines.append(f"  {actor:<8} {score:>8.3f}  {out_n:>4}  {in_n:>4}")

        lines.append("=" * 60)
        return "\n".join(lines)
