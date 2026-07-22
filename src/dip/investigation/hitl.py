"""
Human-in-the-Loop (HITL): Escalation for senior analyst review.

Triggered when the assessment reaches HIGH threat level but has low
verification confidence. This ensures that high-stakes assessments
with shaky evidence get human oversight before dissemination.
"""

from typing import Dict, Any


def request_review(session) -> Dict[str, Any]:
    """
    Escalate the session for human review. Sets session.status to 'HUMAN_REVIEW'.
    Returns a structured review request for the human analyst.
    """
    session.status = "HUMAN_REVIEW"

    # Compile the review package for the human analyst
    hypothesis_summary = []
    for h in session.hypotheses:
        hypothesis_summary.append({
            "minister": h.minister,
            "type": h.hypothesis_type,
            "confidence": h.confidence,
            "matched_signals": h.matched_signals,
            "missing_signals": h.missing_signals,
        })

    review_package = {
        "status": "HUMAN_REVIEW",
        "priority": "URGENT" if session.verification_score < 0.3 else "HIGH",
        "reason": (
            f"HIGH threat assessment detected with low verification score "
            f"({session.verification_score}). Senior analyst review required "
            f"before dissemination."
        ),
        "query": session.query,
        "country": session.state_context.country,
        "threat_decision": session.final_decision,
        "verification_score": session.verification_score,
        "hypotheses": hypothesis_summary,
        "evidence_log": session.evidence_log,
        "red_team_report": session.red_team_report or [],
        "action_required": [
            "Review all minister hypotheses for analytical soundness.",
            "Validate evidence log entries against primary sources.",
            "Confirm or override the threat level assessment.",
            "Approve for dissemination or return for additional investigation.",
        ],
    }

    return review_package
