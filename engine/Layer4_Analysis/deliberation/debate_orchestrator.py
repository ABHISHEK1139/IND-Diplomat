"""
MADAM-RAG: Multi-Agent Debate for Ambiguity and Misinformation
Implements geopolitical multi-perspective debate for grey area handling.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio


class DebateOutcome(Enum):
    """Possible outcomes of a debate."""
    CONSENSUS = "consensus"           # Agents agree
    CONFLICT = "conflict"             # Irreconcilable positions
    PARTIAL_AGREEMENT = "partial"     # Some common ground
    INSUFFICIENT_EVIDENCE = "insufficient"  # Not enough data


class GeopoliticalPerspective(Enum):
    """Geopolitical perspectives for debate agents."""
    INDIA = "new_delhi"
    GLOBAL_NORTH = "global_north"
    GLOBAL_SOUTH = "global_south"
    CHINA = "beijing"
    USA = "washington"
    ASEAN = "asean"
    INTERNATIONAL_LAW = "intl_law"
    NEUTRAL = "neutral"


@dataclass
class DebateAgent:
    """An agent representing a specific perspective."""
    perspective: GeopoliticalPerspective
    name: str
    bias_keywords: List[str]
    document_filter: str  # Query filter for knowledge base
    
    # Dynamic state
    position: Optional[str] = None
    supporting_evidence: List[str] = field(default_factory=list)
    confidence: float = 0.0
    concessions: List[str] = field(default_factory=list)


@dataclass
class DebateRound:
    """A single round of debate."""
    round_number: int
    positions: Dict[str, str]  # perspective -> position
    rebuttals: List[Dict[str, Any]]
    moderator_notes: str


@dataclass
class DebateOutcomeReport:
    """Final report from the debate."""
    query: str
    outcome: DebateOutcome
    rounds: List[DebateRound]
    conflicts_surfaced: List[Dict[str, Any]]
    consensus_points: List[str]
    final_synthesis: str
    confidence: float
    user_advisory: str


class MADAMRAGOrchestrator:
    """
    Multi-Agent Debate for Ambiguity and Misinformation in RAG.
    
    When evidence is conflicting:
    1. Assign document subsets to independent agents
    2. Agents simulate different perspectives
    3. Multi-round debate surfaces conflicts
    4. Final synthesis acknowledges grey areas
    """
    
    # Pre-configured debate agents
    AGENT_CONFIGS = {
        GeopoliticalPerspective.INDIA: DebateAgent(
            perspective=GeopoliticalPerspective.INDIA,
            name="New Delhi Analyst",
            bias_keywords=["india", "indian", "new delhi", "sovereignty", "strategic autonomy", "non-alignment"],
            document_filter="jurisdiction:India OR region:South_Asia"
        ),
        GeopoliticalPerspective.GLOBAL_NORTH: DebateAgent(
            perspective=GeopoliticalPerspective.GLOBAL_NORTH,
            name="Global North Analyst",
            bias_keywords=["western", "developed", "g7", "nato", "rules-based order"],
            document_filter="jurisdiction:USA OR jurisdiction:EU OR jurisdiction:UK"
        ),
        GeopoliticalPerspective.CHINA: DebateAgent(
            perspective=GeopoliticalPerspective.CHINA,
            name="Beijing Analyst",
            bias_keywords=["china", "chinese", "beijing", "prc", "belt and road", "peaceful rise"],
            document_filter="jurisdiction:China OR source:chinese"
        ),
        GeopoliticalPerspective.INTERNATIONAL_LAW: DebateAgent(
            perspective=GeopoliticalPerspective.INTERNATIONAL_LAW,
            name="International Law Expert",
            bias_keywords=["unclos", "icj", "treaty", "convention", "customary law", "jus cogens"],
            document_filter="type:legal OR type:treaty"
        ),
        GeopoliticalPerspective.NEUTRAL: DebateAgent(
            perspective=GeopoliticalPerspective.NEUTRAL,
            name="Neutral Moderator",
            bias_keywords=["objective", "balanced", "factual"],
            document_filter=""
        )
    }
    
    def __init__(self, retriever=None, llm_client=None):
        self.retriever = retriever
        self.llm = llm_client
        self.max_rounds = 3
    
    async def orchestrate_debate(
        self,
        query: str,
        sources: List[Dict],
        perspectives: List[GeopoliticalPerspective] = None,
        max_rounds: int = None
    ) -> DebateOutcomeReport:
        """
        Orchestrate a full multi-agent debate.
        """
        max_rounds = max_rounds or self.max_rounds
        
        # Select perspectives
        if perspectives is None:
            perspectives = self._auto_select_perspectives(query)
        
        # Initialize agents
        agents = [self._create_agent(p) for p in perspectives]
        
        # Partition sources by perspective
        source_partitions = self._partition_sources(sources, agents)
        
        rounds = []
        conflicts = []
        
        # Run debate rounds
        for round_num in range(max_rounds):
            round_result = await self._run_debate_round(
                query, 
                agents, 
                source_partitions, 
                rounds
            )
            rounds.append(round_result)
            
            # Detect new conflicts
            new_conflicts = self._detect_conflicts(round_result)
            conflicts.extend(new_conflicts)
            
            # Check for early consensus
            if self._check_consensus(agents):
                break
        
        # Determine outcome
        outcome = self._determine_outcome(agents, conflicts)
        
        # Generate synthesis
        synthesis = self._generate_synthesis(query, agents, conflicts, outcome)
        
        # Generate user advisory
        advisory = self._generate_advisory(outcome, conflicts)
        
        return DebateOutcomeReport(
            query=query,
            outcome=outcome,
            rounds=rounds,
            conflicts_surfaced=conflicts,
            consensus_points=self._extract_consensus(agents),
            final_synthesis=synthesis,
            confidence=self._calculate_confidence(agents, outcome),
            user_advisory=advisory
        )
    
    def _auto_select_perspectives(self, query: str) -> List[GeopoliticalPerspective]:
        """Auto-select relevant perspectives based on query."""
        query_lower = query.lower()
        
        # Always include neutral moderator
        perspectives = [GeopoliticalPerspective.NEUTRAL]
        
        # India-related
        if any(kw in query_lower for kw in ["india", "indian", "delhi", "modi", "quad"]):
            perspectives.append(GeopoliticalPerspective.INDIA)
        
        # China-related
        if any(kw in query_lower for kw in ["china", "chinese", "beijing", "south china sea", "taiwan", "bri"]):
            perspectives.append(GeopoliticalPerspective.CHINA)
        
        # Western/Global North
        if any(kw in query_lower for kw in ["us", "america", "nato", "europe", "g7", "sanctions"]):
            perspectives.append(GeopoliticalPerspective.GLOBAL_NORTH)
        
        # Legal matters
        if any(kw in query_lower for kw in ["treaty", "law", "legal", "unclos", "icj", "convention"]):
            perspectives.append(GeopoliticalPerspective.INTERNATIONAL_LAW)
        
        # Default: add India and International Law if nothing specific found
        if len(perspectives) == 1:
            perspectives.extend([
                GeopoliticalPerspective.INDIA,
                GeopoliticalPerspective.INTERNATIONAL_LAW
            ])
        
        return perspectives
    
    def _create_agent(self, perspective: GeopoliticalPerspective) -> DebateAgent:
        """Create an agent from config."""
        config = self.AGENT_CONFIGS.get(perspective, self.AGENT_CONFIGS[GeopoliticalPerspective.NEUTRAL])
        return DebateAgent(
            perspective=config.perspective,
            name=config.name,
            bias_keywords=config.bias_keywords.copy(),
            document_filter=config.document_filter
        )
    
    def _partition_sources(
        self, 
        sources: List[Dict], 
        agents: List[DebateAgent]
    ) -> Dict[str, List[Dict]]:
        """Partition sources to different agents based on relevance."""
        partitions = {agent.perspective.value: [] for agent in agents}
        shared = []
        
        for source in sources:
            content = source.get("content", "").lower()
            metadata = source.get("metadata", {})
            
            assigned = False
            for agent in agents:
                if any(kw in content for kw in agent.bias_keywords):
                    partitions[agent.perspective.value].append(source)
                    assigned = True
                    break
            
            if not assigned:
                shared.append(source)
        
        # Add shared to all
        for key in partitions:
            partitions[key].extend(shared)
        
        return partitions
    
    async def _run_debate_round(
        self,
        query: str,
        agents: List[DebateAgent],
        source_partitions: Dict[str, List[Dict]],
        previous_rounds: List[DebateRound]
    ) -> DebateRound:
        """Run a single debate round."""
        round_num = len(previous_rounds)
        positions = {}
        rebuttals = []
        
        # Each agent generates position
        for agent in agents:
            sources = source_partitions.get(agent.perspective.value, [])
            
            # Generate position from sources
            position = self._generate_position(query, agent, sources, previous_rounds)
            agent.position = position
            positions[agent.perspective.value] = position
            
            # Calculate confidence from source coverage
            agent.confidence = self._calculate_source_confidence(sources)
        
        # Generate rebuttals (each agent responds to others)
        for agent in agents:
            other_positions = {k: v for k, v in positions.items() if k != agent.perspective.value}
            
            for other_persp, other_pos in other_positions.items():
                if self._positions_conflict(agent.position, other_pos):
                    rebuttals.append({
                        "from": agent.perspective.value,
                        "to": other_persp,
                        "rebuttal": f"{agent.name} disagrees: {self._generate_rebuttal(agent.position, other_pos)}"
                    })
        
        # Moderator notes
        moderator_notes = self._generate_moderator_notes(positions, rebuttals)
        
        return DebateRound(
            round_number=round_num,
            positions=positions,
            rebuttals=rebuttals,
            moderator_notes=moderator_notes
        )
    
    def _generate_position(
        self,
        query: str,
        agent: DebateAgent,
        sources: List[Dict],
        previous_rounds: List[DebateRound]
    ) -> str:
        """Generate agent's position based on sources."""
        if not sources:
            return f"[{agent.name}] Insufficient evidence to take a position."
        
        # Extract key points from sources
        key_points = []
        for src in sources[:3]:
            content = src.get("content", "")[:200]
            if any(kw in content.lower() for kw in agent.bias_keywords):
                key_points.append(content)
        
        if not key_points:
            key_points = [src.get("content", "")[:200] for src in sources[:2]]
        
        # Frame position
        perspective_framing = {
            GeopoliticalPerspective.INDIA: "From India's strategic perspective",
            GeopoliticalPerspective.GLOBAL_NORTH: "From the rules-based international order perspective",
            GeopoliticalPerspective.CHINA: "From China's development-oriented perspective",
            GeopoliticalPerspective.INTERNATIONAL_LAW: "Under international legal frameworks",
            GeopoliticalPerspective.NEUTRAL: "Taking a balanced view",
        }
        
        framing = perspective_framing.get(agent.perspective, "Considering the evidence")
        evidence_summary = " | ".join(key_points)[:400]
        
        return f"[{agent.name}] {framing}: {evidence_summary}"
    
    def _positions_conflict(self, pos1: str, pos2: str) -> bool:
        """Detect if two positions conflict."""
        conflict_pairs = [
            ("sovereignty", "intervention"), ("territorial", "freedom"),
            ("historical", "current law"), ("bilateral", "multilateral"),
            ("development", "sanctions"), ("strategic", "economic")
        ]
        
        p1_lower = pos1.lower()
        p2_lower = pos2.lower()
        
        for w1, w2 in conflict_pairs:
            if w1 in p1_lower and w2 in p2_lower:
                return True
            if w2 in p1_lower and w1 in p2_lower:
                return True
        
        return False
    
    def _generate_rebuttal(self, my_pos: str, their_pos: str) -> str:
        """Generate a rebuttal to another position."""
        return f"While the other perspective notes relevant points, it overlooks key considerations emphasized in our analysis."
    
    def _generate_moderator_notes(
        self, 
        positions: Dict[str, str], 
        rebuttals: List[Dict]
    ) -> str:
        """Generate moderator summary of the round."""
        if len(rebuttals) == 0:
            return "Agents have presented their positions with no direct conflicts."
        else:
            return f"This round surfaced {len(rebuttals)} areas of disagreement between perspectives."
    
    def _detect_conflicts(self, round_result: DebateRound) -> List[Dict]:
        """Detect conflicts from a debate round."""
        conflicts = []
        
        for rebuttal in round_result.rebuttals:
            conflicts.append({
                "type": "position_conflict",
                "agent_a": rebuttal["from"],
                "agent_b": rebuttal["to"],
                "nature": "Disagreement on interpretation",
                "round": round_result.round_number
            })
        
        return conflicts
    
    def _check_consensus(self, agents: List[DebateAgent]) -> bool:
        """Check if agents have reached consensus."""
        positions = [a.position for a in agents if a.position]
        if len(positions) < 2:
            return True
        
        # Simple heuristic: check for reuse of same key phrases
        first_words = set(positions[0].lower().split()[:20])
        for pos in positions[1:]:
            other_words = set(pos.lower().split()[:20])
            overlap = len(first_words & other_words) / len(first_words) if first_words else 0
            if overlap < 0.3:
                return False
        
        return True
    
    def _determine_outcome(
        self, 
        agents: List[DebateAgent], 
        conflicts: List[Dict]
    ) -> DebateOutcome:
        """Determine the debate outcome."""
        if len(conflicts) == 0:
            return DebateOutcome.CONSENSUS
        elif len(conflicts) > len(agents):
            return DebateOutcome.CONFLICT
        elif any(a.confidence < 0.3 for a in agents):
            return DebateOutcome.INSUFFICIENT_EVIDENCE
        else:
            return DebateOutcome.PARTIAL_AGREEMENT
    
    def _extract_consensus(self, agents: List[DebateAgent]) -> List[str]:
        """Extract points of consensus."""
        if not agents:
            return []
        
        # Find common phrases across positions
        all_positions = [a.position.lower() if a.position else "" for a in agents]
        
        common = []
        words = set(all_positions[0].split())
        for pos in all_positions[1:]:
            words &= set(pos.split())
        
        if len(words) > 5:
            common.append("Agents agree on fundamental context")
        
        return common
    
    def _generate_synthesis(
        self,
        query: str,
        agents: List[DebateAgent],
        conflicts: List[Dict],
        outcome: DebateOutcome
    ) -> str:
        """Generate final synthesis from debate."""
        lines = [f"**Query**: {query}\n"]
        
        if outcome == DebateOutcome.CONFLICT:
            lines.append("**Outcome**: Multiple perspectives offer divergent interpretations.\n")
            lines.append("The following viewpoints emerged:\n")
        elif outcome == DebateOutcome.CONSENSUS:
            lines.append("**Outcome**: Perspectives converge on key points.\n")
        else:
            lines.append("**Outcome**: Partial agreement with notable differences.\n")
        
        for agent in agents:
            if agent.position:
                lines.append(f"- **{agent.name}**: {agent.position[:200]}...\n")
        
        if conflicts:
            lines.append("\n**Conflicts Identified**:\n")
            for c in conflicts[:3]:
                lines.append(f"- {c.get('agent_a', '?')} vs {c.get('agent_b', '?')}: {c.get('nature', 'Position conflict')}\n")
        
        return "".join(lines)
    
    def _generate_advisory(
        self, 
        outcome: DebateOutcome, 
        conflicts: List[Dict]
    ) -> str:
        """Generate user advisory based on outcome."""
        if outcome == DebateOutcome.CONFLICT:
            return (
                "⚠️ **Grey Area Detected**: This topic has significant interpretive divergence. "
                "Rather than providing a single answer, we present multiple perspectives. "
                "Consider the geopolitical context when evaluating these viewpoints."
            )
        elif outcome == DebateOutcome.INSUFFICIENT_EVIDENCE:
            return (
                "⚠️ **Limited Evidence**: The available documents do not provide sufficient "
                "coverage for a definitive answer. Consider requesting additional sources."
            )
        elif outcome == DebateOutcome.PARTIAL_AGREEMENT:
            return (
                "ℹ️ **Nuanced Topic**: While there is partial consensus, notable differences "
                "exist between perspectives. The synthesis reflects these complexities."
            )
        else:
            return "✅ Perspectives converge on the core analysis."
    
    def _calculate_confidence(
        self, 
        agents: List[DebateAgent], 
        outcome: DebateOutcome
    ) -> float:
        """Calculate overall confidence in the debate result."""
        base = sum(a.confidence for a in agents) / len(agents) if agents else 0.5
        
        if outcome == DebateOutcome.CONSENSUS:
            return min(1.0, base + 0.2)
        elif outcome == DebateOutcome.CONFLICT:
            return max(0.3, base - 0.2)
        else:
            return base
    
    def _calculate_source_confidence(self, sources: List[Dict]) -> float:
        """Calculate confidence from source quality."""
        if not sources:
            return 0.2
        
        base = min(1.0, len(sources) * 0.15)
        scores = [s.get("score", 0.5) for s in sources]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        return min(1.0, base + avg_score * 0.3)


# Singleton instance
debate_orchestrator = MADAMRAGOrchestrator()
