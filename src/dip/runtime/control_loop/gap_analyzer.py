from typing import List, Dict, Any
from dataclasses import dataclass
from dip.core.schema import StateContext

@dataclass
class IdentifiedGap:
    """A gap identified by the control loop's gap analyzer (distinct from core.schema.IntelligenceGap)."""
    type: str  # e.g., 'EVIDENCE_SHORTAGE', 'MISSING_DOMAIN', 'EXPLICIT_GAP'
    description: str
    priority: str
    target_domains: List[str]

def analyze_gaps(state_context: StateContext, goal: Any) -> List[IdentifiedGap]:
    """
    Compares the investigation goal and expected blueprints against the
    current World Model (StateContext) to find explicitly missing elements.
    """
    gaps: List[IdentifiedGap] = []
    
    signals = state_context.current_signals
    signal_count = len(signals)
    topic = getattr(goal, 'objective', getattr(goal, 'topic', 'the query'))
    target = getattr(goal, 'country', getattr(goal, 'target_country', 'target area'))
    required_domains = set(getattr(goal, 'domains', []))
    
    # 1. Evidence Shortage Gap
    if signal_count < 12:
        gaps.append(IdentifiedGap(
            type='EVIDENCE_SHORTAGE',
            description=f"Insufficient overall evidence volume for {topic} in {target}. Found {signal_count} signals.",
            priority='HIGH',
            target_domains=list(required_domains) if required_domains else ["political", "economic", "military"]
        ))
        
    # 2. Missing Domains Gap
    found_domains = set()
    for sig in signals:
        if hasattr(sig, 'domain'):
            found_domains.add(sig.domain)
        elif hasattr(sig, 'metadata') and 'domain' in sig.metadata:
            found_domains.add(sig.metadata['domain'])
            
    missing_domains = required_domains - found_domains
    for md in missing_domains:
        gaps.append(IdentifiedGap(
            type='MISSING_DOMAIN',
            description=f"No intelligence found covering the expected '{md}' domain.",
            priority='MEDIUM',
            target_domains=[md]
        ))
        
    # 3. Explicit Gaps identified by Layer 2/3
    for gap in getattr(state_context, 'intelligence_gaps', []):
        desc = getattr(gap, 'description', getattr(gap, 'missing_information', str(gap)))
        domain = getattr(gap, 'domain', 'unknown')
        gaps.append(IdentifiedGap(
            type='EXPLICIT_GAP',
            description=f"Unresolved intelligence gap: {desc}",
            priority='LOW',
            target_domains=[domain]
        ))
        
    return gaps
