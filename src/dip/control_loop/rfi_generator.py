from typing import List, Any
from dip.core.schema import RFIQuery
from .gap_analyzer import IdentifiedGap

def generate_rfis(gaps: List[IdentifiedGap], topic: str, target: str) -> List[RFIQuery]:
    """
    Converts analyzed intelligence gaps into executable Request For Information (RFI) objects,
    complete with priority, target domains, and estimated costs.
    """
    rfis = []
    
    for gap in gaps:
        if gap.type == 'EVIDENCE_SHORTAGE':
            rfis.append(RFIQuery(
                query=f"Find recent events, conflicts, or significant strategic developments regarding {topic} in {target}.",
                target_domains=gap.target_domains,
                priority=gap.priority,
                estimated_time_mins=3.5,
                estimated_tokens=65000,
                estimated_cost_usd=0.31,
                justification=gap.description
            ))
        elif gap.type == 'MISSING_DOMAIN':
            md = gap.target_domains[0] if gap.target_domains else "general"
            rfis.append(RFIQuery(
                query=f"Retrieve recent intelligence reports on {md} sector in relation to {topic}.",
                target_domains=gap.target_domains,
                priority=gap.priority,
                estimated_time_mins=2.0,
                estimated_tokens=20000,
                estimated_cost_usd=0.10,
                justification=gap.description
            ))
        elif gap.type == 'EXPLICIT_GAP':
            rfis.append(RFIQuery(
                query=f"Investigate intelligence gap: {gap.description}",
                target_domains=gap.target_domains,
                priority=gap.priority,
                estimated_time_mins=5.0,
                estimated_tokens=80000,
                estimated_cost_usd=0.45,
                justification=gap.description
            ))
            
    # Group similar RFIs or sort them (highest priority first)
    priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
    rfis.sort(key=lambda x: priority_order.get(x.priority, 99))
    
    return rfis
