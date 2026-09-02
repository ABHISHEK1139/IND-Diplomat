"""
Phase 8: Groupthink Detection Engine.

Quantitatively measures whether the 7-agent council is exhibiting groupthink.
7/7 agreement does NOT automatically mean high confidence if they all
copied the same evidence.

Metrics:
  - Agreement Score: How many agents agree on the same state?
  - Evidence Diversity: Are agents citing different evidence, or the same set?
  - Independent Reasoning Similarity: Are their reasoning chains similar?
  - Contrarian Strength: Did the Red Team land any unresolved challenges?
  - Minority Opinion Strength: How strong is the dissenting view?
"""

import logging
from typing import Dict, List, Tuple
from collections import Counter

from dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from dip.pipeline.deliberation.reasoning.schema import AgentMessage, MessageType

logger = logging.getLogger("Layer4.GroupthinkDetector")


class GroupthinkDetector:
    """
    Reads the Debate Memory and Belief Ledgers to compute a
    Groupthink Risk Score (0.0 = healthy divergence, 1.0 = dangerous groupthink).
    """

    def __init__(self, message_bus: MessageBus):
        self.bus = message_bus

    def compute_agreement_score(self) -> float:
        """
        What fraction of agents agree on the dominant state?
        Returns 0.0-1.0. Higher = more agreement.
        """
        if not self.bus.agent_memory:
            return 0.0

        state_votes: List[str] = []
        for agent, ledgers in self.bus.agent_memory.items():
            if ledgers and ledgers[-1].beliefs:
                # Take the agent's highest-probability belief
                best = max(ledgers[-1].beliefs, key=lambda b: b.probability)
                state_votes.append(best.state)

        if not state_votes:
            return 0.0

        counter = Counter(state_votes)
        dominant_count = counter.most_common(1)[0][1]
        return dominant_count / len(state_votes)

    def compute_evidence_diversity(self) -> float:
        """
        How many unique evidence IDs are cited across all HYPOTHESIS messages?
        Low diversity = agents are copying each other.
        Returns 0.0-1.0. Higher = more diverse (healthier).
        """
        all_evidence: List[str] = []
        per_agent_evidence: Dict[str, set] = {}

        for msg in self.bus.debate_memory:
            if msg.message_type == MessageType.HYPOTHESIS and msg.evidence_ids:
                all_evidence.extend(msg.evidence_ids)
                if msg.sender not in per_agent_evidence:
                    per_agent_evidence[msg.sender] = set()
                per_agent_evidence[msg.sender].update(msg.evidence_ids)

        if not all_evidence:
            return 0.0  # No evidence cited at all — bad sign

        unique = len(set(all_evidence))
        total = len(all_evidence)
        # Ratio of unique to total. If everyone cites the same 3 items, this is low.
        return min(unique / max(total, 1), 1.0)

    def compute_contrarian_strength(self) -> float:
        """
        How effective was the Red Team?
        Returns 0.0-1.0. Higher = Contrarian was effective (healthy).
        """
        challenges = [m for m in self.bus.debate_memory if m.message_type == MessageType.CHALLENGE]
        rebuttals = [m for m in self.bus.debate_memory if m.message_type == MessageType.REBUTTAL]

        if not challenges:
            return 0.0  # No challenges = Red Team didn't engage

        # Unresolved challenges indicate the Red Team won on those points
        unresolved = max(0, len(challenges) - len(rebuttals))
        return unresolved / len(challenges)

    def compute_probability_spread(self) -> float:
        """
        What is the standard deviation of agent probabilities?
        Low spread = they all converged to the same number (suspicious).
        Returns 0.0-1.0 (normalized). Higher = more spread (healthier).
        """
        probs: List[float] = []
        for agent, ledgers in self.bus.agent_memory.items():
            if ledgers and ledgers[-1].beliefs:
                best = max(ledgers[-1].beliefs, key=lambda b: b.probability)
                probs.append(best.probability)

        if len(probs) < 2:
            return 0.0

        mean = sum(probs) / len(probs)
        variance = sum((p - mean) ** 2 for p in probs) / len(probs)
        std = variance ** 0.5
        # Normalize: std of 0.0 = total agreement, std of 0.5 = max reasonable spread
        return min(std / 0.5, 1.0)

    def compute_source_diversity(self) -> float:
        """
        How many unique raw SOURCES are behind the cited evidence?
        Returns 0.0-1.0. Higher = more diverse sources (healthier).
        """
        sources_cited = []
        for msg in self.bus.debate_memory:
            if msg.message_type == MessageType.HYPOTHESIS and msg.evidence_ids:
                for eid in msg.evidence_ids:
                    ev = self.bus.evidence_memory.get(eid)
                    if ev:
                        sources_cited.append(ev.source)
        if not sources_cited:
            return 0.0
            
        unique = len(set(sources_cited))
        total = len(sources_cited)
        return min(unique / max(total, 1), 1.0)

    def compute_argument_diversity(self) -> float:
        """
        Are the reasoning summaries textually similar? (Jaccard similarity approximation)
        Returns 0.0-1.0. Higher = more diverse arguments (healthier).
        """
        summaries = [msg.reasoning_summary for msg in self.bus.debate_memory if msg.message_type == MessageType.HYPOTHESIS]
        if len(summaries) < 2:
            return 1.0
            
        # Basic bag of words intersection
        words_sets = [set(s.lower().split()) for s in summaries]
        similarities = []
        for i in range(len(words_sets)):
            for j in range(i+1, len(words_sets)):
                s1, s2 = words_sets[i], words_sets[j]
                if not s1 or not s2:
                    continue
                iou = len(s1.intersection(s2)) / len(s1.union(s2))
                similarities.append(iou)
                
        if not similarities:
            return 1.0
            
        avg_similarity = sum(similarities) / len(similarities)
        return 1.0 - avg_similarity  # Invert: higher diversity = lower similarity

    def evaluate(self) -> Dict:
        """
        Returns a full Groupthink Assessment.
        """
        agreement = self.compute_agreement_score()
        evidence_div = self.compute_evidence_diversity()
        source_div = self.compute_source_diversity()
        contrarian = self.compute_contrarian_strength()
        spread = self.compute_probability_spread()
        argument_div = self.compute_argument_diversity()

        # Groupthink Risk: High agreement + low div (evidence/source/argument) + weak contrarian + low spread
        risk = (
            0.30 * agreement
            + 0.15 * (1.0 - evidence_div)
            + 0.15 * (1.0 - source_div)
            + 0.10 * (1.0 - argument_div)
            + 0.15 * (1.0 - contrarian)
            + 0.15 * (1.0 - spread)
        )

        result = {
            "agreement_score": round(agreement, 3),
            "evidence_diversity": round(evidence_div, 3),
            "source_diversity": round(source_div, 3),
            "argument_diversity": round(argument_div, 3),
            "contrarian_strength": round(contrarian, 3),
            "probability_spread": round(spread, 3),
            "groupthink_risk": round(risk, 3),
            "warning": risk > 0.70,
        }

        if result["warning"]:
            logger.warning(
                f"[GroupthinkDetector] HIGH GROUPTHINK RISK: {result['groupthink_risk']}"
            )
        else:
            logger.info(
                f"[GroupthinkDetector] Groupthink risk: {result['groupthink_risk']}"
            )

        return result
