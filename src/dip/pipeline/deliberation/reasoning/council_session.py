from typing import List, Optional
from dip.core.schema import StateContext, Hypothesis, AssessmentDecision

class CouncilSession:
    """
    The strict state object that all Layer-4 components must read from and write to.
    Direct communication between agents or bypassing this session is forbidden.
    """
    def __init__(self, query: str, state_context: StateContext):
        self.query = query
        self.state_context = state_context
        self.working_memory = None
        
        # Minister Stage
        self.hypotheses: List[Hypothesis] = []
        
        # Debate Stage
        self.conflicts: List[str] = []
        self.red_team_report: Optional[List[str]] = None
        
        # Investigation Stage
        self.missing_signals: List[str] = []
        self.evidence_log: List[str] = []
        
        # Decision Stage
        self.final_decision: Optional[str] = None
        self.verification_score: float = 0.0
        self.status: str = "ONGOING"
        
        # Introspection Stage
        self.introspection_report: Optional[str] = None
