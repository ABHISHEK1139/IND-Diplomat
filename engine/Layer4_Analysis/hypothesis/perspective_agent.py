"""
Multi-Perspective Simulation Agent - Mixture-of-Agents (MoA) Debate Loop
Handles grey area scenarios by simulating multiple diplomatic viewpoints.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
import json


class Perspective(Enum):
    """Major geopolitical perspectives."""
    NEW_DELHI = "new_delhi"       # India
    WASHINGTON = "washington"     # USA
    BEIJING = "beijing"           # China
    MOSCOW = "moscow"             # Russia
    BRUSSELS = "brussels"         # EU
    TOKYO = "tokyo"               # Japan
    ASEAN = "asean"               # ASEAN bloc
    NEUTRAL = "neutral"           # Non-aligned
    INTERNATIONAL_LAW = "intl_law"  # UNCLOS, ICJ perspective


@dataclass
class AgentVoice:
    """Configuration for a perspective agent."""
    perspective: Perspective
    name: str
    bias_keywords: List[str]
    priority_topics: List[str]
    knowledge_subset: str  # Query filter for knowledge base
    system_prompt: str


@dataclass
class DebatePoint:
    """A point made in the debate."""
    agent: str
    perspective: Perspective
    position: str
    supporting_evidence: List[str]
    confidence: float
    counters: List[str]  # Points this counters


@dataclass  
class DebateResult:
    """Result of a multi-agent debate."""
    query: str
    points: List[DebatePoint]
    consensus: Optional[str]
    conflicts: List[Dict[str, Any]]
    grey_areas: List[str]
    recommendation: str
    confidence: float


class PerspectiveAgent:
    """
    Individual perspective agent that argues from a specific viewpoint.
    """
    
    def __init__(self, voice: AgentVoice, llm_client=None):
        self.voice = voice
        self.llm = llm_client
        self.local_llm = None
        try:
            from engine.Layer4_Analysis.core.llm_client import LocalLLM

            if isinstance(llm_client, LocalLLM):
                self.local_llm = llm_client
            else:
                self.local_llm = LocalLLM()
        except Exception:
            self.local_llm = None

    def analyze(self, state_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Structured minister analysis for council-mode reasoning.
        """
        if self.local_llm is None:
            return {
                "hypothesis_type": "unknown",
                "predicted_signals": [],
                "matched_signals": [],
                "missing_signals": ["llm_unavailable"],
                "confidence": 0.0,
                "reasoning": "LocalLLM unavailable.",
            }

        user_prompt = f"""
You are analyzing a geopolitical situation.

StateContext:
{json.dumps(state_context, indent=2)}

You must produce a JSON response ONLY.

Format:
{{
 "hypothesis_type": "",
 "predicted_signals": [],
 "matched_signals": [],
 "missing_signals": [],
 "confidence": 0.0,
 "reasoning": ""
}}

Rules:
- Output valid JSON only. No markdown. No prose outside JSON.
- Infer signals from StateContext.
- Confidence must be between 0 and 1.
""".strip()

        system_prompt = f"""
{self.voice.system_prompt}
You are a minister in a deliberative council.
You will be terminated if you output anything except JSON.
""".strip()

        raw = self.local_llm.generate(system_prompt, user_prompt, temperature=0.2, json_mode=True)
        if str(raw).startswith("LLM_ERROR:"):
            return {
                "hypothesis_type": "unknown",
                "predicted_signals": [],
                "matched_signals": [],
                "missing_signals": ["llm_error"],
                "confidence": 0.0,
                "reasoning": str(raw)[:300],
            }

        data = self._parse_json_payload(raw)
        if not isinstance(data, dict):
            return {
                "hypothesis_type": "unknown",
                "predicted_signals": [],
                "matched_signals": [],
                "missing_signals": ["parse_error"],
                "confidence": 0.0,
                "reasoning": str(raw)[:300],
            }

        return {
            "hypothesis_type": str(data.get("hypothesis_type", "unknown") or "unknown"),
            "predicted_signals": self._safe_str_list(data.get("predicted_signals")),
            "matched_signals": self._safe_str_list(data.get("matched_signals")),
            "missing_signals": self._safe_str_list(data.get("missing_signals")),
            "confidence": self._clamp_confidence(data.get("confidence", 0.0)),
            "reasoning": str(data.get("reasoning", "") or "")[:1200],
        }

    def analyze_council(
        self,
        state_context: Dict[str, Any],
        minister_prompts: Dict[str, str],
        allowed_signals: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate hypotheses for all ministers in one LLM call.
        """
        if self.local_llm is None:
            return {}

        minister_ids = [str(key) for key in minister_prompts.keys()]
        user_prompt = f"""
You are generating hypotheses for a geopolitical council.

StateContext:
{json.dumps(state_context, indent=2)}

Ministers and focus:
{json.dumps(minister_prompts, indent=2)}

Allowed signals:
{json.dumps(allowed_signals, indent=2)}

Return JSON ONLY in this exact structure:
{{
  "security": {{"hypothesis_type": "", "predicted_signals": [], "confidence": 0.0}},
  "strategy": {{"hypothesis_type": "", "predicted_signals": [], "confidence": 0.0}},
  "diplomacy": {{"hypothesis_type": "", "predicted_signals": [], "confidence": 0.0}},
  "domestic": {{"hypothesis_type": "", "predicted_signals": [], "confidence": 0.0}},
  "economic": {{"hypothesis_type": "", "predicted_signals": [], "confidence": 0.0}},
  "alliance": {{"hypothesis_type": "", "predicted_signals": [], "confidence": 0.0}}
}}

Rules:
- Output valid JSON only.
- Use only allowed signals in predicted_signals.
- Use at most 3 predicted_signals per minister.
- Keep hypothesis_type short (2-4 words).
- No extra keys.
""".strip()

        system_prompt = (
            "You are the Council Secretariat. Return compact JSON only. "
            "Do not output markdown, commentary, or chain-of-thought."
        )
        raw = self.local_llm.generate(system_prompt, user_prompt, temperature=0.2, json_mode=True)
        parsed = self._parse_json_payload(raw)
        if not isinstance(parsed, dict):
            return {}
        return self._normalize_council_payload(parsed, minister_ids)

    def _parse_json_payload(self, raw: str) -> Optional[Dict[str, Any]]:
        text = str(raw or "").strip()
        if not text:
            return None

        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

    def _safe_str_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    def _clamp_confidence(self, value: Any) -> float:
        try:
            score = float(value)
        except Exception:
            score = 0.0
        return max(0.0, min(1.0, score))

    def _normalize_council_payload(
        self,
        payload: Dict[str, Any],
        minister_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for minister_id in minister_ids:
            row = payload.get(minister_id, {})
            if not isinstance(row, dict):
                continue
            out[minister_id] = {
                "hypothesis_type": str(row.get("hypothesis_type", "unknown") or "unknown"),
                "predicted_signals": self._safe_str_list(row.get("predicted_signals")),
                "matched_signals": self._safe_str_list(row.get("matched_signals")),
                "missing_signals": self._safe_str_list(row.get("missing_signals")),
                "confidence": self._clamp_confidence(row.get("confidence", 0.0)),
                "reasoning": str(row.get("reasoning", "") or "")[:1200],
            }
        return out
        
    async def generate_position(
        self, 
        query: str, 
        context: List[Dict],
        other_positions: List[DebatePoint] = None
    ) -> DebatePoint:
        """Generate this agent's position on the query.
        
        BOUNDARY CONTRACT: Layer-4 must not read document content.
        Context entries are treated as signal metadata (signal token, source,
        confidence) NOT as raw text. Supporting evidence references signal
        tokens and provenance summaries, never document excerpts.
        """
        # Filter context to this perspective's relevant signals
        filtered_context = self._filter_context(context)
        
        # Build position
        if self.llm:
            position = await self._llm_generate(query, filtered_context, other_positions)
        else:
            position = self._rule_based_position(query, filtered_context)
        
        # Identify counters
        counters = []
        if other_positions:
            for op in other_positions:
                if self._is_opposing(position, op.position):
                    counters.append(op.agent)
        
        # Reference signal tokens and provenance, never raw content
        supporting = []
        for c in filtered_context[:3]:
            signal = str(c.get("signal", c.get("signal_token", ""))).strip()
            source = str(c.get("source", c.get("source_name", "unknown"))).strip()
            conf = c.get("confidence", c.get("score", 0.0))
            if signal:
                supporting.append(f"{signal} ({source}, conf={conf:.2f})")
            elif source != "unknown":
                supporting.append(f"{source} (conf={conf:.2f})")

        return DebatePoint(
            agent=self.voice.name,
            perspective=self.voice.perspective,
            position=position,
            supporting_evidence=supporting,
            confidence=self._calculate_confidence(filtered_context),
            counters=counters
        )
    
    def _filter_context(self, context: List[Dict]) -> List[Dict]:
        """Filter context to this perspective's relevant signals.
        
        BOUNDARY CONTRACT: Filters by signal metadata (signal token, source,
        jurisdiction) — NOT by scanning document text content.
        """
        filtered = []
        
        for doc in context:
            metadata = doc.get("metadata", {})
            signal_token = str(doc.get("signal", doc.get("signal_token", ""))).strip().upper()
            source_name = str(doc.get("source", doc.get("source_name", ""))).lower()
            
            # Check jurisdiction match via metadata
            jurisdiction = metadata.get("jurisdiction", "").lower()
            if self.voice.perspective.value in jurisdiction:
                filtered.append(doc)
                continue
            
            # Check bias keywords against signal tokens and source names
            check_text = f"{signal_token} {source_name}".lower()
            if any(kw in check_text for kw in self.voice.bias_keywords):
                filtered.append(doc)
                continue
            
            # Check priority topics against signal tokens
            if any(topic.upper().replace(" ", "_") in signal_token for topic in self.voice.priority_topics if topic):
                filtered.append(doc)
        
        return filtered if filtered else context[:3]
    
    def _rule_based_position(self, query: str, context: List[Dict]) -> str:
        """Generate rule-based position without LLM.
        
        BOUNDARY CONTRACT: Uses signal tokens and metadata for evidence summary,
        never raw document content.
        """
        query_lower = query.lower()
        
        # Build evidence summary from signal metadata, not document text
        signal_points = []
        for doc in context[:3]:
            signal = str(doc.get("signal", doc.get("signal_token", ""))).strip()
            source = str(doc.get("source", doc.get("source_name", ""))).strip()
            conf = doc.get("confidence", doc.get("score", 0.0))
            try:
                conf = float(conf or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            if signal:
                signal_points.append(f"{signal} (source: {source}, confidence: {conf:.2f})")
            elif source:
                signal_points.append(f"{source} (confidence: {conf:.2f})")
        
        base = f"From the {self.voice.name} perspective"
        
        # Add perspective-specific framing
        if self.voice.perspective == Perspective.NEW_DELHI:
            base += ", with emphasis on sovereignty and strategic autonomy"
        elif self.voice.perspective == Perspective.WASHINGTON:
            base += ", focusing on rules-based international order"
        elif self.voice.perspective == Perspective.BEIJING:
            base += ", emphasizing historical claims and development rights"
        elif self.voice.perspective == Perspective.INTERNATIONAL_LAW:
            base += ", applying UNCLOS and established legal precedents"
        
        evidence_summary = " | ".join(signal_points) if signal_points else "no relevant signals detected"
        
        return f"{base}: {evidence_summary[:500]}"
    
    async def _llm_generate(
        self, 
        query: str, 
        context: List[Dict], 
        other_positions: List[DebatePoint]
    ) -> str:
        """Generate position using LLM."""
        # This would call the actual LLM
        # For now, use rule-based
        return self._rule_based_position(query, context)
    
    def _is_opposing(self, position1: str, position2: str) -> bool:
        """Detect if two positions are opposing."""
        opposition_markers = [
            ("sovereignty", "interference"),
            ("territorial", "freedom of navigation"),
            ("historical", "current law"),
            ("bilateral", "multilateral")
        ]
        
        for m1, m2 in opposition_markers:
            if m1 in position1.lower() and m2 in position2.lower():
                return True
            if m2 in position1.lower() and m1 in position2.lower():
                return True
        
        return False
    
    def _calculate_confidence(self, context: List[Dict]) -> float:
        """Calculate confidence based on evidence quality."""
        if not context:
            return 0.3
        
        # Score based on number and quality of sources
        base = min(1.0, len(context) * 0.2)
        
        # Boost for high-scoring sources
        scores = [doc.get("score", 0.5) for doc in context]
        avg_score = sum(scores) / len(scores) if scores else 0.5
        
        return min(1.0, base + avg_score * 0.3)


class DebateOrchestrator:
    """
    Orchestrates multi-agent debate for grey area scenarios.
    Implements the Mixture-of-Agents (MoA) debate loop.
    """
    
    # Pre-configured perspective agents
    AGENT_CONFIGS = [
        AgentVoice(
            perspective=Perspective.NEW_DELHI,
            name="New Delhi Agent",
            bias_keywords=["india", "indian", "new delhi", "sovereignty", "autonomy"],
            priority_topics=["quad", "indo-pacific", "border", "kashmir", "economic partnership"],
            knowledge_subset="jurisdiction:India OR jurisdiction:Indo-Pacific",
            system_prompt="You represent India's strategic perspective, emphasizing sovereignty, strategic autonomy, and regional stability."
        ),
        AgentVoice(
            perspective=Perspective.WASHINGTON,
            name="Washington Agent",
            bias_keywords=["united states", "american", "washington", "alliance", "rules-based"],
            priority_topics=["freedom of navigation", "alliance", "sanctions", "security partnership"],
            knowledge_subset="jurisdiction:USA OR jurisdiction:International",
            system_prompt="You represent the US perspective, emphasizing rules-based order, alliances, and democratic values."
        ),
        AgentVoice(
            perspective=Perspective.BEIJING,
            name="Beijing Agent",
            bias_keywords=["china", "chinese", "beijing", "prc", "one china"],
            priority_topics=["south china sea", "taiwan", "belt and road", "development"],
            knowledge_subset="jurisdiction:China OR source:chinese",
            system_prompt="You represent China's perspective, emphasizing historical claims, development rights, and non-interference."
        ),
        AgentVoice(
            perspective=Perspective.INTERNATIONAL_LAW,
            name="International Law Agent",
            bias_keywords=["unclos", "icj", "treaty", "convention", "international law"],
            priority_topics=["territorial waters", "eez", "continental shelf", "customary law"],
            knowledge_subset="source:legal OR type:treaty",
            system_prompt="You represent international legal norms, applying UNCLOS, ICJ rulings, and established treaties objectively."
        ),
    ]
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.agents = [PerspectiveAgent(config, llm_client) for config in self.AGENT_CONFIGS]
    
    async def run_debate(
        self,
        query: str,
        context: List[Dict],
        rounds: int = 2,
        perspectives: List[Perspective] = None
    ) -> DebateResult:
        """
        Run a multi-round debate on a query.
        Each agent generates a position, then responds to others.
        """
        # Filter agents if specific perspectives requested
        active_agents = self.agents
        if perspectives:
            active_agents = [a for a in self.agents if a.voice.perspective in perspectives]
        
        all_points = []
        
        # Round 1: Initial positions
        positions_r1 = await asyncio.gather(*[
            agent.generate_position(query, context, [])
            for agent in active_agents
        ])
        all_points.extend(positions_r1)
        
        # Round 2+: Counter-arguments
        for round_num in range(1, rounds):
            positions_rn = await asyncio.gather(*[
                agent.generate_position(query, context, all_points)
                for agent in active_agents
            ])
            all_points.extend(positions_rn)
        
        # Analyze debate
        conflicts = self._identify_conflicts(all_points)
        grey_areas = self._identify_grey_areas(all_points)
        consensus = self._find_consensus(all_points)
        recommendation = self._generate_recommendation(all_points, conflicts, grey_areas)
        
        overall_confidence = sum(p.confidence for p in all_points) / len(all_points)
        
        return DebateResult(
            query=query,
            points=all_points,
            consensus=consensus,
            conflicts=conflicts,
            grey_areas=grey_areas,
            recommendation=recommendation,
            confidence=overall_confidence
        )
    
    def _identify_conflicts(self, points: List[DebatePoint]) -> List[Dict]:
        """Identify conflicting positions."""
        conflicts = []
        
        for i, p1 in enumerate(points):
            for p2 in points[i+1:]:
                if p1.perspective != p2.perspective and p2.agent in p1.counters:
                    conflicts.append({
                        "agents": [p1.agent, p2.agent],
                        "perspectives": [p1.perspective.value, p2.perspective.value],
                        "nature": "opposing_positions",
                        "p1_excerpt": p1.position[:200],
                        "p2_excerpt": p2.position[:200]
                    })
        
        return conflicts
    
    def _identify_grey_areas(self, points: List[DebatePoint]) -> List[str]:
        """Identify grey areas where no clear consensus exists."""
        grey_areas = []
        
        # Low confidence across all agents
        if all(p.confidence < 0.6 for p in points):
            grey_areas.append("All perspectives show uncertainty - insufficient evidence")
        
        # High conflict count
        perspectives = set(p.perspective for p in points)
        counters = sum(len(p.counters) for p in points)
        if counters > len(perspectives):
            grey_areas.append("Multiple perspectives in direct opposition - diplomatic grey area")
        
        # Check for specific grey area topics
        combined_text = " ".join(p.position.lower() for p in points)
        grey_topics = [
            ("south china sea", "maritime boundary", "Contested maritime boundaries"),
            ("kashmir", "disputed", "Contested territorial claims"),
            ("taiwan", "one china", "Cross-strait status ambiguity"),
            ("sanction", "enforcement", "Sanctions enforcement variability")
        ]
        
        for t1, t2, label in grey_topics:
            if t1 in combined_text and t2 in combined_text:
                grey_areas.append(label)
        
        return list(set(grey_areas))
    
    def _find_consensus(self, points: List[DebatePoint]) -> Optional[str]:
        """Find areas of consensus across perspectives."""
        if not points:
            return None
        
        # Simple heuristic: find common phrases
        # In production, use semantic similarity
        all_text = " ".join(p.position for p in points)
        
        # Check for agreement markers
        agreement_phrases = [
            "all parties agree",
            "universally recognized",
            "established principle",
            "common ground"
        ]
        
        for phrase in agreement_phrases:
            if phrase in all_text.lower():
                return f"Consensus exists on: {phrase}"
        
        # No clear consensus
        return None
    
    def _generate_recommendation(
        self, 
        points: List[DebatePoint],
        conflicts: List[Dict],
        grey_areas: List[str]
    ) -> str:
        """Generate balanced recommendation acknowledging multiple perspectives."""
        if not points:
            return "Insufficient perspectives to generate recommendation."
        
        if grey_areas:
            return (
                f"**Grey Area Detected**: This query involves {len(grey_areas)} area(s) of "
                f"diplomatic ambiguity: {'; '.join(grey_areas)}. "
                f"Rather than providing a single biased answer, I present {len(points)} "
                f"perspectives with their supporting evidence. "
                f"The user should consider multiple viewpoints when analyzing this issue."
            )
        
        if conflicts:
            return (
                f"**Conflicting Perspectives**: {len(conflicts)} significant disagreements were "
                f"identified between perspectives. This reflects genuine diplomatic tensions "
                f"rather than factual uncertainty. Each perspective is grounded in its "
                f"respective knowledge base and priorities."
            )
        
        # If relative consensus
        high_conf_points = [p for p in points if p.confidence > 0.7]
        if len(high_conf_points) >= len(points) / 2:
            return (
                "Moderate consensus exists across perspectives. The presented analysis "
                "reflects areas of agreement while noting specific differences."
            )
        
        return "Analysis complete. Multiple perspectives presented for user consideration."


class SimulationRunner:
    """
    High-level interface for running perspective simulations.
    """
    
    def __init__(self, llm_client=None):
        self.orchestrator = DebateOrchestrator(llm_client)
    
    async def simulate(
        self,
        query: str,
        context: List[Dict],
        mode: str = "full"  # "full", "binary", "legal"
    ) -> Dict[str, Any]:
        """
        Run a simulation with configurable modes.
        
        - full: All perspectives
        - binary: Two opposing perspectives
        - legal: Legal vs political perspectives
        """
        if mode == "binary":
            # Auto-detect relevant opposing perspectives
            perspectives = self._detect_opposing_pair(query)
        elif mode == "legal":
            perspectives = [Perspective.INTERNATIONAL_LAW, Perspective.NEW_DELHI]
        else:
            perspectives = None  # All
        
        result = await self.orchestrator.run_debate(query, context, perspectives=perspectives)
        
        return {
            "query": result.query,
            "mode": mode,
            "perspectives_count": len(result.points),
            "consensus": result.consensus,
            "conflicts_count": len(result.conflicts),
            "grey_areas": result.grey_areas,
            "recommendation": result.recommendation,
            "confidence": result.confidence,
            "full_debate": [
                {
                    "agent": p.agent,
                    "perspective": p.perspective.value,
                    "position": p.position,
                    "confidence": p.confidence
                }
                for p in result.points
            ]
        }
    
    def _detect_opposing_pair(self, query: str) -> List[Perspective]:
        """Detect the two most relevant opposing perspectives."""
        query_lower = query.lower()
        
        pairs = [
            (["india", "pakistan", "kashmir", "loc"], [Perspective.NEW_DELHI, Perspective.NEUTRAL]),
            (["china", "taiwan", "south china sea"], [Perspective.BEIJING, Perspective.WASHINGTON]),
            (["russia", "ukraine", "nato"], [Perspective.MOSCOW, Perspective.BRUSSELS]),
            (["us", "america", "iran", "sanction"], [Perspective.WASHINGTON, Perspective.NEUTRAL])
        ]
        
        for keywords, perspectives in pairs:
            if any(kw in query_lower for kw in keywords):
                return perspectives
        
        # Default to India-US perspectives
        return [Perspective.NEW_DELHI, Perspective.WASHINGTON]


# Singleton instance
simulation_runner = SimulationRunner()
