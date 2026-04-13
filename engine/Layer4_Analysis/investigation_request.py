"""
The Investigation Request.
Structured feedback signal from Layer-4 to the Controller.
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class InvestigationRequest:
    """
    Feedback object returned by Layer-4 when evidence is insufficient.
    """
    session_id: str
    needed_information: List[str]
    priority: str = "HIGH"
    reason: str = "Insufficient evidence to distinguish hypotheses."
    
    # Context (Entities involved)
    subject_country: Optional[str] = None
    target_country: Optional[str] = None

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "needed_information": self.needed_information,
            "priority": self.priority,
            "reason": self.reason,
            "subject": self.subject_country,
            "target": self.target_country
        }
